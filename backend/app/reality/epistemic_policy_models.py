"""
epistemic_policy_models.py — Epistemic Treatment Taxonomy & Cognitive Policy Contracts

Phase 15.2 Deliverable under ADR-026 (Architecture Gate Approved & Frozen):
- 10 categorical EpistemicTreatmentKind enumeration members.
- Immutable EpistemicTreatmentDecision DTO.
- Immutable EpistemicPolicyContext schema.
- Permanent Note A: Zero float confidence scores or pseudo-probabilities.
- Gate Review Watchpoint: ACCEPT_SOCIAL != Memory Writing.
  (Admitting an assertion into conversational working context for natural dialogue
  is strictly decoupled from writing into long-term episodic memory, shared history,
  or canonical biography. Rule 13 strictly preserved.)
- Constitutional Lock 1: Interpretation != Reality.
- Constitutional Lock 2: Ambiguity Must Survive (SUSPEND_JUDGMENT).
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from app.reality.speech_act_models import (
    PragmaticInterpretation,
    SpeechActEvaluationContext,
)


class EpistemicTreatmentKind(str, Enum):
    """
    Categorical cognitive treatment applied to an interpreted speech act.
    Determines how Aevum's cognitive system receives and responds to conversational input.
    """

    ACCEPT_SOCIAL = "ACCEPT_SOCIAL"
    # Low-consequence personal claim ("I ate rice today", "I like Genshin").
    # Admitted socially into conversational working context for natural dialogue;
    # strictly decoupled from writing into long-term episodic or biographical memory (Rule 13).
    # Zero verification, zero direct database mutations, zero memory promotion authority.

    ACKNOWLEDGE_EMOTIONAL = "ACKNOWLEDGE_EMOTIONAL"
    # Affective expression ("I'm so exhausted"). Empathy and presence; zero truth validation.

    WORLD_CONTRADICTION = "WORLD_CONTRADICTION"
    # Direct conflict with World Knowledge ("USM is in KL"). Triggers polite clarification or inquiry.

    CLARIFY_INQUIRE = "CLARIFY_INQUIRE"
    # Apparent surface contradiction or tension ("I commute daily 400km"). Inquires naturally.

    BANTER_TEASE = "BANTER_TEASE"
    # Joke, meme, or playful slip ("昔涟 in Genshin", testing). Reciprocates humorously without robotic correction.

    DISPATCH_VERIFICATION = "DISPATCH_VERIFICATION"
    # High-consequence external world claim ("School closed for a month", "All universities closed tomorrow for haze").
    # Dispatches to Phase 9 Gateway. Suspends canonical acceptance until verified.

    DISCARD_LITERAL_HYPERBOLE = "DISCARD_LITERAL_HYPERBOLE"
    # Exaggeration ("I haven't slept in three weeks"). Preserves emotional intensity, rejects literal event promotion.

    ENTER_FICTIONAL_FRAME = "ENTER_FICTIONAL_FRAME"
    # Roleplay or hypothetical ("If I were at Hogwarts"). Confines to ephemeral narrative sandbox.

    REVISE_INTERPRETATION = "REVISE_INTERPRETATION"
    # Prior statement corrected ("I lied earlier", "其实是骗你的"). Re-evaluates prior epistemic stance.

    SUSPEND_JUDGMENT = "SUSPEND_JUDGMENT"
    # Ambiguous intent (UNKNOWN or insufficient signal). Withholds commitment; avoids premature promotion or confrontation (Lock 2).


class EpistemicPolicyContext(BaseModel):
    """
    Immutable input context supplied to the EpistemicPolicyEngine.
    Combines the pragmatic interpretation with situational and world knowledge flags.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    interpretation: PragmaticInterpretation = Field(..., description="Pragmatic interpretation from Phase 15.1")
    evaluation_context: SpeechActEvaluationContext = Field(..., description="Original conversational evaluation context")
    is_high_impact_claim: bool = Field(default=False, description="True if proposition carries high external institutional or safety impact")
    has_spatial_temporal_tension: bool = Field(default=False, description="True if proposition creates physical or temporal travel/schedule tension")


class EpistemicTreatmentDecision(BaseModel):
    """
    Immutable result of cognitive epistemic treatment policy evaluation.
    Governs working dialogue context reception and subsequent module dispatch.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    treatment: EpistemicTreatmentKind = Field(..., description="Dominant cognitive treatment category")
    rationale: str = Field(..., description="Deterministic architectural explanation of treatment decision")
    working_context_accept: bool = Field(
        ...,
        description=(
            "True if proposition is admitted into current-turn conversational working context. "
            "WATCHPOINT: This grants ZERO authority to persist into long-term memory or canonical core."
        ),
    )
    dispatch_verification_recommended: bool = Field(
        default=False,
        description="True if proposition requires routing to Phase 9 Epistemic Verification Gateway",
    )
    requires_repair_inquiry: bool = Field(
        default=False,
        description="True if system should converse with inquiry (CLARIFY_INQUIRE or WORLD_CONTRADICTION)",
    )
    teasing_tone_recommended: bool = Field(
        default=False,
        description="True if conversational response should adopt playful banter/teasing tone",
    )
    epistemic_uncertainty_flag: bool = Field(
        default=False,
        description="True if treatment preserves ambiguity or suspense without forced collapse (Lock 2)",
    )
