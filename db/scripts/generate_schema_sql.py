"""
Regenerates db/scripts/schema.sql from the actual SQLAlchemy models --
a human-readable reference snapshot of the full schema. This is NOT
what the running app uses to create tables (that's
db/session.py::init_db(), via SQLAlchemy's create_all()); this file
exists so the schema can be reviewed, diffed, or handed to a DBA
without needing to read Python.

Run this after any change to db/models.py:
    python -m db.scripts.generate_schema_sql
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from config.app_info import APP_NAME
from db.models import Base

OUTPUT_PATH = Path(__file__).parent / "schema.sql"


def main() -> None:
    statements = []
    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
        statements.append(ddl.strip() + ";")

    header = (
        f"-- {APP_NAME} -- full database schema (PostgreSQL)\n"
        "-- Generated from db/models.py -- this is a REFERENCE snapshot.\n"
        "-- The actual source of truth is db/models.py + db/session.py::init_db()\n"
        "-- (SQLAlchemy create_all()), which is what the app itself runs.\n"
        "-- Regenerate this file after schema changes with:\n"
        "--   python -m db.scripts.generate_schema_sql\n\n"
    )

    OUTPUT_PATH.write_text(header + "\n\n".join(statements) + "\n")
    print(f"Wrote {len(statements)} CREATE TABLE statements to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
