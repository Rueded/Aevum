"""Phase 19.3 — Contextual Resonance & Cognitive Attention Engine Unit Tests.

Verifies:
1. The 4-Tier Cognitive Separation Chain:
   Trigger ≠ Recall ≠ Attention ≠ Mention ≠ Action.
2. The Agency of Silence ("想到了，但没说"):
   Focal attention consciously choosing REMAIN_SILENT.
3. Terminal thread immunity (CLOSED / FORGOTTEN never resonate).
4. Resonance tier influence (DEEP_CORE elevation vs PERIPHERAL awareness).
5. Tangential cues non-intrusiveness.
6. Immutable audit evaluation records.
"""

from datetime import datetime, timezone
import pytest

from app.prospective.contracts import (
    ClosureReasonKind,
    EpistemicStanceKind,
    GravityTier,
    ProspectiveThread,
    ResonanceTier,
    SalienceCoordinates,
    ThreadDomainKind,
    ThreadEnduranceTier,
    ThreadLifecycleState,
    ThreadProvenanceKind,
    UncertaintyTier,
)

from app.prospective.resonance_models import (
    AttentionDecision,
    ExpressionDisposition,
    RealityEventContext,
    ResonanceDegree,
)
from app.prospective.resonance_engine import ContextualResonanceEngine


def _make_thread(
    state: ThreadLifecycleState = ThreadLifecycleState.QUIET,
    resonance_tier: ResonanceTier = ResonanceTier.DEEP_CORE,
) -> ProspectiveThread:
    now = datetime(2026, 10, 5, 12, 0, 0, tzinfo=timezone.utc)
    salience = SalienceCoordinates(
        gravity=GravityTier.MODERATE,
        resonance=resonance_tier,
        uncertainty=UncertaintyTier.OPEN_EXPLORATION,
        endurance=ThreadEnduranceTier.SEASONAL,
    )
    return ProspectiveThread(
        thread_id="thrd_cam_01",
        character_id="aevum",
        user_id="user_123",
        domain=ThreadDomainKind.USER,
        title="胶片相机探索",
        narrative_anchor="用户提到想尝试胶片摄影，正在挑选二手富士老相机",
        epistemic_stance=EpistemicStanceKind.INTENTION,
        lifecycle_state=state,
        salience=salience,
        provenance=ThreadProvenanceKind.CONVERSATIONAL_SPONTANEOUS,
        created_at=now,
        updated_at=now,
        last_contextual_contact_at=now,
    )


def _make_event(summary: str) -> RealityEventContext:
    return RealityEventContext(
        event_id="ev_test_101",
        event_summary=summary,
        occurred_at=datetime(2026, 10, 8, 15, 30, 0, tzinfo=timezone.utc),
        turn_id="turn_77",
        is_user_initiated=True,
    )


def test_cognitive_separation_and_silence_agency():
    """Verifies the separation chain and the core '想到了，但没说' Silence agency."""
    thread = _make_thread(ThreadLifecycleState.QUIET)
    event_match = _make_event("在二手店挑了台富士相机，终于买到了！")

    # Case A: Full spontaneous flow (Direct -> Focal -> Mention)
    eval_a = ContextualResonanceEngine.evaluate(
        thread=thread,
        event=event_match,
        prefer_silence=False,
        conversational_energy_low=False,
    )
    assert eval_a.resonance_degree == ResonanceDegree.DIRECT_CORRESPONDENCE
    assert eval_a.attention_decision == AttentionDecision.FOCAL_ATTENTION
    assert eval_a.expression_disposition == ExpressionDisposition.ALLOW_SPONTANEOUS_MENTION

    # Case B: The Agency of Silence ("想到了，但没说")
    # Even when focal attention notices the connection, Aevum consciously chooses REMAIN_SILENT!
    eval_b = ContextualResonanceEngine.evaluate(
        thread=thread,
        event=event_match,
        prefer_silence=True,  # Conscious choice of silence
    )
    assert eval_b.resonance_degree == ResonanceDegree.DIRECT_CORRESPONDENCE
    assert eval_b.attention_decision == AttentionDecision.FOCAL_ATTENTION
    assert eval_b.expression_disposition == ExpressionDisposition.REMAIN_SILENT
    assert "想到了，但没说" in eval_b.silence_rationale

    # Case C: Low Conversational Energy -> Reserve for later
    eval_c = ContextualResonanceEngine.evaluate(
        thread=thread,
        event=event_match,
        conversational_energy_low=True,
    )
    assert eval_c.resonance_degree == ResonanceDegree.DIRECT_CORRESPONDENCE
    assert eval_c.attention_decision == AttentionDecision.FOCAL_ATTENTION
    assert eval_c.expression_disposition == ExpressionDisposition.RESERVE_FOR_LATER

    # Case D: Conscious suppression of attention (Recall != Attention)
    eval_d = ContextualResonanceEngine.evaluate(
        thread=thread,
        event=event_match,
        suppress_attention=True,
    )
    assert eval_d.resonance_degree == ResonanceDegree.DIRECT_CORRESPONDENCE
    assert eval_d.attention_decision == AttentionDecision.DISREGARD_FOR_NOW
    assert eval_d.expression_disposition == ExpressionDisposition.REMAIN_SILENT


