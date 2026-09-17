"""Unit tests for Phase 6.1 — Character Engine Foundation.

Verifies:
- CharacterResponseContext domain models and strict immutability.
- CharacterEngine orchestration across CharacterDefinition, CharacterState,
  RelationshipState, EmotionState, and Memory retrieval.
- Correct user input propagation.
- Structured semantic contexts (character, state, relationship, emotion, memory)
  without raw persistence/ORM leakage.
- Empty/no-memory handling.
- Deterministic context generation.
- No mutation of source domain objects.
- Strict isolation: zero LLM calls, zero network calls, zero database writes,
  and zero side-effects across domains.
- Explicit failure on missing or invalid required domain state.
"""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.engine import CharacterEngine
from app.life.context_models import CharacterLifeContext
from app.life.models import LifeState
from app.character.engine_models import (
    CharacterBehaviorContext,
    CharacterDefinitionContext,
    CharacterEmotionContext,
    CharacterMemoryContext,
    CharacterResponseContext,
    CharacterStateContext,
    MemoryExperienceContext,
    format_emotion_summary,
)
from app.character.models import (
    Boundary,
    CharacterDefinition,
    CharacterIdentity,
    Personality,
    Preference,
    PreferenceSentiment,
)
from app.character.service import (
    CharacterDefinitionService,
    create_initial_aevum_definition,
)
from app.character.state_models import CharacterMood, CharacterState
from app.character.state_service import (
    CharacterStateService,
    create_initial_aevum_state,
)
from app.db.models import (
    CharacterDefinitionRecord,
    CharacterStateRecord,
    Conversation,
    EmotionEventRecord,
    EmotionInfluenceRecord,
    EmotionStateRecord,
    MemoryRecord,
    RelationshipExperienceRecord,
    RelationshipRecord,
)
from app.emotion.emotion_models import EmotionState, EmotionType, create_initial_emotion_state
from app.emotion.service import EmotionService
from app.memory.models import HybridMemoryResult, Memory, MemoryCategory
from app.relationship.context_builder import RelationshipContextBuilder
from app.relationship.context_models import RelationshipContext
from app.relationship.models import RelationshipState
from app.relationship.service import RelationshipService, create_initial_relationship_state


def _create_test_character_definition() -> CharacterDefinition:
    """Helper to construct a valid CharacterDefinition for hermetic unit tests."""
    now = datetime.now(timezone.utc)
    return CharacterDefinition(
        id="aevum",
        version=1,
        updated_at=now,
        identity=CharacterIdentity(
            name="Aevum",
            age=21,
            occupation="Researcher & Companion",
            background="A contemplative digital life form existing in persistent temporal flow.",
        ),
        personality=Personality(
            core_traits=("thoughtful", "observant", "measured"),
            social_style=("gentle", "respectful", "patient"),
            emotional_style=("introspective", "steady"),
            communication_style=("articulate", "warm", "clear"),
            behavioral_tendencies=("reflects before acting", "values honesty"),
            flaws=("can overthink", "occasionally hesitant"),
        ),
        preferences=(
            Preference(category="beverages", item="tea", sentiment=PreferenceSentiment.LIKE),
            Preference(category="noise", item="loud crowds", sentiment=PreferenceSentiment.DISLIKE),
        ),
        boundaries=(
            Boundary(description="Does not engage in romantic affection or flirtation."),
            Boundary(description="Maintains personal agency and values honest inquiry."),
        ),
    )


def _create_test_character_state() -> CharacterState:
    """Helper to construct a valid CharacterState for tests."""
    now = datetime.now(timezone.utc)
    return CharacterState(
        id="aevum",
        version=1,
        updated_at=now,
        mood=CharacterMood.CALM,
        energy=0.75,
        stress=0.20,
        social_energy=0.80,
        confidence=0.85,
        irritation=0.05,
        loneliness=0.15,
        current_activity="reading in the study",
        current_location="study",
    )


