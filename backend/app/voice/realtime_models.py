"""Pure immutable data contracts and domain models for Realtime Voice Call & Desktop Shell (Phase 13.1).

Governed by ADR-024 (Revision 2):
- Core Axiom: Realtime is an ephemeral streaming conduit, not a reality loophole.
  Voice is the body. Live2D is the visible body. Mind remains the sole authority.
- Lock 1: Streaming Isolation & Audio != Emotion (RMS drives mouth open only, never EmotionState).
- Lock 2: Monotonic Generation & Sequence Fencing (stale response drop & packet ordering).
- Lock 3: Three-State Transcript & Double-Gated Commitment (PARTIAL -> FINAL_PENDING -> COMMITTED).
- Lock 4: Instant Client-Local Barge-In Latch (Web Audio pauses and clamps mouth to zero; P95 <= 20ms).
- Lock 5: Asymmetric Provider Failure Decoupling (TTS text fallback vs STT Zero Fake Turn).
- Lock 6: Presentation Body Singularity (Rule 19: Shell, HUD, Journey/Bond are read-only projections).
- Lock 7: Hermetic Testability (100% headless CI testability with mock streams).
- Lock 8: Canonical Conversation Boundary (Only COMMITTED turns enter persistent conversation/mind;
  zero ephemeral artifacts enter Phase 14 Reality Construction).

Implementation Watchpoint:
- AudioFrameEnvelope contains ONLY transport metadata and raw audio payload.
  Strictly NO emotion, mood, character_state, conversation_text, memory_id, or biography_id.
"""

from __future__ import annotations

import enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


# ==============================================================================
# Protocol Constants (ADR-024)
# ==============================================================================

REALTIME_PROTOCOL_VERSION: int = 1
REALTIME_SESSION_RECONNECT_LEASE_SECONDS: int = 30
DEFAULT_SAMPLE_RATE_UPSTREAM: int = 16000
DEFAULT_SAMPLE_RATE_DOWNSTREAM: int = 24000
VAD_SILENCE_COMMIT_THRESHOLD_MS: int = 600
BARGE_IN_ACCEPTANCE_TARGET_MS: int = 20


# ==============================================================================
# Categorical Enums
# ==============================================================================

class AudioDirection(str, enum.Enum):
    """Directionality of realtime audio transmission."""

    UPSTREAM_CLIENT_TO_SERVER = "UPSTREAM_CLIENT_TO_SERVER"
    DOWNSTREAM_SERVER_TO_CLIENT = "DOWNSTREAM_SERVER_TO_CLIENT"


class AudioCodec(str, enum.Enum):
    """Supported realtime audio wire codecs."""

    PCM_S16LE = "PCM_S16LE"
    OPUS = "OPUS"


class RealtimeSessionStatus(str, enum.Enum):
    """Authoritative lifecycle status for realtime call sessions."""

    INITIATED = "INITIATED"
    ACTIVE = "ACTIVE"
    RECONNECTING = "RECONNECTING"
    CLOSED = "CLOSED"
    TERMINATED = "TERMINATED"


class TranscriptLifecycleState(str, enum.Enum):
    """Three-state lifecycle of spoken text hypotheses (ADR-024 Lock 3 & Lock 8).

    - PARTIAL: Transient streaming hypothesis for UI preview only.
      NEVER stored in DB, NEVER sent to Memory, NEVER sent to Reality.
    - FINAL_PENDING_COMMIT: STT is_final=True, awaiting linguistic utterance boundary.
    - COMMITTED: Utterance boundary confirmed; double-gated; eligible to become Message.
    """

    PARTIAL = "PARTIAL"
    FINAL_PENDING_COMMIT = "FINAL_PENDING_COMMIT"
    COMMITTED = "COMMITTED"


class UserInputState(str, enum.Enum):
    """Directional state of the user's speech input within a turn."""

    PARTIAL = "PARTIAL"
    FINAL_PENDING = "FINAL_PENDING"
    COMMITTED = "COMMITTED"


class AssistantOutputState(str, enum.Enum):
    """Directional state of Aevum's spoken output within a turn."""

    NOT_STARTED = "NOT_STARTED"
    STREAMING = "STREAMING"
    COMPLETED = "COMPLETED"
    INTERRUPTED = "INTERRUPTED"


