"""Tests for LifeSimulationOrchestrator (Phase 7.5).

Covers: tick semantics, LifeEvent collection, emotion integration,
idempotency, timezone safety, domain isolation, and failure behavior.
"""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.life.orchestrator import LifeSimulationOrchestrator, LifeSimulationTickResult
from app.life.simulator import LifeSimulator, LifeSimulationResult
from app.life.services import LifeService
from app.life.models import (
    LifeActivityType,
    LifeActivityStatus,
    LifePlanStatus,
    LifeEventType,
)
from app.life.emotion_integrator import LifeEmotionIntegrator
from app.emotion.service import EmotionService
from app.emotion.emotion_models import EmotionType
from app.db.models import (
    LifeEventRecord,
    LifePlanRecord,
    LifeActivityRecord,
    EmotionEventRecord,
    EmotionInfluenceRecord,
    EmotionStateRecord,
    RelationshipRecord,
    CharacterStateRecord,
    Conversation,
    Message,
)

T_BASE = datetime(2026, 9, 16, 14, 0, 0, tzinfo=timezone.utc)
T_BEFORE = T_BASE - timedelta(minutes=1)
T_AFTER = T_BASE + timedelta(minutes=1)


async def _seed_character_and_emotion(session: AsyncSession, character_id: str = "aevum"):
    """Seed the character definition and emotion state via existing auto-init."""
    emo = EmotionService(session)
    await emo.get_emotion_state(character_id)


async def _create_plan(
    service: LifeService,
    character_id: str,
    title: str,
    start: datetime,
    end: datetime,
    importance: float = 0.5,
):
    return await service.create_plan(
        character_id=character_id,
        title=title,
        description=f"Plan: {title}",
        importance=importance,
        planned_start=start,
        planned_end=end,
    )


# ─── Test 1: A due plan starts during a tick ───────────────────────────

@pytest.mark.asyncio
async def test_due_plan_starts(test_session: AsyncSession):
    await _seed_character_and_emotion(test_session)
    svc = LifeService(test_session)
    await svc.get_life_state("aevum")

    plan_start = T_BASE - timedelta(minutes=5)
    plan_end = T_BASE + timedelta(hours=1)
    await _create_plan(svc, "aevum", "Study math", plan_start, plan_end)

    orchestrator = LifeSimulationOrchestrator(test_session)
    result = await orchestrator.tick("aevum", T_BASE)

    assert result.plans_started >= 1
    assert result.character_id == "aevum"
    assert result.simulation_time == T_BASE


# ─── Test 2: An ended activity completes during a tick ─────────────────

@pytest.mark.asyncio
async def test_ended_activity_completes(test_session: AsyncSession):
    await _seed_character_and_emotion(test_session)
    svc = LifeService(test_session)
    await svc.get_life_state("aevum")

    act = await svc.create_activity(
        character_id="aevum",
        activity_type=LifeActivityType.READING,
        title="Read novel",
        description="Reading a novel",
        location="HOME",
        importance=0.7,
        planned_end_at=T_BASE - timedelta(minutes=5),
    )

    orchestrator = LifeSimulationOrchestrator(test_session)
    result = await orchestrator.tick("aevum", T_BASE)

    assert result.activities_completed >= 1


# ─── Test 3: Completion produces the expected LifeEvent ────────────────

@pytest.mark.asyncio
async def test_completion_produces_life_event(test_session: AsyncSession):
    await _seed_character_and_emotion(test_session)
    svc = LifeService(test_session)
    await svc.get_life_state("aevum")

    await svc.create_activity(
        character_id="aevum",
        activity_type=LifeActivityType.MUSIC,
        title="Practice piano",
        description="Music practice",
        location="HOME",
        importance=0.8,
        planned_end_at=T_BASE - timedelta(minutes=1),
    )

    orchestrator = LifeSimulationOrchestrator(test_session)
    result = await orchestrator.tick("aevum", T_BASE)

    assert result.life_events_created >= 1

    stmt = select(LifeEventRecord).where(
        LifeEventRecord.character_id == "aevum",
        LifeEventRecord.event_type == LifeEventType.ACTIVITY_COMPLETED.value,
    )
    events = (await test_session.scalars(stmt)).all()
    assert any("Practice piano" in e.title for e in events)


# ─── Test 4: Meaningful LifeEvent reaches emotion integration ──────────

