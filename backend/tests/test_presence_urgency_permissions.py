"""Tests for Presence, Life Simulation Deepening, Urgency, and Permissions (Phase E)."""

from datetime import datetime, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from zoneinfo import ZoneInfo

from app.db.session import Base
from app.core.permissions import Capability, PermissionService
from app.life.presence import PresenceState, PresenceTracker
from app.life.urgency import ProactiveCandidate, ProactiveUrgencyEngine, UrgencyEvaluation
from app.character.engine_models import (
    CharacterBehaviorContext,
    CharacterDefinitionContext,
    CharacterEmotionContext,
    CharacterMemoryContext,
    CharacterResponseContext,
    CharacterStateContext,
)
from app.character.models import (
    Boundary,
    CharacterDefinition,
    CharacterIdentity,
    Personality,
)
from app.character.prompt_assembler import ResponseContextAssembler
from app.character.state_models import CharacterMood, CharacterState
from app.emotion.emotion_models import EmotionState, EmotionType
from app.life.context_models import CharacterLifeContext
from app.relationship.context_builder import RelationshipContextBuilder
from app.relationship.models import RelationshipState


# ---------------------------------------------------------------------------
# 1. Presence Tracker & Anti-Clinginess Guidance
# ---------------------------------------------------------------------------

def test_presence_tracker_first_interaction():
    state = PresenceTracker.track_presence(last_interaction_at=None)
    assert state.absence_duration_seconds == 0.0
    assert state.absence_guidance is None


def test_presence_tracker_long_absence_anti_clingy_guidance():
    """Absence > 24 hours must generate non-clingy guidance forbidding guilt-tripping."""
    last_time = datetime(2026, 9, 15, 10, 0, tzinfo=timezone.utc)
    current_time = datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc)  # 48 hours

    state = PresenceTracker.track_presence(
        last_interaction_at=last_time,
        current_time=current_time,
        current_activity="resting",
    )

    assert state.absence_duration_seconds == 172800.0
    assert state.absence_guidance is not None
    assert "NEVER exhibit clinginess" in state.absence_guidance
    assert "guilt-tripping" in state.absence_guidance


def test_presence_tracker_activity_attention_and_timing():
    """Focused activities set FOCUSED attention and realistic simulated delay."""
    now = datetime.now(timezone.utc)

    # Piano practice
    state_focused = PresenceTracker.track_presence(
        last_interaction_at=now,
        current_time=now,
        current_activity="piano_practice",
    )
    assert state_focused.attention_level == "FOCUSED"
    assert state_focused.suggested_reply_delay_seconds > 0

    # Sleeping
    state_sleep = PresenceTracker.track_presence(
        last_interaction_at=now,
        current_time=now,
        current_activity="sleeping in bed",
    )
    assert state_sleep.attention_level == "DORMANT"
    assert state_sleep.suggested_reply_delay_seconds >= 30


# ---------------------------------------------------------------------------
# 2. Proactive Urgency Engine
# ---------------------------------------------------------------------------

def test_proactive_urgency_suppressed_when_permission_disabled():
    """If notifications capability is not granted, trigger is strictly suppressed."""
    event_time = datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc)
    candidate = ProactiveCandidate(
        id="ev-1",
        title="Finished composing an acoustic piano etude",
        importance=0.9,
        occurred_at=event_time,
    )

    eval_result = ProactiveUrgencyEngine.evaluate(
        candidate=candidate,
        current_time=event_time,
        notifications_permitted=False,
    )

    assert eval_result.should_trigger is False
    assert eval_result.suppression_reason == "PERMISSIONS_DISABLED"


def test_proactive_urgency_suppressed_during_quiet_hours():
    """Events occurring during late night (23:00-07:00 KL time) are suppressed."""
    # 23:30 in Asia/Kuala_Lumpur (UTC+8) is 15:30 UTC
    late_night_utc = datetime(2026, 9, 17, 15, 30, tzinfo=timezone.utc)
    candidate = ProactiveCandidate(
        id="ev-2",
        title="Heard an interesting bird call outside",
        importance=0.8,
        occurred_at=late_night_utc,
    )

    eval_result = ProactiveUrgencyEngine.evaluate(
        candidate=candidate,
        current_time=late_night_utc,
        notifications_permitted=True,
        timezone_name="Asia/Kuala_Lumpur",
    )

    assert eval_result.should_trigger is False
    assert eval_result.suppression_reason == "QUIET_HOURS"


def test_proactive_urgency_suppressed_during_active_cooldown():
    """Events occurring within 4 hours of previous proactive trigger are suppressed."""
    # 14:00 in KL time is 06:00 UTC (daytime)
    current_utc = datetime(2026, 9, 17, 6, 0, tzinfo=timezone.utc)
    last_proactive = datetime(2026, 9, 17, 4, 0, tzinfo=timezone.utc)  # 2 hours ago (< 4h)

    candidate = ProactiveCandidate(
        id="ev-3",
        title="Walked through the botanical gardens",
        importance=0.85,
        occurred_at=current_utc,
    )

    eval_result = ProactiveUrgencyEngine.evaluate(
        candidate=candidate,
        current_time=current_utc,
        last_proactive_at=last_proactive,
        notifications_permitted=True,
        timezone_name="Asia/Kuala_Lumpur",
    )

    assert eval_result.should_trigger is False
    assert eval_result.suppression_reason == "COOLDOWN_ACTIVE"


