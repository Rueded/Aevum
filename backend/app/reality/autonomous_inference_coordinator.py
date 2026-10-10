"""Autonomous Reality Inference Coordinator for Phase 8A.

Coordinates Step C2 of per-turn reality orchestration:
1. Detects inference opportunities via InferenceOpportunityDetector (7-gate filter).
2. Proposes diverse hypotheses via LifeHypothesisProposer (minimum 2 candidates, normalized).
3. Evaluates hypotheses independently via CandidateEvaluationAdapter (GENERATED state, no selection metadata).
4. Persists the candidate batch atomically via CandidateRepository (Correction C: all-or-nothing rollback).

Strict Invariants:
- Single-invocation-per-turn invariant: linear, non-recursive execution; max 1 slot per cycle.
- Cardinality invariant: requires >= 2 viable candidates; never proposes or persists a single candidate.
- Atomic batch persistence: if saving any candidate fails, the entire batch is rolled back.
- Zero canonical mutation: never calls set_fact() or mints promotion tokens.
"""

from __future__ import annotations

import inspect
import logging
from typing import Optional, Sequence, TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.reality.candidate_models import CandidateHypothesis, CandidateLifecycleState
from app.reality.candidate_repository import CandidateRepository
from app.reality.inference_opportunity_detector import InferenceOpportunityDetector
from app.reality.proposer import DeterministicLifeHypothesisProposer, LifeHypothesisProposer
from app.reality.candidate_evaluator import CandidateEvaluationAdapter

if TYPE_CHECKING:
    from app.character.core_models import CharacterCore

logger = logging.getLogger(__name__)


class AutonomousInferenceCoordinator:
    """Encapsulates Step C2 autonomous inference within the per-turn reality pipeline."""

    def __init__(
        self,
        session: AsyncSession,
        candidate_repo: Optional[CandidateRepository] = None,
        detector: Optional[type[InferenceOpportunityDetector]] = None,
        proposer: Optional[LifeHypothesisProposer] = None,
        evaluator: Optional[CandidateEvaluationAdapter] = None,
    ) -> None:
        self._session = session
        self._candidate_repo = candidate_repo or CandidateRepository(session)
        self._detector = detector or InferenceOpportunityDetector
        self._proposer = proposer or DeterministicLifeHypothesisProposer()
        self._evaluator = evaluator or CandidateEvaluationAdapter()

    async def run_inference_cycle(
        self,
        core: "CharacterCore",
        character_id: str = "aevum",
        cycle_id: Optional[str] = None,
        requested_slot: Optional[str] = None,
    ) -> Sequence[CandidateHypothesis]:
        """Execute one autonomous inference cycle for the character.

        Pipeline Stages:
        1. Opportunity Detection: Query active slots from repo, evaluate 7 gates for candidate slots.
        2. Hypothesis Proposal: Synthesize 2 to 4 diverse options.
        3. Validation & Evaluation: Independently evaluate coherence and entity validity.
        4. Atomic Batch Persistence: Persist all evaluated candidates in a single atomic transaction/savepoint.

        Returns:
            Sequence[CandidateHypothesis]: The persisted candidates (in PERSISTED state),
            or () if no opportunity, proposal rejected, or failure occurred.
        """
        try:
            # -----------------------------------------------------------------
            # 1. Detect Opportunity (Gate 1 to Gate 7)
            # -----------------------------------------------------------------
            request = await self._detector.detect_opportunity_async(
                core=core,
                candidate_repo=self._candidate_repo,
                character_id=character_id,
                cycle_id=cycle_id,
                requested_slot=requested_slot,
            )
            if request is None:
                logger.debug("No inference opportunity detected for character '%s'.", character_id)
                return ()

            logger.info(
                "[OPPORTUNITY] slot=%s state=unknown target=%s",
                request.target_slot,
                request.target_slot,
            )

            logger.info(
                "Inference opportunity detected for slot '%s' (cycle '%s').",
                request.target_slot,
                request.inference_cycle_id,
            )

            # -----------------------------------------------------------------
            # 2. Propose Hypotheses (Minimum 2 viable candidates required)
            # -----------------------------------------------------------------
            propose_res = self._proposer.propose_hypotheses(request)
            if inspect.iscoroutine(propose_res):
                envelopes = await propose_res
            else:
                envelopes = propose_res

            if not envelopes or len(envelopes) < 2:
                logger.warning(
                    "Proposer returned fewer than 2 candidates (%d) for slot '%s'; "
                    "aborting cycle to satisfy Gate 6 plurality invariant.",
                    len(envelopes) if envelopes else 0,
                    request.target_slot,
                )
                return ()

            # -----------------------------------------------------------------
            # 3. Validation & Independent Evaluation
            # Emits candidates with lifecycle_state = GENERATED, selection_metadata = None
            # -----------------------------------------------------------------
            evaluated_candidates = self._evaluator.evaluate_envelopes(
                envelopes=envelopes,
                request=request,
                core=core,
            )

            if not evaluated_candidates or len(evaluated_candidates) < 2:
                logger.warning(
                    "Evaluator returned fewer than 2 valid candidates for slot '%s'; aborting cycle.",
                    request.target_slot,
                )
                return ()

            # -----------------------------------------------------------------
            # 4. Atomic Batch Persistence (Correction C)
            # All candidates in the batch are saved together or none are saved.
            # -----------------------------------------------------------------
            persisted_candidates = await self._persist_candidate_batch_atomic(
                candidates=evaluated_candidates,
                character_id=character_id,
                slot_name=request.target_slot,
            )
            return persisted_candidates

        except Exception as exc:
            logger.error(
                "Autonomous inference cycle encountered unhandled error for character '%s': %s. "
                "Absorbing failure safely.",
                character_id, exc,
            )
            return ()

    async def _persist_candidate_batch_atomic(
        self,
        candidates: Sequence[CandidateHypothesis],
        character_id: str,
        slot_name: str,
    ) -> Sequence[CandidateHypothesis]:
        """Persist a candidate hypothesis batch atomically.

        If saving ANY candidate fails, the entire batch is rolled back to prevent
        leaving an incomplete candidate set (e.g. k=1 orphan candidate) in DB.
        """
        persisted: list[CandidateHypothesis] = []

        savepoint_cm = None
        if hasattr(self._session, "begin_nested") and callable(self._session.begin_nested):
            try:
                nested = self._session.begin_nested()
                if hasattr(nested, "__aenter__"):
                    savepoint_cm = nested
            except Exception:
                savepoint_cm = None

        try:
            if savepoint_cm is not None:
                async with savepoint_cm:
                    for cand in candidates:
                        p_cand = await self._candidate_repo.save_candidate(cand)
                        persisted.append(p_cand)
            else:
                for cand in candidates:
                    p_cand = await self._candidate_repo.save_candidate(cand)
                    persisted.append(p_cand)

            logger.info(
                "Successfully persisted candidate batch of %d candidates for slot '%s'.",
                len(persisted), slot_name,
            )
            return tuple(persisted)

        except Exception as exc:
            logger.error(
                "Atomic candidate batch persistence failed for slot '%s' (character '%s'): %s. "
                "Rolling back entire batch to preserve plurality invariant.",
                slot_name, character_id, exc,
            )
            try:
                if hasattr(self._session, "rollback"):
                    res = self._session.rollback()
                    if inspect.iscoroutine(res):
                        await res
            except Exception as rb_exc:
                logger.error("Session rollback failed during batch rollback: %s", rb_exc)

            return ()
