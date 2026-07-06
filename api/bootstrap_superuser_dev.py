"""
DEV-ONLY, NON-INTERACTIVE superuser seeding for local testing.

`api/bootstrap_superuser.py` is the real one (interactive, getpass,
no defaults) -- keep using that for anything beyond your own local
box. This script exists purely so you don't have to re-type a
password every time you wipe/recreate your local dev database while
testing: it reads a fixed username/password from your own .env
(never committed -- see .gitignore) and upserts that superuser,
same idempotent create-or-reset behavior as the interactive script.

Setup (one time): add these two lines to your local .env:
    DEV_SUPERUSER_USERNAME=raheel
    DEV_SUPERUSER_PASSWORD=<pick something you'll remember, 10+ chars>

Usage:
    python -m api.bootstrap_superuser_dev

Refuses to run unless DEV_SUPERUSER_PASSWORD is explicitly set --
there is still no invented/hardcoded password baked into the code
itself, only a convenience layer on top of your own local .env.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

from api.auth import hash_password
from db.models import SuperUser
from db.session import get_session_factory


def main() -> None:
    username = os.environ.get("DEV_SUPERUSER_USERNAME")
    password = os.environ.get("DEV_SUPERUSER_PASSWORD")

    if not username or not password:
        raise SystemExit(
            "DEV_SUPERUSER_USERNAME and DEV_SUPERUSER_PASSWORD must both be "
            "set in your .env for this dev-only script to run. Add them "
            "once, then this becomes a stable login you can reuse across "
            "every DB reset. For anything other than your own local "
            "machine, use `python -m api.bootstrap_superuser` instead."
        )
    if len(password) < 10:
        raise SystemExit("DEV_SUPERUSER_PASSWORD must be at least 10 characters.")

    SessionFactory = get_session_factory()
    with SessionFactory() as session:
        existing = session.query(SuperUser).filter_by(username=username).one_or_none()
        if existing:
            existing.password_hash = hash_password(password)
            session.commit()
            print(f"[dev] Password reset for existing superuser '{username}'.")
        else:
            session.add(SuperUser(username=username, password_hash=hash_password(password)))
            session.commit()
            print(f"[dev] Superuser '{username}' created.")
    print("[dev] Log in at the app's login screen with the credentials from your .env.")


if __name__ == "__main__":
    main()
