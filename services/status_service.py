"""
Account-status lookup/assignment for Organization and Candidate. See
db/models.py::Status for what this is and isn't (not the same as
Candidate.profile_status or availability_status).

The four starting codes are seeded by db/seed.py -- this module only
looks them up by code, it never creates rows itself, so a missing code
here is a real seed-step bug, not something to silently paper over.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from db.models import Status

TRIAL = "trial"
EXTENDED_TRIAL = "extended_trial"
ACTIVE = "active"
SUSPENDED = "suspended"


def get_status_by_code(session: Session, code: str) -> Status:
    status = session.query(Status).filter_by(code=code).one_or_none()
    if status is None:
        raise ValueError(f"Status code '{code}' not found -- has db/seed.py been run?")
    return status


def list_statuses(session: Session) -> list[Status]:
    return session.query(Status).order_by(Status.id.asc()).all()
