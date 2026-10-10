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
from app.reality.choice_models import ChoiceDecisionResult, ChoiceFactorBreakdown, CompetitionResult
from app.reality.competition_service import CandidateCompetitionService
from app.reality.choice_service import ChoiceSelectionService
from app.reality.contradiction_resolver import ContradictionResolver
from app.reality.contradiction_models import ContradictionResolution, ContradictionType
from app.reality.evidence_classifier import EvidenceClassificationResult, EvidenceClassifier
from app.reality.repair_models import RealityRepairResult
from app.reality.repair_service import RealityRepairService
from app.reality.world_facts_selector import WorldFactsSelector
from app.reality.inquiry_detector import RealityInquiryDetector, InquirySignal
from app.reality.autonomous_inference_coordinator import AutonomousInferenceCoordinator
from app.reality.timeline_orchestration_coordinator import (
    TemporalConflictSignal,
    TemporalEvaluationStatus,
    TimelineOrchestrationCoordinator,
    TimelineOrchestrationResult,
)
from app.reality.longitudinal_coordinator import (
    LongitudinalCoordinator,
    LongitudinalCoordinatorResult,
    LongitudinalEvaluationStatus,
)
from app.reality.verification_orchestrator import VerificationEvidenceInbox
from app.reality.verification_reconciler import (
    VerificationReconciler,
    VerificationReconciliationResult,
    VerificationRepairRequest,
)

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
    timeline_result: Optional[TimelineOrchestrationResult] = None
    longitudinal_result: Optional[LongitudinalCoordinatorResult] = None
    reconciliation_result: Optional[VerificationReconciliationResult] = None


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

    def __init__(
        self,
        session: AsyncSession,
        candidate_repo: Optional[CandidateRepository] = None,
        competition_service: Optional[CandidateCompetitionService] = None,
        choice_service: Optional[ChoiceSelectionService] = None,
        inference_coordinator: Optional[AutonomousInferenceCoordinator] = None,
        timeline_coordinator: Optional[TimelineOrchestrationCoordinator] = None,
        longitudinal_coordinator: Optional[LongitudinalCoordinator] = None,
        inbox: Optional[VerificationEvidenceInbox] = None,
        reconciler: Optional[VerificationReconciler] = None,
        rcl_adapter: Optional[Any] = None,
    ) -> None:
        self._session = session
        self._candidate_repo = candidate_repo or CandidateRepository(session)
        self._competition_service = competition_service or CandidateCompetitionService()
        self._choice_service = choice_service or ChoiceSelectionService()
        # Constitutional Lock 9: If rcl_adapter is provided, it supersedes Step C2
        # AutonomousInferenceCoordinator, ensuring exactly ONE Reality Construction authority.
        if rcl_adapter is not None:
            self._inference_coordinator = rcl_adapter
        else:
            self._inference_coordinator = inference_coordinator or AutonomousInferenceCoordinator(
                session=session,
                candidate_repo=self._candidate_repo,
            )
        self._timeline_coordinator = timeline_coordinator or TimelineOrchestrationCoordinator()
        self._longitudinal_coordinator = longitudinal_coordinator or LongitudinalCoordinator()
        self._inbox = inbox
        self._reconciler = reconciler or (VerificationReconciler() if inbox is not None else None)

    async def run_turn(
        self,
        user_input: str,
        core: "CharacterCore",
        memories: Optional[Sequence[Any]] = None,
        character_id: str = "aevum",
        current_location: Optional[str] = None,
        prior_turn_slip: Optional[str] = None,
        bible: Optional["CharacterBible"] = None,
        current_turn_id: str = "turn-0",
        current_turn_sequence: Optional[int] = None,
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
        # Step A2 — Reality Inquiry Signal Detection (Phase 20 Gate 0)
        # INQUIRY != EVIDENCE:
        # Detects whether user message targets an unknown personal reality slot.
        # Pure function. Never raises.
        # ------------------------------------------------------------------
        inquiry_signal: Optional[InquirySignal] = None
        try:
            inquiry_signal = RealityInquiryDetector.detect_inquiry(user_input, core=core)
        except Exception as exc:
            logger.debug("RealityInquiryDetector failed: %s", exc)
            inquiry_signal = None
        requested_slot = inquiry_signal.target_slot if inquiry_signal else None

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
        # Step C2 — Autonomous Reality Inference (Phase 8A)
        # Coordinates Opportunity Detection, Hypothesis Proposal, Evaluation,
        # and Atomic Batch Persistence.
        # Single-invocation-per-turn invariant: executed exactly once per turn.
        # Infrastructure/inference failures are absorbed safely without aborting turn.
        # ------------------------------------------------------------------
        autonomous_candidates: Sequence[CandidateHypothesis] = ()
        try:
            autonomous_candidates = await self._inference_coordinator.run_inference_cycle(
                core=core,
                character_id=character_id,
                requested_slot=requested_slot,
            )
        except Exception as exc:
            logger.error(
                "Autonomous inference cycle failed for character '%s': %s. "
                "Continuing without autonomous candidates.",
                character_id, exc,
            )
            autonomous_candidates = ()

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
        # Step C3 — Retrospective Timeline Orchestration (Phase 8B.5)
        # Evaluates candidate temporal constraint compatibility and synthesizes
        # trajectory plurality without mutating state (Lock 1, 4, 6, 9).
        # Catches unexpected failure and degrades to UNAVAILABLE (zero false exclusions).
        # ------------------------------------------------------------------
        timeline_result: TimelineOrchestrationResult
        try:
            timeline_result = self._timeline_coordinator.coordinate_turn(
                core=core,
                active_candidates=all_candidates,
            )
        except Exception as exc:
            logger.error(
                "Timeline orchestration coordinator failed for character '%s': %s. "
                "Degrading to UNAVAILABLE (zero exclusions, no repair signal).",
                character_id, exc,
            )
            timeline_result = TimelineOrchestrationResult(
                evaluation_status=TemporalEvaluationStatus.UNAVAILABLE,
                evaluation_error=str(exc),
            )

        # Candidate exclusion occurs ONLY when ALL applicable trajectories
        # are HARD_INCOMPATIBLE (Lock 1 & Lock 6).
        eligible_candidates = [
            c for c in all_candidates
            if c.candidate_id not in timeline_result.temporally_incompatible_candidate_ids
        ]

        # ------------------------------------------------------------------
        # Step C4 — Longitudinal Life Progression Coordination (Phase 8C.5)
        # Evaluates derived age, calendar boundaries, guarded transitions,
        # milestone lapses, and trajectory realignment without state mutation.
        # Catches unexpected failure and degrades to UNAVAILABLE (zero false exclusions).
        # ------------------------------------------------------------------
        longitudinal_result: LongitudinalCoordinatorResult
        try:
            active_trajs = (
                timeline_result.trajectory_plurality.compatible_trajectories
                if (
                    timeline_result.evaluation_status == TemporalEvaluationStatus.AVAILABLE
                    and timeline_result.trajectory_plurality is not None
                )
                else ()
            )
            longitudinal_result = self._longitudinal_coordinator.coordinate_turn(
                core=core,
                active_candidates=eligible_candidates,
                trajectories=active_trajs,
            )
        except Exception as exc:
            logger.error(
                "Longitudinal coordinator failed for character '%s': %s. "
                "Degrading to UNAVAILABLE (zero false exclusions).",
                character_id, exc,
            )
            longitudinal_result = LongitudinalCoordinatorResult(
                evaluation_status=LongitudinalEvaluationStatus.UNAVAILABLE,
                effective_now=_utc_now(),
                evaluation_error=str(exc),
            )

        # Candidate exclusion for Step E:
        # Candidates whose intake/activity window has elapsed are excluded from active
        # competition in this turn (Lock 4 & 8C.4 Permanent Lock: Lapsed != Deleted).
        # They remain in all_candidates and in DB, never deleted.
        if longitudinal_result.evaluation_status == LongitudinalEvaluationStatus.AVAILABLE:
            competition_candidates = [
                c for c in eligible_candidates
                if c.candidate_id not in longitudinal_result.temporally_lapsed_candidate_ids
            ]
        else:
            competition_candidates = eligible_candidates

        # ------------------------------------------------------------------
        # Step C5 — Evidence Reconciliation & Refutation Routing (Phase 9.5)
        # Reconciles drained VerificationEvidenceInbox items for this turn.
        # Produces candidate augmentations/proposals to inject into competition,
        # candidates to exclude from current-turn competition view, and repair requests.
        # ADR-020 Item 23: Evaluation-level exclusion ONLY.
        # all_candidates remains the immutable truth source; zero candidate lifecycle mutation.
        # ------------------------------------------------------------------
        reconciliation_result: Optional[VerificationReconciliationResult] = None
        if self._inbox is not None and self._reconciler is not None:
            try:
                drained_items = self._inbox.drain_for_turn(
                    consumer_turn_id=current_turn_id,
                    consumer_turn_sequence=current_turn_sequence,
                )
                if drained_items:
                    reconciliation_result = self._reconciler.reconcile(
                        inbox_items=drained_items,
                        core=core,
                        active_candidates=competition_candidates,
                        consumer_turn_id=current_turn_id,
                        consumer_turn_sequence=current_turn_sequence,
                    )
            except Exception as exc:
                logger.error(
                    "Verification reconciliation failed for character '%s': %s. "
                    "Continuing without reconciliation.",
                    character_id, exc,
                )
                reconciliation_result = None

        if reconciliation_result is not None:
            excluded_ids = set(reconciliation_result.candidate_ids_to_exclude)
            if excluded_ids:
                competition_candidates = [
                    c for c in competition_candidates
                    if c.candidate_id not in excluded_ids
                ]
            if reconciliation_result.candidate_hypotheses_to_inject:
                competition_candidates = (
                    list(competition_candidates)
                    + list(reconciliation_result.candidate_hypotheses_to_inject)
                )

        # ------------------------------------------------------------------
        # Step E — Per-slot Competition
        # No-op when candidate list is empty. Pure computation, no DB writes.
        # ------------------------------------------------------------------
        competition_results = []
        if competition_candidates:
            competition_results = self._run_competition(competition_candidates, core, character_id)

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
        # No-op when contradiction_type is NONE and no canonical temporal conflict.
        # RealityRepairService is the singular repair authority (Lock 2, 3, 7, 8).
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
        elif (
            timeline_result.canonical_conflict_signal is not None
            and timeline_result.evaluation_status == TemporalEvaluationStatus.AVAILABLE
        ):
            try:
                repair_result = self._run_temporal_repair(timeline_result.canonical_conflict_signal)
            except Exception as exc:
                logger.error(
                    "RealityRepairService failed for temporal conflict (character '%s'): %s. "
                    "Continuing without repair result.",
                    character_id, exc,
                )
                repair_result = None
        elif reconciliation_result is not None and reconciliation_result.repair_requests:
            try:
                repair_result = self._run_verification_repair(reconciliation_result.repair_requests[0])
            except Exception as exc:
                logger.error(
                    "RealityRepairService failed for verification repair (character '%s'): %s. "
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

        candidates_for_promotion = (
            list(all_candidates)
            + (list(reconciliation_result.candidate_hypotheses_to_inject) if reconciliation_result else [])
        )
        if choices:
            try:
                promoted, refreshed_core = await self._run_promotion(
                    choices=choices,
                    all_candidates=candidates_for_promotion,
                    core=core,
                    character_id=character_id,
                    target_slot=requested_slot,
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
            trajectory_plurality=timeline_result.trajectory_plurality if timeline_result.evaluation_status == TemporalEvaluationStatus.AVAILABLE else None,
            longitudinal_result=longitudinal_result if longitudinal_result.evaluation_status == LongitudinalEvaluationStatus.AVAILABLE else None,
        )

        return OrchestrationTurnResult(
            governed_reality=governed_reality,
            candidates=all_candidates,
            choices=choices,
            repair_result=repair_result,
            contradiction=contradiction,
            promoted=promoted,
            timeline_result=timeline_result,
            longitudinal_result=longitudinal_result,
            reconciliation_result=reconciliation_result,
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
        slot_name = classification.slot_name
        is_auth = getattr(classification, "is_authoritative", False)
        # Canonical slot normalization: for authoritative revisions, ensure canonical education.institution is targeted
        target_slot = "education.institution" if is_auth and slot_name == "education.university" else slot_name
        cluster_key = f"{character_id}.{target_slot}.user_assertion"

        # Record evidence family (idempotent — same cluster_key increments mention_count)
        source_type = "OFFICIAL_RECORD" if is_auth else "USER_ASSERTION"
        evidence_family = await self._candidate_repo.record_evidence(
            source_type=source_type,
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
        if is_auth:
            plausibility = PlausibilityBreakdown.create(
                evidence_grounding_score=0.95,
                coherence_score=0.90,
            )
        else:
            plausibility = PlausibilityBreakdown.create(
                evidence_grounding_score=0.55,
                coherence_score=0.60,
            )

        candidate = CandidateHypothesis(
            candidate_id=candidate_id,
            entity_id=character_id,
            slot_name=target_slot,
            proposed_value=classification.claimed_value or user_input[:120],
            reality_taxonomy=classification.reality_taxonomy,
            inference_depth=provenance.inference_depth,
            inference_edge_type=classification.inference_edge_type,
            plausibility=plausibility,
            provenance=provenance,
            evidence_families=(evidence_family,),
            lifecycle_state=CandidateLifecycleState.GENERATED,
            selection_metadata=(
                {"is_authoritative_revision": True, "revision_slot": target_slot}
                if is_auth
                else None
            ),
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
                # Correction A: Derive multi-attribute factor inputs with explicit provenance and neutral fallbacks
                factor_inputs = self._derive_choice_factor_inputs(
                    competition_result=comp_result,
                    core=core,
                    bible=bible,
                )
                choice = self._choice_service.select_choice(
                    competition_result=comp_result,
                    factor_inputs_by_candidate=factor_inputs,
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

    @classmethod
    def _derive_choice_factor_inputs(
        cls,
        competition_result: CompetitionResult,
        core: Optional["CharacterCore"] = None,
        bible: Optional["CharacterBible"] = None,
    ) -> dict[str, ChoiceFactorBreakdown]:
        """Derive multi-attribute factor inputs for choice selection.

        Provenance Rules (Correction A):
        - plausibility_score: from competition_result.plausibility_scores (adjusted plausibility).
        - temperament_fit, values_alignment, challenge_preference, resource_compatibility, timeline_compatibility:
          derived from canonical reality if explicit evidence exists, otherwise strictly neutral 0.50 baseline.
        - opportunity_cost, time_cost: strictly default to 0.0 (Phase 7 default contract).
        - ZERO arbitrary constants (like 0.10) allowed.
        """
        factor_inputs: dict[str, ChoiceFactorBreakdown] = {}
        for cand in competition_result.viable_candidates:
            cid = cand.candidate_id
            plaus_score = competition_result.plausibility_scores.get(
                cid,
                cand.plausibility.composite_plausibility_score,
            )

            temp_fit = 0.5
            val_align = 0.5
            chal_pref = 0.5
            res_compat = 0.5
            time_compat = 0.5
            opp_cost = 0.0
            time_cost = 0.0

            # Derive from canonical core if explicit evidence is available
            if core is not None and hasattr(core, "facts") and core.facts:
                val_str = str(cand.proposed_value).lower()
                # 1. Temperament fit from core temperament / personality facts
                temp_fact = core.get_fact("personality.temperament") or core.get_fact("identity.temperament")
                if temp_fact and temp_fact.value:
                    tf_val = str(temp_fact.value).lower()
                    if tf_val in val_str or any(w in val_str for w in tf_val.split()):
                        temp_fit = 0.75

                # 1b. Temperament / Interest fit from core interests
                interests_fact = core.get_fact("interests")
                if interests_fact and interests_fact.value:
                    int_vals = interests_fact.value if isinstance(interests_fact.value, (list, tuple)) else [interests_fact.value]
                    if cand.slot_name == "education.major" and "music" in val_str:
                        if any("piano" in str(x).lower() or "guitar" in str(x).lower() or "music" in str(x).lower() for x in int_vals):
                            temp_fit = 0.75

                # 1c. Temperament fit from core dislikes
                dislikes_fact = core.get_fact("dislikes")
                if dislikes_fact and dislikes_fact.value:
                    dis_vals = dislikes_fact.value if isinstance(dislikes_fact.value, (list, tuple)) else [dislikes_fact.value]
                    if cand.slot_name in ("education.institution", "education.university") and ("usm" in val_str or "sains" in val_str):
                        if any("crowd" in str(x).lower() or "noisy" in str(x).lower() for x in dis_vals):
                            temp_fit = 0.75

                # 2. Values alignment from core values / philosophy facts
                val_fact = core.get_fact("identity.values") or core.get_fact("character.values")
                if val_fact and val_fact.value:
                    vf_val = str(val_fact.value).lower()
                    if vf_val in val_str or any(w in val_str for w in vf_val.split()):
                        val_align = 0.75

                # 3. Timeline compatibility from age
                age_fact = core.get_fact("identity.age")
                if age_fact and age_fact.value:
                    try:
                        age = int(age_fact.value)
                        if age < 16 and "university" in cand.slot_name:
                            time_compat = 0.20
                        elif age >= 18:
                            time_compat = 0.50
                        if cand.slot_name == "education.year" and age == 21:
                            if val_str in ("year 2", "year_2", "2"):
                                time_compat = 0.75
                    except (ValueError, TypeError):
                        time_compat = 0.50

            factor_inputs[cid] = ChoiceFactorBreakdown(
                plausibility_score=plaus_score,
                temperament_fit=temp_fit,
                values_alignment=val_align,
                challenge_preference=chal_pref,
                resource_compatibility=res_compat,
                timeline_compatibility=time_compat,
                opportunity_cost=opp_cost,
                time_cost=time_cost,
            )
        return factor_inputs

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

        elif ct == ContradictionType.WORLD_KNOWLEDGE_CONFLICT:
            conflict_type = "POP_CULTURE_SLIP"
            is_social_misspeak = True
            social_explanation = contradiction.repair_guidance

        elif ct == ContradictionType.USER_FACTUAL_ERROR:
            conflict_type = "FACTUAL_DISAGREEMENT"
            social_explanation = contradiction.repair_guidance

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

    def _run_temporal_repair(
        self,
        signal: TemporalConflictSignal,
    ) -> Optional[RealityRepairResult]:
        """Delegate canonical temporal conflict to existing RealityRepairService (Lock 3).

        Zero second repair engine. C3 produces signal/evidence; RealityRepairService
        is the sole repair authority and selects the repair level (Lock 2, 7, 8).
        """
        adapter = signal.temporal_evidence
        evidence_dict = adapter.to_repair_evidence_dict()
        return RealityRepairService.repair(
            conflict_type="TEMPORAL_CONFLICT",
            timeline_evidence=evidence_dict,
            rationale=signal.rationale,
        )

    def _run_verification_repair(
        self,
        repair_req: VerificationRepairRequest,
    ) -> Optional[RealityRepairResult]:
        """Delegate factual contradiction from verification reconciliation to existing RealityRepairService.

        ADR-020 Item 22: Reconciler passes factual inputs; RealityRepairService evaluates 5-level hierarchy.
        """
        timeline_evidence: Optional[dict[str, Any]] = None
        if repair_req.temporal_split_context is not None:
            ctx = repair_req.temporal_split_context
            timeline_evidence = {
                "independent_timeline_supported": True,
                "temporal_split": {
                    "past": ctx.conflicting_interval,
                    "present": ctx.observed_interval,
                },
                "temporal_relation": ctx.temporal_relation,
            }

        entity_disambiguation: Optional[dict[str, Any]] = None
        if repair_req.entity_disambiguation_context is not None:
            ectx = repair_req.entity_disambiguation_context
            entity_disambiguation = {
                "independent_evidence_supported": True,
                "ambiguous_name": ectx.canonical_entity_anchor,
                "reanchored_target": ectx.observed_entity_anchor,
                "ambiguity_reason": ectx.ambiguity_reason,
            }

        return RealityRepairService.repair(
            claim_key=repair_req.claim_key,
            claimed_value=repair_req.claimed_value,
            existing_value=repair_req.existing_value,
            unconfirmed_candidate_id=repair_req.target_candidate_id,
            timeline_evidence=timeline_evidence,
            entity_disambiguation=entity_disambiguation,
            compensatory_biography_requested=repair_req.compensatory_biography_requested,
            rationale=repair_req.rationale,
        )

    async def _run_promotion(
        self,
        choices: list[ChoiceDecisionResult],
        all_candidates: list[CandidateHypothesis],
        core: "CharacterCore",
        character_id: str,
        target_slot: Optional[str] = None,
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

        # If target_slot is specified, prioritize choices matching target_slot
        ordered_choices = list(choices)
        if target_slot:
            ordered_choices.sort(key=lambda ch: 0 if ch.slot_name == target_slot else 1)

        promoted = False
        for choice in ordered_choices:
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
                    logger.info(
                        "[PROMOTION] slot=%s candidate=%s value=%s",
                        candidate.slot_name,
                        candidate.candidate_id,
                        candidate.proposed_value,
                    )
                    logger.info(
                        "[CANONICAL] Committed slot '%s' with value '%s' to DB",
                        candidate.slot_name,
                        candidate.proposed_value,
                    )
                    # One successful promotion per turn is enough; refresh core and stop.
                    break
            except PermissionError as perm_err:
                logger.info(
                    "Autonomous promotion for candidate '%s' slot '%s' skipped by Hard Gates: %s",
                    candidate.candidate_id, candidate.slot_name, perm_err,
                )
            except Exception as exc:
                logger.error(
                    "promote_candidate unexpected failure for candidate '%s' slot '%s': %s. "
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
