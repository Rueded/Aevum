"""Candidate Competition Service for Project Aevum (Phase 7D.2).

Responsibilities:
- Evaluates candidate viability within a slot's CandidateHypothesisSet.
- Checks constraints against USER_LOCKED core facts, Timeline, Causality, and Quarantine.
- Computes heuristic plausibility comparison with Occam complexity penalty.
- Computes decision margin: Δ = |S1 - S2|.
- Identifies ambiguity (UNDETERMINED_AMBIVALENCE when Δ < 0.10).
- Preserves viable candidates (does not prematurely discard runner-up alternatives).
- STRICT INVARIANT: Competition does NOT choose the winner or mutate canonical reality.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Sequence
import uuid

if TYPE_CHECKING:
    from app.character.core_models import CharacterCore
from app.reality.candidate_models import (
    CandidateFact,
    CandidateHypothesis,
    CandidateHypothesisSet,
)
from app.reality.choice_models import (
    ChoiceConfig,
    CompetitionResult,
    CompetitionState,
)
from app.reality.validators import (
    CausalityValidator,
    ConsistencyValidator,
    TimelineValidator,
)


class CandidateCompetitionService:
    """Service evaluating viability and plausibility competition among candidate hypotheses."""

    def __init__(self, config: Optional[ChoiceConfig] = None) -> None:
        self.config = config or ChoiceConfig()

    def evaluate_competition(
        self,
        candidate_set_or_candidates: Sequence[CandidateHypothesis] | CandidateHypothesisSet,
        core: Optional["CharacterCore"] = None,
        slot_name: Optional[str] = None,
        entity_id: str = "aevum",
    ) -> CompetitionResult:
        """Evaluate competition and viability for candidates targeting a specific slot.
        
        Strict Invariants:
        - Never promotes candidates.
        - Preserves all viable candidates up to capacity.
        - Identifies ambiguity if Δ < 0.10 without manufacturing false certainty.
        """
        if isinstance(candidate_set_or_candidates, CandidateHypothesisSet):
            slot = candidate_set_or_candidates.slot_name
            target_entity = candidate_set_or_candidates.entity_id
            candidates = list(candidate_set_or_candidates.active_candidates)
            set_id = f"set_{slot}_{target_entity}"
        else:
            candidates = list(candidate_set_or_candidates)
            slot = slot_name or (candidates[0].slot_name if candidates else "unknown.slot")
            target_entity = entity_id
            set_id = f"set_{slot}_{target_entity}_{str(uuid.uuid4())[:8]}"

        viable: list[CandidateHypothesis] = []
        excluded: list[tuple[str, str]] = []
        plausibility_scores: dict[str, float] = {}

        # 1. Viability Filtering
        for cand in candidates:
            # Check 1: Quarantine
            if cand.is_quarantined:
                reason = cand.quarantine_reason or "Candidate is quarantined"
                excluded.append((cand.candidate_id, f"QUARANTINED: {reason}"))
                continue

            # Check 2: Absolute immunity of USER_LOCKED core facts
            if core and core.is_locked(cand.slot_name):
                locked_fact = core.get_fact(cand.slot_name)
                if locked_fact and locked_fact.value != cand.proposed_value:
                    excluded.append((
                        cand.candidate_id,
                        f"USER_LOCK_CONFLICT: Fact '{cand.slot_name}' is locked with value '{locked_fact.value}'.",
                    ))
                    continue

            # Check 3: Consistency with core facts
            consistency_res = ConsistencyValidator.validate(cand.slot_name, cand.proposed_value, core=core)
            if not consistency_res.is_valid:
                excluded.append((cand.candidate_id, f"CONSISTENCY_VIOLATION: {consistency_res.reason}"))
                continue

            # Check 4: Timeline validation
            # Convert CandidateHypothesis to temporary CandidateFact for TimelineValidator compatibility
            temp_fact = CandidateFact(
                id=cand.candidate_id,
                fact_key=cand.slot_name,
                value=cand.proposed_value,
            )
            timeline_res = TimelineValidator.validate(temp_fact, core=core)
            if not timeline_res.is_valid:
                excluded.append((cand.candidate_id, f"TIMELINE_VIOLATION: {timeline_res.reason}"))
                continue

            # Check 5: Causality validation
            causality_res = CausalityValidator.validate(temp_fact)
            if not causality_res.is_valid:
                excluded.append((cand.candidate_id, f"CAUSALITY_VIOLATION: {causality_res.reason}"))
                continue

            # Candidate passed all viability checks
            viable.append(cand)

            # Compute adjusted plausibility with Occam complexity penalty
            base_plausibility = cand.plausibility.composite_plausibility_score
            occam_penalty = self.config.occam_penalty_per_depth * cand.inference_depth
            adjusted_plausibility = round(max(0.0, min(1.0, base_plausibility - occam_penalty)), 4)
            plausibility_scores[cand.candidate_id] = adjusted_plausibility

        # 2. Plausibility Ranking & Decision Margin Calculation
        if not viable:
            return CompetitionResult(
                slot_name=slot,
                entity_id=target_entity,
                candidate_set_id=set_id,
                viable_candidates=(),
                excluded_candidates=tuple(excluded),
                plausibility_scores={},
                leading_candidate_id=None,
                runner_up_candidate_id=None,
                decision_margin=0.0,
                is_ambiguous=False,
                competition_state=CompetitionState.NO_VIABLE_CANDIDATES,
            )

        # Sort viable candidates by adjusted plausibility score descending
        sorted_viable = sorted(
            viable,
            key=lambda c: (plausibility_scores[c.candidate_id], -c.created_at.timestamp()),
            reverse=True,
        )

        leading = sorted_viable[0]
        leading_id = leading.candidate_id

        if len(sorted_viable) == 1:
            return CompetitionResult(
                slot_name=slot,
                entity_id=target_entity,
                candidate_set_id=set_id,
                viable_candidates=tuple(sorted_viable),
                excluded_candidates=tuple(excluded),
                plausibility_scores=plausibility_scores,
                leading_candidate_id=leading_id,
                runner_up_candidate_id=None,
                decision_margin=1.0,
                is_ambiguous=False,
                competition_state=CompetitionState.SINGLE_CANDIDATE,
            )

        runner_up = sorted_viable[1]
        runner_up_id = runner_up.candidate_id
        margin = round(
            float(plausibility_scores[leading_id] - plausibility_scores[runner_up_id]),
            4,
        )

        is_ambiguous = margin < self.config.ambivalence_threshold
        state = (
            CompetitionState.UNDETERMINED_AMBIVALENCE
            if is_ambiguous
            else CompetitionState.CLEAR_LEADER
        )

        return CompetitionResult(
            slot_name=slot,
            entity_id=target_entity,
            candidate_set_id=set_id,
            viable_candidates=tuple(sorted_viable),
            excluded_candidates=tuple(excluded),
            plausibility_scores=plausibility_scores,
            leading_candidate_id=leading_id,
            runner_up_candidate_id=runner_up_id,
            decision_margin=margin,
            is_ambiguous=is_ambiguous,
            competition_state=state,
        )
