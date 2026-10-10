"""Pure immutable data contracts and domain models for the Voice subsystem (Phase 10.1).

Governed by ADR-021:
- Mind/Body Boundary: Audio is an ephemeral interaction interface ("the body");
  backend Character Engine remains the sole mind and single source of truth.
- Zero Canonical Reality Mutation: Voice models never touch core facts or memory.
- Lock B: Decoupled failure resilience (TTS failure != Mind failure; STT failure -> 0 fake turns).
- Lock D: Categorical EpistemicCue (Zero pseudo-probability floats; discrete epistemic cues).
- Lock E: Canonical Audio Cache Identity (SHA-256 over canonical tuple preventing cross-emotion collisions).
- Lock F: Ephemeral Media Lifecycle Isolation (Audio cache expiry strictly decoupled from domain state).
"""

from datetime import datetime, timezone
import enum
import hashlib
import json
import math
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AudioFormat(str, enum.Enum):
    """Supported audio container formats."""

    WAV = "WAV"
    MP3 = "MP3"
    OGG_OPUS = "OGG_OPUS"
    WEBM = "WEBM"


class AudioChannel(str, enum.Enum):
    """Audio channel topology."""

    MONO = "MONO"
    STEREO = "STEREO"


class AudioMediaLifecycle(str, enum.Enum):
    """Ephemeral lifecycle states for transient audio artifacts (ADR-021 Lock F)."""

    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    PURGED = "PURGED"


class EpistemicCue(str, enum.Enum):
    """Discrete categorical epistemic cues for prosody modulation (ADR-021 Lock D).

    Strictly forbids continuous pseudo-probability floats (e.g. confidence=0.63).
    Non-certain cues deterministically trigger hesitation or cadence adjustment.
    """

    CERTAIN = "CERTAIN"
    UNCERTAIN = "UNCERTAIN"
    AMBIGUOUS = "AMBIGUOUS"
    CONTESTED = "CONTESTED"
    UNKNOWN = "UNKNOWN"


class SynthesisStatus(str, enum.Enum):
    """Synthesis operational execution status (ADR-021 Lock B)."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"


class TranscriptionStatus(str, enum.Enum):
    """Transcription operational execution status (ADR-021 Lock B)."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"


class VoiceInputMode(str, enum.Enum):
    """Audio capture interaction mode (ADR-021 Decision 3).

    Push-To-Talk is the only mandatory input mode in Phase 10. Continuous VAD is deferred.
    """

    PTT = "PTT"


