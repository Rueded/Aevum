"""Tests for 24-Hour Diurnal Life Schedule Engine."""

import pytest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import AsyncSession

from app.life.schedule_engine import LifeScheduleEngine, OccupationTrack, ScheduleSlot
from app.db.models import CharacterStateRecord, LifeStateRecord


@pytest.mark.asyncio
async def test_life_schedule_slots_coverage():
    """Verify slots map accurately across different times of day and occupation tracks."""
    tz = "Asia/Kuala_Lumpur"

    # 03:00 -> Night sleep (Sembreak)
    t_3am = datetime(2026, 10, 9, 3, 0, 0, tzinfo=ZoneInfo(tz))
    slot_3am = LifeScheduleEngine.get_current_slot(t_3am, timezone_str=tz, track=OccupationTrack.STUDENT_SEMBREAK)
    assert slot_3am.slot_id == "sembreak_sleep"
    assert "熟睡" in slot_3am.activity
    assert slot_3am.status == "REST"

    # 10:00 with Sleep Debt -> Sleep debt recovery
    t_10am = datetime(2026, 10, 9, 10, 0, 0, tzinfo=ZoneInfo(tz))
    slot_sleep_debt = LifeScheduleEngine.get_current_slot(t_10am, timezone_str=tz, has_sleep_debt=True)
    assert slot_sleep_debt.slot_id == "sleep_debt_recovery"
    assert "赖床" in slot_sleep_debt.activity

    # In-term student (weekday morning 08:00) -> Rush to 8am lecture
    t_8am = datetime(2026, 10, 9, 8, 0, 0, tzinfo=ZoneInfo(tz)) # 2026-10-09 is a Friday
    slot_in_term = LifeScheduleEngine.get_current_slot(t_8am, timezone_str=tz, track=OccupationTrack.STUDENT_IN_TERM)
    assert slot_in_term.slot_id == "hurry_morning"
    assert "早八" in slot_in_term.activity

    # Working professional (weekday 09:00) -> Morning work / commute
    t_9am = datetime(2026, 10, 9, 9, 0, 0, tzinfo=ZoneInfo(tz))
    slot_work = LifeScheduleEngine.get_current_slot(t_9am, timezone_str=tz, track=OccupationTrack.WORKING_PROFESSIONAL)
    assert slot_work.slot_id == "work_morning_tasks"
    assert "工作" in slot_work.activity or "早会" in slot_work.activity


@pytest.mark.asyncio
async def test_life_schedule_reconcile_database(test_session: AsyncSession):
    """Verify schedule reconciliation synchronizes both LifeStateRecord and CharacterStateRecord."""
    tz = "Asia/Kuala_Lumpur"
    t_10am = datetime(2026, 10, 9, 10, 0, 0, tzinfo=ZoneInfo(tz))

    # Initialize records
    char = CharacterStateRecord(
        id="aevum",
        mood="calm",
        energy=0.7,
        stress=0.2,
        social_energy=0.6,
        confidence=0.7,
        irritation=0.0,
        loneliness=0.3,
        current_activity="resting",
        current_location="home",
    )
    test_session.add(char)
    await test_session.commit()

    # Reconcile for 10am
    life_record = await LifeScheduleEngine.reconcile_schedule(
        test_session,
        character_id="aevum",
        dt_utc=t_10am,
        force=True,
        timezone_str=tz,
    )
    await test_session.commit()

    assert "钢琴" in life_record.current_activity
    assert "书房" in life_record.current_location

    # Re-query CharacterStateRecord
    updated_char = await test_session.get(CharacterStateRecord, "aevum")
    assert "钢琴" in updated_char.current_activity
    assert "书房" in updated_char.current_location
