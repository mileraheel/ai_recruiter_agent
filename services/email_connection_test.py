"""
Verifies a manually-entered SMTP/IMAP credential actually works BEFORE
it's saved -- sends a real test email to the account's own address via
SMTP, then polls that same account's inbox via IMAP for its arrival.
Both directions have to succeed before api/routers/email_account.py's
connect_smtp saves anything to EmailAccountCredential; a typo'd host,
port, or password would otherwise save as "connected" and only surface
as a failure much later, when the app silently can't send or read on
the user's behalf.

Not used for the Gmail OAuth path -- a successful token exchange there
already proves the account is reachable, and Gmail's send/read paths
go through services/gmail_client.py's API client, not raw SMTP/IMAP.
"""
from __future__ import annotations

import imaplib
import smtplib
import time
import uuid
from email.mime.text import MIMEText

CONNECT_TIMEOUT_SECONDS = 15
IMAP_POLL_TIMEOUT_SECONDS = 25
IMAP_POLL_INTERVAL_SECONDS = 2.5


def _send_test_email(
    smtp_host: str, smtp_port: int, username: str, password: str, account_email: str, marker: str
) -> str:
    subject = f"RolePace connection test {marker}"
    msg = MIMEText(
        "This is an automated test from RolePace confirming your email connection "
        "details work end-to-end (sending and receiving). You can ignore or delete "
        "this message."
    )
    msg["Subject"] = subject
    msg["From"] = account_email
    msg["To"] = account_email

    try:
        # Port 465 is implicit TLS from the first byte (SMTP_SSL); every
        # other common port (587, 25, provider-specific) negotiates TLS
        # via STARTTLS after a plaintext handshake -- same two cases the
        # Zoho-style reference UI's IMAP/SMTP tables always show.
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=CONNECT_TIMEOUT_SECONDS)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=CONNECT_TIMEOUT_SECONDS)
        with server:
            if smtp_port != 465:
                server.starttls()
            server.login(username, password)
            server.sendmail(account_email, [account_email], msg.as_string())
    except Exception as e:  # noqa: BLE001 -- surface as a clear, user-facing reason
        raise ValueError(f"Could not send a test email via SMTP ({smtp_host}:{smtp_port}): {e}") from e

    return subject


def _wait_for_test_email(imap_host: str, imap_port: int, username: str, password: str, subject: str) -> None:
    try:
        imap = imaplib.IMAP4_SSL(imap_host, imap_port, timeout=CONNECT_TIMEOUT_SECONDS)
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"Could not connect to the IMAP server ({imap_host}:{imap_port}): {e}") from e

    try:
        try:
            imap.login(username, password)
        except Exception as e:  # noqa: BLE001
            raise ValueError(f"IMAP login failed for {username}: {e}") from e

        deadline = time.monotonic() + IMAP_POLL_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            imap.select("INBOX")
            status, data = imap.search(None, "SUBJECT", f'"{subject}"')
            if status == "OK" and data and data[0]:
                return
            time.sleep(IMAP_POLL_INTERVAL_SECONDS)

        raise ValueError(
            "The test email sent successfully, but never appeared in the inbox via IMAP "
            f"within {IMAP_POLL_TIMEOUT_SECONDS} seconds. Double-check the IMAP host/port, "
            "and that this is the same inbox the SMTP details just sent to."
        )
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def verify_smtp_imap_roundtrip(
    smtp_host: str,
    smtp_port: int,
    imap_host: str,
    imap_port: int,
    username: str,
    password: str,
    account_email: str,
) -> None:
    """Raises ValueError with a user-facing reason on any failure. Returns
    nothing on success -- caller only needs to know it didn't raise."""
    marker = uuid.uuid4().hex[:8]
    subject = _send_test_email(smtp_host, smtp_port, username, password, account_email, marker)
    _wait_for_test_email(imap_host, imap_port, username, password, subject)
