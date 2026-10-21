"""Conversational Life & Character Conversational Decision Flow (CCDF) Models (Phase 18.1).

Defines compact, machine-parseable conversational decision metadata and contracts,
adhering strictly to Constitutional Locks GC-425 through GC-431.
"""

from enum import Enum
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ResponseCommitmentTier(str, Enum):
    """How much conversational effort the character commits to this turn.

    Constitutional Lock GC-428 / GC-430:
    A character possesses the agency to NOT expand (ZERO_EXPANSION) or offer minimal
    reaction without feeling compelled to maintain artificial momentum.
    """
    ZERO_EXPANSION = "ZERO_EXPANSION"      # Pure emotional/acknowledgment closure (e.g., "笑死", "好羡慕", "嗯。")
    LOW_EFFORT = "LOW_EFFORT"              # Casual short quip or minimal conversational acknowledgment
    PARTIAL_FLOW = "PARTIAL_FLOW"          # Picked a single interest point to engage naturally
    DEEP_ENGAGEMENT = "DEEP_ENGAGEMENT"    # Substantial personal sharing, in-depth discussion, or attentive presence


class ResponseEnergyTier(str, Enum):
    """Current conversational vitality and burst tempo.

    Constitutional Lock GC-427:
    ResponseEnergy is strictly turn-scoped and disposable (ephemeral).
    It MUST NOT be persisted as a durable personality trait, long-term mood,
    relationship scalar, or permanent state.
    """
    VERY_LOW = "VERY_LOW"   # Fatigued / quiet / minimal response
    LOW = "LOW"             # Relaxed / idle / brief
    NORMAL = "NORMAL"       # Steady everyday presence
    ENGAGED = "ENGAGED"     # Genuinely interested by specific subject
    EXCITED = "EXCITED"     # Enthusiastic / rapid / expressive burst


class FrictionTier(str, Enum):
    """Allowed behavioral friction conditioned by relationship familiarity and integrity.

    Constitutional Lock GC-428:
    Friction is a natural component of closeness (playful teasing, eye-rolling,
    holding ground), not random toxicity or universal hostility.
    """
    POLITE_DISTANT = "POLITE_DISTANT"            # Restraint, polite boundaries for new acquaintances
    PLAYFUL_TEASE = "PLAYFUL_TEASE"              # Affectionate teasing, playful pushback, mild eye-rolling
    STUBBORN_OPPOSITION = "STUBBORN_OPPOSITION"  # Independent stance, refusing to sycophantically agree


class ConversationalMotivation(str, Enum):
    """Why the character chooses to speak this turn.

    Constitutional Lock GC-430 (Agency Over Performance):
    Conversation acts must be grounded in an authentic personal reason to speak,
    not a robotic task of answering every user slot.
    """
    TEASE_AND_ROAST = "TEASE_AND_ROAST"         # Playful ribbing of user's misfortune or silliness
    COMMISERATE_VENT = "COMMISERATE_VENT"       # Shared frustration against outside annoyances
    DEFEND_OWN_BIAS = "DEFEND_OWN_BIAS"         # Standing by idiosyncratic preferences (no hedging/preaching)
    PLAYFUL_ROLEPLAY = "PLAYFUL_ROLEPLAY"       # Banter, dramatic exaggeration, playful back-and-forth
    GENUINE_SHARING = "GENUINE_SHARING"         # Spontaneous self-disclosure of personal events/thoughts
    SPONTANEOUS_INITIATIVE = "SPONTANEOUS_INITIATIVE" # Spontaneous unprompted sharing of own activity, thought, or story
    ASSOCIATIVE_DRIFT = "ASSOCIATIVE_DRIFT"           # Branching/linking from user's remark to own lived experience
    AFFECTIVE_SOUNDBITE = "AFFECTIVE_SOUNDBITE" # Immediate emotional resonance (pity, envy, amusement)
    COMFORTABLE_CLOSE = "COMFORTABLE_CLOSE"     # Natural period/closure, giving space without interrogating


