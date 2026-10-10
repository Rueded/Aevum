"""Comprehensive Unit & Architecture Gate Test Suite for Phase 8B.5.

Retrospective Timeline Orchestration & Conflict Delegation (Step C3).

Constitutional Verification (Locks 1 through 8):
1. HARD + COMPATIBLE trajectory -> candidate remains eligible (Lock 1).
2. HARD + UNDETERMINED -> candidate remains eligible (Lock 1).
3. HARD + ADVISORY -> candidate remains eligible (Lock 1).
4. ALL HARD -> candidate excluded (Lock 1).
5. Canonical temporal conflict delegates to existing RealityRepairService (Lock 3).
6. C3 does not choose repair level (Lock 2).
7. Temporal evidence adapter follows explicit schema (Lock 7).
8. No repair target is selected merely through tuple ordering (Lock 8).
9. UNAVAILABLE temporal evaluation causes no false exclusion (Lock 4).
10. UNAVAILABLE != no conflict (Lock 4).
11. Ambiguous trajectories serialize without winner selection (Lock 5).
12. ContextBuilder performs no temporal reasoning (Lock 5).
13. Projected/derived epistemic status remains unchanged (Lock 1 & Invariant C).
14. C3 does not score/rank candidates (Lock 6).
15. Zero direct canonical mutation from C3 (Lock 9).
16. Static AST boundary audit (Zero DB, zero network, zero LLM, zero set_fact, zero tokens).
"""

from __future__ import annotations

import ast
from datetime import date, datetime, timezone
import pathlib
import pytest
from pydantic import ValidationError

