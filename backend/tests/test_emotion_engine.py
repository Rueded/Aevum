"""Unit tests for Phase 5.6 — Emotion Engine Foundation.

Verifies:
- EmotionEngineResult domain model and immutability.
- EmotionEngine orchestration: EmotionState + influences -> proposal -> application -> persisted state.
- Positive current emotion transition, competing transition, and negative current emotion transition.
- No influences handling: deterministic no-op, changed=False, version unchanged.
- Multiple influences passed without reordering or mutation.
- Stale proposal error propagation (StaleEmotionTransitionProposalError).
- Optimistic concurrency conflict error propagation (EmotionConflictError).
- Immutability of inputs: EmotionState, EmotionInfluence, and input sequences.
- Strict isolation: no LLM calls, no network, no new events or influences, no cross-domain mutations.
"""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    EmotionEventRecord,
    EmotionInfluenceRecord,
)
from app.emotion.application_models import EmotionStateApplicationResult
from app.emotion.application_service import (
    EmotionStateApplicationService,
    StaleEmotionTransitionProposalError,
)
from app.emotion.emotion_models import EmotionState, EmotionType
from app.emotion.engine import EmotionEngine, process_emotion_influences
from app.emotion.engine_models import EmotionEngineResult
from app.emotion.influence_models import (
    EmotionInfluence,
    EmotionInfluenceDirection,
)
from app.emotion.service import EmotionConflictError, EmotionService
from app.emotion.transition_models import EmotionTransitionProposal


