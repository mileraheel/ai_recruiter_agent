"""
Seeds baseline reference data into a freshly-created (empty) database.

This does NOT restore your accumulated jobs/recruiters/decisions -- that's
what backups are for (see db/scripts/README.md). What this DOES restore is
the job_sources rows matching your current candidate.yaml, so a fresh
schema isn't a completely blank slate.

Candidate seeding from YAML is retired -- candidates are created via
the app's signup/invite flow now (see config/candidate.yaml's header
comment), not this script.

Usage:
    python -m db.seed
    python -m db.seed --config config/candidate.yaml
"""
from __future__ import annotations

import argparse

from dotenv import load_dotenv

load_dotenv()

from config.loader import load_config
from db.session import get_session_factory
from db.models import JobSource


def seed_sources_from_config(session, cfg) -> list[str]:
    """Idempotent: running this multiple times updates existing rows to
    match the current config rather than creating duplicates."""
    seeded = []
    for source_name, source_cfg in cfg.sources.items():
        existing = session.query(JobSource).filter_by(source_name=source_name).one_or_none()
        if existing is None:
            existing = JobSource(source_name=source_name)
            session.add(existing)
        existing.enabled = source_cfg.enabled
        existing.mode = source_cfg.mode
        existing.source_type = source_cfg.mode
        existing.status = existing.status or "idle"
        seeded.append(source_name)
    session.commit()
    return seeded


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed baseline reference data")
    parser.add_argument("--config", default="config/candidate.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)
    SessionFactory = get_session_factory()
    with SessionFactory() as session:
        seeded_sources = seed_sources_from_config(session, cfg)
    print(f"Seeded/updated {len(seeded_sources)} job_sources rows: {seeded_sources}")


if __name__ == "__main__":
    main()
