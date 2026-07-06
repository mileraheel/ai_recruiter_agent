"""
Admin review for the two candidate-submitted artifacts that need a
human sign-off beyond skill extraction: documents (passport, visa,
etc.) and the resume FILE itself (separate from the skills extracted
from it -- see services/resume_ingestion.py's docstring for why).
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.deps import get_app_storage, get_current_admin, get_db
from db.models import AdminUser, Candidate, CandidateDocument, ResumeIngestionRun
from services.storage import Storage

router = APIRouter(prefix="/api/candidates", tags=["candidate-artifact-review"], dependencies=[Depends(get_current_admin)])


def _owned_candidate_ids(db: Session, admin: AdminUser) -> list[int]:
    return [c.id for c in db.query(Candidate.id).filter_by(organization_id=admin.organization_id).all()]


# --- Documents ----------------------------------------------------------

@router.get("/documents")
def list_pending_documents(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    owned_ids = _owned_candidate_ids(db, admin)
    docs = (
        db.query(CandidateDocument)
        .filter(CandidateDocument.candidate_id.in_(owned_ids), CandidateDocument.status == "pending")
        .order_by(CandidateDocument.created_at.asc())
        .all()
    )
    results = []
    for d in docs:
        candidate = db.query(Candidate).filter_by(id=d.candidate_id).one()
        results.append({
            "id": d.id, "candidate_id": d.candidate_id, "candidate_name": candidate.full_name,
            "document_type": d.document_type, "file_name": d.file_name, "status": d.status,
            "created_at": d.created_at,
        })
    return results


class DocumentDecision(BaseModel):
    decision: str  # "approve" | "reject"
    review_notes: str | None = None


@router.post("/documents/{document_id}/decision")
def decide_document(
    document_id: int,
    payload: DocumentDecision,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    doc = db.query(CandidateDocument).filter_by(id=document_id).one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    candidate = db.query(Candidate).filter_by(id=doc.candidate_id).one_or_none()
    if candidate is None or candidate.organization_id != admin.organization_id:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status != "pending":
        raise HTTPException(status_code=409, detail=f"Already decided (status={doc.status})")
    if payload.decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="decision must be 'approve' or 'reject'")

    doc.status = "approved" if payload.decision == "approve" else "rejected"
    doc.reviewed_by = admin.username
    doc.reviewed_at = datetime.now(timezone.utc)
    doc.review_notes = payload.review_notes
    db.commit()

    from services.notification_service import notify

    notify(
        db, "candidate", candidate.id,
        title=f"Document {doc.status}",
        body=f"Your {doc.document_type} was {doc.status}" + (f": {payload.review_notes}" if payload.review_notes else "."),
        email_address=candidate.login_email,
        organization_id=candidate.organization_id,
    )

    return {"id": doc.id, "status": doc.status}


# --- Resume file approvals ------------------------------------------------

@router.get("/resume-approvals")
def list_pending_resume_approvals(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    owned_ids = _owned_candidate_ids(db, admin)
    runs = (
        db.query(ResumeIngestionRun)
        .filter(
            ResumeIngestionRun.candidate_id.in_(owned_ids),
            ResumeIngestionRun.resume_approval_status == "pending",
        )
        .order_by(ResumeIngestionRun.created_at.asc())
        .all()
    )
    results = []
    for run in runs:
        candidate = db.query(Candidate).filter_by(id=run.candidate_id).one()
        results.append({
            "id": run.id, "candidate_id": run.candidate_id, "candidate_name": candidate.full_name,
            "new_skills_suggested": run.new_skills_suggested, "status": run.status,
            "created_at": run.created_at,
        })
    return results


class ResumeApprovalDecision(BaseModel):
    decision: str  # "approve" | "reject"


@router.post("/resume-approvals/{run_id}/decision")
def decide_resume_approval(
    run_id: int,
    payload: ResumeApprovalDecision,
    db: Session = Depends(get_db),
    storage: Storage = Depends(get_app_storage),
    admin: AdminUser = Depends(get_current_admin),
):
    run = db.query(ResumeIngestionRun).filter_by(id=run_id).one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Resume approval not found")
    candidate = db.query(Candidate).filter_by(id=run.candidate_id).one_or_none()
    if candidate is None or candidate.organization_id != admin.organization_id:
        raise HTTPException(status_code=404, detail="Resume approval not found")
    if run.resume_approval_status != "pending":
        raise HTTPException(status_code=409, detail=f"Already decided (status={run.resume_approval_status})")
    if payload.decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="decision must be 'approve' or 'reject'")

    if payload.decision == "approve":
        if not run.pending_storage_key:
            raise HTTPException(status_code=422, detail="No pending file recorded for this run.")
        content = storage.read(run.pending_storage_key)
        storage.save(run.resume_file_path, content)  # promote pending -> live
        run.active_storage_key = run.resume_file_path
        run.resume_approval_status = "approved"

        # The live file actually changed -- update the watcher's hash so
        # it doesn't immediately re-ingest what an admin just approved.
        from services.file_watcher import get_watch_state
        import hashlib
        state = get_watch_state(db, run.resume_file_path, "resume")
        state.last_hash = hashlib.sha256(content).hexdigest()
    else:
        run.resume_approval_status = "rejected"

    run.resume_approved_by = admin.username
    run.resume_approved_at = datetime.now(timezone.utc)
    db.commit()

    from services.notification_service import notify

    notify(
        db, "candidate", candidate.id,
        title=f"Resume {run.resume_approval_status}",
        body=f"Your resume update was {run.resume_approval_status}.",
        email_address=candidate.login_email,
        organization_id=candidate.organization_id,
    )

    return {"id": run.id, "resume_approval_status": run.resume_approval_status}
