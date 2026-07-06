"""
Unified notification dispatch: try push first, fall back to email only
if push wasn't delivered. This is the single function every event in
the app should call rather than deciding push-vs-email itself.
"""
from __future__ import annotations

from sqlalchemy.orm import Session


def notify(
    session: Session,
    owner_type: str,
    owner_id: int,
    title: str,
    body: str,
    email_address: str | None,
    url: str | None = None,
    organization_id: int | None = None,
) -> str:
    """Returns 'push' | 'email' | 'none' -- which channel actually
    delivered (or attempted), for logging/testing. Push failures
    (including "VAPID not configured yet") are swallowed and treated as
    "push unavailable, fall back to email" rather than raised -- a
    misconfigured push setup should never block an important
    notification from reaching someone by email instead.

    organization_id, if provided, gates whether email fallback is even
    considered: Organization.email_notifications_enabled=False means
    push/in-app only, full stop, even if push failed -- this org has
    explicitly opted out of email as a channel. Without an
    organization_id (e.g. platform-level notifications with no org
    context), email fallback is allowed by default."""
    from services.push_notification_service import send_push_to_owner

    try:
        delivered = send_push_to_owner(session, owner_type, owner_id, title, body, url)
    except RuntimeError:
        delivered = False  # VAPID not configured -- fall back silently

    if delivered:
        return "push"

    email_allowed = True
    if organization_id is not None:
        from db.models import Organization

        org = session.query(Organization).filter_by(id=organization_id).one_or_none()
        if org is not None:
            email_allowed = org.email_notifications_enabled

    if email_allowed and email_address:
        from services.email_sender import send_email

        try:
            send_email(email_address, title, body)
            return "email"
        except RuntimeError:
            pass  # SMTP not configured either -- nothing more we can do

    return "none"
