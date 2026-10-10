"""Phase 19.2 — Prospective Thread State Machine & Event Lifecycle Unit Tests.

Verifies:
1. Canonical Legal Transition Graph invariants and terminal isolation.
2. ACTIVE -> QUIET recede behavior and error cases.
3. Contextual encounter awakenings (QUIET/DORMANT -> ACTIVE/QUIET) and same-state touches.
4. Reality closure (ACTIVE/QUIET/DORMANT -> CLOSED) across all reasons.
5. Authoritative settlement recede (time as context, endurance-aware decay).
6. State Transition ≠ Semantic Progress (zero mutation of core identity/salience/stance).
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
from app.prospective.events import (
    SettlementContextPayload,
    ThreadClosurePayload,
    ThreadEncounterPayload,
    ThreadEventKind,
)
from app.prospective.state_machine import (
    InvalidThreadTransitionError,
    LEGAL_TRANSITIONS,
    ThreadStateMachine,
)


def _make_thread(
    state: ThreadLifecycleState = ThreadLifecycleState.ACTIVE,
    endurance: ThreadEnduranceTier = ThreadEnduranceTier.SEASONAL,
) -> ProspectiveThread:
    now = datetime(2026, 10, 5, 12, 0, 0, tzinfo=timezone.utc)
    salience = SalienceCoordinates(
        gravity=GravityTier.MODERATE,
        resonance=ResonanceTier.DEEP_CORE,
        uncertainty=UncertaintyTier.OPEN_EXPLORATION,
        endurance=endurance,
    )
    return ProspectiveThread(
        thread_id="thrd_test_101",
        character_id="aevum",
        user_id="user_123",
        domain=ThreadDomainKind.USER,
        title="测试胶片摄影",
        narrative_anchor="用户提到想尝试胶片摄影",
        epistemic_stance=EpistemicStanceKind.INTENTION,
        lifecycle_state=state,
        salience=salience,
        provenance=ThreadProvenanceKind.CONVERSATIONAL_SPONTANEOUS,
        created_at=now,
        updated_at=now,
        last_contextual_contact_at=now,
        closure_reason=ClosureReasonKind.REALIZED if state == ThreadLifecycleState.CLOSED else None,
        closure_summary="测试已完成" if state == ThreadLifecycleState.CLOSED else None,
        closed_at=now if state == ThreadLifecycleState.CLOSED else None,
    )


def test_legal_transition_graph_invariants():
    """Verifies that the transition graph contains exactly allowed edges and blocks illegal transitions."""
    # Terminal isolation: CLOSED and FORGOTTEN cannot transition to anything
    for from_s, to_s in LEGAL_TRANSITIONS:
        assert from_s != ThreadLifecycleState.CLOSED, f"Illegal outbound transition from CLOSED: {to_s}"
        assert from_s != ThreadLifecycleState.FORGOTTEN, f"Illegal outbound transition from FORGOTTEN: {to_s}"

    # No teleportation from ACTIVE to DORMANT or FORGOTTEN
    assert (ThreadLifecycleState.ACTIVE, ThreadLifecycleState.DORMANT) not in LEGAL_TRANSITIONS
    assert (ThreadLifecycleState.ACTIVE, ThreadLifecycleState.FORGOTTEN) not in LEGAL_TRANSITIONS

    # Allowed transitions check
    assert ThreadStateMachine.is_transition_legal(ThreadLifecycleState.ACTIVE, ThreadLifecycleState.QUIET)
    assert ThreadStateMachine.is_transition_legal(ThreadLifecycleState.QUIET, ThreadLifecycleState.ACTIVE)
    assert ThreadStateMachine.is_transition_legal(ThreadLifecycleState.QUIET, ThreadLifecycleState.DORMANT)
    assert ThreadStateMachine.is_transition_legal(ThreadLifecycleState.DORMANT, ThreadLifecycleState.ACTIVE)
    assert ThreadStateMachine.is_transition_legal(ThreadLifecycleState.DORMANT, ThreadLifecycleState.QUIET)
    assert ThreadStateMachine.is_transition_legal(ThreadLifecycleState.DORMANT, ThreadLifecycleState.FORGOTTEN)
    assert ThreadStateMachine.is_transition_legal(ThreadLifecycleState.ACTIVE, ThreadLifecycleState.CLOSED)
    assert ThreadStateMachine.is_transition_legal(ThreadLifecycleState.QUIET, ThreadLifecycleState.CLOSED)
    assert ThreadStateMachine.is_transition_legal(ThreadLifecycleState.DORMANT, ThreadLifecycleState.CLOSED)


def test_recede_to_quiet():
    """Verifies ACTIVE -> QUIET recede and error handling."""
    thread = _make_thread(ThreadLifecycleState.ACTIVE)
    ts = datetime(2026, 10, 5, 14, 0, 0, tzinfo=timezone.utc)

    updated, record = ThreadStateMachine.recede_to_quiet(
        thread=thread,
        turn_id="turn_42",
        timestamp=ts,
    )

    assert updated.lifecycle_state == ThreadLifecycleState.QUIET
    assert updated.updated_at == ts
    assert record.from_state == ThreadLifecycleState.ACTIVE
    assert record.to_state == ThreadLifecycleState.QUIET
    assert record.trigger_event_kind == ThreadEventKind.SESSION_RECEDE
    assert record.origin_turn_id == "turn_42"

    # Attempting recede on non-ACTIVE thread raises error
    quiet_thread = _make_thread(ThreadLifecycleState.QUIET)
    with pytest.raises(InvalidThreadTransitionError):
        ThreadStateMachine.recede_to_quiet(quiet_thread)


def test_encounter_thread_awakening():
    """Verifies contextual encounter awakening from QUIET and DORMANT states."""
    ts = datetime(2026, 10, 7, 10, 0, 0, tzinfo=timezone.utc)

    # 1. QUIET -> ACTIVE (Foreground encounter)
    quiet_thread = _make_thread(ThreadLifecycleState.QUIET)
    payload_fg = ThreadEncounterPayload(
        thread_id=quiet_thread.thread_id,
        context_summary="用户询问老相机的快门手感",
        encounter_timestamp=ts,
        turn_id="turn_88",
        foreground=True,
    )
    act_thread, rec_act = ThreadStateMachine.encounter_thread(quiet_thread, payload_fg)
    assert act_thread.lifecycle_state == ThreadLifecycleState.ACTIVE
    assert act_thread.last_contextual_contact_at == ts
    assert rec_act is not None
    assert rec_act.from_state == ThreadLifecycleState.QUIET
    assert rec_act.to_state == ThreadLifecycleState.ACTIVE
    assert rec_act.trigger_event_kind == ThreadEventKind.CONTEXTUAL_ENCOUNTER

    # 2. DORMANT -> QUIET (Faint background awakening)
    dormant_thread = _make_thread(ThreadLifecycleState.DORMANT)
    payload_bg = ThreadEncounterPayload(
        thread_id=dormant_thread.thread_id,
        context_summary="用户无意间发了一张街头照片",
        encounter_timestamp=ts,
        turn_id="turn_90",
        foreground=False,
    )
    q_thread, rec_q = ThreadStateMachine.encounter_thread(dormant_thread, payload_bg)
    assert q_thread.lifecycle_state == ThreadLifecycleState.QUIET
    assert rec_q is not None
    assert rec_q.from_state == ThreadLifecycleState.DORMANT
    assert rec_q.to_state == ThreadLifecycleState.QUIET

    # 3. Same-state touch on ACTIVE -> updates timestamp without state transition record
    active_thread = _make_thread(ThreadLifecycleState.ACTIVE)
    same_thread, rec_none = ThreadStateMachine.encounter_thread(active_thread, payload_fg)
    assert same_thread.lifecycle_state == ThreadLifecycleState.ACTIVE
    assert same_thread.last_contextual_contact_at == ts
    assert rec_none is None

    # 4. Attempting encounter on terminal state raises error
    closed_thread = _make_thread(ThreadLifecycleState.CLOSED)
    with pytest.raises(InvalidThreadTransitionError, match="Terminal states"):
        ThreadStateMachine.encounter_thread(closed_thread, payload_fg)


def test_close_thread_resolution():
    """Verifies reality closure from ACTIVE, QUIET, and DORMANT states."""
    ts = datetime(2026, 10, 8, 16, 0, 0, tzinfo=timezone.utc)
    close_payload = ThreadClosurePayload(
        thread_id="thrd_test_101",
        closure_reason=ClosureReasonKind.REALIZED,
        closure_summary="用户买到了心仪的二手旁轴相机",
        closed_at=ts,
        turn_id="turn_95",
    )

    for initial_state in [
        ThreadLifecycleState.ACTIVE,
        ThreadLifecycleState.QUIET,
        ThreadLifecycleState.DORMANT,
    ]:
        thread = _make_thread(initial_state)
        closed, record = ThreadStateMachine.close_thread(thread, close_payload)

        assert closed.lifecycle_state == ThreadLifecycleState.CLOSED
        assert closed.closure_reason == ClosureReasonKind.REALIZED
        assert closed.closure_summary == "用户买到了心仪的二手旁轴相机"
        assert closed.closed_at == ts
        assert record.from_state == initial_state
        assert record.to_state == ThreadLifecycleState.CLOSED
        assert record.trigger_event_kind == ThreadEventKind.REALITY_CLOSURE

    # Closing already closed thread raises error
    closed_th = _make_thread(ThreadLifecycleState.CLOSED)
    with pytest.raises(InvalidThreadTransitionError):
        ThreadStateMachine.close_thread(closed_th, close_payload)


def test_authoritative_settlement_recede():
    """Verifies time-as-context background recede during authoritative settlements."""
    ts = datetime(2026, 10, 15, 4, 0, 0, tzinfo=timezone.utc)
    settlement_payload = SettlementContextPayload(
        settlement_id="setl_cycle_001",
        settlement_timestamp=ts,
        character_id="aevum",
    )

    # 1. ACTIVE thread is immune to settlement recede
    active_th = _make_thread(ThreadLifecycleState.ACTIVE)
    assert ThreadStateMachine.evaluate_settlement_recede(
        active_th, settlement_payload, hours_since_contact=100.0
    ) is None

    # 2. QUIET thread with insufficient elapsed hours (<72h) -> stays QUIET
    quiet_th = _make_thread(ThreadLifecycleState.QUIET, endurance=ThreadEnduranceTier.SEASONAL)
    assert ThreadStateMachine.evaluate_settlement_recede(
        quiet_th, settlement_payload, hours_since_contact=30.0
    ) is None

    # 3. QUIET ephemeral thread with >= 48h -> dissolves to FORGOTTEN
    ephemeral_th = _make_thread(ThreadLifecycleState.QUIET, endurance=ThreadEnduranceTier.EPHEMERAL_TALK)
    res_eph = ThreadStateMachine.evaluate_settlement_recede(
        ephemeral_th, settlement_payload, hours_since_contact=50.0
    )
    assert res_eph is not None
    updated_eph, rec_eph = res_eph
    assert updated_eph.lifecycle_state == ThreadLifecycleState.FORGOTTEN
    assert rec_eph.trigger_event_kind == ThreadEventKind.AUTHORITATIVE_SETTLEMENT

    # 4. QUIET seasonal thread with >= 72h -> recedes to DORMANT
    res_dorm = ThreadStateMachine.evaluate_settlement_recede(
        quiet_th, settlement_payload, hours_since_contact=80.0
    )
    assert res_dorm is not None
    updated_dorm, rec_dorm = res_dorm
    assert updated_dorm.lifecycle_state == ThreadLifecycleState.DORMANT
    assert rec_dorm.trigger_event_kind == ThreadEventKind.AUTHORITATIVE_SETTLEMENT

    # 5. DORMANT seasonal thread with >= 720h (30 days) -> dissolves to FORGOTTEN
    dormant_seasonal = _make_thread(ThreadLifecycleState.DORMANT, endurance=ThreadEnduranceTier.SEASONAL)
    res_forg = ThreadStateMachine.evaluate_settlement_recede(
        dormant_seasonal, settlement_payload, hours_since_contact=750.0
    )
    assert res_forg is not None
    updated_forg, rec_forg = res_forg
    assert updated_forg.lifecycle_state == ThreadLifecycleState.FORGOTTEN

    # 6. DORMANT DURABLE_ARC thread with >= 720h -> resists forgetting, stays DORMANT
    dormant_durable = _make_thread(ThreadLifecycleState.DORMANT, endurance=ThreadEnduranceTier.DURABLE_ARC)
    res_dur = ThreadStateMachine.evaluate_settlement_recede(
        dormant_durable, settlement_payload, hours_since_contact=1000.0
    )
    assert res_dur is None  # Resisted forgetting!


def test_state_transition_anti_side_effects():
    """Verifies State Transition ≠ Semantic Progress: core domain, salience, stance are 100% immune."""
    thread = _make_thread(ThreadLifecycleState.ACTIVE)
    ts = datetime(2026, 10, 6, 12, 0, 0, tzinfo=timezone.utc)

    updated, _ = ThreadStateMachine.recede_to_quiet(thread, timestamp=ts)

    # Core semantic and epistemic fields MUST be identical
    assert updated.thread_id == thread.thread_id
    assert updated.character_id == thread.character_id
    assert updated.user_id == thread.user_id
    assert updated.domain == thread.domain
    assert updated.title == thread.title
    assert updated.narrative_anchor == thread.narrative_anchor
    assert updated.epistemic_stance == thread.epistemic_stance
    assert updated.salience == thread.salience
    assert updated.provenance == thread.provenance
    assert updated.created_at == thread.created_at