class RealtimeEventType(str, enum.Enum):
    """Signal event types on the WebSocket Control Plane."""

    SESSION_STARTED = "SESSION_STARTED"
    SESSION_RECONNECT = "SESSION_RECONNECT"
    SESSION_CLOSED = "SESSION_CLOSED"
    TRANSCRIPT_EVENT = "TRANSCRIPT_EVENT"
    TURN_EVENT = "TURN_EVENT"
    BARGE_IN = "BARGE_IN"
    INTERRUPT_FLUSH = "INTERRUPT_FLUSH"
    AUDIO_FRAME = "AUDIO_FRAME"
    VISUAL_DIRECTIVE = "VISUAL_DIRECTIVE"
    ERROR_EVENT = "ERROR_EVENT"
    HEARTBEAT = "HEARTBEAT"


class RealtimeErrorKind(str, enum.Enum):
    """Discrete error categories for realtime streaming operations (ADR-024 Lock 5)."""

    STT_FAILURE = "STT_FAILURE"
    TTS_FAILURE = "TTS_FAILURE"
    TRANSPORT_FAILURE = "TRANSPORT_FAILURE"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    INVALID_FRAME = "INVALID_FRAME"
    GENERATION_FENCE_VIOLATION = "GENERATION_FENCE_VIOLATION"
    SEQUENCE_GAP_DETECTED = "SEQUENCE_GAP_DETECTED"
    UNAUTHORIZED_MUTATION_ATTEMPT = "UNAUTHORIZED_MUTATION_ATTEMPT"


# ==============================================================================
# Pure Immutable DTOs
# ==============================================================================

class AudioFrameEnvelope(BaseModel):
    """Encapsulated transport envelope for Media Plane binary audio frames.

    ADR-024 Revision 2 Mandate:
    - Never send unadorned binary blobs.
    - generation_id guarantees stale-response isolation.
    - sequence_id detects packet reordering and lost frames.
    - Strictly forbidden from carrying character state, emotion, or conversation texts.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    protocol_version: int = Field(default=REALTIME_PROTOCOL_VERSION, description="Protocol format version")
    session_id: str = Field(..., min_length=1, description="Call session UUID")
    generation_id: int = Field(..., ge=0, description="Monotonic generation counter for stale response drop")
    sequence_id: int = Field(..., ge=0, description="Monotonic sequence counter within this generation")
    direction: AudioDirection = Field(..., description="Audio flow directionality")
    codec: AudioCodec = Field(..., description="Encoding wire format")
    sample_rate: int = Field(..., gt=0, description="Sampling rate in Hz (e.g. 16000, 24000)")
    stream_position_ms: int = Field(default=0, ge=0, description="Millisecond offset from generation start")
    payload: bytes = Field(..., description="Raw audio bytes (PCM or Opus compressed)")

    @model_validator(mode="after")
    def validate_envelope_constraints(self) -> AudioFrameEnvelope:
        if self.sample_rate not in (8000, 16000, 22050, 24000, 44100, 48000):
            raise ValueError(f"Unsupported audio sample rate: {self.sample_rate}")
        return self


class DirectionalTurnState(BaseModel):
    """Decomposed directional state of a conversational turn (ADR-024 Section 2.4).

    Decouples User speech progress from Assistant speech progress.
    Allows Assistant to be INTERRUPTED while User speech is COMMITTED,
    preventing conversation turns from collapsing into monolithic errors.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    turn_id: str = Field(..., min_length=1, description="Unique turn identifier")
    session_id: str = Field(..., min_length=1, description="Call session identifier")
    conversation_id: str = Field(..., min_length=1, description="Persistent conversation identifier")
    generation_id: int = Field(..., ge=0, description="Active assistant generation counter")
    user_input_state: UserInputState = Field(
        default=UserInputState.PARTIAL,
        description="Current state of user speech input",
    )
    assistant_output_state: AssistantOutputState = Field(
        default=AssistantOutputState.NOT_STARTED,
        description="Current state of companion speech output",
    )
    created_monotonic_at: float = Field(..., ge=0.0, description="Creation timestamp in monotonic seconds")
    updated_monotonic_at: float = Field(..., ge=0.0, description="Last update timestamp in monotonic seconds")

    @model_validator(mode="after")
    def validate_distinct_identities(self) -> DirectionalTurnState:
        # ADR-024 Axiom: session_id != conversation_id != turn_id
        if self.session_id == self.conversation_id:
            raise ValueError("session_id must not equal conversation_id (domain separation violation)")
        if self.turn_id == self.conversation_id:
            raise ValueError("turn_id must not equal conversation_id (domain separation violation)")
        if self.turn_id == self.session_id:
            raise ValueError("turn_id must not equal session_id (domain separation violation)")
        if self.updated_monotonic_at < self.created_monotonic_at:
            raise ValueError("updated_monotonic_at cannot precede created_monotonic_at")
        return self


