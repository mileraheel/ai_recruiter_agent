"""
Superuser: platform-wide, read-only reporting across every
organization. Deliberately scoped narrow for now -- login and reports
only. Creating organizations/admins/candidates from the superuser side
is the invite system, still deferred; this only covers "what's
everyone doing" visibility.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.auth import authenticate_superuser, create_access_token
from api.deps import get_current_superuser, get_db
from api.schemas import OrganizationSummary, PlatformSummary, TokenResponse
from db.models import AdminUser, Candidate, Email, Interview, Job, Organization, Staff, SuperUser
from services.email_sender import send_invite_email
from services.invite_service import create_invite
from services.rate_limit import check_not_locked, record_failure, record_success
from services.trial_service import DEFAULT_TRIAL_DAYS, days_remaining, set_organization_trial

router = APIRouter(tags=["superuser"])


@router.post("/api/superuser-auth/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    account_key = f"superuser:{form_data.username.strip().lower()}"
    check_not_locked(db, account_key)

    user = authenticate_superuser(db, form_data.username, form_data.password)
    if not user:
        record_failure(db, account_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    record_success(db, account_key)
    token = create_access_token(user.username, role="superuser")
    return TokenResponse(access_token=token)


@router.get("/api/superuser/reports/summary", response_model=PlatformSummary, dependencies=[Depends(get_current_superuser)])
def platform_summary(db: Session = Depends(get_db)):
    orgs = db.query(Organization).order_by(Organization.created_at.asc()).all()

    org_summaries = []
    total_candidates = 0
    total_jobs = 0
    total_sent = 0
    total_interviews = 0

    for org in orgs:
        candidate_count = db.query(Candidate).filter_by(organization_id=org.id).count()
        admin_count = db.query(AdminUser).filter_by(organization_id=org.id).count()
        jobs_posted = db.query(Job).filter_by(organization_id=org.id).count()

        applications_sent = (
            db.query(Email)
            .join(Candidate, Email.candidate_id == Candidate.id)
            .filter(Candidate.organization_id == org.id, Email.status.in_(("sent", "approved")))
            .count()
        )
        interviews_scheduled = (
            db.query(Interview)
            .join(Email, Interview.email_id == Email.id)
            .join(Candidate, Email.candidate_id == Candidate.id)
            .filter(Candidate.organization_id == org.id)
            .count()
        )

        sales_person = None
        if org.created_by_staff_id:
            staff_row = db.query(Staff).filter_by(id=org.created_by_staff_id).one_or_none()
            sales_person = staff_row.username if staff_row else None
        elif org.created_by_superuser_id:
            su_row = db.query(SuperUser).filter_by(id=org.created_by_superuser_id).one_or_none()
            sales_person = f"superuser: {su_row.username}" if su_row else None

        org_summaries.append(
            OrganizationSummary(
                organization_id=org.id,
                organization_name=org.name,
                candidate_count=candidate_count,
                admin_count=admin_count,
                jobs_posted=jobs_posted,
                applications_sent=applications_sent,
                interviews_scheduled=interviews_scheduled,
                created_at=org.created_at,
                sales_person=sales_person,
                trial_expires_at=org.trial_expires_at,
                trial_days_remaining=days_remaining(org.trial_expires_at),
            )
        )
        total_candidates += candidate_count
        total_jobs += jobs_posted
        total_sent += applications_sent
        total_interviews += interviews_scheduled

    return PlatformSummary(
        organization_count=len(orgs),
        total_candidates=total_candidates,
        total_jobs_posted=total_jobs,
        total_applications_sent=total_sent,
        total_interviews=total_interviews,
        organizations=org_summaries,
    )


class InviteStaffRequest(BaseModel):
    email: str


class InviteStaffResponse(BaseModel):
    invited_email: str
    expires_at: str


@router.post("/api/superuser/staff/invite", response_model=InviteStaffResponse, dependencies=[Depends(get_current_superuser)])
def invite_staff(
    payload: InviteStaffRequest,
    db: Session = Depends(get_db),
    superuser: SuperUser = Depends(get_current_superuser),
):
    """Only a superuser can invite staff -- no self-signup, same
    reasoning as superuser itself: staff can create organizations and
    invite admins into them, which is real platform-level trust.

    Same OTP-invite mechanism as admin/candidate invites (see
    services/invite_service.py) rather than the superuser choosing a
    username/password directly -- the invitee sets their own
    credentials when they redeem it, same as everyone else on the
    platform. organization_id is None since staff aren't scoped to any
    one organization."""
    from services.platform_settings_service import get_or_create_platform_settings

    settings = get_or_create_platform_settings(db)
    invite, otp = create_invite(
        db, email=payload.email, role="staff", organization_id=None,
        invited_by_type="superuser", invited_by_id=superuser.id,
    )
    try:
        send_invite_email(payload.email, otp, "staff", None, settings.invite_expire_days)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=f"Invite created, but email failed to send: {e}")

    return InviteStaffResponse(invited_email=payload.email, expires_at=invite.expires_at.isoformat())


class StaffPerformance(BaseModel):
    staff_id: int
    username: str
    is_active: bool
    organizations_onboarded: int
    active_organizations: int
    total_candidates_across_orgs: int


@router.get(
    "/api/superuser/staff/performance",
    response_model=list[StaffPerformance],
    dependencies=[Depends(get_current_superuser)],
)
def staff_performance(db: Session = Depends(get_db)):
    """Sales-performance view: how many orgs each staff member has
    onboarded, and how much candidate activity those orgs represent --
    the basis for future revenue attribution per staff member."""
    results = []
    for staff in db.query(Staff).order_by(Staff.created_at.asc()).all():
        orgs = db.query(Organization).filter_by(created_by_staff_id=staff.id).all()
        candidate_total = sum(db.query(Candidate).filter_by(organization_id=o.id).count() for o in orgs)
        results.append(
            StaffPerformance(
                staff_id=staff.id,
                username=staff.username,
                is_active=staff.is_active,
                organizations_onboarded=len(orgs),
                active_organizations=sum(1 for o in orgs if o.is_active),
                total_candidates_across_orgs=candidate_total,
            )
        )
    return results


class PendingInviteResponse(BaseModel):
    id: int
    email: str
    role: str
    organization_name: str | None
    invited_by_type: str
    expires_at: str
    used_at: str | None
    attempts: int
    max_attempts: int


@router.get(
    "/api/superuser/invites/pending",
    response_model=list[PendingInviteResponse],
    dependencies=[Depends(get_current_superuser)],
)
def list_pending_invites(db: Session = Depends(get_db)):
    """Every not-yet-redeemed invite platform-wide (any role/org) --
    lets you see who's been invited but hasn't signed up yet, and
    whether their code has expired, without digging through the DB."""
    from db.models import Invite

    invites = db.query(Invite).filter(Invite.used_at.is_(None)).order_by(Invite.created_at.desc()).all()
    results = []
    for inv in invites:
        org_name = None
        if inv.organization_id:
            org = db.query(Organization).filter_by(id=inv.organization_id).one_or_none()
            org_name = org.name if org else None
        results.append(
            PendingInviteResponse(
                id=inv.id,
                email=inv.email,
                role=inv.role,
                organization_name=org_name,
                invited_by_type=inv.invited_by_type,
                expires_at=inv.expires_at.isoformat(),
                used_at=inv.used_at.isoformat() if inv.used_at else None,
                attempts=inv.attempts,
                max_attempts=inv.max_attempts,
            )
        )
    return results


class PlatformSettingsResponse(BaseModel):
    invite_expire_days: int


class PlatformSettingsUpdate(BaseModel):
    invite_expire_days: int


@router.get(
    "/api/superuser/settings",
    response_model=PlatformSettingsResponse,
    dependencies=[Depends(get_current_superuser)],
)
def get_platform_settings(db: Session = Depends(get_db)):
    from services.platform_settings_service import get_or_create_platform_settings

    settings = get_or_create_platform_settings(db)
    db.commit()
    return PlatformSettingsResponse(invite_expire_days=settings.invite_expire_days)


@router.put(
    "/api/superuser/settings",
    response_model=PlatformSettingsResponse,
    dependencies=[Depends(get_current_superuser)],
)
def update_platform_settings(payload: PlatformSettingsUpdate, db: Session = Depends(get_db)):
    from services.platform_settings_service import get_or_create_platform_settings

    if payload.invite_expire_days < 1:
        raise HTTPException(status_code=422, detail="invite_expire_days must be at least 1.")

    settings = get_or_create_platform_settings(db)
    settings.invite_expire_days = payload.invite_expire_days
    db.commit()
    return PlatformSettingsResponse(invite_expire_days=settings.invite_expire_days)


class CreateOrganizationRequest(BaseModel):
    organization_name: str
    admin_email: str
    account_type: str = "agency"  # "agency" | "individual" -- 'individual' is how a
    # superuser creates what's effectively a single standalone candidate: one
    # Organization + one AdminUser who is also the linked Candidate (see
    # Organization.account_type / AdminUser.linked_candidate_id docstrings).
    trial_days: int | None = DEFAULT_TRIAL_DAYS  # None means no trial expiry (a real paid account)


class CreateOrganizationResponse(BaseModel):
    organization_id: int
    organization_name: str
    invited_email: str
    trial_expires_at: str | None = None


@router.post(
    "/api/superuser/organizations",
    response_model=CreateOrganizationResponse,
    dependencies=[Depends(get_current_superuser)],
)
def create_organization(
    payload: CreateOrganizationRequest,
    db: Session = Depends(get_db),
    superuser: SuperUser = Depends(get_current_superuser),
):
    """Same effect as a staff member's invite-organization, but
    attributed to this superuser directly (Organization.created_by_superuser_id,
    never created_by_staff_id) -- for onboarding an org, or a standalone
    individual/candidate, yourself rather than through a staff account."""
    org_name = payload.organization_name.strip()
    if db.query(Organization).filter_by(name=org_name).one_or_none():
        raise HTTPException(status_code=409, detail=f"An organization named '{org_name}' already exists.")
    if payload.account_type not in ("agency", "individual"):
        raise HTTPException(status_code=422, detail="account_type must be 'agency' or 'individual'.")
    if payload.trial_days is not None and payload.trial_days < 0:
        raise HTTPException(status_code=422, detail="trial_days must be zero or positive (or omitted for no trial).")

    org = Organization(name=org_name, created_by_superuser_id=superuser.id, account_type=payload.account_type)
    set_organization_trial(db, org, payload.trial_days)
    db.add(org)
    db.flush()

    invite, otp = create_invite(
        db, email=payload.admin_email, role="admin", organization_id=org.id,
        invited_by_type="superuser", invited_by_id=superuser.id,
    )
    from services.platform_settings_service import get_or_create_platform_settings

    settings = get_or_create_platform_settings(db)
    try:
        send_invite_email(payload.admin_email, otp, "admin", org_name, settings.invite_expire_days)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=f"Organization created, but invite email failed to send: {e}")

    return CreateOrganizationResponse(
        organization_id=org.id,
        organization_name=org.name,
        invited_email=payload.admin_email,
        trial_expires_at=org.trial_expires_at.isoformat() if org.trial_expires_at else None,
    )


class TrialReminderRunResponse(BaseModel):
    organizations_reminded: int
    organizations_failed: int
    candidates_reminded: int
    candidates_failed: int


@router.post(
    "/api/superuser/trial-reminders/run",
    response_model=TrialReminderRunResponse,
    dependencies=[Depends(get_current_superuser)],
)
def run_trial_reminders(db: Session = Depends(get_db)):
    """Manually triggers the same scan a scheduled job would run
    periodically (cron / Windows Task Scheduler) -- see
    services/trial_service.py::check_and_send_trial_reminders. Safe to
    call repeatedly: each organization/subscription only ever gets one
    reminder per expiry date, guarded by trial_reminder_sent_at."""
    from services.trial_service import check_and_send_trial_reminders

    return TrialReminderRunResponse(**check_and_send_trial_reminders(db))
