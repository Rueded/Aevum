"""Deterministic Relationship Policy Engine for Aevum Core.

Maps validated interaction observations (RelationshipSignal) into bounded, deterministic
RelationshipStateUpdate mutations.

Guarantees:
- Deterministic: Pure function of (RelationshipState, Sequence[RelationshipSignal]).
  Zero randomness, zero LLM calls, zero time-dependent decay.
- Gradual & Bounded: Strict per-signal and per-interaction aggregate delta caps (0.03).
- No Direct Affection Mutation: Ordinary interaction signals NEVER directly modify affection.
- Safe Clamping: All target metrics clamped to [0.0, 1.0].
- High Confidence / Strength Thresholds: Weak signals (<0.70 confidence or <0.10 strength)
  produce no relationship mutation.
- Conflict Resolution & Deduplication: Contradictory signals (e.g. RESPECT_BOUNDARY vs BOUNDARY_VIOLATION)
  and duplicate signal types are resolved deterministically.
"""

from collections.abc import Sequence
import logging

from app.relationship.models import (
    RelationshipSignal,
    RelationshipSignalType,
    RelationshipState,
    RelationshipStateUpdate,
)

logger = logging.getLogger(__name__)

RELATIONSHIP_POLICY_VERSION: str = "1.0.0"

# Policy thresholds
MIN_SIGNAL_CONFIDENCE: float = 0.70
MIN_SIGNAL_STRENGTH: float = 0.10
MAX_SIGNAL_DELTA: float = 0.03
MAX_AGGREGATE_DELTA_PER_DIMENSION: float = 0.03

# Base delta contributions per signal type.
# Affection is strictly omitted: ordinary conversation signals do not directly change affection.
SIGNAL_BASE_DELTAS: dict[RelationshipSignalType, dict[str, float]] = {
    RelationshipSignalType.APPRECIATION: {
        "trust": 0.004,
        "comfort": 0.006,
    },
    RelationshipSignalType.SHARED_INTEREST: {
        "familiarity": 0.006,
        "comfort": 0.004,
    },
    RelationshipSignalType.PERSONAL_DISCLOSURE: {
        "trust": 0.006,
        "familiarity": 0.008,
    },
    RelationshipSignalType.SUPPORT_RECEIVED: {
        "trust": 0.008,
        "comfort": 0.006,
        "attachment": 0.003,
    },
    RelationshipSignalType.SUPPORT_GIVEN: {
        "respect": 0.003,
        "familiarity": 0.003,
    },
    RelationshipSignalType.RESPECT_BOUNDARY: {
        "trust": 0.008,
        "respect": 0.006,
        "comfort": 0.004,
    },
    RelationshipSignalType.BOUNDARY_VIOLATION: {
        "trust": -0.012,
        "respect": -0.010,
        "comfort": -0.008,
    },
    RelationshipSignalType.DISAGREEMENT: {},  # Healthy disagreement is neutral by default
    RelationshipSignalType.REPAIR_ATTEMPT: {
        "trust": 0.010,
        "comfort": 0.006,
    },
    RelationshipSignalType.PLAYFUL_CONNECTION: {
        "comfort": 0.005,
        "familiarity": 0.005,
    },
    RelationshipSignalType.RELIABILITY: {
        "trust": 0.010,
        "respect": 0.005,
    },
}


def resolve_signal_conflicts(signals: Sequence[RelationshipSignal]) -> list[RelationshipSignal]:
    """Resolve contradictory signals deterministically.

    Rule:
    If RESPECT_BOUNDARY and BOUNDARY_VIOLATION both exist in the interaction:
      - Retain the signal with higher confidence.
      - If confidence is tied, retain BOUNDARY_VIOLATION (conservative / cautious interpretation).
    """
    respect_sig = next(
        (s for s in signals if s.signal_type == RelationshipSignalType.RESPECT_BOUNDARY),
        None,
    )
    violation_sig = next(
        (s for s in signals if s.signal_type == RelationshipSignalType.BOUNDARY_VIOLATION),
        None,
    )

    if respect_sig is not None and violation_sig is not None:
        if respect_sig.confidence > violation_sig.confidence:
            discard_sig = violation_sig
        else:
            # If violation confidence >= respect confidence, discard respect
            discard_sig = respect_sig

        return [s for s in signals if s is not discard_sig]

    return list(signals)


