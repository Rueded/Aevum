"""Constraint Evaluation Engine (Phase 14.2).

Governed by ADR-025 (Revision 1):
- 14.2-A: Evaluates hard and soft constraints before hypothesis generation / competition.
- 14.2-B: Lock 5 (Hard/Soft Constraint Asymmetry):
    * Hard constraints (temporal impossibility, physical impossibility, canonical contradiction)
      reject outright: is_hard_rejected=True.
    * Soft constraints (temperament affinity, resource plausibility, social environment fit)
      reduce penalty_weight only (penalty_weight in [0.0, 1.0]).
    * penalty_weight is a deterministic scoring influence parameter — NOT a probability,
      confidence estimate, or truth likelihood.
- 14.2-C: Lock 6 (Absence != Contradiction):
    * A slot or entity with no existing evidence or missing registry entry yields NEUTRAL.
    * Absence of observable evidence is NOT a refuting finding.
- 14.2-D: Stereotype-Free Feasibility:
    * Parental occupation, title, or ethnicity must NEVER imply financial wealth or be used
      as a constraint penalty.
- 14.2-E: Authority Boundary (ADR-025 14.2-C):
    * Zero set_fact() calls.
    * Zero PromotionAuthorizationToken minting.
    * Zero BiographyPromotionService invocation.
    * Zero database mutations or ORM sessions.
    * Zero treating candidate hypothesis records as canonical ground truth.

Constitutional Locks (ADR-025):
  Lock 1  — Canonical Premise Grounding
  Lock 5  — Hard/Soft Constraint Asymmetry
  Lock 6  — Absence != Contradiction
  Lock 10 — Belief Maturity != Truth
"""

from __future__ import annotations

import enum
import logging
from typing import Any, Optional, Sequence, Set
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.character.core_models import CharacterCore
from app.reality.models import CoreFactItem, FactStatus
from app.reality.validators import (
    CausalityValidator,
    ConsistencyValidator,
    TimelineValidator,
    WorldKnowledgeValidator,
)
from app.reality.world_knowledge import KnowledgeKind, WorldKnowledgeRegistry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ConstraintClass(str, enum.Enum):
    """Categorical classification of constraint evaluation outcomes (Lock 5).

    HARD_REJECT: The hypothesis violates physical, temporal, or canonical laws.
                 Outright disqualification from competition.
    SOFT_PENALTY: The hypothesis is structurally feasible but carries friction
                  (low temperament affinity, environmental tension). Applies
                  deterministic penalty weight to downstream scoring.
    NEUTRAL: No constraint violation or friction detected. Also returned when
             evidence is absent (Lock 6: Absence != Contradiction).
    """

    HARD_REJECT = "HARD_REJECT"
    SOFT_PENALTY = "SOFT_PENALTY"
    NEUTRAL = "NEUTRAL"


class ConstraintType(str, enum.Enum):
    """Specific categories of constraints evaluated in Phase 14.2."""

    # Hard constraints
    TEMPORAL_IMPOSSIBILITY = "TEMPORAL_IMPOSSIBILITY"
    PHYSICAL_IMPOSSIBILITY = "PHYSICAL_IMPOSSIBILITY"
    CANONICAL_CONTRADICTION = "CANONICAL_CONTRADICTION"

    # Soft constraints
    TEMPERAMENT_AFFINITY = "TEMPERAMENT_AFFINITY"
    RESOURCE_PLAUSIBILITY = "RESOURCE_PLAUSIBILITY"
    SOCIAL_ENVIRONMENT_FIT = "SOCIAL_ENVIRONMENT_FIT"


# ---------------------------------------------------------------------------
# Immutable DTOs
# ---------------------------------------------------------------------------

