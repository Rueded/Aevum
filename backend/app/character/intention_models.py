"""Turn intention domain models for Character Engine (Phase C)."""

import enum
from typing import Any, Optional
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


# --- Phase 7B.2 Social Intention Engine Models ---


class BehaviorPrimitive(str, enum.Enum):
    """Universal social/conversational behavior primitive move."""

    ANSWER = "ANSWER"
    ASK = "ASK"
    ACCEPT = "ACCEPT"
    DECLINE = "DECLINE"
    NEGOTIATE = "NEGOTIATE"
    COMPROMISE = "COMPROMISE"
    TEASE = "TEASE"
    REASSURE = "REASSURE"
    CHALLENGE = "CHALLENGE"
    SET_BOUNDARY = "SET_BOUNDARY"
    SELF_DISCLOSE = "SELF_DISCLOSE"
    REDIRECT = "REDIRECT"
    DISENGAGE = "DISENGAGE"
    RECONNECT = "RECONNECT"


class SocialPosture(str, enum.Enum):
    """Affective and interpersonal posture adopted for the turn."""

    WARM_ENGAGED = "WARM_ENGAGED"
    RELAXED_NEUTRAL = "RELAXED_NEUTRAL"
    GUARDED_POLITE = "GUARDED_POLITE"
    PLAYFUL_TEASING = "PLAYFUL_TEASING"
    DISTANT_HURT = "DISTANT_HURT"
    FIRM_BOUNDARY = "FIRM_BOUNDARY"
    MILD_DEFENSIVE = "MILD_DEFENSIVE"


class ParticipationLevel(str, enum.Enum):
    """Level of participation or buy-in the character commits to."""

    FULL = "FULL"
    CONDITIONAL = "CONDITIONAL"
    MINIMAL = "MINIMAL"
    DECLINED = "DECLINED"


class SocialIntention(BaseModel):
    """Structured social decision prior to behavior planning and LLM generation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    primary_move: BehaviorPrimitive = Field(
        ...,
        description="Core behavioral primitive move for the turn.",
    )
    social_posture: SocialPosture = Field(
        default=SocialPosture.RELAXED_NEUTRAL,
        description="Affective posture towards user.",
    )
    participation: ParticipationLevel = Field(
        default=ParticipationLevel.FULL,
        description="Level of commitment or agreement.",
    )
    disclosure_level: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Permissible depth of self-disclosure [0.0, 1.0].",
    )
    warmth: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Target social warmth [0.0, 1.0].",
    )
    directness: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Target communicative directness [0.0, 1.0].",
    )
    initiative: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Degree of active conversational driving [0.0, 1.0].",
    )
    reciprocity: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Effort to balance conversational reciprocity [0.0, 1.0].",
    )
    boundary_strength: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Vigilance in maintaining boundaries [0.0, 1.0].",
    )
    compromise_level: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Multi-state calculated compromise level [0.0, 1.0].",
    )
    conversation_hook: Optional[str] = Field(
        default=None,
        description="Optional high-level conversational intention directive for the planner.",
    )

