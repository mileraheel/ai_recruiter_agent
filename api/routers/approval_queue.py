from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.deps import get_current_admin, get_db
from api.schemas import PaginatedResponse, SkillApprovalDecision, SkillInventoryItemResponse
from db.models import AdminUser, Candidate, SkillInventoryItem

router = APIRouter(prefix="/api/approval-queue", tags=["approval-queue"], dependencies=[Depends(get_current_admin)])

_VALID_TIERS = {"core", "component", "secondary", "exposure"}
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


@router.get("", response_model=PaginatedResponse[SkillInventoryItemResponse])
def list_pending(
    candidate_id: int | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """Every skill sitting in status='pending' for candidates in THIS
    admin's organization only -- joined against Candidate to enforce
    that, not just filtered client-side."""
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    offset = max(0, offset)

    query = (
        db.query(SkillInventoryItem)
        .join(Candidate, SkillInventoryItem.candidate_id == Candidate.id)
        .filter(SkillInventoryItem.status == "pending", Candidate.organization_id == admin.organization_id)
    )
    if candidate_id is not None:
        query = query.filter(SkillInventoryItem.candidate_id == candidate_id)

    total = query.count()
    items = query.order_by(SkillInventoryItem.created_at.asc()).offset(offset).limit(limit).all()
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/{item_id}/decision", response_model=SkillInventoryItemResponse)
def decide(
    item_id: int,
    decision: SkillApprovalDecision,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    item = db.query(SkillInventoryItem).filter_by(id=item_id).one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Skill inventory item not found")

    candidate_row = db.query(Candidate).filter_by(id=item.candidate_id).one_or_none()
    if candidate_row is None or candidate_row.organization_id != admin.organization_id:
        raise HTTPException(status_code=404, detail="Skill inventory item not found")

    if item.status != "pending":
        raise HTTPException(status_code=409, detail=f"Item already decided (status={item.status})")

    if decision.decision not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="decision must be 'approve' or 'reject'")

    if decision.decision == "approve":
        if decision.tier_override:
            if decision.tier_override not in _VALID_TIERS:
                raise HTTPException(status_code=400, detail=f"tier_override must be one of {_VALID_TIERS}")
            item.tier = decision.tier_override
        item.status = "approved"
    else:
        item.status = "rejected"

    item.reviewed_by = admin.username
    item.reviewed_at = datetime.now(timezone.utc)
    item.review_notes = decision.review_notes

    db.commit()
    db.refresh(item)
    return item
