from collections.abc import Sequence

from app.llm.base import ChatMessage
from app.llm.context import LLMContext


def build_context(
    messages: Sequence[ChatMessage],
    system_instructions: Sequence[str] | None = None,
) -> LLMContext:
    """Construct a provider-neutral LLMContext from conversation messages and optional instructions.

    Guarantees:
      - Preserves chronological order of messages.
      - Preserves message roles and content.
      - Never mutates the caller's input sequence.
      - Keeps system instructions separate from ordinary messages.
      - Defaults to empty system instructions (no hardcoded personality/system prompt).
      - Completely agnostic of concrete LLM providers and SDKs.

    Args:
        messages: Sequence of provider-neutral ChatMessage objects.
        system_instructions: Optional sequence of explicit system instructions.

    Returns:
        Structured, immutable-by-convention LLMContext ready for provider dispatch.
    """
    # Create independent copies to prevent mutating caller's collection
    copied_messages: list[ChatMessage] = [
        ChatMessage(role=m.role, content=m.content)
        for m in messages
    ]

    # Clean and filter non-empty system instructions without hardcoding personality
    copied_instructions: list[str] = (
        [str(instr).strip() for instr in system_instructions if str(instr).strip()]
        if system_instructions is not None
        else []
    )

    return LLMContext(
        messages=copied_messages,
        system_instructions=copied_instructions,
    )
