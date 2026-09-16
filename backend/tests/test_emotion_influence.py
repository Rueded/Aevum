"""Tests for Phase 5.3: Emotion Influence Foundation.

Validates:
1. EmotionInfluenceDirection vocabulary, target emotions, and non-romance constraints.
2. EmotionInfluence and EmotionInfluenceCreate domain models, validation constraints
   (0.0-1.0 strength range, NaN/inf rejection, non-empty IDs/reason, reason length limit <= 500,
   credential rejection, immutability, extra fields forbidden).
3. SQLite persistence in emotion_influences table, deterministic duplicate protection,
   newest-first ordering, limit clamping, cascade deletion from character and source event.
4. Architectural separation from EmotionState, EmotionEvent, CharacterState, and RelationshipState.
5. Invariance checks: influence creation does NOT mutate EmotionState, CharacterState, or RelationshipState.
6. Security: rejection of credentials in reason, absence of public HTTP mutation routes.
"""

from datetime import datetime, timezone
import uuid
from httpx import AsyncClient
import pydantic
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.service import CharacterDefinitionService
from app.character.state_models import CharacterState
from app.character.state_service import CharacterStateService
from app.db.models import (
    CharacterDefinitionRecord,
    EmotionEventRecord,
    EmotionInfluenceRecord,
    utc_now,
)
from app.db.session import Base
from app.emotion import (
    EmotionEvent,
    EmotionEventCreate,
    EmotionEventService,
    EmotionEventSource,
    EmotionEventType,
    EmotionInfluence,
    EmotionInfluenceCreate,
    EmotionInfluenceDirection,
    EmotionInfluenceService,
    EmotionService,
    EmotionState,
    EmotionType,
)
from app.main import app
from app.relationship.models import RelationshipState
from app.relationship.service import RelationshipService


# ==============================================================================
# Helper fixture for creating a persistent EmotionEvent
# ==============================================================================


async def _create_test_event(
    session: AsyncSession,
    character_id: str = "aevum",
    summary: str = "Test event for influence testing.",
) -> EmotionEvent:
    event_service = EmotionEventService(session)
    event = await event_service.create_event(
        EmotionEventCreate(
            character_id=character_id,
            event_type=EmotionEventType.CHARACTER_EVENT,
            summary=summary,
            source=EmotionEventSource.SYSTEM,
            emotional_relevance=0.6,
        )
    )
    assert event is not None
    return event


# ==============================================================================
# 1. Model Validation Tests
# ==============================================================================


def test_valid_influence_creation():
    """Valid EmotionInfluence is instantiated successfully with all constraints satisfied."""
    now = utc_now()
    event_id = str(uuid.uuid4())
    inf = EmotionInfluence(
        id=str(uuid.uuid4()),
        character_id="aevum",
        event_id=event_id,
        target_emotion=EmotionType.FRUSTRATED,
        direction=EmotionInfluenceDirection.POSITIVE,
        strength=0.65,
        reason="Repeated difficulty during musical practice.",
        created_at=now,
    )
    assert inf.character_id == "aevum"
    assert inf.event_id == event_id
    assert inf.target_emotion == EmotionType.FRUSTRATED
    assert inf.direction == EmotionInfluenceDirection.POSITIVE
    assert inf.strength == 0.65
    assert inf.reason == "Repeated difficulty during musical practice."
    assert inf.created_at == now


def test_every_valid_direction():
    """All valid EmotionInfluenceDirection values are accepted."""
    now = utc_now()
    for direction in [EmotionInfluenceDirection.POSITIVE, EmotionInfluenceDirection.NEGATIVE]:
        inf = EmotionInfluence(
            id=str(uuid.uuid4()),
            character_id="aevum",
            event_id="evt-1",
            target_emotion=EmotionType.CALM,
            direction=direction,
            strength=0.5,
            reason="Direction test reason.",
            created_at=now,
        )
        assert inf.direction == direction


