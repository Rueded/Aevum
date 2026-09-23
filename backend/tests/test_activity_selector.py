import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import text, select

from app.life.activity_templates import (
    CANONICAL_ACTIVITY_TEMPLATES,
    ActivityGroundingPolicy,
    get_template_by_id,
)
from app.life.activity_utility import (
    HardEligibilityGate,
    ActivityUtilityEvaluator,
    effective_goal_fit,
)
from app.life.activity_selector import AutonomousActivitySelector
from app.life.clock import DeterministicSimulationClock
from app.life.models import (
    LifeActivity,
    LifeActivityType,
    LifeActivityStatus,
    LifeGoal,
    LifeGoalStatus,
)
from app.life.physiological_models import CharacterPhysiologicalState
from app.life.services import LifeService
from app.db.models import LifeActivityRecord, LifeStateRecord


@pytest.fixture
def sim_clock():
    return DeterministicSimulationClock(datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc))


@pytest.fixture
def life_service(test_session, sim_clock):
    return LifeService(test_session, clock=sim_clock)


@pytest.fixture
def selector(test_session, life_service):
    return AutonomousActivitySelector(test_session, life_service)


def test_catalog_registration():
    """Verify all 11 canonical templates are registered with correct grounding policies."""
    assert len(CANONICAL_ACTIVITY_TEMPLATES) == 11
    
    night_sleep = get_template_by_id("night_sleep")
    assert night_sleep is not None
    assert night_sleep.grounding_policy == ActivityGroundingPolicy.UNIVERSAL
    assert night_sleep.min_sleep_pressure_threshold == 0.50
    assert night_sleep.default_duration_minutes == 480

    deep_project = get_template_by_id("deep_focus_project")
    assert deep_project is not None
    assert deep_project.grounding_policy == ActivityGroundingPolicy.GOAL_REQUIRED

    read_lit = get_template_by_id("read_literature")
    assert read_lit is not None
    assert read_lit.grounding_policy == ActivityGroundingPolicy.PREFERENCE_GROUNDED

    walk = get_template_by_id("walk_outside")
    assert walk is not None
    assert walk.default_location == "PARK"


def test_hard_eligibility_gate_grounding():
    """Verify GOAL_REQUIRED template is rejected when no matching active goal exists."""
    template = get_template_by_id("deep_focus_project")
    sim_now = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)
    phys_state = CharacterPhysiologicalState(energy=0.80, fatigue=0.20, stress=0.20, sleep_pressure=0.20)

    # 1. No active goals -> rejected
    eligible, reason = HardEligibilityGate.evaluate(template, sim_now, phys_state, active_goals=())
    assert not eligible
    assert "GOAL_REQUIRED" in reason

    # 2. Unrelated active goal -> rejected
    unrelated_goal = LifeGoal(
        id="g-1",
        character_id="aevum",
        title="Bake cookies",
        description="Learn baking recipes",
        status=LifeGoalStatus.ACTIVE,
        importance=0.6,
        progress=0.1,
        progress_per_completion=0.1,
        created_at=sim_now,
        updated_at=sim_now,
    )
    eligible, reason = HardEligibilityGate.evaluate(template, sim_now, phys_state, active_goals=[unrelated_goal])
    assert not eligible

    # 3. Matching active goal -> eligible
    project_goal = LifeGoal(
        id="g-2",
        character_id="aevum",
        title="Develop Personal Coding Project",
        description="Build an open-source software project.",
        status=LifeGoalStatus.ACTIVE,
        importance=0.8,
        progress=0.2,
        progress_per_completion=0.1,
        created_at=sim_now,
        updated_at=sim_now,
    )
    eligible, reason = HardEligibilityGate.evaluate(template, sim_now, phys_state, active_goals=[project_goal])
    assert eligible
    assert reason is None


def test_hard_eligibility_gate_unified_sleep_threshold():
    """Patch A: sleep_pressure >= 0.50 unified hard eligibility for sleep templates."""
    template = get_template_by_id("night_sleep")
    sim_now = datetime(2026, 9, 18, 23, 0, 0, tzinfo=timezone.utc)

    # Below 0.50 -> rejected
    phys_low = CharacterPhysiologicalState(energy=0.60, fatigue=0.40, stress=0.20, sleep_pressure=0.45)
    eligible, reason = HardEligibilityGate.evaluate(template, sim_now, phys_low)
    assert not eligible
    assert "Sleep pressure 0.45 below sleep threshold 0.50" in reason

    # At or above 0.50 -> eligible
    phys_high = CharacterPhysiologicalState(energy=0.30, fatigue=0.60, stress=0.30, sleep_pressure=0.55)
    eligible, reason = HardEligibilityGate.evaluate(template, sim_now, phys_high)
    assert eligible


