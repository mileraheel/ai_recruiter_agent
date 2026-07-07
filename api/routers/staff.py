from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from api.deps import get_current_staff, get_db
from db.models import AdminUser, Candidate, Job, Organization, Staff
from services.email_sender import send_invite_email
from services.invite_service import create_invite
from services.trial_service import DEFAULT_TRIAL_DAYS, days_remaining, set_organization_trial

router = APIRouter(prefix="/api/staff", tags=["staff"], dependencies=[Depends(get_current_staff)])


class InviteOrganizationRequest(BaseModel):
    organization_name: str
    admin_email: EmailStr
    account_type: str = "agency"  # "agency" | "individual"
    trial_days: int | None = DEFAULT_TRIAL_DAYS  # None means no trial expiry


class InviteOrganizationResponse(BaseModel):
    organization_id: int
    organization_name: str
    invited_email: str
    trial_expires_at: str | None = None


@router.post("/invite-organization", response_model=InviteOrganizationResponse)
def invite_organization(
    payload: InviteOrganizationRequest,
    db: Session = Depends(get_db),
    staff: Staff = Depends(get_current_staff),
):
    org_name = payload.organization_name.strip()
    if db.query(Organization).filter_by(name=org_name).one_or_none():
        raise HTTPException(status_code=409, detail=f"An organization named '{org_name}' already exists.")

    if payload.account_type not in ("agency", "individual"):
        raise HTTPException(status_code=422, detail="account_type must be 'agency' or 'individual'.")
    if payload.trial_days is not None and payload.trial_days < 0:
        raise HTTPException(status_code=422, detail="trial_days must be zero or positive (or omitted for no trial).")

    org = Organization(name=org_name, created_by_staff_id=staff.id, account_type=payload.account_type)
    set_organization_trial(db, org, payload.trial_days)
    db.add(org)
    db.flush()

    invite, otp = create_invite(
        db, email=payload.admin_email, role="admin", organization_id=org.id,
        invited_by_type="staff", invited_by_id=staff.id,
    )

    from services.platform_settings_service import get_or_create_platform_settings

    settings = get_or_create_platform_settings(db)
    try:
        send_invite_email(payload.admin_email, otp, "admin", org_name, settings.invite_expire_days)
    except RuntimeError as e:
        # Org + invite are already committed -- surface the SMTP failure
        # clearly rather than silently leaving the admin with no way to
        # know their code, but don't roll back the org/invite (a resend
        # mechanism, not rebuilt from scratch, is the fix).
        raise HTTPException(status_code=502, detail=f"Organization created, but invite email failed to send: {e}")

    return InviteOrganizationResponse(
        organization_id=org.id,
        organization_name=org.name,
        invited_email=payload.admin_email,
        trial_expires_at=org.trial_expires_at.isoformat() if org.trial_expires_at else None,
    )


class StaffOrganizationSummary(BaseModel):
    organization_id: int
    organization_name: str
    account_type: str
    is_active: bool
    candidate_count: int
    admin_count: int
    jobs_posted: int
    created_at: str
    trial_expires_at: str | None = None
    trial_days_remaining: int | None = None


@router.get("/organizations", response_model=list[StaffOrganizationSummary])
def list_my_organizations(db: Session = Depends(get_db), staff: Staff = Depends(get_current_staff)):
    """Orgs THIS staff member created -- their own onboarding activity,
    the basis for sales-performance / future revenue attribution."""
    orgs = db.query(Organization).filter_by(created_by_staff_id=staff.id).order_by(Organization.created_at.desc()).all()
    results = []
    for org in orgs:
        results.append(
            StaffOrganizationSummary(
                organization_id=org.id,
                organization_name=org.name,
                account_type=org.account_type,
                is_active=org.is_active,
                candidate_count=db.query(Candidate).filter_by(organization_id=org.id).count(),
                admin_count=db.query(AdminUser).filter_by(organization_id=org.id).count(),
                jobs_posted=db.query(Job).filter_by(organization_id=org.id).count(),
                created_at=org.created_at.isoformat(),
                trial_expires_at=org.trial_expires_at.isoformat() if org.trial_expires_at else None,
                trial_days_remaining=days_remaining(org.trial_expires_at),
            )
        )
    return results


@router.delete("/organizations/{organization_id}")
def deactivate_organization(
    organization_id: int, db: Session = Depends(get_db), staff: Staff = Depends(get_current_staff)
):
    org = db.query(Organization).filter_by(id=organization_id).one_or_none()
    if org is None or org.created_by_staff_id != staff.id:
        # Same response whether it doesn't exist or belongs to another
        # staff member's onboarding -- a staff member can only act on
        # organizations they personally created.
        raise HTTPException(status_code=404, detail="Organization not found.")

    org.is_active = False
    db.commit()
    return {"organization_id": org.id, "is_active": False}
