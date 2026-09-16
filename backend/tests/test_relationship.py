"""Comprehensive test suite for Phase 4.1: Relationship Foundation.

Verifies:
- Bootstrap initialization and default values.
- Metric validation (0.0, 0.5, 1.0 valid; bounds, NaN, Inf rejected).
- Immutability and extra field forbidding.
- Partial update model (single-field, multi-field, empty rejection).
- Persistence across sessions and version incrementing.
- Optimistic concurrency control and conflict error handling.
- Atomicity on update failure.
- Complete domain separation from CharacterState, Memory, and Emotion.
- Absence of romance booleans, jealousy, or single relationship score.
- Read-only guarantees for get operations.
- Absence of implicit relationship progression during conversation messaging.
"""

from datetime import datetime, timezone
import math
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.state_service import CharacterStateService
from app.db.models import RelationshipRecord
from app.relationship import (
    BOOTSTRAP_AFFECTION,
    BOOTSTRAP_ATTACHMENT,
    BOOTSTRAP_COMFORT,
    BOOTSTRAP_FAMILIARITY,
    BOOTSTRAP_RESPECT,
    BOOTSTRAP_TRUST,
    DEFAULT_RELATIONSHIP_ID,
    DEFAULT_USER_ID,
    RelationshipConflictError,
    RelationshipService,
    RelationshipState,
    RelationshipStateUpdate,
    apply_relationship_update,
    create_initial_relationship_state,
    get_relationship_state,
    update_relationship_state,
)
from tests.conftest import FakeLLMProvider


# =============================================================================
# 1. Bootstrap Tests
# =============================================================================


def test_initial_relationship_state_constructor():
    """Initial relationship state factory produces expected bootstrap baseline."""
    state = create_initial_relationship_state()
    assert state.id == DEFAULT_RELATIONSHIP_ID
    assert state.user_id == DEFAULT_USER_ID
    assert state.version == 1
    assert state.familiarity == BOOTSTRAP_FAMILIARITY  # 0.05
    assert state.trust == BOOTSTRAP_TRUST              # 0.20
    assert state.comfort == BOOTSTRAP_COMFORT          # 0.10
    assert state.affection == BOOTSTRAP_AFFECTION      # 0.00 (no romantic bias)
    assert state.attachment == BOOTSTRAP_ATTACHMENT    # 0.00
    assert state.respect == BOOTSTRAP_RESPECT          # 0.50 (positive baseline)
    assert isinstance(state.created_at, datetime)
    assert isinstance(state.updated_at, datetime)


@pytest.mark.asyncio
async def test_relationship_service_seeds_initial_state_on_empty_db(test_session: AsyncSession):
    """Calling get_relationship_state on an empty database seeds deterministic initial state."""
    service = RelationshipService(test_session)
    state = await service.get_relationship_state()

    assert state.id == DEFAULT_RELATIONSHIP_ID
    assert state.user_id == DEFAULT_USER_ID
    assert state.version == 1
    assert state.familiarity == 0.05
    assert state.trust == 0.20
    assert state.comfort == 0.10
    assert state.affection == 0.00
    assert state.attachment == 0.00
    assert state.respect == 0.50

    # Verify directly in database
    record = (await test_session.scalars(select(RelationshipRecord))).first()
    assert record is not None
    assert record.id == DEFAULT_RELATIONSHIP_ID
    assert record.version == 1


# =============================================================================
# 2. Validation Tests
# =============================================================================


@pytest.mark.parametrize("val", [0.0, 0.5, 1.0])
def test_relationship_state_accepts_valid_boundary_metrics(val: float):
    """0.0, 0.5, and 1.0 are valid metrics for all relational dimensions."""
    now = datetime.now(timezone.utc)
    state = RelationshipState(
        id="test",
        user_id="user",
        version=1,
        created_at=now,
        updated_at=now,
        familiarity=val,
        trust=val,
        comfort=val,
        affection=val,
        attachment=val,
        respect=val,
    )
    assert state.trust == val
    assert state.affection == val


@pytest.mark.parametrize(
    "invalid_val",
    [-0.01, -1.0, 1.01, 2.0, float("nan"), float("inf"), float("-inf")],
)
def test_relationship_state_rejects_invalid_metrics(invalid_val: float):
    """Negative, >1.0, NaN, and Inf values are strictly rejected."""
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError):
        RelationshipState(
            id="test",
            user_id="user",
            version=1,
            created_at=now,
            updated_at=now,
            familiarity=invalid_val,
            trust=0.5,
            comfort=0.5,
            affection=0.5,
            attachment=0.5,
            respect=0.5,
        )


