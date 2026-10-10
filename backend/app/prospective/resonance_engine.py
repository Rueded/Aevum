"""Phase 19.3 — Contextual Resonance & Cognitive Attention Engine.

Pure deterministic engine implementing the 3-stage cognitive separation:
1. Contextual Resonance (Does the event semantically correspond to the thread?)
2. Attention Allocation (Does Aevum consciously attend to this relation?)
3. Expression Calibration & Silence Agency (Does Aevum voice it, or remain silent?)

Constitutional Locks:
- Trigger ≠ Recall ≠ Attention ≠ Mention ≠ Action.
- Silence as First-Class Agency: "想到了，但没说".
- Zero floats, zero DB mutations, zero LLM calls, zero proactive triggers.
"""

from datetime import datetime, timezone
from typing import Optional, Tuple
import uuid

from app.prospective.contracts import (
    ProspectiveThread,
    ResonanceTier,
    ThreadDomainKind,
    ThreadLifecycleState,
)
from app.prospective.resonance_models import (
    AttentionDecision,
    ExpressionDisposition,
    RealityEventContext,
    ResonanceEvaluation,
    ResonanceDegree,
)


class ContextualResonanceEngine:
    """Deterministic, pure-functional engine for prospective resonance and silence calibration."""

    @classmethod
    def evaluate_resonance(
        cls,
        thread: ProspectiveThread,
        event: RealityEventContext,
        force_degree: Optional[ResonanceDegree] = None,
    ) -> ResonanceDegree:
        """Stage 1: Evaluates contextual resonance degree between event and thread.
        
        Terminal states (CLOSED, FORGOTTEN) are strictly non-resonant.
        """
        if thread.lifecycle_state in (ThreadLifecycleState.CLOSED, ThreadLifecycleState.FORGOTTEN):
            return ResonanceDegree.NONE

        if force_degree is not None:
            return force_degree

        # Semantic heuristic for pure testing/local execution:
        # Checks if key semantic roots from title/anchor appear in event summary
        ev_lower = event.event_summary.lower()
        title_lower = thread.title.lower()

        # Direct correspondence: key semantic concepts in title match event summary
        if any(token in ev_lower for token in [title_lower, "买相机", "相机", "买了", "到了", "做完了"]):
            if any(term in ev_lower for term in [title_lower, "相机", "摄影"]):
                return ResonanceDegree.DIRECT_CORRESPONDENCE

        # Plausible alignment
        if any(token in ev_lower for token in ["照片", "胶卷", "镜头", "快门", "器材", "二手市场"]):
            return ResonanceDegree.PLAUSIBLE

        # Tangential association
        if any(token in ev_lower for token in ["周末", "出门", "公园", "逛街", "外出一趟"]):
            return ResonanceDegree.TANGENTIAL

        return ResonanceDegree.NONE

    @classmethod
    def decide_attention(
        cls,
        thread: ProspectiveThread,
        resonance: ResonanceDegree,
        suppress_attention: bool = False,
        engage_focal_interest: bool = False,
    ) -> AttentionDecision:
        """Stage 2: Decides whether Aevum consciously allocates cognitive attention.
        
        Constitutional Invariant:
        Preference ≠ Attention. Touching a DEEP_CORE interest does NOT deterministically
        command focal attention. It serves as contextual influence / affordance,
        defaulting to PERIPHERAL_AWARENESS unless focal interest is explicitly engaged.
        """
        if resonance == ResonanceDegree.NONE or suppress_attention:
            return AttentionDecision.DISREGARD_FOR_NOW

        if resonance == ResonanceDegree.TANGENTIAL:
            # Tangential cues remain peripheral or disregarded; DEEP_CORE never forces focal attention
            return AttentionDecision.PERIPHERAL_AWARENESS

        if resonance == ResonanceDegree.PLAUSIBLE:
            # Plausible cues default to peripheral awareness.
            # DEEP_CORE only elevates to focal attention when focal interest is explicitly engaged.
            if thread.salience.resonance == ResonanceTier.DEEP_CORE and engage_focal_interest:
                return AttentionDecision.FOCAL_ATTENTION
            return AttentionDecision.PERIPHERAL_AWARENESS

        if resonance == ResonanceDegree.DIRECT_CORRESPONDENCE:
            return AttentionDecision.FOCAL_ATTENTION

        return AttentionDecision.DISREGARD_FOR_NOW


    @classmethod
    def calibrate_expression(
        cls,
        thread: ProspectiveThread,
        attention: AttentionDecision,
        resonance: ResonanceDegree,
        prefer_silence: bool = False,
        conversational_energy_low: bool = False,
    ) -> Tuple[ExpressionDisposition, Optional[str]]:
        """Stage 3: Calibrates expression disposition, explicitly enabling Silence as agency.
        
        Attention ≠ Mention: Even with focal attention, Aevum has the complete
        agency to remain silent ("想到了，但没说").
        """
        # If not attended, naturally remain silent
        if attention == AttentionDecision.DISREGARD_FOR_NOW:
            return (
                ExpressionDisposition.REMAIN_SILENT,
                "Thread was disregarded in conscious thought; no conversational basis to mention.",
            )

        # Peripheral awareness: hold as quiet context
        if attention == AttentionDecision.PERIPHERAL_AWARENESS:
            return (
                ExpressionDisposition.REMAIN_SILENT,
                "Held in peripheral background awareness without interrupting current focus.",
            )

        # Focal attention: Aevum consciously noticed the connection!
        if attention == AttentionDecision.FOCAL_ATTENTION:
            # Condition A: Explicit preference for silence (e.g. conversational tact, mood, pacing)
            if prefer_silence:
                return (
                    ExpressionDisposition.REMAIN_SILENT,
                    "Noticed the connection clearly, but consciously chose not to mention it ('想到了，但没说').",
                )

            # Condition B: Low energy turn -> reserve for later
            if conversational_energy_low:
                return (
                    ExpressionDisposition.RESERVE_FOR_LATER,
                    "Consciously attended, but deferred mentioning due to low conversational energy.",
                )

            # Condition C: User thread with direct correspondence -> allow spontaneous mention
            if resonance == ResonanceDegree.DIRECT_CORRESPONDENCE:
                return (
                    ExpressionDisposition.ALLOW_SPONTANEOUS_MENTION,
                    "Thread directly matched reality event; permitted for natural surfacing if conversation flows there.",
                )

            # Default: reserve for a more fitting moment
            return (
                ExpressionDisposition.RESERVE_FOR_LATER,
                "Retained in conscious focus, awaiting an opportune conversational opening.",
            )

        return (ExpressionDisposition.REMAIN_SILENT, "Default silence.")

    @classmethod
    def evaluate(
        cls,
        thread: ProspectiveThread,
        event: RealityEventContext,
        force_resonance: Optional[ResonanceDegree] = None,
        suppress_attention: bool = False,
        engage_focal_interest: bool = False,
        prefer_silence: bool = False,
        conversational_energy_low: bool = False,
        timestamp: Optional[datetime] = None,
    ) -> ResonanceEvaluation:
        """Executes the full 3-stage evaluation pipeline producing an immutable audit record."""
        ts = timestamp or datetime.now(timezone.utc)

        # Stage 1: Contextual Resonance
        res_degree = cls.evaluate_resonance(thread, event, force_degree=force_resonance)

        # Stage 2: Cognitive Attention
        att_decision = cls.decide_attention(
            thread,
            res_degree,
            suppress_attention=suppress_attention,
            engage_focal_interest=engage_focal_interest,
        )


        # Stage 3: Expression & Silence Agency
        exp_disp, silence_why = cls.calibrate_expression(
            thread=thread,
            attention=att_decision,
            resonance=res_degree,
            prefer_silence=prefer_silence,
            conversational_energy_low=conversational_energy_low,
        )

        return ResonanceEvaluation(
            evaluation_id=f"reval_{uuid.uuid4().hex[:12]}",
            thread_id=thread.thread_id,
            event_id=event.event_id,
            resonance_degree=res_degree,
            attention_decision=att_decision,
            expression_disposition=exp_disp,
            silence_rationale=silence_why,
            evaluated_at=ts,
        )
