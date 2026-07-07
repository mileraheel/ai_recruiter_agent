"""
Backend logging setup. Call configure_logging() once, at app startup
(see api/main.py) -- everything else in the codebase should just use
`logging.getLogger(__name__)` as normal from here on.

Writes to BOTH:
  - console (same as today -- your uvicorn terminal), and
  - logs/app.log, rotating at 5MB with 5 backups kept (logs/app.log,
    app.log.1, ... app.log.5) so it never grows unbounded, but survives
    closing the terminal -- this is the durable record for tracking
    down a bug after the fact.

logs/ is gitignored (see .gitignore) -- these are local runtime
artifacts, not something to commit.
"""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(os.environ.get("LOG_DIR", "logs"))
LOG_FILE = LOG_DIR / "app.log"
MAX_BYTES = 5 * 1024 * 1024  # 5MB per file
BACKUP_COUNT = 5

_configured = False


def configure_logging() -> None:
    global _configured
    if _configured:
        return  # calling twice (e.g. under --reload) shouldn't duplicate handlers
    _configured = True

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8")
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(console_handler)
    root.addHandler(file_handler)

    # uvicorn's own access/error logs (one line per request, startup
    # messages) go through Python logging too -- route them into the
    # same file instead of only the console, without changing their
    # format/verbosity.
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logging.getLogger(name).handlers = [console_handler, file_handler]
        logging.getLogger(name).propagate = False