class AudioData(BaseModel):
    """Immutable binary audio payload with acoustic metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    data: bytes = Field(..., description="Raw audio bytes.")
    format: AudioFormat = Field(..., description="Audio container format.")
    sample_rate_hz: int = Field(..., description="Sampling rate in Hz (e.g. 16000, 24000, 44100).")
    channels: AudioChannel = Field(..., description="Audio channel count.")
    duration_ms: int = Field(..., description="Audio duration in milliseconds.")
    sha256_hash: str = Field(..., description="Hex SHA-256 digest of data bytes.")

    @field_validator("data")
    @classmethod
    def validate_non_empty_data(cls, v: bytes) -> bytes:
        if not v:
            raise ValueError("Audio data bytes cannot be empty.")
        return v

    @field_validator("sample_rate_hz")
    @classmethod
    def validate_sample_rate(cls, v: int) -> int:
        if v < 8000 or v > 96000:
            raise ValueError("sample_rate_hz must be between 8000 and 96000 Hz.")
        return v

    @field_validator("duration_ms")
    @classmethod
    def validate_duration(cls, v: int) -> int:
        if v < 0:
            raise ValueError("duration_ms cannot be negative.")
        return v

    @model_validator(mode="after")
    def validate_sha256_integrity(self) -> "AudioData":
        actual_hash = hashlib.sha256(self.data).hexdigest()
        if self.sha256_hash != actual_hash:
            raise ValueError(
                f"sha256_hash mismatch: declared '{self.sha256_hash}', actual '{actual_hash}'."
            )
        return self

    @classmethod
    def create(
        cls,
        data: bytes,
        format: AudioFormat,
        sample_rate_hz: int,
        channels: AudioChannel,
        duration_ms: int,
    ) -> "AudioData":
        """Convenience factory computing sha256_hash automatically."""
        computed_hash = hashlib.sha256(data).hexdigest()
        return cls(
            data=data,
            format=format,
            sample_rate_hz=sample_rate_hz,
            channels=channels,
            duration_ms=duration_ms,
            sha256_hash=computed_hash,
        )


class ProsodyConfig(BaseModel):
    """Deterministic acoustic prosody modulation parameters.

    Physical acoustic variables are bounded floats; zero epistemic probability semantics.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rate_multiplier: float = Field(
        default=1.0,
        description="Speech rate multiplier (0.50x to 2.00x). 1.0 is neutral baseline.",
    )
    pitch_shift_semitones: float = Field(
        default=0.0,
        description="Pitch shift in semitones (-12.0 to +12.0). 0.0 is neutral baseline.",
    )
    volume_gain_db: float = Field(
        default=0.0,
        description="Volume gain in decibels (-20.0 to +10.0 dB). 0.0 is neutral baseline.",
    )
    style_tag: Optional[str] = Field(
        default=None,
        description="Provider-specific expressive style descriptor (e.g. 'cheerful', 'whisper').",
    )
    hesitation_pause_ms: int = Field(
        default=0,
        description="Inserted hesitation pause duration in milliseconds (0 to 2000 ms).",
    )

    @field_validator("rate_multiplier")
    @classmethod
    def validate_rate(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v) or v < 0.50 or v > 2.00:
            raise ValueError("rate_multiplier must be a finite float between 0.50 and 2.00.")
        return float(round(v, 3))

    @field_validator("pitch_shift_semitones")
    @classmethod
    def validate_pitch(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v) or v < -12.0 or v > 12.0:
            raise ValueError("pitch_shift_semitones must be a finite float between -12.0 and +12.0.")
        return float(round(v, 2))

    @field_validator("volume_gain_db")
    @classmethod
    def validate_volume(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v) or v < -20.0 or v > 10.0:
            raise ValueError("volume_gain_db must be a finite float between -20.0 and +10.0.")
        return float(round(v, 2))

    @field_validator("hesitation_pause_ms")
    @classmethod
    def validate_hesitation(cls, v: int) -> int:
        if v < 0 or v > 2000:
            raise ValueError("hesitation_pause_ms must be an integer between 0 and 2000 ms.")
        return v

    def to_canonical_dict(self) -> dict[str, object]:
        """Produce canonical sorted dictionary for cache key hashing (ADR-021 Lock E)."""
        return {
            "hesitation_pause_ms": self.hesitation_pause_ms,
            "pitch_shift_semitones": self.pitch_shift_semitones,
            "rate_multiplier": self.rate_multiplier,
            "style_tag": self.style_tag if self.style_tag is not None else "",
            "volume_gain_db": self.volume_gain_db,
        }


class VoiceProfile(BaseModel):
    """Immutable voice actor profile definition."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    voice_id: str = Field(..., description="Unique voice identifier.")
    name: str = Field(..., description="Human-readable voice name.")
    language: str = Field(default="en-US", description="Primary BCP-47 language tag.")
    gender: str = Field(default="female", description="Voice gender presentation.")
    supported_styles: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Tuple of supported style descriptors.",
    )


def compute_canonical_audio_cache_key(
    text: str,
    voice_id: str,
    audio_format: AudioFormat,
    prosody: ProsodyConfig,
    provider_id: str,
    provider_version: str,
) -> str:
    """Compute canonical SHA-256 audio cache key (ADR-021 Lock E).

    Strictly incorporates text, voice_id, format, canonical prosody dict,
    provider_id, and provider_version to prevent cross-emotion, cross-voice,
    or cross-provider collisions.
    """
    canonical_payload = {
        "audio_format": audio_format.value,
        "prosody": prosody.to_canonical_dict(),
        "provider_id": provider_id,
        "provider_version": provider_version,
        "text": text.strip(),
        "voice_id": voice_id,
    }
    canonical_json_bytes = json.dumps(
        canonical_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical_json_bytes).hexdigest()


class SynthesisRequest(BaseModel):
    """Immutable request contract for text-to-speech synthesis."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    request_id: str = Field(..., description="Unique synthesis request ID.")
    text: str = Field(..., description="Text content to synthesize into speech.")
    voice_id: str = Field(..., description="Target voice profile ID.")
    desired_format: AudioFormat = Field(
        default=AudioFormat.WAV,
        description="Desired audio container format.",
    )
    prosody: ProsodyConfig = Field(
        default_factory=ProsodyConfig,
        description="Acoustic prosody modulation parameters.",
    )
    epistemic_cue: EpistemicCue = Field(
        default=EpistemicCue.CERTAIN,
        description="Discrete epistemic certainty cue.",
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="Optional associated conversation ID for provenance context.",
    )
    message_id: Optional[str] = Field(
        default=None,
        description="Optional associated message ID for provenance context.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC creation timestamp.",
    )

    @field_validator("text")
    @classmethod
    def validate_text_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Synthesis text cannot be empty or whitespace.")
        return v.strip()


