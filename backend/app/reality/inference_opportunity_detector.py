"""Inference Opportunity Detector for Phase 8A.2 (Autonomous Reality & Life Inference).

Strict Invariants:
- Answers exactly: 'Should Aevum attempt autonomous inference for one currently open life slot during this cycle?'
- Emits at most ONE InferenceProposalRequest per cycle (Cycle Budget Enforced).
- Zero candidate generation, zero scoring, zero LLM calls, zero DB mutations.
- Enforces the 7-stage deterministic decision pipeline:
  1. Slot state (Not canonical, not locked)
  2. Active candidate (No duplicate active hypothesis)
  3. Cooldown (Respects transient cooldown set)
  4. Inference Value (HIGH/MEDIUM required via InferenceValuePolicy)
  5. Premise Sufficiency (Domain-specific converging evidence; count >= N forbidden)
  6. Primary Anchor (>= 1 PRIMARY_CANONICAL premise required; purely inferred chains blocked)
  7. Cycle Budget (At most one slot emitted per cycle)
"""

from datetime import datetime, timezone
import logging
from typing import Any, Optional, Sequence
import uuid

from app.character.core_models import CharacterCore
from app.reality.candidate_models import CandidateLifecycleState
from app.reality.candidate_repository import CandidateRepository
from app.reality.inference_models import (
    InferenceProposalRequest,
    InferenceValueTier,
    PremiseOriginCategory,
    categorize_fact_origin,
)
from app.reality.inference_value_policy import InferenceValuePolicy
from app.reality.models import CoreFactItem, FactStatus

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InferenceOpportunityDetector:
    """Deterministic detector governing whether an autonomous inference opportunity may open."""

    # Supported candidate slots in deterministic evaluation priority order
    DEFAULT_SLOT_PRIORITY: tuple[str, ...] = (
        "education.major",
        "education.pathway",
        "career.aspiration",
        "education.institution",
        "education.year",
        "family.parents_occupation",
        "family.childhood_background",
        "lifestyle.transit",
        "lifestyle.beverage",
        "education.secondary_school",
        "education.music_qualification",
    )

    # Domain mapping for supported slots
    SLOT_DOMAINS: dict[str, str] = {
        "education.pathway": "education",
        "education.major": "education",
        "education.institution": "education",
        "education.year": "education",
        "career.aspiration": "career",
        "family.parents_occupation": "family",
        "family.childhood_background": "family",
        "lifestyle.transit": "lifestyle",
        "lifestyle.beverage": "lifestyle",
        "education.secondary_school": "education",
        "education.music_qualification": "education",
    }

    # Static domain boundaries grounding each slot
    SLOT_CONSTRAINTS: dict[str, tuple[str, ...]] = {
        "education.pathway": (
            "post_secondary_pathway_requires_secondary_completion",
            "malaysian_pre_u_options_include_stpm_matrikulasi_foundation_diploma",
        ),
        "education.major": (
            "undergraduate_admission_requires_formal_secondary_qualification",
            "major_choice_must_respect_academic_prerequisites_and_talents",
        ),
        "education.institution": (
            "tertiary_admission_respects_geography_and_family_context",
            "reputable_universities_fit_undergraduate_profile",
        ),
        "education.year": (
            "undergraduate_progression_derives_from_age_and_pre_u_duration",
        ),
        "career.aspiration": (
            "career_aspiration_aligns_with_core_interests_and_education_trajectory",
        ),
        "family.parents_occupation": (
            "middle_class_professional_parents",
            "supportive_educated_family_background",
        ),
        "family.childhood_background": (
            "classical_piano_upbringing_since_childhood",
            "supportive_upbringing_in_kl_selangor",
        ),
        "lifestyle.transit": (
            "selangor_kl_and_penang_transit_realities",
        ),
        "lifestyle.beverage": (
            "malaysian_and_contemporary_beverage_preferences",
        ),
        "education.secondary_school": (
            "reputable_secondary_school_in_selangor_kl",
        ),
        "education.music_qualification": (
            "classical_music_piano_qualifications",
        ),
    }

    # Functional relevance category mappings for premise sufficiency
    # Maps slot -> list of functional dimensions and their matching fact keys/prefixes
    SLOT_RELEVANCE_DIMENSIONS: dict[str, dict[str, tuple[str, ...]]] = {
        "education.major": {
            "academic_foundation": (
                "education.level",
                "identity.occupation",
                "identity.age",
            ),
            "aptitude_grades": (
                "academics.spm_math_grade",
                "academics.spm_science_grade",
                "academics.spm_overall",
                "academics.subject_strengths",
                "academics.grades",
            ),
            "talents_skills": (
                "traits.musical_talent",
                "skills.instrument_playing",
                "skills.programming",
                "skills.artistic_talent",
                "skills.languages",
            ),
            "interests_passions": (
                "interests",
                "preferences.music",
                "preferences.music_activity",
                "interests.primary",
                "dislikes",
            ),
            "values_orientation": (
                "values.parental_expectation",
                "values.creativity",
                "values.career_stability",
                "values.independence",
                "traits.challenge_preference",
            ),
            "explicit_resources": (
                "family.socioeconomic_tier",
                "scholarship.status",
                "finances.budget_tier",
            ),
        },
        "education.institution": {
            "academic_foundation": (
                "education.level",
                "education.major",
                "identity.age",
                "identity.occupation",
            ),
            "geographic_context": (
                "location.residence",
                "family.background",
            ),
            "interests_talents": (
                "interests",
                "traits.musical_talent",
                "skills.instrument_playing",
            ),
            "family_resources": (
                "family.background",
                "family.socioeconomic_tier",
                "finances.budget_tier",
            ),
        },
        "education.year": {
            "temporal_readiness": (
                "identity.age",
                "education.level",
                "education.pathway",
            ),
            "academic_foundation": (
                "education.level",
                "identity.occupation",
            ),
        },
        "education.pathway": {
            "academic_readiness": (
                "academics.spm_overall",
                "academics.spm_results",
                "academics.high_school_completion",
                "education.level",
                "identity.age",
            ),
            "challenge_orientation": (
                "traits.challenge_preference",
                "traits.intellectual_style",
            ),
            "explicit_resources": (
                "family.socioeconomic_tier",
                "scholarship.status",
                "finances.budget_tier",
            ),
            "duration_preference": (
                "preferences.study_duration",
            ),
        },
        "career.aspiration": {
            "education_foundation": (
                "education.major",
                "education.level",
                "education.pathway",
            ),
            "skills_talents": (
                "traits.musical_talent",
                "skills.instrument_playing",
                "skills.programming",
                "skills.languages",
            ),
            "interests_passions": (
                "interests",
                "interests.primary",
                "preferences.music",
            ),
            "values_vocation": (
                "values.career_stability",
                "values.independence",
                "values.creativity",
                "traits.challenge_preference",
            ),
        },
        "family.parents_occupation": {
            "family_foundation": (
                "family.background",
                "identity.background",
                "identity.occupation",
            ),
        },
        "family.childhood_background": {
            "family_foundation": (
                "family.background",
                "identity.background",
            ),
            "music_passion": (
                "interests",
                "education.major",
            ),
        },
        "lifestyle.transit": {
            "location_context": (
                "location.residence",
                "identity.occupation",
                "education.level",
            ),
        },
        "lifestyle.beverage": {
            "lifestyle_context": (
                "interests",
                "identity.occupation",
            ),
        },
        "education.secondary_school": {
            "education_foundation": (
                "education.level",
                "identity.age",
                "family.background",
            ),
        },
        "education.music_qualification": {
            "music_foundation": (
                "interests",
                "education.level",
                "education.major",
            ),
        },
    }

    # Whitelist of irrelevant lifestyle facts that MUST NOT count toward premise sufficiency
    EXCLUDED_FACT_PREFIXES: tuple[str, ...] = (
        "preferences.study_beverage",
        "preferences.favorite_color",
        "lifestyle.transit",
        "lifestyle.commute_mode",
        "lifestyle.routine",
        "identity.name",
        "identity.species",
        "identity.birth_year",
        "world.physics",
    )

    @classmethod
    def detect_opportunity(
        cls,
        core: CharacterCore,
        active_candidate_slots: Optional[set[str]] = None,
        cooldown_slots: Optional[set[str]] = None,
        requested_slot: Optional[str] = None,
        cycle_id: Optional[str] = None,
    ) -> Optional[InferenceProposalRequest]:
        """Evaluate whether an autonomous inference opportunity should open for one slot.

        Args:
            core: Canonical CharacterCore reality snapshot.
            active_candidate_slots: Set of slot names currently having active hypotheses.
            cooldown_slots: Set of slot names currently in a cooldown window.
            requested_slot: Optional specific slot to evaluate (e.g. conversational crossroad).
            cycle_id: Deterministic identifier for this inference cycle.

        Returns:
            InferenceProposalRequest if an opportunity is justified; None otherwise.
        """
        active_slots = active_candidate_slots or set()
        cooling_slots = cooldown_slots or set()
        cycle = cycle_id or f"cycle_{uuid.uuid4().hex[:8]}"

        slots_to_evaluate: tuple[str, ...]
        if requested_slot:
            slots_to_evaluate = (requested_slot.strip(),)
        else:
            slots_to_evaluate = cls.DEFAULT_SLOT_PRIORITY

        # Cycle Budget Invariant: Evaluate slots and stop at the first eligible opportunity
        for slot in slots_to_evaluate:
            request = cls._evaluate_single_slot(
                slot_name=slot,
                core=core,
                active_slots=active_slots,
                cooldown_slots=cooling_slots,
                cycle_id=cycle,
            )
            if request is not None:
                logger.info(
                    "Inference opportunity detected for slot '%s' in cycle '%s'.",
                    slot,
                    cycle,
                )
                return request

        return None

    @classmethod
    async def detect_opportunity_async(
        cls,
        core: CharacterCore,
        candidate_repo: CandidateRepository,
        character_id: str = "aevum",
        cooldown_slots: Optional[set[str]] = None,
        requested_slot: Optional[str] = None,
        cycle_id: Optional[str] = None,
    ) -> Optional[InferenceProposalRequest]:
        """Async convenience method pre-fetching active candidate slots from CandidateRepository."""
        try:
            active_candidates = await candidate_repo.get_all_active_candidates(
                character_id=character_id,
                active_states=[
                    CandidateLifecycleState.GENERATED,
                    CandidateLifecycleState.PERSISTED,
                    CandidateLifecycleState.ACTIVE,
                    CandidateLifecycleState.PROMOTABLE,
                ],
            )
            active_slots = {
                c.slot_name for c in active_candidates
                if not c.is_quarantined
            }
        except Exception as exc:
            logger.error("Failed to query active candidates for opportunity detection: %s", exc)
            active_slots = set()

        return cls.detect_opportunity(
            core=core,
            active_candidate_slots=active_slots,
            cooldown_slots=cooldown_slots,
            requested_slot=requested_slot,
            cycle_id=cycle_id,
        )

    # -------------------------------------------------------------------------
    # Internal Pipeline Gate Evaluation
    # -------------------------------------------------------------------------

    @classmethod
    def _evaluate_single_slot(
        cls,
        slot_name: str,
        core: CharacterCore,
        active_slots: set[str],
        cooldown_slots: set[str],
        cycle_id: str,
    ) -> Optional[InferenceProposalRequest]:
        """Evaluate all 7 gates for a single attribute slot."""

        # ---------------------------------------------------------------------
        # GATE 1: SLOT STATE
        # ---------------------------------------------------------------------
        if core.is_locked(slot_name):
            logger.debug("Gate 1 failed: Slot '%s' is locked by user authority.", slot_name)
            return None

        existing_fact = core.get_fact(slot_name)
        if existing_fact is not None and existing_fact.status == FactStatus.CANONICAL:
            logger.debug("Gate 1 failed: Slot '%s' already contains canonical fact.", slot_name)
            return None

        # ---------------------------------------------------------------------
        # GATE 2: ACTIVE CANDIDATE
        # ---------------------------------------------------------------------
        if slot_name in active_slots:
            logger.debug("Gate 2 failed: Slot '%s' already has active candidate hypotheses.", slot_name)
            return None

        # ---------------------------------------------------------------------
        # GATE 3: COOLDOWN
        # ---------------------------------------------------------------------
        if slot_name in cooldown_slots:
            logger.debug("Gate 3 failed: Slot '%s' is currently in cooldown.", slot_name)
            return None

        # ---------------------------------------------------------------------
        # GATE 4: INFERENCE VALUE
        # ---------------------------------------------------------------------
        assessment = InferenceValuePolicy.evaluate_slot(slot_name, core=core)
        if not assessment.is_worth_inferring or assessment.tier in (InferenceValueTier.ZERO, InferenceValueTier.LOW):
            logger.debug(
                "Gate 4 failed: Slot '%s' has insufficient inference value (%s): %s",
                slot_name,
                assessment.tier.value,
                assessment.reason,
            )
            return None

        # ---------------------------------------------------------------------
        # GATE 5: PREMISE SUFFICIENCY & RELEVANCE
        # ---------------------------------------------------------------------
        relevant_premises = cls._extract_relevant_premises(slot_name, core)
        if not cls._is_premise_set_sufficient(slot_name, relevant_premises, core):
            logger.debug("Gate 5 failed: Premise sufficiency not met for slot '%s'.", slot_name)
            return None

        # ---------------------------------------------------------------------
        # GATE 6: PRIMARY CANONICAL ANCHOR
        # ---------------------------------------------------------------------
        has_primary_anchor = any(
            categorize_fact_origin(fact) == PremiseOriginCategory.PRIMARY_CANONICAL
            for fact in relevant_premises.values()
        )
        if not has_primary_anchor:
            logger.debug(
                "Gate 6 failed: Slot '%s' has no PRIMARY_CANONICAL anchor among premises. "
                "Purely derived inferred-from-inferred chains are forbidden.",
                slot_name,
            )
            return None

        # ---------------------------------------------------------------------
        # GATE 7: BOUNDED PROPOSAL REQUEST CONSTRUCTION
        # ---------------------------------------------------------------------
        domain = cls.SLOT_DOMAINS.get(slot_name, "general")
        authorized_keys = tuple(sorted(relevant_premises.keys()))
        snapshots = {k: fact.value for k, fact in relevant_premises.items()}
        constraints = cls.SLOT_CONSTRAINTS.get(slot_name, ())

        return InferenceProposalRequest(
            target_slot=slot_name,
            domain=domain,
            authorized_premise_keys=authorized_keys,
            premise_snapshots=snapshots,
            known_constraints=constraints,
            inference_cycle_id=cycle_id,
        )

    # -------------------------------------------------------------------------
    # Premise Extraction & Sufficiency Logic
    # -------------------------------------------------------------------------

    @classmethod
    def _is_excluded_fact(cls, key: str) -> bool:
        """Check whether a fact key belongs to the excluded/trivial lifestyle list."""
        for prefix in cls.EXCLUDED_FACT_PREFIXES:
            if key == prefix or key.startswith(f"{prefix}."):
                return True
        return False

    @classmethod
    def _extract_relevant_premises(
        cls,
        slot_name: str,
        core: CharacterCore,
    ) -> dict[str, CoreFactItem]:
        """Extract canonical facts from core that are functionally relevant to target slot."""
        dimension_map = cls.SLOT_RELEVANCE_DIMENSIONS.get(slot_name, {})
        relevant_facts: dict[str, CoreFactItem] = {}

        # Collect all allowed fact keys/prefixes for this slot
        allowed_keys: set[str] = set()
        for keys_tuple in dimension_map.values():
            allowed_keys.update(keys_tuple)

        for key, fact in core.facts.items():
            if fact.status != FactStatus.CANONICAL:
                continue

            # Strict exclusion of trivial lifestyle preferences
            if cls._is_excluded_fact(key):
                continue

            # Match exact key or domain match
            if key in allowed_keys:
                relevant_facts[key] = fact
            elif any(key.startswith(f"{allowed}.") for allowed in allowed_keys):
                relevant_facts[key] = fact

        return relevant_facts

    @classmethod
    def _is_premise_set_sufficient(
        cls,
        slot_name: str,
        relevant_premises: dict[str, CoreFactItem],
        core: CharacterCore,
    ) -> bool:
        """Evaluate domain-specific premise sufficiency without mechanical count rules."""
        if not relevant_premises:
            return False

        dimension_map = cls.SLOT_RELEVANCE_DIMENSIONS.get(slot_name, {})

        # Count how many distinct functional dimensions are satisfied
        satisfied_dimensions: set[str] = set()
        for dim_name, dim_keys in dimension_map.items():
            for key in relevant_premises:
                if key in dim_keys or any(key.startswith(f"{dk}.") for dk in dim_keys):
                    satisfied_dimensions.add(dim_name)
                    break

        # 1. education.pathway (Simple Supported Slot)
        if slot_name == "education.pathway":
            # A single pivotal fact establishing post-secondary transition eligibility is sufficient!
            # e.g. SPM completion, high school graduation, or academic readiness
            if "academic_readiness" in satisfied_dimensions:
                return True
            return False

        # 2. education.major (Complex Multi-Attribute Life Decision)
        if slot_name == "education.major":
            # Complex life decisions require converging relevant dimensions (>= 2 distinct functional dimensions)
            # e.g., (Aptitude + Interest) or (Aptitude + Values) or (Talents + Resource)
            if len(satisfied_dimensions) >= 2:
                return True
            return False

        # 3. education.institution
        if slot_name == "education.institution":
            return "academic_foundation" in satisfied_dimensions

        # 4. education.year
        if slot_name == "education.year":
            return "temporal_readiness" in satisfied_dimensions or "academic_foundation" in satisfied_dimensions

        # 5. career.aspiration (Vocational Aspiration)
        if slot_name == "career.aspiration":
            # Pivotal: established major is sufficient
            if "education_foundation" in satisfied_dimensions:
                return True
            # Otherwise requires converging skills/interests/values (>= 2 dimensions)
            if len(satisfied_dimensions) >= 2:
                return True
            return False

        # 6. family & lifestyle & background slots
        if slot_name in (
            "family.parents_occupation",
            "family.childhood_background",
            "lifestyle.transit",
            "lifestyle.beverage",
            "education.secondary_school",
            "education.music_qualification",
        ):
            return len(satisfied_dimensions) >= 1

        # Default fallback: requires at least 2 dimensions for unconfigured slots
        return len(satisfied_dimensions) >= 2
