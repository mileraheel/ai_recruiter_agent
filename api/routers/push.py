"""
Push subscription management -- works for both admins and candidates,
since either can enable browser notifications.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.deps import get_current_admin, get_current_candidate, get_db
from db.models import AdminUser, Candidate, PushSubscription

router = APIRouter(prefix="/api/push", tags=["push"])


@router.get("/vapid-public-key")
def get_vapid_public_key():
    key = os.environ.get("VAPID_PUBLIC_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="Push notifications are not configured on this server yet.")
    return {"public_key": key}


class SubscriptionPayload(BaseModel):
    endpoint: str
    p256dh: str
    auth: str


def _upsert(session: Session, owner_type: str, owner_id: int, payload: SubscriptionPayload) -> None:
    existing = session.query(PushSubscription).filter_by(endpoint=payload.endpoint).one_or_none()
    if existing is None:
        existing = PushSubscription(owner_type=owner_type, owner_id=owner_id, endpoint=payload.endpoint)
        session.add(existing)
    existing.owner_type = owner_type
    existing.owner_id = owner_id
    existing.p256dh_key = payload.p256dh
    existing.auth_key = payload.auth
    session.commit()


@router.post("/subscribe/admin")
def subscribe_admin(
    payload: SubscriptionPayload, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)
):
    _upsert(db, "admin", admin.id, payload)
    return {"subscribed": True}


@router.post("/subscribe/candidate")
def subscribe_candidate(
    payload: SubscriptionPayload, db: Session = Depends(get_db), candidate: Candidate = Depends(get_current_candidate)
):
    _upsert(db, "candidate", candidate.id, payload)
    return {"subscribed": True}


class UnsubscribeRequest(BaseModel):
    endpoint: str


@router.post("/unsubscribe")
def unsubscribe(payload: UnsubscribeRequest, db: Session = Depends(get_db)):
    """No auth dependency required -- unsubscribing needs only the
    endpoint URL itself (which is effectively a capability token the
    browser controls), so a logged-out state (e.g. token just expired)
    doesn't block a browser from cleaning up its own subscription."""
    sub = db.query(PushSubscription).filter_by(endpoint=payload.endpoint).one_or_none()
    if sub:
        db.delete(sub)
        db.commit()
    return {"unsubscribed": True}
