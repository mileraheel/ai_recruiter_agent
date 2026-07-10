"""
Single source of truth for the platform's display name, used anywhere
the app needs to name itself out loud -- API docs title, CLI banner,
generated schema header, outreach-email disclosure line, etc.

Sourced from the APP_NAME env var so it can change (e.g. during the
current pre-launch naming period) without a code change or redeploy of
anything other than the env var itself. Defaults to "Role Pace" so
nothing breaks if the var isn't set.
"""
from __future__ import annotations

import os

APP_NAME = os.environ.get("APP_NAME", "Role Pace")
