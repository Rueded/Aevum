"""Reality Orchestration Service for Phase 7D.5 — Per-Turn Governed Reality Pipeline.

Owns the complete per-turn pipeline that bridges 7D.1–7D.4 frozen components
with CharacterEngine. Replaces the Phase 7B.3 RealityBeliefEngine dependency
in CharacterEngine.

Pipeline (A → J, executed in strict order):
  A. EvidenceClassifier  — biographical signal detection (user_input + core)
  B. ContradictionResolver — contradiction signal detection (user_input + core)
     [B runs independently of A, never depends on Candidate or Choice output]
  C. Candidate creation — creates CandidateHypothesis if A has signal
  D. Load active candidates — from DB across all slots
  E. Per-slot competition — CandidateCompetitionService (pure, no mutation)
  F. Per-slot choice — ChoiceSelectionService (SELECTED_BUT_NOT_PROMOTED)
  G. Reality repair — RealityRepairService consumes B's signal
  H. Biography promotion — BiographyPromotionService, synchronous, pre-response
  I. World facts selection — WorldFactsSelector (lexical, pure)
  J. Context assembly — RealityContextBuilder (frozen 7D.4 pure-read)

Hard Invariants:
  - NEVER calls RealityBeliefEngine under any condition.
  - NEVER calls set_fact() directly.
  - NEVER creates PromotionAuthorizationToken directly.
  - Empty states (no candidate, no contradiction, no repair, etc.) are valid
    normal states — never abort, never raise.
  - Infrastructure failures are propagated (not swallowed) per failure contract.
  - run_turn() always returns OrchestrationTurnResult with governed_reality non-None.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Sequence, TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.reality.candidate_models import (
    CandidateHypothesis,
    CandidateLifecycleState,
    EvidenceFamily,
    InferenceEdgeType,
    InferenceScope,
    PlausibilityBreakdown,
    ProvenanceLineage,
    RealityTaxonomy,
)
from app.reality.candidate_repository import CandidateRepository
from app.reality.choice_models import ChoiceDecisionResult
from app.reality.competition_service import CandidateCompetitionService
from app.reality.choice_service import ChoiceSelectionService
from app.reality.contradiction_resolver import ContradictionResolver
from app.reality.contradiction_models import ContradictionResolution, ContradictionType
from app.reality.evidence_classifier import EvidenceClassificationResult, EvidenceClassifier
from app.reality.repair_models import RealityRepairResult
from app.reality.repair_service import RealityRepairService
from app.reality.world_facts_selector import WorldFactsSelector

if TYPE_CHECKING:
    from app.character.bible_models import CharacterBible
    from app.character.core_models import CharacterCore
    from app.character.reality_context_models import GovernedRealityContext

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Infrastructure failure sentinel
# ---------------------------------------------------------------------------


class CandidateRepositoryUnavailableError(RuntimeError):
    """Raised when CandidateRepository.get_all_active_candidates() fails.

    Per failure contract: this is an infrastructure failure, NOT an empty state.
    DB exception means the system cannot determine whether candidates exist.
    This must NEVER be silently converted to an empty list [].
    """


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OrchestrationTurnResult:
    """Immutable result of a complete per-turn governed reality orchestration run.

    governed_reality is always non-None.
    All other fields default to safe empty values when their stage produced no output.
    """

    governed_reality: "GovernedRealityContext"
    candidates: list[CandidateHypothesis] = field(default_factory=list)
    choices: list[ChoiceDecisionResult] = field(default_factory=list)
    repair_result: Optional[RealityRepairResult] = None
    contradiction: ContradictionResolution = field(
        default_factory=lambda: ContradictionResolution()
    )
    promoted: bool = False


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class RealityOrchestrationService:
    """Per-turn governed reality pipeline orchestrator.

    Coordinates the 7D.1–7D.4 frozen components into a single coherent
    per-turn execution. Does NOT implement any of the frozen component logic.

    This service is the ONLY authorized caller of BiographyPromotionService
    during a conversation turn. CharacterEngine calls this service; it does
    not call promotion services or CandidateRepository directly.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._candidate_repo = CandidateRepository(session)
        self._competition_service = CandidateCompetitionService()
        self._choice_service = ChoiceSelectionService()

    async def run_turn(
        self,
        user_input: str,
        core: "CharacterCore",
        memories: Optional[Sequence[Any]] = None,
        character_id: str = "aevum",
        current_location: Optional[str] = None,
        prior_turn_slip: Optional[str] = None,
        bible: Optional["CharacterBible"] = None,
    ) -> OrchestrationTurnResult:
        """Execute the complete A→J per-turn governed reality pipeline.

        Args:
            user_input: Raw user message for this turn.
            core: Canonical CharacterCore snapshot (pre-orchestration).
            memories: Retrieved memory context for this turn.
            character_id: Character identifier.
            current_location: Current physical location for contradiction detection.
            prior_turn_slip: Description of prior turn slip for contradiction detection.
            bible: CharacterBible for choice evaluation context.

        Returns:
            OrchestrationTurnResult with governed_reality always non-None.

        Raises:
            CandidateRepositoryUnavailableError: If get_all_active_candidates() fails.
                Per failure contract, this is NOT an empty state.
            Any other exception from run_turn() is NOT caught here — it propagates
            to CharacterEngine's fail-closed handler.
        """
        # ------------------------------------------------------------------
        # Step A — Evidence Classification
        # Pure function. Never raises. Returns no-signal if no pattern matches.
        # ------------------------------------------------------------------
        classification: EvidenceClassificationResult = EvidenceClassifier.classify(
            user_input, core=core
        )

        # ------------------------------------------------------------------
        # Step B — Contradiction Detection
        # Runs INDEPENDENTLY of Step A. Input: user_input + core only.
        # Never depends on Candidate or Choice output.
        # Pure function. Never raises.
        # ------------------------------------------------------------------
        contradiction: ContradictionResolution = ContradictionResolver.resolve(
            user_input,
            core=core,
            current_location=current_location,
            prior_slip=prior_turn_slip,
        )

        # ------------------------------------------------------------------
        # Step C — Candidate Creation (conditional on Step A)
        # Only creates a candidate when Step A detected a biographical signal.
        # Infrastructure failures here are absorbed — they do not abort the turn.
        # ------------------------------------------------------------------
        new_candidate: Optional[CandidateHypothesis] = None
        new_evidence_family: Optional[EvidenceFamily] = None

        if classification.has_biographical_signal and classification.slot_name:
            try:
                new_candidate, new_evidence_family = await self._create_candidate(
                    classification=classification,
                    user_input=user_input,
                    character_id=character_id,
                )
            except Exception as exc:
                logger.error(
                    "Candidate creation failed for slot '%s' (character '%s'): %s. "
                    "Continuing without new candidate.",
                    classification.slot_name, character_id, exc,
                )
                new_candidate = None
                new_evidence_family = None

        # ------------------------------------------------------------------
        # Step D — Load Active Candidates from DB
        # FAILURE CONTRACT: If this raises, propagate as
        # CandidateRepositoryUnavailableError. NEVER convert to [].
        # A DB exception means candidate state is UNKNOWN, not empty.
        # ------------------------------------------------------------------
        try:
            all_candidates = await self._candidate_repo.get_all_active_candidates(
                character_id=character_id,
            )
        except Exception as exc:
            raise CandidateRepositoryUnavailableError(
                f"get_all_active_candidates failed for character '{character_id}': {exc}"
            ) from exc

        # ------------------------------------------------------------------
        # Step E — Per-slot Competition
        # No-op when candidate list is empty. Pure computation, no DB writes.
        # ------------------------------------------------------------------
        competition_results = []
        if all_candidates:
            competition_results = self._run_competition(all_candidates, core, character_id)

        # ------------------------------------------------------------------
        # Step F — Per-slot Choice
        # No-op when competition_results is empty.
        # Persistence failures are absorbed (choice is still used in-memory).
        # ------------------------------------------------------------------
        choices: list[ChoiceDecisionResult] = []
        if competition_results:
            choices = await self._run_choices(
                competition_results=competition_results,
                core=core,
                bible=bible,
            )

        # ------------------------------------------------------------------
        # Step G — Reality Repair
        # No-op when contradiction_type is NONE.
        # Consumes contradiction signal from Step B only.
        # ------------------------------------------------------------------
        repair_result: Optional[RealityRepairResult] = None
        if contradiction.contradiction_type != ContradictionType.NONE:
            try:
                repair_result = self._run_repair(contradiction)
            except Exception as exc:
                logger.error(
                    "RealityRepairService failed for character '%s': %s. "
                    "Continuing without repair result.",
                    character_id, exc,
                )
                repair_result = None

        # ------------------------------------------------------------------
        # Step H — Biography Promotion (synchronous, pre-response)
        # No-op when no choices or no promotable candidate.
        # Promotion failure is absorbed (promoted=False, original core retained).
        # INVARIANT: Only BiographyPromotionService may perform canonical mutation.
        # ------------------------------------------------------------------
        promoted = False
        refreshed_core = core

        if choices:
            try:
                promoted, refreshed_core = await self._run_promotion(
                    choices=choices,
                    all_candidates=all_candidates,
                    core=core,
                    character_id=character_id,
                )
            except Exception as exc:
                logger.error(
                    "Biography promotion failed for character '%s': %s. "
                    "Continuing with pre-promotion core snapshot.",
                    character_id, exc,
                )
                promoted = False
                refreshed_core = core

        # ------------------------------------------------------------------
        # Step I — World Facts Selection
        # No-op (returns {}) when no lexical match found.
        # Never raises — any exception is absorbed.
        # ------------------------------------------------------------------
        world_facts: dict[str, Any] = {}
        try:
            world_facts = WorldFactsSelector.select_for_turn(user_input)
        except Exception as exc:
            logger.error(
                "WorldFactsSelector failed for character '%s': %s. "
                "Continuing with empty world facts.",
                character_id, exc,
            )
            world_facts = {}

        # ------------------------------------------------------------------
        # Step J — Context Assembly
        # Uses post-promotion refreshed_core (may equal original core if no promotion).
        # RealityContextBuilder is frozen 7D.4 — receives only data, makes no decisions.
        # ------------------------------------------------------------------
        evidence_references: list[EvidenceFamily] = (
            [new_evidence_family] if new_evidence_family else []
        )
        unverified_user_claims: list[str] = (
            [user_input] if classification.has_biographical_signal else []
        )

        # Lazy import to avoid circular dependency and keep frozen 7D.4 boundary visible
        from app.character.reality_context_builder import RealityContextBuilder

        governed_reality: "GovernedRealityContext" = RealityContextBuilder.build_context(
            character_id=character_id,
            core=refreshed_core,
            candidates=all_candidates if all_candidates else None,
            choices=choices if choices else None,
            repair_result=repair_result,
            world_facts=world_facts if world_facts else None,
            unverified_user_claims=unverified_user_claims if unverified_user_claims else None,
            evidence_references=evidence_references if evidence_references else None,
            memories=memories,
        )

        return OrchestrationTurnResult(
            governed_reality=governed_reality,
            candidates=all_candidates,
            choices=choices,
            repair_result=repair_result,
            contradiction=contradiction,
            promoted=promoted,
        )

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    async def _create_candidate(
        self,
        classification: EvidenceClassificationResult,
        user_input: str,
        character_id: str,
    ) -> tuple[CandidateHypothesis, EvidenceFamily]:
        """Create and persist a CandidateHypothesis from a biographical signal.

        Returns (candidate, evidence_family). Propagates any exception to caller.
        """
        slot_name = classification.slot_name  # type: ignore[assignment]
        cluster_key = f"{character_id}.{slot_name}.user_assertion"

        # Record evidence family (idempotent — same cluster_key increments mention_count)
        evidence_family = await self._candidate_repo.record_evidence(
            source_type="USER_ASSERTION",
            cluster_key=cluster_key,
        )

        candidate_id = f"cand_{uuid.uuid4().hex[:12]}"
        provenance = ProvenanceLineage(
            origin_id=f"turn_{uuid.uuid4().hex[:8]}",
            evidence_family_ids=(evidence_family.family_id,),
            inference_depth=(
                0 if classification.inference_scope == InferenceScope.DIRECT else 1
            ),
        )
        plausibility = PlausibilityBreakdown.create(
            evidence_grounding_score=0.55,
            coherence_score=0.60,
        )

        candidate = CandidateHypothesis(
            candidate_id=candidate_id,
            entity_id=character_id,
            slot_name=slot_name,
            proposed_value=classification.claimed_value or user_input[:120],
            reality_taxonomy=classification.reality_taxonomy,
            inference_depth=provenance.inference_depth,
            inference_edge_type=classification.inference_edge_type,
            plausibility=plausibility,
            provenance=provenance,
            evidence_families=(evidence_family,),
            lifecycle_state=CandidateLifecycleState.GENERATED,
        )

        saved = await self._candidate_repo.save_candidate(candidate)
        return saved, evidence_family

    def _run_competition(
        self,
        candidates: list[CandidateHypothesis],
        core: "CharacterCore",
        character_id: str,
    ) -> list:
        """Run per-slot competition. Returns list of CompetitionResult objects."""
        from app.reality.candidate_models import CandidateHypothesisSet

        # Group candidates by slot_name
        slots: dict[str, list[CandidateHypothesis]] = {}
        for c in candidates:
            slots.setdefault(c.slot_name, []).append(c)

        results = []
        for slot_name, slot_candidates in slots.items():
            try:
                result = self._competition_service.evaluate_competition(
                    candidate_set_or_candidates=slot_candidates,
                    core=core,
                    slot_name=slot_name,
                    entity_id=character_id,
                )
                results.append(result)
            except Exception as exc:
                logger.error(
                    "Competition failed for slot '%s' (character '%s'): %s. "
                    "Skipping slot.",
                    slot_name, character_id, exc,
                )
        return results

    async def _run_choices(
        self,
        competition_results: list,
        core: "CharacterCore",
        bible: Optional["CharacterBible"],
    ) -> list[ChoiceDecisionResult]:
        """Run choice selection for each competition result. Returns list of ChoiceDecisionResult."""
        choices: list[ChoiceDecisionResult] = []
        for comp_result in competition_results:
            try:
                choice = self._choice_service.select_choice(
                    competition_result=comp_result,
                    core=core,
                    bible=bible,
                )
                # Persist choice decision (non-fatal if persistence fails)
                try:
                    await self._candidate_repo.save_choice_decision(choice)
                except Exception as exc:
                    logger.error(
                        "save_choice_decision failed for slot '%s': %s. "
                        "Using in-memory choice only.",
                        comp_result.slot_name, exc,
                    )
                choices.append(choice)
            except Exception as exc:
                logger.error(
                    "Choice selection failed for slot '%s': %s. Skipping.",
                    comp_result.slot_name, exc,
                )
        return choices

    @staticmethod
    def _map_contradiction_to_repair(
        contradiction: ContradictionResolution,
    ) -> dict[str, Any]:
        """Map ContradictionResolution fields to RealityRepairService.repair() kwargs.

        ContradictionResolver is a signal producer. RealityRepairService is the
        repair authority. This mapping bridges the two without coupling them.
        """
        from app.reality.repair_models import RepairLevel
        from app.reality.contradiction_models import ContradictionType, RepairStrategy

        conflict_type: Optional[str] = None
        is_social_misspeak = False
        social_explanation: Optional[str] = None

        ct = contradiction.contradiction_type
        rs = contradiction.repair_strategy

        if ct == ContradictionType.GENUINE_MISSPEAK or rs.value in (
            "MISSPEAK_ADMISSION", "SELF_CORRECTION"
        ):
            is_social_misspeak = True
            social_explanation = contradiction.repair_guidance

        elif ct in (
            ContradictionType.USER_FACTUAL_ERROR,
            ContradictionType.WORLD_KNOWLEDGE_CONFLICT,
        ):
            conflict_type = "FACTUAL_DISAGREEMENT"

        elif ct == ContradictionType.ANOMALOUS_HIGH_IMPACT:
            conflict_type = "GRACEFUL_UNCERTAINTY"

        elif ct == ContradictionType.SURFACE_TENSION:
            conflict_type = "SOCIAL_MISSPEAK"
            social_explanation = contradiction.contextual_bridge or contradiction.repair_guidance

        return {
            "conflict_type": conflict_type,
            "is_social_misspeak": is_social_misspeak,
            "social_explanation": social_explanation,
            "rationale": contradiction.rationale or f"Contradiction type: {ct.value}",
        }

    def _run_repair(
        self,
        contradiction: ContradictionResolution,
    ) -> Optional[RealityRepairResult]:
        """Run RealityRepairService using contradiction signal from Step B.

        Returns RealityRepairResult or None if repair service raises.
        """
        kwargs = self._map_contradiction_to_repair(contradiction)
        return RealityRepairService.repair(**kwargs)

    async def _run_promotion(
        self,
        choices: list[ChoiceDecisionResult],
        all_candidates: list[CandidateHypothesis],
        core: "CharacterCore",
        character_id: str,
    ) -> tuple[bool, "CharacterCore"]:
        """Attempt biography promotion for any promotable choice decision.

        Returns (promoted: bool, refreshed_core: CharacterCore).
        If promotion fails, returns (False, original_core).

        INVARIANT: BiographyPromotionService is the sole mutation authority.
        This method delegates entirely — it never calls set_fact() directly.
        """
        from app.reality.biography_promotion_service import BiographyPromotionService
        from app.character.core_service import CharacterCoreService

        promo_service = BiographyPromotionService(
            session=self._session,
            candidate_repo=self._candidate_repo,
        )
        core_service = CharacterCoreService(self._session)

        # Build lookup of candidate by ID for choice resolution
        candidate_by_id = {c.candidate_id: c for c in all_candidates}

        promoted = False
        for choice in choices:
            if not choice.selected_candidate_id:
                continue
            candidate = (
                choice.selected_candidate
                or candidate_by_id.get(choice.selected_candidate_id)
            )
            if candidate is None:
                continue

            try:
                promo_record = await promo_service.promote_candidate(
                    candidate=candidate,
                    choice_decision=choice,
                    character_id=character_id,
                )
                if promo_record:
                    promoted = True
                    # One successful promotion per turn is enough; refresh core and stop.
                    break
            except Exception as exc:
                logger.error(
                    "promote_candidate failed for candidate '%s' slot '%s': %s. "
                    "Skipping promotion.",
                    candidate.candidate_id, candidate.slot_name, exc,
                )

        if promoted:
            try:
                refreshed_core = await core_service.get_core(character_id)
                return True, refreshed_core
            except Exception as exc:
                logger.error(
                    "get_core() failed after promotion for character '%s': %s. "
                    "Using pre-promotion core snapshot.",
                    character_id, exc,
                )
                return True, core

        return False, core
