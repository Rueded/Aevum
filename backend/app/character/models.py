"""Character domain models for Aevum Core.

Defines provider-independent, immutable models representing stable character
identity, structured personality tendencies, preferences, and behavioral boundaries.
"""

from datetime import datetime
import enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


class PreferenceSentiment(str, enum.Enum):
    """Sentiment classification for character preferences."""

    LIKE = "like"
    DISLIKE = "dislike"
    NEUTRAL = "neutral"


class CharacterIdentity(BaseModel):
    """Stable character identity attributes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., description="Character name.")
    age: int = Field(..., description="Character age in years.")
    occupation: str = Field(..., description="Character primary occupation or current status.")
    background: str = Field(..., description="Foundational personal background and context.")

    @field_validator("name", "occupation", "background")
    @classmethod
    def validate_non_empty_strings(cls, v: str, info: Any) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"{info.field_name} must not be empty or whitespace.")
        return v.strip()

    @field_validator("age")
    @classmethod
    def validate_age_range(cls, v: int) -> int:
        if v < 18 or v > 100:
            raise ValueError("age must be between 18 and 100 inclusive.")
        return v


def _validate_trait_sequence(traits: Any, field_name: str) -> tuple[str, ...]:
    """Validate that a trait dimension contains at least one non-empty string."""
    if not isinstance(traits, (list, tuple)):
        raise ValueError(f"{field_name} must be a sequence of strings.")

    cleaned: list[str] = []
    for item in traits:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name} items must not be empty or whitespace.")
        cleaned.append(item.strip())

    if not cleaned:
        raise ValueError(f"{field_name} must contain at least one valid trait.")

    return tuple(cleaned)


class Personality(BaseModel):
    """Structured multi-dimensional personality tendencies."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    core_traits: tuple[str, ...] = Field(
        ...,
        description="Fundamental character traits and baseline disposition.",
    )
    social_style: tuple[str, ...] = Field(
        ...,
        description="Social interaction tendencies, boundaries, and comfort zones.",
    )
    emotional_style: tuple[str, ...] = Field(
        ...,
        description="Internal emotional processing and vulnerability patterns.",
    )
    communication_style: tuple[str, ...] = Field(
        ...,
        description="Conversational tone, expression quirks, and linguistic manner.",
    )
    behavioral_tendencies: tuple[str, ...] = Field(
        ...,
        description="Observable action patterns, decision habits, and principles.",
    )
    flaws: tuple[str, ...] = Field(
        ...,
        description="Realistic character imperfections and non-dramatic limitations.",
    )

    @field_validator(
        "core_traits",
        "social_style",
        "emotional_style",
        "communication_style",
        "behavioral_tendencies",
        "flaws",
        mode="before",
    )
    @classmethod
    def validate_dimensions(cls, v: Any, info: Any) -> tuple[str, ...]:
        return _validate_trait_sequence(v, info.field_name)


class Preference(BaseModel):
    """Specific interest or preference independent of user interaction."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    category: str = Field(..., description="Preference domain or category.")
    item: str = Field(..., description="Specific item, subject, or activity.")
    sentiment: PreferenceSentiment = Field(
        ...,
        description="Character disposition towards this item (like, dislike, neutral).",
    )

    @field_validator("category", "item")
    @classmethod
    def validate_non_empty(cls, v: str, info: Any) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"{info.field_name} must not be empty or whitespace.")
        return v.strip()


class Boundary(BaseModel):
    """Stable behavioral principle guiding character actions and limits."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    description: str = Field(..., description="Description of the behavioral boundary.")

    @field_validator("description")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("description must not be empty or whitespace.")
        return v.strip()


class CharacterDefinition(BaseModel):
    """Aggregate root representing the canonical, persistent character definition.

    Owns stable identity, multi-dimensional personality, preferences, and
    behavioral boundaries. Contains zero user-relational state (affection, trust),
    zero emotional transient state (mood, energy), and zero memories.
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
        description="UTC timestamp of the most recent character definition update.",
    )
    identity: CharacterIdentity = Field(
        ...,
        description="Stable character identity.",
    )
    personality: Personality = Field(
        ...,
        description="Structured personality tendencies.",
    )
    preferences: tuple[Preference, ...] = Field(
        default_factory=tuple,
        description="Persistent character preferences.",
    )
    boundaries: tuple[Boundary, ...] = Field(
        default_factory=tuple,
        description="Persistent behavioral boundaries.",
    )

    @field_validator("preferences", "boundaries", mode="before")
    @classmethod
    def coerce_to_tuple(cls, v: Any) -> Any:
        if isinstance(v, (list, tuple)):
            return tuple(v)
        return v