def test_every_emotion_type_target_supported():
    """All 17 EmotionType members can be targeted by an influence."""
    now = utc_now()
    for et in EmotionType:
        inf = EmotionInfluence(
            id=str(uuid.uuid4()),
            character_id="aevum",
            event_id="evt-1",
            target_emotion=et,
            direction=EmotionInfluenceDirection.POSITIVE,
            strength=0.4,
            reason=f"Testing target emotion {et.value}",
            created_at=now,
        )
        assert inf.target_emotion == et


@pytest.mark.parametrize("bad_char_id", ["", "   ", None])
def test_invalid_empty_character_id_rejected(bad_char_id: str | None):
    """Empty, whitespace-only, or None character_id is rejected."""
    now = utc_now()
    with pytest.raises(pydantic.ValidationError):
        EmotionInfluence(
            id=str(uuid.uuid4()),
            character_id=bad_char_id,  # type: ignore
            event_id="evt-1",
            target_emotion=EmotionType.CALM,
            direction=EmotionInfluenceDirection.POSITIVE,
            strength=0.5,
            reason="Valid reason",
            created_at=now,
        )


@pytest.mark.parametrize("bad_event_id", ["", "   ", None])
def test_invalid_empty_event_id_rejected(bad_event_id: str | None):
    """Empty, whitespace-only, or None event_id is rejected."""
    now = utc_now()
    with pytest.raises(pydantic.ValidationError):
        EmotionInfluence(
            id=str(uuid.uuid4()),
            character_id="aevum",
            event_id=bad_event_id,  # type: ignore
            target_emotion=EmotionType.CALM,
            direction=EmotionInfluenceDirection.POSITIVE,
            strength=0.5,
            reason="Valid reason",
            created_at=now,
        )


@pytest.mark.parametrize("bad_reason", ["", "   ", None])
def test_invalid_empty_reason_rejected(bad_reason: str | None):
    """Empty, whitespace-only, or None reason is rejected."""
    now = utc_now()
    with pytest.raises(pydantic.ValidationError):
        EmotionInfluence(
            id=str(uuid.uuid4()),
            character_id="aevum",
            event_id="evt-1",
            target_emotion=EmotionType.CALM,
            direction=EmotionInfluenceDirection.POSITIVE,
            strength=0.5,
            reason=bad_reason,  # type: ignore
            created_at=now,
        )


def test_reason_length_limit():
    """Reason exceeding 500 characters is rejected."""
    now = utc_now()
    overlong = "r" * 501
    with pytest.raises(pydantic.ValidationError):
        EmotionInfluence(
            id=str(uuid.uuid4()),
            character_id="aevum",
            event_id="evt-1",
            target_emotion=EmotionType.HAPPY,
            direction=EmotionInfluenceDirection.POSITIVE,
            strength=0.5,
            reason=overlong,
            created_at=now,
        )

    # 500 characters exactly is accepted
    exact_500 = "r" * 500
    inf = EmotionInfluence(
        id=str(uuid.uuid4()),
        character_id="aevum",
        event_id="evt-1",
        target_emotion=EmotionType.HAPPY,
        direction=EmotionInfluenceDirection.POSITIVE,
        strength=0.5,
        reason=exact_500,
        created_at=now,
    )
    assert len(inf.reason) == 500


@pytest.mark.parametrize("bad_strength", [-0.01, -1.0, 1.01, 2.0])
def test_out_of_range_strength_rejected(bad_strength: float):
    """Strength values outside [0.0, 1.0] are strictly rejected, never clamped."""
    now = utc_now()
    with pytest.raises(pydantic.ValidationError):
        EmotionInfluence(
            id=str(uuid.uuid4()),
            character_id="aevum",
            event_id="evt-1",
            target_emotion=EmotionType.HAPPY,
            direction=EmotionInfluenceDirection.POSITIVE,
            strength=bad_strength,
            reason="Valid reason",
            created_at=now,
        )


@pytest.mark.parametrize("bad_val", [float("nan"), float("inf"), float("-inf")])
def test_nan_and_infinite_strength_rejected(bad_val: float):
    """NaN and infinite strength values are rejected."""
    now = utc_now()
    with pytest.raises(pydantic.ValidationError):
        EmotionInfluence(
            id=str(uuid.uuid4()),
            character_id="aevum",
            event_id="evt-1",
            target_emotion=EmotionType.HAPPY,
            direction=EmotionInfluenceDirection.POSITIVE,
            strength=bad_val,
            reason="Valid reason",
            created_at=now,
        )


