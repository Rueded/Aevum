"""
test_golden_suite_19.py — Golden Suite 19: Prospective Memory, Autonomous Agency & Experiential Continuity

Acceptance Benchmarks GC-437 through GC-454 across 4 Clusters:
- Cluster 1 (GC-437 ~ GC-442): Constitutional Axioms, Schemas & Anti-Ticketing Invariants
- Cluster 2 (GC-443 ~ GC-445): The Epistemic Ladder & Anti-Skipping Gatekeeper
- Cluster 3 (GC-446 ~ GC-450): Agency of Silence, Ownership Domains & Epistemic Stances
- Cluster 4 (GC-451 ~ GC-454): Deterministic State Machine, Terminal States & Non-Cascading Cognitive Flow
"""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

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
    ThreadTransitionRecord,
)
from app.prospective.state_machine import (
    InvalidThreadTransitionError,
    LEGAL_TRANSITIONS,
    ThreadStateMachine,
)
from app.prospective.resonance_models import (
    AttentionDecision,
    ExpressionDisposition,
    RealityEventContext,
    ResonanceDegree,
    ResonanceEvaluation,
)
from app.prospective.resonance_engine import ContextualResonanceEngine
from app.prospective.transformation_models import (
    EpistemicStage,
    IllegalEpistemicSkipError,
    TransformationAuditRecord,
    TransformationEvidenceKind,
)
from app.prospective.transformation_engine import (
    EpistemicTransformationEngine,
    LEGAL_LADDER_STEPS,
)


@pytest.fixture
def sample_salience() -> SalienceCoordinates:
    return SalienceCoordinates(
        gravity=GravityTier.MODERATE,
        resonance=ResonanceTier.DEEP_CORE,
        uncertainty=UncertaintyTier.OPEN_EXPLORATION,
        endurance=ThreadEnduranceTier.SEASONAL,
    )


@pytest.fixture
def active_user_thread(sample_salience: SalienceCoordinates) -> ProspectiveThread:
    now = datetime(2026, 10, 5, 12, 0, 0, tzinfo=timezone.utc)
    return ProspectiveThread(
        thread_id="thrd_user_film_001",
        character_id="aevum",
        user_id="user_gold_01",
        domain=ThreadDomainKind.USER,
        title="胶片摄影构想",
        narrative_anchor="用户提到想尝试用胶片相机记录日常生活",
        epistemic_stance=EpistemicStanceKind.INTENTION,
        lifecycle_state=ThreadLifecycleState.ACTIVE,
        salience=sample_salience,
        provenance=ThreadProvenanceKind.CONVERSATIONAL_SPONTANEOUS,
        created_at=now,
        updated_at=now,
        last_contextual_contact_at=now,
    )


@pytest.fixture
def active_self_thread(sample_salience: SalienceCoordinates) -> ProspectiveThread:
    now = datetime(2026, 10, 5, 12, 0, 0, tzinfo=timezone.utc)
    return ProspectiveThread(
        thread_id="thrd_self_tea_001",
        character_id="aevum",
        user_id="user_gold_01",
        domain=ThreadDomainKind.SELF,
        title="整理旧茶具与窗台绿植",
        narrative_anchor="Aevum计划周末给窗台上的迷迭香分盆换土",
        epistemic_stance=EpistemicStanceKind.INTENTION,
        lifecycle_state=ThreadLifecycleState.ACTIVE,
        salience=sample_salience,
        provenance=ThreadProvenanceKind.LIFE_SIMULATION_EMERGENT,
        created_at=now,
        updated_at=now,
        last_contextual_contact_at=now,
    )


# ============================================================================
# Cluster 1 (GC-437 ~ GC-442): Constitutional Axioms, Schemas & Anti-Ticketing
# ============================================================================

