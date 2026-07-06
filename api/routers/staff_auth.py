from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from api.auth import authenticate_staff, create_access_token
from api.deps import get_db
from api.schemas import TokenResponse
from services.rate_limit import check_not_locked, record_failure, record_success

router = APIRouter(prefix="/api/staff-auth", tags=["staff-auth"])


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    account_key = f"staff:{form_data.username.strip().lower()}"
    check_not_locked(db, account_key)

    user = authenticate_staff(db, form_data.username, form_data.password)
    if not user:
        record_failure(db, account_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    record_success(db, account_key)
    token = create_access_token(user.username, role="staff")
    return TokenResponse(access_token=token)