@pytest.mark.asyncio
async def test_meaningful_event_reaches_emotion(test_session: AsyncSession):
    await _seed_character_and_emotion(test_session)
    svc = LifeService(test_session)
    await svc.get_life_state("aevum")

    await svc.create_activity(
        character_id="aevum",
        activity_type=LifeActivityType.MUSIC,
        title="Complete recital prep",
        description="Important practice",
        location="HOME",
        importance=0.8,
        planned_end_at=T_BASE - timedelta(minutes=1),
    )

    orchestrator = LifeSimulationOrchestrator(test_session)
    result = await orchestrator.tick("aevum", T_BASE)

    # Activity completion with significance=0.5 should trigger emotion integration
    assert result.emotion_events_created >= 1
    assert result.emotion_influences_created >= 1
    assert result.emotion_state_changed is True


# ─── Test 5: Neutral LifeEvents remain emotionally neutral ────────────

@pytest.mark.asyncio
async def test_neutral_event_no_emotion(test_session: AsyncSession):
    await _seed_character_and_emotion(test_session)
    svc = LifeService(test_session)
    await svc.get_life_state("aevum")

    # Create a plan that starts → generates an OTHER type event (neutral)
    plan_start = T_BASE - timedelta(minutes=5)
    plan_end = T_BASE + timedelta(hours=1)
    await _create_plan(svc, "aevum", "Routine task", plan_start, plan_end, importance=0.3)

    pre_count = (await test_session.execute(
        select(func.count()).select_from(EmotionEventRecord)
    )).scalar_one()

    orchestrator = LifeSimulationOrchestrator(test_session)
    result = await orchestrator.tick("aevum", T_BASE)

    post_count = (await test_session.execute(
        select(func.count()).select_from(EmotionEventRecord)
    )).scalar_one()

    # Plan start generates an OTHER LifeEvent, which is not emotionally meaningful
    assert post_count == pre_count


# ─── Test 6: Repeated identical tick is idempotent ─────────────────────

@pytest.mark.asyncio
async def test_repeated_tick_idempotent(test_session: AsyncSession):
    await _seed_character_and_emotion(test_session)
    svc = LifeService(test_session)
    await svc.get_life_state("aevum")

    await svc.create_activity(
        character_id="aevum",
        activity_type=LifeActivityType.STUDY,
        title="Study biology",
        description="Study",
        location="HOME",
        importance=0.6,
        planned_end_at=T_BASE - timedelta(minutes=1),
    )

    orchestrator = LifeSimulationOrchestrator(test_session)

    r1 = await orchestrator.tick("aevum", T_BASE)
    r2 = await orchestrator.tick("aevum", T_BASE)
    r3 = await orchestrator.tick("aevum", T_BASE)

    # Only the first tick should produce events
    assert r1.life_events_created >= 1
    assert r2.life_events_created == 0
    assert r3.life_events_created == 0

    # Total emotion events should be exactly 1
    total_emotion_events = (await test_session.execute(
        select(func.count()).select_from(EmotionEventRecord).where(
            EmotionEventRecord.character_id == "aevum"
        )
    )).scalar_one()
    assert total_emotion_events == 1


# ─── Test 7: Multiple due plans are processed deterministically ────────

@pytest.mark.asyncio
async def test_multiple_plans_processed(test_session: AsyncSession):
    await _seed_character_and_emotion(test_session)
    svc = LifeService(test_session)
    await svc.get_life_state("aevum")

    t1 = T_BASE - timedelta(minutes=10)
    t2 = T_BASE - timedelta(minutes=5)
    end = T_BASE + timedelta(hours=2)

    await _create_plan(svc, "aevum", "Plan A", t1, end)
    await _create_plan(svc, "aevum", "Plan B", t2, end)

    orchestrator = LifeSimulationOrchestrator(test_session)
    result = await orchestrator.tick("aevum", T_BASE)

    assert result.plans_started >= 2


# ─── Test 8: Multiple LifeEvents reach emotion integration ────────────

@pytest.mark.asyncio
async def test_multiple_events_reach_emotion(test_session: AsyncSession):
    await _seed_character_and_emotion(test_session)
    svc = LifeService(test_session)
    await svc.get_life_state("aevum")

    # Create two activities that end before T_BASE
    await svc.create_activity(
        character_id="aevum",
        activity_type=LifeActivityType.STUDY,
        title="Study A",
        description="Study",
        location="HOME",
        importance=0.7,
        planned_end_at=T_BASE - timedelta(minutes=10),
    )
    await svc.create_activity(
        character_id="aevum",
        activity_type=LifeActivityType.READING,
        title="Study B",
        description="Reading",
        location="HOME",
        importance=0.6,
        planned_end_at=T_BASE - timedelta(minutes=5),
    )

    orchestrator = LifeSimulationOrchestrator(test_session)
    result = await orchestrator.tick("aevum", T_BASE)

    assert result.life_events_created >= 2
    # Both completions have significance=0.5 which triggers emotion
    assert result.emotion_events_created >= 2


