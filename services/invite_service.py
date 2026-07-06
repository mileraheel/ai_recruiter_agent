"""
Invite creation -- shared by two call sites: staff inviting a new
admin (and creating their organization), and an admin inviting a
candidate into their own organization. Both produce the same kind of
Invite row; only invited_by_type/role/organization_id differ.

The OTP itself is only ever handed back to the CALLER (to email), never
persisted anywhere in readable form -- otp_hash is bcrypt, same as a
password.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from api.auth import generate_otp, hash_otp
from db.models import Invite

OTP_EXPIRE_MINUTES = 30


def create_invite(
    session: Session,
    email: str,
    role: str,
    organization_id: int,
    invited_by_type: str,
    invited_by_id: int,
) -> tuple[Invite, str]:
    """Returns (invite_row, plaintext_otp) -- the plaintext OTP exists
    only in this return value and the email sent to the invitee; it is
    never written to the DB or logged."""
    otp = generate_otp()
    invite = Invite(
        email=email.strip().lower(),
        role=role,
        organization_id=organization_id,
        invited_by_type=invited_by_type,
        invited_by_id=invited_by_id,
        otp_hash=hash_otp(otp),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES),
    )
    session.add(invite)
    session.commit()
    session.refresh(invite)
    return invite, otp
