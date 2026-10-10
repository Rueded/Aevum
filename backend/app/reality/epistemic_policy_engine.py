"""
epistemic_policy_engine.py — Pure Deterministic Cognitive Epistemic Policy Engine

Phase 15.2 Deliverable under ADR-026 (Architecture Gate Approved & Frozen):
- Pure deterministic policy mapping: EpistemicPolicyContext -> EpistemicTreatmentDecision.
- Maps speech acts and situational discrepancies to one of 10 EpistemicTreatmentKind values.
- Strictly adheres to Gate Review Watchpoint: ACCEPT_SOCIAL != Memory Writing.
  (Admitting an assertion into conversational working context grants ZERO authority
  to persist into long-term memory or canonical core reality.)
- Constitutional Lock 1: Ephemeral evaluation only; 0 DB, 0 set_fact, 0 PromotionAuthorizationToken.
- Constitutional Lock 2: Ambiguity Must Survive; SUSPEND_JUDGMENT preserves uncertainty without collapse.
- Constitutional Lock 5: Zero Lie-Detector Sycophancy.
- Constitutional Lock 6: Anti-Compensatory Hallucination (Zero fake bridge facts invented).
"""

from __future__ import annotations

from app.reality.epistemic_policy_models import (
    EpistemicPolicyContext,
    EpistemicTreatmentDecision,
    EpistemicTreatmentKind,
)
from app.reality.speech_act_models import SpeechActKind


