import pytest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app.core.config import settings
from app.core.time import now_utc, now_aevum, utc_to_aevum, aevum_to_utc

def test_midnight_boundary():
    # 2026-09-15T16:00:00Z
    dt_utc = datetime(2026, 9, 15, 16, 0, 0, tzinfo=timezone.utc)
    dt_aevum = utc_to_aevum(dt_utc)
    
    # Verify local calendar date logic sees this as September 16
    assert dt_aevum.year == 2026
    assert dt_aevum.month == 9
    assert dt_aevum.day == 16
    assert dt_aevum.hour == 0
    assert dt_aevum.minute == 0
    
    # Just before boundary: 15:59:59Z
    dt_before_utc = datetime(2026, 9, 15, 15, 59, 59, tzinfo=timezone.utc)
    dt_before_aevum = utc_to_aevum(dt_before_utc)
    assert dt_before_aevum.day == 15
    assert dt_before_aevum.hour == 23
    assert dt_before_aevum.minute == 59
    
    # Just after boundary: 16:00:01Z
    dt_after_utc = datetime(2026, 9, 15, 16, 0, 1, tzinfo=timezone.utc)
    dt_after_aevum = utc_to_aevum(dt_after_utc)
    assert dt_after_aevum.day == 16
    assert dt_after_aevum.hour == 0
    assert dt_after_aevum.minute == 0

def test_utc_round_trip():
    original_aevum = datetime(2026, 9, 16, 12, 30, 0, tzinfo=ZoneInfo(settings.aevum_timezone))
    
    as_utc = aevum_to_utc(original_aevum)
    assert as_utc.tzinfo == timezone.utc
    
    back_to_aevum = utc_to_aevum(as_utc)
    assert back_to_aevum == original_aevum
    assert back_to_aevum.tzinfo.key == settings.aevum_timezone

def test_machine_timezone_independence():
    # Because we use ZoneInfo explicitly with timezone-aware datetimes,
    # the machine timezone does not affect the calculation.
    # The timezone-aware objects maintain their own absolute offsets.
    # We prove this by instantiating an explicitly offset time
    # and converting to aevum and utc.
    dt = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)
    dt_aevum = utc_to_aevum(dt)
    
    assert dt_aevum.utcoffset().total_seconds() == 8 * 3600