class SessionEvent(BaseModel):
    """Lifecycle event for a realtime call session."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: RealtimeEventType = Field(..., description="Session lifecycle event type")
    session_id: str = Field(..., min_length=1, description="Session UUID")
    conversation_id: str = Field(..., min_length=1, description="Persistent conversation UUID")
    status: RealtimeSessionStatus = Field(..., description="Session operational status")
    active_generation_id: int = Field(default=0, ge=0, description="Current generation counter")
    lease_expires_monotonic_at: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Monotonic timestamp when the 30s reconnect lease expires",
    )
    reason: Optional[str] = Field(default=None, description="Optional human-readable lifecycle reason")


class TranscriptEvent(BaseModel):
    """Spoken transcript event on the control plane (ADR-024 Lock 3 & Lock 8)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: RealtimeEventType = Field(
        default=RealtimeEventType.TRANSCRIPT_EVENT,
        description="Event discriminator",
    )
    session_id: str = Field(..., min_length=1, description="Call session UUID")
    turn_id: str = Field(..., min_length=1, description="Turn identifier")
    lifecycle_state: TranscriptLifecycleState = Field(..., description="Transcript maturity level")
    text: str = Field(..., description="Transcribed spoken text")
    is_final: bool = Field(..., description="Whether STT provider considers the segment final")
    utterance_boundary_confirmed: bool = Field(
        default=False,
        description="Whether VAD silence (>= 600ms) or client release confirmed end-of-utterance",
    )
    provider_name: str = Field(default="streaming_stt", description="STT provider identifier")


class TurnEvent(BaseModel):
    """Full directional turn status update broadcasted to the desktop client."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: RealtimeEventType = Field(
        default=RealtimeEventType.TURN_EVENT,
        description="Event discriminator",
    )
    session_id: str = Field(..., min_length=1, description="Call session UUID")
    turn_id: str = Field(..., min_length=1, description="Turn identifier")
    conversation_id: str = Field(..., min_length=1, description="Persistent conversation UUID")
    directional_state: DirectionalTurnState = Field(..., description="Current directional turn state")
    reason: Optional[str] = Field(default=None, description="Transition trigger description")


class BargeInEvent(BaseModel):
    """Notification that the user interrupted companion speech (ADR-024 Lock 4)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: RealtimeEventType = Field(
        default=RealtimeEventType.BARGE_IN,
        description="Event discriminator",
    )
    session_id: str = Field(..., min_length=1, description="Call session UUID")
    interrupted_turn_id: str = Field(..., min_length=1, description="Turn ID of the interrupted speech")
    interrupted_generation_id: int = Field(..., ge=0, description="Generation ID that was interrupted")
    new_generation_id: int = Field(..., ge=0, description="Newly incremented generation ID")
    client_latch_timestamp_ms: int = Field(
        ...,
        ge=0,
        description="Client-side timestamp when audio was muted and mouth clamped",
    )