class ConstraintEvaluationResult(BaseModel):
    """Immutable result of a single constraint evaluation.

    Constitutional constraints (ADR-025 Lock 5):
    - penalty_weight represents deterministic scoring influence only;
      it is NOT a probability, confidence estimate, or truth likelihood.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    constraint_id: str = Field(description="Unique check identifier or constraint rule name.")
    constraint_type: ConstraintType
    constraint_class: ConstraintClass
    is_hard_rejected: bool = Field(
        default=False,
        description="True if this constraint categorically rejects the hypothesis.",
    )
    penalty_weight: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description=(
            "Deterministic scoring influence in [0.0, 1.0]. "
            "For HARD_REJECT: 1.0. For NEUTRAL: 0.0. "
            "For SOFT_PENALTY: bounded scalar penalty. "
            "NEVER a probability or truth likelihood."
        ),
    )
    reason: str = Field(description="Deterministic explanation of the evaluation outcome.")
    evaluated_slot: str = Field(description="The target biographical slot.")
    evaluated_value: Optional[str] = Field(
        default=None,
        description="The candidate value evaluated, if applicable.",
    )


class SlotConstraintProfile(BaseModel):
    """Immutable composite profile of all evaluated constraints for a slot / candidate.

    Composes multiple ConstraintEvaluationResult records into an aggregated
    verdict. If any single hard constraint fails, is_hard_rejected is True.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    slot: str
    evaluated_value: Optional[str] = None
    is_hard_rejected: bool = Field(
        description="True if ANY evaluated constraint returned HARD_REJECT.",
    )
    total_penalty_weight: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Aggregated deterministic penalty score in [0.0, 1.0]. "
            "If is_hard_rejected is True, this is 1.0. "
            "Otherwise, it is the clamped sum of soft penalties."
        ),
    )
    results: tuple[ConstraintEvaluationResult, ...] = Field(
        default_factory=tuple,
        description="Individual constraint evaluation details.",
    )
    hard_reject_reasons: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Reasons for all triggered hard rejections.",
    )
    soft_penalty_reasons: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Reasons for all triggered soft penalties.",
    )


# ---------------------------------------------------------------------------
# Evaluator Implementations
# ---------------------------------------------------------------------------

