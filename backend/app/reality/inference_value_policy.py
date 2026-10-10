"""Deterministic Inference Value Policy for Phase 8A (Autonomous Reality & Life Inference).

Strict Invariants:
- Evaluates whether a biographical slot is structurally worth attempting to infer.
- Prohibits the Anti-Obsession Fallacy: Aevum must NOT attempt to fill every NULL field.
- Pure deterministic policy: zero candidate generation, zero LLM calls, zero DB mutations.
- Avoids arbitrary mechanical 'count >= N' rules in favor of domain and life-stage significance.
"""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.character.core_models import CharacterCore
from app.reality.inference_models import InferenceValueAssessment, InferenceValueTier
from app.reality.models import FactStatus


class InferenceValuePolicy:
    """Evaluates the structural utility and readiness of attribute slots for autonomous inference."""

    # Slots strictly forbidden from autonomous generation (core invariants)
    FORBIDDEN_SLOTS: frozenset[str] = frozenset({
        "identity.name",
        "identity.birth_year",
        "identity.species",
        "world.physics",
    })

    # Speculative narrative slots that must not be hallucinated out of thin air
    SPECULATIVE_NARRATIVE_SLOTS: frozenset[str] = frozenset({
        "relationships.childhood_friend",
        "identity.pet_name",
        "narrative.trauma_history",
    })

    # Trivial lifestyle preferences with negligible structural life significance
    LOW_IMPACT_PREFERENCE_SLOTS: frozenset[str] = frozenset({
        "preferences.study_beverage",
        "preferences.favorite_color",
        "lifestyle.commute_mode",
        "lifestyle.routine",
    })

    # Core high-value autonomous inference targets
    HIGH_VALUE_SLOTS: frozenset[str] = frozenset({
        "education.major",
        "education.institution",
        "education.year",
        "education.pathway",
        "career.aspiration",
        "family.parents_occupation",
        "family.childhood_background",
        "lifestyle.transit",
        "lifestyle.beverage",
        "education.secondary_school",
        "education.music_qualification",
    })

    @classmethod
    def evaluate_slot(
        cls,
        slot_name: str,
        core: Optional["CharacterCore"] = None,
    ) -> InferenceValueAssessment:
        """Deterministically assess whether a slot is eligible and valuable for autonomous inference."""
        if not isinstance(slot_name, str) or not slot_name.strip():
            return InferenceValueAssessment(
                slot_name=str(slot_name),
                tier=InferenceValueTier.ZERO,
                is_worth_inferring=False,
                reason="Invalid slot name: must be a non-empty dot-notated string.",
            )

        slot = slot_name.strip()

        # 1. Check existing canonical state in core
        if core is not None:
            # Check user lock
            if core.is_locked(slot):
                return InferenceValueAssessment(
                    slot_name=slot,
                    tier=InferenceValueTier.ZERO,
                    is_worth_inferring=False,
                    reason=f"Slot '{slot}' is locked by user authority.",
                )

            # Check if already canonical
            existing_fact = core.get_fact(slot)
            if existing_fact is not None and existing_fact.status == FactStatus.CANONICAL:
                return InferenceValueAssessment(
                    slot_name=slot,
                    tier=InferenceValueTier.ZERO,
                    is_worth_inferring=False,
                    reason=f"Slot '{slot}' already contains canonical fact '{existing_fact.value}'.",
                )

        # 2. Check forbidden core identity invariants
        if slot in cls.FORBIDDEN_SLOTS:
            return InferenceValueAssessment(
                slot_name=slot,
                tier=InferenceValueTier.ZERO,
                is_worth_inferring=False,
                reason="Forbidden slot: core identity invariant or physical world baseline.",
            )

        # 3. Check speculative narrative slots
        if slot in cls.SPECULATIVE_NARRATIVE_SLOTS:
            return InferenceValueAssessment(
                slot_name=slot,
                tier=InferenceValueTier.ZERO,
                is_worth_inferring=False,
                reason="Unanchored speculative narrative slot: autonomous generation prohibited.",
            )

        # 4. Check low-impact trivial preferences
        if slot in cls.LOW_IMPACT_PREFERENCE_SLOTS:
            return InferenceValueAssessment(
                slot_name=slot,
                tier=InferenceValueTier.LOW,
                is_worth_inferring=False,
                reason="Low-impact preference detail: unnecessary to infer autonomously.",
            )

        # 5. Evaluate high-value autonomous slots
        if slot in cls.HIGH_VALUE_SLOTS:
            edu_level = None
            if core is not None:
                lvl_val = core.get_fact_value("education.level")
                if lvl_val is not None:
                    edu_level = str(lvl_val).strip().lower()

            if slot == "education.major":
                if edu_level in ("postgraduate", "master", "phd"):
                    return InferenceValueAssessment(
                        slot_name=slot,
                        tier=InferenceValueTier.LOW,
                        is_worth_inferring=False,
                        reason=f"Undergraduate major inference is inapplicable: character education level is post-undergraduate ('{edu_level}').",
                    )
                return InferenceValueAssessment(
                    slot_name=slot,
                    tier=InferenceValueTier.HIGH,
                    is_worth_inferring=True,
                    reason="High-value education milestone central to character identity and life stage.",
                )

            if slot == "education.institution":
                return InferenceValueAssessment(
                    slot_name=slot,
                    tier=InferenceValueTier.HIGH,
                    is_worth_inferring=True,
                    reason="High-value tertiary education institution shaping geographic and social context.",
                )

            if slot == "education.year":
                return InferenceValueAssessment(
                    slot_name=slot,
                    tier=InferenceValueTier.MEDIUM,
                    is_worth_inferring=True,
                    reason="Academic progression year grounding longitudinal life status.",
                )

            if slot == "education.pathway":
                if edu_level in ("undergraduate", "bachelor", "master", "phd", "graduated"):
                    return InferenceValueAssessment(
                        slot_name=slot,
                        tier=InferenceValueTier.LOW,
                        is_worth_inferring=False,
                        reason=f"Pre-university pathway inference is inapplicable: character is already in or past university ('{edu_level}').",
                    )
                return InferenceValueAssessment(
                    slot_name=slot,
                    tier=InferenceValueTier.HIGH,
                    is_worth_inferring=True,
                    reason="High-value post-secondary pathway choice relevant to character progression.",
                )

            if slot == "career.aspiration":
                return InferenceValueAssessment(
                    slot_name=slot,
                    tier=InferenceValueTier.MEDIUM,
                    is_worth_inferring=True,
                    reason="Meaningful vocational aspiration aligning with character values and interests.",
                )

            if slot == "family.parents_occupation":
                return InferenceValueAssessment(
                    slot_name=slot,
                    tier=InferenceValueTier.HIGH,
                    is_worth_inferring=True,
                    reason="Family upbringing and parental professions grounding socioeconomic reality.",
                )

            if slot in (
                "family.childhood_background",
                "lifestyle.transit",
                "lifestyle.beverage",
                "education.secondary_school",
                "education.music_qualification",
            ):
                return InferenceValueAssessment(
                    slot_name=slot,
                    tier=InferenceValueTier.MEDIUM,
                    is_worth_inferring=True,
                    reason=f"Cohesive autobiographical detail for slot '{slot}'.",
                )

        # 6. Default for unconfigured slots
        return InferenceValueAssessment(
            slot_name=slot,
            tier=InferenceValueTier.LOW,
            is_worth_inferring=False,
            reason=f"Slot '{slot}' is not designated for autonomous inference.",
        )
