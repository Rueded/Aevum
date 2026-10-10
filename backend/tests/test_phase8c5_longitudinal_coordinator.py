"""Comprehensive Unit & Architecture Gate Test Suite for Phase 8C.5.

Longitudinal Coordinator & Context Assembly (Orchestration Step C4 & Step J).

Constitutional Invariant Verifications:
- Lock 1: Anti-Magical-Promotion (PROJECTED + time passage != CANONICAL).
- Lock 2: Derived temporal age view (identity.birth_date -> derived age; zero set_fact writes).
- Lock 3: Three-layer guard (calendar eligibility != personal progression; non-canonical signal).
- Lock 4 & Permanent Lock: Advisory lapse (Lapsed != Deleted; candidates excluded from turn
  competition but never deleted from candidate persistence).
- Lock 7: Canonical mutation singularity (zero canonical writes; BiographyPromotionService sole authority).
- Lock 8: Singular authoritative life clock holding effective_now.
- Lock 10 & 11: Deterministic boundary ordering; world calendar != personal reality.
- Replay Determinism: Bitwise stable prompt serialization and SHA-256 hash across turns.
- AST Boundary Audit: Zero DB imports, zero set_fact calls, zero network/LLM dependencies.
"""

from __future__ import annotations

import ast
from datetime import date, datetime, timezone
import pathlib
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.character.core_models import CharacterCore
from app.character.reality_context_builder import RealityContextBuilder
from app.character.reality_context_models import (
    EpistemicTruthType,
    GovernedRealityContext,
)
from app.reality.authoritative_clock import AuthoritativeLifeClock
from app.reality.calendar_boundary_engine import (
    CalendarBoundaryDetector,
    CalendarBoundaryType,
)
from app.reality.candidate_models import (
    CandidateHypothesis,
    CandidateLifecycleState,
    EvidenceFamily,
    InferenceEdgeType,
    InferenceScope,
    PlausibilityBreakdown,
    ProvenanceLineage,
    RealityTaxonomy,
)
from app.reality.guarded_transition_engine import GuardedTransitionEngine
from app.reality.longitudinal_coordinator import (
    LongitudinalCoordinator,
    LongitudinalCoordinatorResult,
    LongitudinalEvaluationStatus,
)
from app.reality.milestone_lapse_engine import MilestoneLapseEngine
from app.reality.models import CoreFactItem, FactAuthority, FactSource
from app.reality.reality_orchestration_service import RealityOrchestrationService
from app.reality.temporal_models import (
    Canonicality,
    EpistemicGrounding,
    LifeStage,
    TemporalGranularity,
    TemporalHorizon,
    TemporalInterval,
)
from app.reality.temporal_graph import TemporalNode
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
    """Helper to build a deterministic CandidateHypothesis."""
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
    """Helper to build a CharacterCore with typed CoreFactItem facts."""
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


