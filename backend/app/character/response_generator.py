"""Response generation service for Aevum Core.

Phase 6.2 — Response Generation Foundation.
Connects CharacterResponseContext to LLMProvider to synthesize assistant dialogue.
"""

from collections.abc import Sequence
import logging
from typing import Optional

from app.character.conversational_models import StructuredTurnOutput, TurnMessageItem
from app.character.conversational_parser import ConversationalResponseParser
from app.character.engine_models import CharacterResponseContext
from app.character.integrity import DEFAULT_FALLBACK_SPEECH, OutputBoundaryGuard
from app.character.prompt_assembler import ResponseContextAssembler
from app.character.response_models import CharacterResponse
from app.character.shape_controller import ShapeController
from app.llm.base import (
    ChatMessage,
    LLMGenerationError,
    LLMProvider,
)
from app.llm import get_llm_provider

logger = logging.getLogger(__name__)


class ResponseGenerator:
    """Provider-independent response generation service for Aevum Core."""

    def __init__(self, provider: Optional[LLMProvider] = None) -> None:
        """Initialize ResponseGenerator with an optional LLMProvider.

        If provider is omitted, get_llm_provider() is resolved on demand.
        """
        self._provider = provider

    @property
    def provider(self) -> LLMProvider:
        """Retrieve the configured LLMProvider instance."""
        if self._provider is None:
            self._provider = get_llm_provider()
        return self._provider

    async def generate_response(
        self,
        context: CharacterResponseContext,
        conversation_history: Optional[Sequence[ChatMessage]] = None,
    ) -> CharacterResponse:
        """Generate a grounded character response using the configured LLM provider.

        Phase 3: Governed by structured schema output (StructuredTurnOutput)
        and strict code-level shape control (ShapeController).
        """
        if not isinstance(context, CharacterResponseContext):
            raise ValueError("context must be an instance of CharacterResponseContext.")

        llm_context = ResponseContextAssembler.assemble(
            context=context,
            conversation_history=conversation_history,
        )

        energy_level = getattr(context.character_state, "energy", 0.7)
        emo_type = str(getattr(context.emotion, "emotion_type", "")).lower()
        is_tired = any(k in emo_type for k in ("tired", "exhaust", "sleep"))
        curiosity_active = "curious" in emo_type or getattr(context.character_state, "curiosity", False)

        try:
            llm_response = await self.provider.generate_structured_response(
                context=llm_context,
                response_schema=StructuredTurnOutput,
            )
            raw_content = (llm_response.content or "").strip()
            structured_output = StructuredTurnOutput.model_validate_json(raw_content)

            # Apply Phase 3 code-level shape transformations
            shaped_output = ShapeController.process(
                raw_output=structured_output,
                energy_level=energy_level,
                is_tired=is_tired,
                curiosity_active=curiosity_active,
            )
            bubbles = ShapeController.render_bubbles(shaped_output)
            clean_content = "\n".join(bubbles)

            # Verify through boundary guard
            clean_speech = OutputBoundaryGuard.verify_and_clean(
                raw_text=clean_content,
                character_name=context.character.name,
            )
            if clean_speech == DEFAULT_FALLBACK_SPEECH:
                bubbles = [DEFAULT_FALLBACK_SPEECH]
                clean_content = DEFAULT_FALLBACK_SPEECH
                shaped_output = StructuredTurnOutput(messages=[TurnMessageItem(type="text", text=DEFAULT_FALLBACK_SPEECH)])

            return CharacterResponse(
                content=clean_content,
                character_name=context.character.name,
                raw_metadata=llm_response.raw_response,
                decision=None,
                speech_bubbles=bubbles,
                structured_messages=[m.model_dump() for m in shaped_output.messages],
            )
        except Exception as structured_err:
            logger.warning("Structured generation or parsing failed (%s), falling back to raw generation...", structured_err)
            llm_response = await self.provider.generate_response(llm_context)
            raw_content = (llm_response.content or "").strip()
            if not raw_content:
                raise LLMGenerationError("Upstream provider returned empty response content.")

            clean_speech = OutputBoundaryGuard.verify_and_clean(
                raw_text=raw_content,
                character_name=context.character.name,
            )
            is_fallback = clean_speech == DEFAULT_FALLBACK_SPEECH
            bubbles = [clean_speech] if is_fallback else (
                ConversationalResponseParser.extract_bubbles(clean_speech) or [clean_speech]
            )
            return CharacterResponse(
                content=clean_speech,
                character_name=context.character.name,
                raw_metadata=llm_response.raw_response,
                decision=None,
                speech_bubbles=bubbles,
            )