def test_relationship_state_is_immutable_and_forbids_extra():
    """RelationshipState is frozen and forbids extra fields."""
    now = datetime.now(timezone.utc)
    state = RelationshipState(
        id="test",
        user_id="user",
        version=1,
        created_at=now,
        updated_at=now,
        familiarity=0.1,
        trust=0.2,
        comfort=0.3,
        affection=0.0,
        attachment=0.0,
        respect=0.5,
    )
    with pytest.raises(Exception):
        state.trust = 0.9  # mutating frozen instance

    with pytest.raises(ValueError):
        RelationshipState(
            id="test",
            user_id="user",
            version=1,
            created_at=now,
            updated_at=now,
            familiarity=0.1,
            trust=0.2,
            comfort=0.3,
            affection=0.0,
            attachment=0.0,
            respect=0.5,
            extra_field="disallowed",
        )


# =============================================================================
# 3. Update Model Tests
# =============================================================================


def test_relationship_state_update_single_field():
    """Single-field update is valid."""
    update_data = RelationshipStateUpdate(trust=0.65)
    assert update_data.trust == 0.65
    assert update_data.affection is None
    assert update_data.familiarity is None


def test_relationship_state_update_multi_field():
    """Multi-field update is valid."""
    update_data = RelationshipStateUpdate(
        familiarity=0.30,
        trust=0.75,
        comfort=0.60,
    )
    assert update_data.familiarity == 0.30
    assert update_data.trust == 0.75
    assert update_data.comfort == 0.60
    assert update_data.respect is None


def test_relationship_state_update_rejects_empty():
    """Empty update containing no fields is rejected."""
    with pytest.raises(ValueError, match="at least one field"):
        RelationshipStateUpdate()


@pytest.mark.parametrize(
    "invalid_val",
    [-0.05, 1.20, float("nan"), float("inf")],
)
def test_relationship_state_update_rejects_out_of_bounds(invalid_val: float):
    """Out-of-bounds metrics in update model raise ValueError."""
    with pytest.raises(ValueError):
        RelationshipStateUpdate(trust=invalid_val)


# =============================================================================
# 4. Persistence & Service Tests
# =============================================================================


@pytest.mark.asyncio
async def test_relationship_state_survives_reload(test_session: AsyncSession):
    """Relationship state persists in SQLite and survives service reinstantiation."""
    service1 = RelationshipService(test_session)
    await service1.get_relationship_state()

    # Update trust
    await service1.apply_update(RelationshipStateUpdate(trust=0.45))

    # Re-instantiate service
    service2 = RelationshipService(test_session)
    loaded = await service2.get_relationship_state()
    assert loaded.trust == 0.45
    assert loaded.version == 2
    assert loaded.familiarity == BOOTSTRAP_FAMILIARITY  # preserved unspecified field


@pytest.mark.asyncio
async def test_apply_update_preserves_unspecified_fields(test_session: AsyncSession):
    """Applying a partial update replaces specified target values while preserving others."""
    service = RelationshipService(test_session)
    initial = await service.get_relationship_state()

    # Explicit target update for comfort and affection
    updated = await service.apply_update(
        RelationshipStateUpdate(comfort=0.40, affection=0.15)
    )

    assert updated.comfort == 0.40
    assert updated.affection == 0.15
    # Unspecified fields remain identical to initial baseline
    assert updated.familiarity == initial.familiarity
    assert updated.trust == initial.trust
    assert updated.attachment == initial.attachment
    assert updated.respect == initial.respect
    assert updated.version == 2


@pytest.mark.asyncio
async def test_read_only_access_does_not_mutate_state(test_session: AsyncSession):
    """Repeated get_relationship_state calls do not increment version or change updated_at."""
    service = RelationshipService(test_session)
    state1 = await service.get_relationship_state()
    state2 = await service.get_relationship_state()

    assert state1.version == state2.version
    assert state1.updated_at == state2.updated_at


# =============================================================================
# 5. Optimistic Concurrency & Atomicity Tests
# =============================================================================


@pytest.mark.asyncio
async def test_optimistic_concurrency_success(test_session: AsyncSession):
    """Supplying matching expected_version succeeds and increments version."""
    service = RelationshipService(test_session)
    initial = await service.get_relationship_state()

    updated = await service.apply_update(
        RelationshipStateUpdate(respect=0.85),
        expected_version=1,
    )
    assert updated.respect == 0.85
    assert updated.version == 2


