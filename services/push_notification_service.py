"""
Web Push -- the actual "send a browser notification" mechanism.
Standard Push API + VAPID, works across Chrome/Firefox/Edge on desktop
and Android without any native app store; iOS Safari requires the site
to be installed to the home screen first (PWA), which is what
frontend/public/manifest.json + the service worker enable.

This module only sends TO an already-registered subscription -- the
subscribing happens in the browser (frontend/public/sw.js +
frontend/src/services/push.js) and is stored via api/routers/push.py.
"""
from __future__ import annotations

import json
import os

from pywebpush import WebPushException, webpush
from sqlalchemy.orm import Session

from db.models import PushSubscription


def _vapid_config() -> dict:
    public_key = os.environ.get("VAPID_PUBLIC_KEY")
    private_pem = os.environ.get("VAPID_PRIVATE_KEY_PEM")
    subject = os.environ.get("VAPID_SUBJECT")
    missing = [
        name for name, val in [
            ("VAPID_PUBLIC_KEY", public_key), ("VAPID_PRIVATE_KEY_PEM", private_pem), ("VAPID_SUBJECT", subject),
        ] if not val
    ]
    if missing:
        raise RuntimeError(
            f"Missing VAPID config: {missing}. Run `python -m services.generate_vapid_keys` "
            f"once and put the output in your .env."
        )
    return {
        "public_key": public_key,
        "private_key_pem": private_pem.replace("\\n", "\n"),
        "subject": subject,
    }


def send_push_to_owner(
    session: Session, owner_type: str, owner_id: int, title: str, body: str, url: str | None = None
) -> bool:
    """Sends to every subscription this owner has registered (multiple
    devices/browsers). Returns True if at least one delivered
    successfully -- the caller (notification_service.py) uses this to
    decide whether an email fallback is still needed. Dead subscriptions
    (410 Gone -- the browser unsubscribed or the endpoint expired) are
    cleaned up automatically."""
    config = _vapid_config()
    subs = session.query(PushSubscription).filter_by(owner_type=owner_type, owner_id=owner_id).all()
    if not subs:
        return False

    payload = json.dumps({"title": title, "body": body, "url": url or "/"})
    delivered = False

    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh_key, "auth": sub.auth_key},
                },
                data=payload,
                vapid_private_key=config["private_key_pem"],
                vapid_claims={"sub": config["subject"]},
            )
            delivered = True
        except WebPushException as e:
            status_code = getattr(e.response, "status_code", None)
            if status_code == 410:  # Gone -- subscription is dead, remove it
                session.delete(sub)
            # Other failures (network blip, etc.) are not treated as
            # permanent -- the subscription stays, just this send failed.

    session.commit()
    return delivered
