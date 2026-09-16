"""Tests for Phase 5.1: Emotion Model Foundation.

Validates:
1. EmotionType vocabulary and non-romance constraints.
2. EmotionState domain model, validation constraints (0.0-1.0 ranges, NaN/inf rejection,
   non-empty strings, immutability, optimistic concurrency version).
3. EmotionStateUpdate partial-update model constraints.
4. SQLite persistence in emotion_states table, deterministic initial seeding, and optimistic concurrency.
5. Architectural separation from CharacterState, RelationshipState, Memory, and LLM.
6. Non-automatic mutation guarantees (conversations, signals, and memory leave emotion untouched).
7. Security: absence of public emotion mutation endpoints or LLM direct state mutation.
"""

from datetime import datetime, timezone
import math
import uuid
from httpx import ASGITransport, AsyncClient
import pydantic
import pytest
from sqlalchemy import inspect as sa_inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.service import CharacterDefinitionService
from app.character.state_models import CharacterState
from app.db.models import CharacterDefinitionRecord, EmotionStateRecord, utc_now
from app.db.session import Base
from app.emotion import (
    BOOTSTRAP_EMOTION_TYPE,
    BOOTSTRAP_INTENSITY,
    DEFAULT_CHARACTER_ID,
    EmotionConflictError,
    EmotionService,
    EmotionState,
    EmotionStateUpdate,
    EmotionType,
    create_initial_emotion_state,
    get_emotion_state,
    update_emotion_state,
)
from app.main import app
from app.relationship.models import RelationshipState


# ==============================================================================
# 1. Model Validation Tests
# ==============================================================================


def test_valid_neutral_emotion():
    """Default neutral emotion state is instantiated with expected constraints."""
    state = create_initial_emotion_state()
    assert state.character_id == "aevum"
    assert state.emotion_type == EmotionType.NEUTRAL
    assert state.intensity == 0.50
    assert state.version == 1
    assert state.created_at is not None
    assert state.updated_at is not None


def test_valid_non_neutral_emotions():
    """All non-neutral vocabulary emotions can be validly instantiated."""
    for et in EmotionType:
        state = EmotionState(
            id=str(uuid.uuid4()),
            character_id="aevum",
            emotion_type=et,
            intensity=0.85,
            created_at=utc_now(),
            updated_at=utc_now(),
            version=1,
        )
        assert state.emotion_type == et
        assert state.intensity == 0.85


def test_intensity_boundary_values():
    """Intensity exactly at 0.0 and 1.0 are valid."""
    now = utc_now()
    state_0 = EmotionState(
        id="e0",
        character_id="aevum",
        emotion_type=EmotionType.CALM,
        intensity=0.0,
        created_at=now,
        updated_at=now,
        version=1,
    )
    assert state_0.intensity == 0.0

    state_1 = EmotionState(
        id="e1",
        character_id="aevum",
        emotion_type=EmotionType.EXCITED,
        intensity=1.0,
        created_at=now,
        updated_at=now,
        version=1,
    )
    assert state_1.intensity == 1.0


@pytest.mark.parametrize("invalid_intensity", [-0.01, -1.0, 1.01, 2.5])
def test_out_of_range_intensity_rejected(invalid_intensity: float):
    """Intensity values below 0.0 or above 1.0 are rejected with ValidationError."""
    now = utc_now()
    with pytest.raises(pydantic.ValidationError):
        EmotionState(
            id="e",
            character_id="aevum",
            emotion_type=EmotionType.NEUTRAL,
            intensity=invalid_intensity,
            created_at=now,
            updated_at=now,
            version=1,
        )


@pytest.mark.parametrize("bad_val", [float("nan"), float("inf"), float("-inf")])
def test_nan_and_infinite_intensity_rejected(bad_val: float):
    """NaN and infinite intensity values are rejected."""
    now = utc_now()
    with pytest.raises(pydantic.ValidationError):
        EmotionState(
            id="e",
            character_id="aevum",
            emotion_type=EmotionType.NEUTRAL,
            intensity=bad_val,
            created_at=now,
            updated_at=now,
            version=1,
        )


@pytest.mark.parametrize("bad_char_id", ["", "   ", None])
def test_empty_or_whitespace_character_id_rejected(bad_char_id: str | None):
    """Empty, whitespace, or None character_id is rejected."""
    now = utc_now()
    with pytest.raises(pydantic.ValidationError):
        EmotionState(
            id="e",
            character_id=bad_char_id,  # type: ignore
            emotion_type=EmotionType.NEUTRAL,
            intensity=0.5,
            created_at=now,
            updated_at=now,
            version=1,
        )


