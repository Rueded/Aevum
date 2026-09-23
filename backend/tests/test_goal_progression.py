import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import select

from app.life.clock import DeterministicSimulationClock
from app.life.models import (
    LifeActivityStatus,
    LifeActivityType,
    LifeEventType,
    LifeGoalStatus,
)
from app.life.services import LifeService
from app.life.simulator import LifeSimulator
from app.db.models import LifeEventRecord


@pytest.fixture
def sim_clock():
    return DeterministicSimulationClock(datetime(2026, 9, 18, 9, 0, 0, tzinfo=timezone.utc))


@pytest.fixture
def life_service(test_session, sim_clock):
    return LifeService(test_session, clock=sim_clock)


@pytest.fixture
def simulator(test_session, sim_clock):
    return LifeSimulator(test_session, clock=sim_clock)


@pytest.mark.asyncio
async def test_unlinked_activity_leaves_goals_untouched(simulator, life_service, sim_clock):
    """Invariant 22: Activity with goal_id=None completing leaves all active goals 100% unmutated."""
    character_id = "aevum"
    await life_service.initialize_aevum_life(character_id)

    # Character has an initial active goal
    goals = await life_service.list_goals(character_id)
    assert len(goals) == 1
    initial_goal = goals[0]
    assert initial_goal.progress == 0.0

    # Create activity WITHOUT goal_id
    t_start = sim_clock.now()
    t_end = t_start + timedelta(hours=1)
    act = await life_service.create_activity(
        character_id=character_id,
        activity_type=LifeActivityType.OUTING,
        title="Walk in Park",
        description="Casual outdoor walk",
        location="PARK",
        goal_id=None,
        started_at=t_start,
        planned_end_at=t_end,
    )
    assert act.goal_id is None

    # Advance time and reconcile
    sim_clock.set_time(t_end)
    result = await simulator.reconcile(character_id)
    assert result.completed_activities == 1
    assert result.updated_goals == 0

    # Verify goal progress remains exactly 0.0
    updated_goal = await life_service.get_goal(initial_goal.id)
    assert updated_goal.progress == 0.0
    assert updated_goal.status == LifeGoalStatus.ACTIVE


@pytest.mark.asyncio
async def test_explicit_goal_progression(simulator, life_service, sim_clock):
    """Invariant 22: Activity with explicit goal_id advances progress by goal.progress_per_completion."""
    character_id = "aevum"
    await life_service.initialize_aevum_life(character_id)

    goal = await life_service.create_goal(
        character_id=character_id,
        title="Master Violin Etudes",
        description="Daily violin etudes",
        importance=0.8,
        progress_per_completion=0.25,
    )
    assert goal.progress == 0.0
    assert goal.progress_per_completion == 0.25

    t_start = sim_clock.now()
    t_end = t_start + timedelta(hours=1)
    act = await life_service.create_activity(
        character_id=character_id,
        activity_type=LifeActivityType.MUSIC,
        title="Practice Violin",
        description="Scales and etudes",
        location="HOME",
        goal_id=goal.id,
        started_at=t_start,
        planned_end_at=t_end,
    )

    sim_clock.set_time(t_end)
    result = await simulator.reconcile(character_id)
    assert result.completed_activities == 1
    assert result.updated_goals == 1

    updated_goal = await life_service.get_goal(goal.id)
    assert updated_goal.progress == 0.25
    assert updated_goal.status == LifeGoalStatus.ACTIVE


@pytest.mark.asyncio
async def test_goal_completion_and_success_event(simulator, life_service, sim_clock, test_session):
    """Reaching progress >= 1.0 transitions goal to COMPLETED and emits immutable SUCCESS LifeEvent."""
    character_id = "aevum"
    await life_service.initialize_aevum_life(character_id)

    # Goal starts at 0.80, with 0.25 increment -> will reach 1.0 and complete
    goal = await life_service.create_goal(
        character_id=character_id,
        title="Finish Novel Chapter",
        description="Write and polish chapter 1",
        importance=0.9,
        progress_per_completion=0.25,
    )
    await life_service.update_goal(goal.id, progress=0.80)

    t_start = sim_clock.now()
    t_end = t_start + timedelta(hours=1)
    await life_service.create_activity(
        character_id=character_id,
        activity_type=LifeActivityType.READING,
        title="Polish Chapter 1",
        description="Final polishing",
        location="HOME",
        goal_id=goal.id,
        started_at=t_start,
        planned_end_at=t_end,
    )

    sim_clock.set_time(t_end)
    result = await simulator.reconcile(character_id)
    assert result.completed_activities == 1
    assert result.updated_goals == 1

    updated_goal = await life_service.get_goal(goal.id)
    assert updated_goal.progress == 1.0
    assert updated_goal.status == LifeGoalStatus.COMPLETED

    # Verify immutable SUCCESS LifeEvent created
    stmt = select(LifeEventRecord).where(
        LifeEventRecord.idempotency_key == f"goal_completed:{goal.id}"
    )
    success_event = (await test_session.scalars(stmt)).first()
    assert success_event is not None
    assert success_event.event_type == LifeEventType.SUCCESS.value
    assert f"Achieved Goal: {goal.title}" in success_event.title


@pytest.mark.asyncio
async def test_single_settlement_idempotency(simulator, life_service, sim_clock):
    """Standard 26: Completed activity contributes progress exactly once; re-reconciling contributes 0."""
    character_id = "aevum"
    await life_service.initialize_aevum_life(character_id)

    goal = await life_service.create_goal(
        character_id=character_id,
        title="Multi-session study",
        description="Several study blocks",
        importance=0.7,
        progress_per_completion=0.15,
    )

    t_start = sim_clock.now()
    t_end = t_start + timedelta(hours=1)
    await life_service.create_activity(
        character_id=character_id,
        activity_type=LifeActivityType.STUDY,
        title="Study Session 1",
        description="Study block",
        location="HOME",
        goal_id=goal.id,
        started_at=t_start,
        planned_end_at=t_end,
    )

    # First reconciliation: advances goal by 0.15
    sim_clock.set_time(t_end)
    res1 = await simulator.reconcile(character_id)
    assert res1.completed_activities == 1
    assert res1.updated_goals == 1

    g1 = await life_service.get_goal(goal.id)
    assert g1.progress == 0.15

    # Second reconciliation at t_end + 10s: MUST contribute 0 progress
    sim_clock.advance(timedelta(seconds=10))
    res2 = await simulator.reconcile(character_id)
    assert res2.completed_activities == 0
    assert res2.updated_goals == 0

    g2 = await life_service.get_goal(goal.id)
    assert g2.progress == 0.15  # Exactly unchanged!
