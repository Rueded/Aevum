from pydantic import BaseModel, Field

from app.llm.base import ChatMessage


class LLMContext(BaseModel):
    """Provider-neutral LLM context representation.

    Serves as the structural boundary between Aevum Core application state
    and downstream LLM providers. Encapsulates conversation history and explicit
    system instructions without exposing character state or model-specific formats.
    """

    messages: list[ChatMessage] = Field(
        default_factory=list,
        description="Chronological list of conversation messages.",
    )
    system_instructions: list[str] = Field(
        default_factory=list,
        description="Explicit system or contextual instructions.",
    )
