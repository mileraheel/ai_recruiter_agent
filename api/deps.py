from __future__ import annotations

from typing import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from api.auth import decode_access_token
from db.models import AdminUser, Candidate, Staff, SuperUser
from db.session import get_session_factory
from services.storage import Storage, get_storage

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_db() -> Generator[Session, None, None]:
    SessionFactory = get_session_factory()
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()


def _decode_or_401(token: str | None) -> dict:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_error
    try:
        return decode_access_token(token)
    except JWTError:
        raise credentials_error


def get_current_admin(
    token: str | None = Depends(_oauth2_scheme),
    db: Session = Depends(get_db),
) -> AdminUser:
    payload = _decode_or_401(token)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    user = db.query(AdminUser).filter_by(username=payload["sub"]).one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
    return user


def get_current_candidate(
    token: str | None = Depends(_oauth2_scheme),
    db: Session = Depends(get_db),
) -> Candidate:
    """Resolves the candidate for candidate self-service endpoints.

    Two valid paths:
      - role='candidate': the normal case, candidate_id from the token.
      - role='admin' with a 'linked_candidate_id' claim: an INDIVIDUAL
        account (Organization.account_type='individual') -- the same
        person is both admin and candidate, one login, acting on their
        own linked Candidate row. The AdminUser.linked_candidate_id
        column is re-checked here (not just trusting the token claim)
        so a stale/forged claim can't point at someone else's candidate
        row after an admin's linkage changes."""
    payload = _decode_or_401(token)
    role = payload.get("role")

    if role == "candidate":
        candidate_id = payload.get("candidate_id")
        candidate = db.query(Candidate).filter_by(id=candidate_id).one_or_none()
        if candidate is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
        return candidate

    if role == "admin" and payload.get("linked_candidate_id"):
        admin = db.query(AdminUser).filter_by(username=payload["sub"]).one_or_none()
        if admin is None or admin.linked_candidate_id != payload.get("linked_candidate_id"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
        candidate = db.query(Candidate).filter_by(id=admin.linked_candidate_id).one_or_none()
        if candidate is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
        return candidate

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Candidate access required")


def get_current_superuser(
    token: str | None = Depends(_oauth2_scheme),
    db: Session = Depends(get_db),
) -> SuperUser:
    payload = _decode_or_401(token)
    if payload.get("role") != "superuser":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser access required")

    user = db.query(SuperUser).filter_by(username=payload["sub"]).one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
    return user


def get_current_staff(
    token: str | None = Depends(_oauth2_scheme),
    db: Session = Depends(get_db),
) -> Staff:
    payload = _decode_or_401(token)
    if payload.get("role") != "staff":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff access required")

    user = db.query(Staff).filter_by(username=payload["sub"], is_active=True).one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
    return user


def get_app_storage() -> Storage:
    return get_storage()