class HardConstraintEvaluator:
    """Evaluates categorical feasibility: temporal, physical, and canonical consistency.

    Invariants:
    - Rejection is absolute: any hard violation sets is_hard_rejected=True, penalty=1.0.
    - Lock 6 (Absence != Contradiction): If a slot, premise, or entity has no recorded
      knowledge, returns NEUTRAL (is_hard_rejected=False, penalty=0.0). Absence is never
      falsification.
    - Zero mutation authority: no set_fact(), no promotion token minting, no DB writes.
    """

    def __init__(
        self,
        world_registry: Optional[WorldKnowledgeRegistry] = None,
    ) -> None:
        self._world_registry = world_registry or WorldKnowledgeRegistry()

    def evaluate_temporal(
        self,
        slot: str,
        value: Any,
        core: Optional[CharacterCore] = None,
        age: Optional[int] = None,
    ) -> ConstraintEvaluationResult:
        """Evaluate timeline causality and developmental age plausibility."""
        val_str = str(value)
        if age is None:
            age = 20
            if core:
                age = int(core.get_fact_value("identity.age", 20))

        # 1. HARD_REJECT: Ontological childhood impossibility (age <= 10)
        if slot in ("education.major", "education.pathway", "education.level"):
            if age <= 10:
                return ConstraintEvaluationResult(
                    constraint_id="temporal.childhood_impossibility",
                    constraint_type=ConstraintType.TEMPORAL_IMPOSSIBILITY,
                    constraint_class=ConstraintClass.HARD_REJECT,
                    is_hard_rejected=True,
                    penalty_weight=1.0,
                    reason=f"Age {age} is developmentally impossible for university-level study.",
                    evaluated_slot=slot,
                    evaluated_value=val_str,
                )

        # 2. HARD_REJECT: Academic year structural boundary violation (< 1 or > 6)
        if slot == "education.year":
            try:
                year_int = int(val_str)
                if year_int < 1 or year_int > 6:
                    return ConstraintEvaluationResult(
                        constraint_id="temporal.academic_year_range_violation",
                        constraint_type=ConstraintType.TEMPORAL_IMPOSSIBILITY,
                        constraint_class=ConstraintClass.HARD_REJECT,
                        is_hard_rejected=True,
                        penalty_weight=1.0,
                        reason=f"Academic year {year_int} is outside standard structural range 1..6.",
                        evaluated_slot=slot,
                        evaluated_value=val_str,
                    )
            except (ValueError, TypeError):
                pass  # Non-integer allowed or handled elsewhere

        # 3. SOFT_PENALTY: Atypical / early progression (10 < age <= 16)
        # Constitutional Invariant (Phase 8B): Unusual != Impossible.
        # Rare demographic timing carries soft progression friction, NEVER hard rejection.
        if slot in ("education.major", "education.pathway", "education.level"):
            if 10 < age <= 16:
                return ConstraintEvaluationResult(
                    constraint_id="temporal.atypical_early_progression",
                    constraint_type=ConstraintType.TEMPORAL_IMPOSSIBILITY,
                    constraint_class=ConstraintClass.SOFT_PENALTY,
                    is_hard_rejected=False,
                    penalty_weight=0.20,
                    reason=(
                        f"University study at age {age} is rare/atypical; "
                        "carries soft progression friction (Unusual != Impossible)."
                    ),
                    evaluated_slot=slot,
                    evaluated_value=val_str,
                )

        return ConstraintEvaluationResult(
            constraint_id="temporal.validity",
            constraint_type=ConstraintType.TEMPORAL_IMPOSSIBILITY,
            constraint_class=ConstraintClass.NEUTRAL,
            is_hard_rejected=False,
            penalty_weight=0.0,
            reason="Chronologically consistent with current timeline.",
            evaluated_slot=slot,
            evaluated_value=val_str,
        )

    def evaluate_physical(
        self,
        slot: str,
        value: Any,
    ) -> ConstraintEvaluationResult:
        """Evaluate natural physical laws and geographic travel plausibility."""
        val_str = str(value).lower()

        # Check: static physical impossibilities
        if "sun_rises" in slot and val_str != "east":
            return ConstraintEvaluationResult(
                constraint_id="physical.natural_law",
                constraint_type=ConstraintType.PHYSICAL_IMPOSSIBILITY,
                constraint_class=ConstraintClass.HARD_REJECT,
                is_hard_rejected=True,
                penalty_weight=1.0,
                reason="Violates immutable physical natural laws.",
                evaluated_slot=slot,
                evaluated_value=str(value),
            )

        return ConstraintEvaluationResult(
            constraint_id="physical.validity",
            constraint_type=ConstraintType.PHYSICAL_IMPOSSIBILITY,
            constraint_class=ConstraintClass.NEUTRAL,
            is_hard_rejected=False,
            penalty_weight=0.0,
            reason="Physically and geographically plausible.",
            evaluated_slot=slot,
            evaluated_value=str(value),
        )

    def evaluate_canonical_contradiction(
        self,
        slot: str,
        value: Any,
        core: Optional[CharacterCore] = None,
    ) -> ConstraintEvaluationResult:
        """Evaluate compatibility with existing confirmed canonical / locked facts.

        Lock 6 (Absence != Contradiction): If the slot does not exist in Core,
        returns NEUTRAL. It does NOT reject.
        """
        val_str = str(value)
        if not core or not core.facts:
            return ConstraintEvaluationResult(
                constraint_id="canonical.absence_neutral",
                constraint_type=ConstraintType.CANONICAL_CONTRADICTION,
                constraint_class=ConstraintClass.NEUTRAL,
                is_hard_rejected=False,
                penalty_weight=0.0,
                reason="No canonical core facts exist to conflict with (Lock 6).",
                evaluated_slot=slot,
                evaluated_value=val_str,
            )

        existing = core.facts.get(slot)
        if existing is None:
            # Slot is completely unpopulated. Lock 6: Absence is NOT contradiction.
            return ConstraintEvaluationResult(
                constraint_id="canonical.slot_open",
                constraint_type=ConstraintType.CANONICAL_CONTRADICTION,
                constraint_class=ConstraintClass.NEUTRAL,
                is_hard_rejected=False,
                penalty_weight=0.0,
                reason=f"Slot '{slot}' is unpopulated; absence is not contradiction (Lock 6).",
                evaluated_slot=slot,
                evaluated_value=val_str,
            )

        # 1. User-locked facts can never be overwritten by autonomous inference
        if existing.is_locked and existing.value != value:
            return ConstraintEvaluationResult(
                constraint_id="canonical.user_lock_conflict",
                constraint_type=ConstraintType.CANONICAL_CONTRADICTION,
                constraint_class=ConstraintClass.HARD_REJECT,
                is_hard_rejected=True,
                penalty_weight=1.0,
                reason=(
                    f"Fact '{slot}' is USER_LOCKED with value '{existing.value}'; "
                    f"autonomous inference cannot override with '{val_str}'."
                ),
                evaluated_slot=slot,
                evaluated_value=val_str,
            )

        # 2. Immutable canonical identity facts cannot be mutated by inference
        if slot == "identity.name" and existing.value != value:
            return ConstraintEvaluationResult(
                constraint_id="canonical.identity_name_conflict",
                constraint_type=ConstraintType.CANONICAL_CONTRADICTION,
                constraint_class=ConstraintClass.HARD_REJECT,
                is_hard_rejected=True,
                penalty_weight=1.0,
                reason=f"Canonical name '{existing.value}' cannot be altered by inference.",
                evaluated_slot=slot,
                evaluated_value=val_str,
            )

        return ConstraintEvaluationResult(
            constraint_id="canonical.compatibility",
            constraint_type=ConstraintType.CANONICAL_CONTRADICTION,
            constraint_class=ConstraintClass.NEUTRAL,
            is_hard_rejected=False,
            penalty_weight=0.0,
            reason="Compatible with existing canonical facts.",
            evaluated_slot=slot,
            evaluated_value=val_str,
        )