def test_terminal_thread_immunity():
    """Verifies that terminal threads (CLOSED, FORGOTTEN) never resonate."""
    event_match = _make_event("在二手店挑了台富士相机，终于买到了！")

    for terminal_state in [ThreadLifecycleState.CLOSED, ThreadLifecycleState.FORGOTTEN]:
        now = datetime(2026, 10, 5, 12, 0, 0, tzinfo=timezone.utc)
        thread = ProspectiveThread(
            thread_id="thrd_terminal",
            character_id="aevum",
            user_id="user_123",
            domain=ThreadDomainKind.USER,
            title="胶片相机探索",
            narrative_anchor="用户提到想尝试胶片摄影",
            epistemic_stance=EpistemicStanceKind.INTENTION,
            lifecycle_state=terminal_state,
            salience=SalienceCoordinates(
                gravity=GravityTier.MODERATE,
                resonance=ResonanceTier.DEEP_CORE,
                uncertainty=UncertaintyTier.OPEN_EXPLORATION,
                endurance=ThreadEnduranceTier.SEASONAL,
            ),
            provenance=ThreadProvenanceKind.CONVERSATIONAL_SPONTANEOUS,
            created_at=now,
            updated_at=now,
            closure_reason=ClosureReasonKind.REALIZED if terminal_state == ThreadLifecycleState.CLOSED else None,
            closure_summary="已买" if terminal_state == ThreadLifecycleState.CLOSED else None,
            closed_at=now if terminal_state == ThreadLifecycleState.CLOSED else None,
        )

        res = ContextualResonanceEngine.evaluate(thread, event_match)
        assert res.resonance_degree == ResonanceDegree.NONE
        assert res.attention_decision == AttentionDecision.DISREGARD_FOR_NOW
        assert res.expression_disposition == ExpressionDisposition.REMAIN_SILENT


def test_salience_resonance_influence():
    """Verifies that Preference ≠ Attention: DEEP_CORE is contextual influence, NOT deterministic promotion."""
    event_plausible = _make_event("在网上看了一些摄影胶卷的显影效果")

    # 1. By default, even DEEP_CORE plausible cues remain in PERIPHERAL_AWARENESS (Preference ≠ Attention)
    thread_core = _make_thread(resonance_tier=ResonanceTier.DEEP_CORE)
    res_default = ContextualResonanceEngine.evaluate(thread_core, event_plausible, engage_focal_interest=False)
    assert res_default.resonance_degree == ResonanceDegree.PLAUSIBLE
    assert res_default.attention_decision == AttentionDecision.PERIPHERAL_AWARENESS
    assert res_default.expression_disposition == ExpressionDisposition.REMAIN_SILENT

    # 2. When focal interest is actively engaged, DEEP_CORE affords elevation to FOCAL_ATTENTION
    res_engaged = ContextualResonanceEngine.evaluate(thread_core, event_plausible, engage_focal_interest=True)
    assert res_engaged.resonance_degree == ResonanceDegree.PLAUSIBLE
    assert res_engaged.attention_decision == AttentionDecision.FOCAL_ATTENTION

    # 3. PERIPHERAL resonance stays in PERIPHERAL_AWARENESS regardless
    thread_periph = _make_thread(resonance_tier=ResonanceTier.PERIPHERAL)
    res_periph = ContextualResonanceEngine.evaluate(thread_periph, event_plausible, engage_focal_interest=True)
    assert res_periph.resonance_degree == ResonanceDegree.PLAUSIBLE
    assert res_periph.attention_decision == AttentionDecision.PERIPHERAL_AWARENESS
    assert res_periph.expression_disposition == ExpressionDisposition.REMAIN_SILENT


def test_tangential_cues_non_intrusiveness():
    """Verifies tangential cues never force focal attention or compulsive mentions."""
    thread = _make_thread(resonance_tier=ResonanceTier.DEEP_CORE)
    event_tangential = _make_event("今天周末去公园随便逛了一圈")

    res = ContextualResonanceEngine.evaluate(thread, event_tangential)
    assert res.resonance_degree == ResonanceDegree.TANGENTIAL
    assert res.attention_decision == AttentionDecision.PERIPHERAL_AWARENESS
    assert res.expression_disposition == ExpressionDisposition.REMAIN_SILENT


def test_silence_rationale_audit_isolation():
    """Verifies silence_rationale is pure internal audit metadata and does not leak dialogue content."""
    thread = _make_thread(resonance_tier=ResonanceTier.DEEP_CORE)
    event_match = _make_event("在二手店挑了台富士相机，终于买到了！")

    res = ContextualResonanceEngine.evaluate(thread, event_match, prefer_silence=True)
    assert res.attention_decision == AttentionDecision.FOCAL_ATTENTION
    assert res.expression_disposition == ExpressionDisposition.REMAIN_SILENT
    # Audit rationale is purely explainable metadata
    assert res.silence_rationale is not None
    assert "想到了，但没说" in res.silence_rationale

