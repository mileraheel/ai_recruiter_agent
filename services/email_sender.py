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

from config.app_info import APP_NAME

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
    """organization_name is None for a staff invite (not org-scoped) and
    should ALSO be passed as None by the caller for a standalone
    'individual' account -- that org's internal DB name is auto-derived
    from the invitee's own email address for uniqueness (see
    api/routers/superuser.py / staff.py), and showing someone their own
    email address back to them as if it were a company name reads as a
    bug, not a feature."""
    role_labels = {"admin": "an admin", "candidate": "a candidate", "staff": "a staff member"}
    role_label = role_labels.get(role, role)

    if organization_name:
        subject = f"{APP_NAME} invites you to join {organization_name}"
        intro = f"You've been invited to join {organization_name} on {APP_NAME} as {role_label}."
    else:
        subject = f"{APP_NAME} invites you to get started"
        intro = f"You've been invited to set up your account on {APP_NAME}."

    base_url = os.environ.get("FRONTEND_BASE_URL", "http://localhost:5173")
    accept_link = f"{base_url}/accept-invite?email={to_email}&otp={otp}"
    day_word = "day" if expire_days == 1 else "days"
    body = (
        f"{intro}\n\n"
        f"Click the link below to set your password and get started:\n{accept_link}\n\n"
        f"Or go to the {APP_NAME} sign-in page, click \"I have an invite,\" and enter this "
        f"email address along with the code below:\n"
        f"Your one-time verification code: {otp}\n"
        f"This code is valid for {expire_days} {day_word} and can only be used once.\n\n"
        f"If you weren't expecting this invitation, you can safely ignore this email."
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
        f"We received a request to reset your {APP_NAME} password.\n\n"
        f"Click the link below to choose a new one:\n{reset_link}\n\n"
        f"Or enter this code manually: {otp}\n"
        f"This code expires in {expire_minutes} {minute_word}.\n\n"
        f"If you didn't request this, you can safely ignore this email -- your password won't be changed."
    )
    try:
        send_email(session, to_email, f"Reset your {APP_NAME} password", body)
    except RuntimeError:
        logger.info(f"[dev] SMTP not configured -- password reset link for {to_email}: {reset_link}")


def send_trial_reminder_email(session: Session, to_email: str, expires_at, account_label: str | None = None) -> None:
    """expires_at: a date (not datetime) -- Organization.trial_expires_at
    or Subscription.current_period_end, both plain dates. Sent once per
    expiry by services/trial_service.py, which owns the dedup logic;
    this function just formats and sends -- it doesn't decide whether
    to send."""
    subject = f"Your {APP_NAME} subscription is expiring soon"
    who = f" for {account_label}" if account_label else ""
    body = (
        f"This is a friendly reminder that your {APP_NAME} subscription{who} is set to expire "
        f"on {expires_at.isoformat()}.\n\n"
        f"To keep things running without interruption, get in touch with your sales person to "
        f"renew -- or simply reply to this email and we'll follow up."
    )
    send_email(session, to_email, subject, body)
