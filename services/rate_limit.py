"""
Account-based login lockout: N consecutive failures locks the account
for a cooldown window, success clears the counter. This is the
standard pattern (same shape used by most consumer SaaS logins) and
sits at the account level -- IP-based rate limiting is a separate,
infra-level concern (reverse proxy / WAF) once this is actually
deployed, not something app code should try to own.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from db.models import LoginAttempt
from services.platform_settings_service import get_or_create_platform_settings


def get_default_lockout_policy(session: Session) -> tuple[int, int]:
    """(max_attempts, lockout_minutes) for staff/superuser logins (not
    org-scoped) and the fallback for admin/candidate accounts with no
    organization yet -- org-scoped admin/candidate logins use
    Organization.max_failed_login_attempts/lockout_minutes instead, set
    per org."""
    settings = get_or_create_platform_settings(session)
    return settings.login_lockout_max_attempts, settings.login_lockout_minutes


def _naive_to_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def check_not_locked(session: Session, account_key: str) -> None:
    """Raises 429 if this account is currently locked out. Called BEFORE
    attempting to verify credentials, so a locked-out attacker can't
    keep guessing passwords during the lockout window."""
    record = session.query(LoginAttempt).filter_by(account_key=account_key).one_or_none()
    if record is None or record.locked_until is None:
        return
    locked_until = _naive_to_utc(record.locked_until)
    if locked_until > datetime.now(timezone.utc):
        remaining = int((locked_until - datetime.now(timezone.utc)).total_seconds() / 60) + 1
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Try again in about {remaining} minute{'s' if remaining != 1 else ''}.",
        )


def record_failure(
    session: Session,
    account_key: str,
    max_attempts: int | None = None,
    lockout_minutes: int | None = None,
) -> None:
    """max_attempts/lockout_minutes are org-specific for admin/candidate
    logins (see Organization.max_failed_login_attempts/lockout_minutes,
    read by the caller before this is invoked) -- staff/superuser
    logins aren't org-scoped, so callers that omit them fall back to
    the platform-wide default (see get_default_lockout_policy)."""
    if max_attempts is None or lockout_minutes is None:
        default_attempts, default_minutes = get_default_lockout_policy(session)
        max_attempts = max_attempts if max_attempts is not None else default_attempts
        lockout_minutes = lockout_minutes if lockout_minutes is not None else default_minutes

    record = session.query(LoginAttempt).filter_by(account_key=account_key).one_or_none()
    if record is None:
        record = LoginAttempt(account_key=account_key, failed_count=0)
        session.add(record)
        session.flush()

    record.failed_count += 1
    record.last_attempt_at = datetime.now(timezone.utc)
    if record.failed_count >= max_attempts:
        record.locked_until = datetime.now(timezone.utc) + timedelta(minutes=lockout_minutes)
    session.commit()


def record_success(session: Session, account_key: str) -> None:
    record = session.query(LoginAttempt).filter_by(account_key=account_key).one_or_none()
    if record is not None:
        record.failed_count = 0
        record.locked_until = None
        session.commit()