def _create_test_relationship_state() -> RelationshipState:
    """Helper to construct a valid RelationshipState for tests."""
    now = datetime.now(timezone.utc)
    return RelationshipState(
        id="default",
        user_id="user",
        version=1,
        created_at=now,
        updated_at=now,
        familiarity=0.35,
        trust=0.45,
        comfort=0.50,
        affection=0.00,
        attachment=0.10,
        respect=0.70,
    )


def _create_test_emotion_state() -> EmotionState:
    """Helper to construct a valid EmotionState for tests."""
    now = datetime.now(timezone.utc)
    return EmotionState(
        id="emotion-1",
        character_id="aevum",
        emotion_type=EmotionType.CURIOUS,
        intensity=0.65,
        created_at=now,
        updated_at=now,
        version=1,
    )


# ---------------------------------------------------------------------------
# 1. Model Validation & Immutability Tests
# ---------------------------------------------------------------------------

def test_character_response_context_creation() -> None:
    """CharacterResponseContext initializes cleanly with all sub-contexts."""
    char_def = _create_test_character_definition()
    char_state = _create_test_character_state()
    rel_state = _create_test_relationship_state()
    emo_state = _create_test_emotion_state()

    ctx = CharacterResponseContext(
        user_input="Tell me about your thoughts on time.",
        character=CharacterDefinitionContext.from_definition(char_def),
        character_state=CharacterStateContext.from_state(char_state),
        relationship=RelationshipContextBuilder.build(rel_state),
        emotion=CharacterEmotionContext.from_state(emo_state),
        memory=CharacterMemoryContext.from_memories([]),
        behavior=CharacterBehaviorContext.synthesize(
            CharacterStateContext.from_state(char_state),
            CharacterEmotionContext.from_state(emo_state),
        ),
        life=CharacterLifeContext(current_location_summary='Aevum is currently at: HOME.', current_activity_summary='Aevum is currently resting.', recent_experience_summary=(), life_guidance=('You are resting.',)),
    )

    assert ctx.user_input == "Tell me about your thoughts on time."
    assert ctx.character.name == "Aevum"
    assert ctx.character.personality.core_traits == ("thoughtful", "observant", "measured")
    assert ctx.character_state.mood == CharacterMood.CALM
    assert ctx.character_state.current_activity == "reading in the study"
    assert ctx.emotion.emotion_type == EmotionType.CURIOUS
    assert ctx.emotion.intensity == 0.65
    assert ctx.memory.memories == ()
    assert ctx.memory.context_block is None


def test_character_response_context_immutability() -> None:
    """CharacterResponseContext is frozen and rejects in-place field mutation."""
    char_def = _create_test_character_definition()
    char_state = _create_test_character_state()
    rel_state = _create_test_relationship_state()
    emo_state = _create_test_emotion_state()

    ctx = CharacterResponseContext(
        user_input="Hello",
        character=CharacterDefinitionContext.from_definition(char_def),
        character_state=CharacterStateContext.from_state(char_state),
        relationship=RelationshipContextBuilder.build(rel_state),
        emotion=CharacterEmotionContext.from_state(emo_state),
        memory=CharacterMemoryContext.from_memories([]),
        behavior=CharacterBehaviorContext.synthesize(
            CharacterStateContext.from_state(char_state),
            CharacterEmotionContext.from_state(emo_state),
        ),
        life=CharacterLifeContext(current_location_summary='Aevum is currently at: HOME.', current_activity_summary='Aevum is currently resting.', recent_experience_summary=(), life_guidance=('You are resting.',)),
    )

    with pytest.raises(ValidationError):
        ctx.user_input = "Different input"  # type: ignore[misc]


def test_character_response_context_extra_fields_rejected() -> None:
    """Extra fields are forbidden in CharacterResponseContext."""
    char_def = _create_test_character_definition()
    char_state = _create_test_character_state()
    rel_state = _create_test_relationship_state()
    emo_state = _create_test_emotion_state()

    with pytest.raises(ValidationError):
        CharacterResponseContext(
            user_input="Hello",
            character=CharacterDefinitionContext.from_definition(char_def),
            character_state=CharacterStateContext.from_state(char_state),
            relationship=RelationshipContextBuilder.build(rel_state),
            emotion=CharacterEmotionContext.from_state(emo_state),
            memory=CharacterMemoryContext.from_memories([]),
            behavior=CharacterBehaviorContext.synthesize(
                CharacterStateContext.from_state(char_state),
                CharacterEmotionContext.from_state(emo_state),
            ),
            extra_field="disallowed",  # type: ignore[call-arg]
        )


