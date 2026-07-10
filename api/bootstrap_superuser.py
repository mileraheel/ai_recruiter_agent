"""
One-time (or repeatable) superuser account creation. No self-signup for
this role -- platform-wide reporting access across every organization
is too sensitive to leave open.

Usage:
    python -m api.bootstrap_superuser --username you
"""
from __future__ import annotations

import argparse
import getpass

from dotenv import load_dotenv

load_dotenv()

from api.auth import hash_password
from db.models import SuperUser
from db.session import get_session_factory


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or reset a superuser")
    parser.add_argument("--username", required=True)
    parser.add_argument("--email", default=None, help="Optional -- needed for self-service password reset")
    args = parser.parse_args()

    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        raise SystemExit("Passwords did not match.")
    if len(password) < 10:
        raise SystemExit("Password must be at least 10 characters.")

    SessionFactory = get_session_factory()
    with SessionFactory() as session:
        existing = session.query(SuperUser).filter_by(username=args.username).one_or_none()
        if existing:
            existing.password_hash = hash_password(password)
            if args.email:
                existing.email = args.email
            session.commit()
            print(f"Password updated for existing superuser '{args.username}'.")
        else:
            session.add(SuperUser(username=args.username, email=args.email, password_hash=hash_password(password)))
            session.commit()
            print(f"Superuser '{args.username}' created.")


if __name__ == "__main__":
    main()
