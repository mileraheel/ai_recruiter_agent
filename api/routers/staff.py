from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from api.deps import get_current_staff, get_db
from db.models import AdminUser, Candidate, Job, Organization, Staff
from services.email_sender import send_invite_email
from services.invite_service import create_invite
from services.status_service import ACTIVE, TRIAL, get_status_by_code
from services.trial_service import (
    DEFAULT_TRIAL_DAYS,
    days_remaining,
    extend_organization_trial,
    get_default_trial_days,
    set_organization_trial,
)

router = APIRouter(prefix="/api/staff", tags=["staff"], dependencies=[Depends(get_current_staff)])


class InviteOrganizationRequest(BaseModel):
    # Required for 'agency', optional for 'individual' (auto-derived
    # from admin_email if omitted -- a standalone candidate has no
    # agency name to give).
    organization_name: str | None = None
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
    if payload.account_type not in ("agency", "individual"):
        raise HTTPException(status_code=422, detail="account_type must be 'agency' or 'individual'.")
    if payload.trial_days is not None and payload.trial_days < 0:
        raise HTTPException(status_code=422, detail="trial_days must be zero or positive (or omitted for no trial).")

    if payload.account_type == "individual":
        # A standalone candidate has no agency name to give -- fall back
        # to their email, which is guaranteed present and effectively
        # unique, rather than asking them to invent one.
        org_name = (payload.organization_name or "").strip() or payload.admin_email.strip().lower()
    else:
        if not payload.organization_name or not payload.organization_name.strip():
            raise HTTPException(status_code=422, detail="organization_name is required for agency accounts.")
        org_name = payload.organization_name.strip()

    if db.query(Organization).filter_by(name=org_name).one_or_none():
        raise HTTPException(status_code=409, detail=f"An organization named '{org_name}' already exists.")

    org = Organization(name=org_name, created_by_staff_id=staff.id, account_type=payload.account_type)
    set_organization_trial(db, org, payload.trial_days)
    org.status_id = get_status_by_code(db, TRIAL if payload.trial_days is not None else ACTIVE).id
    db.add(org)
    db.flush()

    invite, otp = create_invite(
        db, email=payload.admin_email, role="admin", organization_id=org.id,
        invited_by_type="staff", invited_by_id=staff.id,
    )

    from services.platform_settings_service import get_or_create_platform_settings

    settings = get_or_create_platform_settings(db)
    # For an 'individual' account, org_name is just the invitee's own
    # email address (auto-derived for DB uniqueness) -- showing that
    # back to them as if it were a company name reads as a bug, so the
    # email gets no organization name at all in that case.
    email_org_name = org_name if payload.account_type == "agency" else None
    try:
        send_invite_email(db, payload.admin_email, otp, "admin", email_org_name, settings.invite_expire_days)
    except RuntimeError as e:
        # Nothing sent means nothing should be left behind -- otherwise
        # this org's name is permanently taken with no invite anyone can
        # ever redeem, and no way to retry under the same name.
        db.rollback()
        raise HTTPException(status_code=502, detail=f"Could not create organization: invite email failed to send: {e}")
    db.commit()

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
    status_code: str | None = None
    status_label: str | None = None


@router.get("/organizations", response_model=list[StaffOrganizationSummary])
def list_my_organizations(db: Session = Depends(get_db), staff: Staff = Depends(get_current_staff)):
    """Orgs THIS staff member created -- their own onboarding activity,
    the basis for sales-performance / future revenue attribution."""
    from db.models import Status

    orgs = db.query(Organization).filter_by(created_by_staff_id=staff.id).order_by(Organization.created_at.desc()).all()
    statuses_by_id = {s.id: s for s in db.query(Status).all()}
    results = []
    for org in orgs:
        status_row = statuses_by_id.get(org.status_id)
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
                status_code=status_row.code if status_row else None,
                status_label=status_row.label if status_row else None,
            )
        )
    return results


class StaffExtendTrialRequest(BaseModel):
    additional_days: int


class StaffOrganizationTrialResponse(BaseModel):
    organization_id: int
    trial_expires_at: str | None
    trial_days_remaining: int | None


@router.put("/organizations/{organization_id}/trial", response_model=StaffOrganizationTrialResponse)
def extend_my_organization_trial(
    organization_id: int,
    payload: StaffExtendTrialRequest,
    db: Session = Depends(get_db),
    staff: Staff = Depends(get_current_staff),
):
    """Staff can only extend trials for organizations THEY created --
    same ownership check as deactivate_organization below."""
    if payload.additional_days <= 0:
        raise HTTPException(status_code=422, detail="additional_days must be positive.")
    org = db.query(Organization).filter_by(id=organization_id).one_or_none()
    if org is None or org.created_by_staff_id != staff.id:
        raise HTTPException(status_code=404, detail="Organization not found.")
    extend_organization_trial(db, org, payload.additional_days)
    db.commit()
    return StaffOrganizationTrialResponse(
        organization_id=org.id,
        trial_expires_at=org.trial_expires_at.isoformat() if org.trial_expires_at else None,
        trial_days_remaining=days_remaining(org.trial_expires_at),
    )


@router.get("/trial-default")
def get_trial_default(db: Session = Depends(get_db)):
    """Read-only -- lets the org-creation form pre-fill trial_days with
    the superuser-configured default without giving staff access to the
    rest of /api/superuser/settings."""
    return {"default_trial_days": get_default_trial_days(db)}


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
