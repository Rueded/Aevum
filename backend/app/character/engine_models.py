"""Character engine response context models for Aevum Core.

Defines the structured, immutable, provider-neutral context models representing
gathered character, relational, emotional, and memory state for response decision making:
User Input
    ↓
CharacterEngine
├── CharacterDefinition
├── CharacterState
├── Relevant Memory Context
├── Relationship Context
└── Emotion Context
    ↓
CharacterResponseContext

Guarantees:
- Fully immutable domain representation (frozen=True, extra="forbid").
- Zero raw persistence/ORM details (no SQLAlchemy sessions, records, IDs, version counters).
- Safe to serialize.
- Bounded semantic representations of character identity, state, relationship, and emotion.
"""

import math
from typing import Optional, Sequence, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.character.models import (
    Boundary,
    CharacterDefinition,
    CharacterIdentity,
    Personality,
    Preference,
)
from app.character.state_models import CharacterMood, CharacterState
from app.emotion.emotion_models import EmotionState, EmotionType
from app.memory.context_builder import build_memory_context
from app.memory.models import HybridMemoryResult, Memory
from app.relationship.context_models import RelationshipContext


class CharacterDefinitionContext(BaseModel):
    """Immutable semantic context for character identity, personality, preferences, and boundaries."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., description="Character name.")
    identity: CharacterIdentity = Field(..., description="Foundational character identity.")
    personality: Personality = Field(..., description="Structured personality tendencies.")
    preferences: tuple[Preference, ...] = Field(
        default_factory=tuple,
        description="Character preferences independent of the user.",
    )
    boundaries: tuple[Boundary, ...] = Field(
        default_factory=tuple,
        description="Persistent behavioral boundaries.",
    )

    @classmethod
    def from_definition(cls, definition: CharacterDefinition) -> "CharacterDefinitionContext":
        """Construct context directly from authoritative CharacterDefinition."""
        return cls(
            name=definition.identity.name,
            identity=definition.identity,
            personality=definition.personality,
            preferences=definition.preferences,
            boundaries=definition.boundaries,
        )


class CharacterStateContext(BaseModel):
    """Immutable semantic context for current mutable character condition and situational context."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mood: CharacterMood = Field(..., description="Current qualitative mood.")
    energy: float = Field(..., description="Current physical/mental energy level in [0.0, 1.0].")
    stress: float = Field(..., description="Current stress level in [0.0, 1.0].")
    social_energy: float = Field(..., description="Current social energy level in [0.0, 1.0].")
    confidence: float = Field(..., description="Current situational confidence in [0.0, 1.0].")
    irritation: float = Field(..., description="Current situational irritation in [0.0, 1.0].")
    loneliness: float = Field(..., description="Current subjective loneliness in [0.0, 1.0].")
    current_activity: str = Field(..., description="Current activity description.")
    current_location: str = Field(..., description="Current location description.")

    @field_validator("energy", "stress", "social_energy", "confidence", "irritation", "loneliness")
    @classmethod
    def validate_metric(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v) or v < 0.0 or v > 1.0:
            raise ValueError("Metric must be a finite float in [0.0, 1.0].")
        return float(v)

    @classmethod
    def from_state(cls, state: CharacterState) -> "CharacterStateContext":
        """Construct context directly from authoritative CharacterState."""
        return cls(
            mood=state.mood,
            energy=state.energy,
            stress=state.stress,
            social_energy=state.social_energy,
            confidence=state.confidence,
            irritation=state.irritation,
            loneliness=state.loneliness,
            current_activity=state.current_activity,
            current_location=state.current_location,
        )


def format_emotion_summary(emotion_type: EmotionType, intensity: float) -> str:
    """Produce a concise semantic interpretation of current emotional state for response generation."""
    name = emotion_type.value.lower()
    if intensity < 0.30:
        descriptor = "mild"
    elif intensity <= 0.70:
        descriptor = "moderate"
    else:
        descriptor = "strong"
    return f"Aevum is currently feeling {name} with {descriptor} intensity ({intensity:.2f})."


class CharacterEmotionContext(BaseModel):
    """Immutable semantic context for current emotional affect and intensity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    emotion_type: EmotionType = Field(
        ...,
        description="Current authoritative dominant emotion type.",
    )
    intensity: float = Field(
        ...,
        description="Continuous intensity of current emotion in [0.0, 1.0].",
    )
    summary: str = Field(
        ...,
        description="Concise semantic interpretation of the emotional state for response generation.",
    )

    @field_validator("intensity")
    @classmethod
    def validate_intensity(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v) or v < 0.0 or v > 1.0:
            raise ValueError("intensity must be a finite float in [0.0, 1.0].")
        return float(v)

    @classmethod
    def from_state(cls, state: EmotionState) -> "CharacterEmotionContext":
        """Construct context directly from authoritative EmotionState."""
        return cls(
            emotion_type=state.emotion_type,
            intensity=state.intensity,
            summary=format_emotion_summary(state.emotion_type, state.intensity),
        )


class CharacterMemoryContext(BaseModel):
    """Immutable semantic context for retrieved relevant memories."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    memories: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Retrieved memory contents relevant to user input.",
    )
    context_block: Optional[str] = Field(
        default=None,
        description="Formatted XML memory context block for LLM grounding (if memories fit budget).",
    )

    @classmethod
    def from_memories(
        cls,
        memories: Optional[Sequence[Union[HybridMemoryResult, Memory]]] = None,
    ) -> "CharacterMemoryContext":
        """Construct context directly from retrieved memories sequence."""
        if not memories:
            return cls(memories=(), context_block=None)
        contents: list[str] = []
        for item in memories:
            mem = item.memory if isinstance(item, HybridMemoryResult) else item
            contents.append(mem.content)
        context_block = build_memory_context(memories)
        return cls(memories=tuple(contents), context_block=context_block)


class CharacterResponseContext(BaseModel):
    """Immutable aggregate representing gathered context for response decision making."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    user_input: str = Field(..., description="Current user input query or statement.")
    character: CharacterDefinitionContext = Field(..., description="Character identity and personality context.")
    character_state: CharacterStateContext = Field(..., description="Current character physiological and situational state.")
    relationship: RelationshipContext = Field(..., description="Current qualitative relationship context.")
    emotion: CharacterEmotionContext = Field(..., description="Current emotional state context.")
    memory: CharacterMemoryContext = Field(..., description="Relevant memory context.")