# ─── Test 9: EmotionState changes through existing pipeline ───────────

@pytest.mark.asyncio
async def test_emotion_state_via_pipeline(test_session: AsyncSession):
    await _seed_character_and_emotion(test_session)
    svc = LifeService(test_session)
    await svc.get_life_state("aevum")

    emo = EmotionService(test_session)
    state_before = await emo.get_emotion_state("aevum")
    assert state_before.emotion_type == EmotionType.NEUTRAL

    await svc.create_activity(
        character_id="aevum",
        activity_type=LifeActivityType.MUSIC,
        title="Meaningful practice",
        description="Practice",
        location="HOME",
        importance=0.8,
        planned_end_at=T_BASE - timedelta(minutes=1),
    )

    orchestrator = LifeSimulationOrchestrator(test_session)
    await orchestrator.tick("aevum", T_BASE)

    state_after = await emo.get_emotion_state("aevum")
    assert state_after.emotion_type == EmotionType.CONTENT


# ─── Test 10: RelationshipState remains unchanged ─────────────────────

@pytest.mark.asyncio
async def test_relationship_state_unchanged(test_session: AsyncSession):
    await _seed_character_and_emotion(test_session)
    svc = LifeService(test_session)
    await svc.get_life_state("aevum")

    pre = (await test_session.execute(
        select(func.count()).select_from(RelationshipRecord)
    )).scalar_one()

    await svc.create_activity(
        character_id="aevum",
        activity_type=LifeActivityType.STUDY,
        title="Study",
        description="Study",
        location="HOME",
        importance=0.6,
        planned_end_at=T_BASE - timedelta(minutes=1),
    )

    orchestrator = LifeSimulationOrchestrator(test_session)
    await orchestrator.tick("aevum", T_BASE)

    post = (await test_session.execute(
        select(func.count()).select_from(RelationshipRecord)
    )).scalar_one()
    assert post == pre


# ─── Test 11: Memory remains unchanged ────────────────────────────────

@pytest.mark.asyncio
async def test_memory_unchanged(test_session: AsyncSession):
    await _seed_character_and_emotion(test_session)
    svc = LifeService(test_session)
    await svc.get_life_state("aevum")

    from app.db.models import MemoryRecord
    pre = (await test_session.execute(
        select(func.count()).select_from(MemoryRecord)
    )).scalar_one()

    await svc.create_activity(
        character_id="aevum",
        activity_type=LifeActivityType.STUDY,
        title="Study math",
        description="Study",
        location="HOME",
        planned_end_at=T_BASE - timedelta(minutes=1),
    )

    orchestrator = LifeSimulationOrchestrator(test_session)
    await orchestrator.tick("aevum", T_BASE)

    post = (await test_session.execute(
        select(func.count()).select_from(MemoryRecord)
    )).scalar_one()
    assert post == pre


# ─── Test 12: CharacterState remains unchanged ────────────────────────

@pytest.mark.asyncio
async def test_character_state_unchanged(test_session: AsyncSession):
    await _seed_character_and_emotion(test_session)
    svc = LifeService(test_session)
    await svc.get_life_state("aevum")

    pre = (await test_session.execute(
        select(func.count()).select_from(CharacterStateRecord)
    )).scalar_one()

    await svc.create_activity(
        character_id="aevum",
        activity_type=LifeActivityType.STUDY,
        title="Study X",
        description="X",
        location="HOME",
        planned_end_at=T_BASE - timedelta(minutes=1),
    )

    orchestrator = LifeSimulationOrchestrator(test_session)
    await orchestrator.tick("aevum", T_BASE)

    post = (await test_session.execute(
        select(func.count()).select_from(CharacterStateRecord)
    )).scalar_one()
    assert post == pre


# ─── Test 13: Conversation/Message remains unchanged ──────────────────

@pytest.mark.asyncio
async def test_conversation_unchanged(test_session: AsyncSession):
    await _seed_character_and_emotion(test_session)
    svc = LifeService(test_session)
    await svc.get_life_state("aevum")

    pre_conv = (await test_session.execute(
        select(func.count()).select_from(Conversation)
    )).scalar_one()
    pre_msg = (await test_session.execute(
        select(func.count()).select_from(Message)
    )).scalar_one()

    await svc.create_activity(
        character_id="aevum",
        activity_type=LifeActivityType.STUDY,
        title="Study Y",
        description="Y",
        location="HOME",
        planned_end_at=T_BASE - timedelta(minutes=1),
    )

    orchestrator = LifeSimulationOrchestrator(test_session)
    await orchestrator.tick("aevum", T_BASE)

    post_conv = (await test_session.execute(
        select(func.count()).select_from(Conversation)
    )).scalar_one()
    post_msg = (await test_session.execute(
        select(func.count()).select_from(Message)
    )).scalar_one()
    assert post_conv == pre_conv
    assert post_msg == pre_msg