def deduplicate_signals(signals: Sequence[RelationshipSignal]) -> list[RelationshipSignal]:
    """Deduplicate signals by signal_type, retaining the single highest-impact signal per type.

    Ordering priority:
    1. effective_strength (confidence * strength) descending
    2. confidence descending
    3. strength descending
    """
    grouped: dict[RelationshipSignalType, list[RelationshipSignal]] = {}
    for sig in signals:
        grouped.setdefault(sig.signal_type, []).append(sig)

    deduped: list[RelationshipSignal] = []
    for sig_type, group in grouped.items():
        if len(group) == 1:
            deduped.append(group[0])
        else:
            sorted_group = sorted(
                group,
                key=lambda s: (s.confidence * s.strength, s.confidence, s.strength),
                reverse=True,
            )
            deduped.append(sorted_group[0])

    return deduped


def calculate_signal_delta(
    signal: RelationshipSignal,
    base_delta: float,
) -> float:
    """Calculate the bounded delta for a single dimension from a single signal.

    Formula:
      effective_strength = confidence * strength
      delta = base_delta * effective_strength
      clamped to [-MAX_SIGNAL_DELTA, +MAX_SIGNAL_DELTA]
    """
    effective_strength = signal.confidence * signal.strength
    raw_delta = base_delta * effective_strength
    clamped_delta = max(-MAX_SIGNAL_DELTA, min(MAX_SIGNAL_DELTA, raw_delta))
    return round(clamped_delta, 6)


def filter_eligible_signals(signals: Sequence[RelationshipSignal]) -> list[RelationshipSignal]:
    """Resolve contradictions, deduplicate, and filter signals meeting policy confidence and strength thresholds."""
    if not signals:
        return []
    resolved = resolve_signal_conflicts(signals)
    deduped = deduplicate_signals(resolved)
    return [
        s
        for s in deduped
        if s.confidence >= MIN_SIGNAL_CONFIDENCE and s.strength >= MIN_SIGNAL_STRENGTH
    ]


def apply_relationship_signals(
    state: RelationshipState,
    signals: Sequence[RelationshipSignal],
) -> RelationshipStateUpdate | None:
    """Evaluate signals against deterministic policy and construct a bounded RelationshipStateUpdate.

    Steps:
    1. Resolve contradictions, deduplicate, and filter threshold-meeting signals.
    2. Calculate individual dimensional deltas.
    3. Aggregate deltas per dimension and clamp to [-MAX_AGGREGATE_DELTA_PER_DIMENSION, +MAX_AGGREGATE_DELTA_PER_DIMENSION].
    4. Calculate target values clamped to [0.0, 1.0].
    5. Return RelationshipStateUpdate with explicit target values, or None if no change.
    """
    eligible_signals = filter_eligible_signals(signals)
    if not eligible_signals:
        return None

    # 4. Accumulate per-dimension deltas
    accumulated_deltas: dict[str, float] = {
        "familiarity": 0.0,
        "trust": 0.0,
        "comfort": 0.0,
        "affection": 0.0,
        "attachment": 0.0,
        "respect": 0.0,
    }

    has_any_delta = False

    for sig in eligible_signals:
        base_mapping = SIGNAL_BASE_DELTAS.get(sig.signal_type, {})
        for dim, base_delta in base_mapping.items():
            if dim in accumulated_deltas:
                delta = calculate_signal_delta(sig, base_delta)
                accumulated_deltas[dim] += delta
                has_any_delta = True

    if not has_any_delta:
        return None

    # 5. Clamp aggregate deltas and compute new target values
    updates: dict[str, float] = {}

    for dim, total_delta in accumulated_deltas.items():
        if abs(total_delta) > 1e-9:
            clamped_total = max(
                -MAX_AGGREGATE_DELTA_PER_DIMENSION,
                min(MAX_AGGREGATE_DELTA_PER_DIMENSION, total_delta),
            )
            current_val = getattr(state, dim)
            target_val = round(max(0.0, min(1.0, current_val + clamped_total)), 6)
            if abs(target_val - current_val) > 1e-9:
                updates[dim] = target_val

    if not updates:
        return None

    return RelationshipStateUpdate(**updates)


def apply_relationship_signal(
    state: RelationshipState,
    signal: RelationshipSignal,
) -> RelationshipStateUpdate | None:
    """Convenience helper to apply a single relationship signal against current state."""
    return apply_relationship_signals(state=state, signals=[signal])
