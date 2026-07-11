"""
Free-trial / subscription expiry tracking and reminders.

Two independent expiry clocks, both optional:
  - Organization.trial_expires_at -- the whole account's access (an
    agency's overall account, or an 'individual' account where the org
    IS the one person).
  - Subscription.current_period_end -- one candidate's own trial/plan
    end, for finer-grained control within an agency (e.g. an agency's
    overall org has no expiry, but one particular candidate on the
    bench does).

Both are surfaced two ways: a person logging in within
PlatformSettings.trial_banner_window_days of an unexpired date sees a
short-lived in-app banner (frontend-only, computed from the expiry
date every login -- no separate "have I shown this" flag needed
there). Separately, an actual reminder EMAIL goes out once per expiry,
within PlatformSettings.trial_reminder_window_days of expiry, guarded
by the trial_reminder_sent_at fields -- that dedup happens here since
email sending, unlike a UI banner, has a real external side effect.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from db.models import AdminUser, Candidate, Organization, Subscription
from services.email_sender import send_trial_reminder_email

# Fallback only -- used before PlatformSettings has ever been read/written
# (get_default_trial_days below is the real source of truth once a
# settings row exists, which get_or_create_platform_settings guarantees
# on first access anyway).
DEFAULT_TRIAL_DAYS = 14


def get_default_trial_days(session: Session) -> int:
    """The superuser-configurable default new org-creation forms
    pre-fill (PlatformSettings.default_trial_days) -- staff/superuser
    can still type a different number per org at creation time."""
    from services.platform_settings_service import get_or_create_platform_settings

    return get_or_create_platform_settings(session).default_trial_days


def get_trial_banner_window_days(session: Session) -> int:
    """Show the in-app "expiring soon" banner within this many days of
    expiry (PlatformSettings.trial_banner_window_days) -- surfaced to
    the frontend via OrganizationSettingsResponse/candidate /subscription
    so TrialBanner.jsx doesn't hardcode its own copy of this number."""
    from services.platform_settings_service import get_or_create_platform_settings

    return get_or_create_platform_settings(session).trial_banner_window_days


def get_trial_reminder_window_days(session: Session) -> int:
    """Send the actual reminder EMAIL this many days before expiry, or
    sooner (PlatformSettings.trial_reminder_window_days)."""
    from services.platform_settings_service import get_or_create_platform_settings

    return get_or_create_platform_settings(session).trial_reminder_window_days


def days_remaining(expires_at: date | None, today: date | None = None) -> int | None:
    """None means 'no expiry set' -- not the same as 0 (expires today)
    or a negative number (already expired), both of which are real,
    meaningful values callers should be able to distinguish."""
    if expires_at is None:
        return None
    today = today or datetime.now(timezone.utc).date()
    return (expires_at - today).days


def set_organization_trial(session: Session, org: Organization, trial_days: int | None) -> Organization:
    """trial_days=None means no expiry (a real, immediately-paid account
    with no trial). Changing the date always clears
    trial_reminder_sent_at, so a renewal/extension gets its own fresh
    reminder rather than the old one's dedup guard silently suppressing
    it for the new date."""
    if trial_days is None:
        org.trial_expires_at = None
    else:
        org.trial_expires_at = datetime.now(timezone.utc).date() + timedelta(days=trial_days)
    org.trial_reminder_sent_at = None
    return org


def set_candidate_trial(session: Session, candidate: Candidate, trial_days: int | None) -> Subscription:
    from services.billing_service import get_or_create_subscription

    sub = get_or_create_subscription(session, candidate)
    if trial_days is None:
        sub.current_period_end = None
    else:
        sub.current_period_end = datetime.now(timezone.utc).date() + timedelta(days=trial_days)
    sub.trial_reminder_sent_at = None
    return sub


def extend_organization_trial(session: Session, org: Organization, additional_days: int) -> Organization:
    """Adds days on top of whatever's there -- distinct from
    set_organization_trial (an absolute reset used only at org-creation
    time). Extends from the LATER of today or the current expiry, so
    extending an already-lapsed trial starts counting from today (not
    from a stale past date), while extending a still-active trial adds
    cleanly onto the end of it rather than shortening it."""
    today = datetime.now(timezone.utc).date()
    base = org.trial_expires_at if (org.trial_expires_at and org.trial_expires_at > today) else today
    org.trial_expires_at = base + timedelta(days=additional_days)
    org.trial_reminder_sent_at = None
    return org