@pytest.mark.asyncio
async def test_optimistic_concurrency_conflict_raises_error(test_session: AsyncSession):
    """Supplying stale expected_version raises RelationshipConflictError."""
    service = RelationshipService(test_session)
    await service.get_relationship_state()  # version 1

    with pytest.raises(RelationshipConflictError) as exc_info:
        await service.apply_update(
            RelationshipStateUpdate(respect=0.90),
            expected_version=99,  # Stale / wrong version
        )

    assert exc_info.value.expected_version == 99
    assert exc_info.value.actual_version == 1

    # Verify state remains completely unmutated
    current = await service.get_relationship_state()
    assert current.version == 1
    assert current.respect == BOOTSTRAP_RESPECT


@pytest.mark.asyncio
async def test_update_relationship_state_full_replacement(test_session: AsyncSession):
    """Updating full RelationshipState replaces state atomically."""
    service = RelationshipService(test_session)
    initial = await service.get_relationship_state()

    now = datetime.now(timezone.utc)
    new_state = RelationshipState(
        id=initial.id,
        user_id=initial.user_id,
        version=initial.version,
        created_at=initial.created_at,
        updated_at=now,
        familiarity=0.35,
        trust=0.55,
        comfort=0.45,
        affection=0.20,
        attachment=0.10,
        respect=0.70,
    )
    saved = await service.update_relationship_state(new_state, expected_version=1)
    assert saved.version == 2
    assert saved.familiarity == 0.35
    assert saved.affection == 0.20


# =============================================================================
# 6. Domain Separation & Architectural Boundaries
# =============================================================================


@pytest.mark.asyncio
async def test_relationship_state_does_not_affect_character_state(test_session: AsyncSession):
    """Modifying RelationshipState does not alter CharacterState in any way."""
    char_service = CharacterStateService(test_session)
    rel_service = RelationshipService(test_session)

    char_initial = await char_service.get_state()
    rel_initial = await rel_service.get_relationship_state()

    # Update relationship
    await rel_service.apply_update(RelationshipStateUpdate(trust=0.80, affection=0.30))

    # Verify character state is intact
    char_after = await char_service.get_state()
    assert char_after.version == char_initial.version
    assert char_after.energy == char_initial.energy
    assert char_after.mood == char_initial.mood


def test_relationship_models_contain_no_romance_or_jealousy_or_emotion_fields():
    """Verify architectural boundaries: no boolean romance flags, no jealousy, no emotion/mood."""
    model_fields = RelationshipState.model_fields.keys()

    # Forbidden fields
    forbidden = [
        "is_girlfriend",
        "is_romantic",
        "is_dating",
        "is_partner",
        "jealousy",
        "relationship_score",
        "relationship_level",
        "mood",
        "stress",
        "irritation",
        "energy",
        "loneliness",
    ]
    for field in forbidden:
        assert field not in model_fields, f"Forbidden field '{field}' found in RelationshipState!"


# =============================================================================
# 7. No Implicit Progression in Conversation Flow
# =============================================================================


@pytest.mark.asyncio
async def test_conversation_messages_do_not_alter_relationship_state(
    client: AsyncClient,
    test_session: AsyncSession,
    fake_provider: FakeLLMProvider,
):
    """Creating conversations and sending user messages does NOT mutate relationship state."""
    rel_service = RelationshipService(test_session)
    rel_initial = await rel_service.get_relationship_state()

    # User speaks warmly
    conv_res = await client.post("/conversations")
    conv_id = conv_res.json()["id"]

    fake_provider.response_text = "I am glad to chat with you."
    msg_res = await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "I really like you Aevum, thank you for being here!"},
    )
    assert msg_res.status_code == 201

    # Check relationship state: must remain strictly unchanged
    rel_after = await rel_service.get_relationship_state()
    assert rel_after.version == rel_initial.version
    assert rel_after.updated_at == rel_initial.updated_at
    assert rel_after.trust == rel_initial.trust
    assert rel_after.affection == rel_initial.affection
    assert rel_after.familiarity == rel_initial.familiarity


# =============================================================================
# 8. Convenience Functions Tests
# =============================================================================


@pytest.mark.asyncio
async def test_convenience_functions(test_session: AsyncSession):
    """Module-level convenience functions execute properly."""
    state = await get_relationship_state(test_session)
    assert state.version == 1

    updated = await apply_relationship_update(
        test_session,
        RelationshipStateUpdate(comfort=0.55),
        expected_version=1,
    )
    assert updated.comfort == 0.55
    assert updated.version == 2

    state_obj = RelationshipState(
        id=updated.id,
        user_id=updated.user_id,
        version=updated.version,
        created_at=updated.created_at,
        updated_at=datetime.now(timezone.utc),
        familiarity=0.2,
        trust=0.3,
        comfort=0.4,
        affection=0.0,
        attachment=0.0,
        respect=0.6,
    )
    updated2 = await update_relationship_state(test_session, state_obj, expected_version=2)
    assert updated2.version == 3
    assert updated2.respect == 0.6