def test_proactive_urgency_triggers_when_conditions_met():
    """High importance event during daytime with permission and expired cooldown triggers."""
    # 14:00 in KL time is 06:00 UTC
    current_utc = datetime(2026, 9, 17, 6, 0, tzinfo=timezone.utc)
    last_proactive = datetime(2026, 9, 16, 6, 0, tzinfo=timezone.utc)  # 24 hours ago

    candidate = ProactiveCandidate(
        id="ev-4",
        title="Completed the full score for the Ravel tribute piece",
        importance=0.90,
        occurred_at=current_utc,
    )

    eval_result = ProactiveUrgencyEngine.evaluate(
        candidate=candidate,
        current_time=current_utc,
        last_proactive_at=last_proactive,
        relationship_affinity=60.0,
        notifications_permitted=True,
        timezone_name="Asia/Kuala_Lumpur",
    )

    assert eval_result.should_trigger is True
    assert eval_result.suppression_reason is None
    assert eval_result.urgency_score >= 0.60


# ---------------------------------------------------------------------------
# 3. Permission Service (Default Least Privilege & Security)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_permission_service_least_privilege_and_file_system_block():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with async_session() as session:
        perm_service = PermissionService(session)

        # Default least privilege: all ungranted capabilities return False
        assert await perm_service.is_permitted(Capability.NOTIFICATIONS) is False
        assert await perm_service.is_permitted(Capability.SCREEN_CONTEXT) is False
        assert await perm_service.is_permitted(Capability.CAMERA) is False
        assert await perm_service.is_permitted(Capability.MICROPHONE) is False

        # Rule 18 Invariant: FILE_SYSTEM is strictly non-grantable
        assert await perm_service.is_permitted(Capability.FILE_SYSTEM) is False
        with pytest.raises(ValueError) as exc:
            await perm_service.set_permission(Capability.FILE_SYSTEM, True)
        assert "strictly restricted" in str(exc.value)

        # Grant and check notifications
        await perm_service.set_permission(Capability.NOTIFICATIONS, True)
        assert await perm_service.is_permitted(Capability.NOTIFICATIONS) is True

        # Revoke notifications
        await perm_service.set_permission(Capability.NOTIFICATIONS, False)
        assert await perm_service.is_permitted(Capability.NOTIFICATIONS) is False

    await engine.dispose()


# ---------------------------------------------------------------------------
# 4. Prompt Assembler Presence Integration
# ---------------------------------------------------------------------------

def test_prompt_assembler_injects_presence_guidance():
    char_def = CharacterDefinition(
        id="aevum",
        version=1,
        updated_at=datetime.now(timezone.utc),
        identity=CharacterIdentity(name="Aevum", age=21, occupation="Student", background="Music."),
        personality=Personality(
            core_traits=["Observant"],
            social_style=["Reserved"],
            emotional_style=["Calm"],
            communication_style=["Articulate"],
            behavioral_tendencies=["Introspective"],
            flaws=["Hesitant"],
        ),
    )
    state = CharacterState(
        id="aevum",
        version=1,
        updated_at=datetime.now(timezone.utc),
        mood=CharacterMood.CALM,
        energy=0.8,
        stress=0.2,
        social_energy=0.7,
        confidence=0.8,
        irritation=0.0,
        loneliness=0.1,
        current_activity="Reading",
        current_location="Home",
    )
    emo_state = EmotionState(
        id="emo-1",
        emotion_type=EmotionType.CALM,
        intensity=0.5,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    rel_state = RelationshipState(
        id="user",
        user_id="user",
        version=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    presence = PresenceState(
        current_time=datetime.now(timezone.utc),
        absence_duration_seconds=172800.0,
        absence_guidance="User has returned after 48 hours. Never exhibit clinginess or guilt-tripping.",
    )

    context = CharacterResponseContext(
        user_input="I'm back!",
        character=CharacterDefinitionContext.from_definition(char_def),
        character_state=CharacterStateContext.from_state(state),
        relationship=RelationshipContextBuilder.build(rel_state),
        emotion=CharacterEmotionContext.from_state(emo_state),
        memory=CharacterMemoryContext.from_memories(()),
        behavior=CharacterBehaviorContext.synthesize(
            CharacterStateContext.from_state(state),
            CharacterEmotionContext.from_state(emo_state),
        ),
        life=CharacterLifeContext(
            current_activity_summary="Resting",
            current_location_summary="Home",
            recent_experience_summary=(),
            life_guidance=("Currently resting.",),
        ),
        presence=presence,
    )

    llm_context = ResponseContextAssembler.assemble(context)
    system_text = "\n".join(llm_context.system_instructions)

    assert "<presence_guidance>" in system_text
    assert "User has returned after 48 hours" in system_text
    assert "</presence_guidance>" in system_text