def test_emotion_summary_formatting() -> None:
    """Emotion summary formats concise descriptor across intensity ranges."""
    mild = format_emotion_summary(EmotionType.HAPPY, 0.20)
    assert "mild" in mild
    assert "happy" in mild
    assert "0.20" in mild

    moderate = format_emotion_summary(EmotionType.CALM, 0.50)
    assert "moderate" in moderate
    assert "calm" in moderate
    assert "0.50" in moderate

    strong = format_emotion_summary(EmotionType.EXCITED, 0.85)
    assert "strong" in strong
    assert "excited" in strong
    assert "0.85" in strong


# ---------------------------------------------------------------------------
# 2. CharacterEngine Pure/Pre-loaded Execution Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_response_context_preloaded_states() -> None:
    """Engine gathers pre-loaded domain states deterministically without database queries."""
    engine = CharacterEngine(session=None)

    char_def = _create_test_character_definition()
    char_state = _create_test_character_state()
    rel_state = _create_test_relationship_state()
    emo_state = _create_test_emotion_state()

    mem1 = Memory(
        id="mem-1",
        category=MemoryCategory.FACT,
        content="User enjoys green tea in the morning.",
        confidence=0.90,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        last_recalled=None,
    )

    ctx = await engine.build_response_context(
        user_input="Do you have any tea recommendations?",
        character_definition=char_def,
        character_state=char_state,
        relationship_state=rel_state,
        emotion_state=emo_state,
        memories=[mem1],
        life_state=LifeState(id='aevum', character_id='aevum', current_activity='REST', current_location='HOME', status='ACTIVE', version=1, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)),
        recent_events=[]
    )

    # 1. User input
    assert ctx.user_input == "Do you have any tea recommendations?"

    # 2. Character definition context
    assert ctx.character.name == "Aevum"
    assert ctx.character.identity.age == 21
    assert len(ctx.character.preferences) == 2
    assert len(ctx.character.boundaries) == 2

    # 3. Character state context
    assert ctx.character_state.mood == CharacterMood.CALM
    assert ctx.character_state.energy == 0.75
    assert ctx.character_state.current_location == "study"

    # 4. Relationship context
    assert ctx.relationship.familiarity_summary is not None
    assert ctx.relationship.trust_summary is not None
    assert "romantic" not in ctx.relationship.relationship_summary.lower()

    # 5. Emotion context
    assert ctx.emotion.emotion_type == EmotionType.CURIOUS
    assert ctx.emotion.intensity == 0.65
    assert "curious" in ctx.emotion.summary.lower()

    # 6. Memory context
    assert len(ctx.memory.memories) == 1
    assert ctx.memory.memories[0] == "User enjoys green tea in the morning."
    assert ctx.memory.context_block is not None
    assert "<relevant_memories" in ctx.memory.context_block


@pytest.mark.asyncio
async def test_build_response_context_empty_memory_case() -> None:
    """Empty memories sequence is handled cleanly without errors."""
    engine = CharacterEngine(session=None)

    char_def = _create_test_character_definition()
    char_state = _create_test_character_state()
    rel_state = _create_test_relationship_state()
    emo_state = _create_test_emotion_state()

    ctx = await engine.build_response_context(
        user_input="Hello Aevum",
        character_definition=char_def,
        character_state=char_state,
        relationship_state=rel_state,
        emotion_state=emo_state,
        memories=[],
        life_state=LifeState(id='aevum', character_id='aevum', current_activity='REST', current_location='HOME', status='ACTIVE', version=1, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)),
        recent_events=[]
    )

    assert ctx.memory.memories == ()
    assert ctx.memory.context_block is None


