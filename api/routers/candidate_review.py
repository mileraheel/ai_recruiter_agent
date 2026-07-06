from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from api.deps import get_current_admin, get_db
from api.schemas import CandidateProfileSubmissionResponse, PaginatedResponse, ProfileApprovalDecision, SelfServiceCandidateProfile
from db.models import AdminUser, Candidate, CandidateProfileSubmission

router = APIRouter(prefix="/api/candidate-review", tags=["candidate-review"], dependencies=[Depends(get_current_admin)])

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


@router.get("", response_model=PaginatedResponse[CandidateProfileSubmissionResponse])
def list_pending_submissions(
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    offset = max(0, offset)

    query = (
        db.query(CandidateProfileSubmission)
        .join(Candidate, CandidateProfileSubmission.candidate_id == Candidate.id)
        .filter(CandidateProfileSubmission.status == "pending", Candidate.organization_id == admin.organization_id)
    )
    total = query.count()
    items = query.order_by(CandidateProfileSubmission.created_at.asc()).offset(offset).limit(limit).all()
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/{submission_id}/decision", response_model=CandidateProfileSubmissionResponse)
def decide_submission(
    submission_id: int,
    decision: ProfileApprovalDecision,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    submission = db.query(CandidateProfileSubmission).filter_by(id=submission_id).one_or_none()
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    candidate = db.query(Candidate).filter_by(id=submission.candidate_id).one_or_none()
    if candidate is None or candidate.organization_id != admin.organization_id:
        raise HTTPException(status_code=404, detail="Submission not found")

    if submission.status != "pending":
        raise HTTPException(status_code=409, detail=f"Submission already decided (status={submission.status})")
    if decision.decision not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="decision must be 'approve' or 'reject'")

    if decision.decision == "approve":
        # Re-validate at approval time, not just at submission time --
        # protects against the schema having changed between submission
        # and review, or a submission that was hand-edited some other way.
        try:
            SelfServiceCandidateProfile(**submission.submitted_profile_json)
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=f"Submitted profile no longer validates: {e}")

        candidate.approved_profile_json = submission.submitted_profile_json
        candidate.profile_status = "approved"
        submission.status = "approved"
    else:
        submission.status = "rejected"
        # If this candidate has never had an approved profile, rejecting
        # their only submission puts them back to 'rejected' overall --
        # but if they already have a prior approved profile, that one
        # stays live and profile_status reverts to 'approved', not stuck
        # on the rejected submission.
        candidate.profile_status = "approved" if candidate.approved_profile_json else "rejected"

    submission.reviewed_by = admin.username
    submission.reviewed_at = datetime.now(timezone.utc)
    submission.review_notes = decision.review_notes

    db.commit()
    db.refresh(submission)

    from services.notification_service import notify

    notify(
        db, "candidate", candidate.id,
        title=f"Profile {submission.status}",
        body=f"Your profile submission was {submission.status}."
        + (f" {decision.review_notes}" if decision.review_notes else ""),
        email_address=candidate.login_email,
        organization_id=candidate.organization_id,
    )

    return submission
