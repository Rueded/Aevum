"""Unit tests for Phase 5.4 — Emotion Transition Proposal Foundation.

Verifies:
- EmotionTransitionProposal domain model and strict validations.
- EmotionTransitionEvaluator pure, deterministic transition proposal calculation.
- Positive current-emotion influence aggregation and jump cap (0.30).
- Negative current-emotion influence reduction, floor (0.0), and reduction cap (0.30).
- Balanced mixed current-emotion influences.
- Non-actionable competing negative influences.
- Competing positive influence threshold (>= 0.20), baseline comparison against positive current pressure,
  intensity formula, clamping to [0.40, 0.90], and deterministic tie-breaking.
- Non-lowering of comparison baseline by negative current-emotion pressure.
- Input immutability and side-effect isolation.
- Determinism across repeated evaluations.
"""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.emotion.emotion_models import (
    EmotionState,
    EmotionType,
    create_initial_emotion_state,
)
from app.emotion.influence_models import (
    EmotionInfluence,
    EmotionInfluenceDirection,
)
from app.emotion.transition_evaluator import (
    COMPETING_SWITCH_THRESHOLD,
    MAX_SWITCH_INTENSITY,
    MAX_TRANSITION_MAGNITUDE_PER_EVALUATION,
    MIN_SWITCH_INTENSITY,
    REASON_BALANCED_NO_CHANGE,
    REASON_COMPETING_SWITCH,
    REASON_NEGATIVE_REDUCTION,
    REASON_NO_ACTIONABLE_INFLUENCE,
    REASON_POSITIVE_INCREASE,
    EmotionTransitionEvaluator,
    evaluate_emotion_transition,
)
from app.emotion.transition_models import (
    MAX_TRANSITION_REASON_LENGTH,
    EmotionTransitionProposal,
)


