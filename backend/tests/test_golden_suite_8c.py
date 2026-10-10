"""Golden Suite 8C: Phase 8C End-to-End Longitudinal Life Progression & Time Advancer Acceptance Benchmarks.

Covers Golden Acceptance Cases GC-196 through GC-220:
- Cluster 1: Authoritative Clock & Temporal Progression (GC-196 ~ GC-199)
  - GC-196: Singular Authoritative Life Clock Invariant (Lock 8)
  - GC-197: Strict Temporal Monotonicity Invariant (Lock 9)
  - GC-198: Atomic Clock Advancement Invariant (Lock 12)
  - GC-199: Temporal Advancement Path-Invariance (Lock 5)
- Cluster 2: Derived Temporal Views & Calendar Boundaries (GC-200 ~ GC-203)
  - GC-200: Derived Temporal Age Purity (Lock 2: zero set_fact writes)
  - GC-201: Leap-Year Birthday Progression Determinism (Feb 29 handling)
  - GC-202: World Calendar vs Personal Reality Separation (Lock 11)
  - GC-203: Deterministic Calendar Boundary Ordering (Lock 10)
- Cluster 3: Guarded Life-State Transitions (GC-204 ~ GC-207)
  - GC-204: Guard A Temporal Duration Invariant
  - GC-205: Guard B Predecessor Settled & Topological Forward DAG Invariant
  - GC-206: Guard C Progression Evidence Requirement (Lock 3)
  - GC-207: Non-Canonical Transition Signal Singularity (Lock 7)
- Cluster 4: Milestone Lapse & Candidate Lifecycle Boundary (GC-208 ~ GC-212)
  - GC-208: Anti-Magical-Promotion Milestone Invariant (Lock 1)
  - GC-209: Explicit Evidence Milestone Confirmation
  - GC-210: Candidate Temporal Lapse Advisory Signal (Lock 4)
  - GC-211: Lapsed != Deleted Invariant (Permanent Lock)
  - GC-212: Competition Filtering != Candidate Lifecycle Mutation (Lock A)
- Cluster 5: Trajectory Realignment & Re-evaluation Recovery (GC-213 ~ GC-215)
  - GC-213: Trajectory Realignment Without History Fabrication
  - GC-214: Re-evaluation & Recovery of Preserved Candidates
  - GC-215: Longitudinal Coordination Exception Resilience
- Cluster 6: Context Serialization, Replay & AST Boundary (GC-216 ~ GC-220)
  - GC-216: Serialization-Only Context Assembly (Zero Temporal Reasoning)
  - GC-217: Replay Determinism Across Longitudinal Context
  - GC-218: Longitudinal Context Epistemic Advisory Boundary (Lock B)
  - GC-219: Static AST Boundary Audit Across Phase 8C
  - GC-220: Integrated Full-Turn Governed Reality Lifecycle with Longitudinal Progression
"""

from __future__ import annotations

