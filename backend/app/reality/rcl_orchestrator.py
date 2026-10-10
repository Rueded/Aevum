"""Reality Construction Orchestrator & Governance Gate (Phase 14.3).

Governed by ADR-025 (Revision 1):
- Lock 9  — One Construction Authority:
    There is exactly one authoritative Reality Construction orchestration path.
    Phase 8A Step C2 (AutonomousInferenceCoordinator) is superseded as an independent
    implementation; its per-turn trigger semantics become RCLTriggerKind.POST_CONVERSATION.
    No parallel competing inference path may execute independently.
- Lock 12 — No Same-Cycle Recursive Premise Promotion:
    Candidates generated within RCL cycle N are structurally blocked from promotion
    in cycle N by the CycleIsolationLedger.
- Lock 2  — Cycle Isolation is an Eligibility Boundary, NOT a Promotion Condition:
    A candidate from cycle N must undergo independent re-evaluation in a later cycle
    using canonical premises available at that later cycle before it may be promoted.
- Decision D2 — Promotion Velocity Cap:
    Maximum 1 biography promotion per character per RCL cycle.
- Lock 3  — Single Promotion Authority:
    Promotion is strictly delegated to BiographyPromotionService.promote_candidate()
    holding PromotionAuthorizationToken. RealityConstructionOrchestrator never calls
    set_fact() or mints tokens.
- Lock 7  — Failure Isolation:
    RCL exceptions are caught, logged, and return a skipped result. Conversation flow
    is never broken.
- Lock 8  — Canonical Facts Cannot Be Demoted by Construction.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Sequence, Set
import uuid

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.core_models import CharacterCore
from app.reality.biography_promotion_service import BiographyPromotionService
from app.reality.candidate_evaluator import CandidateEvaluationAdapter
from app.reality.candidate_models import CandidateHypothesis, CandidateLifecycleState
from app.reality.candidate_repository import CandidateRepository
from app.reality.choice_models import ChoiceDecisionResult, CompetitionResult
from app.reality.choice_service import ChoiceSelectionService
from app.reality.competition_service import CandidateCompetitionService
from app.reality.constraint_engine import ConstraintClass, ConstraintSetEvaluator
from app.reality.inference_models import CandidateEnvelope, InferenceProposalRequest
from app.reality.inference_opportunity_detector import InferenceOpportunityDetector
from app.reality.proposer import DeterministicLifeHypothesisProposer, LifeHypothesisProposer
from app.reality.models import FactStatus
from app.reality.rcl_scheduler import (
    RCLCycleContext,
    RCLCycleResult,
    RCLScheduler,
    RCLTriggerKind,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class RCLExecutionError(Exception):
    """Raised when an internal error occurs during RCL cycle execution."""
    pass


# ---------------------------------------------------------------------------
# In-Memory Cycle Isolation Ledger (Lock 12)
# ---------------------------------------------------------------------------

class CycleIsolationLedger:
    """Ephemeral in-memory ledger tracking candidate IDs generated in active cycles.

    Constitutional Invariant (ADR-025 Lock 12):
    Candidates generated within RCL cycle N are structurally blocked from being
    promoted in cycle N.

    Storage:
    Strictly in-memory; never persisted to SQLite. Cleared per cycle upon completion.
    """

    def __init__(self) -> None:
        self._cycle_candidates: dict[str, set[str]] = {}

    def record_generated_candidates(
        self,
        cycle_id: str,
        candidate_ids: Sequence[str],
    ) -> None:
        """Record candidates generated during cycle_id."""
        if cycle_id not in self._cycle_candidates:
            self._cycle_candidates[cycle_id] = set()
        self._cycle_candidates[cycle_id].update(candidate_ids)

    def is_generated_in_current_cycle(
        self,
        cycle_id: str,
        candidate_id: str,
    ) -> bool:
        """Return True if candidate_id was generated in cycle_id."""
        return candidate_id in self._cycle_candidates.get(cycle_id, set())

    def get_cycle_candidates(self, cycle_id: str) -> set[str]:
        """Return a copy of all candidate IDs recorded for cycle_id."""
        return set(self._cycle_candidates.get(cycle_id, set()))

    def clear_cycle(self, cycle_id: str) -> None:
        """Purge cycle records upon cycle completion."""
        self._cycle_candidates.pop(cycle_id, None)

    def clear_all(self) -> None:
        """Clear all records (used for test teardown)."""
        self._cycle_candidates.clear()


# ---------------------------------------------------------------------------
# Governance Gate (Lock 2, Lock 12, Velocity Cap D2, Lock 8)
# ---------------------------------------------------------------------------

class GovernanceGateResult(BaseModel):
    """Immutable outcome of RCL governance gate evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    is_eligible: bool = Field(description="Whether the candidate is authorized for canonical promotion.")
    reason: str = Field(description="Explanation of gate verdict.")
    candidate_id: str
    lock_rule_id: Optional[str] = Field(default=None, description="Triggered lock ID if rejected.")


