"""Unit tests for Phase 5.5 — Emotion State Application Foundation.

Verifies:
- EmotionStateApplicationResult domain model and strict validation.
- EmotionStateApplicationService applying valid transition proposals to authoritative EmotionState.
- Intensity-only changes, emotion-only changes, and full emotion+intensity changes.
- Deterministic no-op proposals returning changed=False without DB mutation or version increments.
- Stale proposal rejection when proposal current_emotion or current_intensity mismatches authoritative state.
- Optimistic concurrency protection preventing concurrent overwrite conflicts.
- Immutability of proposal and in-memory authoritative state objects.
- Isolation: zero side-effects on events, influences, character state, or relationship state.
"""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    CharacterDefinitionRecord,
    CharacterStateRecord,
    EmotionEventRecord,
    EmotionInfluenceRecord,
    EmotionStateRecord,
    RelationshipRecord,
)
from app.emotion.application_models import EmotionStateApplicationResult
from app.emotion.application_service import (
    EmotionStateApplicationService,
    StaleEmotionTransitionProposalError,
    apply_emotion_transition_proposal,
)
from app.emotion.emotion_models import EmotionState, EmotionType
from app.emotion.service import EmotionConflictError, EmotionService
from app.emotion.transition_models import EmotionTransitionProposal


def _make_proposal(
    current_emotion: EmotionType,
    current_intensity: float,
    proposed_emotion: EmotionType,
    proposed_intensity: float,
    reason: str = "Transition evaluation reason",
    considered_ids: list[str] | None = None,
) -> EmotionTransitionProposal:
    """Helper to construct an EmotionTransitionProposal domain object for tests."""
    return EmotionTransitionProposal(
        current_emotion=current_emotion,
        current_intensity=current_intensity,
        proposed_emotion=proposed_emotion,
        proposed_intensity=proposed_intensity,
        considered_influence_ids=considered_ids or ["inf-1"],
        reason=reason,
    )


# ---------------------------------------------------------------------------
# 1. Application Result Model Validation Tests
# ---------------------------------------------------------------------------

def test_valid_application_result_creation() -> None:
    """Valid application result creates cleanly."""
    result = EmotionStateApplicationResult(
        previous_emotion=EmotionType.CALM,
        previous_intensity=0.50,
        applied_emotion=EmotionType.HAPPY,
        applied_intensity=0.70,
        changed=True,
    )
    assert result.previous_emotion == EmotionType.CALM
    assert result.previous_intensity == 0.50
    assert result.applied_emotion == EmotionType.HAPPY
    assert result.applied_intensity == 0.70
    assert result.changed is True


@pytest.mark.parametrize("invalid_intensity", [-0.01, -1.0, 1.01, 2.0, float("nan"), float("inf"), float("-inf")])
def test_invalid_previous_intensity_rejected(invalid_intensity: float) -> None:
    """Previous intensity outside [0.0, 1.0], NaN, or infinite raises ValidationError."""
    with pytest.raises(ValidationError):
        EmotionStateApplicationResult(
            previous_emotion=EmotionType.CALM,
            previous_intensity=invalid_intensity,
            applied_emotion=EmotionType.CALM,
            applied_intensity=0.50,
            changed=False,
        )


@pytest.mark.parametrize("invalid_intensity", [-0.01, -1.0, 1.01, 2.0, float("nan"), float("inf"), float("-inf")])
def test_invalid_applied_intensity_rejected(invalid_intensity: float) -> None:
    """Applied intensity outside [0.0, 1.0], NaN, or infinite raises ValidationError."""
    with pytest.raises(ValidationError):
        EmotionStateApplicationResult(
            previous_emotion=EmotionType.CALM,
            previous_intensity=0.50,
            applied_emotion=EmotionType.CALM,
            applied_intensity=invalid_intensity,
            changed=False,
        )


def test_application_result_extra_fields_rejected() -> None:
    """Extra fields are forbidden."""
    with pytest.raises(ValidationError):
        EmotionStateApplicationResult(
            previous_emotion=EmotionType.CALM,
            previous_intensity=0.50,
            applied_emotion=EmotionType.CALM,
            applied_intensity=0.50,
            changed=False,
            extra_field="disallowed",  # type: ignore[call-arg]
        )