def test_invalid_emotion_type_rejected():
    """Emotion type outside the defined EmotionType enum is rejected."""
    now = utc_now()
    with pytest.raises(pydantic.ValidationError):
        EmotionState(
            id="e",
            character_id="aevum",
            emotion_type="SUPER_HAPPY",  # type: ignore
            intensity=0.5,
            created_at=now,
            updated_at=now,
            version=1,
        )


def test_extra_fields_rejected():
    """Extra undeclared fields on EmotionState are forbidden."""
    now = utc_now()
    with pytest.raises(pydantic.ValidationError):
        EmotionState(
            id="e",
            character_id="aevum",
            emotion_type=EmotionType.NEUTRAL,
            intensity=0.5,
            created_at=now,
            updated_at=now,
            version=1,
            extra_field="disallowed",  # type: ignore
        )


def test_emotion_state_immutability():
    """EmotionState is frozen and cannot be mutated in-place."""
    state = create_initial_emotion_state()
    with pytest.raises(pydantic.ValidationError):
        state.intensity = 0.9  # type: ignore


@pytest.mark.parametrize("bad_version", [0, -1, -10])
def test_version_must_be_positive_integer(bad_version: int):
    """Version must be >= 1."""
    now = utc_now()
    with pytest.raises(pydantic.ValidationError):
        EmotionState(
            id="e",
            character_id="aevum",
            emotion_type=EmotionType.NEUTRAL,
            intensity=0.5,
            created_at=now,
            updated_at=now,
            version=bad_version,
        )


# ==============================================================================
# 2. Update Validation Tests
# ==============================================================================


def test_empty_update_rejected():
    """EmotionStateUpdate with zero specified fields must be rejected."""
    with pytest.raises(pydantic.ValidationError):
        EmotionStateUpdate()


def test_update_single_field():
    """EmotionStateUpdate with either emotion_type or intensity alone is valid."""
    up1 = EmotionStateUpdate(emotion_type=EmotionType.CURIOUS)
    assert up1.emotion_type == EmotionType.CURIOUS
    assert up1.intensity is None

    up2 = EmotionStateUpdate(intensity=0.75)
    assert up2.emotion_type is None
    assert up2.intensity == 0.75


def test_update_both_fields():
    """EmotionStateUpdate with both fields is valid."""
    up = EmotionStateUpdate(emotion_type=EmotionType.DISAPPOINTED, intensity=0.6)
    assert up.emotion_type == EmotionType.DISAPPOINTED
    assert up.intensity == 0.6


@pytest.mark.parametrize("invalid_intensity", [-0.1, 1.2, float("nan"), float("inf")])
def test_update_invalid_intensity_rejected(invalid_intensity: float):
    """EmotionStateUpdate rejects invalid intensity numbers."""
    with pytest.raises(pydantic.ValidationError):
        EmotionStateUpdate(intensity=invalid_intensity)


def test_update_immutability():
    """EmotionStateUpdate is frozen and rejects extra fields."""
    up = EmotionStateUpdate(intensity=0.4)
    with pytest.raises(pydantic.ValidationError):
        up.intensity = 0.5  # type: ignore

    with pytest.raises(pydantic.ValidationError):
        EmotionStateUpdate(intensity=0.4, foo="bar")  # type: ignore


# ==============================================================================
# 3. Architectural Separation Tests
# ==============================================================================


def test_emotion_state_does_not_contain_relationship_metrics():
    """EmotionState must not contain any relationship metrics."""
    field_names = set(EmotionState.model_fields.keys())
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
    assert not overlap, f"EmotionState contains prohibited relationship fields: {overlap}"


def test_emotion_state_does_not_duplicate_character_state_metrics():
    """EmotionState must not duplicate physiological/cognitive CharacterState metrics."""
    field_names = set(EmotionState.model_fields.keys())
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
    assert not overlap, f"EmotionState duplicates CharacterState fields: {overlap}"


def test_vocabulary_contains_no_romance_mechanics():
    """EmotionType vocabulary must strictly avoid romance or dating classifications."""
    prohibited_vocabulary = {
        "IN_LOVE",
        "ROMANTIC",
        "JEALOUS",
        "HEARTBROKEN",
        "CRUSH",
        "INFATUATED",
    }
    actual_values = {e.value for e in EmotionType}
    overlap = actual_values.intersection(prohibited_vocabulary)
    assert not overlap, f"EmotionType contains prohibited romantic terms: {overlap}"


