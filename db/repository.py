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
from db.models import Job, JobSource


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
) -> Job:
    """Persists one job + its eligibility decision. Idempotent on
    (source, dedup_hash): re-checking the same job_title/company/location
    updates the existing row (fresh status, updated_at) rather than creating
    a duplicate -- so re-running check-job on the same posting after a
    config change doesn't pile up copies."""
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

    session.commit()
    session.refresh(job)
    return job