def test_hard_eligibility_gate_circadian_start_hours():
    """allowed_start_hours constrains start hour only; duration may cross midnight."""
    template = get_template_by_id("night_sleep")
    # allowed: (21, 22, 23, 0, 1, 2, 3, 4, 5, 6, 7)
    phys = CharacterPhysiologicalState(energy=0.20, fatigue=0.70, stress=0.20, sleep_pressure=0.80)

    # 12:00 UTC = 20:00 Asia/Kuala_Lumpur (hour 20 not in 21..7) -> rejected
    dt_daytime = datetime(2026, 9, 18, 12, 0, 0, tzinfo=timezone.utc)
    eligible, reason = HardEligibilityGate.evaluate(template, dt_daytime, phys)
    assert not eligible
    assert "outside allowed start hours" in reason

    # 15:00 UTC = 23:00 Asia/Kuala_Lumpur (hour 23 is in 21..7) -> eligible
    dt_night = datetime(2026, 9, 18, 15, 0, 0, tzinfo=timezone.utc)
    eligible, reason = HardEligibilityGate.evaluate(template, dt_night, phys)
    assert eligible


def test_deterministic_goal_tie_break():
    """GC-034-G: deterministic ranking rule based on (-effective_goal_fit, -importance, progress, id)."""
    sim_now = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)
    template = get_template_by_id("practice_instrument")

    # Goal A: importance = 0.90, progress = 0.90 -> fit = 0.90 * (1 - 0.27) = 0.657
    goal_a = LifeGoal(
        id="goal-a",
        character_id="aevum",
        title="Practice music recital",
        description="Instrument practice",
        status=LifeGoalStatus.ACTIVE,
        importance=0.90,
        progress=0.90,
        progress_per_completion=0.05,
        created_at=sim_now,
        updated_at=sim_now,
    )
    # Goal B: importance = 0.80, progress = 0.00 -> fit = 0.80 * 1.0 = 0.800
    goal_b = LifeGoal(
        id="goal-b",
        character_id="aevum",
        title="Improve music skills",
        description="Instrument practice",
        status=LifeGoalStatus.ACTIVE,
        importance=0.80,
        progress=0.00,
        progress_per_completion=0.05,
        created_at=sim_now,
        updated_at=sim_now,
    )

    phys = CharacterPhysiologicalState(energy=0.80, fatigue=0.20, stress=0.20, sleep_pressure=0.20)
    decision = ActivityUtilityEvaluator.evaluate(
        template=template,
        sim_now=sim_now,
        phys_state=phys,
        active_goals=[goal_a, goal_b],
    )

    # Goal B has higher effective_goal_fit (0.80 > 0.657) so it must win!
    assert decision.linked_goal_id == "goal-b"
    assert decision.breakdown.goal_fit == 0.80


def test_repetition_penalty():
    """Repetition penalty prevents consecutive identical activities."""
    template = get_template_by_id("practice_instrument")
    sim_now = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)
    phys = CharacterPhysiologicalState(energy=0.80, fatigue=0.20, stress=0.20, sleep_pressure=0.20)

    # Without recent activities
    d1 = ActivityUtilityEvaluator.evaluate(template, sim_now, phys, recent_activities=())
    assert d1.breakdown.repetition_penalty == 0.0

    # With same activity just completed
    recent = LifeActivity(
        id="act-1",
        character_id="aevum",
        activity_type=LifeActivityType.MUSIC,
        title=template.title,
        description=template.description,
        location="HOME",
        status=LifeActivityStatus.COMPLETED,
        started_at=sim_now - timedelta(hours=1),
        completed_at=sim_now,
        importance=0.8,
        created_at=sim_now,
    )
    d2 = ActivityUtilityEvaluator.evaluate(template, sim_now, phys, recent_activities=[recent])
    assert d2.breakdown.repetition_penalty >= 0.80
    assert d2.utility_score < d1.utility_score


@pytest.mark.asyncio
async def test_sqlite_partial_unique_index_exists(test_session):
    """Verify that the SQLite partial unique index exists in sqlite_master (Standard 27)."""
    result = await test_session.execute(
        text("SELECT sql FROM sqlite_master WHERE type = 'index' AND name = 'ix_life_activities_character_ongoing'")
    )
    row = result.first()
    assert row is not None, "Partial unique index 'ix_life_activities_character_ongoing' was not created!"
    sql = row[0].upper()
    assert "UNIQUE INDEX" in sql
    assert "WHERE STATUS = 'ONGOING'" in sql or "WHERE (STATUS = 'ONGOING')" in sql


@pytest.mark.asyncio
async def test_decision_point_gating(selector, life_service, test_session, sim_clock):
    """Invariant 24: selector returns None if an ongoing activity is active."""
    character_id = "aevum"
    await life_service.initialize_aevum_life(character_id)

    # Initially IDLE -> can select
    assert await selector.can_select(character_id) is True

    # Start an ongoing activity
    act = await life_service.create_activity(
        character_id=character_id,
        activity_type=LifeActivityType.STUDY,
        title="Active Study",
        description="Studying",
        location="HOME",
        started_at=sim_clock.now(),
    )
    await life_service.update_life_state(character_id, "Active Study", "HOME", expected_version=1)

    # Now active -> cannot select
    assert await selector.can_select(character_id) is False
    result = await selector.select_and_start_activity(character_id)
    assert result is None
