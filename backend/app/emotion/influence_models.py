"""Emotion influence models for Aevum Core.

Represents a structured domain representation answering:
"How might an emotionally relevant event affect Aevum emotionally?"

Serves as an intermediate domain layer between EmotionEvent and EmotionState
without modifying current EmotionState or defining emotional transition dynamics.

Guarantees:
- Structured domain representation of emotional influences originating from events.
- Strictly decoupled from EmotionState (does not store current emotion or mutate state).
- Strictly decoupled from CharacterState (no energy, stress, or mood fields).
- Strictly decoupled from RelationshipState (no trust, affection, or romance fields).
- Immutable, bounded representation (frozen=True, extra="forbid").
- Bounded reason text (max 500 chars, no credentials/secrets).
- Non-romance vocabulary: directions are strictly POSITIVE or NEGATIVE.
"""

from datetime import datetime
from enum import Enum
import math
from typing import Any
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.emotion.emotion_models import DEFAULT_CHARACTER_ID, EmotionType
from app.memory.curation_policy import contains_obvious_credentials

MAX_INFLUENCE_REASON_LENGTH: int = 500


class EmotionInfluenceDirection(str, Enum):
    """Direction of an emotional influence relative to the target emotion.

    POSITIVE: Event tends to move emotional experience toward the target emotion.
    NEGATIVE: Event tends to move emotional experience away from the target emotion.
    """

    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"


def _validate_strength(v: float, field_name: str = "strength") -> float:
    """Ensure influence strength is a finite normalized float in [0.0, 1.0]. Rejects out-of-bounds, NaN, and inf."""
    if not isinstance(v, (int, float)):
        raise ValueError(f"{field_name} must be a numeric value, got {type(v).__name__}.")
    if math.isnan(v):
        raise ValueError(f"{field_name} must not be NaN.")
    if math.isinf(v):
        raise ValueError(f"{field_name} must not be infinite.")
    if v < 0.0 or v > 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0 inclusive (got {v}).")
    return float(v)


def _validate_reason_text(v: str) -> str:
    """Sanitize and validate influence reason text."""
    if not isinstance(v, str):
        raise ValueError("reason must be a string.")
    stripped = v.strip()
    if not stripped:
        raise ValueError("reason must not be empty or whitespace.")
    if len(stripped) > MAX_INFLUENCE_REASON_LENGTH:
        raise ValueError(
            f"reason length ({len(stripped)}) exceeds maximum allowed ({MAX_INFLUENCE_REASON_LENGTH})."
        )
    if contains_obvious_credentials(stripped):
        raise ValueError("reason contains prohibited credential or secret patterns.")
    return stripped


class EmotionInfluenceCreate(BaseModel):
    """Payload for creating a new persistent EmotionInfluence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    character_id: str = Field(
        default=DEFAULT_CHARACTER_ID,
        description="Character identifier associated with the emotional influence.",
    )
    event_id: str = Field(
        ...,
        description="ID of the originating EmotionEvent.",
    )
    target_emotion: EmotionType = Field(
        ...,
        description="Target emotion type affected by this influence.",
    )
    direction: EmotionInfluenceDirection = Field(
        ...,
        description="Direction of the influence (POSITIVE or NEGATIVE).",
    )
    strength: float = Field(
        default=0.50,
        description="Magnitude/strength of the proposed emotional influence (0.0 to 1.0).",
    )
    reason: str = Field(
        ...,
        description="Short human-readable explanation of the influence (max 500 chars, no secrets).",
    )

    @field_validator("character_id", "event_id")
    @classmethod
    def validate_ids(cls, v: str, info: Any) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"{info.field_name} must not be empty or whitespace.")
        return v.strip()

    @field_validator("strength")
    @classmethod
    def validate_strength_field(cls, v: float) -> float:
        return _validate_strength(v)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        return _validate_reason_text(v)


class EmotionInfluence(BaseModel):
    """Immutable aggregate representing a structured emotional influence proposal.

    Distinctions:
    - EmotionEvent = What happened? (e.g. 'Aevum's piano practice went poorly today').
    - EmotionInfluence = How might that event affect Aevum emotionally? (e.g. target=FRUSTRATED, direction=POSITIVE, strength=0.55).
    - EmotionState = What is Aevum currently feeling right now? (dominant current affect).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier of the emotion influence record.",
    )
    character_id: str = Field(
        ...,
        description="Character identifier associated with the influence.",
    )
    event_id: str = Field(
        ...,
        description="ID of the originating EmotionEvent.",
    )
    target_emotion: EmotionType = Field(
        ...,
        description="Target emotion type affected by this influence.",
    )
    direction: EmotionInfluenceDirection = Field(
        ...,
        description="Direction of the influence (POSITIVE or NEGATIVE).",
    )
    strength: float = Field(
        ...,
        description="Magnitude/strength of the proposed emotional influence (0.0 to 1.0).",
    )
    reason: str = Field(
        ...,
        description="Short human-readable explanation of the influence.",
    )
    created_at: datetime = Field(
        ...,
        description="Immutable UTC timestamp when the influence was recorded.",
    )

    @field_validator("id", "character_id", "event_id")
    @classmethod
    def validate_ids(cls, v: str, info: Any) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"{info.field_name} must not be empty or whitespace.")
        return v.strip()

    @field_validator("strength")
    @classmethod
    def validate_strength_field(cls, v: float) -> float:
        return _validate_strength(v)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        return _validate_reason_text(v)
