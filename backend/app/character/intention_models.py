"""Turn intention domain models for Character Engine (Phase C)."""

import enum
from pydantic import BaseModel, ConfigDict, Field


class SituationalStance(str, enum.Enum):
    """Authoritative communicative stance adopted for the conversational turn."""

    AGREE_WARMLY = "AGREE_WARMLY"
    AGREE_RELUCTANTLY = "AGREE_RELUCTANTLY"
    NEUTRAL_INQUIRY = "NEUTRAL_INQUIRY"
    MILD_DEFENSIVENESS = "MILD_DEFENSIVENESS"
    POLITE_REFUSAL = "POLITE_REFUSAL"
    PLAYFUL_TEASING = "PLAYFUL_TEASING"
    DISTRACTED_BRIEF = "DISTRACTED_BRIEF"
    FOCUSED_BOUNDARY = "FOCUSED_BOUNDARY"
    CONCEDE_FACT = "CONCEDE_FACT"


class TurnIntention(BaseModel):
    """Concrete behavioral and communicative contract governing character speech generation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    stance: SituationalStance = Field(
        ...,
        description="Core situational stance for the turn.",
    )
    conversational_goal: str = Field(
        ...,
        description="Specific communicative objective the character must accomplish.",
    )
    forbidden_behaviors: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Actions or styles strictly disallowed during this turn.",
    )
    micro_reaction: str = Field(
        ...,
        description="Focal non-verbal or behavioral micro-reaction.",
    )
    desired_warmth: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Target warmth level on [0.0, 1.0].",
    )
    desired_directness: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Target directness/assertiveness level on [0.0, 1.0].",
    )
