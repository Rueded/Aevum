"""Phase 8C.4: Milestone Lapse & Trajectory Realignment Acceptance Tests.

Validates:
1. Lock 1 / Anti-Magical-Promotion Invariant:
   PROJECTED + time elapsed yields strictly ELAPSED_UNVERIFIED, NEVER automatically
   promotes to CONFIRMED_HISTORICAL or CANONICAL.
2. Evidenced Maturation:
   Only explicit corroborating evidence transitions an in-window/past milestone to
   EVIDENCED_IN_PROGRESS or CONFIRMED_HISTORICAL.
3. Lock 4 / Candidate Lapse Boundary:
   Emits read-only TemporalLapseSignal for elapsed candidate windows;
   zero candidate database mutation.
4. Trajectory Realignment:
   Prunes elapsed unconfirmed prospective pathways from the active plurality set
   without fabricating alternative personal histories.
5. Lock 7 & AST Singularity:
   Zero set_fact calls, zero DB writes, zero rogue clocks, zero LLM.
"""

from __future__ import annotations

import ast
from datetime import date, datetime, timedelta, timezone
import pathlib
import pytest
from pydantic import BaseModel, ValidationError

from app.reality.longitudinal_models import TemporalPosition
from app.reality.milestone_lapse_engine import (
    MilestoneEvaluationRecord,
    MilestoneLapseEngine,
    ProjectedMilestoneStatus,
    TemporalLapseSignal,
    TrajectoryRealignmentResult,
)
from app.reality.temporal_graph import TemporalNode
from app.reality.temporal_models import (
    Canonicality,
    EpistemicGrounding,
    LifeStage,
    TemporalGranularity,
    TemporalHorizon,
    TemporalInterval,
)
from app.reality.trajectory_engine import (
    LifeTrajectory,
    TrajectoryStatus,
)


class DummyCandidate(BaseModel):
    """Simple mock candidate representing an 8A candidate hypothesis."""
    candidate_id: str
    slot_name: str
    proposed_value: str


