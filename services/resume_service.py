"""
Shared "generate (or reuse) a tailored resume for this job" logic --
used by both api/routers/resumes.py (explicit tailor action) and
api/routers/applications.py (prepare-to-send flow, which needs a
tailored resume as one of its two components alongside the email).
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from core.job_shape_classifier import build_emphasis_rules_text
from core.role_classifier import classify_role
from db.models import Candidate, Job, ResumeVersion, SkillInventoryItem
from services.candidate_directory import CandidateResolution, generated_storage_prefix, resolve_candidate_profile_for_row
from services.resume_docx_writer import build_resume_filename, render_resume_docx
from services.resume_ingestion import extract_text_from_docx
from services.resume_tailoring import tailor_resume
from services.storage import Storage


class ResumeGenerationError(Exception):
    pass


@dataclass
class GeneratedResume:
    version: ResumeVersion
    docx_bytes: bytes | None  # None when reusing an already-saved version without re-reading it


def get_or_generate_tailored_resume(
    db: Session,
    storage: Storage,
    job: Job,
    candidate_row: Candidate,
    resolution: CandidateResolution | None = None,
    force_regenerate: bool = False,
) -> ResumeVersion:
    """Reuses an existing ResumeVersion for this job_id unless
    force_regenerate=True. Raises ResumeGenerationError (caller maps to
    the appropriate HTTP status) rather than a bare RuntimeError, so
    callers in different routers get consistent error handling."""
    if not force_regenerate:
        existing = db.query(ResumeVersion).filter_by(job_id=job.id).order_by(ResumeVersion.created_at.desc()).first()
        if existing:
            return existing

    resolution = resolution or resolve_candidate_profile_for_row(db, candidate_row)
    if resolution.status != "ok":
        raise ResumeGenerationError(resolution.message or f"Candidate '{candidate_row.slug}' is not active.")
    profile = resolution.profile

    if not storage.exists(profile.candidate.base_resume_path):
        raise ResumeGenerationError(
            f"Master resume not found at {profile.candidate.base_resume_path} -- cannot tailor."
        )

    master_resume_bytes = storage.read(profile.candidate.base_resume_path)
    master_resume_text = extract_text_from_docx(master_resume_bytes)

    approved_skills = (
        db.query(SkillInventoryItem)
        .filter_by(candidate_id=candidate_row.id, status="approved")
        .all()
    )

    matched_categories = classify_role(job.description_text or "")
    emphasis_rules = build_emphasis_rules_text(job.job_title, job.description_text or "")

    try:
        content = tailor_resume(
            master_resume_text=master_resume_text,
            approved_skills=approved_skills,
            job_description_text=job.description_text or "",
            matched_categories=matched_categories,
            job_emphasis_rules=emphasis_rules,
        )
    except RuntimeError as e:
        raise ResumeGenerationError(f"Tailoring failed: {e}")

    docx_bytes = render_resume_docx(
        content,
        candidate_full_name=profile.candidate.full_name,
        contact_line=f"{profile.candidate.phone} | {profile.candidate.email}",
        location=profile.candidate.location,
    )

    file_name = build_resume_filename(profile.candidate.full_name, content.target_title)
    storage_key = f"{generated_storage_prefix(profile.organization_name, candidate_row.slug)}/{file_name}"
    storage.save(storage_key, docx_bytes)

    version = ResumeVersion(
        candidate_id=candidate_row.id,
        job_id=job.id,
        target_role=content.target_title,
        company_name=job.company_name,
        file_name=file_name,
        file_path=storage_key,
        tailoring_summary=content.tailoring_summary,
        risk_notes=content.risk_notes,
        grounding_flags="\n".join(content.grounding_flags) if content.grounding_flags else None,
        human_review_required=bool(content.grounding_flags),
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version
