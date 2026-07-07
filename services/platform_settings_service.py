"""
Platform-wide settings -- a single row (id=1), superuser-editable,
for configuration that doesn't belong to any one organization. Same
lazy-create-on-first-access pattern as
services/billing_service.py::get_or_create_subscription.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from db.models import PlatformSettings

SETTINGS_ROW_ID = 1


def get_or_create_platform_settings(session: Session) -> PlatformSettings:
    settings = session.query(PlatformSettings).filter_by(id=SETTINGS_ROW_ID).one_or_none()
    if settings is None:
        settings = PlatformSettings(id=SETTINGS_ROW_ID)
        session.add(settings)
        session.flush()
    return settings
