from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.deps import get_current_admin, get_db
from db.models import AdminUser, Organization
from services.trial_service import days_remaining

router = APIRouter(prefix="/api/organization", tags=["organization-settings"], dependencies=[Depends(get_current_admin)])


class OrganizationSettingsResponse(BaseModel):
    organization_name: str
    account_type: str
    autonomous_email_enabled: bool
    email_notifications_enabled: bool
    initial_outreach_follow_up_days: int
    client_submission_follow_up_days: int
    post_interview_follow_up_days: int
    resubmission_cooldown_days: int
    inbox_poll_interval_minutes: int
    max_failed_login_attempts: int
    lockout_minutes: int
    max_jobs_per_day: int
    max_applications_per_day: int
    max_emails_per_day: int
    send_only_business_hours: bool
    business_hours_start_hour: int
    business_hours_end_hour: int
    business_hours_timezone: str
    # Read-only -- set by whoever (staff/superuser) onboarded this org,
    # never editable by the org's own admin via this endpoint (they
    # could otherwise just extend their own trial).
    trial_expires_at: str | None = None
    trial_days_remaining: int | None = None


class OrganizationSettingsUpdate(BaseModel):
    autonomous_email_enabled: bool | None = None
    email_notifications_enabled: bool | None = None
    initial_outreach_follow_up_days: int | None = None
    client_submission_follow_up_days: int | None = None
    post_interview_follow_up_days: int | None = None
    resubmission_cooldown_days: int | None = None
    inbox_poll_interval_minutes: int | None = None
    max_failed_login_attempts: int | None = None
    lockout_minutes: int | None = None
    max_jobs_per_day: int | None = None
    max_applications_per_day: int | None = None
    max_emails_per_day: int | None = None
    send_only_business_hours: bool | None = None
    business_hours_start_hour: int | None = None
    business_hours_end_hour: int | None = None
    business_hours_timezone: str | None = None


def _to_response(org) -> "OrganizationSettingsResponse":
    return OrganizationSettingsResponse(
        organization_name=org.name,
        account_type=org.account_type,
        autonomous_email_enabled=org.autonomous_email_enabled,
        email_notifications_enabled=org.email_notifications_enabled,
        initial_outreach_follow_up_days=org.initial_outreach_follow_up_days,
        client_submission_follow_up_days=org.client_submission_follow_up_days,
        post_interview_follow_up_days=org.post_interview_follow_up_days,
        resubmission_cooldown_days=org.resubmission_cooldown_days,
        inbox_poll_interval_minutes=org.inbox_poll_interval_minutes,
        max_failed_login_attempts=org.max_failed_login_attempts,
        lockout_minutes=org.lockout_minutes,
        max_jobs_per_day=org.max_jobs_per_day,
        max_applications_per_day=org.max_applications_per_day,
        max_emails_per_day=org.max_emails_per_day,
        send_only_business_hours=org.send_only_business_hours,
        business_hours_start_hour=org.business_hours_start_hour,
        business_hours_end_hour=org.business_hours_end_hour,
        business_hours_timezone=org.business_hours_timezone,
        trial_expires_at=org.trial_expires_at.isoformat() if org.trial_expires_at else None,
        trial_days_remaining=days_remaining(org.trial_expires_at),
    )


@router.get("/settings", response_model=OrganizationSettingsResponse)
def get_settings(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    org = db.query(Organization).filter_by(id=admin.organization_id).one()
    return _to_response(org)


@router.put("/settings", response_model=OrganizationSettingsResponse)
def update_settings(
    payload: OrganizationSettingsUpdate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """Every org-level feature flag lives here: autonomous sending,
    notification channel preference, follow-up timers, resubmission
    cooldown, daily volume caps, and business-hours sending. Only
    fields actually provided are changed."""
    org = db.query(Organization).filter_by(id=admin.organization_id).one()

    for field in (
        "autonomous_email_enabled", "email_notifications_enabled",
        "initial_outreach_follow_up_days", "client_submission_follow_up_days",
        "post_interview_follow_up_days", "resubmission_cooldown_days",
        "inbox_poll_interval_minutes", "max_failed_login_attempts", "lockout_minutes",
        "max_jobs_per_day", "max_applications_per_day", "max_emails_per_day",
        "send_only_business_hours", "business_hours_start_hour", "business_hours_end_hour",
        "business_hours_timezone",
    ):
        value = getattr(payload, field)
        if value is not None:
            setattr(org, field, value)

    db.commit()
    return _to_response(org)
