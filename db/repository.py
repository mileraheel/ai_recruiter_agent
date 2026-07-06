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
from db.models import Job, JobContact, JobSource, Candidate


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


def get_or_create_job_contact(
    session: Session,
    recruiter_email: str,
    *,
    recruiter_name: str | None = None,
    recruiter_company: str | None = None,
    recruiter_phone: str | None = None,
    recruiter_linkedin_url: str | None = None,
    source_name: str | None = None,
) -> JobContact:
    """job_contacts is the deduplicated recruiter entity, keyed by email.
    A job posting has exactly one recruiter (many jobs -> one recruiter),
    so this returns the SAME row for the same email across multiple
    calls -- callers link a job to it via job.job_contact_id, they don't
    create a new job_contacts row per job. New info fills in blanks on an
    existing record but doesn't overwrite what's already there, since a
    later, sparser posting shouldn't erase a better name/phone/company
    captured earlier."""
    email_normalized = recruiter_email.strip().lower()
    contact = session.query(JobContact).filter_by(recruiter_email=email_normalized).one_or_none()
    if contact is None:
        contact = JobContact(
            recruiter_email=email_normalized,
            recruiter_name=recruiter_name,
            recruiter_company=recruiter_company,
            recruiter_phone=recruiter_phone,
            recruiter_linkedin_url=recruiter_linkedin_url,
            source_name=source_name,
        )
        session.add(contact)
        session.flush()  # get contact.id without a full commit
    else:
        contact.recruiter_name = contact.recruiter_name or recruiter_name
        contact.recruiter_company = contact.recruiter_company or recruiter_company
        contact.recruiter_phone = contact.recruiter_phone or recruiter_phone
        contact.recruiter_linkedin_url = contact.recruiter_linkedin_url or recruiter_linkedin_url
    return contact


def get_or_create_candidate(session: Session, organization_id: int, slug: str, full_name: str) -> Candidate:
    """Same idempotent pattern as get_or_create_source/job_contact.
    Normally db/seed.py has already created this row from config, but
    save_job_check falls back to creating it here too so a candidate
    added to config without re-running seed.py doesn't silently fail.
    Scoped by organization_id -- slug alone is not unique across orgs."""
    candidate_row = (
        session.query(Candidate).filter_by(organization_id=organization_id, slug=slug).one_or_none()
    )
    if candidate_row is None:
        candidate_row = Candidate(organization_id=organization_id, slug=slug, full_name=full_name)
        session.add(candidate_row)
        session.flush()
    return candidate_row


def save_job_check(
    session: Session,
    *,
    job_title: str,
    description_text: str,
    eligibility_result: EligibilityResult,
    organization_id: int | None = None,
    candidate_slug: str | None = None,
    candidate_full_name: str | None = None,
    source_name: str = "manual_cli",
    company_name: str | None = None,
    location: str | None = None,
    work_mode: str | None = None,
    job_url: str | None = None,
    recruiter_email: str | None = None,
    recruiter_name: str | None = None,
) -> Job:
    """Persists one job + its eligibility decision, and -- if a recruiter
    email is provided -- links the job to its (deduplicated) job_contacts
    row via job.job_contact_id. Idempotent on (candidate, source,
    dedup_hash) for the job, and on email for the recruiter: re-checking
    the same posting for the same candidate, or hearing from the same
    recruiter again on a different job, updates existing rows rather than
    duplicating them. Scoped per candidate now -- the same posting
    checked for two different candidates produces two separate Job rows,
    since eligibility/status can differ per candidate."""
    source = get_or_create_source(session, source_name)
    dedup_hash = _dedup_hash(job_title, company_name, location)

    candidate_row = None
    if candidate_slug and organization_id is not None:
        candidate_row = get_or_create_candidate(session, organization_id, candidate_slug, candidate_full_name or candidate_slug)

    existing = (
        session.query(Job)
        .filter_by(
            source_id=source.id,
            dedup_hash=dedup_hash,
            candidate_id=candidate_row.id if candidate_row else None,
        )
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
        job = Job(
            organization_id=organization_id,
            source_id=source.id,
            source_name=source_name,
            dedup_hash=dedup_hash,
            candidate_id=candidate_row.id if candidate_row else None,
        )
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
        contact = get_or_create_job_contact(
            session,
            recruiter_email,
            recruiter_name=recruiter_name,
            recruiter_company=company_name,
            source_name=source_name,
        )
        job.job_contact_id = contact.id

    session.commit()
    session.refresh(job)
    return job
