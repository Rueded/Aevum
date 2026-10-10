"""Candidate Evaluation Adapter for Phase 8A.4 (Autonomous Reality & Life Inference).

Strict Invariants:
- A. Unknown != Impossible: Absence of knowledge is not falsification. External entities absent
     from registry are quarantined as speculative with HardValidity = 1.0. Only explicit confirmed
     contradictions set HardValidity = 0.0.
- B. Heuristic != Probability: Plausibility scores express structural coherence, never real-world
     probabilities or psychological statistics. Baseline fit is neutral 0.50.
- C. Construction != Persistence: CandidateEvaluationAdapter constructs in-memory CandidateHypotheses
     only. Zero database insertions, commits, flushes, or mutations.
- D. Derived != Primary: Every candidate must trace to >= 1 primary canonical anchor. Pure derived
     (AEVUM_INFERRED -> AEVUM_INFERRED) chains without primary anchors receive zero support.
- E. Evaluation != Competition: Evaluator scores individual candidate coherence independently;
     does NOT rank, compute decision margins, or exclude runner-up alternatives.
- F. Evaluation != Promotion: Evaluator outputs non-canonical CandidateHypothesis objects. Zero tokens,
     zero set_fact(), zero canonical reality mutation.
- Non-Epistemic Rationale: Proposer rationale and suggested premise roles are strictly ignored.
- Stereotype-Free Feasibility: Parental occupation/title/ethnicity must NEVER imply financial wealth.
- Anti-Circularity: Downstream inferred facts (e.g. career) cannot provide support to upstream slots (e.g. major).
"""

from datetime import datetime, timezone
import hashlib
import logging
from typing import Any, Optional, Sequence

from app.character.core_models import CharacterCore
from app.reality.candidate_models import (
    CandidateHypothesis,
    CandidateLifecycleState,
    EvidenceFamily,
    InferenceEdgeType,
    PlausibilityBreakdown,
    ProvenanceLineage,
    RealityTaxonomy,
)
from app.reality.inference_models import (
    CandidateEnvelope,
    InferenceProposalRequest,
    PremiseOriginCategory,
    categorize_fact_origin,
)
from app.reality.models import CoreFactItem, FactSource, FactStatus
from app.reality.validators import (
    CausalityValidator,
    ConsistencyValidator,
    TimelineValidator,
    WorldKnowledgeValidator,
)
from app.reality.world_knowledge import KnowledgeKind, WorldKnowledgeRegistry

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# Forbidden keys for financial/wealth stereotyping
PROHIBITED_STEREOTYPE_KEYS = {
    "parents.father_occupation",
    "parents.mother_occupation",
    "family.prestige",
    "identity.ethnicity",
    "family.lineage",
}

# Permitted explicit resource keys
ALLOWED_RESOURCE_KEYS = {
    "family.socioeconomic_tier",
    "finances.budget_tier",
    "scholarship.status",
    "finances.savings_tier",
}

# Acyclic prerequisite dependencies across life domains (anti-circularity)
# Keys cannot be supported by any downstream slot in their set
DOWNSTREAM_SLOT_DEPENDENCIES: dict[str, set[str]] = {
    "education.pathway": {"education.major", "career.aspiration"},
    "education.major": {"career.aspiration"},
}