class RCLGovernanceGate:
    """Enforces Phase 14 constitutional constraints on candidate promotion.

    Rules enforced:
    1. Lock 12: Same-cycle promotion structurally blocked (candidate in CycleIsolationLedger).
    2. Lock 2: Candidate must have been generated in an earlier cycle AND independently
       evaluated against current canonical premises.
    3. Decision D2: Velocity Cap — max 1 biography promotion per character per RCL cycle.
    4. Lock 8: Canonical facts cannot be demoted by construction.
    """

    def __init__(
        self,
        ledger: Optional[CycleIsolationLedger] = None,
        constraint_evaluator: Optional[ConstraintSetEvaluator] = None,
    ) -> None:
        self.ledger = ledger or CycleIsolationLedger()
        self.constraint_evaluator = constraint_evaluator or ConstraintSetEvaluator()

    def evaluate(
        self,
        candidate: CandidateHypothesis,
        current_cycle_id: str,
        promotions_in_current_cycle: int = 0,
        core: Optional[CharacterCore] = None,
    ) -> GovernanceGateResult:
        """Evaluate candidate promotion eligibility."""
        cid = candidate.candidate_id

        # Gate 1 — Lock 12: Same-cycle structural block
        if self.ledger.is_generated_in_current_cycle(current_cycle_id, cid):
            return GovernanceGateResult(
                is_eligible=False,
                reason=(
                    f"Candidate '{cid}' was generated in current cycle '{current_cycle_id}'. "
                    "Same-cycle promotion is structurally blocked (ADR-025 Lock 12)."
                ),
                candidate_id=cid,
                lock_rule_id="LOCK_12_SAME_CYCLE_BLOCKED",
            )

        # Gate 2 — Lock 2: Independent re-evaluation against CURRENT canonical premises
        # Candidate age / prior-cycle existence alone is NEVER a promotion condition.
        # It must undergo fresh constraint evaluation against the current CharacterCore snapshot.
        constraint_profile = self.constraint_evaluator.evaluate(
            slot=candidate.slot_name,
            value=candidate.proposed_value,
            core=core,
        )
        if constraint_profile.is_hard_rejected:
            return GovernanceGateResult(
                is_eligible=False,
                reason=(
                    f"Lock 2: Independent re-evaluation against current canonical premises failed. "
                    f"Hard constraint violations: {constraint_profile.hard_reject_reasons}"
                ),
                candidate_id=cid,
                lock_rule_id="LOCK_2_RE_EVALUATION_FAILED",
            )

        # Gate 3 — Decision D2: Velocity Cap (max 1 promotion per cycle)
        if promotions_in_current_cycle >= 1:
            return GovernanceGateResult(
                is_eligible=False,
                reason=(
                    f"Velocity cap reached: cycle '{current_cycle_id}' has already executed "
                    f"{promotions_in_current_cycle} biography promotion(s). "
                    "Max 1 promotion allowed per cycle (ADR-025 Decision D2)."
                ),
                candidate_id=cid,
                lock_rule_id="DECISION_D2_VELOCITY_CAP",
            )

        # Gate 4 — Lock 8: Canonical fact cannot be demoted by construction
        if core:
            fact = core.get_fact(candidate.slot_name)
            if fact and fact.status == FactStatus.CANONICAL:
                if fact.value != candidate.proposed_value:
                    # Modifying an existing canonical fact cannot be done by standard construction;
                    # must go through full repair/reconciliation pipeline.
                    return GovernanceGateResult(
                        is_eligible=False,
                        reason=(
                            f"Slot '{candidate.slot_name}' already contains canonical fact '{fact.value}'. "
                            "Canonical facts cannot be overwritten or demoted by autonomous construction (ADR-025 Lock 8)."
                        ),
                        candidate_id=cid,
                        lock_rule_id="LOCK_8_CANONICAL_DEMOTION_BLOCKED",
                    )

        # Gate 5 — Lock 2: Candidate generated in earlier cycle and passing current evaluation is eligible
        return GovernanceGateResult(
            is_eligible=True,
            reason="Passed RCL governance gate; authorized for promotion pipeline.",
            candidate_id=cid,
            lock_rule_id=None,
        )


