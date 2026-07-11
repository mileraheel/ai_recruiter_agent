"""
Transactional email (invites, account notifications) -- sent via the
app's own SMTP account, NOT a candidate's connected Gmail (that's
services/gmail_client.py, only usable after a candidate exists and has
connected their own inbox). This is infrastructure the app owns.

The app's own SMTP account is a platform-wide, superuser-editable
setting (PlatformSettings.system_smtp_* -- see
api/routers/superuser.py's /api/superuser/system-email), not just an
.env value: a superuser can view and change it from the Configs
screen without touching the server. .env's SMTP_* vars remain a
fallback for whenever PlatformSettings hasn't been configured yet, so
existing deployments keep working either way.
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.mime.text import MIMEText

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _smtp_config(session: Session) -> dict:
    from services.crypto import decrypt_secret
    from services.platform_settings_service import get_or_create_platform_settings

    settings = get_or_create_platform_settings(session)
    if (
        settings.system_smtp_host
        and settings.system_smtp_port
        and settings.system_smtp_username
        and settings.system_smtp_encrypted_password
        and settings.system_smtp_from_email
    ):
        return {
            "host": settings.system_smtp_host,
            "port": settings.system_smtp_port,
            "username": settings.system_smtp_username,
            "password": decrypt_secret(settings.system_smtp_encrypted_password),
            "from_email": settings.system_smtp_from_email,
            "from_name": settings.system_smtp_from_name,
        }

    host = os.environ.get("SMTP_HOST")
    port = os.environ.get("SMTP_PORT")
    username = os.environ.get("SMTP_USERNAME")
    password = os.environ.get("SMTP_PASSWORD")
    from_email = os.environ.get("SMTP_FROM_EMAIL")
    # Optional -- purely cosmetic. Falls back to just the bare address
    # (e.g. "you@gmail.com") if unset, same behavior as before this
    # existed, so leaving it out never breaks sending.
    from_name = os.environ.get("SMTP_FROM_NAME")
    missing = [
        name
        for name, val in [
            ("SMTP_HOST", host), ("SMTP_PORT", port), ("SMTP_USERNAME", username),
            ("SMTP_PASSWORD", password), ("SMTP_FROM_EMAIL", from_email),
        ]
        if not val
    ]
    if missing:
        raise RuntimeError(
            f"No system email account configured: {missing} not set in .env, and "
            f"nothing set in the superuser Configs screen either. Configure it at "
            f"/superuser/dashboard (Configs tab), or set these in .env -- e.g. for a "
            f"Gmail account: SMTP_HOST=smtp.gmail.com, SMTP_PORT=587, "
            f"SMTP_USERNAME=<address>, SMTP_PASSWORD=<app password, not your real "
            f"password>, SMTP_FROM_EMAIL=<address>."
        )
    return {
        "host": host, "port": int(port), "username": username, "password": password,
        "from_email": from_email, "from_name": from_name,
    }


def send_email(session: Session, to_email: str, subject: str, body_text: str) -> None:
    config = _smtp_config(session)
    msg = MIMEText(body_text, "plain")
    msg["Subject"] = subject
    msg["From"] = (
        f'"{config["from_name"]}" <{config["from_email"]}>' if config["from_name"] else config["from_email"]
    )
    msg["To"] = to_email

    if config["port"] == 465:
        server = smtplib.SMTP_SSL(config["host"], config["port"])
    else:
        server = smtplib.SMTP(config["host"], config["port"])
    with server:
        if config["port"] != 465:
            server.starttls()
        server.login(config["username"], config["password"])
        # The envelope sender (SMTP MAIL FROM) stays the bare address --
        # only the To-be-displayed "From" header gets the friendly name.
        # Some providers reject a display-name-formatted envelope sender.
        server.sendmail(config["from_email"], [to_email], msg.as_string())


def send_invite_email(
    session: Session, to_email: str, otp: str, role: str, organization_name: str | None, expire_days: int
) -> None:
    role_labels = {"admin": "admin", "candidate": "candidate", "staff": "staff member"}
    role_label = role_labels.get(role, role)
    if role == "staff":
        subject = "You're invited to join the platform as staff"
        intro = "You've been invited to join the platform as a staff member."
    else:
        subject = f"You're invited to join {organization_name}"
        intro = f"You've been invited to join {organization_name} as a {role_label}."

    day_word = "day" if expire_days == 1 else "days"
    body = (
        f"{intro}\n\n"
        f"Your one-time code: {otp}\n"
        f"This code expires in {expire_days} {day_word} and can only be used once.\n\n"
        f"Open the app, choose 'I have an invite', and enter this email address "
        f"along with the code to set your password and get started."
    )
    send_email(session, to_email, subject, body)


def send_password_reset_email(session: Session, to_email: str, otp: str) -> None:
    """Used by every password-reset flow (admin, candidate, staff,
    superuser -- see api/routers/auth.py). Includes both a clickable
    link (pre-filling email+otp on the reset-password page) and the
    bare code as a fallback, since the link depends on FRONTEND_BASE_URL
    being reachable from wherever the recipient opens the email -- set
    it to the app's public tunnel/deployment URL, not localhost, once
    real emails need to go out.

    If SMTP isn't configured, logs the link instead of raising -- callers
    already treat "couldn't send" as a silent no-op (same
    non-account-confirming response either way), so this keeps that
    behavior while still making the link discoverable in logs/app.log
    for local testing without a real mail server."""
    from services.platform_settings_service import get_or_create_platform_settings

    expire_minutes = get_or_create_platform_settings(session).otp_expire_minutes
    base_url = os.environ.get("FRONTEND_BASE_URL", "http://localhost:5173")
    reset_link = f"{base_url}/reset-password?email={to_email}&otp={otp}"
    minute_word = "minute" if expire_minutes == 1 else "minutes"
    body = (
        f"Click the link below to set a new password:\n{reset_link}\n\n"
        f"Or enter this code manually: {otp}\n"
        f"This code expires in {expire_minutes} {minute_word}."
    )
    try:
        send_email(session, to_email, "Reset your password", body)
    except RuntimeError:
        logger.info(f"[dev] SMTP not configured -- password reset link for {to_email}: {reset_link}")


def send_trial_reminder_email(session: Session, to_email: str, expires_at, account_label: str | None = None) -> None:
    """expires_at: a date (not datetime) -- Organization.trial_expires_at
    or Subscription.current_period_end, both plain dates. Sent once per
    expiry by services/trial_service.py, which owns the dedup logic;
    this function just formats and sends -- it doesn't decide whether
    to send."""
    subject = "Your subscription is expiring soon"
    who = f" for {account_label}" if account_label else ""
    body = (
        f"This is a reminder that your subscription{who} expires on {expires_at.isoformat()}.\n\n"
        f"Please get in touch with your sales person to renew, or simply reply to this "
        f"email and we'll follow up."
    )
    send_email(session, to_email, subject, body)
