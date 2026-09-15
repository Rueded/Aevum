from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator

from typing import Literal

from app.db.models import MessageRole


class MessageCreate(BaseModel):
    """Schema for adding a message to a conversation.

    Clients may only submit messages with role 'user' to prevent arbitrary state injection.
    """

    role: Literal["user"] = Field(
        default="user",
        description="Role of the client message author. Strictly constrained to 'user'.",
    )
    content: str = Field(
        ...,
        description="Text content of the message.",
    )


    @field_validator("content")
    @classmethod
    def validate_non_empty_content(cls, value: str) -> str:
        """Ensure message content contains non-whitespace characters."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("Message content must not be empty or whitespace only.")
        return stripped


class MessageRead(BaseModel):
    """Schema for a persisted message."""

    id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageCreateResponse(BaseModel):
    """Response returned when a message is persisted and assistant reply is processed."""

    message: MessageRead
    assistant_response: MessageRead | None = Field(
        default=None,
        description="Persisted assistant response message, or None if provider is not configured.",
    )
    assistant_status: str = Field(
        default="generated",
        description="Status indicator ('generated', 'provider_not_configured', 'failed').",
    )



class ConversationCreate(BaseModel):
    """Schema for creating a new conversation."""
    pass


class ConversationRead(BaseModel):
    """Schema for conversation metadata."""

    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationDetailRead(ConversationRead):
    """Schema for conversation metadata including all persisted messages."""

    messages: list[MessageRead] = Field(default_factory=list)
