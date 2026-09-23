"""Choice Selection Service for Project Aevum (Phase 7D.2).

Responsibilities:
- First-class domain operation for Character Choice / Outcome Selection.
- Decouples Plausibility from Choice (Plausibility != Probability != Choice != Promotion).
- Multi-attribute evaluation: Plausibility, Temperament, Values, Challenge,
  Resources, Timeline, Opportunity Cost, and Time Cost.
- Enforces GC-066: Candidate with lower plausibility can be chosen if structured
  character factors justify it.
- Enforces GC-068: Competition ambiguity (Δ < 0.10) != Choice impossibility.
- Enforces GC-067: Unselected viable alternatives are preserved as
  CONSIDERED_BUT_NOT_SELECTED with complete structured provenance.
- STRICT INVARIANT: Selected outcome remains NON-CANONICAL (zero modification of core facts).
- STRICT INVARIANT: Anti-Snowballing (zero biographical spillover into ancillary facts).
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
import uuid

if TYPE_CHECKING:
    from app.character.bible_models import CharacterBible
    from app.character.core_models import CharacterCore
from app.character.bible_service import CharacterBibleService
from app.reality.candidate_models import (
    CandidateHypothesis,
    CandidateLifecycleState,
)
from app.reality.choice_models import (
    ChoiceConfig,
    ChoiceDecisionResult,
    ChoiceFactorBreakdown,
    ChoiceRationaleCode,
    CompetitionResult,
    CompetitionState,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ChoiceSelectionService:
    """Evaluates character choice among competing viable candidates using multi-attribute factors."""

    def __init__(self, config: Optional[ChoiceConfig] = None) -> None:
        self.config = config or ChoiceConfig()

    def calculate_choice_score(
        self,
        factors: ChoiceFactorBreakdown,
    ) -> tuple[float, dict[str, float]]:
        """Compute deterministic ChoiceScore and individual factor contributions.
        
        Formula:
        ChoiceScore = (
            w_plausibility * plausibility
            + w_temperament * temperament_fit
            + w_values * values_alignment
            + w_challenge * challenge_preference
            + w_resources * resource_compatibility
            + w_timeline * timeline_compatibility
            - w_opportunity * opportunity_cost
            - w_time_cost * time_cost
        )
        """
        c = self.config
        contribs = {
            "plausibility": round(c.w_plausibility * factors.plausibility_score, 4),
            "temperament": round(c.w_temperament * factors.temperament_fit, 4),
            "values": round(c.w_values * factors.values_alignment, 4),
            "challenge": round(c.w_challenge * factors.challenge_preference, 4),
            "resources": round(c.w_resources * factors.resource_compatibility, 4),
            "timeline": round(c.w_timeline * factors.timeline_compatibility, 4),
            "opportunity_penalty": round(-c.w_opportunity * factors.opportunity_cost, 4),
            "time_penalty": round(-c.w_time_cost * factors.time_cost, 4),
        }
        total_score = round(sum(contribs.values()), 4)
        return total_score, contribs

    def select_choice(
        self,
        competition_result: CompetitionResult,
        factor_inputs_by_candidate: Optional[dict[str, ChoiceFactorBreakdown]] = None,
        core: Optional["CharacterCore"] = None,
        bible: Optional["CharacterBible"] = None,
        rationale_override: Optional[str] = None,
    ) -> ChoiceDecisionResult:
        """Select an outcome from viable competing candidates.
        
        Strict Invariants:
        - Output is strictly non-canonical.
        - Unselected viable candidates are transitioned to CONSIDERED_BUT_NOT_SELECTED.
        - Plausibility != Choice: choice is governed by ChoiceScore, never blindly highest plausibility.
        - Preserves complete structured provenance for all evaluated options.
        """
        decision_id = f"dec_{uuid.uuid4()}"
        slot = competition_result.slot_name
        entity_id = competition_result.entity_id
        set_id = competition_result.candidate_set_id
        character_bible = bible or CharacterBibleService.get_bible()

        viable = list(competition_result.viable_candidates)
        candidate_ids = tuple(c.candidate_id for c in viable)

        # 1. Edge Case: No viable candidates
        if not viable:
            return ChoiceDecisionResult(
                decision_id=decision_id,
                entity_id=entity_id,
                slot_name=slot,
                candidate_set_id=set_id,
                candidate_ids_considered=(),
                selected_candidate_id=None,
                unselected_candidate_ids=(),
                selected_candidate=None,
                archived_unselected_candidates=(),
                competition_state=competition_result.competition_state,
                competition_margin=competition_result.decision_margin,
                plausibility_scores={},
                factor_inputs={},
                factor_contributions={},
                choice_scores={},
                choice_margin=0.0,
                rationale_code=ChoiceRationaleCode.NO_VIABLE_CANDIDATES,
                rationale_description="No viable candidates survived validation constraints.",
                is_non_canonical=True,
                provenance_references=(),
            )

        # 2. Multi-Attribute Factor Scoring
        factor_inputs: dict[str, dict[str, float]] = {}
        factor_contributions: dict[str, dict[str, float]] = {}
        choice_scores: dict[str, float] = {}
        input_factors_map = factor_inputs_by_candidate or {}

        for cand in viable:
            cid = cand.candidate_id
            plaus_score = competition_result.plausibility_scores.get(
                cid,
                cand.plausibility.composite_plausibility_score,
            )

            # Retrieve explicit factors or fallback to sensible default based on candidate
            if cid in input_factors_map:
                breakdown = input_factors_map[cid]
            elif cand.selection_metadata and "factor_inputs" in cand.selection_metadata:
                breakdown = ChoiceFactorBreakdown(**cand.selection_metadata["factor_inputs"])
            else:
                # Default baseline factors grounded in candidate plausibility
                breakdown = ChoiceFactorBreakdown(
                    plausibility_score=plaus_score,
                    temperament_fit=0.5,
                    values_alignment=0.5,
                    challenge_preference=0.5,
                    resource_compatibility=0.5,
                    timeline_compatibility=0.5,
                    opportunity_cost=0.0,
                    time_cost=0.0,
                )

            # Ensure plausibility_score aligns with adjusted plausibility from competition
            breakdown = breakdown.model_copy(update={"plausibility_score": plaus_score})
            score, contribs = self.calculate_choice_score(breakdown)

            factor_inputs[cid] = breakdown.model_dump()
            factor_contributions[cid] = contribs
            choice_scores[cid] = score

        # 3. Choice Outcome Resolution
        sorted_candidates = sorted(
            viable,
            key=lambda c: (choice_scores[c.candidate_id], -c.created_at.timestamp()),
            reverse=True,
        )

        selected_cand = sorted_candidates[0]
        selected_id = selected_cand.candidate_id
        top_choice_score = choice_scores[selected_id]

        choice_margin: float = 1.0
        rationale_code: ChoiceRationaleCode = ChoiceRationaleCode.MULTI_FACTOR_BALANCED

        if len(sorted_candidates) > 1:
            runner_up_cand = sorted_candidates[1]
            runner_up_id = runner_up_cand.candidate_id
            runner_up_choice_score = choice_scores[runner_up_id]
            choice_margin = round(float(top_choice_score - runner_up_choice_score), 4)

            # Check if Choice factors themselves are tied below margin
            if choice_margin < self.config.choice_ambivalence_margin:
                rationale_code = ChoiceRationaleCode.CHOICE_AMBIVALENCE
            elif competition_result.is_ambiguous:
                # Plausibility was ambiguous, but Choice factors resolved the outcome!
                rationale_code = ChoiceRationaleCode.AMBIVALENCE_RESOLVED
            else:
                # Determine dominant factor
                sel_contribs = factor_contributions[selected_id]
                temp_c = sel_contribs.get("temperament", 0.0)
                val_c = sel_contribs.get("values", 0.0)
                chal_c = sel_contribs.get("challenge", 0.0)
                res_c = sel_contribs.get("resources", 0.0)

                max_factor = max(temp_c, val_c, chal_c, res_c)
                if max_factor == temp_c:
                    rationale_code = ChoiceRationaleCode.TEMPERAMENT_ALIGNMENT
                elif max_factor == val_c:
                    rationale_code = ChoiceRationaleCode.VALUES_ALIGNMENT
                elif max_factor == chal_c:
                    rationale_code = ChoiceRationaleCode.CHALLENGE_PREFERENCE
                elif max_factor == res_c:
                    rationale_code = ChoiceRationaleCode.RESOURCE_OPTIMAL
                else:
                    rationale_code = ChoiceRationaleCode.MULTI_FACTOR_BALANCED

        # 4. State Transitions
        # Selected candidate transitions to PROMOTABLE (awaiting promotion gate in 7D.3)
        promotable_selected = selected_cand.to_promotable()

        # Unselected candidates transition to CONSIDERED_BUT_NOT_SELECTED
        archived_unselected: list[CandidateHypothesis] = []
        unselected_ids: list[str] = []

        for cand in sorted_candidates[1:]:
            cid = cand.candidate_id
            unselected_ids.append(cid)
            non_sel_reason = (
                f"Alternative candidate '{selected_id}' achieved higher ChoiceScore "
                f"({top_choice_score:.4f} vs {choice_scores[cid]:.4f})."
            )
            archived = cand.to_considered_but_not_selected(
                reason=non_sel_reason,
                selected_candidate_id=selected_id,
                choice_score=choice_scores[cid],
                factor_inputs=factor_inputs.get(cid),
            )
            archived_unselected.append(archived)

        # 5. Formulate Human-Auditable Rationale
        if rationale_override:
            explanation = rationale_override
        else:
            explanation = (
                f"Selected '{selected_cand.proposed_value}' for slot '{slot}' "
                f"with ChoiceScore {top_choice_score:.4f} (margin: {choice_margin:.4f}). "
                f"Rationale: {rationale_code.value}. "
                f"Evaluated {len(viable)} candidate alternatives."
            )

        # Collect provenance references
        all_prov_refs: set[str] = set()
        for cand in viable:
            all_prov_refs.add(cand.provenance.origin_id)
            for fid in cand.provenance.evidence_family_ids:
                all_prov_refs.add(fid)

        return ChoiceDecisionResult(
            decision_id=decision_id,
            entity_id=entity_id,
            slot_name=slot,
            candidate_set_id=set_id,
            candidate_ids_considered=candidate_ids,
            selected_candidate_id=selected_id,
            unselected_candidate_ids=tuple(unselected_ids),
            selected_candidate=promotable_selected,
            archived_unselected_candidates=tuple(archived_unselected),
            decision_timestamp=_utc_now(),
            decision_model_version="1.0.0",
            competition_state=competition_result.competition_state,
            competition_margin=competition_result.decision_margin,
            plausibility_scores=competition_result.plausibility_scores,
            factor_inputs=factor_inputs,
            factor_contributions=factor_contributions,
            choice_scores=choice_scores,
            choice_margin=choice_margin,
            rationale_code=rationale_code,
            rationale_description=explanation,
            is_non_canonical=True,
            provenance_references=tuple(sorted(all_prov_refs)),
        )