# ---------------------------------------------------------------------------
# Reality Construction Orchestrator (Lock 9: One Construction Authority)
# ---------------------------------------------------------------------------

class RealityConstructionOrchestrator:
    """The singular authoritative coordinator for autonomous reality construction.

    Coordinates the complete RCL sequence:
      1. Opportunity Detection (InferenceOpportunityDetector)
      2. Constraint Evaluation (ConstraintSetEvaluator - Phase 14.2)
      3. Hypothesis Generation (DeterministicLifeHypothesisProposer)
      4. Cycle Isolation Ledger recording (CycleIsolationLedger - Lock 12)
      5. Atomic Batch Persistence (CandidateRepository)
      6. Candidate Competition (CandidateCompetitionService)
      7. Choice Selection (ChoiceSelectionService)
      8. Governance Gating (RCLGovernanceGate - Lock 2, 12, D2)
      9. Promotion Delegation (BiographyPromotionService - Lock 3)

    Constitutional Discipline:
      - Lock 3: Never calls set_fact() or mints PromotionAuthorizationToken directly.
      - Lock 7: Isolates failures, returns skipped result with loop_skipped_reason="RCL_EXCEPTION".
      - Lock 9: Supersedes Phase 8A Step C2 AutonomousInferenceCoordinator.
    """

    def __init__(
        self,
        session: AsyncSession,
        candidate_repo: Optional[CandidateRepository] = None,
        scheduler: Optional[RCLScheduler] = None,
        ledger: Optional[CycleIsolationLedger] = None,
        governance_gate: Optional[RCLGovernanceGate] = None,
        constraint_evaluator: Optional[ConstraintSetEvaluator] = None,
        detector: Optional[type[InferenceOpportunityDetector]] = None,
        proposer: Optional[LifeHypothesisProposer] = None,
        evaluator: Optional[CandidateEvaluationAdapter] = None,
        competition_service: Optional[CandidateCompetitionService] = None,
        choice_service: Optional[ChoiceSelectionService] = None,
        promotion_service: Optional[BiographyPromotionService] = None,
    ) -> None:
        self._session = session
        self._candidate_repo = candidate_repo or CandidateRepository(session)
        self._scheduler = scheduler or RCLScheduler()
        self._ledger = ledger or CycleIsolationLedger()
        self._governance_gate = governance_gate or RCLGovernanceGate(ledger=self._ledger)
        self._constraint_evaluator = constraint_evaluator or ConstraintSetEvaluator()
        self._detector = detector or InferenceOpportunityDetector
        self._proposer = proposer or DeterministicLifeHypothesisProposer()
        self._evaluator = evaluator or CandidateEvaluationAdapter()
        self._competition_service = competition_service or CandidateCompetitionService()
        self._choice_service = choice_service or ChoiceSelectionService()
        self._promotion_service = promotion_service

    @property
    def scheduler(self) -> RCLScheduler:
        return self._scheduler

    @property
    def ledger(self) -> CycleIsolationLedger:
        return self._ledger

    @property
    def governance_gate(self) -> RCLGovernanceGate:
        return self._governance_gate

    async def run_rcl_cycle(
        self,
        character_id: str,
        core: CharacterCore,
        trigger_kind: RCLTriggerKind = RCLTriggerKind.POST_CONVERSATION,
        cycle_context: Optional[RCLCycleContext] = None,
    ) -> RCLCycleResult:
        """Execute a complete Reality Construction Loop cycle for a character."""
        # 1. Scheduler Eligibility Gate
        if cycle_context is None:
            eligible, ctx, skip_reason = self._scheduler.request_cycle(
                character_id=character_id,
                trigger_kind=trigger_kind,
                active_canonical_facts_count=len(core.facts),
            )
            if not eligible or ctx is None:
                return self._scheduler.make_skipped_result(
                    character_id=character_id,
                    trigger_kind=trigger_kind,
                    skip_reason=skip_reason,
                )
            cycle_context = ctx

        cycle_id = cycle_context.cycle_id
        start_mono = cycle_context.triggered_at_monotonic
        self._scheduler.mark_cycle_started(character_id)

        candidates_generated = 0
        candidates_promoted = 0
        candidates_suppressed = 0

        try:
            # 2. Opportunity Detection
            active_candidates = await self._candidate_repo.get_all_active_candidates(character_id)
            opportunity_req = self._detector.detect_opportunity(
                core=core,
                active_candidates=active_candidates,
                cycle_id=cycle_id,
            )

            if opportunity_req is None:
                result = self._scheduler.make_completed_result(
                    context=cycle_context,
                    started_at_monotonic=start_mono,
                    candidates_generated=0,
                    candidates_promoted=0,
                    candidates_suppressed=0,
                )
                return result

            slot = opportunity_req.target_slot

            # 3. Hypothesis Generation & Constraint Evaluation
            raw_envelopes = self._proposer.propose_hypotheses(opportunity_req)

            # Filter envelopes against ConstraintSetEvaluator (Phase 14.2)
            viable_envelopes: list[CandidateEnvelope] = []
            for env in raw_envelopes:
                profile = self._constraint_evaluator.evaluate(
                    slot=slot,
                    value=env.proposed_value,
                    core=core,
                )
                # Hard rejects are completely excluded from hypothesis set
                if profile.is_hard_rejected:
                    logger.debug(
                        "RCL hypothesis '%s' for slot '%s' hard-rejected: %s",
                        env.proposed_value, slot, profile.hard_reject_reasons,
                    )
                    continue
                viable_envelopes.append(env)

            # Cardinality guard: must have at least 2 viable candidates for plurality
            if len(viable_envelopes) < 2:
                result = self._scheduler.make_completed_result(
                    context=cycle_context,
                    started_at_monotonic=start_mono,
                    candidates_generated=0,
                    candidates_promoted=0,
                    candidates_suppressed=len(raw_envelopes) - len(viable_envelopes),
                )
                return result

            # Evaluate envelopes into in-memory CandidateHypotheses
            generated_candidates = self._evaluator.evaluate_envelopes(
                envelopes=viable_envelopes,
                request=opportunity_req,
                core=core,
            )
            candidates_generated = len(generated_candidates)

            # 4. Cycle Isolation Ledger Recording (Lock 12)
            generated_ids = [c.candidate_id for c in generated_candidates]
            self._ledger.record_generated_candidates(cycle_id, generated_ids)

            # 5. Atomic Batch Persistence
            await self._candidate_repo.save_candidate_batch(generated_candidates)

            # 6. Candidate Competition & Choice Selection
            # Reload all active candidates for this slot (both earlier cycles & newly saved)
            slot_candidates = await self._candidate_repo.get_active_candidates_for_slot(
                slot_name=slot,
                character_id=character_id,
            )

            if len(slot_candidates) >= 2:
                comp_result = self._competition_service.compete_slot(
                    slot_name=slot,
                    candidates=slot_candidates,
                    core=core,
                )

                if comp_result.leading_candidate is not None:
                    choice_result = self._choice_service.select_choice(
                        competition_result=comp_result,
                        core=core,
                    )
                    chosen_cand = choice_result.chosen_candidate

                    # 7. RCL Governance Gate (Lock 2, Lock 12, Velocity Cap D2)
                    gov_result = self._governance_gate.evaluate(
                        candidate=chosen_cand,
                        current_cycle_id=cycle_id,
                        promotions_in_current_cycle=candidates_promoted,
                        core=core,
                    )

                    if gov_result.is_eligible and self._promotion_service is not None:
                        # 8. Promotion Delegation (Lock 3: single promotion authority)
                        promo_record = await self._promotion_service.promote_candidate(
                            candidate_id=chosen_cand.candidate_id,
                            choice_result=choice_result,
                            character_id=character_id,
                        )
                        if promo_record is not None:
                            candidates_promoted += 1
                        else:
                            candidates_suppressed += 1
                    else:
                        candidates_suppressed += 1

            result = self._scheduler.make_completed_result(
                context=cycle_context,
                started_at_monotonic=start_mono,
                candidates_generated=candidates_generated,
                candidates_promoted=candidates_promoted,
                candidates_suppressed=candidates_suppressed,
            )
            return result

        except Exception as exc:
            # Lock 7: Failure Isolation
            logger.error(
                "Reality Construction Loop failed for character '%s': %s",
                character_id, exc, exc_info=True,
            )
            result = self._scheduler.make_skipped_result(
                character_id=character_id,
                trigger_kind=cycle_context.trigger_kind,
                skip_reason="RCL_EXCEPTION",
                started_at_monotonic=start_mono,
                exception_detail=str(exc),
            )
            return result

        finally:
            self._scheduler.mark_cycle_completed(character_id, result)
            self._ledger.clear_cycle(cycle_id)


