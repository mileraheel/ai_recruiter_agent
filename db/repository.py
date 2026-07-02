"""
Repository layer: turns an eligibility decision into database rows.

Kept separate from the eligibility engine itself (core/eligibility.py stays
a pure function with zero DB/network dependency) and separate from the CLI
(cli.py just calls into this). This is the seam where Phase 1's "manual job
input" becomes actual persisted, browsable data.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from config.schema import CandidateConfig
from core.eligibility import EligibilityResult, EligibilityStatus
from db.models import Job, JobContact, JobSource, Recruiter


def _dedup_hash(job_title: str, company_name: str | None, location: str | None) -> str:
    """Stable hash used to catch the same posting reappearing across
    sources/runs. Deliberately loose (title+company+location, lowercased)
    -- exact-match dedup, not fuzzy matching; good enough for Phase 1
    manual input, worth revisiting once real adapters produce noisier data."""
    key = f"{(job_title or '').strip().lower()}|{(company_name or '').strip().lower()}|{(location or '').strip().lower()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def get_or_create_source(session: Session, source_name: str, source_type: str = "manual") -> JobSource:
    source = session.query(JobSource).filter_by(source_name=source_name).one_or_none()
    if source is None:
        source = JobSource(
            source_name=source_name,
            enabled=True,
            source_type=source_type,
            mode="human_in_loop",
            status="idle",
        )
        session.add(source)
        session.flush()  # get source.id without a full commit
    return source


def get_or_create_recruiter(
    session: Session,
    email: str,
    *,
    name: str | None = None,
    company_name: str | None = None,
    source_name: str | None = None,
) -> Recruiter:
    """Email is the identity key for a recruiter -- the same person posts
    many jobs across many boards, and applying against 'this recruiter'
    rather than 'this one job' only works if their contact record is
    shared, not duplicated per posting. New info (name/company) fills in
    blanks on an existing record but doesn't overwrite what's already
    there, since a later, sparser posting shouldn't erase a better name
    or company captured earlier."""
    email_normalized = email.strip().lower()
    recruiter = session.query(Recruiter).filter_by(email=email_normalized).one_or_none()
    if recruiter is None:
        recruiter = Recruiter(
            email=email_normalized,
            name=name,
            company_name=company_name,
            source_name=source_name,
        )
        session.add(recruiter)
        session.flush()
    else:
        if name and not recruiter.name:
            recruiter.name = name
        if company_name and not recruiter.company_name:
            recruiter.company_name = company_name
    return recruiter


def link_job_to_recruiter(session: Session, job: Job, recruiter: Recruiter, role: str = "primary") -> None:
    existing = (
        session.query(JobContact)
        .filter_by(job_id=job.id, recruiter_id=recruiter.id)
        .one_or_none()
    )
    if existing is None:
        session.add(JobContact(job_id=job.id, recruiter_id=recruiter.id, role=role))


def save_job_check(
    session: Session,
    *,
    job_title: str,
    description_text: str,
    eligibility_result: EligibilityResult,
    source_name: str = "manual_cli",
    company_name: str | None = None,
    location: str | None = None,
    work_mode: str | None = None,
    job_url: str | None = None,
    recruiter_email: str | None = None,
    recruiter_name: str | None = None,
) -> Job:
    """Persists one job + its eligibility decision, and -- if a recruiter
    email is provided -- the recruiter contact, linked via job_contacts.
    Idempotent on (source, dedup_hash) for the job, and on email for the
    recruiter: re-checking the same posting or hearing from the same
    recruiter again updates existing rows rather than duplicating them."""
    source = get_or_create_source(session, source_name)
    dedup_hash = _dedup_hash(job_title, company_name, location)

    existing = (
        session.query(Job)
        .filter_by(source_id=source.id, dedup_hash=dedup_hash)
        .one_or_none()
    )

    status_map = {
        EligibilityStatus.ELIGIBLE: "discovered",
        EligibilityStatus.SKIPPED: "skipped",
        EligibilityStatus.NEEDS_HUMAN_REVIEW: "needs_review",
    }

    if existing is not None:
        job = existing
    else:
        job = Job(source_id=source.id, source_name=source_name, dedup_hash=dedup_hash)
        session.add(job)

    job.job_title = job_title
    job.company_name = company_name
    job.location = location
    job.work_mode = work_mode
    job.employment_type = None
    job.description_text = description_text
    job.job_url = job_url
    job.status = status_map[eligibility_result.status]
    job.skip_reason = eligibility_result.reason
    job.last_checked_at = datetime.now(timezone.utc)

    if recruiter_email:
        job.recruiter_name = recruiter_name
        job.recruiter_email = recruiter_email.strip().lower()

    session.commit()
    session.refresh(job)

    if recruiter_email:
        recruiter = get_or_create_recruiter(
            session,
            recruiter_email,
            name=recruiter_name,
            company_name=company_name,
            source_name=source_name,
        )
        link_job_to_recruiter(session, job, recruiter)
        session.commit()

    return job