class TestCluster1ConstitutionalAxiomsAndAntiTicketing:
    """Cluster 1 benchmarks for Golden Suite 19."""

    def test_gc_437_experiential_continuity_over_memory_retrieval(
        self, active_user_thread: ProspectiveThread
    ):
        """GC-437: Experiential Continuity Over Memory Retrieval.

        Verifies that a prospective thread represents an unsettled future trajectory,
        NOT a retrospective memory lookup or ticket.
        """
        assert active_user_thread.lifecycle_state == ThreadLifecycleState.ACTIVE
        assert active_user_thread.epistemic_stance == EpistemicStanceKind.INTENTION
        assert active_user_thread.closure_reason is None
        assert active_user_thread.closed_at is None
        assert not hasattr(active_user_thread, "is_completed")

    def test_gc_438_open_not_todo_anti_ticketing(self, sample_salience: SalienceCoordinates):
        """GC-438: Open ≠ TODO (Anti-Ticketing Invariant).

        Verifies extra='forbid' strictly rejects any task management fields
        (due_date, reminder_time, is_task, todo_status, etc.).
        """
        now = datetime.now(timezone.utc)
        forbidden_fields = [
            {"due_date": "2026-10-10"},
            {"reminder_time": "14:00"},
            {"is_task": True},
            {"todo_status": "PENDING"},
            {"assignee": "Aevum"},
            {"priority_score": 9.5},
        ]
        for extra in forbidden_fields:
            with pytest.raises(ValidationError):
                ProspectiveThread(
                    thread_id="th_invalid",
                    character_id="aevum",
                    user_id="user_123",
                    domain=ThreadDomainKind.USER,
                    title="Test",
                    narrative_anchor="Anchor",
                    epistemic_stance=EpistemicStanceKind.INTENTION,
                    lifecycle_state=ThreadLifecycleState.ACTIVE,
                    salience=sample_salience,
                    provenance=ThreadProvenanceKind.CONVERSATIONAL_SPONTANEOUS,
                    created_at=now,
                    updated_at=now,
                    last_contextual_contact_at=now,
                    **extra,  # type: ignore
                )

    def test_gc_439_open_not_action_required(
        self, active_user_thread: ProspectiveThread
    ):
        """GC-439: Open ≠ Action Required.

        Thread presence never creates obligation for autonomous or conversational action.
        Expression disposition can freely choose REMAIN_SILENT or RESERVE_FOR_LATER.
        """
        cue = RealityEventContext(
            event_id="ev_01",
            event_summary="用户提到了天气很热想喝冷饮",
            occurred_at=datetime.now(timezone.utc),
            turn_id="turn_99",
        )
        res = ContextualResonanceEngine.evaluate_resonance(active_user_thread, cue)
        att = ContextualResonanceEngine.decide_attention(active_user_thread, res)
        disp, _ = ContextualResonanceEngine.calibrate_expression(active_user_thread, att, res)

        assert res == ResonanceDegree.NONE
        assert att == AttentionDecision.DISREGARD_FOR_NOW
        assert disp == ExpressionDisposition.REMAIN_SILENT

    def test_gc_440_memory_not_prospective_thread_schema_isolation(
        self, active_user_thread: ProspectiveThread
    ):
        """GC-440: Memory ≠ Prospective Thread (Schema Isolation).

        ProspectiveThread is completely isolated from Retrospective Memory schemas.
        """
        assert active_user_thread.__class__.__name__ == "ProspectiveThread"
        assert "MemoryRecord" not in [c.__name__ for c in active_user_thread.__class__.__mro__]

    def test_gc_441_trigger_not_keyword_match(
        self, active_user_thread: ProspectiveThread
    ):
        """GC-441: Trigger ≠ Keyword Match.

        Threads evaluate semantic relevance, rejecting naive token/string collisions.
        """
        cue = RealityEventContext(
            event_id="ev_unrelated",
            event_summary="打印机没墨水了，需要换硒鼓",
            occurred_at=datetime.now(timezone.utc),
            turn_id="turn_101",
        )
        resonance = ContextualResonanceEngine.evaluate_resonance(
            thread=active_user_thread,
            event=cue,
        )
        assert resonance == ResonanceDegree.NONE

    def test_gc_442_salience_coordinates_no_additive_scores(
        self, sample_salience: SalienceCoordinates
    ):
        """GC-442: Salience ≠ Importance Alone (Anti-Formula Invariant).

        Salience comprises 4 descriptive categorical coordinates with ZERO floats
        and ZERO linear scoring formulas.
        """
        assert isinstance(sample_salience.gravity, GravityTier)
        assert isinstance(sample_salience.resonance, ResonanceTier)
        assert isinstance(sample_salience.uncertainty, UncertaintyTier)
        assert isinstance(sample_salience.endurance, ThreadEnduranceTier)
        for field_name, field_val in sample_salience.__dict__.items():
            assert not isinstance(field_val, float), f"Float field found: {field_name}"


# ============================================================================
# Cluster 2 (GC-443 ~ GC-455): The Epistemic Ladder & Anti-Skipping Gatekeeper
# ============================================================================

