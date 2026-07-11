from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from api.auth import authenticate_candidate, create_access_token, hash_password
from api.deps import get_db
from api.schemas import CandidateLoginRequest, CandidateSignupRequest, TokenResponse
from config.schema import slugify_name
from db.models import Candidate, Organization
from services.rate_limit import check_not_locked, record_failure, record_success
from services.status_service import TRIAL, get_status_by_code

router = APIRouter(prefix="/api/candidate-auth", tags=["candidate-auth"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: CandidateSignupRequest, db: Session = Depends(get_db)):
    login_email = payload.login_email.strip().lower()

    existing = db.query(Candidate).filter_by(login_email=login_email).one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    if len(payload.password) < 10:
        raise HTTPException(status_code=422, detail="Password must be at least 10 characters")

    org_name = payload.organization_name.strip()
    org = db.query(Organization).filter_by(name=org_name).one_or_none()
    if org is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No organization named '{org_name}' found. Double-check the exact name your "
                f"recruiter registered under, or ask them to confirm it -- candidate signup "
                f"joins an existing organization, it doesn't create one."
            ),
        )

    slug = slugify_name(payload.full_name)
    slug_conflict = db.query(Candidate).filter_by(organization_id=org.id, slug=slug).one_or_none()
    if slug_conflict:
        raise HTTPException(
            status_code=409,
            detail=(
                f"A candidate with a matching name/slug ('{slug}') already exists in "
                f"'{org_name}'. Contact your recruiter if this is you and you're locked out."
            ),
        )

    candidate = Candidate(
        organization_id=org.id,
        slug=slug,
        full_name=payload.full_name,
        login_email=login_email,
        password_hash=hash_password(payload.password),
        profile_status="no_account",  # not yet submitted a profile
        status_id=get_status_by_code(db, TRIAL).id,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    token = create_access_token(login_email, role="candidate", extra_claims={"candidate_id": candidate.id})
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(payload: CandidateLoginRequest, db: Session = Depends(get_db)):
    account_key = f"candidate:{payload.login_email.strip().lower()}"
    check_not_locked(db, account_key)

    existing = db.query(Candidate).filter_by(login_email=payload.login_email.strip().lower()).one_or_none()
    org = db.query(Organization).filter_by(id=existing.organization_id).one_or_none() if existing else None
    from services.rate_limit import LOCKOUT_MINUTES, MAX_FAILED_ATTEMPTS

    max_attempts = org.max_failed_login_attempts if org else MAX_FAILED_ATTEMPTS
    lockout_minutes = org.lockout_minutes if org else LOCKOUT_MINUTES

    candidate = authenticate_candidate(db, payload.login_email, payload.password)
    if not candidate:
        record_failure(db, account_key, max_attempts, lockout_minutes)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    record_success(db, account_key)
    token = create_access_token(candidate.login_email, role="candidate", extra_claims={"candidate_id": candidate.id})
    return TokenResponse(access_token=token)


class CandidateForgotPasswordRequest(BaseModel):
    login_email: EmailStr


class CandidateResetPasswordRequest(BaseModel):
    login_email: EmailStr
    otp: str
    new_password: str


@router.post("/forgot-password")
def forgot_password(payload: CandidateForgotPasswordRequest, db: Session = Depends(get_db)):
    from services.email_sender import send_password_reset_email
    from services.password_reset import create_reset_token

    candidate = db.query(Candidate).filter_by(login_email=payload.login_email.strip().lower()).one_or_none()
    if candidate is not None:
        otp = create_reset_token(db, "candidate", candidate.id)
        send_password_reset_email(candidate.login_email, otp)
    return {"message": "If an account exists for that email, a reset code has been sent."}


@router.post("/reset-password", response_model=TokenResponse)
def reset_password(payload: CandidateResetPasswordRequest, db: Session = Depends(get_db)):
    from services.password_reset import redeem_reset_token

    login_email = payload.login_email.strip().lower()
    candidate = db.query(Candidate).filter_by(login_email=login_email).one_or_none()
    if candidate is None:
        raise HTTPException(status_code=404, detail="No pending password reset request found.")

    redeem_reset_token(db, "candidate", candidate.id, payload.otp, payload.new_password)
    token = create_access_token(login_email, role="candidate", extra_claims={"candidate_id": candidate.id})
    return TokenResponse(access_token=token)