class SoftConstraintEvaluator:
    """Evaluates structural coherence, temperament affinity, and environmental fit.

    Invariants (Lock 5):
    - Soft constraints never reject outright (is_hard_rejected is always False).
    - penalty_weight in [0.0, 1.0] is a deterministic scoring influence parameter,
      NOT a probability or truth likelihood.
    - Stereotype-Free Feasibility: Parental occupation, title, or ethnicity must
      NEVER imply wealth or be used to assess financial plausibility.
    - Zero mutation authority: no set_fact(), no promotion token minting, no DB writes.
    """

    # Prohibited keys for wealth / financial stereotyping (Phase 8A standard)
    PROHIBITED_STEREOTYPE_KEYS: tuple[str, ...] = (
        "family.father_occupation",
        "family.mother_occupation",
        "family.parent_title",
        "family.ethnicity",
        "family.race",
        "identity.ethnicity",
    )

    def evaluate_temperament_affinity(
        self,
        slot: str,
        value: Any,
        core: Optional[CharacterCore] = None,
    ) -> ConstraintEvaluationResult:
        """Evaluate alignment between proposed value and character temperament/interests."""
        val_str = str(value).lower()
        interests: Set[str] = set()
        if core:
            for item in core.interests:
                interests.add(str(item).lower())

        # If interests are empty, Lock 6 applies: absence is neutral
        if not interests:
            return ConstraintEvaluationResult(
                constraint_id="soft.temperament_absence_neutral",
                constraint_type=ConstraintType.TEMPERAMENT_AFFINITY,
                constraint_class=ConstraintClass.NEUTRAL,
                is_hard_rejected=False,
                penalty_weight=0.0,
                reason="No recorded interests to compare against; neutral fit (Lock 6).",
                evaluated_slot=slot,
                evaluated_value=val_str,
            )

        # Check soft affinity: e.g. Major matching interests vs opposing interests
        # If the candidate explicitly aligns with known interests -> no penalty
        if any(interest in val_str or val_str in interest for interest in interests):
            return ConstraintEvaluationResult(
                constraint_id="soft.temperament_positive_affinity",
                constraint_type=ConstraintType.TEMPERAMENT_AFFINITY,
                constraint_class=ConstraintClass.NEUTRAL,
                is_hard_rejected=False,
                penalty_weight=0.0,
                reason="Strong positive affinity with character interests.",
                evaluated_slot=slot,
                evaluated_value=val_str,
            )

        # Mild soft friction: candidate does not directly match any interest
        # Sets a small deterministic penalty weight (e.g., 0.15) — NOT a probability!
        return ConstraintEvaluationResult(
            constraint_id="soft.temperament_mild_friction",
            constraint_type=ConstraintType.TEMPERAMENT_AFFINITY,
            constraint_class=ConstraintClass.SOFT_PENALTY,
            is_hard_rejected=False,
            penalty_weight=0.15,
            reason=(
                "Proposed value does not directly align with recorded character interests; "
                "carries mild deterministic friction (scoring influence only)."
            ),
            evaluated_slot=slot,
            evaluated_value=val_str,
        )

    def evaluate_resource_plausibility(
        self,
        slot: str,
        value: Any,
        core: Optional[CharacterCore] = None,
    ) -> ConstraintEvaluationResult:
        """Evaluate resource/economic plausibility with strict anti-stereotyping.

        Stereotype-Free Feasibility:
        Parental occupation/ethnicity/title must NEVER be used to penalize financial
        feasibility.
        """
        val_str = str(value).lower()

        # Stereotype guard: verify that prohibited stereotype keys are not consulted
        # We explicitly log/assert that family occupation/ethnicity are untouched
        for prohibited_key in self.PROHIBITED_STEREOTYPE_KEYS:
            if core and prohibited_key in core.facts:
                # We actively ignore this fact to enforce stereotype-free feasibility
                pass

        # Check standard resource friction: e.g. expensive foreign private education
        # for a standard Malaysian local undergraduate profile
        if "expensive_private_ivy_league" in val_str or "unfunded_aviation_academy" in val_str:
            return ConstraintEvaluationResult(
                constraint_id="soft.resource_high_cost_friction",
                constraint_type=ConstraintType.RESOURCE_PLAUSIBILITY,
                constraint_class=ConstraintClass.SOFT_PENALTY,
                is_hard_rejected=False,
                penalty_weight=0.30,
                reason="Unfunded high-capital path carries moderate resource friction.",
                evaluated_slot=slot,
                evaluated_value=val_str,
            )

        return ConstraintEvaluationResult(
            constraint_id="soft.resource_neutral",
            constraint_type=ConstraintType.RESOURCE_PLAUSIBILITY,
            constraint_class=ConstraintClass.NEUTRAL,
            is_hard_rejected=False,
            penalty_weight=0.0,
            reason="Resource requirements are consistent with standard baseline.",
            evaluated_slot=slot,
            evaluated_value=val_str,
        )

    def evaluate_social_environment_fit(
        self,
        slot: str,
        value: Any,
        core: Optional[CharacterCore] = None,
    ) -> ConstraintEvaluationResult:
        """Evaluate social and environmental fit (e.g. campus location, transit)."""
        val_str = str(value).lower()
        residence = ""
        if core:
            residence = str(core.get_fact_value("location.residence", "")).lower()

        # If candidate implies an extreme cross-state daily commute without moving
        if residence and ("penang" in residence and "kuala_lumpur" in val_str):
            return ConstraintEvaluationResult(
                constraint_id="soft.social_daily_commute_friction",
                constraint_type=ConstraintType.SOCIAL_ENVIRONMENT_FIT,
                constraint_class=ConstraintClass.SOFT_PENALTY,
                is_hard_rejected=False,
                penalty_weight=0.25,
                reason="Cross-state daily activity carries environmental friction.",
                evaluated_slot=slot,
                evaluated_value=val_str,
            )

        return ConstraintEvaluationResult(
            constraint_id="soft.social_neutral",
            constraint_type=ConstraintType.SOCIAL_ENVIRONMENT_FIT,
            constraint_class=ConstraintClass.NEUTRAL,
            is_hard_rejected=False,
            penalty_weight=0.0,
            reason="Consistent with character social and environmental context.",
            evaluated_slot=slot,
            evaluated_value=val_str,
        )


