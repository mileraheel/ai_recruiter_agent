"""
Wraps `docker exec ... pg_dump` so backups are one command instead of
remembering the exact syntax. Writes to backups/ with a timestamped
filename. See db/scripts/README.md for the full recovery story --
this alone does NOT protect you if your Postgres container has no
persistent volume; it protects you from bad schema changes and disk
issues on top of that.

Usage:
    python db/scripts/backup.py
    python db/scripts/backup.py --container ai_recruiter_db --db ai_recruiter --user postgres
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Backup the AI Recruiter Agent database")
    parser.add_argument("--container", default="ai_recruiter_db")
    parser.add_argument("--db", default="ai_recruiter")
    parser.add_argument("--user", default="postgres")
    parser.add_argument("--out-dir", default="backups")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out_file = out_dir / f"{args.db}_{timestamp}.sql"

    print(f"Backing up {args.db} from container {args.container} to {out_file} ...")
    with open(out_file, "wb") as f:
        result = subprocess.run(
            ["docker", "exec", args.container, "pg_dump", "-U", args.user, args.db],
            stdout=f,
        )

    if result.returncode != 0:
        print("Backup failed. Check that the container name and DB name are correct, "
              "and that Docker is running.", file=sys.stderr)
        sys.exit(1)

    size_kb = out_file.stat().st_size / 1024
    print(f"Backup complete: {out_file} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
