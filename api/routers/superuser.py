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
from api.schemas import CandidatePlatformSummary, OrganizationSummary, PlatformSummary, StatusResponse, TokenResponse
from db.models import AdminUser, Candidate, Email, Interview, Job, Organization, Staff, SuperUser
from services.email_sender import send_invite_email
from services.invite_service import create_invite
from services.rate_limit import check_not_locked, record_failure, record_success
from services.status_service import ACTIVE, TRIAL, get_status_by_code, list_statuses
from services.trial_service import (
    DEFAULT_TRIAL_DAYS,
    days_remaining,
    extend_candidate_trial,
    extend_organization_trial,
    set_organization_trial,
)

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
    from db.models import Status

    orgs = db.query(Organization).order_by(Organization.created_at.asc()).all()
    statuses_by_id = {s.id: s for s in db.query(Status).all()}

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
                is_active=org.is_active,
                status_code=statuses_by_id[org.status_id].code if org.status_id in statuses_by_id else None,
                status_label=statuses_by_id[org.status_id].label if org.status_id in statuses_by_id else None,
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
        send_invite_email(db, payload.email, otp, "staff", None, settings.invite_expire_days)
    except RuntimeError as e:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"Could not invite staff member: email failed to send: {e}")
    db.commit()

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
    default_trial_days: int
    otp_expire_minutes: int
    login_lockout_max_attempts: int
    login_lockout_minutes: int
    invite_max_attempts: int
    trial_banner_window_days: int
    trial_reminder_window_days: int


class PlatformSettingsUpdate(BaseModel):
    invite_expire_days: int
    default_trial_days: int
    otp_expire_minutes: int
    login_lockout_max_attempts: int
    login_lockout_minutes: int
    invite_max_attempts: int
    trial_banner_window_days: int
    trial_reminder_window_days: int


def _platform_settings_response(settings) -> "PlatformSettingsResponse":
    return PlatformSettingsResponse(
        invite_expire_days=settings.invite_expire_days,
        default_trial_days=settings.default_trial_days,
        otp_expire_minutes=settings.otp_expire_minutes,
        login_lockout_max_attempts=settings.login_lockout_max_attempts,
        login_lockout_minutes=settings.login_lockout_minutes,
        invite_max_attempts=settings.invite_max_attempts,
        trial_banner_window_days=settings.trial_banner_window_days,
        trial_reminder_window_days=settings.trial_reminder_window_days,
    )


@router.get(
    "/api/superuser/settings",
    response_model=PlatformSettingsResponse,
    dependencies=[Depends(get_current_superuser)],
)
def get_platform_settings(db: Session = Depends(get_db)):
    from services.platform_settings_service import get_or_create_platform_settings

    settings = get_or_create_platform_settings(db)
    db.commit()
    return _platform_settings_response(settings)


@router.put(
    "/api/superuser/settings",
    response_model=PlatformSettingsResponse,
    dependencies=[Depends(get_current_superuser)],
)
def update_platform_settings(payload: PlatformSettingsUpdate, db: Session = Depends(get_db)):
    from services.platform_settings_service import get_or_create_platform_settings

    if payload.invite_expire_days < 1:
        raise HTTPException(status_code=422, detail="invite_expire_days must be at least 1.")
    if payload.default_trial_days < 0:
        raise HTTPException(status_code=422, detail="default_trial_days must be zero or positive.")
    if payload.otp_expire_minutes < 1:
        raise HTTPException(status_code=422, detail="otp_expire_minutes must be at least 1.")
    if payload.login_lockout_max_attempts < 1:
        raise HTTPException(status_code=422, detail="login_lockout_max_attempts must be at least 1.")
    if payload.login_lockout_minutes < 1:
        raise HTTPException(status_code=422, detail="login_lockout_minutes must be at least 1.")
    if payload.invite_max_attempts < 1:
        raise HTTPException(status_code=422, detail="invite_max_attempts must be at least 1.")
    if payload.trial_banner_window_days < 0:
        raise HTTPException(status_code=422, detail="trial_banner_window_days must be zero or positive.")
    if payload.trial_reminder_window_days < 0:
        raise HTTPException(status_code=422, detail="trial_reminder_window_days must be zero or positive.")

    settings = get_or_create_platform_settings(db)
    settings.invite_expire_days = payload.invite_expire_days
    settings.default_trial_days = payload.default_trial_days
    settings.otp_expire_minutes = payload.otp_expire_minutes
    settings.login_lockout_max_attempts = payload.login_lockout_max_attempts
    settings.login_lockout_minutes = payload.login_lockout_minutes
    settings.invite_max_attempts = payload.invite_max_attempts
    settings.trial_banner_window_days = payload.trial_banner_window_days
    settings.trial_reminder_window_days = payload.trial_reminder_window_days
    db.commit()
    return _platform_settings_response(settings)


class SystemEmailResponse(BaseModel):
    # "database" once a superuser has configured this here; "env" means
    # it's still falling back to .env's SMTP_* vars; "unset" means
    # neither is configured and system emails (invites, resets,
    # reminders) currently can't send at all. Never includes the
    # password -- once saved, no endpoint reads it back out.
    configured: bool
    source: str
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None
    from_email: str | None = None
    from_name: str | None = None


