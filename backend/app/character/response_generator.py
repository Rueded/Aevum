"""Response generation service for Aevum Core.

Phase 6.2 — Response Generation Foundation.
Connects CharacterResponseContext to LLMProvider to synthesize assistant dialogue.
"""

from collections.abc import Sequence
import logging
from typing import Optional

from app.character.conversational_parser import ConversationalResponseParser
from app.character.engine_models import CharacterResponseContext
from app.character.integrity import DEFAULT_FALLBACK_SPEECH, OutputBoundaryGuard
from app.character.prompt_assembler import ResponseContextAssembler
from app.character.response_models import CharacterResponse
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

        Args:
            context: The authoritative CharacterResponseContext gathered by CharacterEngine.
            conversation_history: Optional prior conversation turns.

        Returns:
            An immutable CharacterResponse.

        Raises:
            ValueError: If context is invalid.
            LLMGenerationError: If LLM generation produces empty content or upstream failure.
            LLMProviderNotConfiguredError: If provider lacks API configuration.
            LLMError: Any other provider-level errors.
        """
        if not isinstance(context, CharacterResponseContext):
            raise ValueError("context must be an instance of CharacterResponseContext.")

        llm_context = ResponseContextAssembler.assemble(
            context=context,
            conversation_history=conversation_history,
        )

        llm_response = await self.provider.generate_response(llm_context)

        raw_content = (llm_response.content or "").strip()
        if not raw_content:
            raise LLMGenerationError("Upstream provider returned empty response content.")

        parsed_turn = ConversationalResponseParser.parse(raw_content)

        clean_speech = OutputBoundaryGuard.verify_and_clean(
            raw_text=raw_content,
            character_name=context.character.name,
        )

        is_fallback = clean_speech == DEFAULT_FALLBACK_SPEECH
        decision = None if is_fallback else parsed_turn.decision
        bubbles = [clean_speech] if is_fallback else (
            ConversationalResponseParser.extract_bubbles(clean_speech) or [clean_speech]
        )

        return CharacterResponse(
            content=clean_speech,
            character_name=context.character.name,
            raw_metadata=llm_response.raw_response,
            decision=decision,
            speech_bubbles=bubbles,
        )
