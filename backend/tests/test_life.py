import pytest
from datetime import datetime, timezone
from pydantic import ValidationError
from sqlalchemy import select, func
from app.life.models import (
    LifeState, LifeActivity, LifePlan, LifeEvent, LifeGoal,
    LifeActivityType, LifeActivityStatus, LifePlanStatus, LifeEventType, LifeGoalStatus
)
from app.life.services import LifeService, OptimisticConcurrencyError
from app.db.models import (
    LifeStateRecord, LifeActivityRecord, LifePlanRecord, LifeEventRecord, LifeGoalRecord,
    CharacterStateRecord, EmotionStateRecord, RelationshipRecord, MemoryRecord
)

@pytest.fixture
def life_service(test_session):
    return LifeService(test_session)

@pytest.mark.asyncio
async def test_life_state_creation_retrieval(life_service, test_session):
    state = await life_service.get_life_state("aevum")
    assert state.character_id == "aevum"
    assert state.current_activity in ("IDLE", "REST")
    assert state.current_location == "HOME"
    assert state.version == 1

@pytest.mark.asyncio
async def test_life_state_update_and_version_increment(life_service, test_session):
    state = await life_service.get_life_state("aevum")
    updated_state = await life_service.update_life_state(
        "aevum", "STUDYING", "LIBRARY", expected_version=1
    )
    assert updated_state.current_activity == "STUDYING"
    assert updated_state.current_location == "LIBRARY"
    assert updated_state.version == 2

@pytest.mark.asyncio
async def test_life_state_optimistic_concurrency(life_service, test_session):
    await life_service.get_life_state("aevum")
    with pytest.raises(OptimisticConcurrencyError):
        await life_service.update_life_state("aevum", "STUDYING", "LIBRARY", expected_version=99)

def test_life_state_invalid_input():
    with pytest.raises(ValidationError):
        LifeState(current_activity="X", current_location="Y", updated_at="not_a_date")

@pytest.mark.asyncio
async def test_activity_lifecycle(life_service, test_session):
    activity = await life_service.create_activity("aevum", LifeActivityType.READING, "Read a book", "Reading a fantasy novel", "HOME")
    assert activity.activity_type == LifeActivityType.READING
    assert activity.status == LifeActivityStatus.ONGOING
    
    retrieved = await life_service.get_activity(activity.id)
    assert retrieved.id == activity.id
    
    activities = await life_service.list_activities("aevum")
    assert len(activities) == 1
    
    completed = await life_service.update_activity_status(activity.id, LifeActivityStatus.COMPLETED)
    assert completed.status == LifeActivityStatus.COMPLETED
    assert completed.completed_at is not None

@pytest.mark.asyncio
async def test_plan_lifecycle(life_service, test_session):
    plan = await life_service.create_plan("aevum", "Weekend trip", "Go to the beach")
    assert plan.status == LifePlanStatus.PLANNED
    
    retrieved = await life_service.get_plan(plan.id)
    assert retrieved.title == "Weekend trip"
    
    plans = await life_service.list_plans("aevum")
    assert len(plans) == 1
    
    updated = await life_service.update_plan_status(plan.id, LifePlanStatus.IN_PROGRESS)
    assert updated.status == LifePlanStatus.IN_PROGRESS

def test_plan_invalid_input():
    with pytest.raises(ValidationError):
        LifePlan(id="1", character_id="a", title="T", description="D", status="INVALID", importance=0.5, created_at=datetime.now(), updated_at=datetime.now())

@pytest.mark.asyncio
async def test_event_lifecycle(life_service, test_session):
    event = await life_service.create_event("aevum", LifeEventType.SOCIAL_EVENT, "Met a friend", "Had coffee")
    assert event.event_type == LifeEventType.SOCIAL_EVENT
    assert event.significance == 0.5
    
    retrieved = await life_service.get_event(event.id)
    assert retrieved.id == event.id
    
    events = await life_service.list_events("aevum")
    assert len(events) == 1

def test_event_significance_validation():
    with pytest.raises(ValidationError):
        LifeEvent(id="1", character_id="a", event_type=LifeEventType.OTHER, title="T", description="D", occurred_at=datetime.now(), created_at=datetime.now(), significance=1.5)

@pytest.mark.asyncio
async def test_goal_lifecycle(life_service, test_session):
    goal = await life_service.create_goal("aevum", "Learn Python", "Master async")
    assert goal.status == LifeGoalStatus.ACTIVE
    
    retrieved = await life_service.get_goal(goal.id)
    assert retrieved.id == goal.id
    
    goals = await life_service.list_goals("aevum")
    assert len(goals) == 1
    
    updated = await life_service.update_goal(goal.id, status=LifeGoalStatus.PAUSED, progress=0.5)
    assert updated.status == LifeGoalStatus.PAUSED
    assert updated.progress == 0.5

def test_goal_progress_validation():
    with pytest.raises(ValidationError):
        LifeGoal(id="1", character_id="a", title="T", description="D", status=LifeGoalStatus.ACTIVE, created_at=datetime.now(), updated_at=datetime.now(), progress=1.5, progress_per_completion=0.10)

@pytest.mark.asyncio
async def test_isolation(life_service, test_session):
    async def get_counts():
        char_states = await test_session.scalar(select(func.count(CharacterStateRecord.id)))
        emo_states = await test_session.scalar(select(func.count(EmotionStateRecord.id)))
        rels = await test_session.scalar(select(func.count(RelationshipRecord.id)))
        mems = await test_session.scalar(select(func.count(MemoryRecord.id)))
        return (char_states, emo_states, rels, mems)
        
    counts_before = await get_counts()
    
    await life_service.get_life_state("aevum")
    await life_service.update_life_state("aevum", "PLAYING", "PARK", 1)
    await life_service.create_event("aevum", LifeEventType.OTHER, "Test", "Test")
    await life_service.create_plan("aevum", "Test", "Test")
    await life_service.create_goal("aevum", "Test", "Test")
    
    counts_after = await get_counts()
    
    assert counts_before == counts_after

@pytest.mark.asyncio
async def test_initialize_aevum_life(life_service, test_session):
    await life_service.initialize_aevum_life("aevum")
    state = await life_service.get_life_state("aevum")
    assert state.current_activity in ("IDLE", "REST")
    assert state.current_location == "HOME"
    
    plans = await life_service.list_plans("aevum")
    assert len(plans) == 2
    
    goals = await life_service.list_goals("aevum")
    assert len(goals) == 1
    assert goals[0].title == "Improve at playing instrument"
    
    # Idempotency check
    await life_service.initialize_aevum_life("aevum")
    plans = await life_service.list_plans("aevum")
    assert len(plans) == 2
