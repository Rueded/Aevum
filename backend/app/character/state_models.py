"""Character state domain models for Aevum Core.

Defines provider-independent, immutable models representing current mutable character
condition, physiological/cognitive state indicators, and situational context.
"""

from datetime import datetime
import enum
import math
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CharacterMood(str, enum.Enum):
    """Controlled, qualitative mood representation for baseline character state.

    This enum is intentionally kept small and qualitative. Complex emotional states,
    dimensional vectors, and transition dynamics belong to the future Emotion Engine.
    """

    NEUTRAL = "neutral"
    GOOD = "good"
    LOW = "low"
    IRRITATED = "irritated"
    CALM = "calm"
    TIRED = "tired"
    FOCUSED = "focused"

    @classmethod
    def _missing_(cls, value: object) -> "CharacterMood":
        if isinstance(value, str):
            v_lower = value.strip().lower()
            if v_lower in cls._value2member_map_:
                return cls._value2member_map_[v_lower]
            if v_lower in ("playful", "happy", "joyful", "cheerful", "excited", "delighted", "sweet"):
                return cls.GOOD
            if v_lower in ("relaxed", "peaceful", "serene", "chill"):
                return cls.CALM
            if v_lower in ("sad", "gloomy", "unhappy"):
                return cls.LOW
            if v_lower in ("angry", "annoyed", "mad", "upset"):
                return cls.IRRITATED
            if v_lower in ("sleepy", "exhausted", "drowsy"):
                return cls.TIRED
            if v_lower in ("busy", "working", "concentrated", "studying"):
                return cls.FOCUSED
        return cls.GOOD


class CharacterState(BaseModel):
    """Immutable aggregate representing current mutable character state.

    Distinction:
    - CharacterDefinition = WHO Aevum is (stable identity, personality, preferences, boundaries).
    - CharacterState = HOW Aevum currently is (current condition, situational context).

    Continuous metrics use a normalized range of 0.0 to 1.0 with explicit semantics.
    Note: Initial situational values (activity='resting', location='home') are deterministic
    bootstrap values and do not imply permanent placement; future Life/Event systems will
    manage contextual transitions.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(
        default="aevum",
        description="Stable identifier for the character.",
    )
    version: int = Field(
        default=1,
        ge=1,
        description="Monotonically increasing version counter for optimistic concurrency.",
    )
    updated_at: datetime = Field(
        description="UTC timestamp of the most recent character state update.",
    )

    # Qualitative mood
    mood: CharacterMood = Field(
        default=CharacterMood.NEUTRAL,
        description="Current qualitative mood.",
    )

    # Normalized continuous indicators (0.0 - 1.0)
    energy: float = Field(
        ...,
        description="Current physical/mental energy level (0.0 = depleted, 1.0 = highly energetic).",
    )
    stress: float = Field(
        ...,
        description="Current perceived stress level (0.0 = very relaxed, 1.0 = extremely stressed).",
    )
    social_energy: float = Field(
        ...,
        description="Current capacity/desire for social interaction (0.0 = socially drained, 1.0 = socially energized).",
    )
    confidence: float = Field(
        ...,
        description="Current situational confidence level (0.0 = very uncertain, 1.0 = very confident).",
    )
    irritation: float = Field(
        ...,
        description="Current situational irritation level (0.0 = not irritated, 1.0 = highly irritated).",
    )
    loneliness: float = Field(
        ...,
        description="Current subjective loneliness state (0.0 = not lonely, 1.0 = very lonely).",
    )

    # Situational context (bootstrap defaults; driven by Life simulation in future phases)
    current_activity: str = Field(
        ...,
        description="Current activity description (bootstrap value: 'resting').",
    )
    current_location: str = Field(
        ...,
        description="Current character-world location (bootstrap value: 'home').",
    )

    @field_validator("energy", "stress", "social_energy", "confidence", "irritation", "loneliness")
    @classmethod
    def validate_normalized_metric(cls, v: float, info: Any) -> float:
        if math.isnan(v):
            raise ValueError(f"{info.field_name} must not be NaN.")
        if math.isinf(v):
            raise ValueError(f"{info.field_name} must not be infinite.")
        if v < 0.0 or v > 1.0:
            raise ValueError(f"{info.field_name} must be between 0.0 and 1.0 inclusive.")
        return v

    @field_validator("current_activity", "current_location")
    @classmethod
    def validate_non_empty_strings(cls, v: str, info: Any) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"{info.field_name} must not be empty or whitespace.")
        return v.strip()


class CharacterStateUpdate(BaseModel):
    """Validated partial state replacement request.

    Used by trusted internal application subsystems to request modifications to CharacterState.
    Immutable and strictly validated. A mutation request containing zero specified fields is rejected.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    mood: CharacterMood | None = None
    energy: float | None = None
    stress: float | None = None
    social_energy: float | None = None
    confidence: float | None = None
    irritation: float | None = None
    loneliness: float | None = None
    current_activity: str | None = None
    current_location: str | None = None

    @field_validator("energy", "stress", "social_energy", "confidence", "irritation", "loneliness")
    @classmethod
    def validate_normalized_metric(cls, v: float | None, info: Any) -> float | None:
        if v is None:
            return None
        if math.isnan(v):
            raise ValueError(f"{info.field_name} must not be NaN.")
        if math.isinf(v):
            raise ValueError(f"{info.field_name} must not be infinite.")
        if v < 0.0 or v > 1.0:
            raise ValueError(f"{info.field_name} must be between 0.0 and 1.0 inclusive.")
        return v

    @field_validator("current_activity", "current_location")
    @classmethod
    def validate_non_empty_strings(cls, v: str | None, info: Any) -> str | None:
        if v is None:
            return None
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"{info.field_name} must not be empty or whitespace.")
        return v.strip()

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "CharacterStateUpdate":
        has_any_field = any(
            getattr(self, field_name) is not None
            for field_name in [
                "mood",
                "energy",
                "stress",
                "social_energy",
                "confidence",
                "irritation",
                "loneliness",
                "current_activity",
                "current_location",
            ]
        )
        if not has_any_field:
            raise ValueError("CharacterStateUpdate must contain at least one field to update.")
        return self

