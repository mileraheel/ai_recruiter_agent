"""
Auth: single (or multi-) admin login, JWT bearer tokens.

Deliberately simple for a local, single-operator deployment today, but
structured so it's not a rewrite once this moves to a real deployment:
JWT secret and token expiry come from env vars, passwords are bcrypt
hashed (never stored/logged in plaintext), and admin accounts live in
the same Postgres DB that's already cloud-portable.

No hardcoded credentials anywhere -- first run requires creating an
admin via `python -m api.bootstrap_admin` (see that module), same
spirit as the rest of this repo's "nothing invented, nothing silently
defaulted" approach.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt
from sqlalchemy.orm import Session

import secrets

from db.models import AdminUser, Candidate, Staff, SuperUser

ALGORITHM = "HS256"
DEFAULT_EXPIRE_MINUTES = 60 * 12  # 12 hours
OTP_LENGTH = 6


def _jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET_KEY")
    if not secret:
        raise RuntimeError(
            "JWT_SECRET_KEY is not set. Generate one (e.g. `python -c "
            "\"import secrets; print(secrets.token_hex(32))\"`) and set it "
            "in your .env before starting the API -- there is no default, "
            "on purpose, since a default secret would make every "
            "deployment's tokens forgeable by anyone who read this file."
        )
    return secret


def hash_password(plain_password: str) -> str:
    # bcrypt has a hard 72-byte input limit -- truncate deliberately
    # (not silently) rather than let the library raise on a long
    # passphrase.
    pw_bytes = plain_password.encode("utf-8")[:72]
    return bcrypt.hashpw(pw_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    pw_bytes = plain_password.encode("utf-8")[:72]
    return bcrypt.checkpw(pw_bytes, password_hash.encode("utf-8"))


def authenticate_admin(session: Session, username: str, password: str) -> AdminUser | None:
    user = session.query(AdminUser).filter_by(username=username).one_or_none()
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def authenticate_superuser(session: Session, username: str, password: str) -> SuperUser | None:
    user = session.query(SuperUser).filter_by(username=username).one_or_none()
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def authenticate_staff(session: Session, username: str, password: str) -> Staff | None:
    user = session.query(Staff).filter_by(username=username, is_active=True).one_or_none()
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def generate_otp() -> str:
    """Cryptographically random 6-digit code -- secrets.randbelow, not
    random.randint, since this is a security token, not a UI toy."""
    return f"{secrets.randbelow(10**OTP_LENGTH):0{OTP_LENGTH}d}"


def hash_otp(otp: str) -> str:
    # Same bcrypt mechanism as passwords -- an OTP is a short-lived
    # secret too, and shouldn't sit in the DB in plaintext any more than
    # a password would.
    return hash_password(otp)


def verify_otp(otp: str, otp_hash: str) -> bool:
    return verify_password(otp, otp_hash)


def authenticate_candidate(session: Session, login_email: str, password: str) -> Candidate | None:
    candidate = session.query(Candidate).filter_by(login_email=login_email.strip().lower()).one_or_none()
    if candidate is None or not candidate.password_hash:
        return None
    if not verify_password(password, candidate.password_hash):
        return None
    return candidate


def create_access_token(
    subject: str, role: str, extra_claims: dict | None = None, expires_minutes: int = DEFAULT_EXPIRE_MINUTES
) -> str:
    """role: 'admin' | 'candidate'. extra_claims lets candidate tokens
    carry candidate_id so api/deps.py doesn't need a DB lookup by
    login_email on every request."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload = {"sub": subject, "role": role, "exp": expire, **(extra_claims or {})}
    return jwt.encode(payload, _jwt_secret(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Returns the full token payload (sub, role, and any extra claims).
    Raises JWTError (caught by the caller in api/deps.py) on any
    invalid/expired token, or on a token missing required claims."""
    payload = jwt.decode(token, _jwt_secret(), algorithms=[ALGORITHM])
    if not payload.get("sub") or not payload.get("role"):
        raise JWTError("Token missing required claims")
    return payload
