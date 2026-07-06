"""
The "twenty things to approve" home-screen count -- aggregates every
category of pending item across the app into one summary, instead of
an admin having to know to check five different screens.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.deps import get_current_admin, get_db
from db.models import (
    AdminUser,
    Candidate,
    CandidateDocument,
    CandidateProfileSubmission,
    Email,
    ResumeIngestionRun,
    SkillInventoryItem,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"], dependencies=[Depends(get_current_admin)])


class PendingSummary(BaseModel):
    pending_skills: int
    pending_profile_submissions: int
    pending_resumes: int
    pending_documents: int
    pending_email_drafts: int
    total: int


def _owned_candidate_ids(db: Session, admin: AdminUser) -> list[int]:
    return [c.id for c in db.query(Candidate.id).filter_by(organization_id=admin.organization_id).all()]


@router.get("/pending-summary", response_model=PendingSummary)
def pending_summary(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    owned_ids = _owned_candidate_ids(db, admin)

    pending_skills = (
        db.query(SkillInventoryItem)
        .filter(SkillInventoryItem.candidate_id.in_(owned_ids), SkillInventoryItem.status == "pending")
        .count()
    )
    pending_profiles = (
        db.query(CandidateProfileSubmission)
        .filter(CandidateProfileSubmission.candidate_id.in_(owned_ids), CandidateProfileSubmission.status == "pending")
        .count()
    )
    pending_resumes = (
        db.query(ResumeIngestionRun)
        .filter(ResumeIngestionRun.candidate_id.in_(owned_ids), ResumeIngestionRun.resume_approval_status == "pending")
        .count()
    )
    pending_documents = (
        db.query(CandidateDocument)
        .filter(CandidateDocument.candidate_id.in_(owned_ids), CandidateDocument.status == "pending")
        .count()
    )
    pending_email_drafts = (
        db.query(Email)
        .filter(Email.candidate_id.in_(owned_ids), Email.status == "draft")
        .count()
    )

    total = pending_skills + pending_profiles + pending_resumes + pending_documents + pending_email_drafts

    return PendingSummary(
        pending_skills=pending_skills,
        pending_profile_submissions=pending_profiles,
        pending_resumes=pending_resumes,
        pending_documents=pending_documents,
        pending_email_drafts=pending_email_drafts,
        total=total,
    )
