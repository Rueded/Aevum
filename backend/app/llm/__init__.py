"""LLM Provider package."""

from app.core.config import settings
from app.llm.base import (
    ChatMessage,
    LLMError,
    LLMGenerationError,
    LLMPromptContext,
    LLMProvider,
    LLMProviderNotConfiguredError,
    LLMResponse,
)
from app.llm.context import LLMContext
from app.llm.context_builder import build_context
from app.llm.gemini import GeminiProvider


def get_llm_provider() -> LLMProvider:
    """Dependency provider returning the configured LLM provider instance."""
    provider_name = (settings.llm_provider or "gemini").lower()
    if provider_name == "gemini":
        return GeminiProvider()
    raise LLMProviderNotConfiguredError(f"Unsupported LLM provider '{provider_name}'.")


__all__ = [
    "ChatMessage",
    "GeminiProvider",
    "LLMContext",
    "LLMError",
    "LLMGenerationError",
    "LLMPromptContext",
    "LLMProvider",
    "LLMProviderNotConfiguredError",
    "LLMResponse",
    "build_context",
    "get_llm_provider",
]