class TestCluster2EpistemicLadderGatekeeper:
    """Cluster 2 benchmarks for Golden Suite 19."""

    def test_gc_443_intention_not_action(self):
        """GC-443: Intention ≠ Action.

        Intention requires ACTION_ONLY evidence to become ACTION_RECORDED.
        Attempting to skip to Experience or Preference directly raises IllegalEpistemicSkipError.
        """
        now = datetime.now(timezone.utc)
        stage, audit = EpistemicTransformationEngine.evaluate_transition(
            thread_id="th_camera_gold",
            current_stage=EpistemicStage.PROSPECTIVE_INTENTION,
            evidence_kind=TransformationEvidenceKind.ACTION_ONLY,
            rationale="用户购买了胶片相机",
            timestamp=now,
        )
        assert stage == EpistemicStage.ACTION_RECORDED
        assert EpistemicTransformationEngine.has_action_occurred(stage)
        assert not EpistemicTransformationEngine.has_lived_experience(stage)

        with pytest.raises(IllegalEpistemicSkipError):
            EpistemicTransformationEngine.advance_stage(
                thread_id="th_camera_gold",
                from_stage=EpistemicStage.PROSPECTIVE_INTENTION,
                to_stage=EpistemicStage.EXPERIENCE_ENCOUNTERED,
                evidence_kind=TransformationEvidenceKind.EXPERIENCE_POSITIVE,
                rationale="试图跳过行动直接形成体验",
            )

    def test_gc_444_action_not_experience(self):
        """GC-444: Action ≠ Experience.

        Action requires lived experience evidence to become EXPERIENCE_ENCOUNTERED.
        Action cannot jump directly to Sustained Evidence or Preference.
        """
        now = datetime.now(timezone.utc)
        stage, audit = EpistemicTransformationEngine.evaluate_transition(
            thread_id="th_camera_gold",
            current_stage=EpistemicStage.ACTION_RECORDED,
            evidence_kind=TransformationEvidenceKind.EXPERIENCE_POSITIVE,
            rationale="第一次试拍洗印照片",
            timestamp=now,
        )
        assert stage == EpistemicStage.EXPERIENCE_ENCOUNTERED
        assert EpistemicTransformationEngine.has_lived_experience(stage)
        assert not EpistemicTransformationEngine.is_preference_eligible(stage)

        with pytest.raises(IllegalEpistemicSkipError):
            EpistemicTransformationEngine.advance_stage(
                thread_id="th_camera_gold",
                from_stage=EpistemicStage.ACTION_RECORDED,
                to_stage=EpistemicStage.PREFERENCE_ELIGIBLE,
                evidence_kind=TransformationEvidenceKind.SUSTAINED_POSITIVE,
                rationale="试图跳过体验直接断言偏好",
            )

    def test_gc_445_experience_not_preference_and_negative_outcome(self):
        """GC-445: Experience ≠ Preference & Negative Outcome Integrity.

        - Single experience cannot jump to preference.
        - Negative experience settles as lived experience without preference promotion.
        - Longitudinal sustained evidence is required for preference eligibility.
        """
        now = datetime.now(timezone.utc)

        with pytest.raises(IllegalEpistemicSkipError):
            EpistemicTransformationEngine.advance_stage(
                thread_id="th_exp_01",
                from_stage=EpistemicStage.EXPERIENCE_ENCOUNTERED,
                to_stage=EpistemicStage.PREFERENCE_ELIGIBLE,
                evidence_kind=TransformationEvidenceKind.SUSTAINED_POSITIVE,
                rationale="单次体验跳过持续证据",
            )

        neg_stage, neg_audit = EpistemicTransformationEngine.evaluate_transition(
            thread_id="th_exp_neg",
            current_stage=EpistemicStage.EXPERIENCE_ENCOUNTERED,
            evidence_kind=TransformationEvidenceKind.EXPERIENCE_NEGATIVE,
            rationale="冲洗后感觉繁重繁琐，并不喜欢",
            timestamp=now,
        )
        assert neg_stage == EpistemicStage.EXPERIENCE_ENCOUNTERED
        assert not EpistemicTransformationEngine.is_preference_eligible(neg_stage)

        st1, _ = EpistemicTransformationEngine.evaluate_transition(
            thread_id="th_exp_pos",
            current_stage=EpistemicStage.EXPERIENCE_ENCOUNTERED,
            evidence_kind=TransformationEvidenceKind.SUSTAINED_POSITIVE,
            rationale="多周持续拍摄",
            timestamp=now,
        )
        assert st1 == EpistemicStage.SUSTAINED_EVIDENCE

        st2, _ = EpistemicTransformationEngine.evaluate_transition(
            thread_id="th_exp_pos",
            current_stage=st1,
            evidence_kind=TransformationEvidenceKind.SUSTAINED_POSITIVE,
            rationale="长期审美共振确立",
            timestamp=now,
        )
        assert st2 == EpistemicStage.PREFERENCE_ELIGIBLE
        assert EpistemicTransformationEngine.is_preference_eligible(st2)