@pytest.mark.parametrize("valid_strength", [0.0, 0.5, 1.0])
def test_valid_boundary_strengths_accepted(valid_strength: float):
    """Boundary strength values 0.0, 0.5, and 1.0 are accepted."""
    now = utc_now()
    inf = EmotionInfluence(
        id=str(uuid.uuid4()),
        character_id="aevum",
        event_id="evt-1",
        target_emotion=EmotionType.HAPPY,
        direction=EmotionInfluenceDirection.POSITIVE,
        strength=valid_strength,
        reason="Valid reason",
        created_at=now,
    )
    assert inf.strength == valid_strength


def test_immutable_influence_model():
    """EmotionInfluence is frozen and cannot be mutated in-place."""
    now = utc_now()
    inf = EmotionInfluence(
        id=str(uuid.uuid4()),
        character_id="aevum",
        event_id="evt-1",
        target_emotion=EmotionType.HAPPY,
        direction=EmotionInfluenceDirection.POSITIVE,
        strength=0.5,
        reason="Valid reason",
        created_at=now,
    )
    with pytest.raises(pydantic.ValidationError):
        inf.strength = 0.9  # type: ignore


def test_extra_fields_rejected():
    """Extra undeclared fields on EmotionInfluence are forbidden."""
    now = utc_now()
    with pytest.raises(pydantic.ValidationError):
        EmotionInfluence(
            id=str(uuid.uuid4()),
            character_id="aevum",
            event_id="evt-1",
            target_emotion=EmotionType.HAPPY,
            direction=EmotionInfluenceDirection.POSITIVE,
            strength=0.5,
            reason="Valid reason",
            created_at=now,
            extra_field="disallowed",  # type: ignore
        )


def test_influence_create_model():
    """EmotionInfluenceCreate payload validates fields and sets defaults."""
    payload = EmotionInfluenceCreate(
        character_id="aevum",
        event_id="evt-123",
        target_emotion=EmotionType.SAD,
        direction=EmotionInfluenceDirection.POSITIVE,
        strength=0.7,
        reason="Sad event occurred.",
    )
    assert payload.character_id == "aevum"
    assert payload.event_id == "evt-123"
    assert payload.target_emotion == EmotionType.SAD
    assert payload.direction == EmotionInfluenceDirection.POSITIVE
    assert payload.strength == 0.7

    with pytest.raises(pydantic.ValidationError):
        payload.strength = 0.8  # type: ignore


def test_reason_rejects_credentials():
    """Influence reason containing secret/credential patterns is rejected."""
    now = utc_now()
    with pytest.raises(pydantic.ValidationError):
        EmotionInfluence(
            id=str(uuid.uuid4()),
            character_id="aevum",
            event_id="evt-1",
            target_emotion=EmotionType.WORRIED,
            direction=EmotionInfluenceDirection.POSITIVE,
            strength=0.8,
            reason="Server error exposed api-key: sk-proj-1234567890abcdef1234567890abcdef",
            created_at=now,
        )


# ==============================================================================
# 2. Vocabulary & Non-Romance Constraints
# ==============================================================================


def test_direction_contains_no_romance_or_unsupported_terms():
    """EmotionInfluenceDirection must strictly be POSITIVE or NEGATIVE only."""
    allowed = {"POSITIVE", "NEGATIVE"}
    actual = {d.value for d in EmotionInfluenceDirection}
    assert actual == allowed

    prohibited = {"NEUTRAL", "JEALOUS", "ROMANTIC", "LOVE", "HATE"}
    assert not actual.intersection(prohibited)


# ==============================================================================
# 3. Separation of Concerns Tests
# ==============================================================================