class InterruptFlushEvent(BaseModel):
    """Control frame instructing the client to discard older generation playback buffers."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: RealtimeEventType = Field(
        default=RealtimeEventType.INTERRUPT_FLUSH,
        description="Event discriminator",
    )
    session_id: str = Field(..., min_length=1, description="Call session UUID")
    generation_id: int = Field(..., ge=0, description="Active generation ID to enforce")
    flush_up_to_sequence_id: Optional[int] = Field(
        default=None,
        ge=0,
        description="Optional boundary sequence to drop",
    )
    reason: str = Field(default="user_barge_in", description="Reason for flush instruction")


class RealtimeErrorEvent(BaseModel):
    """Structured error event on the realtime control plane (ADR-024 Lock 5)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: RealtimeEventType = Field(
        default=RealtimeEventType.ERROR_EVENT,
        description="Event discriminator",
    )
    session_id: str = Field(..., min_length=1, description="Call session UUID")
    error_kind: RealtimeErrorKind = Field(..., description="Categorical error kind")
    message: str = Field(..., min_length=1, description="Descriptive error message")
    recoverable: bool = Field(default=True, description="Whether session remains operational")
    affected_generation_id: Optional[int] = Field(
        default=None,
        ge=0,
        description="Generation ID affected by this error, if applicable",
    )


class VisualDirectiveEvent(BaseModel):
    """Synchronized affective visual instruction for the Live2D canvas (ADR-024 Lock 1 & Lock 6).

    Carries presentation-only parameters. Cannot mutate character state or reality.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: RealtimeEventType = Field(
        default=RealtimeEventType.VISUAL_DIRECTIVE,
        description="Event discriminator",
    )
    session_id: str = Field(..., min_length=1, description="Call session UUID")
    expression_archetype: str = Field(..., min_length=1, description="Target Live2D expression name")
    intensity: int = Field(default=100, ge=0, le=100, description="Integer intensity percentage (0-100)")
    transition_duration_ms: int = Field(default=300, ge=0, description="Visual blend transition duration")
    mouth_open_override: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional direct clamp (e.g. 0.0 for barge-in latch)",
    )
    is_speaking: bool = Field(default=False, description="Speaking motion overlay indicator")


# ==============================================================================
# Pure Invariant & Boundary Verification Functions (ADR-024)
# ==============================================================================

def validate_generation_and_sequence_fence(
    active_generation_id: int,
    expected_sequence_id: int,
    incoming_frame: AudioFrameEnvelope,
) -> tuple[bool, str]:
    """Evaluates whether an incoming audio frame satisfies the dual fence (ADR-024 Lock 2).

    Returns:
        (True, "VALID") if frame is acceptable.
        (False, reason) if frame must be dropped.
    """
    if incoming_frame.generation_id < active_generation_id:
        return (
            False,
            f"STALE_GENERATION: Frame generation {incoming_frame.generation_id} < active {active_generation_id}",
        )

    if incoming_frame.generation_id == active_generation_id:
        if incoming_frame.sequence_id < expected_sequence_id:
            return (
                False,
                f"STALE_SEQUENCE: Frame sequence {incoming_frame.sequence_id} < expected {expected_sequence_id}",
            )

    return (True, "VALID")


def can_commit_to_canonical_message(transcript: TranscriptEvent) -> bool:
    """Evaluates the double-gate for committing spoken text to persistent Message (Lock 3 & Lock 8).

    Guarantees:
    - Must be in COMMITTED state.
    - Provider must indicate is_final == True.
    - Utterance boundary must be confirmed (VAD silence threshold or client release).
    - Text must have non-whitespace content.
    """
    if transcript.lifecycle_state != TranscriptLifecycleState.COMMITTED:
        return False
    if not transcript.is_final:
        return False
    if not transcript.utterance_boundary_confirmed:
        return False
    if not transcript.text.strip():
        return False
    return True


def can_trigger_reality_construction(transcript: TranscriptEvent) -> bool:
    """Constitutional Guard: Determines whether a transcript can trigger reality construction (Lock 8).

    Strictly forbids PARTIAL and FINAL_PENDING_COMMIT transcripts from entering Phase 14.
    Only fully verified, COMMITTED semantic messages may ever trigger downstream reasoning.
    """
    return can_commit_to_canonical_message(transcript)


def is_stt_failure_zero_fake_turn(error: RealtimeErrorEvent) -> bool:
    """Evaluates whether an error enforces the Zero Fake Turn rule (ADR-024 Lock 5).

    When STT fails, no user turn or empty message may ever be committed to the database.
    """
    return error.error_kind == RealtimeErrorKind.STT_FAILURE
