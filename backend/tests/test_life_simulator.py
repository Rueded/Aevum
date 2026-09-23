import pytest
from datetime import datetime, timezone, timedelta
from app.life.models import LifeActivityStatus, LifePlanStatus, LifeEventType
from app.life.simulator import LifeSimulator
from app.life.services import LifeService
from app.db.models import (
    LifeStateRecord, LifeActivityRecord, LifePlanRecord, LifeEventRecord, LifeGoalRecord,
    CharacterStateRecord, EmotionStateRecord, RelationshipRecord, MemoryRecord
)
from sqlalchemy import select, func

@pytest.fixture
def simulator(test_session):
    return LifeSimulator(test_session)

@pytest.fixture
def life_service(test_session):
    return LifeService(test_session)

@pytest.mark.asyncio
async def test_reconcile_starts_due_plan(simulator, life_service, test_session):
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    await life_service.initialize_aevum_life("aevum")
    
    plan = await life_service.create_plan(
        "aevum", "Test Plan", "Desc",
        planned_start=now - timedelta(minutes=10),
        planned_end=now + timedelta(minutes=50)
    )
    
    res = await simulator.reconcile("aevum", now)
    assert res.processed_plans == 1
    assert res.started_activities == 1
    assert res.generated_events == 1
    
    # State should be updated
    state = await life_service.get_life_state("aevum")
    assert state.current_activity == "Test Plan"
    
    # Idempotency
    res2 = await simulator.reconcile("aevum", now)
    assert res2.processed_plans == 0
    assert res2.started_activities == 0
    assert res2.generated_events == 0

@pytest.mark.asyncio
async def test_reconcile_completes_activity(simulator, life_service, test_session):
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    await life_service.initialize_aevum_life("aevum")
    
    plan = await life_service.create_plan(
        "aevum", "Test Plan", "Desc",
        planned_start=now - timedelta(minutes=60),
        planned_end=now - timedelta(minutes=10)
    )
    
    # First tick to start it at 11:00
    await simulator.reconcile("aevum", now - timedelta(minutes=60))
    
    # Second tick to complete it at 12:00
    res = await simulator.reconcile("aevum", now)
    assert res.completed_activities == 1
    assert res.generated_events == 1
    
    # State should revert to IDLE / REST
    state = await life_service.get_life_state("aevum")
    assert state.current_activity in ("IDLE", "REST")
    
    # Plan should be completed
    updated_plan = await life_service.get_plan(plan.id)
    assert updated_plan.status == LifePlanStatus.COMPLETED
    
    # Idempotency
    res2 = await simulator.reconcile("aevum", now)
    assert res2.completed_activities == 0
    assert res2.generated_events == 0

@pytest.mark.asyncio
async def test_future_plan_not_started(simulator, life_service, test_session):
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    await life_service.initialize_aevum_life("aevum")
    
    plan = await life_service.create_plan(
        "aevum", "Future Plan", "Desc",
        planned_start=now + timedelta(minutes=10)
    )
    
    res = await simulator.reconcile("aevum", now)
    assert res.processed_plans == 0

@pytest.mark.asyncio
async def test_cross_domain_isolation_during_simulation(simulator, life_service, test_session):
    async def get_counts():
        char_states = await test_session.scalar(select(func.count(CharacterStateRecord.id)))
        emo_states = await test_session.scalar(select(func.count(EmotionStateRecord.id)))
        rels = await test_session.scalar(select(func.count(RelationshipRecord.id)))
        mems = await test_session.scalar(select(func.count(MemoryRecord.id)))
        return (char_states, emo_states, rels, mems)
        
    counts_before = await get_counts()
    
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    await life_service.initialize_aevum_life("aevum")
    await life_service.create_plan(
        "aevum", "Isolated Plan", "Desc",
        planned_start=now - timedelta(minutes=10),
        planned_end=now - timedelta(minutes=5)
    )
    
    # Start it
    await simulator.reconcile("aevum", now - timedelta(minutes=10))
    # Complete it
    await simulator.reconcile("aevum", now)
    
    counts_after = await get_counts()
    assert counts_before == counts_after


from zoneinfo import ZoneInfo
from app.core.config import settings

@pytest.mark.asyncio
async def test_life_plan_timezone_boundary(simulator, life_service, test_session):
    await life_service.initialize_aevum_life("aevum")
    
    # Scheduled for 2026-09-16 00:30 Asia/Kuala_Lumpur
    aevum_tz = ZoneInfo(settings.aevum_timezone)
    scheduled_aevum = datetime(2026, 9, 16, 0, 30, 0, tzinfo=aevum_tz)
    
    # The corresponding UTC instant is 2026-09-15 16:30:00Z
    scheduled_utc = scheduled_aevum.astimezone(timezone.utc)
    
    plan = await life_service.create_plan(
        "aevum", "Midnight Plan", "Desc",
        planned_start=scheduled_utc
    )
    
    # 1. Before scheduled time (16:29:59 UTC)
    before_utc = scheduled_utc - timedelta(seconds=1)
    res = await simulator.reconcile("aevum", before_utc)
    assert res.processed_plans == 0
    updated_plan = await life_service.get_plan(plan.id)
    assert updated_plan.status == LifePlanStatus.PLANNED
    
    # 2. Exact scheduled time (16:30:00 UTC)
    res2 = await simulator.reconcile("aevum", scheduled_utc)
    assert res2.processed_plans == 1
    updated_plan2 = await life_service.get_plan(plan.id)
    assert updated_plan2.status == LifePlanStatus.IN_PROGRESS
    
    # 3. After scheduled time (16:30:01 UTC)
    # Simulator should be idempotent here
    after_utc = scheduled_utc + timedelta(seconds=1)
    res3 = await simulator.reconcile("aevum", after_utc)
    assert res3.processed_plans == 0
