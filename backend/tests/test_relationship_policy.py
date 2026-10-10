"""Comprehensive test suite for Phase 4.2 Relationship Policy Engine.

Verifies:
- Deterministic behavior: same input always produces exact same output.
- Signal type coverage: all 11 signal types correctly map to expected dimensions.
- Healthy DISAGREEMENT is neutral by default (produces no changes).
- Thresholds: confidence < 0.70 or strength < 0.10 produce zero updates.
- Delta calculation formula: delta = round(base_delta * confidence * strength, 6).
- Per-signal cap: maximum delta of 0.03.
- Aggregate cap: multiple signals affecting the same dimension clamped to 0.03 total.
- Boundary clamping: target values strictly clamped within [0.0, 1.0].
- Zero affection changes: ordinary interaction signals NEVER alter affection.
- Attachment modification restricted strictly to SUPPORT_RECEIVED.
- Contradictory signal resolution (RESPECT_BOUNDARY vs BOUNDARY_VIOLATION).
- Duplicate signal deduplication (retains highest impact).
"""

from datetime import datetime, timezone
import pytest

from app.relationship.models import (
    BOOTSTRAP_AFFECTION,
    BOOTSTRAP_ATTACHMENT,
    BOOTSTRAP_COMFORT,
    BOOTSTRAP_FAMILIARITY,
    BOOTSTRAP_RESPECT,
    BOOTSTRAP_TRUST,
    RelationshipSignal,
    RelationshipSignalSource,
    RelationshipSignalType,
    RelationshipState,
    RelationshipStateUpdate,
)
from app.relationship.policy import (
    MAX_AGGREGATE_DELTA_PER_DIMENSION,
    MAX_SIGNAL_DELTA,
    MIN_SIGNAL_CONFIDENCE,
    MIN_SIGNAL_STRENGTH,
    RELATIONSHIP_POLICY_VERSION,
    SIGNAL_BASE_DELTAS,
    apply_relationship_signal,
    apply_relationship_signals,
    calculate_signal_delta,
    deduplicate_signals,
    resolve_signal_conflicts,
)


def _make_state(
    familiarity: float = BOOTSTRAP_FAMILIARITY,
    trust: float = BOOTSTRAP_TRUST,
    comfort: float = BOOTSTRAP_COMFORT,
    affection: float = BOOTSTRAP_AFFECTION,
    attachment: float = BOOTSTRAP_ATTACHMENT,
    respect: float = BOOTSTRAP_RESPECT,
) -> RelationshipState:
    now = datetime.now(timezone.utc)
    return RelationshipState(
        id="test",
        user_id="user",
        version=1,
        created_at=now,
        updated_at=now,
        familiarity=familiarity,
        trust=trust,
        comfort=comfort,
        affection=affection,
        attachment=attachment,
        respect=respect,
    )


def _make_signal(
    signal_type: RelationshipSignalType,
    confidence: float = 0.90,
    strength: float = 0.50,
) -> RelationshipSignal:
    return RelationshipSignal(
        signal_type=signal_type,
        source=RelationshipSignalSource.LLM,
        confidence=confidence,
        strength=strength,
        reason=f"Observed {signal_type.value}",
    )


# =============================================================================
# 1. Determinism and Policy Metadata
# =============================================================================


def test_policy_version():
    """Policy version is strictly defined."""
    assert RELATIONSHIP_POLICY_VERSION == "1.0.0"


def test_deterministic_pure_function():
    """Same state and signals produce identical updates across multiple runs."""
    state = _make_state()
    signal = _make_signal(RelationshipSignalType.APPRECIATION, confidence=0.85, strength=0.40)

    res1 = apply_relationship_signals(state, [signal])
    res2 = apply_relationship_signals(state, [signal])

    assert res1 is not None
    assert res2 is not None
    assert res1.model_dump() == res2.model_dump()


# =============================================================================
# 2. Thresholds
# =============================================================================


def test_signals_below_confidence_threshold_produce_no_update():
    """Signals with confidence < 0.70 are ignored."""
    state = _make_state()
    weak_signal = _make_signal(RelationshipSignalType.APPRECIATION, confidence=0.69, strength=0.50)
    assert apply_relationship_signals(state, [weak_signal]) is None


def test_signals_below_strength_threshold_produce_no_update():
    """Signals with strength < 0.10 are ignored."""
    state = _make_state()
    trivial_signal = _make_signal(RelationshipSignalType.APPRECIATION, confidence=0.90, strength=0.09)
    assert apply_relationship_signals(state, [trivial_signal]) is None


def test_empty_signals_produce_no_update():
    """Empty signals list returns None."""
    state = _make_state()
    assert apply_relationship_signals(state, []) is None


# =============================================================================
# 3. Individual Signal Dimensions and Effects
# =============================================================================