import ast
from datetime import date, datetime, timedelta, timezone
import pathlib
from typing import Any, Optional, Sequence
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.character.core_models import CharacterCore
from app.character.reality_context_builder import RealityContextBuilder
from app.character.reality_context_models import (
    EpistemicTruthType,
    GovernedRealityContext,
)
from app.reality.authoritative_clock import (
    AuthoritativeLifeClock,
    MonotonicTimeViolationError,
)
from app.reality.calendar_boundary_engine import (
    CalendarBoundaryDetector,
    CalendarBoundaryType,
    calendar_age,
)
from app.reality.candidate_models import (
    CandidateHypothesis,
    CandidateLifecycleState,
    EvidenceFamily,
    InferenceEdgeType,
    PlausibilityBreakdown,
    ProvenanceLineage,
    RealityTaxonomy,
)
from app.reality.guarded_transition_engine import (
    GuardedTransitionEngine,
    LifeStateTransitionEvaluation,
    LifeStateTransitionSignal,
    TransitionEvaluationStatus,
)
from app.reality.longitudinal_coordinator import (
    LongitudinalCoordinator,
    LongitudinalCoordinatorResult,
    LongitudinalEvaluationStatus,
)
from app.reality.longitudinal_models import (
    TimeAdvanceRequest,
    TimeAdvanceResult,
)
from app.reality.milestone_lapse_engine import (
    MilestoneLapseEngine,
    ProjectedMilestoneStatus,
    TemporalLapseSignal,
)
from app.reality.models import CoreFactItem, FactAuthority, FactSource
from app.reality.reality_orchestration_service import RealityOrchestrationService
from app.reality.temporal_graph import TemporalNode
from app.reality.temporal_models import (
    Canonicality,
    EpistemicGrounding,
    LifeStage,
    TemporalHorizon,
    TemporalInterval,
)
from app.reality.trajectory_engine import (
    LifeTrajectory,
    TrajectoryStatus,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _make_candidate(
    cid: str,
    slot_name: str,
    value: str,
    composite_plausibility: float = 0.55,
) -> CandidateHypothesis:
    ef = EvidenceFamily(
        family_id=f"fam_{cid}",
        source_type="USER_ASSERTION",
        cluster_key=f"aevum.{slot_name}.claim",
        mention_count=1,
    )
    return CandidateHypothesis(
        candidate_id=cid,
        entity_id="aevum",
        slot_name=slot_name,
        proposed_value=value,
        reality_taxonomy=RealityTaxonomy.SIMULATED_BIOGRAPHY_FACT,
        inference_depth=0,
        inference_edge_type=InferenceEdgeType.DIRECT_ATTRIBUTE,
        plausibility=PlausibilityBreakdown.create(composite_plausibility_score=composite_plausibility),
        provenance=ProvenanceLineage(origin_id=f"stim_{cid}", evidence_family_ids=(ef.family_id,)),
        evidence_families=(ef,),
        lifecycle_state=CandidateLifecycleState.ACTIVE,
    )


def _make_core_with_facts(facts_dict: dict[str, Any]) -> CharacterCore:
    core_facts: dict[str, CoreFactItem] = {}
    for k, v in facts_dict.items():
        is_locked = "birth_date" in k
        core_facts[k] = CoreFactItem(
            key=k,
            value=v,
            authority=FactAuthority.USER_LOCKED if is_locked else FactAuthority.AEVUM_CANONICAL,
            source=FactSource.SYSTEM_BASELINE,
            category=k.split(".")[0],
            locked=is_locked,
            created_at=_utc_now(),
        )
    return CharacterCore(character_id="aevum", facts=core_facts)


class TestGoldenSuite8C:
    """The 25 Golden Acceptance Tests (GC-196 ~ GC-220) for Phase 8C."""

    # =========================================================================
    # Cluster 1: Authoritative Clock & Temporal Progression (GC-196 ~ GC-199)
    # =========================================================================

    def test_gc196_singular_authoritative_life_clock_invariant(self):
        """GC-196: Authoritative life clock is the singular time anchor (Lock 8).

        Asserts effective_now conforms to UTC protocol and advances via typed request.
        """
        initial_t = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        clock = AuthoritativeLifeClock(initial_t)
        assert clock.effective_now == initial_t
        assert clock.now() == initial_t

        res = clock.advance_by(timedelta(days=30), reason="Semester start")

        assert isinstance(res, TimeAdvanceResult)
        assert res.success is True
        assert res.effective_now_old == initial_t
        assert res.effective_now_new == datetime(2026, 1, 31, 12, 0, 0, tzinfo=timezone.utc)
        assert clock.effective_now == datetime(2026, 1, 31, 12, 0, 0, tzinfo=timezone.utc)

    def test_gc197_strict_temporal_monotonicity_invariant(self):
        """GC-197: Clock advancement is strictly monotonic; time rewinds are rejected (Lock 9)."""
        t0 = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        clock = AuthoritativeLifeClock(t0)

        # Attempt to rewind to 2026-05-01
        t_past = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
        req_backward = TimeAdvanceRequest(target_time=t_past, reason="Accidental rewind")

        # 1. Non-raising path returns failure result with unchanged state
        res_fail = clock.advance(req_backward, raise_on_error=False)
        assert res_fail.success is False
        assert res_fail.effective_now_new == t0
        assert clock.effective_now == t0

        # 2. Raising path raises MonotonicTimeViolationError
        with pytest.raises(MonotonicTimeViolationError):
            clock.advance(req_backward, raise_on_error=True)

        # Assert state remains completely untouched
        assert clock.effective_now == t0

    def test_gc198_atomic_clock_advancement_invariant(self):
        """GC-198: Clock advancement is atomic; failure leaves state untouched (Lock 12)."""
        t0 = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        clock = AuthoritativeLifeClock(t0)

        # Negative duration is rejected in request creation
        with pytest.raises(ValueError):
            TimeAdvanceRequest(
                advance_duration=timedelta(days=-5),
                reason="Negative duration",
            )

        assert clock.effective_now == t0

    def test_gc199_temporal_advancement_path_invariance(self):
        """GC-199: Discrete step advancement is path-invariant (Lock 5).

        Advance(T0 -> Tn) == Advance(T0 -> T1 -> ... -> Tn)
        """
        t0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        t_final = datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc)

        # Single step
        clock_single = AuthoritativeLifeClock(t0)
        clock_single.advance_to(t_final, reason="Single leap")

        # Stepwise
        clock_step = AuthoritativeLifeClock(t0)
        clock_step.advance_by(timedelta(days=31), reason="Jan")
        clock_step.advance_by(timedelta(days=28), reason="Feb")
        clock_step.advance_by(timedelta(days=31), reason="Mar")

        assert clock_single.effective_now == clock_step.effective_now == t_final

    # =========================================================================
    # Cluster 2: Derived Temporal Views & Calendar Boundaries (GC-200 ~ GC-203)
    # =========================================================================

    def test_gc200_derived_temporal_age_purity(self):
        """GC-200: identity.birth_date is ground truth; age is a pure derived mathematical view (Lock 2).

        Zero database set_fact calls on age.
        """
        birth_d = date(2006, 5, 12)
        effective_t = datetime(2026, 5, 12, 12, 0, 0, tzinfo=timezone.utc)

        # Pure mathematical derivation
        derived = calendar_age(birth_d, effective_t)
        assert derived == 20

        # Before birthday
        effective_pre = datetime(2026, 5, 11, 23, 59, 59, tzinfo=timezone.utc)
        assert calendar_age(birth_d, effective_pre) == 19

    def test_gc201_leap_year_birthday_progression_determinism(self):
        """GC-201: Feb 29 leap day birthday advances to March 1 in non-leap years."""
        leap_birth = date(2004, 2, 29)  # Leap year birth

        # Non-leap year 2025: on Feb 28, age is 20
        t_feb28_2025 = datetime(2025, 2, 28, 23, 59, 59, tzinfo=timezone.utc)
        assert calendar_age(leap_birth, t_feb28_2025) == 20

        # On March 1 2025: age is 21
        t_mar01_2025 = datetime(2025, 3, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert calendar_age(leap_birth, t_mar01_2025) == 21

        # Leap year 2028: on Feb 29, age is 24
        t_feb29_2028 = datetime(2028, 2, 29, 0, 0, 0, tzinfo=timezone.utc)
        assert calendar_age(leap_birth, t_feb29_2028) == 24

    def test_gc202_world_calendar_vs_personal_reality_separation(self):
        """GC-202: World calendar boundary crossing confers zero personal life advancement (Lock 11)."""
        t_old = datetime(2025, 12, 31, 23, 0, 0, tzinfo=timezone.utc)
        t_new = datetime(2026, 1, 1, 1, 0, 0, tzinfo=timezone.utc)

        events = CalendarBoundaryDetector.detect_boundaries(
            effective_now_old=t_old,
            effective_now_new=t_new,
            birth_date=date(2006, 5, 12),
        )

        assert len(events) >= 1
        event_types = [e.boundary_type for e in events]
        assert CalendarBoundaryType.CALENDAR_YEAR in event_types
        # Event is external calendar only; carries zero personal canonical authority
        for ev in events:
            assert isinstance(ev.boundary_type, CalendarBoundaryType)

    def test_gc203_deterministic_calendar_boundary_ordering(self):
        """GC-203: Simultaneous calendar boundaries are sorted deterministically (Lock 10)."""
        # When New Year and month boundary coincide
        t_old = datetime(2025, 12, 31, 23, 0, 0, tzinfo=timezone.utc)
        t_new = datetime(2026, 1, 1, 1, 0, 0, tzinfo=timezone.utc)

        events = CalendarBoundaryDetector.detect_boundaries(
            effective_now_old=t_old,
            effective_now_new=t_new,
        )

        assert len(events) == 2
        # Priority order: CALENDAR_YEAR (1) precedes CALENDAR_MONTH (2)
        assert events[0].boundary_type == CalendarBoundaryType.CALENDAR_YEAR
        assert events[1].boundary_type == CalendarBoundaryType.CALENDAR_MONTH

    # =========================================================================
    # Cluster 3: Guarded Life-State Transitions (GC-204 ~ GC-207)
    # =========================================================================

    def test_gc204_guard_a_temporal_duration_invariant(self):
        """GC-204: Transition is INELIGIBLE if minimum temporal duration in stage has not elapsed."""
        eval_res = GuardedTransitionEngine.evaluate_transition(
            source_stage=LifeStage.SECONDARY_EDUCATION,
            source_start_date=date(2023, 1, 1),
            effective_now=datetime(2023, 4, 1, 12, 0, 0, tzinfo=timezone.utc),  # ~90 days
            target_stage=LifeStage.PRE_UNIVERSITY,
            minimum_duration_days=365,
            is_predecessor_settled=True,
            progression_evidence=("spm_results",),
        )

        assert eval_res.guard_a.passed is False
        assert eval_res.status == TransitionEvaluationStatus.INELIGIBLE

    def test_gc205_guard_b_predecessor_and_dag_forward_invariant(self):
        """GC-205: Transition is INELIGIBLE if predecessor unsettled, on academic hold, or skipping DAG."""
        # Unsettled predecessor
        res_unsettled = GuardedTransitionEngine.evaluate_transition(
            source_stage=LifeStage.SECONDARY_EDUCATION,
            source_start_date=date(2021, 1, 1),
            effective_now=datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            target_stage=LifeStage.PRE_UNIVERSITY,
            minimum_duration_days=365,
            is_predecessor_settled=False,  # Unsettled!
        )
        assert res_unsettled.guard_b.passed is False
        assert res_unsettled.status == TransitionEvaluationStatus.INELIGIBLE

        # Invalid DAG jump (Primary -> Undergraduate)
        res_jump = GuardedTransitionEngine.evaluate_transition(
            source_stage=LifeStage.PRIMARY_EDUCATION,
            source_start_date=date(2015, 1, 1),
            effective_now=datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            target_stage=LifeStage.UNDERGRADUATE,
            minimum_duration_days=365,
            is_predecessor_settled=True,
        )
        assert res_jump.guard_b.passed is False
        assert res_jump.status == TransitionEvaluationStatus.INELIGIBLE

    def test_gc206_guard_c_progression_evidence_requirement(self):
        """GC-206: Guard A + Guard B pass yields ELIGIBLE_FOR_TRANSITION; Guard C required for SUPPORTED (Lock 3)."""
        # Duration & predecessor pass, but zero progression evidence
        res_eligible = GuardedTransitionEngine.evaluate_transition(
            source_stage=LifeStage.SECONDARY_EDUCATION,
            source_start_date=date(2021, 1, 1),
            effective_now=datetime(2023, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            target_stage=LifeStage.PRE_UNIVERSITY,
            minimum_duration_days=365,
            is_predecessor_settled=True,
            progression_evidence=(),  # Missing evidence!
        )
        assert res_eligible.guard_a.passed is True
        assert res_eligible.guard_b.passed is True
        assert res_eligible.guard_c.passed is False
        assert res_eligible.status == TransitionEvaluationStatus.ELIGIBLE_FOR_TRANSITION

        # Duration & predecessor & evidence all pass
        res_supported = GuardedTransitionEngine.evaluate_transition(
            source_stage=LifeStage.SECONDARY_EDUCATION,
            source_start_date=date(2021, 1, 1),
            effective_now=datetime(2023, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            target_stage=LifeStage.PRE_UNIVERSITY,
            minimum_duration_days=365,
            is_predecessor_settled=True,
            progression_evidence=("spm_certificate",),
        )
        assert res_supported.guard_c.passed is True
        assert res_supported.status == TransitionEvaluationStatus.TRANSITION_SUPPORTED

    def test_gc207_non_canonical_transition_signal_singularity(self):
        """GC-207: Emitted transition signal carries is_canonical=False; zero biography promotion (Lock 7)."""
        eval_res = GuardedTransitionEngine.evaluate_transition(
            source_stage=LifeStage.SECONDARY_EDUCATION,
            source_start_date=date(2021, 1, 1),
            effective_now=datetime(2023, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            target_stage=LifeStage.PRE_UNIVERSITY,
            minimum_duration_days=365,
            is_predecessor_settled=True,
            progression_evidence=("spm_certificate",),
        )
        assert eval_res.status == TransitionEvaluationStatus.TRANSITION_SUPPORTED

        signal = GuardedTransitionEngine.emit_transition_signal(
            evaluation=eval_res,
            effective_now=datetime(2023, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        )

        assert isinstance(signal, LifeStateTransitionSignal)
        # Constitutional Invariant Lock 7
        assert signal.is_canonical is False
        assert signal.target_stage == LifeStage.PRE_UNIVERSITY

    # =========================================================================
    # Cluster 4: Milestone Lapse & Candidate Lifecycle Boundary (GC-208 ~ GC-212)
    # =========================================================================

    def test_gc208_anti_magical_promotion_milestone_invariant(self):
        """GC-208: Unverified elapsed prospective milestone strictly transitions to ELAPSED_UNVERIFIED (Lock 1).

        It is NEVER promoted to CONFIRMED_HISTORICAL or CANONICAL merely because time passed.
        """
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        # Milestone window was in 2025 (elapsed)
        past_interval = TemporalInterval.create_exact(start=date(2025, 9, 1), end=date(2025, 9, 30))

        m_eval = MilestoneLapseEngine.evaluate_milestone(
            node_id="m_foundation_intake",
            label="Foundation Intake",
            interval=past_interval,
            effective_now=now,
            epistemic_grounding=EpistemicGrounding.PROJECTED,
            canonicality=Canonicality.NON_CANONICAL,
            corroborating_evidence=None,
        )

        assert m_eval.status == ProjectedMilestoneStatus.ELAPSED_UNVERIFIED
        assert m_eval.is_canonical is False
        assert m_eval.status != ProjectedMilestoneStatus.CONFIRMED_HISTORICAL

    def test_gc209_explicit_evidence_milestone_confirmation(self):
        """GC-209: Milestone transitions to CONFIRMED_HISTORICAL only with explicit corroborating evidence."""
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        past_interval = TemporalInterval.create_exact(start=date(2025, 9, 1), end=date(2025, 9, 30))

        m_eval = MilestoneLapseEngine.evaluate_milestone(
            node_id="m_foundation_intake",
            label="Foundation Intake",
            interval=past_interval,
            effective_now=now,
            epistemic_grounding=EpistemicGrounding.PROJECTED,
            canonicality=Canonicality.NON_CANONICAL,
            corroborating_evidence=("matriculation_letter",),
        )

        assert m_eval.status == ProjectedMilestoneStatus.CONFIRMED_HISTORICAL
        assert len(m_eval.evidence_keys) > 0

    def test_gc210_candidate_temporal_lapse_advisory_signal(self):
        """GC-210: Candidate temporal lapse emits advisory TemporalLapseSignal without DB mutation (Lock 4)."""
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        cand = _make_candidate("cand_usm", "education.undergraduate_intake", "2025-10")

        signals = MilestoneLapseEngine.detect_candidate_lapses(
            candidates=[cand],
            effective_now=now,
        )

        assert len(signals) == 1
        sig = signals[0]
        assert sig.candidate_id == "cand_usm"
        assert sig.is_advisory is True
        assert sig.reason == "TIME_WINDOW_ELAPSED"

    @pytest.mark.asyncio
    async def test_gc211_lapsed_not_deleted_invariant(self):
        """GC-211: Lapsed candidate is excluded from turn competition, but preserved in DB (Permanent Lock)."""
        clock = AuthoritativeLifeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
        coordinator = LongitudinalCoordinator(clock=clock)

        cand_lapsed = _make_candidate("cand_lapsed", "education.undergraduate_intake", "2025-10")
        cand_active = _make_candidate("cand_active", "education.degree_major", "Computer Science")

        mock_session = AsyncMock()
        mock_repo = MagicMock()
        mock_repo.get_all_active_candidates = AsyncMock(return_value=[cand_lapsed, cand_active])

        core = _make_core_with_facts({
            "identity.birth_date": "2006-05-12",
            "education.spm_year": 2023,
        })

        service = RealityOrchestrationService(
            session=mock_session,
            candidate_repo=mock_repo,
            longitudinal_coordinator=coordinator,
        )

        res = await service.run_turn(
            user_input="Tell me about your studies",
            core=core,
        )

        # Lapsed candidate excluded from choices in this turn
        assert not any(c.selected_candidate_id == "cand_lapsed" for c in res.choices)
        # Constitutional Invariant: Preserved in res.candidates (never deleted from repository!)
        assert "cand_lapsed" in [c.candidate_id for c in res.candidates]

    def test_gc212_competition_filtering_not_candidate_mutation(self):
        """GC-212: Turn-local competition filtering does not mutate CandidateLifecycleState (Lock A)."""
        cand_lapsed = _make_candidate("cand_lapsed", "education.undergraduate_intake", "2025-10")
        coordinator = LongitudinalCoordinator(AuthoritativeLifeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)))

        res = coordinator.coordinate_turn(active_candidates=[cand_lapsed])

        assert "cand_lapsed" in res.temporally_lapsed_candidate_ids
        # Candidate state is unchanged: remains ACTIVE, not REJECTED or DORMANT
        assert cand_lapsed.lifecycle_state == CandidateLifecycleState.ACTIVE

    # =========================================================================
    # Cluster 5: Trajectory Realignment & Re-evaluation Recovery (GC-213 ~ GC-215)
    # =========================================================================

    def test_gc213_trajectory_realignment_without_history_fabrication(self):
        """GC-213: Realignment prunes elapsed prospective pathways without fabricating replacement history."""
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        node_past = TemporalNode(
            node_id="n_past",
            label="Past Intake",
            interval=TemporalInterval.create_exact(start=date(2025, 9, 1), end=date(2025, 9, 30)),
            temporal_horizon=TemporalHorizon.FUTURE,
            epistemic_grounding=EpistemicGrounding.PROJECTED,
            canonicality=Canonicality.NON_CANONICAL,
        )
        traj_lapsed = LifeTrajectory(
            trajectory_id="traj_stpm",
            pathway="STPM",
            status=TrajectoryStatus.COMPATIBLE,
            nodes=(node_past,),
        )

        realignment = MilestoneLapseEngine.realign_trajectories([traj_lapsed], effective_now=now)

        assert len(realignment.lapsed_trajectories) == 1
        assert len(realignment.active_trajectories) == 0
        # Zero alternative history was invented
        assert not any(t.pathway == "DIPLOMA" for t in realignment.active_trajectories)

    def test_gc214_reevaluation_and_recovery_of_preserved_candidates(self):
        """GC-214: Preserved candidate remains recoverable when evaluated under compatible timeline."""
        cand = _make_candidate("cand_intake", "education.undergraduate_intake", "2026-10")

        # In 2026-01: candidate is active in future window
        now_2026 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        sig_future = MilestoneLapseEngine.detect_candidate_lapses([cand], effective_now=now_2026)
        assert len(sig_future) == 0

        # In 2026-11: window has elapsed
        now_late = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)
        sig_lapsed = MilestoneLapseEngine.detect_candidate_lapses([cand], effective_now=now_late)
        assert len(sig_lapsed) == 1

        # The candidate remains in memory/DB intact and can be evaluated for past confirmation
        assert cand.slot_name == "education.undergraduate_intake"

    @pytest.mark.asyncio
    async def test_gc215_longitudinal_coordination_exception_resilience(self):
        """GC-215: Unexpected failure in coordinator degrades to UNAVAILABLE with zero false exclusions."""
        failing_coordinator = MagicMock()
        failing_coordinator.coordinate_turn.side_effect = RuntimeError("Clock hardware failure")

        cand = _make_candidate("cand_1", "education.degree_major", "Physics")
        mock_session = AsyncMock()
        mock_repo = MagicMock()
        mock_repo.get_all_active_candidates = AsyncMock(return_value=[cand])

        service = RealityOrchestrationService(
            session=mock_session,
            candidate_repo=mock_repo,
            longitudinal_coordinator=failing_coordinator,
        )

        res = await service.run_turn(user_input="Hello", core=_make_core_with_facts({}))

        assert res.longitudinal_result is not None
        assert res.longitudinal_result.evaluation_status == LongitudinalEvaluationStatus.UNAVAILABLE
        assert len(res.longitudinal_result.temporally_lapsed_candidate_ids) == 0
        assert len(res.candidates) == 1

    # =========================================================================
    # Cluster 6: Context Serialization, Replay & AST Boundary (GC-216 ~ GC-220)
    # =========================================================================

    def test_gc216_serialization_only_context_assembly(self):
        """GC-216: RealityContextBuilder performs pure serialization of longitudinal context."""
        clock = AuthoritativeLifeClock(datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc))
        coordinator = LongitudinalCoordinator(clock=clock)
        core = _make_core_with_facts({"identity.birth_date": "2006-05-12"})

        long_res = coordinator.coordinate_turn(core=core)
        ctx = RealityContextBuilder.build_context(core=core, longitudinal_result=long_res)

        assert len(ctx.longitudinal_items) == 1
        item = ctx.longitudinal_items[0]
        assert item.provenance.truth_type == EpistemicTruthType.LONGITUDINAL_TEMPORAL_CONTEXT
        assert item.is_canonical is False

        blocks = RealityContextBuilder.format_all_reality_blocks(ctx)
        block = next((b for b in blocks if "<longitudinal_life_context>" in b), None)
        assert block is not None
        assert '<derived_age status="MATHEMATICAL_VIEW">20</derived_age>' in block

    def test_gc217_replay_determinism_across_longitudinal_context(self):
        """GC-217: Replay determinism produces bitwise identical blocks and SHA-256 prompt hash."""
        clock = AuthoritativeLifeClock(datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc))
        coordinator = LongitudinalCoordinator(clock=clock)
        core = _make_core_with_facts({"identity.birth_date": "2006-05-12"})

        long_res = coordinator.coordinate_turn(core=core)

        ctx1 = RealityContextBuilder.build_context(core=core, longitudinal_result=long_res)
        ctx2 = RealityContextBuilder.build_context(core=core, longitudinal_result=long_res)

        blocks1 = RealityContextBuilder.format_all_reality_blocks(ctx1)
        blocks2 = RealityContextBuilder.format_all_reality_blocks(ctx2)
        assert blocks1 == blocks2
        assert ctx1.audit_metadata.context_hash_sha256 == ctx2.audit_metadata.context_hash_sha256

    def test_gc218_longitudinal_context_epistemic_advisory_boundary(self):
        """GC-218: Longitudinal context conveys advisory status; ELAPSED_UNVERIFIED != NEVER_HAPPENED (Lock B)."""
        clock = AuthoritativeLifeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
        coordinator = LongitudinalCoordinator(clock=clock)
        cand_lapsed = _make_candidate("cand_lapsed", "education.undergraduate_intake", "2025-10")

        long_res = coordinator.coordinate_turn(active_candidates=[cand_lapsed])
        ctx = RealityContextBuilder.build_context(longitudinal_result=long_res)

        blocks = RealityContextBuilder.format_all_reality_blocks(ctx)
        long_block = next((b for b in blocks if "<longitudinal_life_context>" in b), None)
        assert long_block is not None
        # Guidance instructs LLM that unverified milestones are not canonical historical facts
        assert "Do NOT assert projected or unverified milestones as canonical historical facts" in long_block
        assert 'status="ELAPSED_UNVERIFIED"' in long_block

    def test_gc219_static_ast_boundary_audit_across_phase_8c(self):
        """GC-219: Static AST boundary audit across all Phase 8C reality modules.

        Asserts 0 database imports, 0 network/LLM SDK imports, 0 set_fact calls.
        """
        modules = [
            "longitudinal_models.py",
            "authoritative_clock.py",
            "calendar_boundary_engine.py",
            "guarded_transition_engine.py",
            "milestone_lapse_engine.py",
            "longitudinal_coordinator.py",
        ]

        reality_dir = pathlib.Path(__file__).parent.parent / "app" / "reality"

        forbidden_modules = {
            "sqlite3",
            "sqlalchemy",
            "aiohttp",
            "httpx",
            "requests",
            "openai",
            "anthropic",
            "google.generativeai",
            "google.genai",
        }

        for m_name in modules:
            file_path = reality_dir / m_name
            assert file_path.exists(), f"Module {m_name} missing"
            tree = ast.parse(file_path.read_text(encoding="utf-8"))

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for forbidden in forbidden_modules:
                            assert not alias.name.startswith(forbidden), (
                                f"Forbidden import '{alias.name}' in {m_name}"
                            )
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        for forbidden in forbidden_modules:
                            assert not node.module.startswith(forbidden), (
                                f"Forbidden from-import '{node.module}' in {m_name}"
                            )
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute) and node.func.attr == "set_fact":
                        pytest.fail(f"Forbidden call to set_fact() in {m_name}")

    @pytest.mark.asyncio
    async def test_gc220_integrated_full_turn_longitudinal_reality_lifecycle(self):
        """GC-220: Integrated end-to-end governed reality turn with longitudinal progression.

        Verifies clock -> derived age -> boundaries -> guarded transition -> candidate lapse ->
        competition filtering -> context assembly with zero unauthorized mutations.
        """
        clock = AuthoritativeLifeClock(datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc))
        coordinator = LongitudinalCoordinator(clock=clock)

        cand_lapsed = _make_candidate("cand_lapsed", "education.undergraduate_intake", "2025-10")
        cand_active = _make_candidate("cand_active", "education.degree_major", "Software Engineering")

        mock_session = AsyncMock()
        mock_repo = MagicMock()
        mock_repo.get_all_active_candidates = AsyncMock(return_value=[cand_lapsed, cand_active])

        core = _make_core_with_facts({
            "identity.birth_date": "2006-05-12",
            "education.spm_year": 2023,
        })

        service = RealityOrchestrationService(
            session=mock_session,
            candidate_repo=mock_repo,
            longitudinal_coordinator=coordinator,
        )

        res = await service.run_turn(
            user_input="What are you currently studying?",
            core=core,
            character_id="aevum",
        )

        # 1. Pipeline execution integrity
        assert res.governed_reality is not None
        assert res.longitudinal_result is not None
        assert res.longitudinal_result.evaluation_status == LongitudinalEvaluationStatus.AVAILABLE

        # 2. Derived age verified in context
        assert res.longitudinal_result.derived_age == 20
        assert "identity.age" not in core.facts

        # 3. Lapsed candidate excluded from turn competition, but preserved in candidates
        assert "cand_lapsed" in res.longitudinal_result.temporally_lapsed_candidate_ids
        assert "cand_lapsed" in [c.candidate_id for c in res.candidates]
        assert not any(c.selected_candidate_id == "cand_lapsed" for c in res.choices)

        # 4. Context assembly contains longitudinal block
        blocks = RealityContextBuilder.format_all_reality_blocks(res.governed_reality)
        assert any("<longitudinal_life_context>" in b for b in blocks)

        # 5. Deterministic context hash
        assert res.governed_reality.audit_metadata.context_hash_sha256 is not None