class EpistemicPolicyEngine:
    """
    Cognitive policy engine deciding how an interpreted utterance is received by Aevum.

    Pure deterministic, synchronous evaluator with zero external network or database dependencies.
    """

    @classmethod
    def evaluate(cls, policy_context: EpistemicPolicyContext) -> EpistemicTreatmentDecision:
        """
        Evaluate conversational pragmatic interpretation and context to produce
        an immutable EpistemicTreatmentDecision.
        """
        interp = policy_context.interpretation
        eval_ctx = policy_context.evaluation_context
        primary = interp.primary_act

        # ---------------------------------------------------------------------
        # Rule 1: Lock 2 — Ambiguity Preservation (SUSPEND_JUDGMENT)
        # ---------------------------------------------------------------------
        if primary == SpeechActKind.UNKNOWN or interp.ambiguity_flag:
            return EpistemicTreatmentDecision(
                treatment=EpistemicTreatmentKind.SUSPEND_JUDGMENT,
                rationale="Ambiguous or undetermined speech act. Preserving uncertainty without premature commitment or confrontation.",
                working_context_accept=False,
                epistemic_uncertainty_flag=True,
            )

        # ---------------------------------------------------------------------
        # Rule 2: Explicit User Retraction / Correction (REVISE_INTERPRETATION)
        # ---------------------------------------------------------------------
        if primary == SpeechActKind.CORRECTION:
            return EpistemicTreatmentDecision(
                treatment=EpistemicTreatmentKind.REVISE_INTERPRETATION,
                rationale="User explicitly retracts or corrects prior statement. Directing belief revision pipeline to re-evaluate affected hypotheses.",
                working_context_accept=False,
            )

        # ---------------------------------------------------------------------
        # Rule 3: Roleplay / Hypothetical Narrative Sandbox (ENTER_FICTIONAL_FRAME)
        # ---------------------------------------------------------------------
        if primary == SpeechActKind.ROLEPLAY:
            return EpistemicTreatmentDecision(
                treatment=EpistemicTreatmentKind.ENTER_FICTIONAL_FRAME,
                rationale="User proposes fictional or hypothetical scenario. Confining propositions to ephemeral narrative sandbox.",
                working_context_accept=True,
            )

        # ---------------------------------------------------------------------
        # Rule 4: Extreme Hyperbole (DISCARD_LITERAL_HYPERBOLE)
        # ---------------------------------------------------------------------
        if primary == SpeechActKind.HYPERBOLE:
            return EpistemicTreatmentDecision(
                treatment=EpistemicTreatmentKind.DISCARD_LITERAL_HYPERBOLE,
                rationale="Extreme biological or temporal hyperbole detected. Discarding literal event while preserving emotional intensity.",
                working_context_accept=False,
            )

        # ---------------------------------------------------------------------
        # Rule 5: Emotional Affective Venting (ACKNOWLEDGE_EMOTIONAL)
        # ---------------------------------------------------------------------
        if primary == SpeechActKind.EMOTION:
            return EpistemicTreatmentDecision(
                treatment=EpistemicTreatmentKind.ACKNOWLEDGE_EMOTIONAL,
                rationale="Subjective emotional venting. Responding with presence and empathy without factual verification.",
                working_context_accept=True,
            )

        # ---------------------------------------------------------------------
        # Rule 6: Pop-Culture Meme, Subcultural Trope, or Boundary Test (BANTER_TEASE)
        # ---------------------------------------------------------------------
        if primary in (SpeechActKind.MEME, SpeechActKind.TEST):
            return EpistemicTreatmentDecision(
                treatment=EpistemicTreatmentKind.BANTER_TEASE,
                rationale="Pop-culture meme, trope, or boundary probe. Emitting playful reciprocal banter.",
                working_context_accept=True,
                teasing_tone_recommended=eval_ctx.relationship_teasing_permitted,
            )

        if primary == SpeechActKind.JOKE:
            if eval_ctx.relationship_teasing_permitted:
                return EpistemicTreatmentDecision(
                    treatment=EpistemicTreatmentKind.BANTER_TEASE,
                    rationale="Humorous joke or banter. Emitting playful reciprocal teasing.",
                    working_context_accept=True,
                    teasing_tone_recommended=True,
                )
            return EpistemicTreatmentDecision(
                treatment=EpistemicTreatmentKind.ACCEPT_SOCIAL,
                rationale="Humorous joke received within polite non-teasing relational boundary.",
                working_context_accept=True,
                teasing_tone_recommended=False,
            )

        # ---------------------------------------------------------------------
        # Rule 7: Sarcasm / Irony Inversion
        # ---------------------------------------------------------------------
        if primary == SpeechActKind.SARCASM:
            if interp.social_tone == "sarcastic_self_deprecating" and eval_ctx.relationship_teasing_permitted:
                return EpistemicTreatmentDecision(
                    treatment=EpistemicTreatmentKind.BANTER_TEASE,
                    rationale="Sarcastic self-deprecating irony detected. Emitting gentle humorous banter acknowledging user's frustration.",
                    working_context_accept=True,
                    teasing_tone_recommended=True,
                )
            return EpistemicTreatmentDecision(
                treatment=EpistemicTreatmentKind.ACKNOWLEDGE_EMOTIONAL,
                rationale="Sarcastic irony inverting negative reality. Acknowledging underlying frustration or distress.",
                working_context_accept=True,
            )

        # ---------------------------------------------------------------------
        # Rule 8: Figurative Metaphor (ACCEPT_SOCIAL)
        # ---------------------------------------------------------------------
        if primary == SpeechActKind.METAPHOR:
            return EpistemicTreatmentDecision(
                treatment=EpistemicTreatmentKind.ACCEPT_SOCIAL,
                rationale="Figurative metaphor detected. Admitted symbolically into conversational working context; literal entity generation suppressed.",
                working_context_accept=True,
            )

        # ---------------------------------------------------------------------
        # Rule 9: Inquiry / Question (ACCEPT_SOCIAL)
        # ---------------------------------------------------------------------
        if primary == SpeechActKind.QUESTION:
            return EpistemicTreatmentDecision(
                treatment=EpistemicTreatmentKind.ACCEPT_SOCIAL,
                rationale="User inquiry seeking character stance or factual information. Proceeding with conversational reply.",
                working_context_accept=True,
            )

        # ---------------------------------------------------------------------
        # Rule 10: Declarative Assertion Sub-Branches
        # ---------------------------------------------------------------------
        if primary == SpeechActKind.ASSERTION:
            # Sub-branch 10a: Spatial-Temporal Tension (e.g. GC-383 commute tension)
            if policy_context.has_spatial_temporal_tension:
                return EpistemicTreatmentDecision(
                    treatment=EpistemicTreatmentKind.CLARIFY_INQUIRE,
                    rationale="Spatial-temporal tension detected (e.g. extreme daily commute). Emitting conversational inquiry before reality modification.",
                    working_context_accept=False,
                    requires_repair_inquiry=True,
                    teasing_tone_recommended=eval_ctx.relationship_teasing_permitted,
                )

            # Sub-branch 10b: High-Impact External World Claim (e.g. GC-387 university closure)
            if policy_context.is_high_impact_claim:
                return EpistemicTreatmentDecision(
                    treatment=EpistemicTreatmentKind.DISPATCH_VERIFICATION,
                    rationale="High-impact external institutional proposition. Dispatching verification request to Phase 9 Gateway before reality commitment.",
                    working_context_accept=False,
                    dispatch_verification_recommended=True,
                )

            # Sub-branch 10c: Direct World Knowledge Contradiction (e.g. GC-381 USM in KL)
            if eval_ctx.known_world_discrepancy:
                return EpistemicTreatmentDecision(
                    treatment=EpistemicTreatmentKind.WORLD_CONTRADICTION,
                    rationale="Direct contradiction with canonical World Knowledge. Initiating gentle conversational correction/inquiry without world registry pollution.",
                    working_context_accept=False,
                    requires_repair_inquiry=True,
                )

            # Sub-branch 10d: Known Canonical Biography Discrepancy (e.g. GC-392 chef contradiction)
            if eval_ctx.known_biography_discrepancy:
                return EpistemicTreatmentDecision(
                    treatment=EpistemicTreatmentKind.CLARIFY_INQUIRE,
                    rationale="Tension detected with established biography or prior user assertion. Emitting respectful conversational inquiry.",
                    working_context_accept=False,
                    requires_repair_inquiry=True,
                )

            # Sub-branch 10e: Low-Consequence / Consistent Personal Claim (e.g. GC-379 chicken rice, GC-382 live in KL)
            # WATCHPOINT: Admitted into current working context for natural dialogue, ZERO memory writing.
            return EpistemicTreatmentDecision(
                treatment=EpistemicTreatmentKind.ACCEPT_SOCIAL,
                rationale="Low-consequence consistent assertion. Admitted into conversational working context for natural dialogue.",
                working_context_accept=True,
            )

        # ---------------------------------------------------------------------
        # Fallback Ambiguity Preservation (Lock 2)
        # ---------------------------------------------------------------------
        return EpistemicTreatmentDecision(
            treatment=EpistemicTreatmentKind.SUSPEND_JUDGMENT,
            rationale="Unresolved epistemic stance. Preserving uncertainty without forced collapse.",
            working_context_accept=False,
            epistemic_uncertainty_flag=True,
        )
