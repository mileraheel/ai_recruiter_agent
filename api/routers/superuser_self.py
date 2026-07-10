"""
Superuser self-service: view/edit their own profile and password.
Mirrors api/routers/admin_self.py exactly -- see that file's docstring
for why AdminMeResponse/AdminProfileUpdateRequest are reused here rather
than duplicated (SuperUser has the same id/username/full_name/email
shape). username is never accepted -- it's the immutable account
identifier.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.auth import hash_password, verify_password
from api.deps import get_current_superuser, get_db
from api.schemas import AdminMeResponse, AdminProfileUpdateRequest, ChangePasswordRequest
from db.models import SuperUser

router = APIRouter(prefix="/api/superuser/me", tags=["superuser-self"], dependencies=[Depends(get_current_superuser)])


@router.get("", response_model=AdminMeResponse)
def get_me(superuser: SuperUser = Depends(get_current_superuser)):
    return AdminMeResponse(id=superuser.id, username=superuser.username, full_name=superuser.full_name, email=superuser.email)


@router.put("", response_model=AdminMeResponse)
def update_profile(
    payload: AdminProfileUpdateRequest,
    superuser: SuperUser = Depends(get_current_superuser),
    db: Session = Depends(get_db),
):
    if payload.full_name is not None:
        superuser.full_name = payload.full_name
    if payload.email is not None:
        superuser.email = payload.email
    db.commit()
    db.refresh(superuser)
    return AdminMeResponse(id=superuser.id, username=superuser.username, full_name=superuser.full_name, email=superuser.email)


@router.put("/password")
def change_password(
    payload: ChangePasswordRequest,
    superuser: SuperUser = Depends(get_current_superuser),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, superuser.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")
    if len(payload.new_password) < 10:
        raise HTTPException(status_code=422, detail="Password must be at least 10 characters.")
    superuser.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"message": "Password updated."}
