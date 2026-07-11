"""
Invite creation -- shared by three call sites: staff inviting a new
admin (and creating their organization), an admin inviting a candidate
into their own organization, and a superuser inviting a new staff
member (or onboarding an organization/admin directly). All produce the
same kind of Invite row; only invited_by_type/role/organization_id
differ, and organization_id is None for a staff invite (staff aren't
scoped to any one organization).

The OTP itself is only ever handed back to the CALLER (to email), never
persisted anywhere in readable form -- otp_hash is bcrypt, same as a
password.

Expiry is a platform-wide, superuser-configurable number of DAYS (see
services/platform_settings_service.py), not a hardcoded constant --
invites commonly need to survive over a weekend before someone gets
around to checking their email, unlike a password-reset OTP (see
services/password_reset.py), which is deliberately short-lived since
it's issued at the moment someone is actively trying to log in.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from api.auth import generate_otp, hash_otp
from db.models import Invite
from services.platform_settings_service import get_or_create_platform_settings


def create_invite(
    session: Session,
    email: str,
    role: str,
    organization_id: int | None,
    invited_by_type: str,
    invited_by_id: int,
) -> tuple[Invite, str]:
    """Returns (invite_row, plaintext_otp) -- the plaintext OTP exists
    only in this return value and the email sent to the invitee; it is
    never written to the DB or logged."""
    settings = get_or_create_platform_settings(session)
    otp = generate_otp()
    invite = Invite(
        email=email.strip().lower(),
        role=role,
        organization_id=organization_id,
        invited_by_type=invited_by_type,
        invited_by_id=invited_by_id,
        otp_hash=hash_otp(otp),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.invite_expire_days),
        max_attempts=settings.invite_max_attempts,
    )
    session.add(invite)
    session.commit()
    session.refresh(invite)
    return invite, otp
