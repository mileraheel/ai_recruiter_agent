"""
Self-service password reset via OTP -- same mechanism as Invite
(bcrypt-hashed OTP, expiry, attempt limit) but for an EXISTING account.
Shared logic across all four account types (admin, candidate, staff,
superuser) -- account_type/account_id are supplied by the caller, which
is responsible for figuring out which table the identifying email
matched (see api/routers/auth.py's unified password-reset endpoints).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from api.auth import generate_otp, hash_otp, hash_password, verify_otp
from db.models import AdminUser, Candidate, PasswordResetToken, Staff, SuperUser

OTP_EXPIRE_MINUTES = 30


def _naive_to_utc(dt):
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def create_reset_token(session: Session, account_type: str, account_id: int) -> str:
    otp = generate_otp()
    token = PasswordResetToken(
        account_type=account_type,
        account_id=account_id,
        otp_hash=hash_otp(otp),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES),
    )
    session.add(token)
    session.commit()
    return otp


def redeem_reset_token(
    session: Session, account_type: str, account_id: int, otp: str, new_password: str
) -> None:
    """Raises HTTPException on any failure -- invalid/expired/exhausted
    token, or an account_id mismatch. Success updates the account's
    password_hash and marks the token used."""
    token = (
        session.query(PasswordResetToken)
        .filter_by(account_type=account_type, account_id=account_id, used_at=None)
        .order_by(PasswordResetToken.created_at.desc())
        .first()
    )
    if token is None:
        raise HTTPException(status_code=404, detail="No pending password reset request found.")

    if _naive_to_utc(token.expires_at) < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="This reset code has expired. Request a new one.")

    if token.attempts >= token.max_attempts:
        raise HTTPException(status_code=429, detail="Too many incorrect codes. Request a new one.")

    if not verify_otp(otp, token.otp_hash):
        token.attempts += 1
        session.commit()
        remaining = token.max_attempts - token.attempts
        raise HTTPException(
            status_code=401,
            detail=f"Incorrect code. {remaining} attempt{'s' if remaining != 1 else ''} remaining.",
        )

    if len(new_password) < 10:
        raise HTTPException(status_code=422, detail="Password must be at least 10 characters.")

    if account_type == "admin":
        account = session.query(AdminUser).filter_by(id=account_id).one_or_none()
    elif account_type == "candidate":
        account = session.query(Candidate).filter_by(id=account_id).one_or_none()
    elif account_type == "staff":
        account = session.query(Staff).filter_by(id=account_id).one_or_none()
    elif account_type == "superuser":
        account = session.query(SuperUser).filter_by(id=account_id).one_or_none()
    else:
        raise HTTPException(status_code=500, detail=f"Unknown account_type: {account_type}")

    if account is None:
        raise HTTPException(status_code=404, detail="Account not found.")

    account.password_hash = hash_password(new_password)
    token.used_at = datetime.now(timezone.utc)
    session.commit()