def extend_candidate_trial(session: Session, candidate: Candidate, additional_days: int) -> Subscription:
    """Candidate equivalent of extend_organization_trial -- see its
    docstring for the "extend from later of today/current expiry" logic."""
    from services.billing_service import get_or_create_subscription

    sub = get_or_create_subscription(session, candidate)
    today = datetime.now(timezone.utc).date()
    base = sub.current_period_end if (sub.current_period_end and sub.current_period_end > today) else today
    sub.current_period_end = base + timedelta(days=additional_days)
    sub.trial_reminder_sent_at = None
    return sub


def _admin_recipient_email(session: Session, organization_id: int) -> str | None:
    """Best-effort: the first admin with an email on file for this org.
    An org can have more than one admin; this picks one rather than
    emailing all of them, since a trial-expiry notice is informational,
    not an action gate."""
    admin = (
        session.query(AdminUser)
        .filter(AdminUser.organization_id == organization_id, AdminUser.email.isnot(None))
        .order_by(AdminUser.id.asc())
        .first()
    )
    return admin.email if admin else None


def check_and_send_trial_reminders(session: Session, today: date | None = None) -> dict:
    """Scans every organization and every subscription with an expiry
    set, and sends a one-time reminder email to anything landing within
    the configured reminder window (inclusive of already-expired --
    someone whose trial lapsed over a weekend before this ran should
    still hear about it once). Returns counts for logging/testing,
    never raises on an individual email failure -- one bad address
    shouldn't stop the whole scan.

    Meant to be run periodically (see api/routers/superuser.py's
    /trial-reminders/run for a manually-triggerable version, and
    DISABLE_TRIAL_REMINDERS in your .env to turn off any scheduled
    loop) -- same pattern as services/file_watcher.py's watch cycle.
    """
    today = today or datetime.now(timezone.utc).date()
    reminder_window_days = get_trial_reminder_window_days(session)
    org_reminders_sent = 0
    org_reminders_failed = 0
    candidate_reminders_sent = 0
    candidate_reminders_failed = 0

    orgs = (
        session.query(Organization)
        .filter(
            Organization.is_active.is_(True),
            Organization.trial_expires_at.isnot(None),
            Organization.trial_reminder_sent_at.is_(None),
        )
        .all()
    )
    for org in orgs:
        remaining = days_remaining(org.trial_expires_at, today)
        if remaining is None or remaining > reminder_window_days:
            continue
        recipient = _admin_recipient_email(session, org.id)
        if not recipient:
            continue
        try:
            send_trial_reminder_email(session, recipient, org.trial_expires_at, account_label=org.name)
            org.trial_reminder_sent_at = datetime.now(timezone.utc)
            org_reminders_sent += 1
        except RuntimeError:
            org_reminders_failed += 1

    subs = (
        session.query(Subscription)
        .filter(
            Subscription.status == "active",
            Subscription.current_period_end.isnot(None),
            Subscription.trial_reminder_sent_at.is_(None),
        )
        .all()
    )
    for sub in subs:
        remaining = days_remaining(sub.current_period_end, today)
        if remaining is None or remaining > reminder_window_days:
            continue
        candidate = session.query(Candidate).filter_by(id=sub.candidate_id).one_or_none()
        if candidate is None or not candidate.login_email:
            continue
        try:
            send_trial_reminder_email(session, candidate.login_email, sub.current_period_end, account_label=candidate.full_name)
            sub.trial_reminder_sent_at = datetime.now(timezone.utc)
            candidate_reminders_sent += 1
        except RuntimeError:
            candidate_reminders_failed += 1

    session.commit()
    return {
        "organizations_reminded": org_reminders_sent,
        "organizations_failed": org_reminders_failed,
        "candidates_reminded": candidate_reminders_sent,
        "candidates_failed": candidate_reminders_failed,
    }
