"""Emotion cause and event models for Aevum Core.

Represents discrete historical emotionally relevant causes and occurrences
answering "Why is Aevum currently feeling this emotion?" without modifying
current EmotionState or defining emotional transition dynamics.

Guarantees:
- Structured domain representation of emotional causes and external/internal events.
- Strictly decoupled from EmotionState (does not store previous/next emotion or transitions).
- Strictly decoupled from CharacterState (no energy, stress, or mood fields).
- Strictly decoupled from RelationshipState (no trust, affection, or romance fields).
- Immutable, bounded representation (frozen=True, extra="forbid").
- Bounded summary text (max 500 chars, no credentials/secrets).
"""

from datetime import datetime
from enum import Enum
import math
from typing import Any
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models import utc_now
from app.memory.curation_policy import contains_obvious_credentials

MAX_EMOTION_EVENT_SUMMARY_LENGTH: int = 500
DEFAULT_CHARACTER_ID: str = "aevum"


class EmotionEventType(str, Enum):
    """Controlled vocabulary of discrete emotionally relevant event types.

    Deliberately compact and non-romantic. No romance or relationship mechanics.
    """

    USER_INTERACTION = "USER_INTERACTION"
    CHARACTER_EVENT = "CHARACTER_EVENT"
    MEMORY_RECALL = "MEMORY_RECALL"
    LIFE_EVENT = "LIFE_EVENT"
    RELATIONSHIP_EVENT = "RELATIONSHIP_EVENT"
    INTERNAL_STATE = "INTERNAL_STATE"
    SYSTEM_EVENT = "SYSTEM_EVENT"


class EmotionEventSource(str, Enum):
    """Origin source of the emotion event observation or report."""

    SYSTEM = "SYSTEM"
    LLM = "LLM"
    MANUAL = "MANUAL"


def _validate_relevance(v: float, field_name: str = "emotional_relevance") -> float:
    """Ensure emotional relevance is a finite normalized float between 0.0 and 1.0 inclusive."""
    if not isinstance(v, (int, float)):
        raise ValueError(f"{field_name} must be a numeric value, got {type(v).__name__}.")
    if math.isnan(v):
        raise ValueError(f"{field_name} must not be NaN.")
    if math.isinf(v):
        raise ValueError(f"{field_name} must not be infinite.")
    if v < 0.0 or v > 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0 inclusive (got {v}).")
    return float(v)


def _validate_summary_text(v: str) -> str:
    """Sanitize and validate event summary text."""
    if not isinstance(v, str):
        raise ValueError("summary must be a string.")
    stripped = v.strip()
    if not stripped:
        raise ValueError("summary must not be empty or whitespace.")
    if len(stripped) > MAX_EMOTION_EVENT_SUMMARY_LENGTH:
        raise ValueError(
            f"summary length ({len(stripped)}) exceeds maximum allowed ({MAX_EMOTION_EVENT_SUMMARY_LENGTH})."
        )
    if contains_obvious_credentials(stripped):
        raise ValueError("summary contains prohibited credential or secret patterns.")
    return stripped


class EmotionEventCreate(BaseModel):
    """Payload for creating a new persistent EmotionEvent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    character_id: str = Field(
        default=DEFAULT_CHARACTER_ID,
        description="Character identifier associated with the emotional event.",
    )
    event_type: EmotionEventType = Field(
        ...,
        description="Categorical type of the emotionally relevant event.",
    )
    summary: str = Field(
        ...,
        description="Concise description of the event (max 500 chars, no secrets).",
    )
    source: EmotionEventSource = Field(
        default=EmotionEventSource.SYSTEM,
        description="Source of the event observation.",
    )
    emotional_relevance: float = Field(
        default=0.50,
        description="Estimated emotional relevance/salience of the event (0.0 to 1.0).",
    )

    @field_validator("character_id")
    @classmethod
    def validate_character_id(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("character_id must not be empty or whitespace.")
        return v.strip()

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, v: str) -> str:
        return _validate_summary_text(v)

    @field_validator("emotional_relevance")
    @classmethod
    def validate_relevance_field(cls, v: float) -> float:
        return _validate_relevance(v)


class EmotionEvent(BaseModel):
    """Immutable aggregate representing an emotionally relevant cause or event.

    Distinctions:
    - EmotionState = What Aevum is currently feeling (e.g. CURIOUS at 0.7 intensity).
    - EmotionEvent = What happened that is emotionally relevant (e.g. 'Finished reading a captivating novel').
    - CharacterState = Broad physiological condition (energy, stress, location, etc.).
    - RelationshipState = How Aevum relates to the user (trust, respect, familiarity, etc.).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier of the emotion event record.",
    )
    character_id: str = Field(
        ...,
        description="Character identifier associated with the event.",
    )
    event_type: EmotionEventType = Field(
        ...,
        description="Categorical type of the emotionally relevant event.",
    )
    summary: str = Field(
        ...,
        description="Concise description of the event.",
    )
    source: EmotionEventSource = Field(
        ...,
        description="Source of the event observation.",
    )
    emotional_relevance: float = Field(
        ...,
        description="Emotional relevance/salience (0.0 to 1.0).",
    )
    created_at: datetime = Field(
        ...,
        description="Immutable UTC timestamp when the event was recorded.",
    )

    @field_validator("id", "character_id")
    @classmethod
    def validate_non_empty_strings(cls, v: str, info: Any) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"{info.field_name} must not be empty or whitespace.")
        return v.strip()

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, v: str) -> str:
        return _validate_summary_text(v)

    @field_validator("emotional_relevance")
    @classmethod
    def validate_relevance_field(cls, v: float) -> float:
        return _validate_relevance(v)
