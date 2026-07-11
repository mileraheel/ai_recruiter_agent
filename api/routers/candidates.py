from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from api.deps import get_current_admin, get_db, get_app_storage
from api.schemas import CandidateSummary, PaginatedResponse, WatchCycleResponse
from db.models import AdminUser, Candidate, Organization, SkillInventoryItem
from services.candidate_directory import list_all_candidate_resolutions, resume_storage_key
from services.email_sender import send_invite_email
from services.file_watcher import run_watch_cycle
from services.invite_service import create_invite
from services.storage import Storage

router = APIRouter(prefix="/api/candidates", tags=["candidates"], dependencies=[Depends(get_current_admin)])

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


class InviteCandidateRequest(BaseModel):
    email: EmailStr


class InviteCandidateResponse(BaseModel):
    invited_email: str


@router.get("", response_model=PaginatedResponse[CandidateSummary])
def list_candidates(
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
    db: Session = Depends(get_db),
    storage: Storage = Depends(get_app_storage),
    admin: AdminUser = Depends(get_current_admin),
):
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    offset = max(0, offset)

    summaries = []
    for slug, resolution in list_all_candidate_resolutions(db, admin.organization_id):
        row = db.query(Candidate).filter_by(organization_id=admin.organization_id, slug=slug).one_or_none()
        pending_count = 0
        candidate_row_id = -1
        if row:
            candidate_row_id = row.id
            pending_count = (
                db.query(SkillInventoryItem).filter_by(candidate_id=row.id, status="pending").count()
            )

        if resolution.status == "ok":
            profile = resolution.profile
            summaries.append(
                CandidateSummary(
                    id=candidate_row_id,
                    slug=slug,
                    full_name=profile.candidate.full_name,
                    resume_path=profile.candidate.base_resume_path,
                    resume_exists=storage.exists(profile.candidate.base_resume_path),
                    strict_skill_match_required=profile.application_policy.strict_skill_match_required,
                    pending_skill_count=pending_count,
                    status="ok",
                    status_message=None,
                )
            )
        else:
            # Best-effort resume path guess for orgs/candidates that
            # haven't fully resolved yet (e.g. needs_search_config) --
            # we still know the org name from the admin's own session.
            org = db.query(Organization).filter_by(id=admin.organization_id).one()
            guessed_path = resume_storage_key(org.name, slug)
            summaries.append(
                CandidateSummary(
                    id=candidate_row_id,
                    slug=slug,
                    full_name=row.full_name if row else slug,
                    resume_path=guessed_path,
                    resume_exists=storage.exists(guessed_path),
                    strict_skill_match_required=False,
                    pending_skill_count=pending_count,
                    status=resolution.status,
                    status_message=resolution.message,
                )
            )
    total = len(summaries)
    page = summaries[offset:offset + limit]
    return PaginatedResponse(items=page, total=total, limit=limit, offset=offset)


@router.post("/invite", response_model=InviteCandidateResponse)
def invite_candidate(
    payload: InviteCandidateRequest,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """Admin invites a candidate into their OWN organization only --
    organization_id always comes from the admin's own session, never
    from the request body."""
    org = db.query(Organization).filter_by(id=admin.organization_id).one()

    from services.platform_settings_service import get_or_create_platform_settings

    settings = get_or_create_platform_settings(db)
    invite, otp = create_invite(
        db, email=payload.email, role="candidate", organization_id=admin.organization_id,
        invited_by_type="admin", invited_by_id=admin.id,
    )
    try:
        send_invite_email(db, payload.email, otp, "candidate", org.name, settings.invite_expire_days)
    except RuntimeError as e:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"Could not invite candidate: email failed to send: {e}")
    db.commit()

    return InviteCandidateResponse(invited_email=payload.email)


@router.get("/{candidate_id}/subscription")
def get_candidate_subscription(
    candidate_id: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)
):
    from services.billing_service import get_or_create_subscription

    candidate = db.query(Candidate).filter_by(id=candidate_id).one_or_none()
    if candidate is None or candidate.organization_id != admin.organization_id:
        raise HTTPException(status_code=404, detail="Candidate not found.")

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


@router.post("/{candidate_id}/subscription/pause")
def pause_candidate_subscription(
    candidate_id: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)
):
    """Org-initiated pause -- distinct from the candidate pausing
    themselves, tracked via paused_by for audit/support purposes."""
    from services.billing_service import pause_subscription

    candidate = db.query(Candidate).filter_by(id=candidate_id).one_or_none()
    if candidate is None or candidate.organization_id != admin.organization_id:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    sub = pause_subscription(db, candidate, paused_by="org")
    return {"status": sub.status, "paused_by": sub.paused_by}


@router.post("/{candidate_id}/subscription/resume")
def resume_candidate_subscription(
    candidate_id: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)
):
    from services.billing_service import resume_subscription

    candidate = db.query(Candidate).filter_by(id=candidate_id).one_or_none()
    if candidate is None or candidate.organization_id != admin.organization_id:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    sub = resume_subscription(db, candidate)
    return {"status": sub.status}


@router.put("/{candidate_id}/subscription/rate")
def set_candidate_rate(
    candidate_id: int, payload: dict, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)
):
    from services.billing_service import get_or_create_subscription

    candidate = db.query(Candidate).filter_by(id=candidate_id).one_or_none()
    if candidate is None or candidate.organization_id != admin.organization_id:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    monthly_rate = payload.get("monthly_rate")
    if monthly_rate is not None and (not isinstance(monthly_rate, (int, float)) or monthly_rate < 0):
        raise HTTPException(status_code=422, detail="monthly_rate must be a non-negative number.")

    sub = get_or_create_subscription(db, candidate)
    sub.monthly_rate = monthly_rate
    db.commit()
    return {"monthly_rate": float(sub.monthly_rate) if sub.monthly_rate is not None else None}


@router.post("/watch-cycle", response_model=WatchCycleResponse)
def trigger_watch_cycle(db: Session = Depends(get_db), storage: Storage = Depends(get_app_storage)):
    """Manually triggers what the background loop otherwise runs on a
    timer -- runs across ALL organizations (there's no meaningful
    'org-scoped watch cycle' for a resume-file check)."""
    result = run_watch_cycle(db, storage)
    return WatchCycleResponse(**result)