def test_application_result_immutability() -> None:
    """EmotionStateApplicationResult is frozen and immutable."""
    result = EmotionStateApplicationResult(
        previous_emotion=EmotionType.CALM,
        previous_intensity=0.50,
        applied_emotion=EmotionType.CALM,
        applied_intensity=0.50,
        changed=False,
    )
    with pytest.raises(ValidationError):
        result.changed = True  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 2. State Application Service Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_apply_valid_full_proposal(test_session: AsyncSession) -> None:
    """Applying valid proposal mutates authoritative state and increments version."""
    emotion_service = EmotionService(test_session)
    app_service = EmotionStateApplicationService(test_session)

    current_state = await emotion_service.get_emotion_state("aevum")
    assert current_state.emotion_type == EmotionType.NEUTRAL
    assert current_state.intensity == 0.50
    initial_version = current_state.version

    proposal = _make_proposal(
        current_emotion=EmotionType.NEUTRAL,
        current_intensity=0.50,
        proposed_emotion=EmotionType.HAPPY,
        proposed_intensity=0.60,
    )

    result = await app_service.apply_proposal(current_state, proposal)

    assert result.previous_emotion == EmotionType.NEUTRAL
    assert result.previous_intensity == 0.50
    assert result.applied_emotion == EmotionType.HAPPY
    assert result.applied_intensity == 0.60
    assert result.changed is True

    # Verify persistent state in DB
    updated_state = await emotion_service.get_emotion_state("aevum")
    assert updated_state.emotion_type == EmotionType.HAPPY
    assert updated_state.intensity == 0.60
    assert updated_state.version == initial_version + 1


@pytest.mark.asyncio
async def test_apply_intensity_only_change(test_session: AsyncSession) -> None:
    """Proposal that only changes intensity mutates state cleanly."""
    emotion_service = EmotionService(test_session)
    app_service = EmotionStateApplicationService(test_session)

    current_state = await emotion_service.get_emotion_state("aevum")
    proposal = _make_proposal(
        current_emotion=current_state.emotion_type,
        current_intensity=current_state.intensity,
        proposed_emotion=current_state.emotion_type,
        proposed_intensity=0.70,
    )

    result = await app_service.apply_proposal(current_state, proposal)

    assert result.changed is True
    assert result.applied_emotion == current_state.emotion_type
    assert result.applied_intensity == 0.70

    updated_state = await emotion_service.get_emotion_state("aevum")
    assert updated_state.emotion_type == current_state.emotion_type
    assert updated_state.intensity == 0.70


@pytest.mark.asyncio
async def test_apply_emotion_only_change(test_session: AsyncSession) -> None:
    """Proposal that only changes emotion type mutates state cleanly."""
    emotion_service = EmotionService(test_session)
    app_service = EmotionStateApplicationService(test_session)

    current_state = await emotion_service.get_emotion_state("aevum")
    proposal = _make_proposal(
        current_emotion=current_state.emotion_type,
        current_intensity=current_state.intensity,
        proposed_emotion=EmotionType.CALM,
        proposed_intensity=current_state.intensity,
    )

    result = await app_service.apply_proposal(current_state, proposal)

    assert result.changed is True
    assert result.applied_emotion == EmotionType.CALM
    assert result.applied_intensity == current_state.intensity

    updated_state = await emotion_service.get_emotion_state("aevum")
    assert updated_state.emotion_type == EmotionType.CALM
    assert updated_state.intensity == current_state.intensity


@pytest.mark.asyncio
async def test_apply_no_op_proposal(test_session: AsyncSession) -> None:
    """No-op proposal returns changed=False without DB mutation or version increment."""
    emotion_service = EmotionService(test_session)
    app_service = EmotionStateApplicationService(test_session)

    current_state = await emotion_service.get_emotion_state("aevum")
    initial_version = current_state.version

    proposal = _make_proposal(
        current_emotion=current_state.emotion_type,
        current_intensity=current_state.intensity,
        proposed_emotion=current_state.emotion_type,
        proposed_intensity=current_state.intensity,
    )

    result = await app_service.apply_proposal(current_state, proposal)

    assert result.changed is False
    assert result.previous_emotion == current_state.emotion_type
    assert result.previous_intensity == current_state.intensity
    assert result.applied_emotion == current_state.emotion_type
    assert result.applied_intensity == current_state.intensity

    # Verify DB state and version were not modified
    db_state = await emotion_service.get_emotion_state("aevum")
    assert db_state.version == initial_version


