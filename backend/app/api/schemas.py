from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from typing import Literal, Optional

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
    speech_bubbles: Optional[list[str]] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("created_at")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            from datetime import timezone
            return v.replace(tzinfo=timezone.utc)
        return v

    @model_validator(mode="after")
    def populate_speech_bubbles(self) -> "MessageRead":
        if (self.speech_bubbles is None or len(self.speech_bubbles) == 0) and self.role == "assistant" and self.content:
            from app.character.conversational_parser import ConversationalResponseParser
            self.speech_bubbles = ConversationalResponseParser.extract_bubbles(self.content)
        return self


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
    reply_delay_seconds: float = Field(
        default=0.0,
        description="Recommended display delay in seconds reflecting character's life activity (Phase 5 §8.6).",
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


class ConversationListItem(BaseModel):
    """Schema for a conversation list summary item."""

    id: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    last_message_preview: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Phase 10: Voice & Audio Schemas
# =============================================================================


class VoiceMessageCreate(BaseModel):
    """Schema for submitting spoken audio input to a conversation (ADR-021)."""

    audio_base64: str = Field(..., description="Base64 encoded audio payload.")
    format: str = Field(default="WAV", description="Audio format (WAV, MP3, OGG_OPUS).")
    sample_rate_hz: int = Field(default=16000, description="Sampling rate in Hz.")
    channels: str = Field(default="MONO", description="Audio channel count (MONO, STEREO).")
    duration_ms: int = Field(default=0, description="Duration in milliseconds.")
    user_consent_granted: bool = Field(..., description="Rule 18 microphone consent verification.")
    input_mode: str = Field(default="PTT", description="Capture mode. Strictly PTT in Phase 10.")
    synthesize_reply_audio: bool = Field(
        default=True,
        description="Whether to synthesize companion spoken reply audio.",
    )
    voice_id: str | None = Field(
        default=None,
        description="Optional voice profile ID for reply synthesis.",
    )


class VoiceMessageResponse(BaseModel):
    """Response returned from a voice-driven conversational turn."""

    message: MessageRead = Field(..., description="Persisted user message with transcribed content.")
    transcribed_text: str = Field(..., description="Recognized speech text.")
    assistant_response: MessageRead | None = Field(
        default=None,
        description="Persisted assistant reply message.",
    )
    assistant_status: str = Field(
        default="generated",
        description="Assistant text generation status.",
    )
    audio_data_base64: str | None = Field(
        default=None,
        description="Base64 encoded synthesized audio, if synthesized.",
    )
    audio_cache_key: str | None = Field(
        default=None,
        description="Canonical audio cache key for audio streaming/playback.",
    )
    audio_status: str = Field(
        default="skipped",
        description="Audio synthesis status ('success', 'failed', 'unavailable', 'skipped').",
    )


class VoiceTTSRequest(BaseModel):
    """Schema for standalone text-to-speech synthesis."""

    text: str = Field(..., description="Text content to synthesize.")
    voice_id: str | None = Field(default=None, description="Target voice profile ID.")
    desired_format: str = Field(default="WAV", description="Audio format.")
    epistemic_cue: str = Field(default="CERTAIN", description="Epistemic certainty cue.")
    character_id: str = Field(default="aevum", description="Character ID for emotional context.")


class VoiceTTSResponse(BaseModel):
    """Response from standalone text-to-speech synthesis."""

    status: str = Field(..., description="Synthesis status.")
    audio_base64: str | None = Field(default=None, description="Base64 encoded audio bytes.")
    cache_key: str | None = Field(default=None, description="Canonical audio cache key.")
    duration_ms: int = Field(default=0, description="Audio duration in ms.")
    error_message: str | None = Field(default=None, description="Diagnostic error message.")


class VoiceSTTRequest(BaseModel):
    """Schema for standalone speech-to-text transcription."""

    audio_base64: str = Field(..., description="Base64 encoded audio payload.")
    format: str = Field(default="WAV", description="Audio format.")
    sample_rate_hz: int = Field(default=16000, description="Sampling rate in Hz.")
    channels: str = Field(default="MONO", description="Audio channels.")
    duration_ms: int = Field(default=0, description="Duration in ms.")
    user_consent_granted: bool = Field(..., description="Rule 18 microphone consent.")
    input_mode: str = Field(default="PTT", description="Input mode.")


class VoiceSTTResponse(BaseModel):
    """Response from standalone speech-to-text transcription."""

    status: str = Field(..., description="Transcription status.")
    transcribed_text: str | None = Field(default=None, description="Recognized transcript.")
    error_message: str | None = Field(default=None, description="Diagnostic error message.")