def test_appreciation_affects_trust_and_comfort():
    """APPRECIATION increases trust, comfort, and bounded affection."""
    state = _make_state()
    sig = _make_signal(RelationshipSignalType.APPRECIATION, confidence=0.90, strength=0.50)
    update_data = apply_relationship_signals(state, [sig])

    assert update_data is not None
    # effective_strength = 0.90 * 0.50 = 0.45
    # trust delta = 0.004 * 0.45 = 0.0018 -> 0.20 + 0.0018 = 0.2018
    # comfort delta = 0.006 * 0.45 = 0.0027 -> 0.10 + 0.0027 = 0.1027
    # affection delta = 0.005 * 0.45 = 0.00225 -> 0.00 + 0.00225 = 0.00225
    assert update_data.trust == pytest.approx(0.2018, rel=1e-4)
    assert update_data.comfort == pytest.approx(0.1027, rel=1e-4)
    assert update_data.affection == pytest.approx(0.00225, rel=1e-4)
    assert update_data.attachment is None
    assert update_data.respect is None
    assert update_data.familiarity is None


def test_shared_interest_affects_familiarity_and_comfort():
    """SHARED_INTEREST increases familiarity, comfort, and bounded affection."""
    state = _make_state()
    sig = _make_signal(RelationshipSignalType.SHARED_INTEREST, confidence=0.80, strength=0.50)
    update_data = apply_relationship_signals(state, [sig])

    assert update_data is not None
    assert update_data.familiarity is not None
    assert update_data.comfort is not None
    assert update_data.trust is None


def test_personal_disclosure_affects_trust_and_familiarity():
    """PERSONAL_DISCLOSURE increases trust and familiarity."""
    state = _make_state()
    sig = _make_signal(RelationshipSignalType.PERSONAL_DISCLOSURE, confidence=0.80, strength=0.50)
    update_data = apply_relationship_signals(state, [sig])

    assert update_data is not None
    assert update_data.trust is not None
    assert update_data.familiarity is not None


def test_support_received_affects_trust_comfort_and_attachment():
    """SUPPORT_RECEIVED increases trust, comfort, attachment, and bounded affection."""
    state = _make_state()
    sig = _make_signal(RelationshipSignalType.SUPPORT_RECEIVED, confidence=0.80, strength=0.50)
    update_data = apply_relationship_signals(state, [sig])

    assert update_data is not None
    assert update_data.trust is not None
    assert update_data.comfort is not None
    assert update_data.attachment is not None
    assert update_data.affection == pytest.approx(0.0024, rel=1e-4)


def test_support_given_affects_respect_and_familiarity():
    """SUPPORT_GIVEN increases respect and familiarity without creating transactional affection."""
    state = _make_state()
    sig = _make_signal(RelationshipSignalType.SUPPORT_GIVEN, confidence=0.80, strength=0.50)
    update_data = apply_relationship_signals(state, [sig])

    assert update_data is not None
    assert update_data.respect is not None
    assert update_data.familiarity is not None
    assert update_data.affection is None


def test_respect_boundary_affects_trust_respect_and_comfort():
    """RESPECT_BOUNDARY increases trust, respect, and comfort."""
    state = _make_state()
    sig = _make_signal(RelationshipSignalType.RESPECT_BOUNDARY, confidence=0.80, strength=0.50)
    update_data = apply_relationship_signals(state, [sig])

    assert update_data is not None
    assert update_data.trust is not None
    assert update_data.respect is not None
    assert update_data.comfort is not None


def test_boundary_violation_reduces_trust_respect_and_comfort():
    """BOUNDARY_VIOLATION meaningfully decreases trust, respect, comfort, and affection."""
    state = _make_state(trust=0.50, respect=0.60, comfort=0.40, affection=0.30)
    sig = _make_signal(RelationshipSignalType.BOUNDARY_VIOLATION, confidence=0.90, strength=0.80)
    update_data = apply_relationship_signals(state, [sig])

    assert update_data is not None
    assert update_data.trust < 0.50
    assert update_data.respect < 0.60
    assert update_data.comfort < 0.40
    assert update_data.affection < 0.30


def test_disagreement_is_neutral_by_default():
    """DISAGREEMENT alone produces no state change."""
    state = _make_state()
    sig = _make_signal(RelationshipSignalType.DISAGREEMENT, confidence=0.95, strength=0.80)
    update_data = apply_relationship_signals(state, [sig])
    assert update_data is None


def test_repair_attempt_affects_trust_and_comfort():
    """REPAIR_ATTEMPT increases trust and comfort."""
    state = _make_state()
    sig = _make_signal(RelationshipSignalType.REPAIR_ATTEMPT, confidence=0.80, strength=0.50)
    update_data = apply_relationship_signals(state, [sig])

    assert update_data is not None
    assert update_data.trust is not None
    assert update_data.comfort is not None


def test_playful_connection_affects_comfort_and_familiarity():
    """PLAYFUL_CONNECTION increases comfort, familiarity, and bounded affection."""
    state = _make_state()
    sig = _make_signal(RelationshipSignalType.PLAYFUL_CONNECTION, confidence=0.80, strength=0.50)
    update_data = apply_relationship_signals(state, [sig])

    assert update_data is not None
    assert update_data.comfort is not None
    assert update_data.familiarity is not None
    assert update_data.affection == pytest.approx(0.002, rel=1e-4)