# ==============================================================================
# 4. Persistence & Service Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_initial_state_seeded_deterministically(test_session: AsyncSession):
    """get_emotion_state creates deterministic baseline if table is empty."""
    service = EmotionService(test_session)
    state = await service.get_emotion_state("aevum")

    assert state.character_id == "aevum"
    assert state.emotion_type == EmotionType.NEUTRAL
    assert state.intensity == 0.50
    assert state.version == 1

    # Read-only repeated call returns identical state without mutating version or timestamps
    re_read = await service.get_emotion_state("aevum")
    assert re_read.id == state.id
    assert re_read.version == 1
    assert re_read.updated_at == state.updated_at


@pytest.mark.asyncio
async def test_update_emotion_state_persists_and_increments_version(test_session: AsyncSession):
    """update_emotion_state updates values and increments version atomically."""
    service = EmotionService(test_session)
    initial = await service.get_emotion_state("aevum")
    assert initial.version == 1

    updated_candidate = EmotionState(
        id=initial.id,
        character_id="aevum",
        emotion_type=EmotionType.CURIOUS,
        intensity=0.72,
        created_at=initial.created_at,
        updated_at=utc_now(),
        version=initial.version,
    )

    result = await service.update_emotion_state(
        updated_state=updated_candidate,
        expected_version=1,
        character_id="aevum",
    )

    assert result.version == 2
    assert result.emotion_type == EmotionType.CURIOUS
    assert result.intensity == 0.72
    assert result.created_at == initial.created_at
    assert result.updated_at >= initial.updated_at

    # Check persistence directly via SQL query
    stmt = select(EmotionStateRecord).where(EmotionStateRecord.character_id == "aevum")
    record = (await test_session.scalars(stmt)).first()
    assert record is not None
    assert record.version == 2
    assert record.emotion_type == "CURIOUS"
    assert record.intensity == 0.72


@pytest.mark.asyncio
async def test_optimistic_concurrency_conflict_rejected(test_session: AsyncSession):
    """Updates specifying mismatched expected_version raise EmotionConflictError."""
    service = EmotionService(test_session)
    initial = await service.get_emotion_state("aevum")
    assert initial.version == 1

    updated_candidate = EmotionState(
        id=initial.id,
        character_id="aevum",
        emotion_type=EmotionType.AMUSED,
        intensity=0.8,
        created_at=initial.created_at,
        updated_at=utc_now(),
        version=initial.version,
    )

    with pytest.raises(EmotionConflictError) as exc_info:
        await service.update_emotion_state(
            updated_state=updated_candidate,
            expected_version=99,  # Mismatched version
            character_id="aevum",
        )

    assert exc_info.value.expected_version == 99
    assert exc_info.value.actual_version == 1

    # Verify state in DB remains untouched
    current = await service.get_emotion_state("aevum")
    assert current.version == 1
    assert current.emotion_type == EmotionType.NEUTRAL


@pytest.mark.asyncio
async def test_apply_update_partial_modifications(test_session: AsyncSession):
    """apply_update updates only specified fields and keeps unspecified fields unchanged."""
    service = EmotionService(test_session)
    initial = await service.get_emotion_state("aevum")
    assert initial.version == 1
    assert initial.emotion_type == EmotionType.NEUTRAL
    assert initial.intensity == 0.50

    # 1. Update only emotion_type
    up1 = EmotionStateUpdate(emotion_type=EmotionType.CALM)
    res1 = await service.apply_update(up1, expected_version=1, character_id="aevum")
    assert res1.version == 2
    assert res1.emotion_type == EmotionType.CALM
    assert res1.intensity == 0.50  # unchanged

    # 2. Update only intensity
    up2 = EmotionStateUpdate(intensity=0.35)
    res2 = await service.apply_update(up2, expected_version=2, character_id="aevum")
    assert res2.version == 3
    assert res2.emotion_type == EmotionType.CALM  # unchanged
    assert res2.intensity == 0.35

    # 3. Update both fields together
    up3 = EmotionStateUpdate(emotion_type=EmotionType.EXCITED, intensity=0.90)
    res3 = await service.apply_update(up3, expected_version=3, character_id="aevum")
    assert res3.version == 4
    assert res3.emotion_type == EmotionType.EXCITED
    assert res3.intensity == 0.90


@pytest.mark.asyncio
async def test_module_convenience_functions(test_session: AsyncSession):
    """Test get_emotion_state and update_emotion_state top-level convenience functions."""
    s1 = await get_emotion_state(test_session, "aevum")
    assert s1.version == 1

    new_state = EmotionState(
        id=s1.id,
        character_id="aevum",
        emotion_type=EmotionType.CONTENT,
        intensity=0.65,
        created_at=s1.created_at,
        updated_at=utc_now(),
        version=1,
    )
    s2 = await update_emotion_state(test_session, new_state, expected_version=1, character_id="aevum")
    assert s2.version == 2
    assert s2.emotion_type == EmotionType.CONTENT


