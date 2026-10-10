"""
speech_act_models.py — Social Epistemics & Pragmatic Speech Act Contracts

Phase 15.1 Deliverable under ADR-026 (Architecture Gate Approved & Frozen):
- Categorical speech act taxonomy (SpeechActKind: 12 discrete kinds).
- Dual-track pragmatic interpretation DTO (primary + secondary acts).
- Evaluation context schema with conversational history and discrepancy flags.
- Strict immutability (ConfigDict(frozen=True, extra="forbid")).
- Permanent Note A: Zero float confidence scores or pseudo-probabilities.
- Constitutional Lock 1: Interpretation != Reality.
- Constitutional Lock 2: Ambiguity must survive (UNKNOWN & ambiguity_flag).
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional, Sequence, Tuple
from pydantic import BaseModel, ConfigDict, Field, field_validator


class SpeechActKind(str, Enum):
    """Categorical classification of conversational speech acts."""

    ASSERTION = "ASSERTION"          # Sincere declarative proposition about self, character, or world
    QUESTION = "QUESTION"            # Inquiry seeking information or stance
    EMOTION = "EMOTION"              # Subjective affective venting, distress, joy, fatigue
    JOKE = "JOKE"                    # Humorous intent, banter, irony, absurdism
    SARCASM = "SARCASM"              # Ironical statement meaning the opposite of literal words
    HYPERBOLE = "HYPERBOLE"          # Deliberate exaggeration not meant to be taken literally
    METAPHOR = "METAPHOR"            # Figurative analogy or symbolic framing
    MEME = "MEME"                    # Pop-culture reference, subcultural trope, intentional crossing
    ROLEPLAY = "ROLEPLAY"            # Hypothetical or fictional framing ("What if I were at Hogwarts...")
    CORRECTION = "CORRECTION"        # Explicit amendment or admission of prior turn ("Actually I lied earlier")
    TEST = "TEST"                    # Social boundary or consistency probing
    UNKNOWN = "UNKNOWN"              # Undetermined / insufficient signal / genuine ambiguity


class PragmaticInterpretation(BaseModel):
    """Immutable result of speech act and pragmatic evaluation for a conversational turn."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    primary_act: SpeechActKind = Field(..., description="Dominant communicative act")
    secondary_act: Optional[SpeechActKind] = Field(None, description="Co-occurring act in compound utterances")
    social_tone: str = Field(..., description="Qualitative tonal descriptor: playful, exhausted, sarcastic, etc.")
    literal_proposition: Optional[str] = Field(None, description="Extracted surface proposition if parseable")
    pragmatic_intent_summary: str = Field(..., description="Non-canonical explanation for prompt context")
    ambiguity_flag: bool = Field(default=False, description="True if classification carries unresolved ambiguity")

    @field_validator("secondary_act")
    @classmethod
    def _validate_secondary_distinct(cls, v: Optional[SpeechActKind], info) -> Optional[SpeechActKind]:
        if v is not None and "primary_act" in info.data:
            if v == info.data["primary_act"]:
                raise ValueError("secondary_act must be distinct from primary_act if specified.")
        return v


class SpeechActEvaluationContext(BaseModel):
    """Immutable input context supplied to the SpeechActClassifier."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    user_text: str = Field(..., description="Raw user input text")
    conversation_history: Tuple[str, ...] = Field(default_factory=tuple, description="Recent conversation turns")
    known_world_discrepancy: bool = Field(default=False, description="True if text conflicts with World Knowledge")
    known_biography_discrepancy: bool = Field(default=False, description="True if text conflicts with Canonical Biography")
    relationship_teasing_permitted: bool = Field(default=True, description="Whether teasing is socially permissible")
    prior_turn_speech_act: Optional[SpeechActKind] = Field(None, description="Speech act of the preceding turn")

    @field_validator("conversation_history", mode="before")
    @classmethod
    def _coerce_history_tuple(cls, v: Any) -> Tuple[str, ...]:
        if isinstance(v, (list, tuple)):
            return tuple(str(x) for x in v)
        return tuple()
