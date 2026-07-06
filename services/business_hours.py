"""
Business-hours-only sending -- an email landing in a recruiter's inbox
at 3am undermines the "looks human" positioning. Uses Python's stdlib
zoneinfo (3.9+), no new dependency.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from db.models import Organization


def is_within_business_hours(org: Organization) -> bool:
    if not org.send_only_business_hours:
        return True  # feature off -- always "within hours"

    try:
        tz = ZoneInfo(org.business_hours_timezone)
    except Exception:
        tz = ZoneInfo("America/New_York")  # fallback if an invalid tz string was somehow saved

    local_hour = datetime.now(tz).hour
    return org.business_hours_start_hour <= local_hour < org.business_hours_end_hour