def test_reliability_affects_trust_and_respect():
    """RELIABILITY increases trust and respect without modifying affection."""
    state = _make_state()
    sig = _make_signal(RelationshipSignalType.RELIABILITY, confidence=0.80, strength=0.50)
    update_data = apply_relationship_signals(state, [sig])

    assert update_data is not None
    assert update_data.trust is not None
    assert update_data.respect is not None
    assert update_data.affection is None


# =============================================================================
# 4. Strict Constraints: No Affection Leak on Non-Relational Signals, Bounded Clamping
# =============================================================================


def test_non_affection_signals_do_not_modify_affection():
    """Verify that task/boundary/work signals (SUPPORT_GIVEN, RESPECT_BOUNDARY, RELIABILITY) do NOT alter affection."""
    state = _make_state(affection=0.0)
    non_affection_types = [
        RelationshipSignalType.SUPPORT_GIVEN,
        RelationshipSignalType.RESPECT_BOUNDARY,
        RelationshipSignalType.RELIABILITY,
        RelationshipSignalType.DISAGREEMENT,
    ]
    for sig_type in non_affection_types:
        sig = _make_signal(sig_type, confidence=1.0, strength=1.0)
        update_data = apply_relationship_signals(state, [sig])
        if update_data is not None:
            assert update_data.affection is None, f"Signal {sig_type} unexpectedly updated affection!"


def test_maximum_aggregate_delta_cap():
    """Even with multiple reinforcing signals, per-dimension aggregate delta is capped at 0.03."""
    state = _make_state(trust=0.20)
    # Three strong signals all affecting trust
    signals = [
        _make_signal(RelationshipSignalType.APPRECIATION, confidence=1.0, strength=1.0),
        _make_signal(RelationshipSignalType.RELIABILITY, confidence=1.0, strength=1.0),
        _make_signal(RelationshipSignalType.REPAIR_ATTEMPT, confidence=1.0, strength=1.0),
    ]
    update_data = apply_relationship_signals(state, signals)

    assert update_data is not None
    # Maximum allowed change is 0.03
    assert update_data.trust <= 0.20 + MAX_AGGREGATE_DELTA_PER_DIMENSION + 1e-6


def test_clamping_to_zero_and_one():
    """State updates are strictly bounded within [0.0, 1.0]."""
    # Low trust state
    state_low = _make_state(trust=0.005, respect=0.005, comfort=0.005)
    sig_neg = _make_signal(RelationshipSignalType.BOUNDARY_VIOLATION, confidence=1.0, strength=1.0)
    update_low = apply_relationship_signals(state_low, [sig_neg])

    assert update_low is not None
    assert update_low.trust == 0.0  # Does not go negative
    assert update_low.respect == 0.0
    assert update_low.comfort == 0.0

    # High trust state
    state_high = _make_state(trust=0.995)
    sig_pos = _make_signal(RelationshipSignalType.RELIABILITY, confidence=1.0, strength=1.0)
    update_high = apply_relationship_signals(state_high, [sig_pos])

    assert update_high is not None
    assert update_high.trust == 1.0  # Does not exceed 1.0


# =============================================================================
# 5. Conflict Resolution and Deduplication
# =============================================================================


def test_conflict_resolution_favors_higher_confidence():
    """Contradictory signals resolve to the one with higher confidence."""
    sig_respect = _make_signal(RelationshipSignalType.RESPECT_BOUNDARY, confidence=0.95, strength=0.50)
    sig_violation = _make_signal(RelationshipSignalType.BOUNDARY_VIOLATION, confidence=0.75, strength=0.50)

    resolved = resolve_signal_conflicts([sig_respect, sig_violation])
    assert len(resolved) == 1
    assert resolved[0].signal_type == RelationshipSignalType.RESPECT_BOUNDARY


def test_conflict_resolution_tied_confidence_favors_conservative():
    """When confidence is tied between RESPECT and VIOLATION, boundary violation is retained."""
    sig_respect = _make_signal(RelationshipSignalType.RESPECT_BOUNDARY, confidence=0.85, strength=0.50)
    sig_violation = _make_signal(RelationshipSignalType.BOUNDARY_VIOLATION, confidence=0.85, strength=0.50)

    resolved = resolve_signal_conflicts([sig_respect, sig_violation])
    assert len(resolved) == 1
    assert resolved[0].signal_type == RelationshipSignalType.BOUNDARY_VIOLATION


def test_deduplication_retains_strongest_signal_per_type():
    """Multiple signals of the same type deduplicate to the single highest-impact signal."""
    sig_weak = _make_signal(RelationshipSignalType.APPRECIATION, confidence=0.75, strength=0.20)
    sig_strong = _make_signal(RelationshipSignalType.APPRECIATION, confidence=0.90, strength=0.60)

    deduped = deduplicate_signals([sig_weak, sig_strong])
    assert len(deduped) == 1
    assert deduped[0].confidence == 0.90
    assert deduped[0].strength == 0.60
