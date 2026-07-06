"""
Candidate-facing Gmail connection endpoints.

/connect-url and /status and DELETE are behind normal candidate bearer
auth. The OAuth callback (/api/oauth/google/callback) is NOT -- Google's
redirect is a plain browser navigation with no Authorization header, so
identity is instead carried in the signed `state` param (a short-lived
JWT-like token, role='oauth_state', embedding candidate_id) generated
by /connect-url and verified on callback. This prevents both CSRF
(state is unguessable and single-purpose) and account-linking attacks
(an attacker can't complete their own Google consent and have it
attached to someone else's candidate_id, since state is bound to the
candidate who initiated the flow).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from jose import JWTError
from sqlalchemy.orm import Session

from api.auth import create_access_token, decode_access_token
from api.deps import get_current_candidate, get_db
from db.models import Candidate, EmailAccountCredential
from services.crypto import encrypt_secret
from services.google_oauth import build_consent_url, exchange_code_for_tokens, revoke_token

router = APIRouter(tags=["email-account"])

STATE_EXPIRE_MINUTES = 10


@router.get("/api/me/email-account/connect-url", dependencies=[Depends(get_current_candidate)])
def get_connect_url(candidate: Candidate = Depends(get_current_candidate)):
    state = create_access_token(
        subject=f"oauth_state:{candidate.id}",
        role="oauth_state",
        extra_claims={"candidate_id": candidate.id},
        expires_minutes=STATE_EXPIRE_MINUTES,
    )
    try:
        url = build_consent_url(state)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"consent_url": url}


@router.get("/api/oauth/google/callback")
def google_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    try:
        payload = decode_access_token(state)
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state -- please reconnect.")
    if payload.get("role") != "oauth_state":
        raise HTTPException(status_code=400, detail="Invalid OAuth state.")

    candidate_id = payload.get("candidate_id")
    candidate = db.query(Candidate).filter_by(id=candidate_id).one_or_none()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found for this OAuth state.")

    try:
        tokens = exchange_code_for_tokens(code)
    except Exception as e:  # noqa: BLE001 -- surface as a clear connect failure, not a 500
        raise HTTPException(status_code=502, detail=f"Google token exchange failed: {e}")

    if not tokens.refresh_token:
        raise HTTPException(
            status_code=422,
            detail=(
                "Google did not return a refresh token -- this usually means the account "
                "already has a prior grant for this app. Revoke access at "
                "https://myaccount.google.com/permissions and try connecting again."
            ),
        )

    existing = (
        db.query(EmailAccountCredential)
        .filter_by(candidate_id=candidate.id, provider="gmail")
        .one_or_none()
    )
    if existing is None:
        existing = EmailAccountCredential(candidate_id=candidate.id, provider="gmail")
        db.add(existing)

    existing.account_email = tokens.account_email
    existing.secret_type = "oauth_refresh_token"
    existing.encrypted_secret = encrypt_secret(tokens.refresh_token)
    existing.scopes_granted = tokens.granted_scopes
    existing.status = "connected"
    existing.last_error = None
    db.commit()

    # Redirect back into the SPA rather than returning raw JSON -- this
    # request is a top-level browser navigation from Google, not an API
    # call the frontend JS initiated.
    return RedirectResponse(url="/candidate/profile?email_connected=1")


@router.get("/api/me/email-account", dependencies=[Depends(get_current_candidate)])
def email_account_status(candidate: Candidate = Depends(get_current_candidate), db: Session = Depends(get_db)):
    row = db.query(EmailAccountCredential).filter_by(candidate_id=candidate.id).one_or_none()
    if row is None:
        return {"connected": False}
    return {
        "connected": row.status == "connected",
        "provider": row.provider,
        "account_email": row.account_email,
        "scopes_granted": row.scopes_granted,
        "status": row.status,
        "connected_at": row.connected_at,
    }


@router.delete("/api/me/email-account", dependencies=[Depends(get_current_candidate)])
def disconnect_email_account(candidate: Candidate = Depends(get_current_candidate), db: Session = Depends(get_db)):
    row = db.query(EmailAccountCredential).filter_by(candidate_id=candidate.id).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="No connected email account.")

    from services.crypto import decrypt_secret

    try:
        secret = decrypt_secret(row.encrypted_secret)
        revoke_token(secret)
    except Exception:
        pass  # best-effort revoke at Google; the local row is deleted regardless

    db.delete(row)
    db.commit()
    return {"disconnected": True}