def test_emotion_influence_does_not_contain_relationship_metrics():
    """EmotionInfluence must not contain any relationship metrics."""
    field_names = set(EmotionInfluence.model_fields.keys())
    prohibited_relationship_fields = {
        "trust",
        "affection",
        "attachment",
        "comfort",
        "familiarity",
        "respect",
        "jealousy",
        "romance",
        "relationship_score",
    }
    overlap = field_names.intersection(prohibited_relationship_fields)
    assert not overlap, f"EmotionInfluence contains prohibited relationship fields: {overlap}"


def test_emotion_influence_does_not_duplicate_character_state_metrics():
    """EmotionInfluence must not duplicate physiological/cognitive CharacterState metrics."""
    field_names = set(EmotionInfluence.model_fields.keys())
    prohibited_character_fields = {
        "energy",
        "stress",
        "social_energy",
        "confidence",
        "irritation",
        "loneliness",
        "mood",
        "current_activity",
        "current_location",
    }
    overlap = field_names.intersection(prohibited_character_fields)
    assert not overlap, f"EmotionInfluence duplicates CharacterState fields: {overlap}"


def test_emotion_influence_does_not_contain_emotion_state_fields():
    """EmotionInfluence must not duplicate current EmotionState fields."""
    field_names = set(EmotionInfluence.model_fields.keys())
    prohibited_state_fields = {
        "intensity",
        "version",
        "previous_emotion",
        "new_emotion",
        "transition_reason",
    }
    overlap = field_names.intersection(prohibited_state_fields)
    assert not overlap, f"EmotionInfluence duplicates EmotionState fields: {overlap}"


def test_emotion_influence_does_not_duplicate_emotion_event_fields():
    """EmotionInfluence must reference event_id, not duplicate EmotionEvent fields."""
    field_names = set(EmotionInfluence.model_fields.keys())
    prohibited_event_fields = {
        "event_type",
        "summary",
        "source",
        "emotional_relevance",
    }
    overlap = field_names.intersection(prohibited_event_fields)
    assert not overlap, f"EmotionInfluence duplicates EmotionEvent fields: {overlap}"


# ==============================================================================
# 4. Persistence & Service Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_create_and_get_influence(test_session: AsyncSession):
    """create_influence persists an EmotionInfluence and get_influence retrieves it by ID."""
    event = await _create_test_event(test_session)
    service = EmotionInfluenceService(test_session)

    payload = EmotionInfluenceCreate(
        character_id="aevum",
        event_id=event.id,
        target_emotion=EmotionType.CONTENT,
        direction=EmotionInfluenceDirection.POSITIVE,
        strength=0.75,
        reason="Felt a sense of accomplishment after finishing a task.",
    )
    created = await service.create_influence(payload)
    assert created is not None
    assert created.character_id == "aevum"
    assert created.event_id == event.id
    assert created.target_emotion == EmotionType.CONTENT
    assert created.direction == EmotionInfluenceDirection.POSITIVE
    assert created.strength == 0.75
    assert created.reason == "Felt a sense of accomplishment after finishing a task."

    # Retrieve by ID
    retrieved = await service.get_influence(created.id)
    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.reason == created.reason
    assert retrieved.created_at == created.created_at


@pytest.mark.asyncio
async def test_create_influence_nonexistent_event_raises_error(test_session: AsyncSession):
    """create_influence raises ValueError if the originating event does not exist."""
    service = EmotionInfluenceService(test_session)
    payload = EmotionInfluenceCreate(
        character_id="aevum",
        event_id="nonexistent-event-id",
        target_emotion=EmotionType.SAD,
        direction=EmotionInfluenceDirection.POSITIVE,
        strength=0.5,
        reason="Some reason",
    )
    with pytest.raises(ValueError, match="not found"):
        await service.create_influence(payload)


@pytest.mark.asyncio
async def test_get_nonexistent_influence_returns_none(test_session: AsyncSession):
    """Querying an unknown influence ID returns None."""
    service = EmotionInfluenceService(test_session)
    result = await service.get_influence("nonexistent-id")
    assert result is None


