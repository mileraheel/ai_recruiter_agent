"""
Single-job prepare/send endpoints. For posting a job once and fanning
out across every matched candidate, see api/routers/job_posting.py --
that's the primary workflow now; these endpoints remain for reviewing/
re-sending one candidate's application individually (e.g. after editing
their profile) without re-running the whole batch.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.deps import get_current_admin, get_db, get_app_storage
from db.models import AdminUser, Candidate, Email, Job
from services.application_service import (
    ApplicationError,
    prepare_application_for_job,
    send_prepared_email,
)
from services.storage import Storage

router = APIRouter(prefix="/api/applications", tags=["applications"], dependencies=[Depends(get_current_admin)])


class PrepareApplicationResponse(BaseModel):
    email_id: int
    to_email: str | None
    subject: str
    body: str
    resume_file_name: str
    resume_human_review_required: bool
    resume_risk_notes: str | None


class SendApplicationRequest(BaseModel):
    confirm: bool = False


class SendApplicationResponse(BaseModel):
    email_id: int
    status: str
    gmail_object_id: str | None
    send_mode: str | None


@router.post("/{job_id}/prepare", response_model=PrepareApplicationResponse)
def prepare_application(
    job_id: int,
    db: Session = Depends(get_db),
    storage: Storage = Depends(get_app_storage),
    admin: AdminUser = Depends(get_current_admin),
):
    job = db.query(Job).filter_by(id=job_id).one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail=f"No job with id {job_id}")
    if job.candidate_id is None:
        raise HTTPException(status_code=422, detail="Job has no candidate associated.")
    candidate_row = db.query(Candidate).filter_by(id=job.candidate_id).one_or_none()
    if (
        candidate_row is None
        or candidate_row.organization_id != admin.organization_id
        or (job.organization_id is not None and job.organization_id != admin.organization_id)
    ):
        raise HTTPException(status_code=404, detail=f"No job with id {job_id}")

    try:
        result = prepare_application_for_job(db, storage, job, candidate_row)
    except ApplicationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return PrepareApplicationResponse(**result.__dict__)


@router.post("/emails/{email_id}/send", response_model=SendApplicationResponse)
def send_application(
    email_id: int,
    payload: SendApplicationRequest,
    db: Session = Depends(get_db),
    storage: Storage = Depends(get_app_storage),
    admin: AdminUser = Depends(get_current_admin),
):
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="Set confirm=true to send. This is the real send action.")

    email_row = db.query(Email).filter_by(id=email_id).one_or_none()
    if email_row is None:
        raise HTTPException(status_code=404, detail="Prepared email not found -- call /prepare first.")
    candidate_row = db.query(Candidate).filter_by(id=email_row.candidate_id).one_or_none()
    if candidate_row is None or candidate_row.organization_id != admin.organization_id:
        raise HTTPException(status_code=404, detail="Prepared email not found -- call /prepare first.")

    try:
        result = send_prepared_email(db, storage, email_id)
    except ApplicationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return SendApplicationResponse(**result.__dict__)
