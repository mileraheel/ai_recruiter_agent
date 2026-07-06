from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from api.deps import get_app_storage, get_current_candidate, get_db
from api.schemas import CandidateMeResponse, CandidateProfileSubmissionResponse, SelfServiceCandidateProfile
from db.models import Candidate, CandidateProfileSubmission, Organization
from services.candidate_directory import resume_storage_key
from services.resume_ingestion import ingest_resume
from services.storage import Storage

router = APIRouter(prefix="/api/me", tags=["candidate-self"], dependencies=[Depends(get_current_candidate)])


@router.get("", response_model=CandidateMeResponse)
def get_me(candidate: Candidate = Depends(get_current_candidate), db: Session = Depends(get_db)):
    latest = (
        db.query(CandidateProfileSubmission)
        .filter_by(candidate_id=candidate.id)
        .order_by(CandidateProfileSubmission.created_at.desc())
        .first()
    )
    return CandidateMeResponse(
        id=candidate.id,
        slug=candidate.slug,
        full_name=candidate.full_name,
        login_email=candidate.login_email,
        profile_status=candidate.profile_status,
        approved_profile=candidate.approved_profile_json,
        latest_submission_status=latest.status if latest else None,
    )


@router.put("/profile", response_model=CandidateProfileSubmissionResponse)
def submit_profile(
    payload: SelfServiceCandidateProfile,
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db),
):
    """Creates a new pending submission -- never writes directly to
    Candidate.approved_profile_json. The candidate can resubmit as many
    times as they like; only the admin's approval decision (see
    api/routers/candidate_review.py) makes a submission live."""
    submission = CandidateProfileSubmission(
        candidate_id=candidate.id,
        submitted_profile_json=payload.model_dump(mode="json"),
        status="pending",
    )
    db.add(submission)

    # Keep full_name in sync on the Candidate row itself (used for slug
    # derivation and display) -- but NOT approved_profile_json, which
    # only ever changes on admin approval.
    if payload.full_name and payload.full_name != candidate.full_name:
        candidate.full_name = payload.full_name  # display only; slug stays fixed once created

    if candidate.profile_status in ("no_account", "rejected"):
        candidate.profile_status = "pending"
    elif candidate.profile_status == "approved":
        # A new edit to an already-approved profile goes back to pending
        # review -- the previously approved version stays live and usable
        # (Candidate.approved_profile_json is untouched) until this new
        # submission is itself approved.
        candidate.profile_status = "pending"

    db.commit()
    db.refresh(submission)
    return submission


@router.post("/resume")
async def upload_resume(
    file: UploadFile = File(...),
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db),
    storage: Storage = Depends(get_app_storage),
):
    """Saves the resume to a PENDING location, not the live resume path
    -- extraction/skill-suggestion runs immediately, but nothing about
    this file (including the file itself, not just its extracted
    skills) is used for matching/tailoring until an admin explicitly
    approves it. See services/resume_ingestion.py's ingest_resume
    docstring for why the file itself needs this gate too, not just the
    skills extracted from it."""
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=422, detail="Only .docx resumes are accepted.")

    content = await file.read()
    org = db.query(Organization).filter_by(id=candidate.organization_id).one_or_none()
    if org is None:
        raise HTTPException(status_code=500, detail="Candidate has no organization on record.")

    file_hash = hashlib.sha256(content).hexdigest()
    live_resume_path = resume_storage_key(org.name, candidate.slug)
    pending_key = f"pending_resumes/{live_resume_path.removeprefix('resumes/')}"
    # Timestamped so multiple pending uploads before review don't
    # collide -- admin sees each as its own reviewable run.
    pending_key = pending_key.replace(".docx", f".{file_hash[:10]}.docx")
    storage.save(pending_key, content)

    run = ingest_resume(
        db,
        candidate=candidate,
        resume_file_path=live_resume_path,
        file_bytes=content,
        file_hash=file_hash,
        triggered_by="candidate_upload",
        pending_storage_key=pending_key,
    )

    # NOTE: deliberately NOT touching the live resume's FileWatchState
    # here -- the live file at live_resume_path hasn't changed, only the
    # pending copy has. The watcher's hash for the live path stays as-is
    # until an admin approves this run and the live file actually changes.

    from db.models import AdminUser
    from services.notification_service import notify

    for admin_row in db.query(AdminUser).filter_by(organization_id=candidate.organization_id).all():
        notify(
            db, "admin", admin_row.id,
            title="New resume awaiting approval",
            body=f"{candidate.full_name} uploaded a new resume.",
            email_address=admin_row.email,
            organization_id=candidate.organization_id,
        )

    return {
        "resume_ingestion_run_id": run.id,
        "status": run.status,
        "resume_approval_status": run.resume_approval_status,
        "new_skills_suggested": run.new_skills_suggested,
        "message": "Resume uploaded and pending admin approval. New skills detected will also appear in the approval queue.",
    }


@router.get("/subscription")
def get_my_subscription(candidate: Candidate = Depends(get_current_candidate), db: Session = Depends(get_db)):
    from services.billing_service import get_or_create_subscription

    sub = get_or_create_subscription(db, candidate)
    db.commit()
    return {
        "status": sub.status,
        "monthly_rate": float(sub.monthly_rate) if sub.monthly_rate is not None else None,
        "currency": sub.currency,
        "paused_by": sub.paused_by,
        "paused_at": sub.paused_at,
        "availability_status": candidate.availability_status,
    }


@router.post("/subscription/pause")
def pause_my_subscription(candidate: Candidate = Depends(get_current_candidate), db: Session = Depends(get_db)):
    """Candidate-initiated pause -- not billed, not applied for, until
    they resume. Distinct from an org pausing them (see
    api/routers/candidates.py), tracked via paused_by for audit."""
    from services.billing_service import pause_subscription

    sub = pause_subscription(db, candidate, paused_by="candidate")
    return {"status": sub.status, "paused_by": sub.paused_by}


@router.post("/subscription/resume")
def resume_my_subscription(candidate: Candidate = Depends(get_current_candidate), db: Session = Depends(get_db)):
    from services.billing_service import resume_subscription

    sub = resume_subscription(db, candidate)
    return {"status": sub.status}


@router.put("/availability")
def update_my_availability(
    payload: dict, candidate: Candidate = Depends(get_current_candidate), db: Session = Depends(get_db)
):
    status_value = payload.get("availability_status")
    if status_value not in ("active_looking", "not_looking"):
        raise HTTPException(status_code=422, detail="availability_status must be 'active_looking' or 'not_looking'.")
    candidate.availability_status = status_value
    db.commit()
    return {"availability_status": candidate.availability_status}