@pytest.mark.asyncio
async def test_duplicate_protection(test_session: AsyncSession):
    """Identical influences (same character, event, target, direction, normalized reason) are skipped."""
    event = await _create_test_event(test_session)
    service = EmotionInfluenceService(test_session)

    payload1 = EmotionInfluenceCreate(
        character_id="aevum",
        event_id=event.id,
        target_emotion=EmotionType.EXCITED,
        direction=EmotionInfluenceDirection.POSITIVE,
        strength=0.8,
        reason="Anticipating an upcoming concert.",
    )
    res1 = await service.create_influence(payload1)
    assert res1 is not None

    # Exact duplicate
    res2 = await service.create_influence(payload1)
    assert res2 is None

    # Normalized whitespace/case duplicate
    payload_normalized = EmotionInfluenceCreate(
        character_id="aevum",
        event_id=event.id,
        target_emotion=EmotionType.EXCITED,
        direction=EmotionInfluenceDirection.POSITIVE,
        strength=0.9,
        reason="  anticipating an upcoming concert.  ",
    )
    res3 = await service.create_influence(payload_normalized)
    assert res3 is None

    # Different target emotion is NOT a duplicate
    payload_diff_target = EmotionInfluenceCreate(
        character_id="aevum",
        event_id=event.id,
        target_emotion=EmotionType.CURIOUS,
        direction=EmotionInfluenceDirection.POSITIVE,
        strength=0.8,
        reason="Anticipating an upcoming concert.",
    )
    res4 = await service.create_influence(payload_diff_target)
    assert res4 is not None


@pytest.mark.asyncio
async def test_list_influences_deterministic_ordering_and_filtering(test_session: AsyncSession):
    """list_influences orders newest-first and supports event_id and target_emotion filters."""
    event1 = await _create_test_event(test_session, summary="Event 1")
    event2 = await _create_test_event(test_session, summary="Event 2")
    service = EmotionInfluenceService(test_session)

    inf1 = await service.create_influence(
        EmotionInfluenceCreate(
            character_id="aevum",
            event_id=event1.id,
            target_emotion=EmotionType.CALM,
            direction=EmotionInfluenceDirection.POSITIVE,
            strength=0.4,
            reason="Influence 1 reason",
        )
    )
    inf2 = await service.create_influence(
        EmotionInfluenceCreate(
            character_id="aevum",
            event_id=event2.id,
            target_emotion=EmotionType.HAPPY,
            direction=EmotionInfluenceDirection.POSITIVE,
            strength=0.7,
            reason="Influence 2 reason",
        )
    )
    inf3 = await service.create_influence(
        EmotionInfluenceCreate(
            character_id="aevum",
            event_id=event2.id,
            target_emotion=EmotionType.CALM,
            direction=EmotionInfluenceDirection.NEGATIVE,
            strength=0.5,
            reason="Influence 3 reason",
        )
    )
    assert inf1 and inf2 and inf3

    # All influences newest-first (inf3, inf2, inf1)
    all_infs = await service.list_influences(character_id="aevum")
    assert len(all_infs) == 3
    assert all_infs[0].id == inf3.id
    assert all_infs[1].id == inf2.id
    assert all_infs[2].id == inf1.id

    # Filtered by event_id
    event2_infs = await service.list_influences(character_id="aevum", event_id=event2.id)
    assert len(event2_infs) == 2
    assert event2_infs[0].id == inf3.id
    assert event2_infs[1].id == inf2.id

    # Filtered by target_emotion
    calm_infs = await service.list_influences(character_id="aevum", target_emotion=EmotionType.CALM)
    assert len(calm_infs) == 2
    assert calm_infs[0].id == inf3.id
    assert calm_infs[1].id == inf1.id


@pytest.mark.asyncio
async def test_list_influences_limit_clamping(test_session: AsyncSession):
    """list_influences clamps limit between 1 and 50."""
    event = await _create_test_event(test_session)
    service = EmotionInfluenceService(test_session)

    for i in range(5):
        await service.create_influence(
            EmotionInfluenceCreate(
                character_id="aevum",
                event_id=event.id,
                target_emotion=EmotionType.AMUSED,
                direction=EmotionInfluenceDirection.POSITIVE,
                strength=0.5,
                reason=f"Amusement reason {i}",
            )
        )

    # limit = 2
    res_2 = await service.list_influences(character_id="aevum", limit=2)
    assert len(res_2) == 2

    # limit = 0 clamped to 1
    res_0 = await service.list_influences(character_id="aevum", limit=0)
    assert len(res_0) == 1

    # limit = 100 clamped to 50
    res_100 = await service.list_influences(character_id="aevum", limit=100)
    assert len(res_100) == 5


