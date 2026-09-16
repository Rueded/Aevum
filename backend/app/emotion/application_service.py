"""Emotion state application service for Aevum Core.

Applies a validated EmotionTransitionProposal to authoritative persistent EmotionState:
"Application state owns reality.
 Emotion evaluation proposes a possible next state.
 Persistence/application happens in a later phase."

Guarantees:
- Explicit boundary: Only this service converts an EmotionTransitionProposal into an authoritative state mutation.
- Stale proposal rejection: Rejects proposals whose current_emotion or current_intensity does not match authoritative state.
- Optimistic concurrency control: Reuses EmotionService version verification to prevent concurrent overwrite.
- No-op efficiency: Proposals with no change return changed=False without database mutations or version increments.
- Pure state mutation: Exactly applies proposal values without hidden modifiers, heuristics, or external side-effects.
- Reuses existing storage: Leverages EmotionService without adding tables or duplicating CRUD logic.
"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import utc_now
from app.emotion.application_models import EmotionStateApplicationResult
from app.emotion.emotion_models import DEFAULT_CHARACTER_ID, EmotionState, EmotionType
from app.emotion.service import EmotionService
from app.emotion.transition_models import EmotionTransitionProposal

logger = logging.getLogger(__name__)


class StaleEmotionTransitionProposalError(Exception):
    """Raised when an EmotionTransitionProposal cannot be applied because its current state does not match authoritative EmotionState."""

    def __init__(
        self,
        expected_emotion: EmotionType,
        actual_emotion: EmotionType,
        expected_intensity: float,
        actual_intensity: float,
    ) -> None:
        self.expected_emotion = expected_emotion
        self.actual_emotion = actual_emotion
        self.expected_intensity = expected_intensity
        self.actual_intensity = actual_intensity
        super().__init__(
            f"Stale emotion transition proposal: proposal current state was "
            f"({expected_emotion.value}, {expected_intensity}), but authoritative state is "
            f"({actual_emotion.value}, {actual_intensity}). Proposal was calculated from an older "
            f"emotion state and must not overwrite newer state."
        )


class EmotionStateApplicationService:
    """Service that validates and applies EmotionTransitionProposal to authoritative EmotionState."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._emotion_service = EmotionService(session)

    async def apply_proposal(
        self,
        current_state: EmotionState,
        proposal: EmotionTransitionProposal,
    ) -> EmotionStateApplicationResult:
        """Apply an EmotionTransitionProposal against an authoritative EmotionState.

        Args:
            current_state: Authoritative EmotionState against which proposal is validated.
            proposal: The proposed state transition to apply.

        Returns:
            EmotionStateApplicationResult detailing previous and applied state, and whether mutation occurred.

        Raises:
            TypeError: If arguments are not of the expected domain types.
            StaleEmotionTransitionProposalError: If proposal's current state mismatches authoritative state.
            EmotionConflictError: If database-level optimistic concurrency check fails.
        """
        if not isinstance(current_state, EmotionState):
            raise TypeError(f"current_state must be an EmotionState instance, got {type(current_state).__name__}.")
        if not isinstance(proposal, EmotionTransitionProposal):
            raise TypeError(f"proposal must be an EmotionTransitionProposal instance, got {type(proposal).__name__}.")

        # 1. Stale proposal verification
        emotion_matches = proposal.current_emotion == current_state.emotion_type
        intensity_matches = abs(proposal.current_intensity - current_state.intensity) < 1e-4

        if not (emotion_matches and intensity_matches):
            raise StaleEmotionTransitionProposalError(
                expected_emotion=proposal.current_emotion,
                actual_emotion=current_state.emotion_type,
                expected_intensity=proposal.current_intensity,
                actual_intensity=current_state.intensity,
            )

        # 2. No-op detection
        is_no_op = (
            proposal.proposed_emotion == current_state.emotion_type
            and abs(proposal.proposed_intensity - current_state.intensity) < 1e-4
        )

        if is_no_op:
            logger.debug(
                "EmotionTransitionProposal for character '%s' is a no-op (%s, %.2f); skipping state mutation.",
                current_state.character_id,
                current_state.emotion_type.value,
                current_state.intensity,
            )
            return EmotionStateApplicationResult(
                previous_emotion=current_state.emotion_type,
                previous_intensity=current_state.intensity,
                applied_emotion=current_state.emotion_type,
                applied_intensity=current_state.intensity,
                changed=False,
            )

        # 3. Changed proposal application
        candidate = EmotionState(
            id=current_state.id,
            character_id=current_state.character_id,
            emotion_type=proposal.proposed_emotion,
            intensity=proposal.proposed_intensity,
            created_at=current_state.created_at,
            updated_at=utc_now(),
            version=current_state.version + 1,
        )

        await self._emotion_service.update_emotion_state(
            updated_state=candidate,
            expected_version=current_state.version,
            character_id=current_state.character_id,
        )

        logger.info(
            "Applied emotion transition for character '%s': (%s, %.2f) -> (%s, %.2f)",
            current_state.character_id,
            current_state.emotion_type.value,
            current_state.intensity,
            proposal.proposed_emotion.value,
            proposal.proposed_intensity,
        )

        return EmotionStateApplicationResult(
            previous_emotion=current_state.emotion_type,
            previous_intensity=current_state.intensity,
            applied_emotion=proposal.proposed_emotion,
            applied_intensity=proposal.proposed_intensity,
            changed=True,
        )

    async def apply_proposal_to_character(
        self,
        proposal: EmotionTransitionProposal,
        character_id: str = DEFAULT_CHARACTER_ID,
    ) -> EmotionStateApplicationResult:
        """Load authoritative state for character, validate proposal, and apply mutation atomically."""
        current_state = await self._emotion_service.get_emotion_state(character_id=character_id)
        return await self.apply_proposal(current_state=current_state, proposal=proposal)


async def apply_emotion_transition_proposal(
    session: AsyncSession,
    current_state: EmotionState,
    proposal: EmotionTransitionProposal,
) -> EmotionStateApplicationResult:
    """Convenience helper to apply an EmotionTransitionProposal to authoritative EmotionState."""
    service = EmotionStateApplicationService(session)
    return await service.apply_proposal(current_state=current_state, proposal=proposal)