# ---------------------------------------------------------------------------
# RCL Adapter (Bridges into RealityOrchestrationService, supersedes Step C2)
# ---------------------------------------------------------------------------

class RCLAdapter:
    """Adapter integrating RealityConstructionOrchestrator into per-turn orchestration.

    Constitutional Lock 9:
    Supersedes Phase 8A Step C2 AutonomousInferenceCoordinator.
    When invoked per-turn, routes through RCLScheduler with trigger POST_CONVERSATION.
    If cooldown is active, gracefully returns empty tuple (zero fake turns, zero competing paths).
    """

    def __init__(
        self,
        orchestrator: RealityConstructionOrchestrator,
    ) -> None:
        self._orchestrator = orchestrator

    async def run_inference_cycle(
        self,
        core: CharacterCore,
        character_id: str = "aevum",
        cycle_id: Optional[str] = None,
    ) -> Sequence[CandidateHypothesis]:
        """Interface method superseding AutonomousInferenceCoordinator.run_inference_cycle (Lock 9)."""
        return await self.coordinate_post_turn(core=core, character_id=character_id)

    async def coordinate_post_turn(
        self,
        core: CharacterCore,
        character_id: str = "aevum",
    ) -> Sequence[CandidateHypothesis]:
        """Execute post-conversation reality construction via the singular RCL authority.

        Returns newly generated candidates if an RCL cycle successfully executed,
        or empty tuple if skipped/cooling down.
        """
        result = await self._orchestrator.run_rcl_cycle(
            character_id=character_id,
            core=core,
            trigger_kind=RCLTriggerKind.POST_CONVERSATION,
        )

        if result.loop_skipped_reason is not None or result.candidates_generated == 0:
            return ()

        # Return active candidates for the character
        return await self._orchestrator._candidate_repo.get_all_active_candidates(character_id)
