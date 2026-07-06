"""
Redeeming an invite. The registrant supplies email + OTP + password
(+ role-specific fields); the role and organization come from the
Invite row itself, never from what the registrant types -- see
services/invite_service.py's docstring for why that matters.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from api.auth import create_access_token, hash_password, verify_otp
from api.deps import get_db
from api.schemas import TokenResponse
from config.schema import slugify_name
from db.models import AdminUser, Candidate, Invite, Organization

router = APIRouter(prefix="/api/invite", tags=["invite"])


class InviteRegisterRequest(BaseModel):
    email: EmailStr
    otp: str
    password: str
    # Role-specific -- only one of these is required depending on the
    # invite's role, validated after the invite is looked up.
    username: str | None = None  # for admin invites
    full_name: str | None = None  # for candidate invites


@router.post("/register", response_model=TokenResponse)
def register_via_invite(payload: InviteRegisterRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()

    invite = (
        db.query(Invite)
        .filter_by(email=email, used_at=None)
        .order_by(Invite.created_at.desc())
        .first()
    )
    if invite is None:
        raise HTTPException(status_code=404, detail="No pending invite found for this email.")

    expires_at = invite.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="This invite has expired. Ask for a new one.")

    if invite.attempts >= invite.max_attempts:
        raise HTTPException(
            status_code=429,
            detail="Too many incorrect codes entered for this invite. Ask for a new one.",
        )

    if not verify_otp(payload.otp, invite.otp_hash):
        invite.attempts += 1
        db.commit()
        remaining = invite.max_attempts - invite.attempts
        raise HTTPException(
            status_code=401,
            detail=f"Incorrect code. {remaining} attempt{'s' if remaining != 1 else ''} remaining.",
        )

    if len(payload.password) < 10:
        raise HTTPException(status_code=422, detail="Password must be at least 10 characters.")

    if invite.role == "admin":
        if not payload.username:
            raise HTTPException(status_code=422, detail="username is required for an admin invite.")
        if db.query(AdminUser).filter_by(username=payload.username).one_or_none():
            raise HTTPException(status_code=409, detail="An admin with this username already exists.")

        org = db.query(Organization).filter_by(id=invite.organization_id).one()
        linked_candidate_id = None

        if org.account_type == "individual":
            # This person IS both admin and candidate -- one login,
            # linked to their own Candidate row. See
            # api/deps.py::get_current_candidate for how the same admin
            # token then also authorizes candidate self-service actions.
            if not payload.full_name:
                raise HTTPException(
                    status_code=422,
                    detail="full_name is required for an individual account (used for your candidate profile).",
                )
            slug = slugify_name(payload.full_name)
            if db.query(Candidate).filter_by(organization_id=org.id, slug=slug).one_or_none():
                raise HTTPException(status_code=409, detail=f"A candidate slug conflict occurred ('{slug}').")

            linked_candidate = Candidate(
                organization_id=org.id,
                slug=slug,
                full_name=payload.full_name,
                login_email=email,
                profile_status="no_account",
            )
            db.add(linked_candidate)
            db.flush()
            linked_candidate_id = linked_candidate.id

        account = AdminUser(
            organization_id=invite.organization_id,
            username=payload.username,
            email=email,
            password_hash=hash_password(payload.password),
            linked_candidate_id=linked_candidate_id,
        )
        db.add(account)
        db.flush()
        invite.used_at = datetime.now(timezone.utc)
        db.commit()

        extra_claims = {"linked_candidate_id": linked_candidate_id} if linked_candidate_id else None
        token = create_access_token(account.username, role="admin", extra_claims=extra_claims)
        return TokenResponse(access_token=token)

    elif invite.role == "candidate":
        if not payload.full_name:
            raise HTTPException(status_code=422, detail="full_name is required for a candidate invite.")
        if db.query(Candidate).filter_by(login_email=email).one_or_none():
            raise HTTPException(status_code=409, detail="An account with this email already exists.")

        slug = slugify_name(payload.full_name)
        if db.query(Candidate).filter_by(organization_id=invite.organization_id, slug=slug).one_or_none():
            raise HTTPException(
                status_code=409,
                detail=f"A candidate with a matching name/slug ('{slug}') already exists in this organization.",
            )

        account = Candidate(
            organization_id=invite.organization_id,
            slug=slug,
            full_name=payload.full_name,
            login_email=email,
            password_hash=hash_password(payload.password),
            profile_status="no_account",
        )
        db.add(account)
        db.flush()
        invite.used_at = datetime.now(timezone.utc)
        db.commit()

        token = create_access_token(email, role="candidate", extra_claims={"candidate_id": account.id})
        return TokenResponse(access_token=token)

    raise HTTPException(status_code=500, detail=f"Invite has an unrecognized role: {invite.role}")