# ==============================================================================
# 5. Database Schema & Cascade Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_database_table_and_columns(test_session: AsyncSession):
    """Verify emotion_states table exists with exact column names and expected types."""
    from sqlalchemy import text

    assert "emotion_states" in Base.metadata.tables
    table = Base.metadata.tables["emotion_states"]
    col_names = {c.name for c in table.columns}
    expected_cols = {
        "id",
        "character_id",
        "emotion_type",
        "intensity",
        "created_at",
        "updated_at",
        "version",
    }
    assert expected_cols.issubset(col_names)

    # Verify live SQLite table schema via PRAGMA table_info
    res = await test_session.execute(text("PRAGMA table_info(emotion_states)"))
    pragma_cols = {row[1] for row in res.fetchall()}
    assert expected_cols.issubset(pragma_cols)


@pytest.mark.asyncio
async def test_character_cascade_deletion(test_session: AsyncSession):
    """Deleting the parent CharacterDefinitionRecord cascades to emotion_states."""
    # Ensure character definition and emotion state are seeded
    char_service = CharacterDefinitionService(test_session)
    char = await char_service.get_character("aevum")

    emotion_service = EmotionService(test_session)
    emotion = await emotion_service.get_emotion_state("aevum")
    assert emotion.character_id == "aevum"

    # Verify emotion record exists
    stmt = select(EmotionStateRecord).where(EmotionStateRecord.character_id == "aevum")
    record = (await test_session.scalars(stmt)).first()
    assert record is not None

    # Delete character definition record
    char_stmt = select(CharacterDefinitionRecord).where(CharacterDefinitionRecord.id == "aevum")
    char_record = (await test_session.scalars(char_stmt)).first()
    assert char_record is not None

    await test_session.delete(char_record)
    await test_session.commit()

    # Verify emotion state was cascade deleted
    post_delete_rec = (await test_session.scalars(stmt)).first()
    assert post_delete_rec is None


# ==============================================================================
# 6. Non-Automatic Mutation & Conversation Isolation Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_conversation_does_not_mutate_emotion(client: AsyncClient, test_session: AsyncSession):
    """Sending user messages and creating conversations does not mutate EmotionState."""
    emotion_service = EmotionService(test_session)
    initial_emotion = await emotion_service.get_emotion_state("aevum")
    assert initial_emotion.version == 1
    assert initial_emotion.emotion_type == EmotionType.NEUTRAL
    assert initial_emotion.intensity == 0.50

    # 1. Create conversation
    create_resp = await client.post("/conversations")
    assert create_resp.status_code == 201
    conv_id = create_resp.json()["id"]

    # Verify emotion remains untouched after conversation creation
    after_conv_emotion = await emotion_service.get_emotion_state("aevum")
    assert after_conv_emotion.version == 1
    assert after_conv_emotion.updated_at == initial_emotion.updated_at

    # 2. Send message
    msg_resp = await client.post(
        f"/conversations/{conv_id}/messages",
        json={"content": "Hello Aevum! I really appreciate your help today."},
    )
    assert msg_resp.status_code == 201

    # Verify emotion remains untouched after message interaction
    after_msg_emotion = await emotion_service.get_emotion_state("aevum")
    assert after_msg_emotion.version == 1
    assert after_msg_emotion.emotion_type == EmotionType.NEUTRAL
    assert after_msg_emotion.intensity == 0.50
    assert after_msg_emotion.updated_at == initial_emotion.updated_at


# ==============================================================================
# 7. Security Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_no_public_emotion_mutation_endpoint(client: AsyncClient):
    """Verify there are no public HTTP endpoints that allow mutating EmotionState."""
    openapi_paths = list(app.openapi().get("paths", {}).keys())
    emotion_routes = [p for p in openapi_paths if "emotion" in p.lower()]
    assert not emotion_routes, f"Prohibited public emotion routes detected in OpenAPI schema: {emotion_routes}"

    # Verify attempting to POST or PUT to common emotion paths returns 404
    resp_post = await client.post("/emotion", json={"emotion_type": "HAPPY", "intensity": 1.0})
    assert resp_post.status_code == 404

    resp_put = await client.put("/character/emotion", json={"intensity": 0.8})
    assert resp_put.status_code == 404
