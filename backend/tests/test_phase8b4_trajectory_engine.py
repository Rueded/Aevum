"""Unit tests for Phase 8B.4 Trajectory Plurality & Timeline State Engine.

Verifies:
1. Ambiguity preservation when pathway is UNKNOWN (all 4 canonical pathways generated).
2. Cardinality bounding: MAX_COMPATIBLE_TRAJECTORIES = 3 bounds the retained set.
3. No arbitrary selection: selected_canonical_trajectory is None when multiple trajectories are viable.
4. Evidenced pathway narrows candidate set to that specific pathway and designates selected_canonical_trajectory.
5. Diploma -> Undergraduate trajectory is COMPATIBLE without requiring Pre-U.
6. LOCK-8B3-01: Hard rule violation marks HARD_INCOMPATIBLE and isolates into incompatible_trajectories.
7. LOCK-8B3-01: Advisory rule violation marks ADVISORY_ANOMALY but keeps trajectory in compatible_trajectories.
8. MAX_PROJECTED_NODES bound (<= 4) strictly enforced per trajectory.
9. Invariant C: Projected nodes carry FUTURE, PROJECTED, and NON_CANONICAL.
10. Invariant B: Reconstructed past nodes carry PAST, DERIVED, and NON_CANONICAL.
11. LOCK-8B3-03: Precision ceiling (year-only evidence does not fabricate exact dates).
12. Deterministic trajectory generation (identical ordering, IDs, and findings).
13. No pseudo-probability (zero float confidence or likelihood fields).
14. Invariant D: Zero mutations to CharacterCore facts.
15. Static AST boundary audit: Zero DB, zero network, zero LLM, zero set_fact, zero tokens, zero RBE.
"""

from __future__ import annotations

import ast
from datetime import date
import pathlib
import pytest
from pydantic import ValidationError

from app.character.core_models import CharacterCore
from app.reality.temporal_models import (
    MAX_COMPATIBLE_TRAJECTORIES,
    MAX_PROJECTED_NODES,
    Canonicality,
    EpistemicGrounding,
    LifeStage,
    TemporalGranularity,
    TemporalHorizon,
    TemporalInterval,
)
from app.reality.trajectory_engine import (
    CANONICAL_HIGHER_ED_PATHWAYS,
    LifeTrajectory,
    TimelineTrajectoryEngine,
    TrajectoryPluralityResult,
    TrajectoryStatus,
)
from app.reality.temporal_graph import (
    ConstraintStatus,
    TemporalConstraintEvaluator,
    TemporalConstraintGraph,
    TemporalNode,
)
from app.reality.temporal_rules import (
    TemporalRuleRegistry,
)


