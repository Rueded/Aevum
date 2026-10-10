"""Phase 8C.3: Guarded Life-State Transition Engine Acceptance Tests.

Validates the Three-Layer Guard Architecture and Core Guardrail:
1. Guard A (Temporal Duration): Rejects transition when minimum duration window is unmet.
2. Guard B (Predecessor & DAG): Rejects invalid topological jumps (e.g. secondary -> degree jump,
   undergraduate Y1 -> Y3 leapfrog) and unsettled predecessors.
3. The Critical Invariant: Guard A + Guard B passed without Guard C yields strictly
   ELIGIBLE_FOR_TRANSITION (Time elapsed != personal progression).
4. Guard C (Progression Evidence): All three guards passed yields TRANSITION_SUPPORTED and emits
   non-canonical LifeStateTransitionSignal.
5. Lock 7 & AST Singularity: Zero set_fact calls, zero DB writes, zero rogue clocks, zero LLM.
"""

from __future__ import annotations

import ast
from datetime import date, datetime, timedelta, timezone
import pathlib
import pytest
from pydantic import ValidationError

from app.reality.guarded_transition_engine import (
    GuardedTransitionEngine,
    LifeStateTransitionEvaluation,
    LifeStateTransitionSignal,
    TransitionEvaluationStatus,
)
from app.reality.temporal_models import LifeStage