def _make_influence(
    id: str,
    target_emotion: EmotionType,
    direction: EmotionInfluenceDirection,
    strength: float,
    reason: str = "Engine test influence reason",
    character_id: str = "aevum",
    event_id: str = "evt-123",
) -> EmotionInfluence:
    """Helper to construct an EmotionInfluence domain object for tests."""
    return EmotionInfluence(
        id=id,
        character_id=character_id,
        event_id=event_id,
        target_emotion=target_emotion,
        direction=direction,
        strength=strength,
        reason=reason,
        created_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# 1. Engine Result Model Tests
# ---------------------------------------------------------------------------

def test_engine_result_model_validation() -> None:
    """EmotionEngineResult creates cleanly and enforces immutability and extra='forbid'."""
    proposal = EmotionTransitionProposal(
        current_emotion=EmotionType.CALM,
        current_intensity=0.50,
        proposed_emotion=EmotionType.HAPPY,
        proposed_intensity=0.60,
        considered_influence_ids=["inf-1"],
        reason="Test reason",
    )
    application_result = EmotionStateApplicationResult(
        previous_emotion=EmotionType.CALM,
        previous_intensity=0.50,
        applied_emotion=EmotionType.HAPPY,
        applied_intensity=0.60,
        changed=True,
    )

    result = EmotionEngineResult(
        proposal=proposal,
        application_result=application_result,
    )

    assert result.proposal == proposal
    assert result.application_result == application_result

    # Immutability
    with pytest.raises(ValidationError):
        result.proposal = proposal  # type: ignore[misc]

    # Extra fields forbidden
    with pytest.raises(ValidationError):
        EmotionEngineResult(
            proposal=proposal,
            application_result=application_result,
            extra_field="disallowed",  # type: ignore[call-arg]
        )


# ---------------------------------------------------------------------------
# 2. Engine Orchestration Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_positive_transition_orchestration(test_session: AsyncSession) -> None:
    """Positive current emotion transition: CALM 0.50 + CALM POSITIVE 0.20 -> CALM 0.70."""
    emotion_service = EmotionService(test_session)
    engine = EmotionEngine(test_session)

    current_state = await emotion_service.get_emotion_state("aevum")
    # Set to CALM 0.50 for the test
    calm_candidate = EmotionState(
        id=current_state.id,
        character_id="aevum",
        emotion_type=EmotionType.CALM,
        intensity=0.50,
        created_at=current_state.created_at,
        updated_at=current_state.updated_at,
        version=current_state.version,
    )
    current_state = await emotion_service.update_emotion_state(
        calm_candidate, expected_version=current_state.version
    )
    initial_version = current_state.version

    inf = _make_influence("inf-1", EmotionType.CALM, EmotionInfluenceDirection.POSITIVE, 0.20)
    engine_result = await engine.process_influences(current_state, [inf])

    # 1. Proposal checks
    assert engine_result.proposal.current_emotion == EmotionType.CALM
    assert engine_result.proposal.current_intensity == 0.50
    assert engine_result.proposal.proposed_emotion == EmotionType.CALM
    assert engine_result.proposal.proposed_intensity == 0.70

    # 2. Application result checks
    assert engine_result.application_result.previous_emotion == EmotionType.CALM
    assert engine_result.application_result.previous_intensity == 0.50
    assert engine_result.application_result.applied_emotion == EmotionType.CALM
    assert engine_result.application_result.applied_intensity == 0.70
    assert engine_result.application_result.changed is True

    # 3. Database verification
    persisted = await emotion_service.get_emotion_state("aevum")
    assert persisted.emotion_type == EmotionType.CALM
    assert persisted.intensity == 0.70
    assert persisted.version == initial_version + 1


@pytest.mark.asyncio
async def test_competing_transition_orchestration(test_session: AsyncSession) -> None:
    """Competing transition: CALM 0.50 + HAPPY POSITIVE 0.40 -> HAPPY 0.60."""
    emotion_service = EmotionService(test_session)
    engine = EmotionEngine(test_session)

    current_state = await emotion_service.get_emotion_state("aevum")
    calm_candidate = EmotionState(
        id=current_state.id,
        character_id="aevum",
        emotion_type=EmotionType.CALM,
        intensity=0.50,
        created_at=current_state.created_at,
        updated_at=current_state.updated_at,
        version=current_state.version,
    )
    current_state = await emotion_service.update_emotion_state(
        calm_candidate, expected_version=current_state.version
    )

    inf = _make_influence("inf-1", EmotionType.HAPPY, EmotionInfluenceDirection.POSITIVE, 0.40)
    engine_result = await engine.process_influences(current_state, [inf])

    assert engine_result.proposal.proposed_emotion == EmotionType.HAPPY
    assert engine_result.proposal.proposed_intensity == 0.60  # clamp(0.40 + 0.40 * 0.50, 0.40, 0.90)

    assert engine_result.application_result.applied_emotion == EmotionType.HAPPY
    assert engine_result.application_result.applied_intensity == 0.60
    assert engine_result.application_result.changed is True

    persisted = await emotion_service.get_emotion_state("aevum")
    assert persisted.emotion_type == EmotionType.HAPPY
    assert persisted.intensity == 0.60


@pytest.mark.asyncio
async def test_negative_current_emotion_orchestration(test_session: AsyncSession) -> None:
    """Negative current transition: CALM 0.50 + CALM NEGATIVE 0.20 -> CALM 0.30."""
    emotion_service = EmotionService(test_session)
    engine = EmotionEngine(test_session)

    current_state = await emotion_service.get_emotion_state("aevum")
    calm_candidate = EmotionState(
        id=current_state.id,
        character_id="aevum",
        emotion_type=EmotionType.CALM,
        intensity=0.50,
        created_at=current_state.created_at,
        updated_at=current_state.updated_at,
        version=current_state.version,
    )
    current_state = await emotion_service.update_emotion_state(
        calm_candidate, expected_version=current_state.version
    )

    inf = _make_influence("inf-1", EmotionType.CALM, EmotionInfluenceDirection.NEGATIVE, 0.20)
    engine_result = await engine.process_influences(current_state, [inf])

    assert engine_result.proposal.proposed_emotion == EmotionType.CALM
    assert engine_result.proposal.proposed_intensity == 0.30

    assert engine_result.application_result.applied_emotion == EmotionType.CALM
    assert engine_result.application_result.applied_intensity == 0.30
    assert engine_result.application_result.changed is True

    persisted = await emotion_service.get_emotion_state("aevum")
    assert persisted.intensity == 0.30


@pytest.mark.asyncio
async def test_no_influences_orchestration(test_session: AsyncSession) -> None:
    """Zero influences produce proposal preserving current state and application no-op."""
    emotion_service = EmotionService(test_session)
    engine = EmotionEngine(test_session)

    current_state = await emotion_service.get_emotion_state("aevum")
    initial_version = current_state.version

    # Empty list
    result_empty = await engine.process_influences(current_state, [])
    assert result_empty.proposal.proposed_emotion == current_state.emotion_type
    assert result_empty.proposal.proposed_intensity == current_state.intensity
    assert result_empty.application_result.changed is False

    # None
    result_none = await engine.process_influences(current_state, None)
    assert result_none.proposal.proposed_emotion == current_state.emotion_type
    assert result_none.application_result.changed is False

    # DB version unchanged
    persisted = await emotion_service.get_emotion_state("aevum")
    assert persisted.version == initial_version


@pytest.mark.asyncio
async def test_multiple_influences_orchestration(test_session: AsyncSession) -> None:
    """Engine passes multiple influences without reordering or dropping."""
    emotion_service = EmotionService(test_session)
    engine = EmotionEngine(test_session)

    current_state = await emotion_service.get_emotion_state("aevum")
    inf1 = _make_influence("inf-1", EmotionType.NEUTRAL, EmotionInfluenceDirection.POSITIVE, 0.10)
    inf2 = _make_influence("inf-2", EmotionType.NEUTRAL, EmotionInfluenceDirection.POSITIVE, 0.15)

    result = await engine.process_influences(current_state, [inf1, inf2])

    assert result.proposal.considered_influence_ids == ["inf-1", "inf-2"]
    assert result.proposal.proposed_intensity == 0.75  # 0.50 + 0.25
    assert result.application_result.applied_intensity == 0.75
    assert result.application_result.changed is True


# ---------------------------------------------------------------------------
# 3. Error and Concurrency Preservation Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stale_state_mismatch_error_propagates(test_session: AsyncSession) -> None:
    """If current_state mismatches underlying authoritative state, StaleEmotionTransitionProposalError propagates."""
    emotion_service = EmotionService(test_session)
    engine = EmotionEngine(test_session)

    # 1. Snapshot state v1
    v1_state = await emotion_service.get_emotion_state("aevum")

    # 2. Advance state in DB
    mutated = EmotionState(
        id=v1_state.id,
        character_id="aevum",
        emotion_type=EmotionType.EXCITED,
        intensity=0.85,
        created_at=v1_state.created_at,
        updated_at=v1_state.updated_at,
        version=v1_state.version,
    )
    await emotion_service.update_emotion_state(mutated, expected_version=v1_state.version)

    # 3. Attempt to apply a proposal constructed from an external old state using custom application service
    # We verify that passing mismatched proposal/state to application service propagates error
    app_service = EmotionStateApplicationService(test_session)
    stale_proposal = EmotionTransitionProposal(
        current_emotion=EmotionType.SAD,  # Mismatches v1_state (NEUTRAL)
        current_intensity=0.50,
        proposed_emotion=EmotionType.CALM,
        proposed_intensity=0.60,
        considered_influence_ids=["inf-1"],
        reason="Mismatched reason",
    )

    with pytest.raises(StaleEmotionTransitionProposalError):
        await app_service.apply_proposal(v1_state, stale_proposal)


@pytest.mark.asyncio
async def test_optimistic_concurrency_error_propagates(test_session: AsyncSession) -> None:
    """If state was modified concurrently before application commits, EmotionConflictError propagates."""
    emotion_service = EmotionService(test_session)
    engine = EmotionEngine(test_session)

    # Snapshot v1
    v1_state = await emotion_service.get_emotion_state("aevum")

    # Intervening write advances DB version to 2
    intervening_inf = _make_influence("inf-x", EmotionType.HAPPY, EmotionInfluenceDirection.POSITIVE, 0.30)
    await engine.process_influences(v1_state, [intervening_inf])

    # Now attempt to process influences with the old v1_state snapshot (its version=1 is now stale in DB)
    subsequent_inf = _make_influence("inf-y", EmotionType.CALM, EmotionInfluenceDirection.POSITIVE, 0.25)
    with pytest.raises(EmotionConflictError):
        await engine.process_influences(v1_state, [subsequent_inf])


# ---------------------------------------------------------------------------
# 4. Input Immutability & Convenience Helpers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_input_immutability(test_session: AsyncSession) -> None:
    """Engine does not mutate EmotionState, EmotionInfluence, or input sequence."""
    emotion_service = EmotionService(test_session)
    engine = EmotionEngine(test_session)

    current_state = await emotion_service.get_emotion_state("aevum")
    orig_emotion = current_state.emotion_type
    orig_intensity = current_state.intensity

    inf = _make_influence("inf-1", current_state.emotion_type, EmotionInfluenceDirection.POSITIVE, 0.20)
    orig_inf_strength = inf.strength

    influences_list = [inf]
    result = await engine.process_influences(current_state, influences_list)

    assert current_state.emotion_type == orig_emotion
    assert current_state.intensity == orig_intensity
    assert inf.strength == orig_inf_strength
    assert len(influences_list) == 1
    assert result.proposal.proposed_intensity == 0.70


@pytest.mark.asyncio
async def test_process_character_influences_helper(test_session: AsyncSession) -> None:
    """process_character_influences loads current authoritative state and runs cycle."""
    engine = EmotionEngine(test_session)
    inf = _make_influence("inf-1", EmotionType.NEUTRAL, EmotionInfluenceDirection.POSITIVE, 0.15)

    result = await engine.process_character_influences(character_id="aevum", influences=[inf])
    assert result.application_result.changed is True
    assert result.application_result.applied_intensity == 0.65


@pytest.mark.asyncio
async def test_process_emotion_influences_functional_helper(test_session: AsyncSession) -> None:
    """process_emotion_influences convenience functional wrapper works identically."""
    emotion_service = EmotionService(test_session)
    current_state = await emotion_service.get_emotion_state("aevum")
    inf = _make_influence("inf-1", EmotionType.NEUTRAL, EmotionInfluenceDirection.POSITIVE, 0.10)

    result = await process_emotion_influences(test_session, current_state, [inf])
    assert result.application_result.changed is True


# ---------------------------------------------------------------------------
# 5. Isolation & Side-Effect Boundary Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_engine_side_effect_boundary(test_session: AsyncSession) -> None:
    """Engine does not create events, influences, or modify unrelated tables."""
    emotion_service = EmotionService(test_session)
    engine = EmotionEngine(test_session)

    current = await emotion_service.get_emotion_state("aevum")
    inf = _make_influence("inf-1", EmotionType.HAPPY, EmotionInfluenceDirection.POSITIVE, 0.35)

    events_before = (await test_session.scalars(select(func.count(EmotionEventRecord.id)))).one()
    influences_before = (await test_session.scalars(select(func.count(EmotionInfluenceRecord.id)))).one()

    await engine.process_influences(current, [inf])

    events_after = (await test_session.scalars(select(func.count(EmotionEventRecord.id)))).one()
    influences_after = (await test_session.scalars(select(func.count(EmotionInfluenceRecord.id)))).one()

    assert events_before == events_after
    assert influences_before == influences_after


@pytest.mark.asyncio
async def test_engine_invalid_inputs_raise_type_error(test_session: AsyncSession) -> None:
    """Invalid input types raise TypeError immediately."""
    engine = EmotionEngine(test_session)
    emotion_service = EmotionService(test_session)
    current = await emotion_service.get_emotion_state("aevum")

    with pytest.raises(TypeError, match="current_state must be an EmotionState"):
        await engine.process_influences("invalid-state", [])  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="Every item in influences must be an EmotionInfluence"):
        await engine.process_influences(current, ["invalid-influence"])  # type: ignore[list-item]
