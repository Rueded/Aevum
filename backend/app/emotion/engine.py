"""Emotion engine for Aevum Core.

Orchestrates the internal emotion evaluation and application pipeline:
EmotionEvent
      ↓
EmotionInfluence(s)
      ↓
EmotionTransitionEvaluator (pure calculation)
      ↓
EmotionTransitionProposal (proposed transition)
      ↓
EmotionStateApplicationService (authoritative application)
      ↓
Authoritative EmotionState

Guarantees:
- Orchestration only: Contains zero emotional psychology rules (delegated to EmotionTransitionEvaluator).
- Persistence boundary: Contains zero SQL or direct persistence logic (delegated to EmotionStateApplicationService).
- Error preservation: Propagates StaleEmotionTransitionProposalError and EmotionConflictError without swallowing or retrying.
- Domain isolation: Internal emotion pipeline only; does not connect Conversation, Memory, Relationship, Life, Autonomy, or LLMs.
- Zero state mutation within engine: Delegated strictly to the application service.
"""

from collections.abc import Sequence
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.emotion.application_service import EmotionStateApplicationService
from app.emotion.emotion_models import DEFAULT_CHARACTER_ID, EmotionState
from app.emotion.engine_models import EmotionEngineResult
from app.emotion.influence_models import EmotionInfluence
from app.emotion.service import EmotionService
from app.emotion.transition_evaluator import EmotionTransitionEvaluator

logger = logging.getLogger(__name__)


class EmotionEngine:
    """Orchestrates emotion transition evaluation and authoritative state application."""

    def __init__(
        self,
        session: AsyncSession,
        application_service: Optional[EmotionStateApplicationService] = None,
    ) -> None:
        self._session = session
        self._application_service = application_service or EmotionStateApplicationService(session)
        self._emotion_service = EmotionService(session)

    async def process_influences(
        self,
        current_state: EmotionState,
        influences: Optional[Sequence[EmotionInfluence]] = None,
    ) -> EmotionEngineResult:
        """Evaluate influences against current authoritative state and apply the resulting transition.

        Args:
            current_state: The current authoritative EmotionState.
            influences: Zero or more EmotionInfluence objects to evaluate.

        Returns:
            An EmotionEngineResult containing the generated proposal and the application result.

        Raises:
            TypeError: If current_state or any influence is of an invalid type.
            StaleEmotionTransitionProposalError: If the proposal cannot be applied due to state mismatch.
            EmotionConflictError: If database optimistic concurrency fails during application.
        """
        if not isinstance(current_state, EmotionState):
            raise TypeError(f"current_state must be an EmotionState instance, got {type(current_state).__name__}.")

        raw_influences: list[EmotionInfluence] = []
        if influences is not None:
            for item in influences:
                if not isinstance(item, EmotionInfluence):
                    raise TypeError(f"Every item in influences must be an EmotionInfluence, got {type(item).__name__}.")
                raw_influences.append(item)

        # 1. Evaluate influences -> proposal (pure, synchronous calculation)
        proposal = EmotionTransitionEvaluator.evaluate(
            current_state=current_state,
            influences=raw_influences,
        )

        # 2. Apply proposal -> authoritative state (delegated to application service)
        application_result = await self._application_service.apply_proposal(
            current_state=current_state,
            proposal=proposal,
        )

        logger.debug(
            "EmotionEngine completed cycle for character '%s': proposed (%s, %.2f) -> applied (%s, %.2f, changed=%s)",
            current_state.character_id,
            proposal.proposed_emotion.value,
            proposal.proposed_intensity,
            application_result.applied_emotion.value,
            application_result.applied_intensity,
            application_result.changed,
        )

        return EmotionEngineResult(
            proposal=proposal,
            application_result=application_result,
        )

    async def process_character_influences(
        self,
        character_id: str = DEFAULT_CHARACTER_ID,
        influences: Optional[Sequence[EmotionInfluence]] = None,
    ) -> EmotionEngineResult:
        """Load current authoritative state for character, evaluate influences, and apply transition."""
        current_state = await self._emotion_service.get_emotion_state(character_id=character_id)
        return await self.process_influences(current_state=current_state, influences=influences)


async def process_emotion_influences(
    session: AsyncSession,
    current_state: EmotionState,
    influences: Optional[Sequence[EmotionInfluence]] = None,
) -> EmotionEngineResult:
    """Convenience helper to orchestrate emotion influence evaluation and state application."""
    engine = EmotionEngine(session)
    return await engine.process_influences(current_state=current_state, influences=influences)