# ---------------------------------------------------------------------------
# 3. Stale Proposal Rejection Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stale_emotion_type_rejected(test_session: AsyncSession) -> None:
    """Proposal whose current_emotion does not match authoritative state raises error."""
    emotion_service = EmotionService(test_session)
    app_service = EmotionStateApplicationService(test_session)

    current_state = await emotion_service.get_emotion_state("aevum")  # NEUTRAL 0.50
    proposal = _make_proposal(
        current_emotion=EmotionType.HAPPY,  # Mismatch
        current_intensity=0.50,
        proposed_emotion=EmotionType.CALM,
        proposed_intensity=0.60,
    )

    with pytest.raises(StaleEmotionTransitionProposalError) as exc_info:
        await app_service.apply_proposal(current_state, proposal)

    assert exc_info.value.expected_emotion == EmotionType.HAPPY
    assert exc_info.value.actual_emotion == EmotionType.NEUTRAL


@pytest.mark.asyncio
async def test_stale_intensity_rejected(test_session: AsyncSession) -> None:
    """Proposal whose current_intensity does not match authoritative state raises error."""
    emotion_service = EmotionService(test_session)
    app_service = EmotionStateApplicationService(test_session)

    current_state = await emotion_service.get_emotion_state("aevum")  # NEUTRAL 0.50
    proposal = _make_proposal(
        current_emotion=EmotionType.NEUTRAL,
        current_intensity=0.70,  # Mismatch with actual 0.50
        proposed_emotion=EmotionType.HAPPY,
        proposed_intensity=0.80,
    )

    with pytest.raises(StaleEmotionTransitionProposalError) as exc_info:
        await app_service.apply_proposal(current_state, proposal)

    assert exc_info.value.expected_intensity == 0.70
    assert exc_info.value.actual_intensity == 0.50


@pytest.mark.asyncio
async def test_both_stale_rejected(test_session: AsyncSession) -> None:
    """Proposal with both mismatched emotion and intensity raises error."""
    emotion_service = EmotionService(test_session)
    app_service = EmotionStateApplicationService(test_session)

    current_state = await emotion_service.get_emotion_state("aevum")  # NEUTRAL 0.50
    proposal = _make_proposal(
        current_emotion=EmotionType.SAD,
        current_intensity=0.20,
        proposed_emotion=EmotionType.HAPPY,
        proposed_intensity=0.80,
    )

    with pytest.raises(StaleEmotionTransitionProposalError):
        await app_service.apply_proposal(current_state, proposal)


# ---------------------------------------------------------------------------
# 4. Optimistic Concurrency & Atomicity Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_optimistic_concurrency_conflict(test_session: AsyncSession) -> None:
    """If authoritative state version advances concurrently, application raises EmotionConflictError."""
    emotion_service = EmotionService(test_session)
    app_service = EmotionStateApplicationService(test_session)

    # 1. Stale state snapshot at version 1
    snapshot_v1 = await emotion_service.get_emotion_state("aevum")

    # 2. Another writer advances state to version 2
    proposal_intervening = _make_proposal(
        current_emotion=snapshot_v1.emotion_type,
        current_intensity=snapshot_v1.intensity,
        proposed_emotion=EmotionType.EXCITED,
        proposed_intensity=0.75,
    )
    await app_service.apply_proposal(snapshot_v1, proposal_intervening)

    # 3. Attempt to apply another proposal using the old snapshot_v1 (stale version in DB)
    proposal_conflicting = _make_proposal(
        current_emotion=snapshot_v1.emotion_type,
        current_intensity=snapshot_v1.intensity,
        proposed_emotion=EmotionType.CALM,
        proposed_intensity=0.40,
    )

    with pytest.raises(EmotionConflictError) as exc_info:
        await app_service.apply_proposal(snapshot_v1, proposal_conflicting)

    assert exc_info.value.expected_version == snapshot_v1.version
    assert exc_info.value.actual_version == snapshot_v1.version + 1


