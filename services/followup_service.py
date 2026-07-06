"""
Follow-up scheduling and the resubmission dedup check.

Three scheduling entry points, each called from the specific moment
that triggers it (see call sites: application_service.py for
initial_outreach, api/routers/reports.py for client_submission and
post_interview). All three read their delay from Organization's
configurable fields -- no hardcoded "2 days" or "a week" anywhere.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from db.models import ClientSubmission, Email, FollowUp, Job, Organization


def _normalize(text: str | None) -> str | None:
    if not text:
        return None
    return re.sub(r"\s+", " ", text.strip().lower())


def _get_org(session: Session, organization_id: int) -> Organization:
    return session.query(Organization).filter_by(id=organization_id).one()


def schedule_initial_outreach_followup(session: Session, email_row: Email) -> FollowUp | None:
    """Called right after an application email is CONFIRMED sent
    (status='sent', i.e. send_directly succeeded) -- not for
    draft_first's 'approved' status, since there's no reliable signal
    yet that a drafted email was actually sent by the candidate. That's
    a real gap tied to the not-yet-built inbox-monitoring phase, which
    would need to detect the message actually left the outbox."""
    job = session.query(Job).filter_by(id=email_row.job_id).one_or_none()
    if job is None or job.organization_id is None:
        return None
    org = _get_org(session, job.organization_id)

    follow_up = FollowUp(
        organization_id=org.id,
        job_id=email_row.job_id,
        email_id=email_row.id,
        follow_up_type="initial_outreach",
        next_follow_up_date=date.today() + timedelta(days=org.initial_outreach_follow_up_days),
        status="scheduled",
    )
    session.add(follow_up)
    session.commit()
    session.refresh(follow_up)
    return follow_up


def schedule_client_submission_followup(session: Session, email_row: Email) -> FollowUp | None:
    """Called when an application's pipeline_stage is set to
    'client_submitted' (see api/routers/reports.py::update_pipeline)."""
    job = session.query(Job).filter_by(id=email_row.job_id).one_or_none()
    if job is None or job.organization_id is None:
        return None
    org = _get_org(session, job.organization_id)

    follow_up = FollowUp(
        organization_id=org.id,
        job_id=email_row.job_id,
        email_id=email_row.id,
        follow_up_type="client_submission",
        next_follow_up_date=date.today() + timedelta(days=org.client_submission_follow_up_days),
        status="scheduled",
    )
    session.add(follow_up)
    session.commit()
    session.refresh(follow_up)
    return follow_up


def schedule_post_interview_followup(session: Session, email_row: Email) -> FollowUp | None:
    """Called when an Interview's status is set to 'completed' (see
    api/routers/reports.py::update_interview)."""
    job = session.query(Job).filter_by(id=email_row.job_id).one_or_none()
    if job is None or job.organization_id is None:
        return None
    org = _get_org(session, job.organization_id)

    follow_up = FollowUp(
        organization_id=org.id,
        job_id=email_row.job_id,
        email_id=email_row.id,
        follow_up_type="post_interview",
        next_follow_up_date=date.today() + timedelta(days=org.post_interview_follow_up_days),
        status="scheduled",
    )
    session.add(follow_up)
    session.commit()
    session.refresh(follow_up)
    return follow_up


def get_due_followups(session: Session, organization_id: int) -> list[FollowUp]:
    return (
        session.query(FollowUp)
        .filter(
            FollowUp.organization_id == organization_id,
            FollowUp.status == "scheduled",
            FollowUp.next_follow_up_date <= date.today(),
        )
        .order_by(FollowUp.next_follow_up_date.asc())
        .all()
    )


# --- Resubmission dedup -------------------------------------------------

def check_resubmission_dedup(
    session: Session, candidate_id: int, organization_id: int, end_client_name: str, location: str | None
) -> ClientSubmission | None:
    """Returns the existing ClientSubmission row that blocks a new
    submission, or None if none exists (safe to proceed). Matching is
    on (candidate, normalized end_client_name, normalized location)
    within Organization.resubmission_cooldown_days -- configurable per
    org, not a hardcoded week."""
    org = _get_org(session, organization_id)
    cutoff = datetime.now(timezone.utc) - timedelta(days=org.resubmission_cooldown_days)

    client_norm = _normalize(end_client_name)
    location_norm = _normalize(location)

    query = (
        session.query(ClientSubmission)
        .filter(
            ClientSubmission.candidate_id == candidate_id,
            ClientSubmission.end_client_name_normalized == client_norm,
            ClientSubmission.submitted_at >= cutoff,
        )
    )
    if location_norm:
        query = query.filter(ClientSubmission.location_normalized == location_norm)

    return query.order_by(ClientSubmission.submitted_at.desc()).first()


def record_client_submission(
    session: Session,
    candidate_id: int,
    email_id: int | None,
    end_client_name: str,
    implementation_partner_name: str | None,
    location: str | None,
) -> ClientSubmission:
    submission = ClientSubmission(
        candidate_id=candidate_id,
        email_id=email_id,
        end_client_name=end_client_name,
        end_client_name_normalized=_normalize(end_client_name) or "",
        implementation_partner_name=implementation_partner_name,
        location=location,
        location_normalized=_normalize(location),
    )
    session.add(submission)
    session.commit()
    session.refresh(submission)
    return submission