@pytest.mark.asyncio
async def test_delete_influence(test_session: AsyncSession):
    """delete_influence deletes an influence and returns boolean status."""
    event = await _create_test_event(test_session)
    service = EmotionInfluenceService(test_session)

    created = await service.create_influence(
        EmotionInfluenceCreate(
            character_id="aevum",
            event_id=event.id,
            target_emotion=EmotionType.NERVOUS,
            direction=EmotionInfluenceDirection.POSITIVE,
            strength=0.6,
            reason="Public presentation approaching.",
        )
    )
    assert created is not None

    deleted = await service.delete_influence(created.id)
    assert deleted is True

    # Confirm deleted
    assert await service.get_influence(created.id) is None

    # Deleting again returns False
    assert await service.delete_influence(created.id) is False


# ==============================================================================
# 5. Database Schema & Cascade Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_database_table_and_columns(test_session: AsyncSession):
    """Verify emotion_influences table exists with exact column names and expected types."""
    assert "emotion_influences" in Base.metadata.tables
    table = Base.metadata.tables["emotion_influences"]
    col_names = {c.name for c in table.columns}
    expected_cols = {
        "id",
        "character_id",
        "event_id",
        "target_emotion",
        "direction",
        "strength",
        "reason",
        "created_at",
    }
    assert expected_cols.issubset(col_names)

    # Verify live SQLite table schema via PRAGMA table_info
    res = await test_session.execute(text("PRAGMA table_info(emotion_influences)"))
    pragma_cols = {row[1] for row in res.fetchall()}
    assert expected_cols.issubset(pragma_cols)


@pytest.mark.asyncio
async def test_source_event_cascade_deletion(test_session: AsyncSession):
    """Deleting the originating EmotionEventRecord cascades to emotion_influences."""
    event = await _create_test_event(test_session)
    service = EmotionInfluenceService(test_session)

    inf = await service.create_influence(
        EmotionInfluenceCreate(
            character_id="aevum",
            event_id=event.id,
            target_emotion=EmotionType.CURIOUS,
            direction=EmotionInfluenceDirection.POSITIVE,
            strength=0.7,
            reason="Discovered an intriguing topic.",
        )
    )
    assert inf is not None

    # Verify influence exists in DB
    stmt = select(EmotionInfluenceRecord).where(EmotionInfluenceRecord.id == inf.id)
    assert (await test_session.scalars(stmt)).first() is not None

    # Delete originating event
    event_service = EmotionEventService(test_session)
    await event_service.delete_event(event.id)

    # Verify influence was deleted by cascade
    assert (await test_session.scalars(stmt)).first() is None


@pytest.mark.asyncio
async def test_character_cascade_deletion(test_session: AsyncSession):
    """Deleting the parent CharacterDefinitionRecord cascades to emotion_influences."""
    char_service = CharacterDefinitionService(test_session)
    char = await char_service.get_character("aevum")

    event = await _create_test_event(test_session)
    service = EmotionInfluenceService(test_session)

    inf = await service.create_influence(
        EmotionInfluenceCreate(
            character_id="aevum",
            event_id=event.id,
            target_emotion=EmotionType.AMUSED,
            direction=EmotionInfluenceDirection.POSITIVE,
            strength=0.5,
            reason="Heard a witty remark.",
        )
    )
    assert inf is not None

    stmt = select(EmotionInfluenceRecord).where(EmotionInfluenceRecord.id == inf.id)
    assert (await test_session.scalars(stmt)).first() is not None

    # Delete character definition
    char_stmt = select(CharacterDefinitionRecord).where(CharacterDefinitionRecord.id == "aevum")
    char_record = (await test_session.scalars(char_stmt)).first()
    assert char_record is not None

    await test_session.delete(char_record)
    await test_session.commit()

    # Verify influence was cascade deleted
    assert (await test_session.scalars(stmt)).first() is None


