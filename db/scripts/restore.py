"""
Restores a backup taken by db/scripts/backup.py. Destructive -- this
overwrites whatever is currently in the target database with the backup's
contents. Asks for confirmation before running.

Usage:
    python db/scripts/restore.py backups/ai_recruiter_2026-07-02_143000.sql
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Restore a database backup")
    parser.add_argument("backup_file", help="Path to a .sql file created by backup.py")
    parser.add_argument("--container", default="ai_recruiter_db")
    parser.add_argument("--db", default="ai_recruiter")
    parser.add_argument("--user", default="postgres")
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt")
    args = parser.parse_args()

    backup_path = Path(args.backup_file)
    if not backup_path.exists():
        print(f"Backup file not found: {backup_path}", file=sys.stderr)
        sys.exit(1)

    if not args.yes:
        confirm = input(
            f"This will OVERWRITE all current data in database '{args.db}' "
            f"with the contents of {backup_path}. Type 'yes' to continue: "
        )
        if confirm.strip().lower() != "yes":
            print("Cancelled.")
            return

    print(f"Restoring {backup_path} into {args.db} on container {args.container} ...")
    with open(backup_path, "rb") as f:
        result = subprocess.run(
            ["docker", "exec", "-i", args.container, "psql", "-U", args.user, "-d", args.db],
            stdin=f,
        )

    if result.returncode != 0:
        print("Restore failed. Check container/db/user names and that Docker is running.", file=sys.stderr)
        sys.exit(1)

    print("Restore complete.")


if __name__ == "__main__":
    main()
