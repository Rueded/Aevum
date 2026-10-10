"""Response generation domain models for Aevum Core.

Phase 6.2 — Response Generation Foundation.
"""

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.character.conversational_models import TurnConversationalDecision


class CharacterResponse(BaseModel):
    """Immutable response result produced by ResponseGenerator.

    Encapsulates synthesized dialogue text and minimal required metadata
    without leaking internal application IDs or domain state.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    content: str = Field(
        ...,
        min_length=1,
        description="The synthesized assistant dialogue text.",
    )
    character_name: str = Field(
        ...,
        min_length=1,
        description="Name of the character generating the response.",
    )
    raw_metadata: dict[str, Any] | None = Field(
        default=None,
        description="Optional provider-neutral generation metadata (e.g. usage, finish reason).",
    )
    decision: Optional[TurnConversationalDecision] = Field(
        default=None,
        description="Optional parsed TurnConversationalDecision metadata from CCDF protocol.",
    )
    speech_bubbles: list[str] = Field(
        default_factory=list,
        description="Realized conversational speech bubbles (GC-426 emergent multi-bubble).",
    )