def _make_influence(
    id: str,
    target_emotion: EmotionType,
    direction: EmotionInfluenceDirection,
    strength: float,
    reason: str = "Test influence reason",
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
# 1. Model Validation Tests
# ---------------------------------------------------------------------------

def test_valid_proposal_creation() -> None:
    """Valid proposal initializes cleanly."""
    proposal = EmotionTransitionProposal(
        current_emotion=EmotionType.CALM,
        current_intensity=0.50,
        proposed_emotion=EmotionType.HAPPY,
        proposed_intensity=0.70,
        considered_influence_ids=["inf-1", "inf-2"],
        reason="Test proposal reason.",
    )
    assert proposal.current_emotion == EmotionType.CALM
    assert proposal.current_intensity == 0.50
    assert proposal.proposed_emotion == EmotionType.HAPPY
    assert proposal.proposed_intensity == 0.70
    assert proposal.considered_influence_ids == ["inf-1", "inf-2"]
    assert proposal.reason == "Test proposal reason."


@pytest.mark.parametrize("invalid_intensity", [-0.01, -1.0, 1.01, 2.0, float("nan"), float("inf"), float("-inf")])
def test_invalid_current_intensity_rejected(invalid_intensity: float) -> None:
    """Current intensity outside [0.0, 1.0], NaN, or infinite raises ValidationError."""
    with pytest.raises(ValidationError):
        EmotionTransitionProposal(
            current_emotion=EmotionType.CALM,
            current_intensity=invalid_intensity,
            proposed_emotion=EmotionType.CALM,
            proposed_intensity=0.50,
            reason="Test reason",
        )


@pytest.mark.parametrize("invalid_intensity", [-0.01, -1.0, 1.01, 2.0, float("nan"), float("inf"), float("-inf")])
def test_invalid_proposed_intensity_rejected(invalid_intensity: float) -> None:
    """Proposed intensity outside [0.0, 1.0], NaN, or infinite raises ValidationError."""
    with pytest.raises(ValidationError):
        EmotionTransitionProposal(
            current_emotion=EmotionType.CALM,
            current_intensity=0.50,
            proposed_emotion=EmotionType.CALM,
            proposed_intensity=invalid_intensity,
            reason="Test reason",
        )


@pytest.mark.parametrize("empty_reason", ["", "   ", None])
def test_empty_reason_rejected(empty_reason: str) -> None:
    """Empty or whitespace reason raises ValidationError."""
    with pytest.raises(ValidationError):
        EmotionTransitionProposal(
            current_emotion=EmotionType.CALM,
            current_intensity=0.50,
            proposed_emotion=EmotionType.CALM,
            proposed_intensity=0.50,
            reason=empty_reason,  # type: ignore[arg-type]
        )


def test_reason_length_limit() -> None:
    """Reason exceeding MAX_TRANSITION_REASON_LENGTH is rejected."""
    long_reason = "a" * (MAX_TRANSITION_REASON_LENGTH + 1)
    with pytest.raises(ValidationError, match="exceeds maximum allowed"):
        EmotionTransitionProposal(
            current_emotion=EmotionType.CALM,
            current_intensity=0.50,
            proposed_emotion=EmotionType.CALM,
            proposed_intensity=0.50,
            reason=long_reason,
        )


def test_reason_rejects_credentials() -> None:
    """Reason containing prohibited credentials raises ValidationError."""
    with pytest.raises(ValidationError, match="prohibited credential"):
        EmotionTransitionProposal(
            current_emotion=EmotionType.CALM,
            current_intensity=0.50,
            proposed_emotion=EmotionType.CALM,
            proposed_intensity=0.50,
            reason="Triggered by sk-proj-1234567890abcdef1234567890abcdef",
        )


def test_invalid_considered_ids_rejected() -> None:
    """Empty strings in considered_influence_ids raise ValidationError."""
    with pytest.raises(ValidationError):
        EmotionTransitionProposal(
            current_emotion=EmotionType.CALM,
            current_intensity=0.50,
            proposed_emotion=EmotionType.CALM,
            proposed_intensity=0.50,
            considered_influence_ids=["valid-1", "   "],
            reason="Test reason",
        )


def test_proposal_extra_fields_rejected() -> None:
    """Extra fields are forbidden."""
    with pytest.raises(ValidationError):
        EmotionTransitionProposal(
            current_emotion=EmotionType.CALM,
            current_intensity=0.50,
            proposed_emotion=EmotionType.CALM,
            proposed_intensity=0.50,
            reason="Test reason",
            extra_field="disallowed",  # type: ignore[call-arg]
        )


def test_proposal_immutability() -> None:
    """EmotionTransitionProposal is frozen and immutable."""
    proposal = EmotionTransitionProposal(
        current_emotion=EmotionType.CALM,
        current_intensity=0.50,
        proposed_emotion=EmotionType.CALM,
        proposed_intensity=0.50,
        reason="Test reason",
    )
    with pytest.raises(ValidationError):
        proposal.proposed_intensity = 0.80  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 2. Zero / Non-actionable Influences
# ---------------------------------------------------------------------------

def test_evaluator_zero_influences_preserves_state() -> None:
    """Empty influences list returns proposal preserving current state."""
    state = create_initial_emotion_state()
    proposal = EmotionTransitionEvaluator.evaluate(state, [])

    assert proposal.current_emotion == state.emotion_type
    assert proposal.current_intensity == state.intensity
    assert proposal.proposed_emotion == state.emotion_type
    assert proposal.proposed_intensity == state.intensity
    assert proposal.considered_influence_ids == []
    assert proposal.reason == REASON_NO_ACTIONABLE_INFLUENCE


def test_evaluator_none_influences_preserves_state() -> None:
    """Passing None for influences cleanly preserves state."""
    state = create_initial_emotion_state()
    proposal = EmotionTransitionEvaluator.evaluate(state, None)

    assert proposal.proposed_emotion == state.emotion_type
    assert proposal.proposed_intensity == state.intensity
    assert proposal.considered_influence_ids == []
    assert proposal.reason == REASON_NO_ACTIONABLE_INFLUENCE


def test_evaluator_negative_competing_influence_is_non_actionable() -> None:
    """Negative influence targeting a DIFFERENT emotion does not cause arbitrary switch."""
    state = create_initial_emotion_state()  # NEUTRAL 0.50
    inf = _make_influence("inf-1", EmotionType.SAD, EmotionInfluenceDirection.NEGATIVE, 0.50)

    proposal = EmotionTransitionEvaluator.evaluate(state, [inf])

    assert proposal.proposed_emotion == EmotionType.NEUTRAL
    assert proposal.proposed_intensity == 0.50
    assert proposal.considered_influence_ids == ["inf-1"]
    assert proposal.reason == REASON_NO_ACTIONABLE_INFLUENCE


# ---------------------------------------------------------------------------
# 3. Current Emotion Influences (Positive & Negative)
# ---------------------------------------------------------------------------

def test_positive_current_emotion_influence() -> None:
    """Positive influence targeting current emotion increases intensity."""
    state = create_initial_emotion_state()  # NEUTRAL 0.50
    inf = _make_influence("inf-1", EmotionType.NEUTRAL, EmotionInfluenceDirection.POSITIVE, 0.20)

    proposal = EmotionTransitionEvaluator.evaluate(state, [inf])

    assert proposal.proposed_emotion == EmotionType.NEUTRAL
    assert proposal.proposed_intensity == 0.70
    assert proposal.considered_influence_ids == ["inf-1"]
    assert proposal.reason == REASON_POSITIVE_INCREASE


def test_positive_current_emotion_jump_cap() -> None:
    """Total positive adjustment is capped at 0.30 per evaluation."""
    state = create_initial_emotion_state()  # NEUTRAL 0.50
    inf = _make_influence("inf-1", EmotionType.NEUTRAL, EmotionInfluenceDirection.POSITIVE, 0.50)

    proposal = EmotionTransitionEvaluator.evaluate(state, [inf])

    assert proposal.proposed_emotion == EmotionType.NEUTRAL
    assert proposal.proposed_intensity == 0.80  # 0.50 + 0.30 cap
    assert proposal.reason == REASON_POSITIVE_INCREASE


def test_positive_current_emotion_ceiling() -> None:
    """Intensity cannot exceed 1.0."""
    now = datetime.now(timezone.utc)
    state = EmotionState(
        id="state-1",
        character_id="aevum",
        emotion_type=EmotionType.HAPPY,
        intensity=0.90,
        created_at=now,
        updated_at=now,
        version=1,
    )
    inf = _make_influence("inf-1", EmotionType.HAPPY, EmotionInfluenceDirection.POSITIVE, 0.25)

    proposal = EmotionTransitionEvaluator.evaluate(state, [inf])

    assert proposal.proposed_intensity == 1.00


def test_negative_current_emotion_influence() -> None:
    """Negative influence targeting current emotion decreases intensity."""
    state = create_initial_emotion_state()  # NEUTRAL 0.50
    inf = _make_influence("inf-1", EmotionType.NEUTRAL, EmotionInfluenceDirection.NEGATIVE, 0.20)

    proposal = EmotionTransitionEvaluator.evaluate(state, [inf])

    assert proposal.proposed_emotion == EmotionType.NEUTRAL
    assert proposal.proposed_intensity == 0.30
    assert proposal.considered_influence_ids == ["inf-1"]
    assert proposal.reason == REASON_NEGATIVE_REDUCTION


def test_negative_current_emotion_reduction_cap() -> None:
    """Total negative adjustment cannot exceed 0.30 reduction per evaluation."""
    now = datetime.now(timezone.utc)
    state = EmotionState(
        id="state-1",
        character_id="aevum",
        emotion_type=EmotionType.CALM,
        intensity=0.80,
        created_at=now,
        updated_at=now,
        version=1,
    )
    inf = _make_influence("inf-1", EmotionType.CALM, EmotionInfluenceDirection.NEGATIVE, 0.50)

    proposal = EmotionTransitionEvaluator.evaluate(state, [inf])

    assert proposal.proposed_emotion == EmotionType.CALM
    assert proposal.proposed_intensity == 0.50  # 0.80 - 0.30 cap
    assert proposal.reason == REASON_NEGATIVE_REDUCTION


def test_negative_current_emotion_floor() -> None:
    """Intensity cannot drop below 0.0."""
    now = datetime.now(timezone.utc)
    state = EmotionState(
        id="state-1",
        character_id="aevum",
        emotion_type=EmotionType.CALM,
        intensity=0.10,
        created_at=now,
        updated_at=now,
        version=1,
    )
    inf = _make_influence("inf-1", EmotionType.CALM, EmotionInfluenceDirection.NEGATIVE, 0.25)

    proposal = EmotionTransitionEvaluator.evaluate(state, [inf])

    assert proposal.proposed_intensity == 0.00


def test_multiple_current_emotion_influences_aggregate() -> None:
    """Multiple positive influences on current emotion sum deterministically before cap."""
    state = create_initial_emotion_state()  # NEUTRAL 0.50
    inf1 = _make_influence("inf-1", EmotionType.NEUTRAL, EmotionInfluenceDirection.POSITIVE, 0.10)
    inf2 = _make_influence("inf-2", EmotionType.NEUTRAL, EmotionInfluenceDirection.POSITIVE, 0.15)

    proposal = EmotionTransitionEvaluator.evaluate(state, [inf1, inf2])

    assert proposal.proposed_intensity == 0.75
    assert proposal.considered_influence_ids == ["inf-1", "inf-2"]


def test_mixed_current_emotion_influences_net_result() -> None:
    """Positive and negative influences on current emotion calculate net delta."""
    state = create_initial_emotion_state()  # NEUTRAL 0.50
    inf_pos = _make_influence("inf-1", EmotionType.NEUTRAL, EmotionInfluenceDirection.POSITIVE, 0.25)
    inf_neg = _make_influence("inf-2", EmotionType.NEUTRAL, EmotionInfluenceDirection.NEGATIVE, 0.10)

    proposal = EmotionTransitionEvaluator.evaluate(state, [inf_pos, inf_neg])

    assert proposal.proposed_intensity == 0.65  # 0.50 + 0.15 net
    assert proposal.reason == REASON_POSITIVE_INCREASE


def test_mixed_current_emotion_balanced_net_zero() -> None:
    """Equal positive and negative influences produce balanced no change."""
    state = create_initial_emotion_state()  # NEUTRAL 0.50
    inf_pos = _make_influence("inf-1", EmotionType.NEUTRAL, EmotionInfluenceDirection.POSITIVE, 0.15)
    inf_neg = _make_influence("inf-2", EmotionType.NEUTRAL, EmotionInfluenceDirection.NEGATIVE, 0.15)

    proposal = EmotionTransitionEvaluator.evaluate(state, [inf_pos, inf_neg])

    assert proposal.proposed_intensity == 0.50
    assert proposal.reason == REASON_BALANCED_NO_CHANGE


# ---------------------------------------------------------------------------
# 4. Competing Emotion Switch & Conflict Handling
# ---------------------------------------------------------------------------

def test_competing_positive_emotion_switch() -> None:
    """Strong positive competing influence proposes a dominant emotion switch."""
    state = create_initial_emotion_state()  # NEUTRAL 0.50
    inf = _make_influence("inf-1", EmotionType.HAPPY, EmotionInfluenceDirection.POSITIVE, 0.40)

    proposal = EmotionTransitionEvaluator.evaluate(state, [inf])

    assert proposal.proposed_emotion == EmotionType.HAPPY
    assert proposal.proposed_intensity == 0.60  # 0.40 + 0.40 * 0.50
    assert proposal.reason == REASON_COMPETING_SWITCH


def test_competing_influence_below_threshold_rejected() -> None:
    """Competing positive influence below 0.20 does not trigger switch."""
    state = create_initial_emotion_state()  # NEUTRAL 0.50
    inf = _make_influence("inf-1", EmotionType.HAPPY, EmotionInfluenceDirection.POSITIVE, 0.19)

    proposal = EmotionTransitionEvaluator.evaluate(state, [inf])

    assert proposal.proposed_emotion == EmotionType.NEUTRAL
    assert proposal.proposed_intensity == 0.50
    assert proposal.reason == REASON_NO_ACTIONABLE_INFLUENCE


def test_competing_influence_intensity_bounds() -> None:
    """Proposed switch intensity is bounded by [0.40, 0.90]."""
    state = create_initial_emotion_state()  # NEUTRAL 0.50

    # At threshold 0.20: 0.40 + 0.20 * 0.50 = 0.50
    inf_min = _make_influence("inf-1", EmotionType.HAPPY, EmotionInfluenceDirection.POSITIVE, 0.20)
    prop_min = EmotionTransitionEvaluator.evaluate(state, [inf_min])
    assert prop_min.proposed_intensity == 0.50

    # At strength 0.80: 0.40 + 0.80 * 0.50 = 0.80
    inf_mid = _make_influence("inf-2", EmotionType.HAPPY, EmotionInfluenceDirection.POSITIVE, 0.80)
    prop_mid = EmotionTransitionEvaluator.evaluate(state, [inf_mid])
    assert prop_mid.proposed_intensity == 0.80

    # At strength 1.00: 0.40 + 1.00 * 0.50 = 0.90 ceiling
    inf_max = _make_influence("inf-3", EmotionType.HAPPY, EmotionInfluenceDirection.POSITIVE, 1.00)
    prop_max = EmotionTransitionEvaluator.evaluate(state, [inf_max])
    assert prop_max.proposed_intensity == 0.90


def test_competing_influence_deterministic_tie_breaking() -> None:
    """Competing influences with identical strength break ties deterministically."""
    state = create_initial_emotion_state()  # NEUTRAL 0.50
    # Two different target emotions with same strength
    inf_happy = _make_influence("inf-h", EmotionType.HAPPY, EmotionInfluenceDirection.POSITIVE, 0.40)
    inf_calm = _make_influence("inf-c", EmotionType.CALM, EmotionInfluenceDirection.POSITIVE, 0.40)

    # In alphabetical order of EmotionType value: "CALM" comes before "HAPPY"
    prop1 = EmotionTransitionEvaluator.evaluate(state, [inf_happy, inf_calm])
    prop2 = EmotionTransitionEvaluator.evaluate(state, [inf_calm, inf_happy])

    assert prop1.proposed_emotion == EmotionType.CALM
    assert prop2.proposed_emotion == EmotionType.CALM
    assert prop1.proposed_emotion == prop2.proposed_emotion


def test_competing_influence_same_emotion_id_tie_breaking() -> None:
    """Competing influences with same strength and target emotion break ties by ID."""
    state = create_initial_emotion_state()  # NEUTRAL 0.50
    inf_b = _make_influence("inf-b", EmotionType.HAPPY, EmotionInfluenceDirection.POSITIVE, 0.40)
    inf_a = _make_influence("inf-a", EmotionType.HAPPY, EmotionInfluenceDirection.POSITIVE, 0.40)

    # Sorts by id: "inf-a" < "inf-b"
    prop1 = EmotionTransitionEvaluator.evaluate(state, [inf_b, inf_a])
    prop2 = EmotionTransitionEvaluator.evaluate(state, [inf_a, inf_b])

    assert prop1.proposed_emotion == EmotionType.HAPPY
    assert prop2.proposed_emotion == EmotionType.HAPPY


# ---------------------------------------------------------------------------
# 5. User-Specified Specification & Baseline Comparison Tests
# ---------------------------------------------------------------------------

def test_user_example_1_competing_emotion_wins() -> None:
    """User Example 1:
    current = CALM, positive_current = +0.10, negative_current = 0, competing HAPPY = +0.25
    Since 0.25 >= 0.20 and 0.25 > 0.10 -> propose HAPPY.
    """
    now = datetime.now(timezone.utc)
    state = EmotionState(
        id="state-1",
        character_id="aevum",
        emotion_type=EmotionType.CALM,
        intensity=0.60,
        created_at=now,
        updated_at=now,
        version=1,
    )
    inf_calm = _make_influence("inf-1", EmotionType.CALM, EmotionInfluenceDirection.POSITIVE, 0.10)
    inf_happy = _make_influence("inf-2", EmotionType.HAPPY, EmotionInfluenceDirection.POSITIVE, 0.25)

    proposal = EmotionTransitionEvaluator.evaluate(state, [inf_calm, inf_happy])

    assert proposal.proposed_emotion == EmotionType.HAPPY
    assert proposal.proposed_intensity == 0.525  # 0.40 + 0.25 * 0.50
    assert proposal.reason == REASON_COMPETING_SWITCH


def test_user_example_2_current_emotion_remains_stronger() -> None:
    """User Example 2:
    current = CALM, positive_current = +0.30, negative_current = 0, competing HAPPY = +0.25
    Since 0.25 < 0.30 -> remain CALM.
    """
    now = datetime.now(timezone.utc)
    state = EmotionState(
        id="state-1",
        character_id="aevum",
        emotion_type=EmotionType.CALM,
        intensity=0.50,
        created_at=now,
        updated_at=now,
        version=1,
    )
    inf_calm = _make_influence("inf-1", EmotionType.CALM, EmotionInfluenceDirection.POSITIVE, 0.30)
    inf_happy = _make_influence("inf-2", EmotionType.HAPPY, EmotionInfluenceDirection.POSITIVE, 0.25)

    proposal = EmotionTransitionEvaluator.evaluate(state, [inf_calm, inf_happy])

    assert proposal.proposed_emotion == EmotionType.CALM
    assert proposal.proposed_intensity == 0.80  # 0.50 + 0.30
    assert proposal.reason == REASON_POSITIVE_INCREASE


def test_user_example_3_current_emotion_weakened_competing_qualifies() -> None:
    """User Example 3:
    current = CALM, positive_current = 0, negative_current = -0.30, competing HAPPY = +0.20
    The competing influence satisfies 0.20 >= 0.20 and 0.20 > 0 -> propose HAPPY.
    """
    now = datetime.now(timezone.utc)
    state = EmotionState(
        id="state-1",
        character_id="aevum",
        emotion_type=EmotionType.CALM,
        intensity=0.60,
        created_at=now,
        updated_at=now,
        version=1,
    )
    inf_calm_neg = _make_influence("inf-1", EmotionType.CALM, EmotionInfluenceDirection.NEGATIVE, 0.30)
    inf_happy = _make_influence("inf-2", EmotionType.HAPPY, EmotionInfluenceDirection.POSITIVE, 0.20)

    proposal = EmotionTransitionEvaluator.evaluate(state, [inf_calm_neg, inf_happy])

    assert proposal.proposed_emotion == EmotionType.HAPPY
    assert proposal.proposed_intensity == 0.50  # 0.40 + 0.20 * 0.50
    assert proposal.reason == REASON_COMPETING_SWITCH


def test_negative_current_pressure_does_not_lower_comparison_baseline_below_threshold() -> None:
    """Negative current pressure does NOT artificially allow a below-threshold competing emotion.
    current = CALM, positive_current = +0.10, negative_current = -0.30, competing HAPPY = +0.15
    Even though net_current_delta = -0.20, competing HAPPY (0.15) is below 0.20 threshold -> remain CALM.
    """
    now = datetime.now(timezone.utc)
    state = EmotionState(
        id="state-1",
        character_id="aevum",
        emotion_type=EmotionType.CALM,
        intensity=0.60,
        created_at=now,
        updated_at=now,
        version=1,
    )
    inf_pos = _make_influence("inf-1", EmotionType.CALM, EmotionInfluenceDirection.POSITIVE, 0.10)
    inf_neg = _make_influence("inf-2", EmotionType.CALM, EmotionInfluenceDirection.NEGATIVE, 0.30)
    inf_happy = _make_influence("inf-3", EmotionType.HAPPY, EmotionInfluenceDirection.POSITIVE, 0.15)

    proposal = EmotionTransitionEvaluator.evaluate(state, [inf_pos, inf_neg, inf_happy])

    assert proposal.proposed_emotion == EmotionType.CALM
    # Net delta = +0.10 - 0.30 = -0.20
    assert proposal.proposed_intensity == 0.40  # 0.60 - 0.20
    assert proposal.reason == REASON_NEGATIVE_REDUCTION


def test_negative_current_pressure_with_qualifying_competing_emotion() -> None:
    """Negative current pressure alongside a qualifying competing positive emotion:
    current = CALM, positive_current = +0.10, negative_current = -0.30, competing HAPPY = +0.20
    Since 0.20 >= 0.20 and 0.20 > positive_current_strength (0.10) -> propose HAPPY.
    """
    now = datetime.now(timezone.utc)
    state = EmotionState(
        id="state-1",
        character_id="aevum",
        emotion_type=EmotionType.CALM,
        intensity=0.60,
        created_at=now,
        updated_at=now,
        version=1,
    )
    inf_pos = _make_influence("inf-1", EmotionType.CALM, EmotionInfluenceDirection.POSITIVE, 0.10)
    inf_neg = _make_influence("inf-2", EmotionType.CALM, EmotionInfluenceDirection.NEGATIVE, 0.30)
    inf_happy = _make_influence("inf-3", EmotionType.HAPPY, EmotionInfluenceDirection.POSITIVE, 0.20)

    proposal = EmotionTransitionEvaluator.evaluate(state, [inf_pos, inf_neg, inf_happy])

    assert proposal.proposed_emotion == EmotionType.HAPPY
    assert proposal.proposed_intensity == 0.50
    assert proposal.reason == REASON_COMPETING_SWITCH


# ---------------------------------------------------------------------------
# 6. Immutability, Determinism, and Side-Effect Isolation
# ---------------------------------------------------------------------------

def test_input_immutability() -> None:
    """Evaluator does not mutate EmotionState, EmotionInfluence, or the input list."""
    state = create_initial_emotion_state()
    orig_intensity = state.intensity
    inf = _make_influence("inf-1", EmotionType.HAPPY, EmotionInfluenceDirection.POSITIVE, 0.40)
    orig_strength = inf.strength

    influences_list = [inf]
    proposal = EmotionTransitionEvaluator.evaluate(state, influences_list)

    # Verify input models were unmutated
    assert state.intensity == orig_intensity
    assert inf.strength == orig_strength
    assert len(influences_list) == 1
    assert proposal is not None


def test_determinism_across_multiple_runs() -> None:
    """Identical inputs produce exact identical proposals every single run."""
    state = create_initial_emotion_state()
    inf1 = _make_influence("inf-1", EmotionType.CALM, EmotionInfluenceDirection.POSITIVE, 0.15)
    inf2 = _make_influence("inf-2", EmotionType.HAPPY, EmotionInfluenceDirection.POSITIVE, 0.35)

    results = [EmotionTransitionEvaluator.evaluate(state, [inf1, inf2]) for _ in range(10)]

    for res in results[1:]:
        assert res == results[0]


def test_convenience_function() -> None:
    """evaluate_emotion_transition matches EmotionTransitionEvaluator.evaluate."""
    state = create_initial_emotion_state()
    inf = _make_influence("inf-1", EmotionType.HAPPY, EmotionInfluenceDirection.POSITIVE, 0.40)

    p1 = EmotionTransitionEvaluator.evaluate(state, [inf])
    p2 = evaluate_emotion_transition(state, [inf])

    assert p1 == p2


def test_invalid_input_types_raise_type_error() -> None:
    """Passing invalid object types to evaluate raises TypeError."""
    state = create_initial_emotion_state()

    with pytest.raises(TypeError, match="current_state must be an EmotionState"):
        EmotionTransitionEvaluator.evaluate("not-an-emotion-state", [])  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="Every item in influences must be an EmotionInfluence"):
        EmotionTransitionEvaluator.evaluate(state, ["not-an-influence"])  # type: ignore[list-item]
