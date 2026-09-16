from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app.core.config import settings

def _get_aevum_tz() -> ZoneInfo:
    return ZoneInfo(settings.aevum_timezone)

def now_utc() -> datetime:
    """Return the current time as a UTC timezone-aware instant."""
    return datetime.now(timezone.utc)

def now_aevum() -> datetime:
    """Return the current time as an Aevum timezone-aware local time."""
    return now_utc().astimezone(_get_aevum_tz())

def utc_to_aevum(dt_utc: datetime) -> datetime:
    """Convert a UTC instant to Aevum's local time."""
    if dt_utc.tzinfo is None:
        raise ValueError("Cannot convert naive datetime. Must be timezone-aware.")
    return dt_utc.astimezone(_get_aevum_tz())

def aevum_to_utc(dt_aevum: datetime) -> datetime:
    """Convert an Aevum local time instant to UTC."""
    if dt_aevum.tzinfo is None:
        raise ValueError("Cannot convert naive datetime. Must be timezone-aware.")
    return dt_aevum.astimezone(timezone.utc)
