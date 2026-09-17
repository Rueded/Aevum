"""Character domain models for Aevum Core.

Defines provider-independent, immutable models representing stable character
identity, structured personality tendencies, preferences, and behavioral boundaries.
"""

from datetime import datetime
import enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator, model_validator


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




class CharacterCoreAnchor(BaseModel):
    """Immutable existential core of the character.
    
    Contains bedrock identity, innate temperamental traits, and non-negotiable boundaries.
    Never altered through conversational drift or prompt suggestions.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    identity: CharacterIdentity = Field(..., description="Foundational identity.")
    core_traits: tuple[str, ...] = Field(..., description="Unalterable innate character traits.")
    core_boundaries: tuple[Boundary, ...] = Field(..., description="Non-negotiable ethical and behavioral boundaries.")
    existential_anchor: str = Field(
        default="A persistent digital life living an authentic, independent existence.",
        description="Core philosophical axiom.",
    )


class CharacterSurfacePersona(BaseModel):
    """Evolving surface persona, conversational habits, and developing interests.
    
    Can evolve slowly through structured experience consolidation, while anchored to core traits.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    conversational_style: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Current conversational patterns.",
    )
    speech_habits: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Surface speech quirks or phrases.",
    )
    active_topics_of_interest: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Current topics capturing character curiosity.",
    )
    evolving_preferences: tuple[Preference, ...] = Field(
        default_factory=tuple,
        description="Preferences that have emerged through recent experiences.",
    )
    mood_expression_bias: Optional[str] = Field(
        default=None,
        description="Situational stylistic tendency in how emotions are surfaced.",
    )


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

    _custom_core_anchor: Optional[CharacterCoreAnchor] = PrivateAttr(default=None)
    _custom_surface_persona: Optional[CharacterSurfacePersona] = PrivateAttr(default=None)

    @field_validator("preferences", "boundaries", mode="before")
    @classmethod
    def coerce_to_tuple(cls, v: Any) -> Any:
        if isinstance(v, (list, tuple)):
            return tuple(v)
        return v

    @property
    def core_anchor(self) -> CharacterCoreAnchor:
        """Immutable existential core anchor derived from foundational identity, traits, and boundaries."""
        if self._custom_core_anchor is not None:
            return self._custom_core_anchor
        return CharacterCoreAnchor(
            identity=self.identity,
            core_traits=self.personality.core_traits,
            core_boundaries=self.boundaries,
        )

    @property
    def surface_persona(self) -> CharacterSurfacePersona:
        """Dynamic surface persona derived from communication style, habits, and preferences."""
        if self._custom_surface_persona is not None:
            return self._custom_surface_persona
        return CharacterSurfacePersona(
            conversational_style=self.personality.communication_style,
            speech_habits=self.personality.behavioral_tendencies,
            active_topics_of_interest=tuple(p.item for p in self.preferences),
            evolving_preferences=self.preferences,
        )