class TurnConversationalDecision(BaseModel):
    """Compact machine-parseable conversational decision metadata (Phase 18.1).

    Constitutional Locks:
    - GC-425: curiosity is a motivation flag, never a runtime hard prohibition.
    - GC-426: Zero target_bubble_count; message count emerges in surface realization.
    - GC-427: ResponseEnergy is disposable and turn-scoped; zero durable trait bleed.
    - GC-431: Compact structured metadata, strictly NOT a Chain-of-Thought reasoning essay.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    # 1. Attention & Immediate Affect
    attention: str = Field(
        ...,
        max_length=120,
        description="The specific fragment, detail, or topic the character genuinely locked onto.",
    )
    reaction: str = Field(
        ...,
        max_length=120,
        description="Core spontaneous affect/reaction anchor (e.g. 'amused_by_bad_food', 'baffled_by_alarm').",
    )

    # 2. Commitment & Vitality
    commitment: ResponseCommitmentTier = Field(
        ...,
        description="Cognitive effort tier committed to this turn (GC-430).",
    )
    energy: ResponseEnergyTier = Field(
        ...,
        description="Turn-scoped disposable vitality tier (GC-427).",
    )

    # 3. Motivation & Friction
    motivation: ConversationalMotivation = Field(
        ...,
        description="Core human motive for opening mouth this turn.",
    )
    friction: FrictionTier = Field(
        ...,
        description="Familiarity-conditioned friction level.",
    )

    # 4. Curiosity & Selective Scope
    curiosity: bool = Field(
        default=False,
        description="True if motivated by genuine curiosity; GC-425 compliant (not a runtime lock).",
    )
    ignored_elements: list[str] = Field(
        default_factory=list,
        description="User points naturally left unaddressed in this turn.",
    )
    momentum_anchor: Optional[str] = Field(
        default=None,
        max_length=120,
        description="Connection to ongoing topic, recent callback, or unclosed loop.",
    )

    @field_validator("reaction", "attention", mode="after")
    @classmethod
    def validate_compact_metadata(cls, v: str) -> str:
        """Enforces GC-431: Rejects verbose Chain-of-Thought reasoning essays."""
        stripped = v.strip()
        if len(stripped) > 120 or "\n" in stripped:
            raise ValueError(
                f"GC-431 Violation: Metadata must be compact (<120 chars, single-line non-CoT). Got: '{v[:60]}...'"
            )
        return stripped


class ConversationalMomentumState(BaseModel):
    """Tracks active conversational dynamics across recent turns (Phase 18.2)."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    active_topic_anchor: Optional[str] = Field(default=None, max_length=120)
    unresolved_threads: list[str] = Field(default_factory=list)
    running_in_jokes: list[str] = Field(default_factory=list)
    recent_friction_history: list[FrictionTier] = Field(default_factory=list)
    consecutive_low_effort_turns: int = Field(default=0, ge=0)


class CharacterExpressionSignature(BaseModel):
    """Linguistic and conversational expression habits for an individual character.

    Constitutional Lock GC-428 / GC-430:
    Expression signature is NOT a demographic stereotype (e.g. '21yo art girl -> cute laugh').
    It reflects emergent personal habits: laugh forms, punctuation, and idioms.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    laugh_habits: list[str] = Field(
        default_factory=lambda: ["哈哈", "噗", "（笑）"],
        description="Individual laugh patterns",
    )
    teasing_style: str = Field(
        default="gentle_irony",
        description="Personal nuance for playful friction",
    )
    stubborn_quirks: list[str] = Field(
        default_factory=list,
        description="Personal stubborn tastes (e.g. morning person, dislikes cilantro)",
    )
    punctuation_style: str = Field(
        default="natural_pauses",
        description="Cadence and breathing habit (dots, dashes, breaks)",
    )
    soundbite_lexicon: list[str] = Field(
        default_factory=lambda: ["好羡慕", "救命", "笑死", "这倒也是"],
        description="Zero-information affective reactions",
    )


class TurnMessageItem(BaseModel):
    """An individual message bubble in a conversational turn (Phase 3)."""
    type: Literal["text", "sticker", "photo"] = Field(
        description="Type of the message: 'text', 'sticker', or 'photo'."
    )
    text: Optional[str] = Field(
        default=None,
        description="Text content of the bubble when type is 'text'.",
    )
    sticker_id: Optional[str] = Field(
        default=None,
        description="Sticker identifier or descriptive name when type is 'sticker'.",
    )
    photo_id: Optional[str] = Field(
        default=None,
        description="Photo ID or scene reference when type is 'photo'.",
    )


class StructuredTurnOutput(BaseModel):
    """Structured response container for character turn output (Phase 3)."""
    messages: List[TurnMessageItem] = Field(
        default_factory=list,
        description="Sequential list of message bubbles. Can be empty for read-only silence.",
    )

