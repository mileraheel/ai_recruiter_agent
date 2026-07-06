"""
Admin-editable operational config per candidate -- what used to be
candidate.yaml's `search:`/`application_policy:`/`email.send_mode`
blocks. This is the actual point of retiring the YAML file: an org
admin configures their own candidates' search keywords from the UI,
no file/shell access needed.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.deps import get_current_admin, get_db
from db.models import AdminUser, Candidate
from services.candidate_directory import get_or_create_operational_config

router = APIRouter(prefix="/api/candidates", tags=["candidate-config"], dependencies=[Depends(get_current_admin)])


class SearchConfigPayload(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    required_keywords: list[str] = Field(default_factory=list)
    nice_to_have_keywords: list[str] = Field(default_factory=list)
    excluded_keywords: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    work_mode: list[str] = Field(default_factory=list)
    employment_type: list[str] = Field(default_factory=list)


class OperationalConfigRequest(BaseModel):
    search_config: SearchConfigPayload
    strict_skill_match_required: bool = True
    send_mode: str = "draft_first"  # "draft_first" | "send_directly"


class OperationalConfigResponse(BaseModel):
    candidate_id: int
    search_config: SearchConfigPayload
    strict_skill_match_required: bool
    send_mode: str


def _get_owned_candidate(db: Session, admin: AdminUser, candidate_id: int) -> Candidate:
    candidate = db.query(Candidate).filter_by(id=candidate_id).one_or_none()
    if candidate is None or candidate.organization_id != admin.organization_id:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    return candidate


@router.get("/{candidate_id}/config", response_model=OperationalConfigResponse)
def get_config(candidate_id: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    candidate = _get_owned_candidate(db, admin, candidate_id)
    config = get_or_create_operational_config(db, candidate.id)
    db.commit()
    return OperationalConfigResponse(
        candidate_id=candidate.id,
        search_config=SearchConfigPayload(**(config.search_config_json or {})),
        strict_skill_match_required=config.strict_skill_match_required,
        send_mode=config.send_mode,
    )


@router.put("/{candidate_id}/config", response_model=OperationalConfigResponse)
def update_config(
    candidate_id: int,
    payload: OperationalConfigRequest,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    candidate = _get_owned_candidate(db, admin, candidate_id)

    if payload.send_mode not in ("draft_first", "send_directly"):
        raise HTTPException(status_code=422, detail="send_mode must be 'draft_first' or 'send_directly'")

    config = get_or_create_operational_config(db, candidate.id)
    config.search_config_json = payload.search_config.model_dump()
    config.strict_skill_match_required = payload.strict_skill_match_required
    config.send_mode = payload.send_mode
    db.commit()
    db.refresh(config)

    return OperationalConfigResponse(
        candidate_id=candidate.id,
        search_config=SearchConfigPayload(**config.search_config_json),
        strict_skill_match_required=config.strict_skill_match_required,
        send_mode=config.send_mode,
    )
