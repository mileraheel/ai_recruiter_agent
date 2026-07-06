"""
One-time (or repeatable) admin account creation.

Usage:
    python -m api.bootstrap_admin --username admin
    (prompts for password interactively -- never pass it as a CLI arg,
    since that leaks into shell history)
"""
from __future__ import annotations

import argparse
import getpass

from dotenv import load_dotenv

load_dotenv()

from api.auth import hash_password
from db.models import AdminUser
from db.session import get_session_factory


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or reset an admin user")
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
        existing = session.query(AdminUser).filter_by(username=args.username).one_or_none()
        if existing:
            existing.password_hash = hash_password(password)
            session.commit()
            print(f"Password updated for existing admin '{args.username}'.")
        else:
            session.add(AdminUser(username=args.username, password_hash=hash_password(password)))
            session.commit()
            print(f"Admin '{args.username}' created.")


if __name__ == "__main__":
    main()
