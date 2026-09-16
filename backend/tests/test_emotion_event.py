"""Tests for Phase 5.2: Emotion Cause / Event Foundation.

Validates:
1. EmotionEventType vocabulary, source vocabulary, and non-romance constraints.
2. EmotionEvent and EmotionEventCreate domain models, validation constraints
   (0.0-1.0 relevance range, NaN/inf rejection, non-empty strings, summary length limit <= 500,
   credential rejection, immutability, extra fields forbidden).
3. SQLite persistence in emotion_events table, deterministic duplicate protection,
   newest-first ordering, limit clamping, and cascade deletion upon character deletion.
4. Architectural separation from EmotionState, CharacterState, RelationshipState, and Memory.
5. Invariance checks: event creation does NOT mutate EmotionState, CharacterState, or RelationshipState.
6. Security: rejection of credentials in summary, absence of public HTTP mutation routes.
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
from app.db.models import CharacterDefinitionRecord, EmotionEventRecord, utc_now
from app.db.session import Base
from app.emotion import (
    EmotionEvent,
    EmotionEventCreate,
    EmotionEventService,
    EmotionEventSource,
    EmotionEventType,
    EmotionService,
    EmotionState,
    EmotionType,
)
from app.main import app
from app.relationship.models import RelationshipState
from app.relationship.service import RelationshipService


# ==============================================================================
# 1. Model Validation Tests
# ==============================================================================


def test_valid_event_creation():
    """Valid EmotionEvent is instantiated successfully with all constraints satisfied."""
    now = utc_now()
    event = EmotionEvent(
        id=str(uuid.uuid4()),
        character_id="aevum",
        event_type=EmotionEventType.USER_INTERACTION,
        summary="User shared an interesting story about astronomy.",
        source=EmotionEventSource.SYSTEM,
        emotional_relevance=0.75,
        created_at=now,
    )
    assert event.character_id == "aevum"
    assert event.event_type == EmotionEventType.USER_INTERACTION
    assert event.summary == "User shared an interesting story about astronomy."
    assert event.source == EmotionEventSource.SYSTEM
    assert event.emotional_relevance == 0.75
    assert event.created_at == now


def test_every_event_type_supported():
    """All EmotionEventType values can be instantiated without errors."""
    now = utc_now()
    for et in EmotionEventType:
        event = EmotionEvent(
            id=str(uuid.uuid4()),
            character_id="aevum",
            event_type=et,
            summary=f"Event summary for {et.value}",
            source=EmotionEventSource.SYSTEM,
            emotional_relevance=0.5,
            created_at=now,
        )
        assert event.event_type == et


def test_all_sources_supported():
    """All EmotionEventSource values are valid."""
    now = utc_now()
    for src in EmotionEventSource:
        event = EmotionEvent(
            id=str(uuid.uuid4()),
            character_id="aevum",
            event_type=EmotionEventType.INTERNAL_STATE,
            summary="Processed internal fatigue.",
            source=src,
            emotional_relevance=0.4,
            created_at=now,
        )
        assert event.source == src


@pytest.mark.parametrize("bad_char_id", ["", "   ", None])
def test_invalid_empty_character_id_rejected(bad_char_id: str | None):
    """Empty, whitespace-only, or None character_id is rejected."""
    now = utc_now()
    with pytest.raises(pydantic.ValidationError):
        EmotionEvent(
            id=str(uuid.uuid4()),
            character_id=bad_char_id,  # type: ignore
            event_type=EmotionEventType.USER_INTERACTION,
            summary="Valid summary",
            source=EmotionEventSource.SYSTEM,
            emotional_relevance=0.5,
            created_at=now,
        )


@pytest.mark.parametrize("bad_summary", ["", "   ", None])
def test_invalid_empty_summary_rejected(bad_summary: str | None):
    """Empty, whitespace-only, or None summary is rejected."""
    now = utc_now()
    with pytest.raises(pydantic.ValidationError):
        EmotionEvent(
            id=str(uuid.uuid4()),
            character_id="aevum",
            event_type=EmotionEventType.USER_INTERACTION,
            summary=bad_summary,  # type: ignore
            source=EmotionEventSource.SYSTEM,
            emotional_relevance=0.5,
            created_at=now,
        )


def test_summary_length_limit():
    """Summary exceeding 500 characters is rejected."""
    now = utc_now()
    overlong = "x" * 501
    with pytest.raises(pydantic.ValidationError):
        EmotionEvent(
            id=str(uuid.uuid4()),
            character_id="aevum",
            event_type=EmotionEventType.USER_INTERACTION,
            summary=overlong,
            source=EmotionEventSource.SYSTEM,
            emotional_relevance=0.5,
            created_at=now,
        )

    # 500 characters exactly is accepted
    exact_500 = "x" * 500
    ev = EmotionEvent(
        id=str(uuid.uuid4()),
        character_id="aevum",
        event_type=EmotionEventType.USER_INTERACTION,
        summary=exact_500,
        source=EmotionEventSource.SYSTEM,
        emotional_relevance=0.5,
        created_at=now,
    )
    assert len(ev.summary) == 500


@pytest.mark.parametrize("bad_rel", [-0.01, -1.0, 1.01, 2.5])
def test_out_of_range_emotional_relevance_rejected(bad_rel: float):
    """Emotional relevance values below 0.0 or above 1.0 are rejected."""
    now = utc_now()
    with pytest.raises(pydantic.ValidationError):
        EmotionEvent(
            id=str(uuid.uuid4()),
            character_id="aevum",
            event_type=EmotionEventType.USER_INTERACTION,
            summary="Valid summary",
            source=EmotionEventSource.SYSTEM,
            emotional_relevance=bad_rel,
            created_at=now,
        )


@pytest.mark.parametrize("bad_val", [float("nan"), float("inf"), float("-inf")])
def test_nan_and_infinite_relevance_rejected(bad_val: float):
    """NaN and infinite emotional relevance values are rejected."""
    now = utc_now()
    with pytest.raises(pydantic.ValidationError):
        EmotionEvent(
            id=str(uuid.uuid4()),
            character_id="aevum",
            event_type=EmotionEventType.USER_INTERACTION,
            summary="Valid summary",
            source=EmotionEventSource.SYSTEM,
            emotional_relevance=bad_val,
            created_at=now,
        )


def test_immutable_event_model():
    """EmotionEvent is frozen and cannot be mutated in-place."""
    now = utc_now()
    event = EmotionEvent(
        id=str(uuid.uuid4()),
        character_id="aevum",
        event_type=EmotionEventType.USER_INTERACTION,
        summary="User said hello.",
        source=EmotionEventSource.SYSTEM,
        emotional_relevance=0.5,
        created_at=now,
    )
    with pytest.raises(pydantic.ValidationError):
        event.emotional_relevance = 0.9  # type: ignore


def test_extra_fields_rejected():
    """Extra undeclared fields on EmotionEvent are forbidden."""
    now = utc_now()
    with pytest.raises(pydantic.ValidationError):
        EmotionEvent(
            id=str(uuid.uuid4()),
            character_id="aevum",
            event_type=EmotionEventType.USER_INTERACTION,
            summary="Valid summary",
            source=EmotionEventSource.SYSTEM,
            emotional_relevance=0.5,
            created_at=now,
            extra_field="disallowed",  # type: ignore
        )


def test_event_create_model():
    """EmotionEventCreate payload validates fields and sets defaults."""
    payload = EmotionEventCreate(
        character_id="aevum",
        event_type=EmotionEventType.CHARACTER_EVENT,
        summary="Aevum practiced playing the piano.",
    )
    assert payload.source == EmotionEventSource.SYSTEM
    assert payload.emotional_relevance == 0.50
    assert payload.character_id == "aevum"

    with pytest.raises(pydantic.ValidationError):
        payload.summary = "new"  # type: ignore


@pytest.mark.parametrize("invalid_rel", [-1.0, 1.01, 2.0, float("nan"), float("inf"), float("-inf")])
def test_event_create_rejects_out_of_range_relevance(invalid_rel: float):
    """EmotionEventCreate strictly rejects out-of-range, NaN, and infinite relevance."""
    with pytest.raises(pydantic.ValidationError):
        EmotionEventCreate(
            character_id="aevum",
            event_type=EmotionEventType.USER_INTERACTION,
            summary="Valid summary",
            emotional_relevance=invalid_rel,
        )


@pytest.mark.parametrize("valid_rel", [0.0, 0.5, 1.0])
def test_event_create_accepts_valid_boundary_relevance(valid_rel: float):
    """EmotionEventCreate accepts valid boundary values 0.0, 0.5, and 1.0."""
    payload = EmotionEventCreate(
        character_id="aevum",
        event_type=EmotionEventType.USER_INTERACTION,
        summary="Valid summary",
        emotional_relevance=valid_rel,
    )
    assert payload.emotional_relevance == valid_rel


def test_summary_rejects_credentials():
    """Event summary containing credential/secret patterns is rejected."""
    now = utc_now()
    with pytest.raises(pydantic.ValidationError):
        EmotionEvent(
            id=str(uuid.uuid4()),
            character_id="aevum",
            event_type=EmotionEventType.SYSTEM_EVENT,
            summary="System configured api-key: sk-proj-1234567890abcdef1234567890abcdef",
            source=EmotionEventSource.SYSTEM,
            emotional_relevance=0.5,
            created_at=now,
        )


# ==============================================================================
# 2. Vocabulary & Non-Romance Constraints
# ==============================================================================


def test_event_types_contain_no_romance():
    """EmotionEventType vocabulary must strictly avoid romance/dating concepts."""
    prohibited_vocabulary = {
        "JEALOUSY",
        "ROMANTIC_EVENT",
        "LOVE",
        "BREAKUP",
        "HEARTBREAK",
        "CRUSH",
        "IN_LOVE",
        "DATING",
    }
    actual_types = {e.value for e in EmotionEventType}
    overlap = actual_types.intersection(prohibited_vocabulary)
    assert not overlap, f"EmotionEventType contains prohibited romantic terms: {overlap}"


# ==============================================================================
# 3. Separation of Concerns Tests
# ==============================================================================


def test_emotion_event_does_not_contain_relationship_metrics():
    """EmotionEvent must not contain any relationship metrics."""
    field_names = set(EmotionEvent.model_fields.keys())
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
    assert not overlap, f"EmotionEvent contains prohibited relationship fields: {overlap}"


def test_emotion_event_does_not_duplicate_character_state_metrics():
    """EmotionEvent must not duplicate physiological/cognitive CharacterState metrics."""
    field_names = set(EmotionEvent.model_fields.keys())
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
    assert not overlap, f"EmotionEvent duplicates CharacterState fields: {overlap}"


def test_emotion_event_does_not_contain_emotion_state_or_transition_fields():
    """EmotionEvent must not contain EmotionState fields or state-transition fields."""
    field_names = set(EmotionEvent.model_fields.keys())
    prohibited_emotion_fields = {
        "intensity",
        "previous_emotion",
        "new_emotion",
        "old_intensity",
        "new_intensity",
        "transition_reason",
        "version",
    }
    overlap = field_names.intersection(prohibited_emotion_fields)
    assert not overlap, f"EmotionEvent contains prohibited transition/state fields: {overlap}"


# ==============================================================================
# 4. Persistence & Service Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_create_and_get_event(test_session: AsyncSession):
    """create_event persists an EmotionEvent and get_event retrieves it by ID."""
    service = EmotionEventService(test_session)
    payload = EmotionEventCreate(
        character_id="aevum",
        event_type=EmotionEventType.CHARACTER_EVENT,
        summary="Aevum practiced her piano piece for 30 minutes.",
        source=EmotionEventSource.SYSTEM,
        emotional_relevance=0.65,
    )
    created = await service.create_event(payload)
    assert created is not None
    assert created.character_id == "aevum"
    assert created.event_type == EmotionEventType.CHARACTER_EVENT
    assert created.summary == "Aevum practiced her piano piece for 30 minutes."
    assert created.emotional_relevance == 0.65

    # Retrieve by ID
    retrieved = await service.get_event(created.id)
    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.summary == created.summary
    assert retrieved.created_at == created.created_at


@pytest.mark.asyncio
async def test_get_nonexistent_event_returns_none(test_session: AsyncSession):
    """Querying an unknown event ID returns None."""
    service = EmotionEventService(test_session)
    result = await service.get_event("nonexistent-id")
    assert result is None


@pytest.mark.asyncio
async def test_duplicate_protection(test_session: AsyncSession):
    """Identical events (same character, type, normalized summary) are skipped as duplicates."""
    service = EmotionEventService(test_session)
    payload1 = EmotionEventCreate(
        character_id="aevum",
        event_type=EmotionEventType.LIFE_EVENT,
        summary="Completed university midterm exam.",
        emotional_relevance=0.80,
    )
    res1 = await service.create_event(payload1)
    assert res1 is not None

    # Exact duplicate
    res2 = await service.create_event(payload1)
    assert res2 is None

    # Case-insensitive / whitespace-normalized duplicate
    payload_normalized = EmotionEventCreate(
        character_id="aevum",
        event_type=EmotionEventType.LIFE_EVENT,
        summary="  completed university midterm exam.  ",
        emotional_relevance=0.85,
    )
    res3 = await service.create_event(payload_normalized)
    assert res3 is None

    # Different event type with same summary is NOT a duplicate
    payload_diff_type = EmotionEventCreate(
        character_id="aevum",
        event_type=EmotionEventType.USER_INTERACTION,
        summary="Completed university midterm exam.",
        emotional_relevance=0.80,
    )
    res4 = await service.create_event(payload_diff_type)
    assert res4 is not None


@pytest.mark.asyncio
async def test_list_events_deterministic_ordering_and_filtering(test_session: AsyncSession):
    """list_events orders newest-first (created_at DESC, id DESC) and filters by type."""
    service = EmotionEventService(test_session)

    # Seed events across types
    p1 = EmotionEventCreate(
        character_id="aevum",
        event_type=EmotionEventType.MEMORY_RECALL,
        summary="Remembered a childhood summer trip.",
        emotional_relevance=0.4,
    )
    p2 = EmotionEventCreate(
        character_id="aevum",
        event_type=EmotionEventType.USER_INTERACTION,
        summary="Had a cheerful conversation with user.",
        emotional_relevance=0.7,
    )
    p3 = EmotionEventCreate(
        character_id="aevum",
        event_type=EmotionEventType.USER_INTERACTION,
        summary="Discussed favorite science fiction novels.",
        emotional_relevance=0.8,
    )

    e1 = await service.create_event(p1)
    e2 = await service.create_event(p2)
    e3 = await service.create_event(p3)

    assert e1 and e2 and e3

    # All events for aevum (newest first: e3, e2, e1)
    all_events = await service.list_events(character_id="aevum", limit=10)
    assert len(all_events) == 3
    assert all_events[0].id == e3.id
    assert all_events[1].id == e2.id
    assert all_events[2].id == e1.id

    # Filtered by event_type
    user_events = await service.list_events(
        character_id="aevum",
        event_type=EmotionEventType.USER_INTERACTION,
    )
    assert len(user_events) == 2
    assert user_events[0].id == e3.id
    assert user_events[1].id == e2.id


@pytest.mark.asyncio
async def test_list_events_limit_clamping(test_session: AsyncSession):
    """list_events clamps limit between 1 and 50."""
    service = EmotionEventService(test_session)
    for i in range(5):
        await service.create_event(
            EmotionEventCreate(
                character_id="aevum",
                event_type=EmotionEventType.SYSTEM_EVENT,
                summary=f"System event {i}",
            )
        )

    # Limit = 2 returns 2
    res_2 = await service.list_events(character_id="aevum", limit=2)
    assert len(res_2) == 2

    # Limit = 0 clamped to 1
    res_0 = await service.list_events(character_id="aevum", limit=0)
    assert len(res_0) == 1

    # Limit = 100 clamped to 50
    res_100 = await service.list_events(character_id="aevum", limit=100)
    assert len(res_100) == 5


@pytest.mark.asyncio
async def test_delete_event(test_session: AsyncSession):
    """delete_event deletes an event and returns boolean status."""
    service = EmotionEventService(test_session)
    created = await service.create_event(
        EmotionEventCreate(
            character_id="aevum",
            event_type=EmotionEventType.INTERNAL_STATE,
            summary="Feeling slightly low energy in the afternoon.",
        )
    )
    assert created is not None

    deleted = await service.delete_event(created.id)
    assert deleted is True

    # Confirm it's gone
    retrieved = await service.get_event(created.id)
    assert retrieved is None

    # Deleting again returns False
    deleted_again = await service.delete_event(created.id)
    assert deleted_again is False


# ==============================================================================
# 5. Database Schema & Cascade Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_database_table_and_columns(test_session: AsyncSession):
    """Verify emotion_events table exists with exact column names and expected types."""
    assert "emotion_events" in Base.metadata.tables
    table = Base.metadata.tables["emotion_events"]
    col_names = {c.name for c in table.columns}
    expected_cols = {
        "id",
        "character_id",
        "event_type",
        "summary",
        "source",
        "emotional_relevance",
        "created_at",
    }
    assert expected_cols.issubset(col_names)

    # Verify live SQLite table schema via PRAGMA table_info
    res = await test_session.execute(text("PRAGMA table_info(emotion_events)"))
    pragma_cols = {row[1] for row in res.fetchall()}
    assert expected_cols.issubset(pragma_cols)


@pytest.mark.asyncio
async def test_character_cascade_deletion(test_session: AsyncSession):
    """Deleting the parent CharacterDefinitionRecord cascades to emotion_events."""
    char_service = CharacterDefinitionService(test_session)
    char = await char_service.get_character("aevum")

    event_service = EmotionEventService(test_session)
    event = await event_service.create_event(
        EmotionEventCreate(
            character_id="aevum",
            event_type=EmotionEventType.LIFE_EVENT,
            summary="Rainy weather outside.",
        )
    )
    assert event is not None

    # Verify event record exists in SQLite
    stmt = select(EmotionEventRecord).where(EmotionEventRecord.id == event.id)
    record = (await test_session.scalars(stmt)).first()
    assert record is not None

    # Delete character definition
    char_stmt = select(CharacterDefinitionRecord).where(CharacterDefinitionRecord.id == "aevum")
    char_record = (await test_session.scalars(char_stmt)).first()
    assert char_record is not None

    await test_session.delete(char_record)
    await test_session.commit()

    # Verify emotion event was cascade deleted
    post_delete_rec = (await test_session.scalars(stmt)).first()
    assert post_delete_rec is None


# ==============================================================================
# 6. Architectural Invariance Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_creating_event_does_not_mutate_emotion_state(test_session: AsyncSession):
    """Recording an EmotionEvent leaves EmotionState completely untouched."""
    emotion_service = EmotionService(test_session)
    initial_emotion = await emotion_service.get_emotion_state("aevum")
    assert initial_emotion.version == 1
    assert initial_emotion.emotion_type == EmotionType.NEUTRAL
    assert initial_emotion.intensity == 0.50

    # Create an emotion event
    event_service = EmotionEventService(test_session)
    await event_service.create_event(
        EmotionEventCreate(
            character_id="aevum",
            event_type=EmotionEventType.USER_INTERACTION,
            summary="User gave a warm compliment.",
            emotional_relevance=0.85,
        )
    )

    # Verify EmotionState is completely unchanged
    current_emotion = await emotion_service.get_emotion_state("aevum")
    assert current_emotion.version == 1
    assert current_emotion.emotion_type == EmotionType.NEUTRAL
    assert current_emotion.intensity == 0.50
    assert current_emotion.updated_at == initial_emotion.updated_at


@pytest.mark.asyncio
async def test_creating_event_does_not_mutate_character_state(test_session: AsyncSession):
    """Recording an EmotionEvent leaves CharacterState completely untouched."""
    char_state_service = CharacterStateService(test_session)
    initial_state = await char_state_service.get_state("aevum")
    assert initial_state.version == 1

    event_service = EmotionEventService(test_session)
    await event_service.create_event(
        EmotionEventCreate(
            character_id="aevum",
            event_type=EmotionEventType.LIFE_EVENT,
            summary="Exhausting physical workout.",
            emotional_relevance=0.90,
        )
    )

    current_state = await char_state_service.get_state("aevum")
    assert current_state.version == 1
    assert current_state.energy == initial_state.energy
    assert current_state.stress == initial_state.stress
    assert current_state.updated_at == initial_state.updated_at


@pytest.mark.asyncio
async def test_creating_event_does_not_mutate_relationship_state(test_session: AsyncSession):
    """Recording an EmotionEvent leaves RelationshipState completely untouched."""
    rel_service = RelationshipService(test_session)
    initial_rel = await rel_service.get_relationship_state()
    assert initial_rel.version == 1

    event_service = EmotionEventService(test_session)
    await event_service.create_event(
        EmotionEventCreate(
            character_id="aevum",
            event_type=EmotionEventType.RELATIONSHIP_EVENT,
            summary="User remembered Aevum's birthday.",
            emotional_relevance=0.95,
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
async def test_no_public_emotion_event_endpoint(client: AsyncClient):
    """Verify there are no public HTTP endpoints that allow mutating EmotionEvent records."""
    openapi_paths = list(app.openapi().get("paths", {}).keys())
    event_routes = [p for p in openapi_paths if "event" in p.lower() or "emotion" in p.lower()]
    assert not event_routes, f"Prohibited public emotion/event routes detected: {event_routes}"

    resp_post = await client.post(
        "/emotion/events",
        json={"event_type": "USER_INTERACTION", "summary": "Hello"},
    )
    assert resp_post.status_code == 404

    resp_get = await client.get("/emotion/events")
    assert resp_get.status_code == 404
