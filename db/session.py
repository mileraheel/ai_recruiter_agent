"""
Engine/session setup. Reads DATABASE_URL from the environment, e.g.:
    postgresql+psycopg://user:password@localhost:5432/ai_recruiter
"""
from __future__ import annotations

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base


def get_engine():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Example: "
            "postgresql+psycopg://user:password@localhost:5432/ai_recruiter"
        )
    return create_engine(db_url, future=True)


def get_session_factory():
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def init_db() -> None:
    """Creates all tables. Fine for early development; switch to Alembic
    migrations once the schema stabilizes and there's real data to preserve."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    print("Database tables created.")


if __name__ == "__main__":
    init_db()