class SynthesisResult(BaseModel):
    """Immutable result contract for text-to-speech synthesis."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    request_id: str = Field(..., description="Originating request ID.")
    status: SynthesisStatus = Field(..., description="Synthesis outcome status.")
    audio: Optional[AudioData] = Field(
        default=None,
        description="Synthesized audio data (present if SUCCESS, None if FAILED).",
    )
    cache_key: Optional[str] = Field(
        default=None,
        description="Canonical audio cache key (present if SUCCESS).",
    )
    provider_id: str = Field(..., description="ID of the synthesizing provider.")
    provider_version: str = Field(..., description="Version of the synthesizing provider.")
    error_message: Optional[str] = Field(
        default=None,
        description="Diagnostic error explanation (present if FAILED).",
    )

    @model_validator(mode="after")
    def validate_status_payload_consistency(self) -> "SynthesisResult":
        if self.status == SynthesisStatus.SUCCESS:
            if self.audio is None:
                raise ValueError("SynthesisResult with status=SUCCESS must contain audio data.")
            if self.cache_key is None:
                raise ValueError("SynthesisResult with status=SUCCESS must contain cache_key.")
            if self.error_message is not None:
                raise ValueError("SynthesisResult with status=SUCCESS must not contain error_message.")
        elif self.status in (SynthesisStatus.FAILED, SynthesisStatus.UNAVAILABLE):
            if self.audio is not None:
                raise ValueError(
                    f"SynthesisResult with status={self.status.value} must not contain audio data."
                )
        return self


class TranscriptionRequest(BaseModel):
    """Immutable request contract for speech-to-text transcription."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    request_id: str = Field(..., description="Unique transcription request ID.")
    audio: AudioData = Field(..., description="Input audio data to transcribe.")
    language: Optional[str] = Field(
        default=None,
        description="Optional expected BCP-47 language hint.",
    )
    input_mode: VoiceInputMode = Field(
        default=VoiceInputMode.PTT,
        description="Interaction capture mode. Strictly PTT in Phase 10.",
    )
    user_consent_granted: bool = Field(
        ...,
        description="Rule 18 microphone consent verification flag.",
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="Optional conversation context ID.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC creation timestamp.",
    )

    @field_validator("input_mode")
    @classmethod
    def validate_ptt_only(cls, v: VoiceInputMode) -> VoiceInputMode:
        if v != VoiceInputMode.PTT:
            raise ValueError("Only VoiceInputMode.PTT is permitted in Phase 10 (ADR-021 Decision 3).")
        return v


class TranscriptionResult(BaseModel):
    """Immutable result contract for speech-to-text transcription."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    request_id: str = Field(..., description="Originating request ID.")
    status: TranscriptionStatus = Field(..., description="Transcription outcome status.")
    transcribed_text: Optional[str] = Field(
        default=None,
        description="Recognized transcript text (present if SUCCESS, None if FAILED).",
    )
    provider_id: str = Field(..., description="ID of the transcribing provider.")
    provider_version: str = Field(..., description="Version of the transcribing provider.")
    error_message: Optional[str] = Field(
        default=None,
        description="Diagnostic error explanation (present if FAILED).",
    )

    @model_validator(mode="after")
    def validate_status_payload_consistency(self) -> "TranscriptionResult":
        if self.status == TranscriptionStatus.SUCCESS:
            if self.transcribed_text is None:
                raise ValueError(
                    "TranscriptionResult with status=SUCCESS must contain transcribed_text."
                )
            if self.error_message is not None:
                raise ValueError(
                    "TranscriptionResult with status=SUCCESS must not contain error_message."
                )
        elif self.status in (TranscriptionStatus.FAILED, TranscriptionStatus.UNAVAILABLE):
            if self.transcribed_text is not None:
                raise ValueError(
                    f"TranscriptionResult with status={self.status.value} must not contain transcribed_text."
                )
        return self
