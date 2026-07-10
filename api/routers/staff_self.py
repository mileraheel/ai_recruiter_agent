"""
Staff self-service: view/edit their own profile and password. Mirrors
api/routers/admin_self.py exactly -- Staff and AdminUser have the same
id/username/full_name/email shape, so the same AdminMeResponse/
AdminProfileUpdateRequest schemas are reused rather than duplicated.
username is never accepted -- it's the immutable account identifier.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.auth import hash_password, verify_password
from api.deps import get_current_staff, get_db
from api.schemas import AdminMeResponse, AdminProfileUpdateRequest, ChangePasswordRequest
from db.models import Staff

router = APIRouter(prefix="/api/staff/me", tags=["staff-self"], dependencies=[Depends(get_current_staff)])


@router.get("", response_model=AdminMeResponse)
def get_me(staff: Staff = Depends(get_current_staff)):
    return AdminMeResponse(id=staff.id, username=staff.username, full_name=staff.full_name, email=staff.email)


@router.put("", response_model=AdminMeResponse)
def update_profile(
    payload: AdminProfileUpdateRequest,
    staff: Staff = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    if payload.full_name is not None:
        staff.full_name = payload.full_name
    if payload.email is not None:
        staff.email = payload.email
    db.commit()
    db.refresh(staff)
    return AdminMeResponse(id=staff.id, username=staff.username, full_name=staff.full_name, email=staff.email)


@router.put("/password")
def change_password(
    payload: ChangePasswordRequest,
    staff: Staff = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, staff.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")
    if len(payload.new_password) < 10:
        raise HTTPException(status_code=422, detail="Password must be at least 10 characters.")
    staff.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"message": "Password updated."}
