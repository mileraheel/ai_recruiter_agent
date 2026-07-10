"""
DEV-ONLY: drops every table and recreates them fresh from the current
db/models.py. Use this instead of hand-writing ALTER TABLE statements
whenever the schema changes and there's nothing real in the database
worth preserving yet (early development/testing) -- see this repo's
README for why create_all() alone can't apply column changes to a
table that already exists.

This is NOT a migration tool -- it destroys all data, including your
superuser account. Once there's real organization/candidate data
worth keeping, switch to a proper migration tool (e.g. Alembic)
instead of reaching for this.

Usage:
    python -m db.scripts.reset_db          # asks for confirmation
    python -m db.scripts.reset_db --yes    # skips the prompt (scripting/CI)
"""
from __future__ import annotations

import argparse

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import text

from db.models import Base
from db.session import get_engine


def main() -> None:
    parser = argparse.ArgumentParser(description="Drop and recreate every table from db/models.py")
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt")
    args = parser.parse_args()

    engine = get_engine()
    # Doesn't print the DB name/credentials -- just enough context to
    # confirm which server this is about to wipe.
    safe_url = str(engine.url).split("@")[-1] if "@" in str(engine.url) else str(engine.url)
    print(f"This will DROP EVERY TABLE (all data, all accounts) on: {safe_url}")

    if not args.yes:
        confirm = input("Type 'reset' to continue: ")
        if confirm.strip() != "reset":
            raise SystemExit("Confirmation did not match -- aborted, nothing changed.")

    print("Dropping all tables...")
    # Base.metadata.drop_all() orders drops using the CURRENT model graph --
    # if a schema change removed/renamed a foreign key (e.g. a column swap),
    # the live database can still have the OLD constraint sitting there,
    # unknown to the current metadata, and drop_all() has no way to order
    # around a constraint it doesn't know exists. Dropping the whole schema
    # with CASCADE sidesteps that entirely -- correct for a dev-only reset
    # tool where nothing here is worth preserving anyway.
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    print("Recreating all tables from db/models.py...")
    Base.metadata.create_all(engine)
    print("Done. Tables are empty -- re-run your seed steps, e.g.:")
    print("  python -m db.seed")
    print("  python -m api.bootstrap_superuser_dev")


if __name__ == "__main__":
    main()