class TestPhase8C5LongitudinalCoordinator:
    """Unit and integration test suite for LongitudinalCoordinator (Phase 8C.5)."""

    def test_derived_age_pure_view_zero_canonical_mutation(self):
        """Verify derived_age is a pure mathematical calculation from identity.birth_date.

        Constitutional Invariants (Lock 2 & Lock 7):
        - identity.birth_date is canonical ground truth.
        - derived_age = calendar_age(birth_date, effective_now).
        - Zero set_fact calls or writes to core.facts['identity.age'].
        """
        clock = AuthoritativeLifeClock(datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc))
        coordinator = LongitudinalCoordinator(clock=clock)

        core = _make_core_with_facts({
            "identity.birth_date": "2006-05-12",
        })

        result = coordinator.coordinate_turn(core=core)

        assert result.evaluation_status == LongitudinalEvaluationStatus.AVAILABLE
        assert result.derived_age == 20
        # Assert strict purity: core.facts['identity.age'] was NEVER created or modified
        assert "identity.age" not in core.facts
        assert core.facts["identity.birth_date"].value == "2006-05-12"

    def test_calendar_boundaries_detected_in_coordination(self):
        """Verify calendar boundary detection across advance in coordination turn (Lock 10, 11)."""
        clock = AuthoritativeLifeClock(datetime(2026, 5, 15, 12, 0, 0, tzinfo=timezone.utc))
        coordinator = LongitudinalCoordinator(clock=clock)

        core = _make_core_with_facts({
            "identity.birth_date": "2006-05-12",
        })

        # Advance past birthday from 2026-05-01
        last_eval = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = coordinator.coordinate_turn(core=core, last_evaluated_now=last_eval)

        assert result.evaluation_status == LongitudinalEvaluationStatus.AVAILABLE
        assert len(result.detected_boundaries) > 0
        b_types = [b.boundary_type for b in result.detected_boundaries]
        assert CalendarBoundaryType.BIRTHDAY in b_types

    @pytest.mark.asyncio
    async def test_candidate_lapse_excludes_from_competition_without_deletion(self):
        """Verify candidate temporal lapse excludes from turn competition without deleting from DB (Lock 4).

        Constitutional Invariant (Permanent Lock: Lapsed != Deleted):
        - A candidate whose intake window has elapsed (e.g. 2025-10 vs now 2026-01) is
          excluded from active competition in this turn.
        - The candidate is NEVER deleted from candidate persistence (all_candidates retains it).
        """
        clock = AuthoritativeLifeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
        coordinator = LongitudinalCoordinator(clock=clock)

        lapsed_cand = _make_candidate("cand_lapsed", "education.undergraduate_intake", "2025-10")
        active_cand = _make_candidate("cand_active", "education.degree_major", "Software Engineering")

        mock_session = AsyncMock()
        mock_repo = MagicMock()
        mock_repo.get_all_active_candidates = AsyncMock(return_value=[lapsed_cand, active_cand])

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
            character_id="aevum",
        )

        # 1. Verification of Step C4 result
        assert res.longitudinal_result is not None
        assert res.longitudinal_result.evaluation_status == LongitudinalEvaluationStatus.AVAILABLE
        assert "cand_lapsed" in res.longitudinal_result.temporally_lapsed_candidate_ids

        # 2. Verification of Competition exclusion
        # Only active_cand was eligible for competition; lapsed_cand was excluded
        assert not any(c.selected_candidate_id == "cand_lapsed" for c in res.choices)

        # 3. Constitutional Invariant: Lapsed != Deleted!
        # lapsed_cand is strictly preserved in res.candidates (retrieved from repo)
        c_ids = [c.candidate_id for c in res.candidates]
        assert "cand_lapsed" in c_ids
        assert "cand_active" in c_ids

        # 4. Zero delete calls made to repository
        mock_repo.delete_candidate.assert_not_called() if hasattr(mock_repo, "delete_candidate") else True

    def test_guarded_transition_signal_collected_non_canonical(self):
        """Verify guarded transition evaluation produces non-canonical signals without mutation (Lock 3, 7)."""
        clock = AuthoritativeLifeClock(datetime(2023, 1, 15, 12, 0, 0, tzinfo=timezone.utc))
        coordinator = LongitudinalCoordinator(clock=clock)

        core = _make_core_with_facts({"identity.birth_date": "2006-05-12"})

        spec = {
            "current_stage": LifeStage.SECONDARY_EDUCATION,
            "target_stage": LifeStage.PRE_UNIVERSITY,
            "current_stage_start_date": date(2021, 1, 1),
            "required_days": 365,
            "required_evidence_items": ("spm_certificate",),
            "provided_evidence_items": ("spm_certificate",),
        }

        result = coordinator.coordinate_turn(core=core, target_transition_spec=spec)

        assert result.evaluation_status == LongitudinalEvaluationStatus.AVAILABLE
        assert len(result.transition_signals) == 1
        signal = result.transition_signals[0]
        assert signal.target_stage == LifeStage.PRE_UNIVERSITY
        # Non-canonical invariant
        assert signal.is_canonical is False
        assert core.facts.get("education.level") is None

    def test_trajectory_realignment_in_coordination(self):
        """Verify trajectory realignment segregate lapsed pathways without history fabrication."""
        clock = AuthoritativeLifeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
        coordinator = LongitudinalCoordinator(clock=clock)

        node_past = TemporalNode(
            node_id="n_past",
            label="Past Intake",
            interval=TemporalInterval.create_exact(start=date(2025, 9, 1), end=date(2025, 9, 30)),
            temporal_horizon=TemporalHorizon.FUTURE,
            epistemic_grounding=EpistemicGrounding.PROJECTED,
            canonicality=Canonicality.NON_CANONICAL,
        )
        node_future = TemporalNode(
            node_id="n_future",
            label="Future Intake",
            interval=TemporalInterval.create_exact(start=date(2026, 9, 1), end=date(2026, 9, 30)),
            temporal_horizon=TemporalHorizon.FUTURE,
            epistemic_grounding=EpistemicGrounding.PROJECTED,
            canonicality=Canonicality.NON_CANONICAL,
        )

        traj_lapsed = LifeTrajectory(
            trajectory_id="traj_lapsed",
            pathway="FOUNDATION",
            status=TrajectoryStatus.COMPATIBLE,
            nodes=(node_past,),
        )
        traj_active = LifeTrajectory(
            trajectory_id="traj_active",
            pathway="STPM",
            status=TrajectoryStatus.COMPATIBLE,
            nodes=(node_future,),
        )

        result = coordinator.coordinate_turn(trajectories=(traj_lapsed, traj_active))

        assert result.evaluation_status == LongitudinalEvaluationStatus.AVAILABLE
        assert result.realignment_result is not None
        assert len(result.realignment_result.lapsed_trajectories) == 1
        assert result.realignment_result.lapsed_trajectories[0].trajectory_id == "traj_lapsed"
        assert len(result.realignment_result.active_trajectories) == 1
        assert result.realignment_result.active_trajectories[0].trajectory_id == "traj_active"

    def test_context_assembly_pure_serialization_replay_determinism(self):
        """Verify ContextBuilder serializes longitudinal context with 100% bitwise determinism."""
        clock = AuthoritativeLifeClock(datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc))
        coordinator = LongitudinalCoordinator(clock=clock)

        core = _make_core_with_facts({"identity.birth_date": "2006-05-12"})
        long_res = coordinator.coordinate_turn(core=core)

        ctx1 = RealityContextBuilder.build_context(
            core=core,
            longitudinal_result=long_res,
        )
        ctx2 = RealityContextBuilder.build_context(
            core=core,
            longitudinal_result=long_res,
        )

        # Context item verification
        assert len(ctx1.longitudinal_items) == 1
        l_item = ctx1.longitudinal_items[0]
        assert l_item.provenance.truth_type == EpistemicTruthType.LONGITUDINAL_TEMPORAL_CONTEXT
        assert l_item.is_canonical is False

        # Blocks serialization verification
        blocks1 = RealityContextBuilder.format_all_reality_blocks(ctx1)
        blocks2 = RealityContextBuilder.format_all_reality_blocks(ctx2)
        assert blocks1 == blocks2

        # Check longitudinal block structure
        long_block = next((b for b in blocks1 if "<longitudinal_life_context>" in b), None)
        assert long_block is not None
        assert '<derived_age status="MATHEMATICAL_VIEW">20</derived_age>' in long_block
        assert "<effective_time>2026-06-15T12:00:00+00:00</effective_time>" in long_block

        # Replay hash determinism
        assert ctx1.audit_metadata.context_hash_sha256 == ctx2.audit_metadata.context_hash_sha256

    @pytest.mark.asyncio
    async def test_coordination_failure_degrades_gracefully_zero_exclusions(self):
        """Verify coordination failure degrades to UNAVAILABLE with zero candidate exclusions."""
        failing_coordinator = MagicMock()
        failing_coordinator.coordinate_turn.side_effect = RuntimeError("Clock failure")

        cand = _make_candidate("cand_1", "education.degree_major", "Physics")
        mock_session = AsyncMock()
        mock_repo = MagicMock()
        mock_repo.get_all_active_candidates = AsyncMock(return_value=[cand])

        core = _make_core_with_facts({"identity.birth_date": "2006-05-12"})

        service = RealityOrchestrationService(
            session=mock_session,
            candidate_repo=mock_repo,
            longitudinal_coordinator=failing_coordinator,
        )

        res = await service.run_turn(
            user_input="Hello",
            core=core,
            character_id="aevum",
        )

        # Degraded status
        assert res.longitudinal_result is not None
        assert res.longitudinal_result.evaluation_status == LongitudinalEvaluationStatus.UNAVAILABLE
        # Zero false exclusions
        assert len(res.longitudinal_result.temporally_lapsed_candidate_ids) == 0
        assert len(res.candidates) == 1

    def test_ast_audit_pure_coordinator_module(self):
        """Verify static AST boundary of longitudinal_coordinator.py (zero DB, zero network, zero LLM)."""
        module_path = (
            pathlib.Path(__file__).parent.parent
            / "app"
            / "reality"
            / "longitudinal_coordinator.py"
        )
        assert module_path.exists()

        tree = ast.parse(module_path.read_text(encoding="utf-8"))

        forbidden_modules = {
            "sqlite3",
            "sqlalchemy",
            "aiohttp",
            "httpx",
            "requests",
            "urllib",
            "openai",
            "anthropic",
            "google.generativeai",
            "google.genai",
            "app.database",
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in forbidden_modules:
                        assert not alias.name.startswith(forbidden), (
                            f"Forbidden import '{alias.name}' in longitudinal_coordinator.py"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for forbidden in forbidden_modules:
                        assert not node.module.startswith(forbidden), (
                            f"Forbidden from-import '{node.module}' in longitudinal_coordinator.py"
                        )
            elif isinstance(node, ast.Call):
                # Ensure no set_fact calls
                if isinstance(node.func, ast.Attribute) and node.func.attr == "set_fact":
                    pytest.fail("Forbidden call to set_fact() in longitudinal_coordinator.py")