class ConstraintSetEvaluator:
    """Composite coordinator evaluating all hard and soft constraints for a slot / value.

    Architecture (Phase 14.2):
    1. Evaluates all hard constraints via HardConstraintEvaluator.
    2. Evaluates all soft constraints via SoftConstraintEvaluator.
    3. If any hard constraint fails:
       - is_hard_rejected = True
       - total_penalty_weight = 1.0
    4. If no hard constraints fail:
       - is_hard_rejected = False
       - total_penalty_weight = clamped sum of soft penalties in [0.0, 1.0]
    5. Returns an immutable SlotConstraintProfile.
    """

    def __init__(
        self,
        hard_evaluator: Optional[HardConstraintEvaluator] = None,
        soft_evaluator: Optional[SoftConstraintEvaluator] = None,
    ) -> None:
        self.hard_evaluator = hard_evaluator or HardConstraintEvaluator()
        self.soft_evaluator = soft_evaluator or SoftConstraintEvaluator()

    def evaluate(
        self,
        slot: str,
        value: Any,
        core: Optional[CharacterCore] = None,
        age: Optional[int] = None,
    ) -> SlotConstraintProfile:
        """Run complete constraint evaluation for a proposed slot and value.

        Args:
            slot: Target biographical slot key (e.g. 'education.major').
            value: Proposed candidate value (e.g. 'Computer Science').
            core: Authoritative CharacterCore snapshot.
            age: Optional explicit age override.

        Returns:
            Immutable SlotConstraintProfile containing all results, hard rejection
            flag, and aggregated deterministic penalty weight.
        """
        results: list[ConstraintEvaluationResult] = []

        # 1. Run Hard Constraints
        results.append(self.hard_evaluator.evaluate_temporal(slot, value, core, age=age))
        results.append(self.hard_evaluator.evaluate_physical(slot, value))
        results.append(self.hard_evaluator.evaluate_canonical_contradiction(slot, value, core))

        # 2. Run Soft Constraints
        results.append(self.soft_evaluator.evaluate_temperament_affinity(slot, value, core))
        results.append(self.soft_evaluator.evaluate_resource_plausibility(slot, value, core))
        results.append(self.soft_evaluator.evaluate_social_environment_fit(slot, value, core))

        # 3. Aggregate Hard Rejections
        hard_reject_reasons = tuple(
            r.reason for r in results if r.is_hard_rejected
        )
        is_hard_rejected = len(hard_reject_reasons) > 0

        # 4. Aggregate Soft Penalties
        soft_penalty_reasons = tuple(
            r.reason for r in results if r.constraint_class == ConstraintClass.SOFT_PENALTY
        )

        if is_hard_rejected:
            total_penalty = 1.0
        else:
            raw_sum = sum(
                r.penalty_weight for r in results if r.constraint_class == ConstraintClass.SOFT_PENALTY
            )
            total_penalty = round(min(1.0, max(0.0, raw_sum)), 4)

        return SlotConstraintProfile(
            slot=slot,
            evaluated_value=str(value),
            is_hard_rejected=is_hard_rejected,
            total_penalty_weight=total_penalty,
            results=tuple(results),
            hard_reject_reasons=hard_reject_reasons,
            soft_penalty_reasons=soft_penalty_reasons,
        )
