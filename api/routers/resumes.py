from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.deps import get_current_admin, get_db, get_app_storage
from db.models import AdminUser, Candidate, Job
from services.candidate_directory import resolve_candidate_profile_for_row
from services.resume_service import ResumeGenerationError, get_or_generate_tailored_resume
from services.storage import Storage

router = APIRouter(prefix="/api/resumes", tags=["resumes"], dependencies=[Depends(get_current_admin)])


class TailorResumeRequest(BaseModel):
    job_id: int
    force_regenerate: bool = False


class TailorResumeResponse(BaseModel):
    resume_version_id: int
    file_name: str
    storage_path: str
    target_title: str | None
    tailoring_summary: str | None
    risk_notes: str | None
    grounding_flags: list[str]
    human_review_required: bool

    class Config:
        from_attributes = True


@router.post("/tailor", response_model=TailorResumeResponse)
def tailor_resume_for_job(
    payload: TailorResumeRequest,
    db: Session = Depends(get_db),
    storage: Storage = Depends(get_app_storage),
    admin: AdminUser = Depends(get_current_admin),
):
    job = db.query(Job).filter_by(id=payload.job_id).one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail=f"No job with id {payload.job_id}")
    if job.candidate_id is None:
        raise HTTPException(status_code=422, detail="Job has no candidate associated -- cannot tailor.")

    candidate_row = db.query(Candidate).filter_by(id=job.candidate_id).one_or_none()
    if (
        candidate_row is None
        or candidate_row.organization_id != admin.organization_id
        or (job.organization_id is not None and job.organization_id != admin.organization_id)
    ):
        # Same response whether the job doesn't exist or belongs to
        # another org -- doesn't confirm to the caller which case it is.
        raise HTTPException(status_code=404, detail=f"No job with id {payload.job_id}")

    resolution = resolve_candidate_profile_for_row(db, candidate_row)

    try:
        version = get_or_generate_tailored_resume(
            db, storage, job, candidate_row, resolution, force_regenerate=payload.force_regenerate
        )
    except ResumeGenerationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    grounding_flags = version.grounding_flags.split("\n") if version.grounding_flags else []

    return TailorResumeResponse(
        resume_version_id=version.id,
        file_name=version.file_name,
        storage_path=version.file_path,
        target_title=version.target_role,
        tailoring_summary=version.tailoring_summary,
        risk_notes=version.risk_notes,
        grounding_flags=grounding_flags,
        human_review_required=version.human_review_required,
    )
