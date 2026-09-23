import pytest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app.life.circadian_engine import CircadianEngine
from app.core.config import settings

def test_circadian_local_hour():
    tz = ZoneInfo(settings.aevum_timezone) # Asia/Kuala_Lumpur is UTC+8
    # 2026-09-18 02:00 UTC == 10:00 local time
    dt_utc = datetime(2026, 9, 18, 2, 0, 0, tzinfo=timezone.utc)
    hour = CircadianEngine.get_local_hour(dt_utc)
    assert abs(hour - 10.0) < 1e-4

def test_circadian_diurnal_curve():
    # Helper to create UTC instant from local hour
    tz = ZoneInfo(settings.aevum_timezone)
    def make_local(h: int, m: int = 0) -> datetime:
        loc = datetime(2026, 9, 18, h, m, 0, tzinfo=tz)
        return loc.astimezone(timezone.utc)

    # 1. Deep night valley (03:00 local)
    mod_night = CircadianEngine.get_circadian_modifier(make_local(3, 0))
    assert mod_night == -0.7

    # 2. Morning transition (07:45 local)
    mod_morning_trans = CircadianEngine.get_circadian_modifier(make_local(7, 45))
    assert -0.7 < mod_morning_trans < 0.3

    # 3. Morning productive window (10:00 local)
    mod_morning = CircadianEngine.get_circadian_modifier(make_local(10, 0))
    assert mod_morning == 0.5

    # 4. Midday dip (13:30 local)
    mod_midday = CircadianEngine.get_circadian_modifier(make_local(13, 30))
    assert mod_midday == 0.2

    # 5. Evening peak focus (19:00 local)
    mod_evening = CircadianEngine.get_circadian_modifier(make_local(19, 0))
    assert mod_evening == 0.65

    # 6. Evening wind-down (23:15 local)
    mod_winddown = CircadianEngine.get_circadian_modifier(make_local(23, 15))
    assert -0.2 <= mod_winddown <= 0.4

    # 7. Midnight transition (00:30 local)
    mod_midnight = CircadianEngine.get_circadian_modifier(make_local(0, 30))
    assert mod_midnight < -0.2

def test_circadian_naive_datetime_handling():
    # Naive datetime should be treated as UTC without crash
    dt_naive = datetime(2026, 9, 18, 2, 0, 0)
    mod = CircadianEngine.get_circadian_modifier(dt_naive)
    assert -1.0 <= mod <= 1.0