class SystemEmailUpdate(BaseModel):
    smtp_host: str
    smtp_port: int
    smtp_username: str
    from_email: str
    from_name: str | None = None
    # Optional on update -- omit to keep whatever's already encrypted
    # and saved, same "never ask to retype an existing secret" pattern
    # used by every other password-bearing field in this app. Required
    # the first time this is configured.
    password: str | None = None


def _system_email_response(settings) -> "SystemEmailResponse":
    import os

    if settings.system_smtp_host:
        return SystemEmailResponse(
            configured=True,
            source="database",
            smtp_host=settings.system_smtp_host,
            smtp_port=settings.system_smtp_port,
            smtp_username=settings.system_smtp_username,
            from_email=settings.system_smtp_from_email,
            from_name=settings.system_smtp_from_name,
        )
    if os.environ.get("SMTP_HOST"):
        return SystemEmailResponse(
            configured=True,
            source="env",
            smtp_host=os.environ.get("SMTP_HOST"),
            smtp_port=int(os.environ["SMTP_PORT"]) if os.environ.get("SMTP_PORT") else None,
            smtp_username=os.environ.get("SMTP_USERNAME"),
            from_email=os.environ.get("SMTP_FROM_EMAIL"),
            from_name=os.environ.get("SMTP_FROM_NAME"),
        )
    return SystemEmailResponse(configured=False, source="unset")


@router.get(
    "/api/superuser/system-email",
    response_model=SystemEmailResponse,
    dependencies=[Depends(get_current_superuser)],
)
def get_system_email(db: Session = Depends(get_db)):
    """The app's OWN outbound email account -- sends invite/password-
    reset/trial-reminder emails. Distinct from a superuser's personal
    connected email (GET /api/me/email-account), which is that one
    person's own outreach-sending account, not the platform's."""
    from services.platform_settings_service import get_or_create_platform_settings

    settings = get_or_create_platform_settings(db)
    db.commit()
    return _system_email_response(settings)


@router.put(
    "/api/superuser/system-email",
    response_model=SystemEmailResponse,
    dependencies=[Depends(get_current_superuser)],
)
def update_system_email(payload: SystemEmailUpdate, db: Session = Depends(get_db)):
    from services.crypto import encrypt_secret
    from services.email_connection_test import verify_smtp_send
    from services.platform_settings_service import get_or_create_platform_settings

    settings = get_or_create_platform_settings(db)
    if not payload.password and settings.system_smtp_encrypted_password is None:
        raise HTTPException(status_code=422, detail="password is required the first time you configure this.")

    password = payload.password or None
    if password is None:
        from services.crypto import decrypt_secret

        password = decrypt_secret(settings.system_smtp_encrypted_password)

    try:
        verify_smtp_send(payload.smtp_host, payload.smtp_port, payload.smtp_username, password, payload.from_email)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    settings.system_smtp_host = payload.smtp_host.strip()
    settings.system_smtp_port = payload.smtp_port
    settings.system_smtp_username = payload.smtp_username.strip()
    settings.system_smtp_from_email = payload.from_email.strip()
    settings.system_smtp_from_name = (payload.from_name or "").strip() or None
    if payload.password:
        settings.system_smtp_encrypted_password = encrypt_secret(payload.password)
    db.commit()
    return _system_email_response(settings)


@router.get(
    "/api/superuser/statuses",
    response_model=list[StatusResponse],
    dependencies=[Depends(get_current_superuser)],
)
def list_platform_statuses(db: Session = Depends(get_db)):
    return [StatusResponse(id=s.id, code=s.code, label=s.label) for s in list_statuses(db)]


