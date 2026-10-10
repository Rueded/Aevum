"""Volatility Decay Policy for Reality Candidates (Phase 7D.2).

Enforces Invariant 32:
- Absence of evidence is not contradictory evidence.
- Decay is governed by domain-aware slot volatility profiles (hours for transient,
  days/weeks for preferences, months/years for biography, infinite for immutable facts).
- 7 days serves as a standardized test fixture, not a universal expiration rule.
- Volatility decay NEVER transitions a candidate to REJECTED (only explicit contradictory
  evidence can reject). When decayed below threshold, candidates become DORMANT.
- Canonical reality facts are never deleted by volatility decay.
"""

from datetime import datetime, timezone
import enum
import math
from typing import Optional

from app.reality.candidate_models import CandidateHypothesis, CandidateLifecycleState


class FactVolatilityCategory(str, enum.Enum):
    """Categorical shelf-life and decay profile for reality claims."""

    TRANSIENT_STATE = "TRANSIENT_STATE"          # Current activity, immediate mood (half-life: 6 hours)
    EPHEMERAL_ROUTINE = "EPHEMERAL_ROUTINE"      # Daily schedule, transit mode (half-life: 24 hours)
    PREFERENCE_INTEREST = "PREFERENCE_INTEREST"  # Beverage, hobbies, casual tastes (half-life: 14 days)
    BIOGRAPHICAL_MAJOR = "BIOGRAPHICAL_MAJOR"    # Degree, university, hometown (half-life: 365 days)
    IMMUTABLE_CORE = "IMMUTABLE_CORE"            # Birth year, siblings baseline (infinite shelf-life)


# Half-life durations in seconds per category
VOLATILITY_HALF_LIVES_SECONDS: dict[FactVolatilityCategory, Optional[float]] = {
    FactVolatilityCategory.TRANSIENT_STATE: 6.0 * 3600.0,
    FactVolatilityCategory.EPHEMERAL_ROUTINE: 24.0 * 3600.0,
    FactVolatilityCategory.PREFERENCE_INTEREST: 14.0 * 86400.0,
    FactVolatilityCategory.BIOGRAPHICAL_MAJOR: 365.0 * 86400.0,
    FactVolatilityCategory.IMMUTABLE_CORE: None,  # Infinite: no decay
}


def classify_slot_volatility(slot_name: str) -> FactVolatilityCategory:
    """Determine volatility profile by slot key path."""
    lower_slot = slot_name.lower()

    if lower_slot.startswith(("life.current", "mood.", "ephemeral.", "state.")):
        return FactVolatilityCategory.TRANSIENT_STATE
    if lower_slot.startswith(("schedule.", "daily.", "transit.")):
        return FactVolatilityCategory.EPHEMERAL_ROUTINE
    if lower_slot.startswith(("preferences.", "interests.", "lifestyle.", "habits.")):
        return FactVolatilityCategory.PREFERENCE_INTEREST
    if lower_slot.startswith(("identity.birth", "identity.id", "identity.gender")):
        return FactVolatilityCategory.IMMUTABLE_CORE
    if lower_slot.startswith(("education.", "career.", "family.", "location.")):
        return FactVolatilityCategory.BIOGRAPHICAL_MAJOR

    return FactVolatilityCategory.PREFERENCE_INTEREST


class VolatilityDecayPolicy:
    """Evaluates temporal decay of candidate hypotheses."""

    DORMANCY_THRESHOLD: float = 0.25

    @classmethod
    def compute_decay_multiplier(
        cls,
        category: FactVolatilityCategory,
        elapsed_seconds: float,
    ) -> float:
        """Calculate exponential half-life decay multiplier [0.0, 1.0]."""
        half_life = VOLATILITY_HALF_LIVES_SECONDS.get(category)
        if half_life is None or elapsed_seconds <= 0:
            return 1.0
        return float(math.pow(0.5, elapsed_seconds / half_life))

    @classmethod
    def apply_decay(
        cls,
        candidate: CandidateHypothesis,
        as_of: Optional[datetime] = None,
    ) -> CandidateHypothesis:
        """Apply volatility decay to candidate plausibility without deleting provenance.
        
        Transitions to DORMANT if decayed score falls below DORMANCY_THRESHOLD.
        Strictly NEVER transitions to REJECTED.
        """
        now = as_of or datetime.now(timezone.utc)
        cand_updated = candidate.updated_at
        if cand_updated.tzinfo is None:
            cand_updated = cand_updated.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        elapsed = (now - cand_updated).total_seconds()
        if elapsed <= 0:
            return candidate

        category = classify_slot_volatility(candidate.slot_name)
        decay_mult = cls.compute_decay_multiplier(category, elapsed)

        if decay_mult >= 0.999:
            return candidate

        original_plausibility = candidate.plausibility
        decayed_score = round(
            original_plausibility.composite_plausibility_score * decay_mult,
            4,
        )

        new_plausibility = original_plausibility.model_copy(
            update={"composite_plausibility_score": decayed_score}
        )

        new_state = candidate.lifecycle_state
        if (
            decayed_score < cls.DORMANCY_THRESHOLD
            and candidate.lifecycle_state in (
                CandidateLifecycleState.ACTIVE,
                CandidateLifecycleState.PERSISTED,
                CandidateLifecycleState.GENERATED,
            )
        ):
            new_state = CandidateLifecycleState.DORMANT

        return candidate.model_copy(
            update={
                "plausibility": new_plausibility,
                "lifecycle_state": new_state,
                "updated_at": now,
            }
        )
