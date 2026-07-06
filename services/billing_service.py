"""
Subscription lifecycle -- per-candidate-per-month billing STATUS
tracking and the pause/resume rules, not real payment processing
(charging a card is a distinct future integration, e.g. Stripe).

Two independent things can each stop the app from applying for a
candidate, and both are checked by is_candidate_active():
  - Subscription.status != 'active' (paused or cancelled, by either
    the candidate or the org)
  - Candidate.availability_status == 'not_looking' (job-search intent,
    independent of billing -- someone can be actively subscribed/billed
    but between engagements and not currently wanting new applications)
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from db.models import Candidate, Subscription


def get_or_create_subscription(session: Session, candidate: Candidate) -> Subscription:
    sub = session.query(Subscription).filter_by(candidate_id=candidate.id).one_or_none()
    if sub is None:
        sub = Subscription(candidate_id=candidate.id, organization_id=candidate.organization_id, status="active")
        session.add(sub)
        session.flush()
    return sub


def pause_subscription(session: Session, candidate: Candidate, paused_by: str) -> Subscription:
    """paused_by: 'candidate' | 'org'. Idempotent -- pausing an
    already-paused subscription just updates who/when, doesn't error."""
    sub = get_or_create_subscription(session, candidate)
    sub.status = "paused"
    sub.paused_by = paused_by
    sub.paused_at = datetime.now(timezone.utc)
    sub.resumed_at = None
    session.commit()
    return sub


def resume_subscription(session: Session, candidate: Candidate) -> Subscription:
    sub = get_or_create_subscription(session, candidate)
    sub.status = "active"
    sub.resumed_at = datetime.now(timezone.utc)
    session.commit()
    return sub


def cancel_subscription(session: Session, candidate: Candidate) -> Subscription:
    sub = get_or_create_subscription(session, candidate)
    sub.status = "cancelled"
    sub.cancelled_at = datetime.now(timezone.utc)
    session.commit()
    return sub


def is_candidate_active(session: Session, candidate: Candidate) -> tuple[bool, str | None]:
    """Returns (active, reason_if_not). Checked before any job-matching/
    application activity -- both post-and-match fan-out and inbound
    email evaluation must skip a candidate that fails this, exactly
    like they'd skip one with no admin-approved profile."""
    if candidate.availability_status == "not_looking":
        return False, "Candidate is marked as not currently looking for jobs."

    sub = session.query(Subscription).filter_by(candidate_id=candidate.id).one_or_none()
    if sub is None:
        return True, None  # no subscription row yet defaults to active (created lazily on first check)

    if sub.status == "paused":
        return False, f"Subscription paused by {sub.paused_by or 'unknown'} -- not billed, not applying."
    if sub.status == "cancelled":
        return False, "Subscription cancelled."

    return True, None