class CreateOrganizationRequest(BaseModel):
    # Required for 'agency', optional for 'individual' (auto-derived
    # from admin_email if omitted -- a standalone candidate has no
    # agency name to give).
    organization_name: str | None = None
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
    if payload.account_type not in ("agency", "individual"):
        raise HTTPException(status_code=422, detail="account_type must be 'agency' or 'individual'.")

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
    if payload.trial_days is not None and payload.trial_days < 0:
        raise HTTPException(status_code=422, detail="trial_days must be zero or positive (or omitted for no trial).")

    org = Organization(name=org_name, created_by_superuser_id=superuser.id, account_type=payload.account_type)
    set_organization_trial(db, org, payload.trial_days)
    # A trial gets the "trial" status; a real paid account created with
    # no trial (trial_days=None) starts "active" instead.
    org.status_id = get_status_by_code(db, TRIAL if payload.trial_days is not None else ACTIVE).id
    db.add(org)
    db.flush()

    invite, otp = create_invite(
        db, email=payload.admin_email, role="admin", organization_id=org.id,
        invited_by_type="superuser", invited_by_id=superuser.id,
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

    return CreateOrganizationResponse(
        organization_id=org.id,
        organization_name=org.name,
        invited_email=payload.admin_email,
        trial_expires_at=org.trial_expires_at.isoformat() if org.trial_expires_at else None,
    )


class ExtendTrialRequest(BaseModel):
    additional_days: int


class OrganizationTrialResponse(BaseModel):
    organization_id: int
    trial_expires_at: str | None
    trial_days_remaining: int | None


@router.put(
    "/api/superuser/organizations/{organization_id}/trial",
    response_model=OrganizationTrialResponse,
    dependencies=[Depends(get_current_superuser)],
)
def extend_organization_trial_endpoint(
    organization_id: int, payload: ExtendTrialRequest, db: Session = Depends(get_db)
):
    """Superuser can extend any organization's trial (no ownership
    restriction, unlike the staff equivalent -- see api/routers/staff.py)."""
    if payload.additional_days <= 0:
        raise HTTPException(status_code=422, detail="additional_days must be positive.")
    org = db.query(Organization).filter_by(id=organization_id).one_or_none()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found.")
    extend_organization_trial(db, org, payload.additional_days)
    db.commit()
    return OrganizationTrialResponse(
        organization_id=org.id,
        trial_expires_at=org.trial_expires_at.isoformat() if org.trial_expires_at else None,
        trial_days_remaining=days_remaining(org.trial_expires_at),
    )


class ChangeStatusRequest(BaseModel):
    status_code: str


@router.put(
    "/api/superuser/organizations/{organization_id}/status",
    response_model=StatusResponse,
    dependencies=[Depends(get_current_superuser)],
)
def change_organization_status(organization_id: int, payload: ChangeStatusRequest, db: Session = Depends(get_db)):
    org = db.query(Organization).filter_by(id=organization_id).one_or_none()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found.")
    try:
        status_row = get_status_by_code(db, payload.status_code)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Unknown status code '{payload.status_code}'.")
    org.status_id = status_row.id
    db.commit()
    return StatusResponse(id=status_row.id, code=status_row.code, label=status_row.label)


@router.put(
    "/api/superuser/candidates/{candidate_id}/status",
    response_model=StatusResponse,
    dependencies=[Depends(get_current_superuser)],
)
def change_candidate_status(candidate_id: int, payload: ChangeStatusRequest, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter_by(id=candidate_id).one_or_none()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    try:
        status_row = get_status_by_code(db, payload.status_code)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Unknown status code '{payload.status_code}'.")
    candidate.status_id = status_row.id
    db.commit()
    return StatusResponse(id=status_row.id, code=status_row.code, label=status_row.label)


class CandidateTrialResponse(BaseModel):
    candidate_id: int
    trial_expires_at: str | None
    trial_days_remaining: int | None


@router.put(
    "/api/superuser/candidates/{candidate_id}/trial",
    response_model=CandidateTrialResponse,
    dependencies=[Depends(get_current_superuser)],
)
def extend_candidate_trial_endpoint(candidate_id: int, payload: ExtendTrialRequest, db: Session = Depends(get_db)):
    if payload.additional_days <= 0:
        raise HTTPException(status_code=422, detail="additional_days must be positive.")
    candidate = db.query(Candidate).filter_by(id=candidate_id).one_or_none()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    sub = extend_candidate_trial(db, candidate, payload.additional_days)
    db.commit()
    return CandidateTrialResponse(
        candidate_id=candidate.id,
        trial_expires_at=sub.current_period_end.isoformat() if sub.current_period_end else None,
        trial_days_remaining=days_remaining(sub.current_period_end),
    )


@router.get(
    "/api/superuser/candidates",
    response_model=list[CandidatePlatformSummary],
    dependencies=[Depends(get_current_superuser)],
)
def list_all_candidates(db: Session = Depends(get_db)):
    """Every candidate platform-wide, across every organization -- the
    candidate-level equivalent of /api/superuser/reports/summary's
    organization list, so a superuser can browse and act on (status,
    trial) any candidate without going through that candidate's org."""
    from db.models import Status, Subscription

    candidates = db.query(Candidate).order_by(Candidate.created_at.desc()).all()
    orgs_by_id = {o.id: o for o in db.query(Organization).all()}
    statuses_by_id = {s.id: s for s in db.query(Status).all()}
    subs_by_candidate_id = {s.candidate_id: s for s in db.query(Subscription).all()}

    results = []
    for c in candidates:
        org = orgs_by_id.get(c.organization_id)
        sub = subs_by_candidate_id.get(c.id)
        status_row = statuses_by_id.get(c.status_id)
        results.append(
            CandidatePlatformSummary(
                candidate_id=c.id,
                full_name=c.full_name,
                organization_id=c.organization_id,
                organization_name=org.name if org else "(unknown)",
                login_email=c.login_email,
                availability_status=c.availability_status,
                status_code=status_row.code if status_row else None,
                status_label=status_row.label if status_row else None,
                trial_expires_at=sub.current_period_end if sub else None,
                trial_days_remaining=days_remaining(sub.current_period_end) if sub else None,
                created_at=c.created_at,
            )
        )
    return results


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
