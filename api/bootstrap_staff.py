"""
Create a staff account. In production this should go through the
superuser API (POST /api/superuser/staff) once a superuser is logged
in; this CLI script exists for bootstrapping the very first staff
account, or for direct server-side account management.

Usage:
    python -m api.bootstrap_staff --username jane
"""
from __future__ import annotations

import argparse
import getpass

from dotenv import load_dotenv

load_dotenv()

from api.auth import hash_password
from db.models import Staff
from db.session import get_session_factory


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or reset a staff account")
    parser.add_argument("--username", required=True)
    args = parser.parse_args()

    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        raise SystemExit("Passwords did not match.")
    if len(password) < 10:
        raise SystemExit("Password must be at least 10 characters.")

    SessionFactory = get_session_factory()
    with SessionFactory() as session:
        existing = session.query(Staff).filter_by(username=args.username).one_or_none()
        if existing:
            existing.password_hash = hash_password(password)
            existing.is_active = True
            session.commit()
            print(f"Password updated (and reactivated) for existing staff '{args.username}'.")
        else:
            session.add(Staff(username=args.username, password_hash=hash_password(password)))
            session.commit()
            print(f"Staff '{args.username}' created.")


if __name__ == "__main__":
    main()
