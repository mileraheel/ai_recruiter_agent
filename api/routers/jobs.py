from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from api.deps import get_current_admin, get_db
from api.schemas import JobCheckRequest, JobCheckResponse
from core.eligibility import evaluate_eligibility
from core.extraction import (
    extract_company_name,
    extract_emails,
    extract_job_title,
    extract_location,
    extract_recruiter_name,
    extract_work_mode,
)
from db.models import AdminUser
from db.repository import save_job_check
from services.candidate_directory import resolve_candidate_profile
from services.screenshot_ingestion import extract_job_posting_from_screenshot

router = APIRouter(prefix="/api/jobs", tags=["jobs"], dependencies=[Depends(get_current_admin)])


def _resolve_profile_or_422(db: Session, organization_id: int, slug: str):
    resolution = resolve_candidate_profile(db, organization_id, slug)
    if resolution.status != "ok":
        raise HTTPException(status_code=422, detail=resolution.message or f"Candidate '{slug}' is not active.")
    return resolution.profile


def _run_check(profile, organization_id: int, text: str, location: str | None, work_mode: str | None,
                recruiter_email: str | None, recruiter_name: str | None,
                company_name: str | None, job_title: str | None, save: bool, db: Session) -> JobCheckResponse:
    result = evaluate_eligibility(
        job_description_text=text,
        candidate=profile.candidate,
        search_config=profile.search,
        job_location=location,
        job_work_mode=work_mode,
        strict_skill_match_required=profile.application_policy.strict_skill_match_required,
    )

    saved_job_id = None
    if save:
        job = save_job_check(
            db,
            job_title=job_title or "(untitled)",
            description_text=text,
            eligibility_result=result,
            organization_id=organization_id,
            candidate_slug=profile.resolved_id(),
            candidate_full_name=profile.candidate.full_name,
            company_name=company_name,
            location=location,
            work_mode=work_mode,
            recruiter_email=recruiter_email,
            recruiter_name=recruiter_name,
        )
        saved_job_id = job.id

    return JobCheckResponse(
        job_title=job_title,
        company_name=company_name,
        location=location,
        work_mode=work_mode,
        recruiter_email=recruiter_email,
        recruiter_name=recruiter_name,
        status=result.status.value,
        reason=result.reason,
        matched_signals=result.matched_signals,
        saved_job_id=saved_job_id,
    )


@router.post("/check", response_model=JobCheckResponse)
def check_job(payload: JobCheckRequest, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    profile = _resolve_profile_or_422(db, admin.organization_id, payload.candidate_slug)

    text = payload.job_description_text
    job_title = extract_job_title(text)
    location = payload.job_location or extract_location(text)
    work_mode = payload.job_work_mode or extract_work_mode(text)
    emails_found = extract_emails(text)
    recruiter_email = emails_found[0] if emails_found else None
    recruiter_name = extract_recruiter_name(text, recruiter_email)
    company_name = extract_company_name(text, recruiter_email)

    return _run_check(profile, admin.organization_id, text, location, work_mode, recruiter_email, recruiter_name,
                       company_name, job_title, payload.save, db)


@router.post("/check-screenshot", response_model=JobCheckResponse)
async def check_job_screenshot(
    candidate_slug: str = Form(...),
    save: bool = Form(True),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """Same eligibility pipeline as /check, but the job text comes from
    a screenshot via Claude's vision API instead of being pasted in."""
    profile = _resolve_profile_or_422(db, admin.organization_id, candidate_slug)

    image_bytes = await file.read()
    try:
        extracted = extract_job_posting_from_screenshot(image_bytes, file.filename or "upload.png")
    except (RuntimeError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e))

    text = extracted.raw_text
    if not text.strip():
        raise HTTPException(status_code=422, detail="No job text could be read from the screenshot.")

    location = extracted.location or extract_location(text)
    work_mode = extracted.work_mode or extract_work_mode(text)
    emails_found = extract_emails(text)
    recruiter_email = extracted.recruiter_email or (emails_found[0] if emails_found else None)
    recruiter_name = extracted.recruiter_name or extract_recruiter_name(text, recruiter_email)
    company_name = extracted.company_name or extract_company_name(text, recruiter_email)
    job_title = extracted.job_title or extract_job_title(text)

    return _run_check(profile, admin.organization_id, text, location, work_mode, recruiter_email, recruiter_name,
                       company_name, job_title, save, db)
