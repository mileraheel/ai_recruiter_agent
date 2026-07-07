"""
Transactional email (invites, account notifications) -- sent via the
app's own SMTP account, NOT a candidate's connected Gmail (that's
services/gmail_client.py, only usable after a candidate exists and has
connected their own inbox). This is infrastructure the app owns.

Works with any SMTP provider: a Gmail account + app password to start
(matches "I can create a gmail for our app initially"), a real
transactional provider (SendGrid/Postmark/SES's SMTP interface) later
-- same env vars either way, just different host/port/credentials.
"""
from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText


def _smtp_config() -> dict:
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
            f"Missing SMTP config: {missing}. Set these in your .env to send invite "
            f"emails -- e.g. for a Gmail account: SMTP_HOST=smtp.gmail.com, "
            f"SMTP_PORT=587, SMTP_USERNAME=<address>, SMTP_PASSWORD=<app password, "
            f"not your real password>, SMTP_FROM_EMAIL=<address>."
        )
    return {
        "host": host, "port": int(port), "username": username, "password": password,
        "from_email": from_email, "from_name": from_name,
    }


def send_email(to_email: str, subject: str, body_text: str) -> None:
    config = _smtp_config()
    msg = MIMEText(body_text, "plain")
    msg["Subject"] = subject
    msg["From"] = (
        f'"{config["from_name"]}" <{config["from_email"]}>' if config["from_name"] else config["from_email"]
    )
    msg["To"] = to_email

    with smtplib.SMTP(config["host"], config["port"]) as server:
        server.starttls()
        server.login(config["username"], config["password"])
        # The envelope sender (SMTP MAIL FROM) stays the bare address --
        # only the To-be-displayed "From" header gets the friendly name.
        # Some providers reject a display-name-formatted envelope sender.
        server.sendmail(config["from_email"], [to_email], msg.as_string())


def send_invite_email(to_email: str, otp: str, role: str, organization_name: str) -> None:
    role_label = "admin" if role == "admin" else "candidate"
    subject = f"You're invited to join {organization_name}"
    body = (
        f"You've been invited to join {organization_name} as a {role_label}.\n\n"
        f"Your one-time code: {otp}\n"
        f"This code expires in 30 minutes and can only be used once.\n\n"
        f"Open the app, choose 'I have an invite', and enter this email address "
        f"along with the code to set your password and get started."
    )
    send_email(to_email, subject, body)


def send_trial_reminder_email(to_email: str, expires_at, account_label: str | None = None) -> None:
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
    send_email(to_email, subject, body)