class TestPhase8C4MilestoneLapse:
    """Acceptance test suite for Phase 8C.4 Milestone Lapse and Trajectory Realignment Engine."""

    # -------------------------------------------------------------------------
    # 1. Lock 1: Anti-Magical-Promotion (PROJECTED + Time Elapsed != CANONICAL)
    # -------------------------------------------------------------------------

    def test_projected_milestone_progresses_to_elapsed_unverified_never_canonical(self):
        """THE CORE INVARIANT (Lock 1): Time passing cannot magically turn a projection into a confirmed fact.

        A projected milestone (graduation in 2028-07):
        - Before start: PENDING_FUTURE
        - During window: DUE_IN_WINDOW (not CANONICAL)
        - After window with NO evidence: ELAPSED_UNVERIFIED (strictly NOT CONFIRMED_HISTORICAL, NOT CANONICAL).
        """
        interval = TemporalInterval(
            earliest_start=date(2028, 7, 1),
            latest_start=date(2028, 7, 1),
            earliest_end=date(2028, 7, 31),
            latest_end=date(2028, 7, 31),
            granularity=TemporalGranularity.MONTH,
        )

        # 1. Evaluated in 2026 (Future)
        t_2026 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
        rec_future = MilestoneLapseEngine.evaluate_milestone(
            node_id="proj_grad_2028",
            label="Degree Graduation",
            interval=interval,
            epistemic_grounding=EpistemicGrounding.PROJECTED,
            effective_now=t_2026,
        )
        assert rec_future.temporal_position == TemporalPosition.FUTURE
        assert rec_future.status == ProjectedMilestoneStatus.PENDING_FUTURE
        assert rec_future.is_canonical is False

        # 2. Evaluated in July 2028 (In Window, but unobserved)
        t_due = datetime(2028, 7, 15, 12, 0, tzinfo=timezone.utc)
        rec_due = MilestoneLapseEngine.evaluate_milestone(
            node_id="proj_grad_2028",
            label="Degree Graduation",
            interval=interval,
            epistemic_grounding=EpistemicGrounding.PROJECTED,
            effective_now=t_due,
        )
        assert rec_due.temporal_position == TemporalPosition.IN_WINDOW
        assert rec_due.status == ProjectedMilestoneStatus.DUE_IN_WINDOW
        assert rec_due.is_canonical is False

        # 3. Evaluated in September 2028 (Window Passed, ZERO evidence)
        t_past = datetime(2028, 9, 1, 0, 0, tzinfo=timezone.utc)
        rec_elapsed = MilestoneLapseEngine.evaluate_milestone(
            node_id="proj_grad_2028",
            label="Degree Graduation",
            interval=interval,
            epistemic_grounding=EpistemicGrounding.PROJECTED,
            effective_now=t_past,
            corroborating_evidence=None,  # ZERO EVIDENCE
        )
        assert rec_elapsed.temporal_position == TemporalPosition.PAST

        # CRITICAL ASSERTION:
        assert rec_elapsed.status == ProjectedMilestoneStatus.ELAPSED_UNVERIFIED
        assert rec_elapsed.status != ProjectedMilestoneStatus.CONFIRMED_HISTORICAL
        assert rec_elapsed.is_canonical is False
        assert "NEVER automatically promoted to canonical historical fact" in rec_elapsed.explanation

    # -------------------------------------------------------------------------
    # 2. Evidenced Confirmation Transitions
    # -------------------------------------------------------------------------

    def test_explicit_evidence_authorizes_confirmed_historical(self):
        """When explicit evidence is present, past milestone is CONFIRMED_HISTORICAL."""
        interval = TemporalInterval(
            earliest_start=date(2025, 2, 1),
            latest_start=date(2025, 2, 1),
            earliest_end=date(2025, 3, 1),
            latest_end=date(2025, 3, 1),
            granularity=TemporalGranularity.MONTH,
        )
        t_now = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

        rec = MilestoneLapseEngine.evaluate_milestone(
            node_id="spm_exam_2025",
            label="SPM Examination",
            interval=interval,
            epistemic_grounding=EpistemicGrounding.PROJECTED,
            effective_now=t_now,
            corroborating_evidence=["spm.results.slip_observed", "user.claim.spm_passed"],
            canonicality=Canonicality.CANONICAL,
        )

        assert rec.temporal_position == TemporalPosition.PAST
        assert rec.status == ProjectedMilestoneStatus.CONFIRMED_HISTORICAL
        assert rec.is_canonical is True
        assert len(rec.evidence_keys) == 2

    # -------------------------------------------------------------------------
    # 3. Lock 4: Candidate Temporal Lapse Boundary (Signal-Only)
    # -------------------------------------------------------------------------

    def test_candidate_lapse_detection_emits_advisory_signal_without_db_mutation(self):
        """Lock 4: Elapsed candidate windows generate TemporalLapseSignal without DB mutation."""
        t_now = datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc)

        candidates = [
            # Candidate 1: Intake 2025-10 (Elapsed in Oct 2025 < Nov 2026) -> LAPSED
            DummyCandidate(
                candidate_id="cand_usm_2025",
                slot_name="education.undergraduate_intake",
                proposed_value="2025-10",
            ),
            # Candidate 2: Intake 2027-10 (Future intake window) -> ACTIVE
            DummyCandidate(
                candidate_id="cand_usm_2027",
                slot_name="education.undergraduate_intake",
                proposed_value="2027-10",
            ),
            # Candidate 3: SPM 2023 (Elapsed in Dec 2023) -> LAPSED
            DummyCandidate(
                candidate_id="cand_spm_2023",
                slot_name="education.spm_year",
                proposed_value="2023",
            ),
        ]

        signals = MilestoneLapseEngine.detect_candidate_lapses(candidates, t_now)

        assert len(signals) == 2
        lapsed_cids = {s.candidate_id for s in signals}
        assert lapsed_cids == {"cand_usm_2025", "cand_spm_2023"}

        for s in signals:
            assert isinstance(s, TemporalLapseSignal)
            assert s.is_advisory is True
            assert s.reason == "TIME_WINDOW_ELAPSED"
            assert s.effective_now == t_now

        # Guardrail check: Candidates were NOT mutated
        assert candidates[0].proposed_value == "2025-10"

    # -------------------------------------------------------------------------
    # 4. Trajectory Realignment (Plurality Pruning without History Fabrication)
    # -------------------------------------------------------------------------

    def test_trajectory_realignment_prunes_elapsed_prospective_pathways(self):
        """Verify realignment segregates pathways with elapsed unconfirmed nodes without fabricating history."""
        t_now = datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)

        # Trajectory A: Matriculation pathway whose start window was 2025-05 (Elapsed into the past)
        node_matrik_2025 = TemporalNode(
            node_id="node_matrik_start",
            label="Matriculation Studies",
            stage=LifeStage.PRE_UNIVERSITY,
            interval=TemporalInterval.create_month(2025, 5),
            temporal_horizon=TemporalHorizon.FUTURE,
            epistemic_grounding=EpistemicGrounding.PROJECTED,
            canonicality=Canonicality.NON_CANONICAL,
            pathway="MATRIKULASI",
        )
        traj_a = LifeTrajectory(
            trajectory_id="traj_matrikulasi",
            pathway="MATRIKULASI",
            nodes=(node_matrik_2025,),
            status=TrajectoryStatus.COMPATIBLE,
        )

        # Trajectory B: Future Foundation pathway starting 2026-09 (Still in the future)
        node_foundation_2026 = TemporalNode(
            node_id="node_foundation_start",
            label="Foundation Studies",
            stage=LifeStage.PRE_UNIVERSITY,
            interval=TemporalInterval.create_month(2026, 9),
            temporal_horizon=TemporalHorizon.FUTURE,
            epistemic_grounding=EpistemicGrounding.PROJECTED,
            canonicality=Canonicality.NON_CANONICAL,
            pathway="FOUNDATION",
        )
        traj_b = LifeTrajectory(
            trajectory_id="traj_foundation",
            pathway="FOUNDATION",
            nodes=(node_foundation_2026,),
            status=TrajectoryStatus.COMPATIBLE,
        )

        result = MilestoneLapseEngine.realign_trajectories((traj_a, traj_b), t_now)

        assert isinstance(result, TrajectoryRealignmentResult)
        assert len(result.active_trajectories) == 1
        assert result.active_trajectories[0].trajectory_id == "traj_foundation"

        assert len(result.lapsed_trajectories) == 1
        assert result.lapsed_trajectories[0].trajectory_id == "traj_matrikulasi"
        assert result.elapsed_milestones_count == 1

        # Invariant: Zero history fabrication (Traj A remains Matrikulasi, not modified)
        assert result.lapsed_trajectories[0].pathway == "MATRIKULASI"

    # -------------------------------------------------------------------------
    # 5. Lock 7 & AST Singularity: Zero DB / Zero set_fact() / Zero Rogue Clocks
    # -------------------------------------------------------------------------

    def test_ast_audit_pure_lapse_module(self):
        """Lock 7 AST Audit: Verify milestone_lapse_engine is 100% pure and mutation-free."""
        mod_path = pathlib.Path("app/reality/milestone_lapse_engine.py")
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