from app.character.core_models import CharacterCore
from app.character.reality_context_builder import RealityContextBuilder
from app.character.reality_context_models import (
    EpistemicTruthType,
    GovernedRealityContext,
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
from app.reality.models import CoreFactItem, FactAuthority, FactSource
from app.reality.repair_models import RealityRepairResult, RepairLevel
from app.reality.repair_service import RealityRepairService
from app.reality.temporal_models import (
    Canonicality,
    EpistemicGrounding,
    LifeStage,
    TemporalGranularity,
    TemporalHorizon,
    TemporalInterval,
)
from app.reality.temporal_graph import (
    ConstraintStatus,
    TemporalNode,
)
from app.reality.trajectory_engine import (
    LifeTrajectory,
    TimelineTrajectoryEngine,
    TrajectoryPluralityResult,
    TrajectoryStatus,
)
from app.reality.timeline_orchestration_coordinator import (
    TemporalConflictSignal,
    TemporalEvaluationStatus,
    TimelineEvidenceAdapter,
    TimelineOrchestrationCoordinator,
    TimelineOrchestrationResult,
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
        core_facts[k] = CoreFactItem(
            key=k,
            value=v,
            authority=FactAuthority.AEVUM_CANONICAL,
            source=FactSource.SYSTEM_BASELINE,
            category=k.split(".")[0],
            created_at=_utc_now(),
        )
    return CharacterCore(character_id="aevum", facts=core_facts)


class TestPhase8B5TimelineOrchestration:
    """Comprehensive test suite for Phase 8B.5 Retrospective Timeline Orchestration."""

    # -------------------------------------------------------------------------
    # 1. HARD + COMPATIBLE trajectory -> candidate remains eligible (Lock 1)
    # -------------------------------------------------------------------------
    def test_lock1_hard_plus_compatible_candidate_remains_eligible(self):
        """A candidate associated with multiple trajectories where one is HARD_INCOMPATIBLE

        and one is COMPATIBLE remains eligible for competition (Lock 1).
        """
        coordinator = TimelineOrchestrationCoordinator()
        cand = _make_candidate("c_dual_1", "education.pathway", "GENERAL_HIGHER_ED")

        # Candidate yields 1 HARD and 1 COMPATIBLE trajectory
        eval_override = {
            "c_dual_1": (TrajectoryStatus.HARD_INCOMPATIBLE, TrajectoryStatus.COMPATIBLE),
        }
        result = coordinator.coordinate_turn(
            active_candidates=[cand],
            candidate_evaluations_override=eval_override,
        )

        assert result.evaluation_status == TemporalEvaluationStatus.AVAILABLE
        assert "c_dual_1" not in result.temporally_incompatible_candidate_ids
        assert result.is_candidate_eligible("c_dual_1") is True

    # -------------------------------------------------------------------------
    # 2. HARD + UNDETERMINED -> candidate remains eligible (Lock 1)
    # -------------------------------------------------------------------------
    def test_lock1_hard_plus_undetermined_candidate_remains_eligible(self):
        """A candidate with HARD_INCOMPATIBLE and UNDETERMINED trajectories remains eligible.

        (Incomplete evidence is not proof of impossibility).
        """
        coordinator = TimelineOrchestrationCoordinator()
        cand = _make_candidate("c_dual_2", "education.pathway", "GENERAL_HIGHER_ED")

        eval_override = {
            "c_dual_2": (TrajectoryStatus.HARD_INCOMPATIBLE, ConstraintStatus.UNDETERMINED),
        }
        result = coordinator.coordinate_turn(
            active_candidates=[cand],
            candidate_evaluations_override=eval_override,
        )

        assert result.evaluation_status == TemporalEvaluationStatus.AVAILABLE
        assert "c_dual_2" not in result.temporally_incompatible_candidate_ids
        assert result.is_candidate_eligible("c_dual_2") is True

    # -------------------------------------------------------------------------
    # 3. HARD + ADVISORY -> candidate remains eligible (Lock 1)
    # -------------------------------------------------------------------------
    def test_lock1_hard_plus_advisory_candidate_remains_eligible(self):
        """A candidate with HARD_INCOMPATIBLE and ADVISORY_ANOMALY trajectories remains eligible."""
        coordinator = TimelineOrchestrationCoordinator()
        cand = _make_candidate("c_dual_3", "education.pathway", "GENERAL_HIGHER_ED")

        eval_override = {
            "c_dual_3": (TrajectoryStatus.HARD_INCOMPATIBLE, TrajectoryStatus.ADVISORY_ANOMALY),
        }
        result = coordinator.coordinate_turn(
            active_candidates=[cand],
            candidate_evaluations_override=eval_override,
        )

        assert result.evaluation_status == TemporalEvaluationStatus.AVAILABLE
        assert "c_dual_3" not in result.temporally_incompatible_candidate_ids
        assert result.is_candidate_eligible("c_dual_3") is True

    # -------------------------------------------------------------------------
    # 4. ALL HARD -> candidate excluded (Lock 1)
    # -------------------------------------------------------------------------
    def test_lock1_all_hard_candidate_is_excluded(self):
        """A candidate where ALL applicable trajectories are HARD_INCOMPATIBLE is excluded."""
        coordinator = TimelineOrchestrationCoordinator()
        cand = _make_candidate("c_all_hard", "education.pathway", "IMPOSSIBLE_PATHWAY")

        eval_override = {
            "c_all_hard": (TrajectoryStatus.HARD_INCOMPATIBLE, TrajectoryStatus.HARD_INCOMPATIBLE),
        }
        result = coordinator.coordinate_turn(
            active_candidates=[cand],
            candidate_evaluations_override=eval_override,
        )

        assert result.evaluation_status == TemporalEvaluationStatus.AVAILABLE
        assert "c_all_hard" in result.temporally_incompatible_candidate_ids
        assert result.is_candidate_eligible("c_all_hard") is False

    # -------------------------------------------------------------------------
    # 5. Canonical temporal conflict delegates to existing RealityRepairService (Lock 3)
    # -------------------------------------------------------------------------
    def test_lock3_canonical_conflict_delegates_to_reality_repair_service(self):
        """When a canonical temporal contradiction is detected, C3 delegates directly

        to the existing Phase 7 RealityRepairService via timeline_evidence (Lock 3).
        """
        coordinator = TimelineOrchestrationCoordinator()
        # Inverted history: SPM in 2023, but Undergraduate intake in 2020!
        core = _make_core_with_facts({
            "identity.birth_date": "2006-05-12",
            "education.spm_year": 2023,
            "education.undergraduate_intake": "2020-10",
        })

        result = coordinator.coordinate_turn(core=core)

        assert result.evaluation_status == TemporalEvaluationStatus.AVAILABLE
        assert result.canonical_conflict_signal is not None
        signal = result.canonical_conflict_signal

        # Verify delegation to existing RealityRepairService
        adapter = signal.temporal_evidence
        evidence_dict = adapter.to_repair_evidence_dict()
        repair_res = RealityRepairService.repair(
            conflict_type="TEMPORAL_CONFLICT",
            timeline_evidence=evidence_dict,
            rationale=signal.rationale,
        )

        assert isinstance(repair_res, RealityRepairResult)
        assert repair_res.canonical_mutated is False
        assert repair_res.compensatory_biography_created is False
        assert repair_res.repair_level in (
            RepairLevel.LEVEL_2_TEMPORAL_REINTERPRETATION,
            RepairLevel.LEVEL_5_GRACEFUL_UNCERTAINTY,
        )

    # -------------------------------------------------------------------------
    # 6. C3 does not choose repair level (Lock 2)
    # -------------------------------------------------------------------------
    def test_lock2_c3_has_zero_repair_policy_authority(self):
        """C3 produces signal and evidence only. It has zero repair-policy authority.

        suggested_repair_level is strictly forbidden (Lock 2).
        """
        coordinator = TimelineOrchestrationCoordinator()
        core = _make_core_with_facts({
            "identity.birth_date": "2006-05-12",
            "education.spm_year": 2023,
            "education.undergraduate_intake": "2020-10",
        })

        result = coordinator.coordinate_turn(core=core)
        signal = result.canonical_conflict_signal
        assert signal is not None

        # Lock 2: C3 signal does NOT specify suggested_repair_level
        assert not hasattr(signal, "suggested_repair_level")
        assert "suggested_repair_level" not in TemporalConflictSignal.model_fields

    # -------------------------------------------------------------------------
    # 7. Temporal evidence adapter follows explicit schema (Lock 7)
    # -------------------------------------------------------------------------
    def test_lock7_temporal_evidence_adapter_follows_explicit_schema(self):
        """TimelineEvidenceAdapter conforms strictly to the Phase 7 timeline_evidence schema.

        Extra fields are forbidden.
        """
        adapter = TimelineEvidenceAdapter(
            independent_timeline_supported=True,
            temporal_split={"past": "SPM 2023", "present": "Degree 2025"},
            conflicting_node_ids=("node_spm", "node_undergrad"),
            evidence_fact_keys=("education.spm_year", "education.undergraduate_intake"),
            explanation="Reconcilable past vs present stages.",
        )

        evidence_dict = adapter.to_repair_evidence_dict()
        assert evidence_dict["independent_timeline_supported"] is True
        assert evidence_dict["temporal_split"] == {"past": "SPM 2023", "present": "Degree 2025"}
        assert evidence_dict["conflicting_node_ids"] == ["node_spm", "node_undergrad"]
        assert evidence_dict["evidence_fact_keys"] == ["education.spm_year", "education.undergraduate_intake"]
        assert "explanation" in evidence_dict

        # Extra fields forbidden by Pydantic extra='forbid'
        with pytest.raises(ValidationError):
            TimelineEvidenceAdapter(
                independent_timeline_supported=True,
                arbitrary_unstructured_field="forbidden",  # type: ignore[call-arg]
            )

    # -------------------------------------------------------------------------
    # 8. No repair target is selected merely through tuple ordering (Lock 8)
    # -------------------------------------------------------------------------
    def test_lock8_no_implicit_repair_target_by_tuple_ordering(self):
        """Conflicting facts in TemporalConflictSignal are symmetric.

        Tuple index [0] MUST NOT designate an erroneous fact or target (Lock 8).
        """
        coordinator = TimelineOrchestrationCoordinator()
        core = _make_core_with_facts({
            "identity.birth_date": "2006-05-12",
            "education.spm_year": 2023,
            "education.undergraduate_intake": "2020-10",
        })

        result = coordinator.coordinate_turn(core=core)
        signal = result.canonical_conflict_signal
        assert signal is not None

        # Verify symmetric representation (no single fact singled out as claim_key)
        assert len(signal.conflicting_fact_keys) == 2
        assert "education.spm_year" in signal.conflicting_fact_keys
        assert "education.undergraduate_intake" in signal.conflicting_fact_keys

        # Reversing fact tuple produces symmetric dictionary
        evidence_dict = signal.temporal_evidence.to_repair_evidence_dict()
        res1 = RealityRepairService.repair(
            conflict_type="TEMPORAL_CONFLICT",
            timeline_evidence=evidence_dict,
            rationale="Run 1",
        )

        # Inverted fact keys adapter
        rev_adapter = TimelineEvidenceAdapter(
            independent_timeline_supported=signal.temporal_evidence.independent_timeline_supported,
            temporal_split=signal.temporal_evidence.temporal_split,
            conflicting_node_ids=tuple(reversed(signal.temporal_evidence.conflicting_node_ids)),
            evidence_fact_keys=tuple(reversed(signal.temporal_evidence.evidence_fact_keys)),
            explanation="Reversed check",
        )
        res2 = RealityRepairService.repair(
            conflict_type="TEMPORAL_CONFLICT",
            timeline_evidence=rev_adapter.to_repair_evidence_dict(),
            rationale="Run 2",
        )

        assert res1.repair_level == res2.repair_level
        assert res1.repair_action == res2.repair_action

    # -------------------------------------------------------------------------
    # 9. UNAVAILABLE temporal evaluation causes no false exclusion (Lock 4)
    # -------------------------------------------------------------------------
    def test_lock4_unavailable_evaluation_causes_no_false_exclusions(self):
        """When timeline orchestration degrades to UNAVAILABLE, zero candidates are excluded (Lock 4)."""
        coordinator = TimelineOrchestrationCoordinator()
        cands = [
            _make_candidate("c_1", "education.major", "CS"),
            _make_candidate("c_2", "education.pathway", "DIPLOMA"),
        ]

        # Simulate unexpected engine exception during coordinate_turn
        # by passing an object that raises during attribute access
        class BrokenCore:
            @property
            def facts(self):
                raise RuntimeError("Database engine explosion")

        result = coordinator.coordinate_turn(
            core=BrokenCore(),  # type: ignore[arg-type]
            active_candidates=cands,
        )

        assert result.evaluation_status == TemporalEvaluationStatus.UNAVAILABLE
        assert result.temporally_incompatible_candidate_ids == ()
        assert result.is_candidate_eligible("c_1") is True
        assert result.is_candidate_eligible("c_2") is True
        assert result.canonical_conflict_signal is None
        assert result.evaluation_error is not None

    # -------------------------------------------------------------------------
    # 10. UNAVAILABLE != no conflict (Lock 4)
    # -------------------------------------------------------------------------
    def test_lock4_unavailable_is_distinct_from_no_conflict(self):
        """NOT EVALUATED != NO CONFLICT.

        UNAVAILABLE represents unknown evaluation state, not zero conflicts (Lock 4).
        """
        # Case A: Normal evaluation with no conflict
        coordinator = TimelineOrchestrationCoordinator()
        core_normal = _make_core_with_facts({
            "identity.birth_date": "2006-05-12",
            "education.spm_year": 2023,
            "education.undergraduate_intake": "2025-10",
        })
        res_normal = coordinator.coordinate_turn(core=core_normal)
        assert res_normal.evaluation_status == TemporalEvaluationStatus.AVAILABLE
        assert res_normal.canonical_conflict_signal is None
        assert res_normal.evaluation_error is None

        # Case B: Failure degradation
        res_failed = TimelineOrchestrationResult(
            evaluation_status=TemporalEvaluationStatus.UNAVAILABLE,
            evaluation_error="Infrastructure timeout",
        )
        assert res_failed.evaluation_status == TemporalEvaluationStatus.UNAVAILABLE
        assert res_failed.evaluation_status != res_normal.evaluation_status

    # -------------------------------------------------------------------------
    # 11. Ambiguous trajectories serialize without winner selection (Lock 5)
    # -------------------------------------------------------------------------
    def test_lock5_ambiguous_trajectories_serialize_without_winner_selection(self):
        """When multiple trajectories are viable, ContextBuilder serializes all of them

        without arbitrarily choosing a winner (Lock 5).
        """
        # Plurality with 3 viable pathways (STPM, Foundation, Diploma)
        base_nodes = [
            TemporalNode(
                node_id="node_birth",
                label="Birth",
                interval=TemporalInterval.create_exact(start=date(2006, 5, 12)),
                temporal_horizon=TemporalHorizon.PAST,
                epistemic_grounding=EpistemicGrounding.USER_CONFIRMED,
                canonicality=Canonicality.CANONICAL,
            ),
            TemporalNode(
                node_id="node_spm",
                label="SPM",
                stage=LifeStage.SECONDARY_EDUCATION,
                interval=TemporalInterval.create_year(2023),
                temporal_horizon=TemporalHorizon.PAST,
                epistemic_grounding=EpistemicGrounding.OBSERVED,
                canonicality=Canonicality.CANONICAL,
            ),
            TemporalNode(
                node_id="node_undergrad",
                label="Undergraduate",
                stage=LifeStage.UNDERGRADUATE,
                interval=TemporalInterval.create_month(year=2025, month=10),
                temporal_horizon=TemporalHorizon.PRESENT,
                epistemic_grounding=EpistemicGrounding.USER_CONFIRMED,
                canonicality=Canonicality.CANONICAL,
            ),
        ]
        plurality = TimelineTrajectoryEngine.generate_trajectories(base_nodes=base_nodes)
        assert plurality.is_ambiguity_unresolved is True
        assert plurality.selected_canonical_trajectory is None

        # Build context at Step J
        context = RealityContextBuilder.build_context(trajectory_plurality=plurality)

        assert len(context.temporal_items) == 1
        item = context.temporal_items[0]
        assert item.provenance.truth_type == EpistemicTruthType.TEMPORAL_TRAJECTORY_PLURALITY
        assert item.is_canonical is False

        # Format prompt blocks
        blocks = RealityContextBuilder.format_all_reality_blocks(context)
        traj_block = next((b for b in blocks if "<temporal_trajectory_context>" in b), None)
        assert traj_block is not None

        # Epistemic warning present
        assert "Do NOT assert a specific pathway as a confirmed personal fact." in traj_block
        # All viable pathways serialized, none designated as winner
        assert ('name="DIPLOMA"' in traj_block or 'pathway="DIPLOMA"' in traj_block)
        assert ('name="STPM"' in traj_block or 'pathway="STPM"' in traj_block)
        assert "<selected_winner>" not in traj_block

    # -------------------------------------------------------------------------
    # 12. ContextBuilder performs no temporal reasoning (Lock 5)
    # -------------------------------------------------------------------------
    def test_lock5_context_builder_performs_no_temporal_reasoning(self):
        """RealityContextBuilder is pure serialization. It does not perform graph analysis,

        rule evaluation, or trajectory calculation (Lock 5).
        """
        # Given identical input, prompt output and SHA-256 hash are 100% bitwise deterministic
        t_result = TrajectoryPluralityResult(
            compatible_trajectories=(),
            compatible_pathways=("DIPLOMA", "STPM"),
            incompatible_trajectories=(),
            total_compatible_count=2,
            is_ambiguity_unresolved=True,
            trajectory_bound_exceeded=False,
            selected_canonical_trajectory=None,
        )

        ctx1 = RealityContextBuilder.build_context(trajectory_plurality=t_result)
        ctx2 = RealityContextBuilder.build_context(trajectory_plurality=t_result)

        assert ctx1.audit_metadata.context_hash_sha256 == ctx2.audit_metadata.context_hash_sha256

        blocks1 = RealityContextBuilder.format_all_reality_blocks(ctx1)
        blocks2 = RealityContextBuilder.format_all_reality_blocks(ctx2)
        assert blocks1 == blocks2

    # -------------------------------------------------------------------------
    # 13. Projected/derived epistemic status remains unchanged (Lock 1 & Invariant C)
    # -------------------------------------------------------------------------
    def test_projected_epistemic_status_preserved_in_context(self):
        """Future projected and derived intermediate nodes preserve their non-canonical status

        through Step C3 and Step J context projection.
        """
        base_nodes = [
            TemporalNode(
                node_id="node_birth",
                label="Birth",
                interval=TemporalInterval.create_exact(start=date(2006, 5, 12)),
                temporal_horizon=TemporalHorizon.PAST,
                epistemic_grounding=EpistemicGrounding.USER_CONFIRMED,
                canonicality=Canonicality.CANONICAL,
            ),
            TemporalNode(
                node_id="node_undergrad",
                label="Undergraduate",
                stage=LifeStage.UNDERGRADUATE,
                interval=TemporalInterval.create_month(year=2025, month=10),
                temporal_horizon=TemporalHorizon.PRESENT,
                epistemic_grounding=EpistemicGrounding.USER_CONFIRMED,
                canonicality=Canonicality.CANONICAL,
            ),
        ]
        plurality = TimelineTrajectoryEngine.generate_trajectories(
            base_nodes=base_nodes,
            known_pathway="STPM",
            project_degree_graduation=True,
        )
        assert len(plurality.compatible_trajectories) == 1
        traj = plurality.compatible_trajectories[0]

        grad_node = next(n for n in traj.nodes if n.temporal_horizon == TemporalHorizon.FUTURE)
        assert grad_node.epistemic_grounding == EpistemicGrounding.PROJECTED
        assert grad_node.canonicality == Canonicality.NON_CANONICAL

        # Check context projection
        context = RealityContextBuilder.build_context(trajectory_plurality=plurality)
        blocks = RealityContextBuilder.format_all_reality_blocks(context)
        traj_block = next((b for b in blocks if "<temporal_trajectory_context>" in b), "")

        assert 'grounding="PROJECTED"' in traj_block

    # -------------------------------------------------------------------------
    # 14. C3 does not score/rank candidates (Lock 6)
    # -------------------------------------------------------------------------
    def test_lock6_c3_does_not_score_or_rank_candidates(self):
        """Step C3 is a constraint gate, not a competition engine.

        It produces binary eligibility only and never modifies candidate scores (Lock 6).
        """
        coordinator = TimelineOrchestrationCoordinator()
        cand1 = _make_candidate("c_1", "skills.python", "Advanced", composite_plausibility=0.72)
        cand2 = _make_candidate("c_2", "skills.python", "Intermediate", composite_plausibility=0.45)

        result = coordinator.coordinate_turn(active_candidates=[cand1, cand2])

        assert result.evaluation_status == TemporalEvaluationStatus.AVAILABLE
        # Plausibility breakdown untouched
        assert cand1.plausibility.composite_plausibility_score == 0.72
        assert cand2.plausibility.composite_plausibility_score == 0.45

        # Result contains binary IDs only
        assert isinstance(result.temporally_incompatible_candidate_ids, tuple)

    # -------------------------------------------------------------------------
    # 15. Zero direct canonical mutation from C3 (Lock 9)
    # -------------------------------------------------------------------------
    def test_zero_direct_canonical_mutation_from_c3(self):
        """Step C3 does not call set_fact() and never mutates CharacterCore."""
        coordinator = TimelineOrchestrationCoordinator()
        core = _make_core_with_facts({
            "identity.birth_date": "2006-05-12",
            "education.spm_year": 2023,
            "education.undergraduate_intake": "2025-10",
        })
        original_facts_keys = set(core.facts.keys())
        original_values = {k: v.value for k, v in core.facts.items()}

        result = coordinator.coordinate_turn(core=core)

        # Core facts unchanged
        assert set(core.facts.keys()) == original_facts_keys
        for k, v in core.facts.items():
            assert v.value == original_values[k]

    # -------------------------------------------------------------------------
    # 16. Static AST boundary audit
    # -------------------------------------------------------------------------
    def test_ast_boundary_audit_pure_ephemeral_c3(self):
        """Static AST boundary audit for timeline_orchestration_coordinator.py.

        Verifies:
        - Zero DB / ORM imports (sqlite3, sqlalchemy).
        - Zero set_fact() calls.
        - Zero network/HTTP clients (requests, httpx, aiohttp, urllib).
        - Zero LLM libraries (openai, anthropic, google.generativeai).
        - Zero promotion tokens.
        - Zero RealityBeliefEngine.
        """
        module_path = (
            pathlib.Path(__file__).resolve().parent.parent
            / "app"
            / "reality"
            / "timeline_orchestration_coordinator.py"
        )
        assert module_path.is_file(), f"File {module_path} not found"

        source = module_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(module_path))

        forbidden_imports = {
            "sqlite3",
            "sqlalchemy",
            "requests",
            "httpx",
            "aiohttp",
            "urllib",
            "openai",
            "anthropic",
            "google.generativeai",
        }

        for node in ast.walk(tree):
            # Check import x
            if isinstance(node, ast.Import):
                for alias in node.names:
                    pkg = alias.name.split(".")[0]
                    assert pkg not in forbidden_imports, f"Forbidden import '{alias.name}' at line {node.lineno}"
            # Check from x import y
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    pkg = node.module.split(".")[0]
                    assert pkg not in forbidden_imports, f"Forbidden from-import '{node.module}' at line {node.lineno}"

            # Check function / method calls
            elif isinstance(node, ast.Call):
                func = node.func
                # set_fact()
                if isinstance(func, ast.Attribute) and func.attr == "set_fact":
                    pytest.fail(f"Forbidden call to set_fact() at line {node.lineno}")
                elif isinstance(func, ast.Name) and func.id == "set_fact":
                    pytest.fail(f"Forbidden call to set_fact() at line {node.lineno}")

                # PromotionAuthorizationToken.create()
                if isinstance(func, ast.Attribute) and func.attr == "create":
                    if isinstance(func.value, ast.Name) and "PromotionAuthorizationToken" in func.value.id:
                        pytest.fail(f"Forbidden PromotionAuthorizationToken.create() at line {node.lineno}")

        # Check raw text sentinels
        assert "RealityBeliefEngine" not in source, "Found forbidden RealityBeliefEngine reference"
        assert "PromotionAuthorizationToken" not in source, "Found forbidden token reference"


class TestPhase8B5RealityOrchestrationIntegration:
    """End-to-end integration tests for Step C3 within RealityOrchestrationService pipeline."""

    @pytest.mark.asyncio
    async def test_step_c3_filters_incompatible_candidates_before_competition(self):
        """Step C3 filters temporally incompatible candidates before Step E competition."""
        from unittest.mock import AsyncMock, MagicMock
        from app.reality.reality_orchestration_service import RealityOrchestrationService

        # Candidate 1 is temporally compatible (CS)
        cand1 = _make_candidate("c_valid", "education.major", "Computer Science")
        # Candidate 2 proposes SPM in 2028 when undergrad already started in 2025 (all trajectories HARD)
        cand2 = _make_candidate("c_invalid", "education.spm_year", "2028")

        mock_session = AsyncMock()
        mock_repo = MagicMock()
        mock_repo.get_all_active_candidates = AsyncMock(return_value=[cand1, cand2])
        mock_repo.save_choice_decision = AsyncMock()

        core = _make_core_with_facts({
            "identity.birth_date": "2006-05-12",
            "education.spm_year": 2023,
            "education.undergraduate_intake": "2025-10",
        })

        service = RealityOrchestrationService(
            session=mock_session,
            candidate_repo=mock_repo,
        )

        turn_result = await service.run_turn(
            user_input="Hello Aevum, tell me about your studies.",
            core=core,
            character_id="aevum",
        )

        assert turn_result.timeline_result is not None
        assert turn_result.timeline_result.evaluation_status == TemporalEvaluationStatus.AVAILABLE
        assert "c_invalid" in turn_result.timeline_result.temporally_incompatible_candidate_ids

        # Only c_valid proceeded to choice
        if turn_result.choices:
            for ch in turn_result.choices:
                assert ch.selected_candidate_id != "c_invalid"

    @pytest.mark.asyncio
    async def test_step_g_delegates_canonical_temporal_conflict_to_repair(self):
        """Step G delegates canonical temporal conflict to RealityRepairService."""
        from unittest.mock import AsyncMock, MagicMock
        from app.reality.reality_orchestration_service import RealityOrchestrationService

        mock_session = AsyncMock()
        mock_repo = MagicMock()
        mock_repo.get_all_active_candidates = AsyncMock(return_value=[])

        # Chronologically inverted core facts: Undergrad in 2020 precedes SPM in 2023
        core = _make_core_with_facts({
            "identity.birth_date": "2006-05-12",
            "education.spm_year": 2023,
            "education.undergraduate_intake": "2020-10",
        })

        service = RealityOrchestrationService(
            session=mock_session,
            candidate_repo=mock_repo,
        )

        turn_result = await service.run_turn(
            user_input="Hello",
            core=core,
            character_id="aevum",
        )

        # Step G repair was executed for the temporal conflict
        assert turn_result.repair_result is not None
        assert turn_result.repair_result.canonical_mutated is False
        assert turn_result.repair_result.compensatory_biography_created is False
        assert turn_result.repair_result.repair_level in (
            RepairLevel.LEVEL_2_TEMPORAL_REINTERPRETATION,
            RepairLevel.LEVEL_5_GRACEFUL_UNCERTAINTY,
        )

    @pytest.mark.asyncio
    async def test_step_j_serializes_trajectory_plurality_in_prompt_context(self):
        """Step J receives and serializes trajectory plurality into GovernedRealityContext."""
        from unittest.mock import AsyncMock, MagicMock
        from app.reality.reality_orchestration_service import RealityOrchestrationService

        mock_session = AsyncMock()
        mock_repo = MagicMock()
        mock_repo.get_all_active_candidates = AsyncMock(return_value=[])

        core = _make_core_with_facts({
            "identity.birth_date": "2006-05-12",
            "education.spm_year": 2023,
            "education.undergraduate_intake": "2025-10",
        })

        service = RealityOrchestrationService(
            session=mock_session,
            candidate_repo=mock_repo,
        )

        turn_result = await service.run_turn(
            user_input="What did you study after high school?",
            core=core,
            character_id="aevum",
        )

        context = turn_result.governed_reality
        assert len(context.temporal_items) == 1
        assert context.temporal_items[0].provenance.truth_type == EpistemicTruthType.TEMPORAL_TRAJECTORY_PLURALITY

        blocks = RealityContextBuilder.format_all_reality_blocks(context)
        assert any("<temporal_trajectory_context>" in b for b in blocks)

    def test_lock_a_zero_applicable_trajectories_remains_eligible(self):
        """Lock A: Zero applicable trajectories MUST NOT cause candidate exclusion.

        Invariant: Exclusion requires applicable_trajectory_count > 0 AND all(s == HARD_INCOMPATIBLE).
        When applicable_count == 0 -> candidate remains eligible, zero conflict signal, zero repair.
        """
        coordinator = TimelineOrchestrationCoordinator()
        c_zero = _make_candidate("c_zero", "hobbies.gardening", "bonsai")

        # Candidate with 0 applicable trajectories override
        result = coordinator.coordinate_turn(
            active_candidates=[c_zero],
            candidate_evaluations_override={"c_zero": ()},
        )

        assert result.evaluation_status == TemporalEvaluationStatus.AVAILABLE
        assert result.candidate_evaluations["c_zero"] == ()
        assert "c_zero" not in result.temporally_incompatible_candidate_ids
        assert result.is_candidate_eligible("c_zero") is True
        assert result.canonical_conflict_signal is None

    def test_lock_b_trajectory_bound_exceeded_remains_eligible(self):
        """Lock B: When 4 compatible trajectories exist (trajectory_bound_exceeded = True, compatible_trajectories = ()),
        C3 MUST NOT treat this as 0 trajectories or all HARD_INCOMPATIBLE. Candidate remains eligible.
        """
        coordinator = TimelineOrchestrationCoordinator()

        # Baseline where all 4 pathways (STPM, Matrikulasi, Foundation, Diploma) are compatible
        core = _make_core_with_facts({
            "identity.birth_date": "2006-05-12",
            "education.spm_year": 2023,
            "education.undergraduate_intake": "2025-10",
        })

        c_hobby = _make_candidate("c_hobby", "hobbies.reading", "mystery novels")
        c_pathway = _make_candidate("c_pathway", "education.pathway", "MATRIKULASI")

        result = coordinator.coordinate_turn(
            core=core,
            active_candidates=[c_hobby, c_pathway],
        )

        assert result.evaluation_status == TemporalEvaluationStatus.AVAILABLE
        assert result.trajectory_plurality is not None
        assert result.trajectory_plurality.trajectory_bound_exceeded is True
        assert result.trajectory_plurality.total_compatible_count == 4
        assert result.trajectory_plurality.compatible_trajectories == ()

        # Candidate c_hobby must remain eligible
        assert "c_hobby" not in result.temporally_incompatible_candidate_ids
        assert result.is_candidate_eligible("c_hobby") is True
        # Evaluations must have compatible entries, not treated as 0 or hard incompatible
        assert result.candidate_evaluations["c_hobby"] == ("COMPATIBLE", "COMPATIBLE", "COMPATIBLE", "COMPATIBLE")

        # Candidate c_pathway must remain eligible
        assert "c_pathway" not in result.temporally_incompatible_candidate_ids
        assert result.is_candidate_eligible("c_pathway") is True

        # No canonical conflict signal
        assert result.canonical_conflict_signal is None

    @pytest.mark.asyncio
    async def test_lock_c_post_repair_state_freshness_in_context(self):
        """Lock C: Post-repair state freshness in context.

        When Step G executes RealityRepairService.repair() to resolve a temporal contradiction,
        downstream context assembly reflects the repaired state, asserting that post-repair
        context projection matches repaired reality.
        """
        from unittest.mock import AsyncMock, MagicMock
        from app.reality.reality_orchestration_service import RealityOrchestrationService

        mock_session = AsyncMock()
        mock_repo = MagicMock()
        mock_repo.get_all_active_candidates = AsyncMock(return_value=[])

        # Core with temporal contradiction: Undergrad intake precedes SPM
        core = _make_core_with_facts({
            "identity.birth_date": "2006-05-12",
            "education.spm_year": 2023,
            "education.undergraduate_intake": "2020-10",
        })

        service = RealityOrchestrationService(
            session=mock_session,
            candidate_repo=mock_repo,
        )

        turn_result = await service.run_turn(
            user_input="Tell me about your school years.",
            core=core,
            character_id="aevum",
        )

        # 1. Step G repair executed and succeeded
        assert turn_result.repair_result is not None
        assert turn_result.repair_result.is_repaired is True
        assert turn_result.repair_result.repair_level == RepairLevel.LEVEL_2_TEMPORAL_REINTERPRETATION
        assert turn_result.repair_result.temporal_split is not None

        # 2. Context assembly receives and reflects repaired state
        context = turn_result.governed_reality
        assert len(context.repair_items) == 1
        repair_item = context.repair_items[0]
        assert repair_item.provenance.truth_type == EpistemicTruthType.EPHEMERAL_REPAIR_INTERPRETATION
        assert repair_item.value["repair_level"] == RepairLevel.LEVEL_2_TEMPORAL_REINTERPRETATION.value
        assert repair_item.value["temporal_split"] == turn_result.repair_result.temporal_split

        # 3. Context formatting serializes <ephemeral_repair_context> with <temporal_split>
        blocks = RealityContextBuilder.format_all_reality_blocks(context)
        repair_block = next((b for b in blocks if "<ephemeral_repair_context" in b), None)
        assert repair_block is not None
        assert 'scope="CURRENT_TURN_ONLY"' in repair_block
        assert "<temporal_split>" in repair_block
        assert "education.spm_year" in repair_block
        assert "education.undergraduate_intake" in repair_block

    def test_lock_d_timeline_evidence_adapter_strict_contract(self):
        """Lock D: TimelineEvidenceAdapter strict schema audit.

        1. Adapter strictly forbids extra fields (extra='forbid').
        2. TemporalConflictSignal requires TimelineEvidenceAdapter instance.
        3. to_repair_evidence_dict() emits exact schema expected by RealityRepairService.
        """
        # 1. Rejects unknown fields
        with pytest.raises(ValidationError):
            TimelineEvidenceAdapter(
                independent_timeline_supported=True,
                unauthorized_extra_field="malformed_data",  # type: ignore[call-arg]
            )

        # 2. Valid adapter instance
        adapter = TimelineEvidenceAdapter(
            independent_timeline_supported=True,
            temporal_split={
                "past": {"fact_key": "education.spm_year", "interval": {"earliest_start": "2023-01-01"}},
                "present": {"fact_key": "education.undergraduate_intake", "interval": {"earliest_start": "2025-10-01"}},
            },
            conflicting_node_ids=("node_spm", "node_undergrad"),
            evidence_fact_keys=("education.spm_year", "education.undergraduate_intake"),
            explanation="Test timeline explanation.",
        )

        # 3. TemporalConflictSignal rejects raw dict
        with pytest.raises(ValidationError):
            TemporalConflictSignal(
                conflict_id="signal_bad",
                conflicting_fact_keys=("education.spm_year", "education.undergraduate_intake"),
                temporal_evidence={"raw": "dict"},  # type: ignore[arg-type]
                rationale="Bad signal",
            )

        # 4. Valid signal accepts adapter
        signal = TemporalConflictSignal(
            conflict_id="signal_ok",
            conflicting_fact_keys=("education.spm_year", "education.undergraduate_intake"),
            temporal_evidence=adapter,
            rationale="Valid signal",
        )
        assert signal.temporal_evidence == adapter

        # 5. Serialization to dict matches RealityRepairService.repair schema exactly
        repair_dict = adapter.to_repair_evidence_dict()
        assert repair_dict["independent_timeline_supported"] is True
        assert "past" in repair_dict
        assert "present" in repair_dict
        assert repair_dict["conflicting_node_ids"] == ["node_spm", "node_undergrad"]
        assert repair_dict["evidence_fact_keys"] == ["education.spm_year", "education.undergraduate_intake"]
        assert repair_dict["explanation"] == "Test timeline explanation."

        # 6. Delegating to RealityRepairService with repair_dict succeeds at Level 2
        repair_res = RealityRepairService.repair(
            conflict_type="TEMPORAL_CONFLICT",
            timeline_evidence=repair_dict,
            rationale="Test delegation",
        )
        assert repair_res.repair_level == RepairLevel.LEVEL_2_TEMPORAL_REINTERPRETATION
        assert repair_res.is_repaired is True
        assert repair_res.canonical_mutated is False
        assert repair_res.compensatory_biography_created is False


