"""Emotion transition evaluator for Aevum Core.

Provides a pure, deterministic, side-effect free evaluation of emotional transition proposals:
"Application state owns reality.
 Emotion evaluation proposes a possible next state.
 Persistence/application happens in a later phase."

Guarantees:
- Pure & deterministic: No random numbers, identical inputs always yield identical proposals.
- Synchronous & side-effect free: No database, no network, no LLM, no state mutations.
- Input immutability: Does not mutate EmotionState, EmotionInfluence, or input collections.
- Single dominant emotion: Operates strictly within Aevum's single-dominant-emotion architecture.
  Negative influences targeting different emotions are non-actionable (documented & traced).
- Bounded adjustments: Total current-emotion adjustment capped at +/-0.30 per evaluation.
- Bounded competing switch: Minimum switch threshold 0.20, switch intensity bounded [0.40, 0.90].
  Comparison baseline for competing switches is positive current pressure, preventing negative
  pressure from artificially lowering the threshold.
"""

from collections.abc import Sequence
from typing import Optional

from app.emotion.emotion_models import EmotionState, EmotionType
from app.emotion.influence_models import EmotionInfluence, EmotionInfluenceDirection
from app.emotion.transition_models import EmotionTransitionProposal

MAX_TRANSITION_MAGNITUDE_PER_EVALUATION: float = 0.30
COMPETING_SWITCH_THRESHOLD: float = 0.20
MIN_SWITCH_INTENSITY: float = 0.40
MAX_SWITCH_INTENSITY: float = 0.90

REASON_NO_ACTIONABLE_INFLUENCE: str = "No actionable emotion influence was present."
REASON_COMPETING_SWITCH: str = "Strong competing positive influence proposed a dominant-emotion switch."
REASON_POSITIVE_INCREASE: str = "Positive influence increased current emotion intensity."
REASON_NEGATIVE_REDUCTION: str = "Negative influence reduced current emotion intensity."
REASON_BALANCED_NO_CHANGE: str = "Current emotion influences balanced out with no net change."


class EmotionTransitionEvaluator:
    """Pure, deterministic evaluator that computes an EmotionTransitionProposal."""

    @classmethod
    def evaluate(
        cls,
        current_state: EmotionState,
        influences: Optional[Sequence[EmotionInfluence]] = None,
    ) -> EmotionTransitionProposal:
        """Evaluate a sequence of emotion influences against the current emotion state.

        Args:
            current_state: Current authoritative EmotionState (unmutated).
            influences: Zero or more EmotionInfluence domain models (unmutated).

        Returns:
            An immutable EmotionTransitionProposal containing the proposed next state.
        """
        if not isinstance(current_state, EmotionState):
            raise TypeError(f"current_state must be an EmotionState instance, got {type(current_state).__name__}.")

        raw_influences: list[EmotionInfluence] = []
        if influences is not None:
            for item in influences:
                if not isinstance(item, EmotionInfluence):
                    raise TypeError(f"Every item in influences must be an EmotionInfluence, got {type(item).__name__}.")
                raw_influences.append(item)

        # 1. Traceability: Collect considered influence IDs preserving input order
        considered_ids: list[str] = list(dict.fromkeys(inf.id for inf in raw_influences))

        # 2. Categorization
        positive_current: list[EmotionInfluence] = []
        negative_current: list[EmotionInfluence] = []
        positive_competing: list[EmotionInfluence] = []
        # Note: Negative competing influences (inf.direction == NEGATIVE and inf.target_emotion != current_state.emotion_type)
        # are non-actionable in the current single-dominant-emotion architecture. They are preserved in considered_ids
        # for auditing, but cannot arbitrarily invent a replacement emotion.

        for inf in raw_influences:
            if inf.target_emotion == current_state.emotion_type:
                if inf.direction == EmotionInfluenceDirection.POSITIVE:
                    positive_current.append(inf)
                elif inf.direction == EmotionInfluenceDirection.NEGATIVE:
                    negative_current.append(inf)
            else:
                if inf.direction == EmotionInfluenceDirection.POSITIVE:
                    positive_competing.append(inf)

        # 3. Calculate current emotion pressures
        positive_current_strength: float = round(sum(inf.strength for inf in positive_current), 4)
        negative_current_strength: float = round(sum(inf.strength for inf in negative_current), 4)
        net_current_delta: float = round(positive_current_strength - negative_current_strength, 4)

        adjustment: float = max(
            -MAX_TRANSITION_MAGNITUDE_PER_EVALUATION,
            min(MAX_TRANSITION_MAGNITUDE_PER_EVALUATION, net_current_delta),
        )
        new_current_intensity: float = max(
            0.0,
            min(1.0, round(current_state.intensity + adjustment, 4)),
        )

        # 4. Evaluate competing positive influences
        best_competing: Optional[EmotionInfluence] = None
        if positive_competing:
            # Deterministic ordering: highest strength first, then target_emotion alphabetically, then id alphabetically
            best_competing = min(
                positive_competing,
                key=lambda x: (-x.strength, x.target_emotion.value, x.id),
            )

        qualifies_for_switch = False
        if best_competing is not None:
            # Competing switch rule:
            # 1. Must reach or exceed activation threshold (0.20)
            # 2. Must be strictly stronger than the positive pressure supporting the current emotion
            qualifies_for_switch = (
                best_competing.strength >= COMPETING_SWITCH_THRESHOLD
                and best_competing.strength > positive_current_strength
            )

        if qualifies_for_switch and best_competing is not None:
            raw_intensity = round(MIN_SWITCH_INTENSITY + best_competing.strength * 0.50, 4)
            proposed_intensity = max(MIN_SWITCH_INTENSITY, min(MAX_SWITCH_INTENSITY, raw_intensity))
            return EmotionTransitionProposal(
                current_emotion=current_state.emotion_type,
                current_intensity=current_state.intensity,
                proposed_emotion=best_competing.target_emotion,
                proposed_intensity=proposed_intensity,
                considered_influence_ids=considered_ids,
                reason=REASON_COMPETING_SWITCH,
            )

        # 5. If no switch, evaluate current emotion adjustments
        if positive_current or negative_current:
            if net_current_delta > 0:
                reason = REASON_POSITIVE_INCREASE
            elif net_current_delta < 0:
                reason = REASON_NEGATIVE_REDUCTION
            else:
                reason = REASON_BALANCED_NO_CHANGE

            return EmotionTransitionProposal(
                current_emotion=current_state.emotion_type,
                current_intensity=current_state.intensity,
                proposed_emotion=current_state.emotion_type,
                proposed_intensity=new_current_intensity,
                considered_influence_ids=considered_ids,
                reason=reason,
            )

        # 6. Zero actionable influences (empty list, competing influences < threshold or <= current positive, or negative competing only)
        return EmotionTransitionProposal(
            current_emotion=current_state.emotion_type,
            current_intensity=current_state.intensity,
            proposed_emotion=current_state.emotion_type,
            proposed_intensity=current_state.intensity,
            considered_influence_ids=considered_ids,
            reason=REASON_NO_ACTIONABLE_INFLUENCE,
        )


def evaluate_emotion_transition(
    current_state: EmotionState,
    influences: Optional[Sequence[EmotionInfluence]] = None,
) -> EmotionTransitionProposal:
    """Convenience functional wrapper around EmotionTransitionEvaluator.evaluate."""
    return EmotionTransitionEvaluator.evaluate(current_state, influences)