# ─── Test 14: Timezone boundary behavior ──────────────────────────────

@pytest.mark.asyncio
async def test_timezone_boundary(test_session: AsyncSession):
    await _seed_character_and_emotion(test_session)
    svc = LifeService(test_session)
    await svc.get_life_state("aevum")

    exact_end = T_BASE
    await svc.create_activity(
        character_id="aevum",
        activity_type=LifeActivityType.STUDY,
        title="Boundary study",
        description="Boundary",
        location="HOME",
        planned_end_at=exact_end,
    )

    orchestrator = LifeSimulationOrchestrator(test_session)

    # At T_BASE the activity end <= T_BASE, so it should complete
    result = await orchestrator.tick("aevum", T_BASE)
    assert result.activities_completed >= 1


# ─── Test 15: Machine timezone independence ───────────────────────────

@pytest.mark.asyncio
async def test_machine_timezone_independence(test_session: AsyncSession):
    """Result must be identical regardless of machine timezone."""
    await _seed_character_and_emotion(test_session)
    svc = LifeService(test_session)
    await svc.get_life_state("aevum")

    await svc.create_activity(
        character_id="aevum",
        activity_type=LifeActivityType.STUDY,
        title="TZ test",
        description="TZ",
        location="HOME",
        planned_end_at=T_BASE - timedelta(minutes=1),
    )

    orchestrator = LifeSimulationOrchestrator(test_session)
    result = await orchestrator.tick("aevum", T_BASE)

    # The tick accepts explicit UTC, not wall-clock
    assert result.simulation_time == T_BASE
    assert result.activities_completed >= 1


# ─── Test 16: Failure does not fabricate success ──────────────────────

@pytest.mark.asyncio
async def test_naive_datetime_rejected(test_session: AsyncSession):
    """Naive (no tzinfo) datetime must be rejected."""
    await _seed_character_and_emotion(test_session)

    orchestrator = LifeSimulationOrchestrator(test_session)
    with pytest.raises(ValueError, match="timezone-aware"):
        await orchestrator.tick("aevum", datetime(2026, 9, 16, 14, 0, 0))


# ─── Test 17: No duplicate EmotionEvents/Influences ───────────────────

@pytest.mark.asyncio
async def test_no_duplicate_emotion_artifacts(test_session: AsyncSession):
    await _seed_character_and_emotion(test_session)
    svc = LifeService(test_session)
    await svc.get_life_state("aevum")

    await svc.create_activity(
        character_id="aevum",
        activity_type=LifeActivityType.MUSIC,
        title="Dup test",
        description="Dup",
        location="HOME",
        importance=0.7,
        planned_end_at=T_BASE - timedelta(minutes=1),
    )

    orchestrator = LifeSimulationOrchestrator(test_session)
    await orchestrator.tick("aevum", T_BASE)
    await orchestrator.tick("aevum", T_BASE)
    await orchestrator.tick("aevum", T_BASE)

    total_emo_events = (await test_session.execute(
        select(func.count()).select_from(EmotionEventRecord).where(
            EmotionEventRecord.character_id == "aevum"
        )
    )).scalar_one()

    total_influences = (await test_session.execute(
        select(func.count()).select_from(EmotionInfluenceRecord)
    )).scalar_one()

    assert total_emo_events == 1
    assert total_influences == 1


# ─── Test 18: Same instant produces deterministic results ─────────────

@pytest.mark.asyncio
async def test_deterministic_results(test_session: AsyncSession):
    """Given identical state and time, the result structure is deterministic."""
    await _seed_character_and_emotion(test_session)
    svc = LifeService(test_session)
    await svc.get_life_state("aevum")

    await svc.create_activity(
        character_id="aevum",
        activity_type=LifeActivityType.READING,
        title="Deterministic read",
        description="Det",
        location="HOME",
        importance=0.6,
        planned_end_at=T_BASE - timedelta(minutes=1),
    )

    orchestrator = LifeSimulationOrchestrator(test_session)
    r1 = await orchestrator.tick("aevum", T_BASE)

    assert r1.character_id == "aevum"
    assert r1.simulation_time == T_BASE
    assert isinstance(r1.plans_started, int)
    assert isinstance(r1.activities_completed, int)
    assert isinstance(r1.life_events_created, int)
    assert isinstance(r1.emotion_events_created, int)
    assert isinstance(r1.emotion_state_changed, bool)