class TestPhase8B4TrajectoryEngine:
    """Comprehensive test suite for Phase 8B.4 Trajectory Plurality & Timeline State Engine."""

    # -------------------------------------------------------------------------
    # 1. Ambiguity Preservation When Pathway is UNKNOWN
    # -------------------------------------------------------------------------
    def test_unknown_pathway_preserves_plurality_across_all_canonical_pathways(self):
        """When educational pathway is unrecorded, engine synthesizes candidate

        trajectories across all canonical pathways without arbitrarily picking one.
        """
        # Baseline evidence: SPM in 2023, University Undergraduate started Oct 2025
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
                label="SPM Examination",
                interval=TemporalInterval.create_year(2023),
                stage=LifeStage.SECONDARY_EDUCATION,
                temporal_horizon=TemporalHorizon.PAST,
                epistemic_grounding=EpistemicGrounding.OBSERVED,
                canonicality=Canonicality.CANONICAL,
            ),
            TemporalNode(
                node_id="node_undergrad",
                label="Undergraduate Studies",
                stage=LifeStage.UNDERGRADUATE,
                interval=TemporalInterval.create_month(year=2025, month=10),
                temporal_horizon=TemporalHorizon.PRESENT,
                epistemic_grounding=EpistemicGrounding.USER_CONFIRMED,
                canonicality=Canonicality.CANONICAL,
            ),
        ]

        result = TimelineTrajectoryEngine.generate_trajectories(
            base_nodes=base_nodes,
            known_pathway=None,  # UNKNOWN!
        )

        # 4 candidate pathways discovered (STPM, Matrikulasi, Foundation, Diploma)
        assert result.total_compatible_count == 4

        # Ambiguity must be flagged as UNRESOLVED
        assert result.is_ambiguity_unresolved is True

        # CRITICAL LOCK: Never arbitrarily select a winner when ambiguous!
        assert result.selected_canonical_trajectory is None

        # LOCK 1: Cardinality overflow (>3) must NOT arbitrarily truncate to 3 branches!
        # Discarding a 4th valid candidate is prohibited arbitrary selection.
        # Instead, enters bounded ambiguity representation:
        assert result.trajectory_bound_exceeded is True
        assert len(result.compatible_trajectories) == 0  # Non-enumerated to prevent disguising 4 as 3!

        # All 4 compatible pathways are explicitly preserved in compatible_pathways:
        assert len(result.compatible_pathways) == 4
        assert set(result.compatible_pathways) == {"STPM", "MATRIKULASI", "FOUNDATION", "DIPLOMA"}

    # -------------------------------------------------------------------------
    # 2. Evidenced Pathway Narrows Candidates to Designated Path
    # -------------------------------------------------------------------------
    def test_evidenced_pathway_narrows_candidates_to_single_trajectory(self):
        """When pathway is explicitly evidenced (e.g. Diploma), engine narrows candidates

        and uniquely designates the selected canonical trajectory.
        """
        base_nodes = [
            TemporalNode(
                node_id="node_undergrad",
                label="Undergraduate Studies",
                stage=LifeStage.UNDERGRADUATE,
                interval=TemporalInterval.create_month(year=2025, month=10),
                temporal_horizon=TemporalHorizon.PRESENT,
                epistemic_grounding=EpistemicGrounding.USER_CONFIRMED,
                canonicality=Canonicality.CANONICAL,
            ),
        ]

        result = TimelineTrajectoryEngine.generate_trajectories(
            base_nodes=base_nodes,
            known_pathway="DIPLOMA",  # Evidenced!
        )

        assert result.total_compatible_count == 1
        assert result.is_ambiguity_unresolved is False
        assert len(result.compatible_trajectories) == 1
        assert result.compatible_trajectories[0].pathway == "DIPLOMA"

        # Dedicated canonical trajectory designated
        assert result.selected_canonical_trajectory is not None
        assert result.selected_canonical_trajectory.pathway == "DIPLOMA"
        assert result.selected_canonical_trajectory.status == TrajectoryStatus.COMPATIBLE

    # -------------------------------------------------------------------------
    # 3. Diploma -> Undergraduate Trajectory is COMPATIBLE without Pre-U
    # -------------------------------------------------------------------------
    def test_diploma_trajectory_is_compatible_without_pre_u(self):
        """Diploma pathway candidate does NOT violate Pre-U precedence rules."""
        base_nodes = [
            TemporalNode(
                node_id="node_undergrad",
                label="Undergraduate Studies",
                stage=LifeStage.UNDERGRADUATE,
                interval=TemporalInterval.create_month(year=2025, month=10),
                temporal_horizon=TemporalHorizon.PRESENT,
                epistemic_grounding=EpistemicGrounding.USER_CONFIRMED,
                canonicality=Canonicality.CANONICAL,
            ),
        ]

        result = TimelineTrajectoryEngine.generate_trajectories(
            base_nodes=base_nodes,
            known_pathway="DIPLOMA",
        )

        traj = result.compatible_trajectories[0]
        assert traj.status == TrajectoryStatus.COMPATIBLE

        # Intermediate stage is DIPLOMA, not PRE_UNIVERSITY
        stages = [n.stage for n in traj.nodes]
        assert LifeStage.DIPLOMA in stages
        assert LifeStage.PRE_UNIVERSITY not in stages

    # -------------------------------------------------------------------------
    # 4. LOCK-8B3-01: Hard Rule Violation Marks HARD_INCOMPATIBLE
    # -------------------------------------------------------------------------
    def test_hard_rule_violation_isolates_incompatible_trajectory(self):
        """Violating an applicable hard rule (e.g. inverted sequence) marks HARD_INCOMPATIBLE."""
        # Intentionally create inverted nodes: degree in 2020, secondary in 2025
        inverted_nodes = (
            TemporalNode(
                node_id="ug_first",
                stage=LifeStage.UNDERGRADUATE,
                interval=TemporalInterval.create_year(2020),
            ),
            TemporalNode(
                node_id="sec_later",
                stage=LifeStage.SECONDARY_EDUCATION,
                interval=TemporalInterval.create_year(2025),
            ),
        )

        traj = LifeTrajectory(
            trajectory_id="traj_invalid_sequence",
            pathway="STPM",
            nodes=inverted_nodes,
        )

        evaluated = TimelineTrajectoryEngine._evaluate_trajectory(traj)
        assert evaluated.status == TrajectoryStatus.HARD_INCOMPATIBLE

        has_hard_rejection = any(
            f.status == ConstraintStatus.VIOLATED and f.is_hard_rejection
            for f in evaluated.evaluation_findings
        )
        assert has_hard_rejection is True

    # -------------------------------------------------------------------------
    # 5. LOCK-8B3-01: Advisory Rule Violation Marks ADVISORY_ANOMALY (Not Deletion)
    # -------------------------------------------------------------------------
    def test_advisory_rule_violation_marks_advisory_anomaly_not_deletion(self):
        """Advisory rule violation (e.g. USM intake month mismatch) marks

        ADVISORY_ANOMALY but does NOT delete or eliminate the trajectory.
        """
        # USM with March intake (typical is October) -> Advisory violation
        base_nodes = [
            TemporalNode(
                node_id="node_usm_march",
                label="USM Undergraduate Studies",
                stage=LifeStage.UNDERGRADUATE,
                institution_ref="world.usm.main_campus",
                interval=TemporalInterval.create_month(year=2025, month=3),  # March intake!
                temporal_horizon=TemporalHorizon.PRESENT,
                epistemic_grounding=EpistemicGrounding.USER_CONFIRMED,
                canonicality=Canonicality.CANONICAL,
            ),
        ]

        result = TimelineTrajectoryEngine.generate_trajectories(
            base_nodes=base_nodes,
            known_pathway="STPM",
            target_institution_ref="world.usm.main_campus",
        )

        assert len(result.compatible_trajectories) == 1
        traj = result.compatible_trajectories[0]

        # Critical assertion: Status is ADVISORY_ANOMALY, NOT HARD_INCOMPATIBLE!
        assert traj.status == TrajectoryStatus.ADVISORY_ANOMALY
        # Must still be retained in compatible_trajectories, NOT discarded
        assert len(result.incompatible_trajectories) == 0

    # -------------------------------------------------------------------------
    # 6. Cardinality Bound: MAX_PROJECTED_NODES per Trajectory
    # -------------------------------------------------------------------------
    def test_max_projected_nodes_bound_enforced(self):
        """A trajectory with more than MAX_PROJECTED_NODES (4) raises ValueError."""
        projected_nodes = [
            TemporalNode(
                node_id=f"proj_{i}",
                temporal_horizon=TemporalHorizon.FUTURE,
                epistemic_grounding=EpistemicGrounding.PROJECTED,
                canonicality=Canonicality.NON_CANONICAL,
            )
            for i in range(5)  # 5 projected nodes -> exceeds bound of 4!
        ]

        with pytest.raises(ValueError, match="exceeds MAX_PROJECTED_NODES"):
            LifeTrajectory(
                trajectory_id="traj_overflow",
                nodes=tuple(projected_nodes),
            )

    # -------------------------------------------------------------------------
    # 7. Invariant C: Projected Nodes Carry Epistemic Invariants
    # -------------------------------------------------------------------------
    def test_projected_nodes_epistemic_invariants(self):
        """Future projected nodes must strictly carry FUTURE, PROJECTED, and NON_CANONICAL."""
        base_nodes = [
            TemporalNode(
                node_id="node_undergrad",
                stage=LifeStage.UNDERGRADUATE,
                interval=TemporalInterval.create_month(year=2025, month=10),
            ),
        ]

        result = TimelineTrajectoryEngine.generate_trajectories(
            base_nodes=base_nodes,
            known_pathway="STPM",
            project_degree_graduation=True,
        )

        traj = result.compatible_trajectories[0]
        grad_node = next(n for n in traj.nodes if "projected_grad" in n.node_id)

        assert grad_node.temporal_horizon == TemporalHorizon.FUTURE
        assert grad_node.epistemic_grounding == EpistemicGrounding.PROJECTED
        assert grad_node.canonicality == Canonicality.NON_CANONICAL

    # -------------------------------------------------------------------------
    # 8. Invariant B: Reconstructed Past Nodes Epistemic Invariants
    # -------------------------------------------------------------------------
    def test_reconstructed_past_nodes_epistemic_invariants(self):
        """Reconstructed past intermediate nodes carry PAST, DERIVED, and NON_CANONICAL."""
        base_nodes = [
            TemporalNode(
                node_id="node_undergrad",
                stage=LifeStage.UNDERGRADUATE,
                interval=TemporalInterval.create_month(year=2025, month=10),
            ),
        ]

        result = TimelineTrajectoryEngine.generate_trajectories(
            base_nodes=base_nodes,
            known_pathway="STPM",
        )

        traj = result.compatible_trajectories[0]
        stpm_node = next(n for n in traj.nodes if n.stage == LifeStage.PRE_UNIVERSITY)

        assert stpm_node.temporal_horizon == TemporalHorizon.PAST
        assert stpm_node.epistemic_grounding == EpistemicGrounding.DERIVED
        assert stpm_node.canonicality == Canonicality.NON_CANONICAL

    # -------------------------------------------------------------------------
    # 9. LOCK-8B3-03: Precision Ceiling (No Synthetic Dates)
    # -------------------------------------------------------------------------
    def test_precision_ceiling_no_synthetic_exact_dates_fabricated(self):
        """When input evidence is year-only, projected graduation must NOT fabricate exact day/month."""
        base_nodes = [
            TemporalNode(
                node_id="node_ug_year",
                stage=LifeStage.UNDERGRADUATE,
                interval=TemporalInterval.create_year(2025),
            ),
        ]

        result = TimelineTrajectoryEngine.generate_trajectories(
            base_nodes=base_nodes,
            known_pathway="STPM",
            project_degree_graduation=True,
        )

        traj = result.compatible_trajectories[0]
        grad_node = next(n for n in traj.nodes if "grad" in n.node_id)

        # Must not fabricate EXACT_DATE
        assert grad_node.interval.granularity != TemporalGranularity.EXACT_DATE
        assert grad_node.interval.granularity in (
            TemporalGranularity.YEAR,
            TemporalGranularity.APPROXIMATE_YEAR,
            TemporalGranularity.UNKNOWN,
        )

    # -------------------------------------------------------------------------
    # 10. Deterministic Trajectory Output
    # -------------------------------------------------------------------------
    def test_deterministic_trajectory_output(self):
        """Multiple runs on identical inputs yield identical trajectory ordering and IDs."""
        base_nodes = [
            TemporalNode(
                node_id="node_undergrad",
                stage=LifeStage.UNDERGRADUATE,
                interval=TemporalInterval.create_month(year=2025, month=10),
            ),
        ]

        # 1. Ambiguous (plurality across 4 pathways) deterministic consistency
        res1 = TimelineTrajectoryEngine.generate_trajectories(base_nodes=base_nodes)
        res2 = TimelineTrajectoryEngine.generate_trajectories(base_nodes=base_nodes)

        assert res1.compatible_pathways == res2.compatible_pathways
        assert res1.total_compatible_count == res2.total_compatible_count
        assert res1.is_ambiguity_unresolved == res2.is_ambiguity_unresolved
        assert res1.trajectory_bound_exceeded == res2.trajectory_bound_exceeded
        assert res1.selected_canonical_trajectory == res2.selected_canonical_trajectory

        # 2. Enumerated single-pathway deterministic consistency
        res_ev1 = TimelineTrajectoryEngine.generate_trajectories(base_nodes=base_nodes, known_pathway="DIPLOMA")
        res_ev2 = TimelineTrajectoryEngine.generate_trajectories(base_nodes=base_nodes, known_pathway="DIPLOMA")

        assert [t.trajectory_id for t in res_ev1.compatible_trajectories] == [
            t.trajectory_id for t in res_ev2.compatible_trajectories
        ]
        assert [f.rule_id for f in res_ev1.compatible_trajectories[0].evaluation_findings] == [
            f.rule_id for f in res_ev2.compatible_trajectories[0].evaluation_findings
        ]

    # -------------------------------------------------------------------------
    # 11. No Pseudo-Probability Attributes
    # -------------------------------------------------------------------------
    def test_no_pseudo_probability_attributes(self):
        """LifeTrajectory and TrajectoryPluralityResult contain zero probability or confidence floats."""
        traj = LifeTrajectory(trajectory_id="t1", nodes=())
        assert not hasattr(traj, "confidence")
        assert not hasattr(traj, "probability")
        assert not hasattr(traj, "score")
        assert not hasattr(traj, "likelihood")

        res = TrajectoryPluralityResult(
            compatible_trajectories=(),
            total_compatible_count=0,
        )
        assert not hasattr(res, "confidence")
        assert not hasattr(res, "score")

    # -------------------------------------------------------------------------
    # 12. Invariant D: Zero Core Mutations
    # -------------------------------------------------------------------------
    def test_zero_core_mutations(self):
        """Generating trajectories produces zero mutations to CharacterCore."""
        core = CharacterCore(character_id="aevum")
        initial_facts = dict(core.facts)

        base_nodes = [
            TemporalNode(
                node_id="node_undergrad",
                stage=LifeStage.UNDERGRADUATE,
                interval=TemporalInterval.create_month(year=2025, month=10),
            ),
        ]

        _ = TimelineTrajectoryEngine.generate_trajectories(base_nodes=base_nodes)

        assert core.facts == initial_facts
        assert len(core.facts) == len(initial_facts)

    # -------------------------------------------------------------------------
    # 13. LOCK 2 — Case A: User-Confirmed Pathway Selects Canonical Trajectory
    # -------------------------------------------------------------------------
    def test_lock2_case_a_user_confirmed_pathway_selects_canonical_trajectory(self):
        """When exactly one trajectory is supported by authoritative user evidence,

        it is designated as the selected canonical trajectory.
        """
        base_nodes = [
            TemporalNode(
                node_id="node_undergrad",
                label="Undergraduate Studies",
                stage=LifeStage.UNDERGRADUATE,
                pathway="DIPLOMA",
                interval=TemporalInterval.create_month(year=2025, month=10),
                temporal_horizon=TemporalHorizon.PRESENT,
                epistemic_grounding=EpistemicGrounding.USER_CONFIRMED,
                canonicality=Canonicality.CANONICAL,
            ),
        ]

        result = TimelineTrajectoryEngine.generate_trajectories(
            base_nodes=base_nodes,
            known_pathway="DIPLOMA",
            pathway_grounding=EpistemicGrounding.USER_CONFIRMED,
        )

        assert result.total_compatible_count == 1
        assert result.is_ambiguity_unresolved is False
        assert result.selected_canonical_trajectory is not None
        assert result.selected_canonical_trajectory.pathway == "DIPLOMA"
        assert result.selected_canonical_trajectory.status == TrajectoryStatus.COMPATIBLE

    # -------------------------------------------------------------------------
    # 14. LOCK 2 — Case B: Derived Compatibility Alone Cannot Select Canonical
    # -------------------------------------------------------------------------
    def test_lock2_case_b_derived_temporal_compatibility_cannot_select_canonical(self):
        """Derived/temporal compatibility alone without authoritative evidence MUST NOT

        designate a selected canonical trajectory (Plausible != Canonical).
        """
        # Base node has DERIVED grounding (e.g. system hypothesized or inferred)
        base_nodes = [
            TemporalNode(
                node_id="node_undergrad",
                label="Undergraduate Studies",
                stage=LifeStage.UNDERGRADUATE,
                pathway="DIPLOMA",
                interval=TemporalInterval.create_month(year=2025, month=10),
                temporal_horizon=TemporalHorizon.PRESENT,
                epistemic_grounding=EpistemicGrounding.DERIVED,
                canonicality=Canonicality.NON_CANONICAL,
            ),
        ]

        result = TimelineTrajectoryEngine.generate_trajectories(
            base_nodes=base_nodes,
            known_pathway="DIPLOMA",
            pathway_grounding=EpistemicGrounding.DERIVED,  # NOT user-confirmed!
        )

        assert result.total_compatible_count == 1
        # CRITICAL LOCK 2: selected_canonical_trajectory MUST be None!
        assert result.selected_canonical_trajectory is None

    # -------------------------------------------------------------------------
    # 15. LOCK 2 — Case C: Multiple Compatible Pathways Never Select Canonical
    # -------------------------------------------------------------------------
    def test_lock2_case_c_multiple_compatible_pathways_never_selects_canonical(self):
        """When multiple pathways are viable, selected_canonical_trajectory MUST be None."""
        base_nodes = [
            TemporalNode(
                node_id="node_undergrad",
                stage=LifeStage.UNDERGRADUATE,
                interval=TemporalInterval.create_month(year=2025, month=10),
            ),
        ]

        result = TimelineTrajectoryEngine.generate_trajectories(
            base_nodes=base_nodes,
            known_pathway=None,
        )

        assert result.is_ambiguity_unresolved is True
        assert result.selected_canonical_trajectory is None

    # -------------------------------------------------------------------------
    # 16. LOCK 3 — Developmental Rank Does Not Fabricate Missing Stages
    # -------------------------------------------------------------------------
    def test_lock3_developmental_rank_does_not_fabricate_missing_stages(self):
        """Missing prior educational history yields UNDETERMINED without fabricating nodes."""
        rule_pre_u = TemporalRuleRegistry.get("RULE_PRECEDENCE_PRE_U_TO_UNDERGRAD")
        assert rule_pre_u is not None

        # Graph contains ONLY undergraduate node; prior secondary/pre-u is absent
        graph = TemporalConstraintGraph()
        ug_node = TemporalNode(
            node_id="ug_sole_node",
            stage=LifeStage.UNDERGRADUATE,
            pathway="STPM",
            interval=TemporalInterval.create_month(year=2025, month=10),
        )
        graph.add_node(ug_node)

        # Precedence evaluation must be UNDETERMINED, NOT VIOLATED
        finding = TemporalConstraintEvaluator.evaluate_stage_precedence(graph, ug_node, rule_pre_u)
        assert finding.status == ConstraintStatus.UNDETERMINED
        assert "Prior educational history is UNKNOWN in graph" in finding.explanation

        # Graph MUST NOT have fabricated missing nodes
        assert graph.node_count == 1
        assert graph.edge_count == 0

    # -------------------------------------------------------------------------
    # 17. LOCK 4 — Trajectory Compatibility Never Escalates Epistemic Status
    # -------------------------------------------------------------------------
    def test_lock4_compatibility_never_escalates_projection_epistemic_status(self):
        """Trajectory compatibility NEVER upgrades PROJECTED/DERIVED to CANONICAL or USER_CONFIRMED."""
        base_nodes = [
            TemporalNode(
                node_id="node_undergrad",
                label="Undergraduate Studies",
                stage=LifeStage.UNDERGRADUATE,
                pathway="DIPLOMA",
                interval=TemporalInterval.create_month(year=2025, month=10),
                temporal_horizon=TemporalHorizon.PRESENT,
                epistemic_grounding=EpistemicGrounding.USER_CONFIRMED,
                canonicality=Canonicality.CANONICAL,
            ),
        ]

        result = TimelineTrajectoryEngine.generate_trajectories(
            base_nodes=base_nodes,
            known_pathway="DIPLOMA",
            pathway_grounding=EpistemicGrounding.USER_CONFIRMED,
            project_degree_graduation=True,
        )

        # Selected canonical trajectory designated
        canon_traj = result.selected_canonical_trajectory
        assert canon_traj is not None

        # 1. Projected graduation node MUST remain FUTURE, PROJECTED, and NON_CANONICAL
        grad_node = next(n for n in canon_traj.nodes if "projected_grad" in n.node_id)
        assert grad_node.temporal_horizon == TemporalHorizon.FUTURE
        assert grad_node.epistemic_grounding == EpistemicGrounding.PROJECTED
        assert grad_node.canonicality == Canonicality.NON_CANONICAL

        # 2. Reconstructed past diploma stage MUST remain PAST, DERIVED, and NON_CANONICAL
        diploma_node = next(n for n in canon_traj.nodes if n.stage == LifeStage.DIPLOMA)
        assert diploma_node.temporal_horizon == TemporalHorizon.PAST
        assert diploma_node.epistemic_grounding == EpistemicGrounding.DERIVED
        assert diploma_node.canonicality == Canonicality.NON_CANONICAL

    # -------------------------------------------------------------------------
    # 13. Static AST Boundary Audit
    # -------------------------------------------------------------------------
    def test_ast_audit_trajectory_engine(self):
        """Verify trajectory_engine.py contains 0 network imports, 0 DB calls, 0 RBE, 0 set_fact, 0 tokens."""
        target_path = pathlib.Path(__file__).parent.parent / "app" / "reality" / "trajectory_engine.py"
        assert target_path.exists(), "trajectory_engine.py must exist"

        content = target_path.read_text(encoding="utf-8")

        # 1. No RealityBeliefEngine
        assert "RealityBeliefEngine" not in content

        # 2. No set_fact
        assert "set_fact" not in content

        # 3. No token minting
        assert "PromotionAuthorizationToken" not in content

        # 4. No forbidden modules
        forbidden_modules = {"requests", "httpx", "aiohttp", "urllib", "urllib3", "sqlalchemy", "sqlmodel"}
        tree = ast.parse(content, filename=str(target_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod_root = alias.name.split(".")[0]
                    assert mod_root not in forbidden_modules, f"Forbidden import: {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    mod_root = node.module.split(".")[0]
                    assert mod_root not in forbidden_modules, f"Forbidden import from: {node.module}"
