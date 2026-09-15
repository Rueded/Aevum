from abc import ABC, abstractmethod
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Provider-neutral representation of a conversation message."""

    role: str = Field(
        ...,
        description="Neutral role: 'user', 'assistant', or 'system'.",
    )
    content: str = Field(
        ...,
        description="Text content of the message.",
    )


class LLMPromptContext(BaseModel):
    """Grounded context passed to an LLM provider for natural language synthesis."""

    system_instruction: str = Field(
        ...,
        description="Ground truth persona and behavioral constraints from Aevum Core.",
    )
    user_message: str = Field(
        ...,
        description="The latest input message from the user.",
    )
    grounded_state: dict = Field(
        default_factory=dict,
        description="Deterministic character state (mood, relationship, current activity).",
    )


class LLMResponse(BaseModel):
    """Structured response synthesized by an LLM provider."""

    content: str = Field(
        ...,
        description="The synthesized dialogue text.",
    )
    raw_response: dict | None = Field(
        default=None,
        description="Optional raw provider metadata (e.g. usage, finish reason).",
    )


class LLMError(Exception):
    """Base exception for all LLM provider errors."""

    pass


class LLMProviderNotConfiguredError(LLMError):
    """Raised when an LLM provider is requested but lacks necessary configuration (e.g. API key)."""

    pass


class LLMGenerationError(LLMError):
    """Raised when an upstream LLM API call fails or returns an invalid/empty response."""

    pass


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.llm.context import LLMContext


class LLMProvider(ABC):
    """Abstract base class for all language model providers in Aevum Core.

    Concrete implementations (e.g. GeminiProvider) encapsulate SDK-specific details,
    allowing Aevum Core to remain completely agnostic of the underlying model provider.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique identifier of the LLM provider."""
        pass

    @abstractmethod
    async def generate_response(
        self,
        context: "LLMContext",
    ) -> LLMResponse:
        """Synthesize dialogue from the provided LLMContext without altering application state.

        Args:
            context: Provider-neutral LLMContext containing messages and system instructions.

        Returns:
            LLMResponse containing synthesized text.

        Raises:
            LLMProviderNotConfiguredError: If provider credentials are missing.
            LLMGenerationError: If the upstream provider call fails or returns empty content.
        """
        pass

    async def generate_structured(
        self,
        context: "LLMContext",
        response_schema: type[BaseModel] | None = None,
    ) -> str:
        """Generate structured text (e.g. JSON) adhering to an optional schema.

        Default implementation falls back to generate_response(context) content.
        Concrete providers may override this to utilize native structured generation.
        """
        response = await self.generate_response(context)
        return response.content