# ============================================================================
# Cluster 3 (GC-446 ~ GC-450): Agency of Silence, Ownership & Stances
# ============================================================================

class TestCluster3AgencyOfSilenceAndOwnership:
    """Cluster 3 benchmarks for Golden Suite 19."""

    def test_gc_446_agency_of_silence_remembering_not_mentioning(
        self, active_user_thread: ProspectiveThread
    ):
        """GC-446: Remembering ≠ Mentioning ("想到了，但没说").

        Aevum can hold focal attention on a thread but consciously choose REMAIN_SILENT.
        `silence_rationale` remains internal audit metadata only.
        """
        cue = RealityEventContext(
            event_id="ev_film_mention",
            event_summary="在二手店挑了台富士相机，终于买到了！",
            occurred_at=datetime.now(timezone.utc),
            turn_id="turn_300",
        )
        eval_result = ContextualResonanceEngine.evaluate(
            thread=active_user_thread,
            event=cue,
            prefer_silence=True,
        )
        assert eval_result.attention_decision == AttentionDecision.FOCAL_ATTENTION
        assert eval_result.expression_disposition == ExpressionDisposition.REMAIN_SILENT
        assert eval_result.silence_rationale is not None
        assert "想到了，但没说" in eval_result.silence_rationale

    def test_gc_447_open_not_must_be_mentioned_silent_closure(
        self, active_self_thread: ProspectiveThread
    ):
        """GC-447: Open ≠ Must Be Mentioned.

        An open thread can settle or close completely silently without dialogue output.
        """
        now = datetime.now(timezone.utc)
        payload = ThreadClosurePayload(
            thread_id=active_self_thread.thread_id,
            closure_reason=ClosureReasonKind.REALIZED,
            closure_summary="Aevum周末自主完成了窗台换土修剪，未作对话汇报",
            closed_at=now,
            turn_id=None,
        )
        closed_thread, record = ThreadStateMachine.close_thread(
            thread=active_self_thread,
            payload=payload,
        )
        assert closed_thread.lifecycle_state == ThreadLifecycleState.CLOSED
        assert closed_thread.closure_reason == ClosureReasonKind.REALIZED
        assert record.to_state == ThreadLifecycleState.CLOSED

    def test_gc_448_user_future_not_aevum_responsibility(
        self, active_user_thread: ProspectiveThread
    ):
        """GC-448: User Future ≠ Aevum Responsibility.

        Ownership domain USER confirms zero accountability or reminder duty on Aevum.
        """
        assert active_user_thread.domain == ThreadDomainKind.USER
        assert not hasattr(active_user_thread, "reminder_job_id")
        assert not hasattr(active_user_thread, "notification_pending")

    def test_gc_449_time_passing_not_automatic_proactivity(
        self, active_self_thread: ProspectiveThread
    ):
        """GC-449: Time Passing ≠ Automatic Proactivity.

        Calendar passage does NOT automatically mutate states or trigger outreach.
        Settlement occurs only via authoritative settlement checkpoints.
        """
        later = datetime(2026, 11, 5, 12, 0, 0, tzinfo=timezone.utc)
        assert active_self_thread.lifecycle_state == ThreadLifecycleState.ACTIVE

        quiet_thread, record = ThreadStateMachine.recede_to_quiet(
            thread=active_self_thread,
            timestamp=later,
        )
        assert quiet_thread.lifecycle_state == ThreadLifecycleState.QUIET
        assert record.trigger_event_kind == ThreadEventKind.SESSION_RECEDE

    def test_gc_450_open_not_belief_exclusion(self):
        """GC-450: Open ≠ Belief.

        Epistemic stance separates INTENTION, EXPECTATION, PREDICTION from BELIEF.
        BELIEF is strictly barred from ProspectiveThread stances.
        """
        assert "BELIEF" not in [s.value for s in EpistemicStanceKind]
        assert set(EpistemicStanceKind) == {
            EpistemicStanceKind.INTENTION,
            EpistemicStanceKind.EXPECTATION,
            EpistemicStanceKind.PREDICTION,
        }


