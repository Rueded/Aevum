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
    CharacterCoreAnchor,
    CharacterDefinition,
    CharacterIdentity,
    CharacterSurfacePersona,
    Personality,
    Preference,
)
from app.character.state_models import CharacterMood, CharacterState
from app.emotion.emotion_models import EmotionState, EmotionType
from app.memory.context_builder import build_memory_context
from app.memory.models import HybridMemoryResult, Memory, MemoryCategory
from app.relationship.context_models import RelationshipContext
from app.life.context_models import CharacterLifeContext
from app.life.presence import PresenceState
from app.relationship.models import RelationshipState
from app.world.models import PersonalWorldContext
from app.character.bible_models import CharacterBible
from app.character.core_models import CharacterCore
from app.character.intention_models import (
    BehaviorPrimitive,
    SituationalStance,
    SocialIntention,
    SocialPosture,
    TurnIntention,
)
from app.character.desire_models import CharacterDesireState
from app.relationship.contract_models import RelationshipContract
from app.character.behavior_plan_models import BehaviorDecisionTrace, BehaviorPlan
from app.reality.ledger_models import RealityLedgerProjection
from app.reality.belief_models import BeliefClaim
from app.reality.contradiction_models import ContradictionResolution
from app.reality.promotion_models import PromotionDecision
from app.character.reality_context_models import GovernedRealityContext


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
    core_anchor: Optional[CharacterCoreAnchor] = Field(
        default=None,
        description="Immutable core anchor.",
    )
    surface_persona: Optional[CharacterSurfacePersona] = Field(
        default=None,
        description="Surface persona and evolving expression.",
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
            core_anchor=definition.core_anchor,
            surface_persona=definition.surface_persona,
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


class MemoryExperienceContext(BaseModel):
    """Immutable semantic guidance derived from retrieved memories."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    continuity_hints: tuple[str, ...] = Field(
        ...,
        description="Qualitative behavioral hints about how to naturally use these memories.",
    )

    @classmethod
    def synthesize(
        cls,
        memories: Optional[Sequence[Union[HybridMemoryResult, Memory]]] = None,
    ) -> "MemoryExperienceContext":
        """Synthesize behavioral continuity hints from retrieved memory characteristics."""
        hints = []
        if not memories:
            return cls(continuity_hints=())

        has_low_confidence = False
        has_high_confidence = False
        has_high_importance = False
        categories = set()

        for item in memories:
            mem = item.memory if isinstance(item, HybridMemoryResult) else item
            categories.add(mem.category)

            if mem.confidence < 0.4:
                has_low_confidence = True
            elif mem.confidence > 0.8:
                has_high_confidence = True

            if mem.importance > 0.7:
                has_high_importance = True

        if has_low_confidence:
            hints.append("Some retrieved memories are marked as low-confidence. Use them cautiously and express uncertainty naturally (e.g., 'I vaguely recall...'). Do not assert them as absolute fact.")
        
        if has_high_confidence:
            hints.append("You have strongly established memories relevant to this context. You may treat them as established context if appropriate.")

        if has_high_importance:
            hints.append("Some retrieved memories are marked as highly important. If contextually relevant, you may give them stronger continuity significance.")

        if MemoryCategory.USER_GOAL in categories:
            hints.append("A relevant user goal was retrieved. When contextually appropriate, you may naturally follow up or reference their progress.")

        if MemoryCategory.USER_PROBLEM in categories:
            hints.append("A past user problem or concern was retrieved. You may gently check in or keep it in mind if it relates to their current situation.")

        if MemoryCategory.EVENT in categories:
            hints.append("A past event is relevant. You can naturally provide continuity by referencing it if the user brings up related topics.")

        if MemoryCategory.PREFERENCE in categories:
            hints.append("A known user preference is relevant. You may let this influence your recommendations or choices without awkwardly pointing out that you remembered it.")

        if MemoryCategory.PROMISE in categories:
            hints.append("A previous promise or commitment is relevant. Treat this with stronger continuity significance.")

        if MemoryCategory.JOKE in categories:
            hints.append("A shared inside joke was retrieved. You may enable a natural callback if the timing is right, but do not force it.")

        if MemoryCategory.CHARACTER_EVENT in categories:
            hints.append("One of your own past personal experiences is relevant. You may naturally reference your own history if it relates to the conversation.")

        if not hints:
            hints.append("Use the retrieved memories naturally as background context. Do not force them into the conversation if they are not directly relevant.")

        hints.append("Important: Memory is context, not a database dump. Do not explicitly announce that you are looking at your memory database.")

        return cls(continuity_hints=tuple(hints))


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
    experience: MemoryExperienceContext = Field(
        ...,
        description="Synthesized memory experience guidance.",
    )

    @classmethod
    def from_memories(
        cls,
        memories: Optional[Sequence[Union[HybridMemoryResult, Memory]]] = None,
    ) -> "CharacterMemoryContext":
        """Construct context directly from retrieved memories sequence."""
        if not memories:
            return cls(
                memories=(),
                context_block=None,
                experience=MemoryExperienceContext.synthesize(None),
            )
        contents: list[str] = []
        for item in memories:
            mem = item.memory if isinstance(item, HybridMemoryResult) else item
            contents.append(mem.content)
        context_block = build_memory_context(memories)
        return cls(
            memories=tuple(contents),
            context_block=context_block,
            experience=MemoryExperienceContext.synthesize(memories),
        )


class CharacterBehaviorContext(BaseModel):
    """Immutable semantic guidance derived from mood, emotion, and relationship state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    behavioral_hints: tuple[str, ...] = Field(
        ...,
        description="Qualitative behavioral hints reflecting current state.",
    )
    intention: Optional[TurnIntention] = Field(
        default=None,
        description="Authoritative situational stance and turn intention.",
    )

    @classmethod
    def synthesize(
        cls,
        state: CharacterStateContext,
        emotion: CharacterEmotionContext,
        intention: Optional[TurnIntention] = None,
    ) -> "CharacterBehaviorContext":
        """Synthesize behavioral hints from current domain states."""
        hints = []

        # Energy/Mood driven hints
        if state.energy < 0.3:
            hints.append("You are feeling physically or mentally exhausted. Keep responses relatively brief and lower-energy.")
        elif state.energy > 0.8:
            hints.append("You are feeling highly energetic and alert. Your tone can be more animated or enthusiastic.")

        if state.stress > 0.7:
            hints.append("You are currently highly stressed. Your tone may be terse, anxious, or distracted.")

        # Emotion driven hints
        emo_type = emotion.emotion_type.value
        if emotion.intensity >= 0.6:
            hints.append(f"Your dominant emotion is {emo_type}. Let this strongly color your word choice and focus.")
        elif emotion.intensity >= 0.3:
            hints.append(f"Your dominant emotion is {emo_type}. Let this subtly influence your tone.")

        # Relationship guidance is handled authoritatively by RelationshipContext,
        # ensuring no raw scores leak here and removing duplicated logic.

        if not hints:
            hints.append("Maintain your baseline personality and conversational tone.")

        return cls(behavioral_hints=tuple(hints), intention=intention)


class CharacterResponseContext(BaseModel):
    """Immutable aggregate representing gathered context for response decision making."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    user_input: str = Field(..., description="Current user input query or statement.")
    character: CharacterDefinitionContext = Field(..., description="Character identity and personality context.")
    character_state: CharacterStateContext = Field(..., description="Current character physiological and situational state.")
    relationship: RelationshipContext = Field(..., description="Current qualitative relationship context.")
    emotion: CharacterEmotionContext = Field(..., description="Current emotional state context.")
    memory: CharacterMemoryContext = Field(..., description="Relevant memory context.")
    behavior: CharacterBehaviorContext = Field(..., description="Synthesized behavioral cues and hints.")
    life: CharacterLifeContext = Field(..., description="Current factual life context.")
    personal_world: Optional[PersonalWorldContext] = Field(default=None, description="Personal world and epistemic context.")
    presence: Optional[PresenceState] = Field(default=None, description="Current presence and absence dynamics.")
    core: Optional[CharacterCore] = Field(default=None, description="Authoritative Character Core reality facts.")
    bible: Optional[CharacterBible] = Field(default=None, description="Authoritative Character Bible behavioral and reasoning priors.")
    ledger: Optional[RealityLedgerProjection] = Field(default=None, description="Reality Ledger multi-tier projection.")
    desire: Optional[CharacterDesireState] = Field(default=None, description="Authoritative Character Desire & Need state.")
    contract: Optional[RelationshipContract] = Field(default=None, description="Authoritative Relationship Contract.")
    social_intention: Optional[SocialIntention] = Field(default=None, description="Authoritative Social Intention decision.")
    behavior_plan: Optional[BehaviorPlan] = Field(default=None, description="Authoritative Behavior Plan.")
    decision_trace: Optional[BehaviorDecisionTrace] = Field(default=None, description="Structured explainable decision trace.")
    belief_claim: Optional[BeliefClaim] = Field(default=None, description="Authoritative active BeliefClaim under evaluation.")
    contradiction_resolution: Optional[ContradictionResolution] = Field(default=None, description="Active contradiction resolution and repair strategy.")
    promotion_decision: Optional[PromotionDecision] = Field(default=None, description="Active reality promotion policy decision.")
    governed_reality: Optional[GovernedRealityContext] = Field(default=None, description="Authoritative Governed Reality Context (Phase 7D.4).")

