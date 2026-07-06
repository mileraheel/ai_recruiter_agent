"""
Google OAuth2 for candidate-connected Gmail accounts.

Scopes requested cover not just today's need (verifying a connection
exists) but the agreed next phase: reading incoming recruiter emails,
sending replies/follow-ups, and managing interview calendar events.
Requesting them now means the consent screen the candidate sees is
accurate about what the app will eventually do -- not a narrower ask
now followed by a second, more alarming consent screen later.

access_type=offline + prompt=consent guarantees Google issues a
refresh_token (not just a short-lived access_token) -- without both of
those params Google often omits it, especially on a second connection
attempt from the same account.

No Google client library dependency -- plain HTTP calls via httpx to
Google's documented OAuth2 endpoints. Requires GOOGLE_OAUTH_CLIENT_ID,
GOOGLE_OAUTH_CLIENT_SECRET, and GOOGLE_OAUTH_REDIRECT_URI to be set
(from a Google Cloud OAuth 2.0 Client ID, with Gmail API and Calendar
API enabled for the project) -- there is no default/test credential
here; this module cannot be exercised end-to-end without real Google
Cloud credentials, which is a setup step outside this codebase.
"""
from __future__ import annotations

import os
import urllib.parse
from dataclasses import dataclass

import httpx

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
REVOKE_ENDPOINT = "https://oauth2.googleapis.com/revoke"
USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v3/userinfo"

# Scoped for the agreed roadmap: read inbox (detect recruiter emails,
# job-related threads), send (replies, follow-ups, initial outreach),
# and calendar (store/confirm interview events) -- not just today's
# "verify a connection exists" need.
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.events",
    "openid",
    "email",
]


def _client_config() -> tuple[str, str, str]:
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    redirect_uri = os.environ.get("GOOGLE_OAUTH_REDIRECT_URI")
    missing = [
        name
        for name, val in [
            ("GOOGLE_OAUTH_CLIENT_ID", client_id),
            ("GOOGLE_OAUTH_CLIENT_SECRET", client_secret),
            ("GOOGLE_OAUTH_REDIRECT_URI", redirect_uri),
        ]
        if not val
    ]
    if missing:
        raise RuntimeError(
            f"Missing Google OAuth config: {missing}. Create an OAuth 2.0 Client ID "
            f"in Google Cloud Console (with Gmail API + Calendar API enabled for the "
            f"project) and set these in your .env."
        )
    return client_id, client_secret, redirect_uri


def build_consent_url(state: str) -> str:
    client_id, _, redirect_uri = _client_config()
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GMAIL_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"


@dataclass
class ExchangedTokens:
    refresh_token: str | None
    access_token: str
    account_email: str
    granted_scopes: list[str]


def exchange_code_for_tokens(code: str) -> ExchangedTokens:
    """Trades an authorization code (from the OAuth redirect) for
    tokens. refresh_token may be None if Google didn't issue one (e.g.
    a repeat connection without revoking the prior grant first) --
    callers must handle that explicitly rather than storing None as if
    it were a valid credential."""
    client_id, client_secret, redirect_uri = _client_config()

    with httpx.Client(timeout=15.0) as client:
        token_resp = client.post(
            TOKEN_ENDPOINT,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()

        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token")
        granted_scopes = token_data.get("scope", "").split()

        userinfo_resp = client.get(
            USERINFO_ENDPOINT, headers={"Authorization": f"Bearer {access_token}"}
        )
        userinfo_resp.raise_for_status()
        account_email = userinfo_resp.json().get("email", "")

    return ExchangedTokens(
        refresh_token=refresh_token,
        access_token=access_token,
        account_email=account_email,
        granted_scopes=granted_scopes,
    )


def refresh_access_token(refresh_token: str) -> str:
    """Used by the (future) email-monitoring/sending service to get a
    fresh short-lived access token from the stored refresh token --
    refresh tokens themselves are long-lived and reused, never rotated
    per-call."""
    client_id, client_secret, _ = _client_config()
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(
            TOKEN_ENDPOINT,
            data={
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


def revoke_token(token: str) -> None:
    """Revokes a refresh (or access) token at Google -- called on
    disconnect so the candidate's Google account no longer shows this
    app as having access, not just a local DB row deletion."""
    with httpx.Client(timeout=15.0) as client:
        client.post(REVOKE_ENDPOINT, data={"token": token})