@pytest.mark.asyncio
async def test_engine_determinism() -> None:
    """Repeated calls with identical inputs produce identical contexts."""
    engine = CharacterEngine(session=None)

    char_def = _create_test_character_definition()
    char_state = _create_test_character_state()
    rel_state = _create_test_relationship_state()
    emo_state = _create_test_emotion_state()

    ctx1 = await engine.build_response_context(
        user_input="How are you feeling?",
        character_definition=char_def,
        character_state=char_state,
        relationship_state=rel_state,
        emotion_state=emo_state,
        memories=[],
        life_state=LifeState(id='aevum', character_id='aevum', current_activity='REST', current_location='HOME', status='ACTIVE', version=1, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)),
        recent_events=[]
    )

    ctx2 = await engine.build_response_context(
        user_input="How are you feeling?",
        character_definition=char_def,
        character_state=char_state,
        relationship_state=rel_state,
        emotion_state=emo_state,
        memories=[],
        life_state=LifeState(id='aevum', character_id='aevum', current_activity='REST', current_location='HOME', status='ACTIVE', version=1, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)),
        recent_events=[]
    )

    assert ctx1 == ctx2


@pytest.mark.asyncio
async def test_input_immutability() -> None:
    """Engine does not mutate the source domain objects passed to it."""
    engine = CharacterEngine(session=None)

    char_def = _create_test_character_definition()
    char_state = _create_test_character_state()
    rel_state = _create_test_relationship_state()
    emo_state = _create_test_emotion_state()

    orig_energy = char_state.energy
    orig_trust = rel_state.trust
    orig_intensity = emo_state.intensity

    await engine.build_response_context(
        user_input="Testing immutability",
        character_definition=char_def,
        character_state=char_state,
        relationship_state=rel_state,
        emotion_state=emo_state,
        memories=[],
        life_state=LifeState(id='aevum', character_id='aevum', current_activity='REST', current_location='HOME', status='ACTIVE', version=1, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)),
        recent_events=[]
    )

    assert char_state.energy == orig_energy
    assert rel_state.trust == orig_trust
    assert emo_state.intensity == orig_intensity


# ---------------------------------------------------------------------------
# 3. Database-Integrated Orchestration Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_response_context_loads_from_database(test_session: AsyncSession) -> None:
    """Engine loads authoritative states from database session when not pre-loaded."""
    # Ensure baseline definitions and states exist
    char_def_service = CharacterDefinitionService(test_session)
    await char_def_service.get_character("aevum")

    char_state_service = CharacterStateService(test_session)
    await char_state_service.get_state("aevum")

    rel_service = RelationshipService(test_session)
    await rel_service.get_relationship_state(relationship_id="user")

    emotion_service = EmotionService(test_session)
    await emotion_service.get_emotion_state("aevum")

    engine = CharacterEngine(session=test_session, embedding_provider=None)

    ctx = await engine.build_response_context(
        user_input="Good morning, Aevum.",
        character_id="aevum",
        user_id="user",
    )

    assert ctx.user_input == "Good morning, Aevum."
    assert ctx.character.name == "Aevum"
    assert ctx.character_state.mood is not None
    assert ctx.relationship.familiarity_summary is not None
    assert ctx.emotion.emotion_type == EmotionType.NEUTRAL
    assert ctx.emotion.intensity == 0.50
    assert ctx.personal_world is not None
    assert len(ctx.personal_world.world_facts) > 0
    assert len(ctx.personal_world.epistemic_directives) > 0


# ---------------------------------------------------------------------------
# 4. Error Handling & Validation Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("invalid_input", ["", "   ", "\n\t"])
@pytest.mark.asyncio
async def test_empty_user_input_raises_value_error(invalid_input: str) -> None:
    """Empty or whitespace user_input raises ValueError immediately."""
    engine = CharacterEngine(session=None)
    with pytest.raises(ValueError, match="user_input must not be empty"):
        await engine.build_response_context(
            user_input=invalid_input,
            character_definition=_create_test_character_definition(),
            character_state=_create_test_character_state(),
            relationship_state=_create_test_relationship_state(),
            emotion_state=_create_test_emotion_state(),
        )


