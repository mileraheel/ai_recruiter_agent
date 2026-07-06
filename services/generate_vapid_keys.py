"""
One-time setup: generates a VAPID keypair for Web Push notifications.
Run once, put both values in your .env, never regenerate afterward
(regenerating invalidates every existing browser subscription --
everyone would need to re-subscribe).

Usage:
    python -m services.generate_vapid_keys
"""
from __future__ import annotations

import base64

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid02


def main() -> None:
    v = Vapid02()
    v.generate_keys()

    private_pem = v.private_pem().decode()
    raw_public = v.public_key.public_bytes(
        encoding=Encoding.X962, format=PublicFormat.UncompressedPoint
    )
    public_b64url = base64.urlsafe_b64encode(raw_public).decode().rstrip("=")

    print("Add these to your .env:\n")
    print(f"VAPID_PUBLIC_KEY={public_b64url}")
    print("VAPID_PRIVATE_KEY_PEM=" + private_pem.replace("\n", "\\n"))
    print('VAPID_SUBJECT=mailto:you@example.com  # required by the Push protocol, contact for push-service abuse reports')


if __name__ == "__main__":
    main()
