"""
Daily volume caps, per organization. Migrated from the old YAML
`limits:` block into the same DB-backed org settings model as
everything else.

Definitions (counted directly from existing rows rather than a
separate counter table -- always accurate, no drift):
  - "jobs" = Job rows created today for this org
  - "applications" = Email rows CREATED today (prepared, whether or not
    later sent)
  - "emails" = Email rows that reached status in ('sent', 'approved')
    today -- actually left the app in some form
"""
from __future__ import annotations

from datetime import datetime, time, timezone

from sqlalchemy.orm import Session

from db.models import Candidate, Email, Job, Organization


def _today_start_utc() -> datetime:
    now = datetime.now(timezone.utc)
    return datetime.combine(now.date(), time.min, tzinfo=timezone.utc)


def check_job_volume(session: Session, organization_id: int) -> tuple[bool, str | None]:
    org = session.query(Organization).filter_by(id=organization_id).one()
    count = session.query(Job).filter(Job.organization_id == organization_id, Job.created_at >= _today_start_utc()).count()
    if count >= org.max_jobs_per_day:
        return False, f"Daily job-matching limit reached ({org.max_jobs_per_day}/day)."
    return True, None


def check_application_volume(session: Session, organization_id: int) -> tuple[bool, str | None]:
    org = session.query(Organization).filter_by(id=organization_id).one()
    count = (
        session.query(Email)
        .join(Candidate, Email.candidate_id == Candidate.id)
        .filter(Candidate.organization_id == organization_id, Email.created_at >= _today_start_utc())
        .count()
    )
    if count >= org.max_applications_per_day:
        return False, f"Daily application limit reached ({org.max_applications_per_day}/day)."
    return True, None


def check_email_volume(session: Session, organization_id: int) -> tuple[bool, str | None]:
    org = session.query(Organization).filter_by(id=organization_id).one()
    count = (
        session.query(Email)
        .join(Candidate, Email.candidate_id == Candidate.id)
        .filter(
            Candidate.organization_id == organization_id,
            Email.status.in_(("sent", "approved")),
            Email.updated_at >= _today_start_utc(),
        )
        .count()
    )
    if count >= org.max_emails_per_day:
        return False, f"Daily email-send limit reached ({org.max_emails_per_day}/day)."
    return True, None