# ============================================================================
# Cluster 4 (GC-451 ~ GC-454): State Machine, Terminal States & Cognitive Chain
# ============================================================================

class TestCluster4StateMachineAndCognitiveChain:
    """Cluster 4 benchmarks for Golden Suite 19."""

    def test_gc_451_canonical_lifecycle_graph_and_terminal_isolation(
        self, active_self_thread: ProspectiveThread
    ):
        """GC-451: Canonical Legal Lifecycle Graph & Terminal Isolation.

        Strictly enforces 10 legal transitions.
        CLOSED and FORGOTTEN are irreversible terminal states.
        """
        assert len(LEGAL_TRANSITIONS) == 10

        closed_thread, _ = ThreadStateMachine.close_thread(
            thread=active_self_thread,
            payload=ThreadClosurePayload(
                thread_id=active_self_thread.thread_id,
                closure_reason=ClosureReasonKind.ABANDONED,
                closure_summary="放弃计划",
                closed_at=datetime.now(timezone.utc),
                turn_id="turn_404",
            ),
        )
        assert closed_thread.lifecycle_state == ThreadLifecycleState.CLOSED

        with pytest.raises(InvalidThreadTransitionError):
            ThreadStateMachine.recede_to_quiet(closed_thread)

        with pytest.raises(InvalidThreadTransitionError):
            ThreadStateMachine.encounter_thread(
                closed_thread,
                ThreadEncounterPayload(
                    thread_id=closed_thread.thread_id,
                    context_summary="Reactivate closed thread",
                    encounter_timestamp=datetime.now(timezone.utc),
                    turn_id="turn_405",
                ),
            )

    def test_gc_452_state_transition_not_semantic_progress(
        self, active_self_thread: ProspectiveThread
    ):
        """GC-452: State Transition ≠ Semantic Progress.

        State changes only modulate cognitive accessibility; they never alter
        factual truth, lived experience, or preferences.
        """
        quiet_thread, _ = ThreadStateMachine.recede_to_quiet(active_self_thread)
        assert quiet_thread.lifecycle_state == ThreadLifecycleState.QUIET
        assert quiet_thread.epistemic_stance == active_self_thread.epistemic_stance
        assert quiet_thread.narrative_anchor == active_self_thread.narrative_anchor
        assert quiet_thread.title == active_self_thread.title

    def test_gc_453_non_cascading_cognitive_chain(
        self, active_user_thread: ProspectiveThread
    ):
        """GC-453: 7-Stage Non-Cascading Cognitive Chain.

        Encounter -> Resonance -> Recall -> Attention -> Expression Disposition -> Mention/Silence -> Action.
        Can safely halt at any stage without implicit cascade.
        """
        cue = RealityEventContext(
            event_id="ev_halt_demo",
            event_summary="路过一家照相馆橱窗，去公园散步了一趟",
            occurred_at=datetime.now(timezone.utc),
            turn_id="turn_chain_01",
        )
        res = ContextualResonanceEngine.evaluate_resonance(active_user_thread, cue)
        assert res == ResonanceDegree.TANGENTIAL

        att = ContextualResonanceEngine.decide_attention(
            active_user_thread, res, engage_focal_interest=False
        )
        assert att == AttentionDecision.PERIPHERAL_AWARENESS

        disp, _ = ContextualResonanceEngine.calibrate_expression(active_user_thread, att, res)
        assert disp == ExpressionDisposition.REMAIN_SILENT

    def test_gc_454_preference_not_attention_deep_core_boundary(
        self, active_user_thread: ProspectiveThread
    ):
        """GC-454: Preference ≠ Attention (DEEP_CORE Attentional Boundary).

        Touching a DEEP_CORE preference is an attentional affordance, NOT a deterministic promoter.
        When cue is tangential and focal interest is not engaged, it stays peripheral.
        """
        assert active_user_thread.salience.resonance == ResonanceTier.DEEP_CORE

        cue = RealityEventContext(
            event_id="ev_rain",
            event_summary="今天外出一趟，下雨了，窗外有些阴沉",
            occurred_at=datetime.now(timezone.utc),
            turn_id="turn_rain_01",
        )
        res = ContextualResonanceEngine.evaluate_resonance(active_user_thread, cue)
        assert res == ResonanceDegree.TANGENTIAL

        att = ContextualResonanceEngine.decide_attention(
            active_user_thread, res, engage_focal_interest=False
        )
        assert att == AttentionDecision.PERIPHERAL_AWARENESS