class CandidateEvaluationAdapter:
    """Validates, evaluates, and constructs in-memory Phase 7 CandidateHypotheses from CandidateEnvelopes."""

    def __init__(self, world_registry: Optional[type[WorldKnowledgeRegistry]] = None) -> None:
        self._world_registry = world_registry or WorldKnowledgeRegistry

    def evaluate_envelope(
        self,
        envelope: CandidateEnvelope,
        request: InferenceProposalRequest,
        core: Optional[CharacterCore] = None,
    ) -> CandidateHypothesis:
        """Deterministically evaluate a single CandidateEnvelope and construct an in-memory CandidateHypothesis."""
        slot = envelope.slot
        raw_val = envelope.raw_value
        snapshots = request.premise_snapshots

        # ---------------------------------------------------------------------
        # 1. Dimension 1: HardValidity in {0.0, 1.0} (Binary Admissibility)
        #    Rule: Unknown != Impossible. Only explicit contradiction sets 0.0.
        # ---------------------------------------------------------------------
        hard_validity = self._calculate_hard_validity(slot, raw_val, snapshots, core)

        # ---------------------------------------------------------------------
        # 2. Dimension 2: Feasibility in [0.0, 1.0] (Prerequisites & Resources)
        #    Rule: Stereotype-Free (no occupation -> wealth inference).
        # ---------------------------------------------------------------------
        feasibility = self._calculate_feasibility(slot, raw_val, snapshots, core)

        # ---------------------------------------------------------------------
        # 3. Dimension 3: ContextSupport in [0.0, 1.0] (Deterministic Grounding)
        #    Rule: Recalculated independently; ignores proposer roles and rationale.
        #    Rule: Requires primary canonical anchor; blocks downstream circularity.
        # ---------------------------------------------------------------------
        context_support = self._calculate_context_support(
            slot,
            raw_val,
            envelope.suggested_premise_keys,
            request,
            core,
        )

        # ---------------------------------------------------------------------
        # 4. Dimension 4: Affinity in [0.0, 1.0] (Temperament & Values Fit)
        # ---------------------------------------------------------------------
        affinity = self._calculate_affinity(slot, raw_val, snapshots, core)

        # ---------------------------------------------------------------------
        # 5. Dimension: Structural Baseline Fit (Heuristic != Probability)
        #    Constant neutral baseline fit (0.50), NEVER a Bayesian prior.
        # ---------------------------------------------------------------------
        structural_baseline_fit = 0.50

        # ---------------------------------------------------------------------
        # Composite Plausibility Score
        # Formula: H * (0.15*baseline + 0.35*support + 0.25*feas + 0.25*aff)
        # ---------------------------------------------------------------------
        if hard_validity == 0.0:
            composite_plausibility = 0.0
        else:
            weighted_sum = (
                0.15 * structural_baseline_fit
                + 0.35 * context_support
                + 0.25 * feasibility
                + 0.25 * affinity
            )
            composite_plausibility = round(max(0.0, min(1.0, weighted_sum)), 4)

        # ---------------------------------------------------------------------
        # 6. Entity Quarantine Check (Unknown != Impossible)
        #    Unverified external entity -> is_quarantined = True, HardValidity = 1.0
        # ---------------------------------------------------------------------
        is_quarantined, quarantine_reason, edge_type = self._check_entity_quarantine(slot, raw_val)

        # ---------------------------------------------------------------------
        # 7. Model Construction: In-Memory Phase 7 CandidateHypothesis
        # ---------------------------------------------------------------------
        val_str = str(raw_val).lower().replace(" ", "_")
        hash_seed = f"{request.inference_cycle_id}:{slot}:{val_str}"
        cand_hash = hashlib.sha256(hash_seed.encode("utf-8")).hexdigest()[:12]
        cand_id = f"cand_{slot.replace('.', '_')}_{val_str[:16]}_{cand_hash}"

        plausibility = PlausibilityBreakdown.create(
            prior_weight=structural_baseline_fit,
            evidence_grounding_score=context_support,
            coherence_score=feasibility,
            utility_score=affinity,
            composite_plausibility_score=composite_plausibility,
        )

        provenance = ProvenanceLineage(
            origin_id=request.inference_cycle_id,
            parent_candidate_ids=(),
            evidence_family_ids=tuple(f"fam_{k}" for k in envelope.suggested_premise_keys),
            inference_depth=1,
            derivation_path=("autonomous_reality_inference", slot, str(raw_val)),
        )

        now = _utc_now()
        evidence_families = tuple(
            EvidenceFamily(
                family_id=f"fam_{k}",
                source_type="CANONICAL_FACT",
                cluster_key=f"cluster_{k}",
                mention_count=1,
                session_ids=(),
                first_observed_at=now,
                last_observed_at=now,
            )
            for k in envelope.suggested_premise_keys
        )

        candidate = CandidateHypothesis(
            candidate_id=cand_id,
            entity_id="aevum",
            slot_name=slot,
            proposed_value=raw_val,
            reality_taxonomy=RealityTaxonomy.SIMULATED_BIOGRAPHY_FACT,
            inference_depth=1,
            inference_edge_type=edge_type,
            plausibility=plausibility,
            provenance=provenance,
            evidence_families=evidence_families,
            lifecycle_state=CandidateLifecycleState.GENERATED,
            is_quarantined=is_quarantined,
            quarantine_reason=quarantine_reason,
            selection_metadata=None,
            created_at=now,
            updated_at=now,
        )

        return candidate

    def evaluate_envelopes(
        self,
        envelopes: Sequence[CandidateEnvelope],
        request: InferenceProposalRequest,
        core: Optional[CharacterCore] = None,
    ) -> Sequence[CandidateHypothesis]:
        """Batch evaluate a sequence of CandidateEnvelopes, preserving order and count."""
        return tuple(
            self.evaluate_envelope(env, request, core)
            for env in envelopes
        )

    # -------------------------------------------------------------------------
    # Dimension 1: HardValidity
    # -------------------------------------------------------------------------

    def _calculate_hard_validity(
        self,
        slot: str,
        value: Any,
        snapshots: dict[str, Any],
        core: Optional[CharacterCore],
    ) -> float:
        """Binary admissibility check: 0.0 if known impossible / lock conflict, 1.0 otherwise."""
        # 1. Check user locks on Core
        if core and core.is_locked(slot):
            locked_val = core.get_fact_value(slot)
            if locked_val is not None and locked_val != value:
                logger.debug("HardValidity=0: Core fact '%s' is locked with '%s' != '%s'", slot, locked_val, value)
                return 0.0

        # 2. Check timeline impossibility (e.g. undergraduate degree at age <= 16)
        age = None
        if "identity.age" in snapshots:
            try:
                age = int(snapshots["identity.age"])
            except (ValueError, TypeError):
                pass
        elif core and core.has_fact("identity.age"):
            try:
                age = int(core.get_fact_value("identity.age"))
            except (ValueError, TypeError):
                pass

        if age is not None and age <= 16:
            if slot in ("education.major", "education.pathway", "career.aspiration"):
                logger.debug("HardValidity=0: Age %d cannot possess undergraduate major/pathway without prodigy canon", age)
                return 0.0

        # 3. Check static physical causality
        if slot == "world.astronomy.sun_rises" and str(value).lower() != "east":
            return 0.0

        # Unknown != Impossible: If rules or criteria are unrecorded, default to 1.0
        return 1.0

    # -------------------------------------------------------------------------
    # Dimension 2: Feasibility (Stereotype-Free)
    # -------------------------------------------------------------------------

    def _calculate_feasibility(
        self,
        slot: str,
        value: Any,
        snapshots: dict[str, Any],
        core: Optional[CharacterCore],
    ) -> float:
        """Evaluate academic prerequisites and explicit resources; zero occupation stereotyping."""
        # 1. Academic Feasibility
        val_str = str(value).lower()
        math_grade = str(snapshots.get("academics.spm_math_grade", "")).upper()
        if not math_grade and core:
            math_grade = str(core.get_fact_value("academics.spm_math_grade", "")).upper()

        acad_score = 0.70
        if slot == "education.major":
            if val_str in ("computer_science", "software_engineering"):
                if math_grade in ("A", "A+", "A-"):
                    acad_score = 0.95
                elif math_grade in ("B", "B+"):
                    acad_score = 0.80
                elif math_grade in ("C", "C+"):
                    acad_score = 0.50
                elif math_grade in ("D", "E", "F"):
                    acad_score = 0.20
            else:
                # Non-STEM majors (music, design): math does not penalize
                acad_score = 0.85

        elif slot == "education.pathway":
            acad_score = 0.85

        elif slot == "career.aspiration":
            acad_score = 0.80

        # 2. Resource Feasibility (Stereotype-Free)
        # STPM and Matrikulasi are public subsidized pathways accessible regardless of wealth
        if slot == "education.pathway" and val_str in ("stpm", "matrikulasi"):
            resource_score = 0.90
        else:
            # Check explicit resource facts only
            socio_tier = snapshots.get("family.socioeconomic_tier")
            if not socio_tier and core:
                socio_tier = core.get_fact_value("family.socioeconomic_tier")

            scholarship = snapshots.get("scholarship.status")
            if scholarship is None and core:
                scholarship = core.get_fact_value("scholarship.status")

            budget_tier = snapshots.get("finances.budget_tier")
            if not budget_tier and core:
                budget_tier = core.get_fact_value("finances.budget_tier")

            # Expensive private foundation / degree
            is_expensive_option = val_str in ("foundation", "private_university")

            if scholarship is True or scholarship == "awarded":
                resource_score = 0.95
            elif socio_tier in ("HIGH", "T20") or budget_tier == "HIGH":
                resource_score = 0.90
            elif socio_tier in ("B40", "LOW") and is_expensive_option:
                resource_score = 0.25
            else:
                # No explicit resource facts: default to neutral baseline (cannot infer from occupation)
                resource_score = 0.50

        feasibility = round(0.5 * acad_score + 0.5 * resource_score, 4)
        return max(0.0, min(1.0, feasibility))

    # -------------------------------------------------------------------------
    # Dimension 3: ContextSupport (Independent Deterministic Grounding)
    # -------------------------------------------------------------------------

    def _calculate_context_support(
        self,
        slot: str,
        value: Any,
        cited_premise_keys: Sequence[str],
        request: InferenceProposalRequest,
        core: Optional[CharacterCore],
    ) -> float:
        """Deterministically compute evidence support; ignores proposer roles/rationale.

        Enforces:
        - Primary canonical anchor required (>= 1 primary source). Pure AEVUM_INFERRED chains = 0.0.
        - Downstream inferred facts cannot provide support to upstream slots (anti-circularity).
        - Non-canonical or nonexistent premise keys contribute zero.
        """
        snapshots = request.premise_snapshots
        downstream_slots = DOWNSTREAM_SLOT_DEPENDENCIES.get(slot, set())

        # 1. Primary Anchor & Source Hierarchy Check
        has_primary_anchor = False
        valid_premises: dict[str, Any] = {}

        for key in cited_premise_keys:
            # Canonical existence check
            val = snapshots.get(key)
            source = None

            if core and core.has_fact(key):
                fact_item = core.get_fact(key)
                if fact_item and fact_item.status == FactStatus.CANONICAL:
                    val = fact_item.value
                    source = fact_item.source
            elif key in snapshots:
                # In request premise snapshots: determine origin category
                source = FactSource.USER_CONFIGURED  # Primary default for request snapshots

            if val is None:
                # Non-existent or non-canonical key contributes zero weight
                continue

            # Anti-circularity: Check if key is a downstream slot
            if any(key == ds or key.startswith(f"{ds}.") for ds in downstream_slots):
                if source == FactSource.AEVUM_INFERRED:
                    logger.debug("Anti-circularity: Pruning downstream inferred premise '%s' for upstream slot '%s'", key, slot)
                    continue

            valid_premises[key] = val

            # Check if this fact constitutes a primary anchor
            if source in (FactSource.USER_CONFIGURED, FactSource.CONVERSATION, FactSource.SYSTEM_BASELINE):
                has_primary_anchor = True

        # Pure derived chain without primary canonical anchor receives zero support
        if not has_primary_anchor or not valid_premises:
            logger.debug("ContextSupport=0: Zero primary canonical anchors or zero valid premises for slot '%s'", slot)
            return 0.0

        # 2. Deterministic Domain Coherence Matrix
        val_str = str(value).lower()
        support_score = 0.50  # Baseline neutral

        if slot == "education.major":
            if val_str == "music_performance":
                if valid_premises.get("traits.musical_talent") is True:
                    support_score += 0.35
                if valid_premises.get("skills.instrument_playing"):
                    support_score += 0.30
                interests = valid_premises.get("interests", [])
                interests_list = interests if isinstance(interests, (list, tuple)) else [interests]
                if any(any(m in str(i).lower() for m in ("music", "piano", "guitar", "instrument")) for i in interests_list):
                    support_score += 0.25

            elif val_str == "computer_science":
                if valid_premises.get("skills.programming"):
                    support_score += 0.35
                math = str(valid_premises.get("academics.spm_math_grade", "")).upper()
                if math in ("A", "A+", "A-"):
                    support_score += 0.30
                elif math in ("D", "E", "F"):
                    support_score -= 0.35
                if valid_premises.get("values.career_stability") or valid_premises.get("values.parental_expectation"):
                    support_score += 0.15

            elif val_str == "sound_engineering":
                if valid_premises.get("traits.musical_talent") is True or valid_premises.get("skills.instrument_playing"):
                    support_score += 0.25
                if valid_premises.get("skills.programming"):
                    support_score += 0.25
                interests = valid_premises.get("interests", [])
                interests_list = interests if isinstance(interests, (list, tuple)) else [interests]
                if any(any(m in str(i).lower() for m in ("music", "piano", "guitar", "instrument")) for i in interests_list):
                    support_score += 0.10

            elif val_str == "digital_media":
                if valid_premises.get("values.creativity"):
                    support_score += 0.30
                if valid_premises.get("traits.musical_talent") is True:
                    support_score += 0.20

        elif slot in ("education.institution", "education.university"):
            if "usm" in val_str or "sains" in val_str:
                support_score += 0.25
                dislikes = valid_premises.get("dislikes", [])
                dislikes_list = dislikes if isinstance(dislikes, (list, tuple)) else [dislikes]
                if any("crowd" in str(d).lower() or "noisy" in str(d).lower() for d in dislikes_list):
                    support_score += 0.10
            elif "um" in val_str or "malaya" in val_str:
                support_score += 0.15
            elif "monash" in val_str:
                support_score += 0.10

        elif slot == "education.year":
            age = valid_premises.get("identity.age")
            if str(age) == "21":
                if val_str in ("year_2", "year 2", "2"):
                    support_score += 0.30
                elif val_str in ("year_3", "year 3", "3"):
                    support_score += 0.15
                elif val_str in ("year_1", "year 1", "1"):
                    support_score += 0.05

        elif slot == "education.pathway":
            if val_str == "stpm":
                if str(valid_premises.get("traits.challenge_preference", "")).upper() == "HIGH":
                    support_score += 0.35
                if valid_premises.get("academics.spm_overall"):
                    support_score += 0.25
            elif val_str == "matrikulasi":
                if "short" in str(valid_premises.get("preferences.study_duration", "")).lower():
                    support_score += 0.35
            elif val_str == "foundation":
                if valid_premises.get("family.socioeconomic_tier"):
                    support_score += 0.25

        elif slot == "career.aspiration":
            if val_str == "software_engineer":
                if "computer" in str(valid_premises.get("education.major", "")).lower():
                    support_score += 0.40
                if valid_premises.get("skills.programming"):
                    support_score += 0.30
            elif val_str == "musician":
                if "music" in str(valid_premises.get("education.major", "")).lower():
                    support_score += 0.40
                if valid_premises.get("skills.instrument_playing"):
                    support_score += 0.30

        return round(max(0.0, min(1.0, support_score)), 4)

    # -------------------------------------------------------------------------
    # Dimension 4: Affinity
    # -------------------------------------------------------------------------

    def _calculate_affinity(
        self,
        slot: str,
        value: Any,
        snapshots: dict[str, Any],
        core: Optional[CharacterCore],
    ) -> float:
        """Evaluate alignment with intrinsic character temperament, values, and traits."""
        val_str = str(value).lower()
        affinity = 0.50  # Neutral baseline fit

        # Creativity and artistic values fit
        has_creativity = (
            str(snapshots.get("values.creativity", "")).upper() == "HIGH"
            or (core and str(core.get_fact_value("values.creativity", "")).upper() == "HIGH")
        )
        interests = snapshots.get("interests", []) or []
        interests_list = interests if isinstance(interests, (list, tuple)) else [interests]
        has_artistic = any(any(k in str(i).lower() for k in ("piano", "guitar", "anime", "fiction", "film")) for i in interests_list)
        if (has_creativity or has_artistic) and val_str in ("music_performance", "digital_media", "game_developer", "musician"):
            affinity += 0.20

        # Institution environment fit
        if slot in ("education.institution", "education.university"):
            if "usm" in val_str or "sains" in val_str:
                affinity += 0.15

        # Academic year trajectory fit
        if slot == "education.year":
            if val_str in ("year_2", "year 2", "2"):
                affinity += 0.10

        # Career stability values fit
        has_stability = (
            snapshots.get("values.career_stability") is not None
            or snapshots.get("values.parental_expectation") is not None
            or (core and core.has_fact("values.career_stability"))
        )
        if has_stability and val_str in ("computer_science", "software_engineer", "stpm"):
            affinity += 0.25

        # Challenge preference fit
        has_challenge = (
            str(snapshots.get("traits.challenge_preference", "")).upper() == "HIGH"
            or (core and str(core.get_fact_value("traits.challenge_preference", "")).upper() == "HIGH")
        )
        if has_challenge and val_str in ("stpm", "computer_science"):
            affinity += 0.20

        return round(max(0.0, min(1.0, affinity)), 4)

    # -------------------------------------------------------------------------
    # Entity Quarantine Check (Unknown != Impossible)
    # -------------------------------------------------------------------------

    def _check_entity_quarantine(
        self,
        slot: str,
        value: Any,
    ) -> tuple[bool, Optional[str], InferenceEdgeType]:
        """Check if candidate references an external real-world entity and enforce quarantine boundaries.

        Returns (is_quarantined, quarantine_reason, inference_edge_type).
        """
        val_str = str(value).lower()

        # Institutional or university reference detection
        is_entity_slot = slot in ("education.university", "education.institution") or any(
            w in val_str for w in ("university", "college", "school", "conservatory", "academy", "juilliard")
        )

        if not is_entity_slot:
            return False, None, InferenceEdgeType.DIRECT_ATTRIBUTE

        # Check in WorldKnowledgeRegistry
        # Format can be e.g. "world.usm.main_campus" or direct name lookup
        found_in_registry = False
        for key in ("world.usm.main_campus", "world.um.main_campus"):
            item = self._world_registry.get(key)
            if item and (item.value.lower() in val_str or key.split(".")[1] in val_str):
                found_in_registry = True
                break

        if found_in_registry:
            return False, None, InferenceEdgeType.STRUCTURAL_DEPENDENCY

        # Entity absent from registry: Mandatory Quarantine for Phase 9 verification
        # Invariant: Unknown != Impossible (is_quarantined=True, but HardValidity remains 1.0)
        return (
            True,
            "UNVERIFIED_EXTERNAL_WORLD_ENTITY",
            InferenceEdgeType.SPECULATIVE_ASSOCIATION,
        )
