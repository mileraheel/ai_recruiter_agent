"""
Admin self-service: view/edit their own profile and password.

Mirrors api/routers/candidate_self.py's shape. Unlike candidate profile
edits, there's no approval queue here -- an admin editing their own
email/full_name applies immediately, since there's no one else who'd
review it (candidates' edits are reviewed by their org's admin; an
admin has no analogous reviewer for their own identity fields).
username is never accepted by either endpoint below -- it's the
immutable account identifier.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.auth import hash_password, verify_password
from api.deps import get_current_admin, get_db
from api.schemas import AdminMeResponse, AdminProfileUpdateRequest, ChangePasswordRequest
from db.models import AdminUser

router = APIRouter(prefix="/api/admin/me", tags=["admin-self"], dependencies=[Depends(get_current_admin)])


@router.get("", response_model=AdminMeResponse)
def get_me(admin: AdminUser = Depends(get_current_admin)):
    return AdminMeResponse(id=admin.id, username=admin.username, full_name=admin.full_name, email=admin.email)


@router.put("", response_model=AdminMeResponse)
def update_profile(
    payload: AdminProfileUpdateRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if payload.full_name is not None:
        admin.full_name = payload.full_name
    if payload.email is not None:
        admin.email = payload.email
    db.commit()
    db.refresh(admin)
    return AdminMeResponse(id=admin.id, username=admin.username, full_name=admin.full_name, email=admin.email)


@router.put("/password")
def change_password(
    payload: ChangePasswordRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")
    if len(payload.new_password) < 10:
        raise HTTPException(status_code=422, detail="Password must be at least 10 characters.")
    admin.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"message": "Password updated."}