# ==============================================================================
# 6. Architectural Invariance Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_creating_influence_does_not_mutate_emotion_state(test_session: AsyncSession):
    """Recording an EmotionInfluence leaves EmotionState completely untouched."""
    emotion_service = EmotionService(test_session)
    initial_emotion = await emotion_service.get_emotion_state("aevum")
    assert initial_emotion.version == 1
    assert initial_emotion.emotion_type == EmotionType.NEUTRAL
    assert initial_emotion.intensity == 0.50

    event = await _create_test_event(test_session)
    influence_service = EmotionInfluenceService(test_session)

    # Create a strong influence
    await influence_service.create_influence(
        EmotionInfluenceCreate(
            character_id="aevum",
            event_id=event.id,
            target_emotion=EmotionType.ANGRY,
            direction=EmotionInfluenceDirection.POSITIVE,
            strength=1.0,
            reason="Encountered unfair treatment.",
        )
    )

    # Verify EmotionState is completely unchanged
    current_emotion = await emotion_service.get_emotion_state("aevum")
    assert current_emotion.version == 1
    assert current_emotion.emotion_type == EmotionType.NEUTRAL
    assert current_emotion.intensity == 0.50
    assert current_emotion.updated_at == initial_emotion.updated_at


@pytest.mark.asyncio
async def test_creating_influence_does_not_mutate_character_state(test_session: AsyncSession):
    """Recording an EmotionInfluence leaves CharacterState completely untouched."""
    char_state_service = CharacterStateService(test_session)
    initial_state = await char_state_service.get_state("aevum")
    assert initial_state.version == 1

    event = await _create_test_event(test_session)
    influence_service = EmotionInfluenceService(test_session)

    await influence_service.create_influence(
        EmotionInfluenceCreate(
            character_id="aevum",
            event_id=event.id,
            target_emotion=EmotionType.TIRED,
            direction=EmotionInfluenceDirection.POSITIVE,
            strength=0.9,
            reason="Exhausting schedule.",
        )
    )

    current_state = await char_state_service.get_state("aevum")
    assert current_state.version == 1
    assert current_state.energy == initial_state.energy
    assert current_state.stress == initial_state.stress
    assert current_state.updated_at == initial_state.updated_at


@pytest.mark.asyncio
async def test_creating_influence_does_not_mutate_relationship_state(test_session: AsyncSession):
    """Recording an EmotionInfluence leaves RelationshipState completely untouched."""
    rel_service = RelationshipService(test_session)
    initial_rel = await rel_service.get_relationship_state()
    assert initial_rel.version == 1

    event = await _create_test_event(test_session)
    influence_service = EmotionInfluenceService(test_session)

    await influence_service.create_influence(
        EmotionInfluenceCreate(
            character_id="aevum",
            event_id=event.id,
            target_emotion=EmotionType.HAPPY,
            direction=EmotionInfluenceDirection.POSITIVE,
            strength=0.9,
            reason="Positive social encounter.",
        )
    )

    current_rel = await rel_service.get_relationship_state()
    assert current_rel.version == 1
    assert current_rel.trust == initial_rel.trust
    assert current_rel.affection == initial_rel.affection
    assert current_rel.updated_at == initial_rel.updated_at


# ==============================================================================
# 7. Security Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_no_public_emotion_influence_endpoint(client: AsyncClient):
    """Verify there are no public HTTP endpoints that allow mutating EmotionInfluence records."""
    openapi_paths = list(app.openapi().get("paths", {}).keys())
    influence_routes = [p for p in openapi_paths if "influence" in p.lower()]
    assert not influence_routes, f"Prohibited public influence routes detected: {influence_routes}"

    resp_post = await client.post(
        "/emotion/influences",
        json={"target_emotion": "HAPPY", "reason": "Test reason"},
    )
    assert resp_post.status_code == 404

    resp_get = await client.get("/emotion/influences")
    assert resp_get.status_code == 404