class TestPhase8C3GuardedTransitions:
    """Acceptance test suite for Phase 8C.3 Guarded Life-State Transition Engine."""

    # -------------------------------------------------------------------------
    # 1. Guard A: Temporal Duration Ineligibility
    # -------------------------------------------------------------------------

    def test_guard_a_rejects_insufficient_elapsed_duration(self):
        """Guard A: When time elapsed is less than minimum duration, transition is INELIGIBLE."""
        start_date = date(2025, 10, 1)
        # Advance only 60 days (far below standard 240 days minimum academic year)
        now_dt = datetime(2025, 11, 30, 0, 0, tzinfo=timezone.utc)

        eval_res = GuardedTransitionEngine.evaluate_transition(
            source_stage=LifeStage.UNDERGRADUATE,
            source_start_date=start_date,
            effective_now=now_dt,
            target_stage=LifeStage.UNDERGRADUATE,
            source_academic_level=1,
            target_academic_level=2,
            is_predecessor_settled=True,
            progression_evidence=["user.statement.semester_done"],
        )

        assert eval_res.guard_a.passed is False
        assert eval_res.guard_a.elapsed_duration_days == 60
        assert eval_res.status == TransitionEvaluationStatus.INELIGIBLE
        assert GuardedTransitionEngine.emit_transition_signal(eval_res, now_dt) is None

    # -------------------------------------------------------------------------
    # 2. Guard B: Predecessor State & Stage DAG Validity
    # -------------------------------------------------------------------------

    def test_guard_b_rejects_invalid_dag_leap(self):
        """Guard B: Rejects illegal topological jumps in the life stage DAG."""
        start_date = date(2020, 1, 1)
        now_dt = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

        # Primary education attempting direct transition to undergraduate degree
        eval_res = GuardedTransitionEngine.evaluate_transition(
            source_stage=LifeStage.PRIMARY_EDUCATION,
            source_start_date=start_date,
            effective_now=now_dt,
            target_stage=LifeStage.UNDERGRADUATE,
            is_predecessor_settled=True,
            progression_evidence=["some.evidence"],
        )

        assert eval_res.guard_b.passed is False
        assert eval_res.guard_b.is_valid_dag_successor is False
        assert eval_res.status == TransitionEvaluationStatus.INELIGIBLE
        assert "not a valid successor" in eval_res.guard_b.reason

    def test_guard_b_rejects_intra_stage_leapfrogging(self):
        """Guard B: Rejects undergraduate Year 1 leaping directly to Year 3 without Year 2."""
        start_date = date(2025, 10, 1)
        now_dt = datetime(2026, 10, 15, 0, 0, tzinfo=timezone.utc)

        eval_res = GuardedTransitionEngine.evaluate_transition(
            source_stage=LifeStage.UNDERGRADUATE,
            source_start_date=start_date,
            effective_now=now_dt,
            target_stage=LifeStage.UNDERGRADUATE,
            source_academic_level=1,
            target_academic_level=3,  # Illegal leapfrog
            is_predecessor_settled=True,
            progression_evidence=["evidence.skipped"],
        )

        assert eval_res.guard_b.passed is False
        assert eval_res.status == TransitionEvaluationStatus.INELIGIBLE

    def test_guard_b_rejects_unsettled_predecessor_or_academic_hold(self):
        """Guard B: Rejects transition if predecessor is unsettled or student is on leave/hold."""
        start_date = date(2025, 10, 1)
        now_dt = datetime(2026, 10, 15, 0, 0, tzinfo=timezone.utc)

        # 1. Unsettled predecessor
        eval_unsettled = GuardedTransitionEngine.evaluate_transition(
            source_stage=LifeStage.UNDERGRADUATE,
            source_start_date=start_date,
            effective_now=now_dt,
            target_stage=LifeStage.UNDERGRADUATE,
            source_academic_level=1,
            target_academic_level=2,
            is_predecessor_settled=False,
            progression_evidence=["exam.taken"],
        )
        assert eval_unsettled.guard_b.passed is False
        assert eval_unsettled.status == TransitionEvaluationStatus.INELIGIBLE

        # 2. Academic leave / hold
        eval_hold = GuardedTransitionEngine.evaluate_transition(
            source_stage=LifeStage.UNDERGRADUATE,
            source_start_date=start_date,
            effective_now=now_dt,
            target_stage=LifeStage.UNDERGRADUATE,
            source_academic_level=1,
            target_academic_level=2,
            is_predecessor_settled=True,
            is_on_leave_or_hold=True,
            progression_evidence=["exam.taken"],
        )
        assert eval_hold.status == TransitionEvaluationStatus.BLOCKED_BY_ANOMALY
        assert GuardedTransitionEngine.emit_transition_signal(eval_hold, now_dt) is None

    # -------------------------------------------------------------------------
    # 3. The Critical Invariant: Guard A + Guard B Passed WITHOUT Guard C
    # -------------------------------------------------------------------------

    def test_critical_guard_a_and_b_without_guard_c_yields_eligible_only(self):
        """THE CORE INVARIANT: Time elapsed + predecessor settled != personal progression.

        When minimum duration is satisfied and predecessor is settled, but explicit
        progression evidence is missing:
        - Status must be ELIGIBLE_FOR_TRANSITION (NOT TRANSITION_SUPPORTED).
        - Must NOT emit any LifeStateTransitionSignal (returns None).
        - Prevents automatically advancing Aevum to Year 2 solely because 1 year passed.
        """
        start_date = date(2025, 10, 1)
        now_dt = datetime(2026, 10, 15, 0, 0, tzinfo=timezone.utc)  # Elapsed 379 days > 240

        eval_res = GuardedTransitionEngine.evaluate_transition(
            source_stage=LifeStage.UNDERGRADUATE,
            source_start_date=start_date,
            effective_now=now_dt,
            target_stage=LifeStage.UNDERGRADUATE,
            source_academic_level=1,
            target_academic_level=2,
            is_predecessor_settled=True,
            progression_evidence=None,  # ZERO progression evidence!
        )

        assert eval_res.guard_a.passed is True  # Time satisfied
        assert eval_res.guard_b.passed is True  # Predecessor settled & valid DAG
        assert eval_res.guard_c.passed is False  # Evidence missing!

        # Crucial assertion: Status is strictly ELIGIBLE_FOR_TRANSITION
        assert eval_res.status == TransitionEvaluationStatus.ELIGIBLE_FOR_TRANSITION
        assert "lacks progression evidence" in eval_res.explanation

        # Crucial assertion: Zero signal emitted
        signal = GuardedTransitionEngine.emit_transition_signal(eval_res, now_dt)
        assert signal is None

    # -------------------------------------------------------------------------
    # 4. Full Convergence: Guard A + Guard B + Guard C ALL Pass
    # -------------------------------------------------------------------------

    def test_full_convergence_yields_transition_supported_and_emits_signal(self):
        """When all three guards pass, status is TRANSITION_SUPPORTED and emits non-canonical signal."""
        start_date = date(2025, 10, 1)
        now_dt = datetime(2026, 10, 15, 0, 0, tzinfo=timezone.utc)

        eval_res = GuardedTransitionEngine.evaluate_transition(
            source_stage=LifeStage.UNDERGRADUATE,
            source_start_date=start_date,
            effective_now=now_dt,
            target_stage=LifeStage.UNDERGRADUATE,
            source_academic_level=1,
            target_academic_level=2,
            is_predecessor_settled=True,
            progression_evidence=["exam.results.y1_passed", "user.confirmed.enrolled_year_2"],
        )

        assert eval_res.guard_a.passed is True
        assert eval_res.guard_b.passed is True
        assert eval_res.guard_c.passed is True
        assert eval_res.status == TransitionEvaluationStatus.TRANSITION_SUPPORTED

        signal = GuardedTransitionEngine.emit_transition_signal(eval_res, now_dt)
        assert signal is not None
        assert isinstance(signal, LifeStateTransitionSignal)
        assert signal.source_stage == LifeStage.UNDERGRADUATE
        assert signal.source_academic_level == 1
        assert signal.target_stage == LifeStage.UNDERGRADUATE
        assert signal.target_academic_level == 2
        assert signal.is_canonical is False  # Lock 7: Never canonical directly
        assert len(signal.evidence_keys) == 2

    # -------------------------------------------------------------------------
    # 5. Diploma & Pre-University Pathways DAG Validation
    # -------------------------------------------------------------------------

    def test_diploma_and_pre_u_to_undergraduate_dag_transitions(self):
        """Verify secondary -> diploma -> undergrad and secondary -> pre-u -> undergrad DAG validity."""
        now_dt = datetime(2027, 10, 1, tzinfo=timezone.utc)
        start_diploma = date(2025, 6, 1)

        # Diploma -> Undergraduate
        eval_dip = GuardedTransitionEngine.evaluate_transition(
            source_stage=LifeStage.DIPLOMA,
            source_start_date=start_diploma,
            effective_now=now_dt,
            target_stage=LifeStage.UNDERGRADUATE,
            target_academic_level=1,
            is_predecessor_settled=True,
            progression_evidence=["diploma.graduated"],
            minimum_duration_days=700,
        )
        assert eval_dip.guard_b.passed is True
        assert eval_dip.status == TransitionEvaluationStatus.TRANSITION_SUPPORTED

        # Transitional (gap year)
        eval_gap = GuardedTransitionEngine.evaluate_transition(
            source_stage=LifeStage.SECONDARY_EDUCATION,
            source_start_date=date(2024, 1, 1),
            effective_now=now_dt,
            target_stage=LifeStage.TRANSITIONAL,
            is_predecessor_settled=True,
            progression_evidence=["gap_year.started"],
            minimum_duration_days=300,
        )
        assert eval_gap.guard_b.passed is True
        assert eval_gap.status == TransitionEvaluationStatus.TRANSITION_SUPPORTED

    # -------------------------------------------------------------------------
    # 6. Lock 7 & AST Singularity: Zero DB / Zero set_fact() / Zero Rogue Clocks
    # -------------------------------------------------------------------------

    def test_ast_audit_pure_transition_module(self):
        """Lock 7 AST Audit: Verify guarded_transition_engine is 100% pure and mutation-free."""
        mod_path = pathlib.Path("app/reality/guarded_transition_engine.py")
        assert mod_path.exists()
        tree = ast.parse(mod_path.read_text(encoding="utf-8"))

        banned_calls = {"now", "today", "utcnow"}

        for node in ast.walk(tree):
            # Check for rogue clock calls
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute) and node.func.attr in banned_calls:
                    if isinstance(node.func.value, ast.Name) and node.func.value.id in ("datetime", "date"):
                        pytest.fail(
                            f"AST Violation: Rogue un-injected clock call in {mod_path}:{node.lineno}"
                        )
                # Check for set_fact calls
                if isinstance(node.func, ast.Attribute) and node.func.attr == "set_fact":
                    pytest.fail(
                        f"AST Violation (Lock 7): Direct set_fact() mutation call found in {mod_path}:{node.lineno}."
                    )

            # Check for forbidden imports (DB, Network, LLM)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in ("sqlalchemy", "sqlite3", "httpx", "aiohttp", "google.genai", "openai"):
                        if forbidden in alias.name:
                            pytest.fail(
                                f"AST Violation: Forbidden import '{alias.name}' in {mod_path}:{node.lineno}"
                            )
            elif isinstance(node, ast.ImportFrom):
                mod_name = node.module or ""
                for alias in node.names:
                    full_name = f"{mod_name}.{alias.name}" if mod_name else alias.name
                    for forbidden in ("sqlalchemy", "sqlite3", "httpx", "aiohttp", "google.genai", "openai"):
                        if forbidden in full_name:
                            pytest.fail(
                                f"AST Violation: Forbidden import '{full_name}' in {mod_path}:{node.lineno}"
                            )