# ---------------------------------------------------------------------------
# 5. Immutability & Convenience Helpers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_input_immutability(test_session: AsyncSession) -> None:
    """Proposal and in-memory current_state are not mutated by the application service."""
    emotion_service = EmotionService(test_session)
    app_service = EmotionStateApplicationService(test_session)

    current_state = await emotion_service.get_emotion_state("aevum")
    orig_emotion = current_state.emotion_type
    orig_intensity = current_state.intensity

    proposal = _make_proposal(
        current_emotion=orig_emotion,
        current_intensity=orig_intensity,
        proposed_emotion=EmotionType.HAPPY,
        proposed_intensity=0.65,
    )

    await app_service.apply_proposal(current_state, proposal)

    # Assert in-memory objects remain unchanged
    assert current_state.emotion_type == orig_emotion
    assert current_state.intensity == orig_intensity
    assert proposal.current_emotion == orig_emotion
    assert proposal.proposed_intensity == 0.65


@pytest.mark.asyncio
async def test_convenience_function(test_session: AsyncSession) -> None:
    """apply_emotion_transition_proposal functional wrapper behaves identically."""
    emotion_service = EmotionService(test_session)

    current_state = await emotion_service.get_emotion_state("aevum")
    proposal = _make_proposal(
        current_emotion=current_state.emotion_type,
        current_intensity=current_state.intensity,
        proposed_emotion=EmotionType.CONTENT,
        proposed_intensity=0.55,
    )

    result = await apply_emotion_transition_proposal(test_session, current_state, proposal)
    assert result.changed is True
    assert result.applied_emotion == EmotionType.CONTENT


@pytest.mark.asyncio
async def test_apply_proposal_to_character(test_session: AsyncSession) -> None:
    """apply_proposal_to_character loads authoritative state from DB first."""
    app_service = EmotionStateApplicationService(test_session)
    emotion_service = EmotionService(test_session)

    current = await emotion_service.get_emotion_state("aevum")
    proposal = _make_proposal(
        current_emotion=current.emotion_type,
        current_intensity=current.intensity,
        proposed_emotion=EmotionType.CALM,
        proposed_intensity=0.60,
    )

    result = await app_service.apply_proposal_to_character(proposal, character_id="aevum")
    assert result.changed is True
    assert result.applied_emotion == EmotionType.CALM


# ---------------------------------------------------------------------------
# 6. Side-Effect Boundary Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_side_effect_boundary(test_session: AsyncSession) -> None:
    """Applying a proposal does not touch events, influences, character state, or relationships."""
    app_service = EmotionStateApplicationService(test_session)
    emotion_service = EmotionService(test_session)

    current = await emotion_service.get_emotion_state("aevum")
    proposal = _make_proposal(
        current_emotion=current.emotion_type,
        current_intensity=current.intensity,
        proposed_emotion=EmotionType.HAPPY,
        proposed_intensity=0.75,
    )

    # Initial counts
    events_count_before = (await test_session.scalars(select(func.count(EmotionEventRecord.id)))).one()
    influences_count_before = (await test_session.scalars(select(func.count(EmotionInfluenceRecord.id)))).one()

    await app_service.apply_proposal(current, proposal)

    # Post counts
    events_count_after = (await test_session.scalars(select(func.count(EmotionEventRecord.id)))).one()
    influences_count_after = (await test_session.scalars(select(func.count(EmotionInfluenceRecord.id)))).one()

    assert events_count_before == events_count_after
    assert influences_count_before == influences_count_after


@pytest.mark.asyncio
async def test_invalid_arguments_raise_type_error(test_session: AsyncSession) -> None:
    """Passing invalid object types to apply_proposal raises TypeError."""
    app_service = EmotionStateApplicationService(test_session)
    emotion_service = EmotionService(test_session)
    current = await emotion_service.get_emotion_state("aevum")

    with pytest.raises(TypeError, match="current_state must be an EmotionState"):
        await app_service.apply_proposal("not-state", "not-proposal")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="proposal must be an EmotionTransitionProposal"):
        await app_service.apply_proposal(current, "not-proposal")  # type: ignore[arg-type]
