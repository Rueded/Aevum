"""Emotion domain models for Aevum Core.

Defines provider-independent, immutable models representing current dominant
emotional state, discrete affective categories, and optimistic-concurrency updates.

Guarantees:
- Single dominant emotion: Represents dominant affective condition, not multi-vector blends.
- Normalized continuous intensity: 0.0 (essentially absent) to 1.0 (extremely strong).
- Decoupled from CharacterState: Does not duplicate energy, stress, or baseline mood.
- Decoupled from RelationshipState: Does not contain trust, affection, attachment, or romance.
- Application-owned: The application state machine is the sole authority for emotional state.
"""

from datetime import datetime
import enum
import math
from typing import Any
import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.models import utc_now

DEFAULT_CHARACTER_ID: str = "aevum"


class EmotionType(str, enum.Enum):
    """Controlled qualitative vocabulary for dominant current emotional state.

    Deliberately compact, human-readable, and non-romantic. Complex emotional
    causes, transitions, decay, and prompt-context builders belong to future phases.
    """

    NEUTRAL = "NEUTRAL"
    HAPPY = "HAPPY"
    CALM = "CALM"
    EXCITED = "EXCITED"
    CURIOUS = "CURIOUS"
    AMUSED = "AMUSED"
    CONTENT = "CONTENT"
    SAD = "SAD"
    DISAPPOINTED = "DISAPPOINTED"
    WORRIED = "WORRIED"
    FRUSTRATED = "FRUSTRATED"
    IRRITATED = "IRRITATED"
    ANGRY = "ANGRY"
    LONELY = "LONELY"
    EMBARRASSED = "EMBARRASSED"
    NERVOUS = "NERVOUS"
    TIRED = "TIRED"


BOOTSTRAP_EMOTION_TYPE: EmotionType = EmotionType.NEUTRAL
BOOTSTRAP_INTENSITY: float = 0.50


def _validate_intensity(v: float, field_name: str = "intensity") -> float:
    """Ensure intensity is a finite normalized float between 0.0 and 1.0 inclusive."""
    if math.isnan(v):
        raise ValueError(f"{field_name} must not be NaN.")
    if math.isinf(v):
        raise ValueError(f"{field_name} must not be infinite.")
    if v < 0.0 or v > 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0 inclusive.")
    return float(v)


class EmotionState(BaseModel):
    """Immutable aggregate representing current dominant emotional condition.

    Distinctions:
    - CharacterDefinition = WHO Aevum is (stable identity, traits, boundaries).
    - CharacterState = HOW Aevum currently is (broad physiological & situational condition).
    - EmotionState = DOMINANT CURRENT emotional experience (affective state and intensity).
    - RelationshipState = HOW Aevum relates to the user (familiarity, trust, respect, etc.).
    - Memory = WHAT Aevum remembers (historical facts and episodic memories).

    Intensity is continuous [0.0, 1.0] and represents how strongly the dominant emotion
    is experienced. It is application state, not an LLM score or prompt directive.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Stable unique identifier for the emotion state record.",
    )
    character_id: str = Field(
        default=DEFAULT_CHARACTER_ID,
        description="Stable character identifier.",
    )
    emotion_type: EmotionType = Field(
        default=BOOTSTRAP_EMOTION_TYPE,
        description="Dominant current emotional state.",
    )
    intensity: float = Field(
        default=BOOTSTRAP_INTENSITY,
        description="Normalized intensity of the current emotion (0.0 = essentially absent, 1.0 = extremely strong).",
    )
    created_at: datetime = Field(
        description="Immutable UTC timestamp when the emotion state was initialized.",
    )
    updated_at: datetime = Field(
        description="UTC timestamp of the most recent emotion state update.",
    )
    version: int = Field(
        default=1,
        ge=1,
        description="Monotonically increasing version counter for optimistic concurrency.",
    )

    @field_validator("id", "character_id")
    @classmethod
    def validate_non_empty_strings(cls, v: str, info: Any) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"{info.field_name} must not be empty or whitespace.")
        return v.strip()

    @field_validator("intensity")
    @classmethod
    def validate_intensity_field(cls, v: float, info: Any) -> float:
        return _validate_intensity(v, info.field_name)

    @field_validator("version")
    @classmethod
    def validate_version_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("version must be greater than or equal to 1.")
        return v


class EmotionStateUpdate(BaseModel):
    """Immutable, validated partial replacement request for EmotionState.

    Used by trusted internal application subsystems (e.g. future Emotion Engine).
    Updates specify target values, NOT delta additions.
    Empty mutation requests with zero specified fields are rejected.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    emotion_type: EmotionType | None = None
    intensity: float | None = None

    @field_validator("intensity")
    @classmethod
    def validate_optional_intensity(cls, v: float | None, info: Any) -> float | None:
        if v is not None:
            return _validate_intensity(v, info.field_name)
        return None

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "EmotionStateUpdate":
        if self.emotion_type is None and self.intensity is None:
            raise ValueError("EmotionStateUpdate must contain at least one field to update.")
        return self


def create_initial_emotion_state(
    character_id: str = DEFAULT_CHARACTER_ID,
) -> EmotionState:
    """Construct the canonical initial EmotionState baseline for Aevum.

    Semantics:
    - Dominant emotion: NEUTRAL.
    - Baseline intensity: 0.50.
    - Version begins at 1.
    """
    now = utc_now()
    return EmotionState(
        id=str(uuid.uuid4()),
        character_id=character_id,
        emotion_type=BOOTSTRAP_EMOTION_TYPE,
        intensity=BOOTSTRAP_INTENSITY,
        created_at=now,
        updated_at=now,
        version=1,
    )
