"""
The primary "post a job" workflow: admin pastes/uploads ONE job
posting. The app evaluates it against EVERY resolvable candidate
(core/eligibility.py + core/role_match.py, unchanged) and, for every
candidate that comes back eligible, automatically tailors a resume and
composes an email -- prepare_application_for_job is pure generation, no
external call, so doing it automatically across all matches is safe.

Sending is NEVER automatic here. /post-and-match returns a batch of
prepared drafts for the admin to review; a separate /batch-send call,
requiring confirm=true, is what actually reaches Gmail -- for one
candidate or many, but always as an explicit, reviewable action.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.deps import get_current_admin, get_db, get_app_storage
from core.eligibility import evaluate_eligibility
from core.extraction import (
    extract_company_name,
    extract_emails,
    extract_job_title,
    extract_location,
    extract_recruiter_name,
    extract_work_mode,
)
from db.models import AdminUser, Candidate, Email
from db.repository import save_job_check
from services.application_service import ApplicationError, prepare_application_for_job, send_prepared_email
from services.billing_service import is_candidate_active
from services.candidate_directory import list_all_candidate_resolutions
from services.volume_limits import check_job_volume
from services.screenshot_ingestion import extract_job_posting_from_screenshot
from services.storage import Storage

router = APIRouter(prefix="/api/job-posting", tags=["job-posting"], dependencies=[Depends(get_current_admin)])


class PostJobRequest(BaseModel):
    job_description_text: str


class CandidateMatchResult(BaseModel):
    candidate_slug: str
    candidate_full_name: str
    eligibility_status: str  # eligible | skipped | needs_human_review | not_active
    reason: str | None = None
    saved_job_id: int | None = None
    email_id: int | None = None
    to_email: str | None = None
    subject: str | None = None
    body: str | None = None
    resume_file_name: str | None = None
    resume_human_review_required: bool | None = None
    prepare_error: str | None = None


class PostJobResponse(BaseModel):
    job_title: str | None
    company_name: str | None
    location: str | None
    work_mode: str | None
    recruiter_email: str | None
    recruiter_name: str | None
    results: list[CandidateMatchResult]


def _post_and_match_core(
    db: Session,
    storage: Storage,
    admin: AdminUser,
    text: str,
    job_title: str | None,
    location: str | None,
    work_mode: str | None,
    recruiter_email: str | None,
    recruiter_name: str | None,
    company_name: str | None,
) -> PostJobResponse:
    """Shared by both entry points (paste-text and screenshot) -- once
    the job text and extracted fields exist, matching/fan-out is
    identical regardless of how the text arrived."""
    results: list[CandidateMatchResult] = []

    # Scoped to the admin's OWN organization only -- posting a job never
    # fans out across tenant boundaries.
    for slug, resolution in list_all_candidate_resolutions(db, admin.organization_id):
        if resolution.status != "ok":
            results.append(
                CandidateMatchResult(
                    candidate_slug=slug,
                    candidate_full_name=slug,
                    eligibility_status="not_active",
                    reason=resolution.message,
                )
            )
            continue

        candidate_row_for_billing = (
            db.query(Candidate).filter_by(organization_id=admin.organization_id, slug=slug).one()
        )
        active, inactive_reason = is_candidate_active(db, candidate_row_for_billing)
        if not active:
            results.append(
                CandidateMatchResult(
                    candidate_slug=slug,
                    candidate_full_name=resolution.profile.candidate.full_name,
                    eligibility_status="not_active",
                    reason=inactive_reason,
                )
            )
            continue

        within_volume, volume_reason = check_job_volume(db, admin.organization_id)
        if not within_volume:
            results.append(
                CandidateMatchResult(
                    candidate_slug=slug,
                    candidate_full_name=resolution.profile.candidate.full_name,
                    eligibility_status="not_active",
                    reason=volume_reason,
                )
            )
            continue

        profile = resolution.profile
        eligibility = evaluate_eligibility(
            job_description_text=text,
            candidate=profile.candidate,
            search_config=profile.search,
            job_location=location,
            job_work_mode=work_mode,
            strict_skill_match_required=profile.application_policy.strict_skill_match_required,
        )

        job = save_job_check(
            db,
            job_title=job_title or "(untitled)",
            description_text=text,
            eligibility_result=eligibility,
            organization_id=admin.organization_id,
            candidate_slug=slug,
            candidate_full_name=profile.candidate.full_name,
            company_name=company_name,
            location=location,
            work_mode=work_mode,
            recruiter_email=recruiter_email,
            recruiter_name=recruiter_name,
        )

        result = CandidateMatchResult(
            candidate_slug=slug,
            candidate_full_name=profile.candidate.full_name,
            eligibility_status=eligibility.status.value,
            reason=eligibility.reason,
            saved_job_id=job.id,
        )

        if eligibility.status.value == "eligible":
            candidate_row = (
                db.query(Candidate)
                .filter_by(organization_id=admin.organization_id, slug=slug)
                .one()
            )
            try:
                prepared = prepare_application_for_job(db, storage, job, candidate_row, resolution)
                result.email_id = prepared.email_id
                result.to_email = prepared.to_email
                result.subject = prepared.subject
                result.body = prepared.body
                result.resume_file_name = prepared.resume_file_name
                result.resume_human_review_required = prepared.resume_human_review_required
            except ApplicationError as e:
                result.prepare_error = str(e)

        results.append(result)

    return PostJobResponse(
        job_title=job_title,
        company_name=company_name,
        location=location,
        work_mode=work_mode,
        recruiter_email=recruiter_email,
        recruiter_name=recruiter_name,
        results=results,
    )


@router.post("/post-and-match", response_model=PostJobResponse)
def post_and_match(
    payload: PostJobRequest,
    db: Session = Depends(get_db),
    storage: Storage = Depends(get_app_storage),
    admin: AdminUser = Depends(get_current_admin),
):
    text = payload.job_description_text
    job_title = extract_job_title(text)
    location = extract_location(text)
    work_mode = extract_work_mode(text)
    emails_found = extract_emails(text)
    recruiter_email = emails_found[0] if emails_found else None
    recruiter_name = extract_recruiter_name(text, recruiter_email)
    company_name = extract_company_name(text, recruiter_email)

    return _post_and_match_core(
        db, storage, admin, text, job_title, location, work_mode, recruiter_email, recruiter_name, company_name
    )


@router.post("/post-and-match-screenshot", response_model=PostJobResponse)
async def post_and_match_screenshot(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    storage: Storage = Depends(get_app_storage),
    admin: AdminUser = Depends(get_current_admin),
):
    """Same fan-out as /post-and-match, but the job text comes from a
    screenshot (e.g. a Dice/LinkedIn posting) via Claude's vision API
    instead of pasted text -- the one gap flagged earlier: screenshot
    intake previously only worked on the single-candidate Quick Check
    screen, not the real batch-posting flow."""
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

    return _post_and_match_core(
        db, storage, admin, text, job_title, location, work_mode, recruiter_email, recruiter_name, company_name
    )


class BatchSendRequest(BaseModel):
    email_ids: list[int]
    confirm: bool = False


class BatchSendItemResult(BaseModel):
    email_id: int
    status: str | None = None
    gmail_object_id: str | None = None
    send_mode: str | None = None
    error: str | None = None


class BatchSendResponse(BaseModel):
    results: list[BatchSendItemResult]


@router.post("/batch-send", response_model=BatchSendResponse)
def batch_send(
    payload: BatchSendRequest,
    db: Session = Depends(get_db),
    storage: Storage = Depends(get_app_storage),
    admin: AdminUser = Depends(get_current_admin),
):
    if not payload.confirm:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="Set confirm=true to send. This is the real send action.")

    results = []
    for email_id in payload.email_ids:
        # Authorization check: email_id is a guessable numeric id, so
        # verify the underlying candidate belongs to THIS admin's org
        # before sending anything on their behalf. Not just a data
        # filter -- a wrong org here would mean sending an email as
        # someone else's candidate.
        email_row = db.query(Email).filter_by(id=email_id).one_or_none()
        if email_row is None:
            results.append(BatchSendItemResult(email_id=email_id, error="Prepared email not found."))
            continue
        candidate_row = db.query(Candidate).filter_by(id=email_row.candidate_id).one_or_none()
        if candidate_row is None or candidate_row.organization_id != admin.organization_id:
            results.append(BatchSendItemResult(email_id=email_id, error="Not found in your organization."))
            continue

        try:
            sent = send_prepared_email(db, storage, email_id)
            results.append(
                BatchSendItemResult(
                    email_id=email_id, status=sent.status, gmail_object_id=sent.gmail_object_id, send_mode=sent.send_mode
                )
            )
        except ApplicationError as e:
            # One candidate's failure (e.g. no connected Gmail) does not
            # abort the batch -- every other prepared email still gets
            # its own send attempt.
            results.append(BatchSendItemResult(email_id=email_id, error=str(e)))

    return BatchSendResponse(results=results)