@pytest.mark.asyncio
async def test_missing_state_without_session_raises_runtime_error() -> None:
    """Attempting to load state without preloaded objects and without session raises RuntimeError."""
    engine = CharacterEngine(session=None)
    with pytest.raises(RuntimeError, match="Cannot load character_definition without a database session"):
        await engine.build_response_context(
            user_input="Hello",
            character_definition=None,
        )


# ---------------------------------------------------------------------------
# 5. Isolation & Side-Effect Boundary Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_side_effect_boundary(test_session: AsyncSession) -> None:
    """Building response context does not mutate DB or create events/experiences/messages."""
    # Seed baselines
    await CharacterDefinitionService(test_session).get_character("aevum")
    await CharacterStateService(test_session).get_state("aevum")
    await RelationshipService(test_session).get_relationship_state("user")
    await EmotionService(test_session).get_emotion_state("aevum")

    # Initial counts
    events_before = (await test_session.scalars(select(func.count(EmotionEventRecord.id)))).one()
    influences_before = (await test_session.scalars(select(func.count(EmotionInfluenceRecord.id)))).one()
    experiences_before = (await test_session.scalars(select(func.count(RelationshipExperienceRecord.id)))).one()
    conversations_before = (await test_session.scalars(select(func.count(Conversation.id)))).one()
    memories_before = (await test_session.scalars(select(func.count(MemoryRecord.id)))).one()

    engine = CharacterEngine(session=test_session)
    await engine.build_response_context(user_input="Are there any side effects?")

    # Post counts
    events_after = (await test_session.scalars(select(func.count(EmotionEventRecord.id)))).one()
    influences_after = (await test_session.scalars(select(func.count(EmotionInfluenceRecord.id)))).one()
    experiences_after = (await test_session.scalars(select(func.count(RelationshipExperienceRecord.id)))).one()
    conversations_after = (await test_session.scalars(select(func.count(Conversation.id)))).one()
    memories_after = (await test_session.scalars(select(func.count(MemoryRecord.id)))).one()

    assert events_before == events_after
    assert influences_before == influences_after
    assert experiences_before == experiences_after
    assert conversations_before == conversations_after
    assert memories_before == memories_after


def test_memory_experience_synthesis_confidence() -> None:
    """Memory experience synthesizes confidence guidance."""
    mem_low = Memory(
        id="mem-1", category=MemoryCategory.FACT, content="Low confidence.",
        confidence=0.3, importance=0.5, created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    mem_high = Memory(
        id="mem-2", category=MemoryCategory.FACT, content="High confidence.",
        confidence=0.9, importance=0.5, created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    
    ctx_low = MemoryExperienceContext.synthesize([mem_low])
    assert any("low-confidence" in h for h in ctx_low.continuity_hints)
    
    ctx_high = MemoryExperienceContext.synthesize([mem_high])
    assert any("strongly established" in h for h in ctx_high.continuity_hints)


def test_memory_experience_synthesis_importance() -> None:
    """Memory experience synthesizes importance guidance."""
    mem_important = Memory(
        id="mem-1", category=MemoryCategory.FACT, content="Very important.",
        confidence=0.9, importance=0.9, created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    ctx = MemoryExperienceContext.synthesize([mem_important])
    assert any("highly important" in h for h in ctx.continuity_hints)


def test_memory_experience_synthesis_categories() -> None:
    """Memory experience synthesizes category-specific guidance."""
    categories = [
        MemoryCategory.USER_GOAL, MemoryCategory.USER_PROBLEM,
        MemoryCategory.EVENT, MemoryCategory.PREFERENCE,
        MemoryCategory.PROMISE, MemoryCategory.JOKE,
        MemoryCategory.CHARACTER_EVENT
    ]
    for cat in categories:
        mem = Memory(
            id="mem-1", category=cat, content="Test content",
            confidence=0.9, importance=0.5, created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        ctx = MemoryExperienceContext.synthesize([mem])
        assert len(ctx.continuity_hints) >= 2 # 1 cat hint + 1 common hint at least
