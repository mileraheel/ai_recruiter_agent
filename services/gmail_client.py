"""
The actual "send an email" mechanism -- deliberately small. Refresh the
stored token, build one MIME message with the resume attached, call one
Gmail API endpoint. Everything else (composing the text, deciding
whether a job/candidate should be applied to, approval gating) already
lives elsewhere; this module's only job is the mechanical last step.

Two Gmail API calls, both simple:
  - drafts.create: writes a draft into the CANDIDATE's own Gmail --
    nothing is sent to the recruiter. This is what send_mode=draft_first
    produces, and it's inherently low-risk (the candidate still has to
    open Gmail and hit send themselves).
  - messages.send: actually delivers to the recruiter. This is the one
    real "send a message on the user's behalf" action, and the calling
    endpoint (api/routers/applications.py) only reaches this after an
    explicit, separate confirm step -- never automatically.
"""
from __future__ import annotations

import base64
import re
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

from services.google_oauth import refresh_access_token

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


def build_mime_message(
    to_email: str,
    from_email: str,
    subject: str,
    body_text: str,
    attachment_bytes: bytes | None = None,
    attachment_filename: str | None = None,
) -> str:
    """Returns the base64url-encoded raw message Gmail's API expects."""
    msg = MIMEMultipart()
    msg["To"] = to_email
    msg["From"] = from_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body_text, "plain"))

    if attachment_bytes is not None:
        part = MIMEApplication(
            attachment_bytes,
            _subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        part.add_header("Content-Disposition", "attachment", filename=attachment_filename or "resume.docx")
        msg.attach(part)

    raw_bytes = msg.as_bytes()
    return base64.urlsafe_b64encode(raw_bytes).decode("utf-8")


def _access_token_from_refresh(encrypted_refresh_token_plain: str) -> str:
    """Takes an already-decrypted refresh token (caller decrypts via
    services/crypto.py right before this call, never earlier) and
    returns a fresh short-lived access token."""
    return refresh_access_token(encrypted_refresh_token_plain)


def create_draft(refresh_token: str, raw_mime: str) -> str:
    """Writes a draft into the candidate's own Gmail. Returns the draft id."""
    access_token = _access_token_from_refresh(refresh_token)
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(
            f"{GMAIL_API_BASE}/drafts",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"message": {"raw": raw_mime}},
        )
        resp.raise_for_status()
        return resp.json()["id"]


def list_recent_messages(refresh_token: str, max_results: int = 20, query: str = "in:inbox newer_than:7d") -> list[str]:
    """Returns message ids -- newest first. Default query scopes to the
    inbox, last 7 days, so a normal polling cycle isn't re-scanning a
    candidate's entire mail history every run."""
    access_token = _access_token_from_refresh(refresh_token)
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(
            f"{GMAIL_API_BASE}/messages",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"maxResults": max_results, "q": query},
        )
        resp.raise_for_status()
        return [m["id"] for m in resp.json().get("messages", [])]


def get_message(refresh_token: str, message_id: str) -> dict:
    """Returns the raw Gmail message resource (format=full) -- headers
    (From, Subject, Date, Message-Id, In-Reply-To/References for
    threading) plus the body payload."""
    access_token = _access_token_from_refresh(refresh_token)
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(
            f"{GMAIL_API_BASE}/messages/{message_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"format": "full"},
        )
        resp.raise_for_status()
        return resp.json()


def extract_plain_text_body(message: dict) -> str:
    """Gmail messages are a MIME tree (often multipart/alternative with
    text/plain and text/html siblings) -- walks it depth-first and
    returns the first text/plain part found, falling back to a stripped
    text/html part if no plain-text part exists (some clients only send
    HTML)."""
    def _walk(part: dict) -> str | None:
        mime_type = part.get("mimeType", "")
        body_data = part.get("body", {}).get("data")
        if mime_type == "text/plain" and body_data:
            return base64.urlsafe_b64decode(body_data + "==").decode("utf-8", errors="replace")
        for sub in part.get("parts", []) or []:
            found = _walk(sub)
            if found:
                return found
        if mime_type == "text/html" and body_data:
            html = base64.urlsafe_b64decode(body_data + "==").decode("utf-8", errors="replace")
            return re.sub(r"<[^>]+>", " ", html)
        return None

    payload = message.get("payload", {})
    return _walk(payload) or ""


def get_message_headers(message: dict) -> dict[str, str]:
    headers = {}
    for h in message.get("payload", {}).get("headers", []):
        headers[h["name"].lower()] = h["value"]
    return headers
    """Writes a draft into the candidate's own Gmail. Returns the draft id."""
    access_token = _access_token_from_refresh(refresh_token)
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(
            f"{GMAIL_API_BASE}/drafts",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"message": {"raw": raw_mime}},
        )
        resp.raise_for_status()
        return resp.json()["id"]


def send_message(refresh_token: str, raw_mime: str) -> str:
    """Actually delivers the email. Returns the sent message id. Callers
    must only reach this after an explicit human confirm step -- see
    api/routers/applications.py's two-step prepare/send design."""
    access_token = _access_token_from_refresh(refresh_token)
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(
            f"{GMAIL_API_BASE}/messages/send",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"raw": raw_mime},
        )
        resp.raise_for_status()
        return resp.json()["id"]
