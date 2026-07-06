from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from api.auth import authenticate_admin, create_access_token, hash_password
from api.deps import get_db
from api.schemas import TokenResponse
from db.models import AdminUser, Organization
from services.rate_limit import check_not_locked, record_failure, record_success

router = APIRouter(prefix="/api/auth", tags=["auth"])


class AdminSignupRequest(BaseModel):
    username: str
    password: str
    organization_name: str
    email: EmailStr | None = None  # optional but strongly recommended -- required for self-service password reset


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: AdminSignupRequest, db: Session = Depends(get_db)):
    """Self-signup ALWAYS creates a brand new organization -- there is
    no path for an admin to join an existing org by typing its name.
    An admin has full visibility into every candidate's PII in their
    org (passport numbers, rates, resumes), so letting a stranger join
    an existing org by guessing/knowing its name would be a serious
    access-control gap. Adding a second admin to an existing org is a
    deliberate future 'invite teammate' feature, not open signup."""
    org_name = payload.organization_name.strip()
    if not org_name:
        raise HTTPException(status_code=422, detail="Organization name is required.")

    existing_org = db.query(Organization).filter_by(name=org_name).one_or_none()
    if existing_org:
        raise HTTPException(
            status_code=409,
            detail=(
                f"An organization named '{org_name}' already exists. If this is your "
                f"company, ask an existing admin there to add you -- self-signup can't "
                f"join an existing organization."
            ),
        )

    if db.query(AdminUser).filter_by(username=payload.username).one_or_none():
        raise HTTPException(status_code=409, detail="An admin with this username already exists.")

    if len(payload.password) < 10:
        raise HTTPException(status_code=422, detail="Password must be at least 10 characters.")

    org = Organization(name=org_name)
    db.add(org)
    db.flush()

    admin = AdminUser(
        organization_id=org.id, username=payload.username, email=payload.email,
        password_hash=hash_password(payload.password),
    )
    db.add(admin)
    db.commit()

    token = create_access_token(admin.username, role="admin")
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    account_key = f"admin:{form_data.username.strip().lower()}"
    check_not_locked(db, account_key)

    # Looked up regardless of whether the password will verify, purely
    # to read this org's lockout policy -- doesn't change the response,
    # so it doesn't leak account existence to the caller.
    existing = db.query(AdminUser).filter_by(username=form_data.username).one_or_none()
    org = db.query(Organization).filter_by(id=existing.organization_id).one_or_none() if existing else None
    from services.rate_limit import LOCKOUT_MINUTES, MAX_FAILED_ATTEMPTS

    max_attempts = org.max_failed_login_attempts if org else MAX_FAILED_ATTEMPTS
    lockout_minutes = org.lockout_minutes if org else LOCKOUT_MINUTES

    user = authenticate_admin(db, form_data.username, form_data.password)
    if not user:
        record_failure(db, account_key, max_attempts, lockout_minutes)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    record_success(db, account_key)
    extra_claims = {"linked_candidate_id": user.linked_candidate_id} if user.linked_candidate_id else None
    token = create_access_token(user.username, role="admin", extra_claims=extra_claims)
    return TokenResponse(access_token=token)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    from services.email_sender import send_email
    from services.password_reset import create_reset_token

    account = db.query(AdminUser).filter_by(email=payload.email.strip().lower()).one_or_none()
    # Same response whether or not the email matches an account -- does
    # not confirm/deny account existence to whoever's asking.
    if account is not None:
        otp = create_reset_token(db, "admin", account.id)
        try:
            send_email(
                account.email, "Reset your password",
                f"Your password reset code is: {otp}\nThis code expires in 30 minutes.",
            )
        except RuntimeError:
            pass  # SMTP not configured -- fail quietly here too, same non-confirming response
    return {"message": "If an account exists for that email, a reset code has been sent."}


@router.post("/reset-password", response_model=TokenResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    from services.password_reset import redeem_reset_token

    account = db.query(AdminUser).filter_by(email=payload.email.strip().lower()).one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="No pending password reset request found.")

    redeem_reset_token(db, "admin", account.id, payload.otp, payload.new_password)
    token = create_access_token(account.username, role="admin")
    return TokenResponse(access_token=token)
