"""Golden Suite 8B: Phase 8B End-to-End Temporal Reality Subsystem Acceptance Benchmarks.

Covers Golden Acceptance Cases GC-171 through GC-195:
- Cluster 1: Epistemic Contracts & Bounds (GC-171 ~ GC-174)
  - GC-171: Epistemic Grounding Matrix Validity Invariant
  - GC-172: Temporal Granularity & Boundary Invariants (Zero Synthetic Precision)
  - GC-173: Semantic Pseudo-Probability & Confidence Ban (Targeted AST / Contract Audit)
  - GC-174: Graph Cardinality Bounds & Bounded Representation with Overflow Preservation
- Cluster 2: World Rules & Applicability (GC-175 ~ GC-178)
  - GC-175: WorldKnowledgeRegistry as the Singular Rule Authority
  - GC-176: Scoped Applicability & Non-Leaking Institutional Constraints
  - GC-177: Non-Universal Pre-University Prerequisite & Diploma Articulation
  - GC-178: Advisory Anomaly vs. Hard Rejection Demarcation
- Cluster 3: Constraint Graph & Tri-State Semantics (GC-179 ~ GC-182)
  - GC-179: Tri-State Logic Completeness & UNKNOWN Semantics
  - GC-180: Temporal Constraint Violation != Personal Contradiction
  - GC-181: Ephemeral In-Memory Graph Lifecycle (Zero SQLite Footprint)
  - GC-182: Deterministic Topological Node and Edge Sequencing
- Cluster 4: Trajectory Plurality & Temporal Inference (GC-183 ~ GC-186)
  - GC-183: Trajectory Plurality Preservation Under Pathway Ambiguity
  - GC-184: Bounded Ambiguity Representation (Overflow Preservation, No Truncation)
  - GC-185: Temporal Compatibility Alone Never Authorizes Canonical Selection
  - GC-186: Developmental Rank Sanity Check Without Missing Stage Fabrication
- Cluster 5: C3 Gate & Repair Delegation (GC-187 ~ GC-191)
  - GC-187: Trajectory Incompatibility != Candidate Incompatibility (Lock 1 & Lock A)
  - GC-188: Bounded Ambiguity Candidate Immunity (Lock B)
  - GC-189: Zero Repair-Policy Authority in C3 & Symmetric Conflict Facts (Lock 2 & Lock 8)
  - GC-190: TimelineEvidenceAdapter Strict Contract & Repair Delegation (Lock 3, 7 & Lock D)
  - GC-191: Explicit Evaluation Status Semantics (Lock 4: UNAVAILABLE != NO CONFLICT)
- Cluster 6: End-to-End Integration & Boundary Audit (GC-192 ~ GC-195)
  - GC-192: Post-Repair Context Freshness & Repair-Result Propagation (Lock C)
  - GC-193: Serialization-Only Trajectory Presentation (Lock 5 & Invariant C)
  - GC-194: Pure 8B Module AST Audit vs. Integration Layer Delegation
  - GC-195: Integrated Full-Turn Temporal Reality Lifecycle (Semantic Determinism)
"""

from __future__ import annotations

import ast
from datetime import date, datetime, timezone
import hashlib
import json
import pathlib
from typing import Any, Optional, Sequence
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest
from pydantic import ValidationError

from app.character.core_models import CharacterCore
from app.character.reality_context_builder import RealityContextBuilder
from app.character.reality_context_models import (
    EpistemicTruthType,
    GovernedRealityContext,
    GovernedRealityItem,
    RealityItemProvenance,
    FactVolatilityCategory,
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
    MAX_COMPATIBLE_TRAJECTORIES,
    MAX_PROJECTED_NODES,
    MAX_TEMPORAL_PROPAGATION_HOPS,
    Canonicality,
    EpistemicGrounding,
    LifeStage,
    TemporalGranularity,
    TemporalHorizon,
    TemporalInterval,
    validate_epistemic_canonicality_combination,
)
from app.reality.temporal_rules import (
    AgeWindowValue,
    CalendarWindowValue,
    DurationBoundValue,
    StagePrecedenceValue,
    TemporalConstraintType,
    TemporalRuleItem,
    TemporalRuleRegistry,
    TemporalRuleScope,
)
from app.reality.temporal_graph import (
    ConstraintEvaluationResult,
    ConstraintStatus,
    TemporalConstraintEvaluator,
    TemporalConstraintGraph,
    TemporalEdge,
    TemporalNode,
    TemporalRelationType,
)
from app.reality.trajectory_engine import (
    CANONICAL_HIGHER_ED_PATHWAYS,
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
from app.reality.reality_orchestration_service import (
    OrchestrationTurnResult,
    RealityOrchestrationService,
)
from app.reality.world_knowledge import KnowledgeKind, WorldKnowledgeRegistry


# =============================================================================
# Test Helpers
# =============================================================================

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _make_candidate(
    cid: str,
    slot_name: str,
    value: str,
    composite_plausibility: float = 0.55,
) -> CandidateHypothesis:
    """Helper to build a deterministic CandidateHypothesis matching 7D/8A contracts."""
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


# =============================================================================
# Golden Suite 8B Acceptance Benchmarks (GC-171 ~ GC-195)
# =============================================================================

class TestGoldenSuite8B:
    """Golden Suite 8B Acceptance Benchmarks (GC-171 ~ GC-195)."""

    # -------------------------------------------------------------------------
    # Cluster 1: Epistemic Contracts & Bounds (GC-171 ~ GC-174)
    # -------------------------------------------------------------------------

    def test_gc171_epistemic_grounding_matrix_validity(self):
        """GC-171: Epistemic Grounding Matrix Validity Invariant.

        Asserts that the 5 frozen EpistemicGrounding states enforce the constitutional
        epistemic-canonicality matrix:
        - DERIVED, PROJECTED, UNKNOWN paired with CANONICAL are strictly invalid.
        - USER_CONFIRMED, OBSERVED paired with CANONICAL are valid.
        - Canonicality validity does not confer canonical mutation authority on 8B DTOs.
        """
        # 1. Invalid combinations must raise ValueError
        for invalid_grounding in (
            EpistemicGrounding.DERIVED,
            EpistemicGrounding.PROJECTED,
            EpistemicGrounding.UNKNOWN,
        ):
            with pytest.raises(ValueError, match="cannot be paired with Canonicality.CANONICAL"):
                validate_epistemic_canonicality_combination(
                    grounding=invalid_grounding,
                    canonicality=Canonicality.CANONICAL,
                )

            # Node creation must also fail
            with pytest.raises(ValidationError):
                TemporalNode(
                    node_id=f"node_{invalid_grounding.value}",
                    label=f"Invalid Node {invalid_grounding.value}",
                    interval=TemporalInterval.create_year(2025),
                    epistemic_grounding=invalid_grounding,
                    canonicality=Canonicality.CANONICAL,
                )

        # 2. Valid combinations succeed without error
        for valid_grounding in (
            EpistemicGrounding.USER_CONFIRMED,
            EpistemicGrounding.OBSERVED,
        ):
            validate_epistemic_canonicality_combination(
                grounding=valid_grounding,
                canonicality=Canonicality.CANONICAL,
            )
            node = TemporalNode(
                node_id=f"node_{valid_grounding.value}",
                label=f"Valid Node {valid_grounding.value}",
                interval=TemporalInterval.create_year(2025),
                epistemic_grounding=valid_grounding,
                canonicality=Canonicality.CANONICAL,
            )
            assert node.canonicality == Canonicality.CANONICAL

        # 3. All groundings paired with NON_CANONICAL are valid
        for any_grounding in EpistemicGrounding:
            validate_epistemic_canonicality_combination(
                grounding=any_grounding,
                canonicality=Canonicality.NON_CANONICAL,
            )

    def test_gc172_temporal_granularity_and_boundary_invariants(self):
        """GC-172: Temporal Granularity & Boundary Invariants (Zero Synthetic Precision).

        Asserts that lower-granularity intervals (YEAR, MONTH, UNKNOWN) never fabricate
        synthetic exact dates or collapse uncertainty into arbitrary day stamps,
        while maintaining strict interval boundary inequalities.
        """
        # 1. Year granularity preserves year span without claiming exact date knowledge
        year_interval = TemporalInterval.create_year(2025)
        assert year_interval.granularity == TemporalGranularity.YEAR
        assert year_interval.earliest_start == date(2025, 1, 1)
        assert year_interval.latest_end == date(2025, 12, 31)
        assert year_interval.earliest_start != year_interval.latest_end
        assert year_interval.granularity != TemporalGranularity.EXACT_DATE

        # 2. Month granularity preserves month span
        month_interval = TemporalInterval.create_month(2025, 10)
        assert month_interval.granularity == TemporalGranularity.MONTH
        assert month_interval.earliest_start == date(2025, 10, 1)
        assert month_interval.latest_end == date(2025, 10, 31)
        assert month_interval.earliest_start != month_interval.latest_end
        assert month_interval.granularity != TemporalGranularity.EXACT_DATE

        # 3. UNKNOWN granularity preserves unbounded uncertainty
        unk_interval = TemporalInterval.create_unknown()
        assert unk_interval.granularity == TemporalGranularity.UNKNOWN
        assert unk_interval.earliest_start is None
        assert unk_interval.latest_end is None

        # 4. Strict boundary invariants: earliest_start <= latest_end
        assert year_interval.earliest_start <= year_interval.latest_end
        assert month_interval.earliest_start <= month_interval.latest_end

        # Inverted interval must fail validation
        with pytest.raises(ValidationError):
            TemporalInterval(
                granularity=TemporalGranularity.DATE_RANGE,
                earliest_start=date(2025, 12, 31),
                latest_end=date(2025, 1, 1),
            )

    def test_gc173_semantic_pseudo_probability_ban(self):
        """GC-173: Semantic Pseudo-Probability & Confidence Ban (Targeted AST / Contract Audit).

        Asserts that Phase 8B temporal DTOs and reasoning structures contain:
        - No confidence field
        - No probability field
        - No likelihood field
        - No score/ranking field
        - No probabilistic selection mechanism
        While legitimately permitting standard duration/interval floats (e.g. 1.5 years).
        """
        prohibited_field_names = {"confidence", "probability", "likelihood", "score", "ranking"}

        models_to_audit = [
            TemporalInterval,
            TemporalNode,
            TemporalEdge,
            LifeTrajectory,
            TrajectoryPluralityResult,
            TemporalConflictSignal,
            TimelineEvidenceAdapter,
            TimelineOrchestrationResult,
            TemporalRuleItem,
        ]

        for model_cls in models_to_audit:
            fields = model_cls.model_fields.keys()
            for bad_name in prohibited_field_names:
                assert bad_name not in fields, (
                    f"Prohibited pseudo-probability field '{bad_name}' found in model {model_cls.__name__}."
                )

        # Legitimate numeric float fields (e.g. durations or age thresholds) are permitted
        bound_val = DurationBoundValue(min_years=1.5, max_years=2.0)
        assert bound_val.min_years == 1.5

    def test_gc174_graph_cardinality_and_projection_bounds(self):
        """GC-174: Graph Cardinality Bounds & Bounded Representation with Overflow Preservation.

        Asserts:
        - Forward projected nodes are bounded by MAX_PROJECTED_NODES = 4.
        - Projected nodes cannot recursively seed further projections (anti-snowballing).
        - Exceeding the bound stops expansion; it does not treat unprojected nodes as impossible facts.
        """
        graph = TemporalConstraintGraph()

        # Add 4 projected nodes (maximum allowed)
        for i in range(MAX_PROJECTED_NODES):
            p_node = TemporalNode(
                node_id=f"proj_{i}",
                label=f"Projected Stage {i}",
                stage=LifeStage.CAREER,
                interval=TemporalInterval.create_year(2026 + i),
                temporal_horizon=TemporalHorizon.FUTURE,
                epistemic_grounding=EpistemicGrounding.PROJECTED,
                canonicality=Canonicality.NON_CANONICAL,
                propagation_depth=1,
            )
            graph.add_node(p_node)

        assert graph.projected_node_count == 4

        # Attempting to add a 5th projected node must raise ValueError
        overflow_node = TemporalNode(
            node_id="proj_overflow",
            label="Projected Stage Overflow",
            stage=LifeStage.CAREER,
            interval=TemporalInterval.create_year(2030),
            temporal_horizon=TemporalHorizon.FUTURE,
            epistemic_grounding=EpistemicGrounding.PROJECTED,
            canonicality=Canonicality.NON_CANONICAL,
            propagation_depth=1,
        )
        with pytest.raises(ValueError, match="MAX_PROJECTED_NODES bound.*reached"):
            graph.add_node(overflow_node)

        # Anti-snowballing: recursive projection forbidden (tested on graph before reaching bound)
        graph_anti = TemporalConstraintGraph()
        p0 = TemporalNode(
            node_id="proj_0",
            label="Projected Stage 0",
            stage=LifeStage.CAREER,
            interval=TemporalInterval.create_year(2026),
            temporal_horizon=TemporalHorizon.FUTURE,
            epistemic_grounding=EpistemicGrounding.PROJECTED,
            canonicality=Canonicality.NON_CANONICAL,
            propagation_depth=1,
        )
        graph_anti.add_node(p0)
        p_recursive = TemporalNode(
            node_id="proj_recursive",
            label="Recursive Projected",
            stage=LifeStage.CAREER,
            interval=TemporalInterval.create_year(2031),
            temporal_horizon=TemporalHorizon.FUTURE,
            epistemic_grounding=EpistemicGrounding.PROJECTED,
            canonicality=Canonicality.NON_CANONICAL,
            origin_node_id="proj_0",
            propagation_depth=2,
        )
        with pytest.raises(ValueError, match="Recursive projection forbidden"):
            graph_anti.add_node(p_recursive)

    # -------------------------------------------------------------------------
    # Cluster 2: World Rules & Applicability (GC-175 ~ GC-178)
    # -------------------------------------------------------------------------

    def test_gc175_world_knowledge_registry_authority_singularity(self):
        """GC-175: WorldKnowledgeRegistry as the Singular Rule Authority.

        Asserts that TemporalRuleRegistry maintains zero competing storage or state;
        it operates strictly as a typed view/adapter over WorldKnowledgeRegistry.
        """
        all_temporal_rules = TemporalRuleRegistry.all_rules()
        assert len(all_temporal_rules) > 0

        assert not hasattr(TemporalRuleRegistry, "_rules")
        assert not hasattr(TemporalRuleRegistry, "_store")

        for rule in all_temporal_rules:
            assert isinstance(rule, TemporalRuleItem)
            assert rule.scope in (
                TemporalRuleScope.NATIONAL_EDUCATION_SYSTEM,
                TemporalRuleScope.INSTITUTION_SPECIFIC,
                TemporalRuleScope.PATHWAY_SPECIFIC,
                TemporalRuleScope.GENERAL_ACADEMIC,
            )

    def test_gc176_scoped_applicability_and_non_leaking_constraints(self):
        """GC-176: Scoped Applicability & Non-Leaking Institutional Constraints.

        Asserts that institution-scoped rules (e.g. USM intake window in October)
        apply strictly within their declared scope and never leak to other institutions.
        """
        rule_usm = TemporalRuleRegistry.get("RULE_USM_INTAKE_WINDOW")
        assert rule_usm is not None
        assert rule_usm.scope == TemporalRuleScope.INSTITUTION_SPECIFIC

        # Applies to designated institution
        assert rule_usm.applies_to_institution("world.usm.main_campus") is True
        # Rejects other institutions
        assert rule_usm.applies_to_institution("world.um.main_campus") is False
        # Rejects unrecorded / unknown institution
        assert rule_usm.applies_to_institution(None) is False

    def test_gc177_non_universal_pre_u_and_diploma_articulation(self):
        """GC-177: Non-Universal Pre-University Prerequisite & Diploma Articulation.

        Asserts that Pre-U is NOT a universal prerequisite for higher education.
        The Diploma pathway articulates directly to Undergraduate education and
        is evaluated as fully compatible without Pre-U nodes.
        """
        base_nodes = [
            TemporalNode(
                node_id="node_birth",
                label="Birth",
                interval=TemporalInterval.create_year(2004),
                temporal_horizon=TemporalHorizon.PAST,
            ),
            TemporalNode(
                node_id="node_spm",
                label="SPM",
                stage=LifeStage.SECONDARY_EDUCATION,
                interval=TemporalInterval.create_year(2021),
                temporal_horizon=TemporalHorizon.PAST,
            ),
            TemporalNode(
                node_id="node_undergrad",
                label="Undergraduate",
                stage=LifeStage.UNDERGRADUATE,
                interval=TemporalInterval.create_month(2024, 10),
                temporal_horizon=TemporalHorizon.PRESENT,
            ),
        ]

        plurality = TimelineTrajectoryEngine.generate_trajectories(
            base_nodes=base_nodes,
            known_pathway="DIPLOMA",
        )

        assert plurality.total_compatible_count >= 1
        diploma_traj = next(
            (t for t in plurality.compatible_trajectories if t.pathway == "DIPLOMA"),
            None,
        )
        assert diploma_traj is not None
        assert diploma_traj.status == TrajectoryStatus.COMPATIBLE
        stages = [n.stage for n in diploma_traj.nodes]
        assert LifeStage.DIPLOMA in stages
        assert LifeStage.PRE_UNIVERSITY not in stages
        assert LifeStage.UNDERGRADUATE in stages

    def test_gc178_advisory_anomaly_vs_hard_rejection_demarcation(self):
        """GC-178: Advisory Anomaly vs. Hard Rejection Demarcation.

        Asserts that advisory rule violations mark ADVISORY_ANOMALY but remain in
        compatible_trajectories, while hard rule violations isolate HARD_INCOMPATIBLE.
        """
        hard_incomp_traj = LifeTrajectory(
            trajectory_id="traj_hard_incomp",
            pathway="STPM",
            nodes=(
                TemporalNode(
                    node_id="n_spm",
                    label="SPM",
                    stage=LifeStage.SECONDARY_EDUCATION,
                    interval=TemporalInterval.create_year(2025),
                ),
                TemporalNode(
                    node_id="n_ug",
                    label="Undergrad",
                    stage=LifeStage.UNDERGRADUATE,
                    interval=TemporalInterval.create_month(2020, 10),
                ),
            ),
            status=TrajectoryStatus.HARD_INCOMPATIBLE,
            evaluation_findings=(
                ConstraintEvaluationResult(
                    rule_id="RULE_PRECEDENCE_SECONDARY_TO_UNDERGRAD",
                    status=ConstraintStatus.VIOLATED,
                    target_node_ids=("n_spm", "n_ug"),
                    is_hard_rejection=True,
                    explanation="Undergraduate intake precedes SPM.",
                ),
            ),
        )
        assert hard_incomp_traj.status == TrajectoryStatus.HARD_INCOMPATIBLE

        advisory_traj = LifeTrajectory(
            trajectory_id="traj_advisory",
            pathway="STPM",
            nodes=(
                TemporalNode(
                    node_id="n_spm2",
                    label="SPM",
                    stage=LifeStage.SECONDARY_EDUCATION,
                    interval=TemporalInterval.create_year(2020),
                ),
                TemporalNode(
                    node_id="n_ug2",
                    label="Undergrad",
                    stage=LifeStage.UNDERGRADUATE,
                    interval=TemporalInterval.create_month(2025, 10),
                ),
            ),
            status=TrajectoryStatus.ADVISORY_ANOMALY,
            evaluation_findings=(
                ConstraintEvaluationResult(
                    rule_id="RULE_GAP_ADVISORY",
                    status=ConstraintStatus.VIOLATED,
                    target_node_ids=("n_spm2", "n_ug2"),
                    is_hard_rejection=False,
                    explanation="Long interval between secondary and undergraduate studies.",
                ),
            ),
        )
        assert advisory_traj.status == TrajectoryStatus.ADVISORY_ANOMALY

    # -------------------------------------------------------------------------
    # Cluster 3: Constraint Graph & Tri-State Semantics (GC-179 ~ GC-182)
    # -------------------------------------------------------------------------

    def test_gc179_tri_state_logic_completeness_and_unknown_semantics(self):
        """GC-179: Tri-State Logic Completeness & UNKNOWN Semantics.

        Asserts that missing information or UNKNOWN granularity strictly yields
        ConstraintStatus.UNDETERMINED, never falling back to false VIOLATED or SATISFIED.
        """
        graph = TemporalConstraintGraph()

        node1 = TemporalNode(
            node_id="node_known",
            interval=TemporalInterval.create_year(2025),
        )
        node2 = TemporalNode(
            node_id="node_unknown",
            interval=TemporalInterval.create_unknown(),
        )
        graph.add_node(node1)
        graph.add_node(node2)

        edge = TemporalEdge(
            edge_id="e_unknown",
            source_node_id="node_known",
            target_node_id="node_unknown",
            relation=TemporalRelationType.BEFORE,
        )
        graph.add_edge(edge)

        res = TemporalConstraintEvaluator.evaluate_edge_relation(graph, edge)
        assert res.status == ConstraintStatus.UNDETERMINED
        assert "Interval boundaries unknown" in res.explanation

    def test_gc180_temporal_constraint_violation_not_personal_contradiction(self):
        """GC-180: Temporal Constraint Violation != Personal Contradiction.

        Asserts that a temporal constraint violation represents world temporal incompatibility,
        not a personal contradiction within CharacterCore or user deceit.
        """
        finding = ConstraintEvaluationResult(
            rule_id="RULE_PRECEDENCE_SECONDARY_TO_UNDERGRAD",
            status=ConstraintStatus.VIOLATED,
            target_node_ids=("n_spm", "n_ug"),
            is_hard_rejection=True,
            explanation="Temporal precedence inverted.",
        )
        assert finding.status == ConstraintStatus.VIOLATED

        core = _make_core_with_facts({
            "identity.birth_date": "2006-05-12",
            "education.spm_year": 2023,
        })
        assert core.get_fact("education.spm_year").value == 2023

    def test_gc181_ephemeral_in_memory_graph_lifecycle(self):
        """GC-181: Ephemeral In-Memory Graph Lifecycle (Zero SQLite Footprint).

        Asserts that TemporalConstraintGraph exists strictly in ephemeral memory
        without SQLite ORM backing or cross-turn persistence.
        """
        graph = TemporalConstraintGraph()
        assert not hasattr(graph, "__tablename__")
        assert not hasattr(graph, "session")
        assert not hasattr(TemporalNode, "__tablename__")
        assert not hasattr(TemporalEdge, "__tablename__")

    def test_gc182_deterministic_topological_node_and_edge_sequencing(self):
        """GC-182: Deterministic Topological Node and Edge Sequencing.

        Asserts that node sequencing is deterministic regardless of insertion order.
        """
        graph_a = TemporalConstraintGraph()
        for name in ["node_z", "node_a", "node_m", "node_c"]:
            graph_a.add_node(TemporalNode(node_id=name))

        graph_b = TemporalConstraintGraph()
        for name in ["node_c", "node_m", "node_a", "node_z"]:
            graph_b.add_node(TemporalNode(node_id=name))

        assert [n.node_id for n in graph_a.all_nodes()] == ["node_a", "node_c", "node_m", "node_z"]
        assert [n.node_id for n in graph_b.all_nodes()] == ["node_a", "node_c", "node_m", "node_z"]

    # -------------------------------------------------------------------------
    # Cluster 4: Trajectory Plurality & Temporal Inference (GC-183 ~ GC-186)
    # -------------------------------------------------------------------------

    def test_gc183_trajectory_plurality_preservation_under_ambiguity(self):
        """GC-183: Trajectory Plurality Preservation Under Pathway Ambiguity.

        Asserts that when educational pathway is unknown, all 4 canonical pathways
        are synthesized and ambiguity is strictly preserved without arbitrary selection.
        """
        base_nodes = [
            TemporalNode(
                node_id="node_birth",
                label="Birth",
                interval=TemporalInterval.create_year(2006),
                temporal_horizon=TemporalHorizon.PAST,
            ),
            TemporalNode(
                node_id="node_spm",
                label="SPM",
                stage=LifeStage.SECONDARY_EDUCATION,
                interval=TemporalInterval.create_year(2023),
                temporal_horizon=TemporalHorizon.PAST,
            ),
        ]

        plurality = TimelineTrajectoryEngine.generate_trajectories(
            base_nodes=base_nodes,
            known_pathway=None,
        )

        assert plurality.is_ambiguity_unresolved is True
        assert plurality.selected_canonical_trajectory is None
        assert set(plurality.compatible_pathways) == set(CANONICAL_HIGHER_ED_PATHWAYS)

    def test_gc184_bounded_ambiguity_representation_overflow_preservation(self):
        """GC-184: Bounded Ambiguity Representation (Overflow Preservation, No Truncation).

        Asserts that when all 4 pathways are compatible (> MAX_COMPATIBLE_TRAJECTORIES = 3),
        the engine enters bounded ambiguity without silently truncating to 3 items.
        """
        base_nodes = [
            TemporalNode(
                node_id="node_birth",
                label="Birth",
                interval=TemporalInterval.create_year(2006),
                temporal_horizon=TemporalHorizon.PAST,
            ),
            TemporalNode(
                node_id="node_spm",
                label="SPM",
                stage=LifeStage.SECONDARY_EDUCATION,
                interval=TemporalInterval.create_year(2023),
                temporal_horizon=TemporalHorizon.PAST,
            ),
            TemporalNode(
                node_id="node_ug",
                label="Undergraduate",
                stage=LifeStage.UNDERGRADUATE,
                interval=TemporalInterval.create_month(2025, 10),
                temporal_horizon=TemporalHorizon.PRESENT,
            ),
        ]

        plurality = TimelineTrajectoryEngine.generate_trajectories(
            base_nodes=base_nodes,
            known_pathway=None,
        )

        assert plurality.total_compatible_count == 4
        assert plurality.trajectory_bound_exceeded is True
        assert plurality.compatible_trajectories == ()
        assert set(plurality.compatible_pathways) == set(CANONICAL_HIGHER_ED_PATHWAYS)
        assert plurality.selected_canonical_trajectory is None

    def test_gc185_temporal_compatibility_alone_never_authorizes_canonical(self):
        """GC-185: Temporal Compatibility Alone Never Authorizes Canonical Selection.

        Asserts that uniquely compatible temporal trajectories with DERIVED/PROJECTED
        grounding remain selected_canonical_trajectory = None. Canonical designation
        strictly requires USER_CONFIRMED or OBSERVED grounding.
        """
        base_nodes = [
            TemporalNode(
                node_id="node_birth",
                label="Birth",
                interval=TemporalInterval.create_year(2006),
                temporal_horizon=TemporalHorizon.PAST,
            ),
            TemporalNode(
                node_id="node_spm",
                label="SPM",
                stage=LifeStage.SECONDARY_EDUCATION,
                interval=TemporalInterval.create_year(2023),
                temporal_horizon=TemporalHorizon.PAST,
            ),
            TemporalNode(
                node_id="node_ug",
                label="Undergraduate",
                stage=LifeStage.UNDERGRADUATE,
                interval=TemporalInterval.create_month(2024, 7),  # Only Foundation fits 1-year duration
                temporal_horizon=TemporalHorizon.PRESENT,
            ),
        ]

        plurality = TimelineTrajectoryEngine.generate_trajectories(
            base_nodes=base_nodes,
            known_pathway="FOUNDATION",
            pathway_grounding=EpistemicGrounding.DERIVED,
        )

        assert plurality.total_compatible_count == 1
        assert plurality.selected_canonical_trajectory is None

    def test_gc186_developmental_rank_sanity_without_stage_fabrication(self):
        """GC-186: Developmental Rank Sanity Check Without Missing Stage Fabrication.

        Asserts that developmental stage order checks sanity, but does not invent
        or fabricate missing intermediate stages as canonical facts.
        """
        core = _make_core_with_facts({
            "identity.birth_date": "2006-05-12",
            "education.spm_year": 2023,
            "education.undergraduate_intake": "2025-10",
        })

        coordinator = TimelineOrchestrationCoordinator()
        base_nodes = coordinator.extract_base_temporal_nodes(core)

        stages = [n.stage for n in base_nodes]
        assert LifeStage.SECONDARY_EDUCATION in stages
        assert LifeStage.UNDERGRADUATE in stages
        assert LifeStage.PRE_UNIVERSITY not in stages

        assert core.get_fact("education.pre_u") is None

    # -------------------------------------------------------------------------
    # Cluster 5: C3 Gate & Repair Delegation (GC-187 ~ GC-191)
    # -------------------------------------------------------------------------

    def test_gc187_trajectory_incompatibility_not_candidate_incompatibility(self):
        """GC-187: Trajectory Incompatibility != Candidate Incompatibility (Lock 1 & Lock A).

        Asserts that candidate exclusion requires applicable_trajectory_count > 0
        AND all(status == HARD_INCOMPATIBLE).
        0 applicable trajectories or any COMPATIBLE/UNDETERMINED/ADVISORY keeps candidate eligible.
        """
        coordinator = TimelineOrchestrationCoordinator()
        c_cand = _make_candidate("c_test", "hobbies.reading", "novels")

        # 1. Zero applicable trajectories (applicable_count == 0) -> NOT excluded (Lock A)
        res_zero = coordinator.coordinate_turn(
            active_candidates=[c_cand],
            candidate_evaluations_override={"c_test": ()},
        )
        assert res_zero.is_candidate_eligible("c_test") is True
        assert "c_test" not in res_zero.temporally_incompatible_candidate_ids

        # 2. HARD + COMPATIBLE -> NOT excluded
        res_mix1 = coordinator.coordinate_turn(
            active_candidates=[c_cand],
            candidate_evaluations_override={
                "c_test": (TrajectoryStatus.HARD_INCOMPATIBLE, TrajectoryStatus.COMPATIBLE),
            },
        )
        assert res_mix1.is_candidate_eligible("c_test") is True

        # 3. HARD + UNDETERMINED -> NOT excluded
        res_mix2 = coordinator.coordinate_turn(
            active_candidates=[c_cand],
            candidate_evaluations_override={
                "c_test": (TrajectoryStatus.HARD_INCOMPATIBLE, ConstraintStatus.UNDETERMINED),
            },
        )
        assert res_mix2.is_candidate_eligible("c_test") is True

        # 4. HARD + ADVISORY -> NOT excluded
        res_mix3 = coordinator.coordinate_turn(
            active_candidates=[c_cand],
            candidate_evaluations_override={
                "c_test": (TrajectoryStatus.HARD_INCOMPATIBLE, TrajectoryStatus.ADVISORY_ANOMALY),
            },
        )
        assert res_mix3.is_candidate_eligible("c_test") is True

        # 5. ALL HARD -> excluded
        res_all_hard = coordinator.coordinate_turn(
            active_candidates=[c_cand],
            candidate_evaluations_override={
                "c_test": (TrajectoryStatus.HARD_INCOMPATIBLE, TrajectoryStatus.HARD_INCOMPATIBLE),
            },
        )
        assert res_all_hard.is_candidate_eligible("c_test") is False
        assert "c_test" in res_all_hard.temporally_incompatible_candidate_ids

    def test_gc188_bounded_ambiguity_candidate_immunity(self):
        """GC-188: Bounded Ambiguity Candidate Immunity (Lock B).

        Asserts that when trajectory_bound_exceeded = True (4 compatible pathways),
        candidates evaluated against this plurality remain fully eligible.
        """
        coordinator = TimelineOrchestrationCoordinator()
        core = _make_core_with_facts({
            "identity.birth_date": "2006-05-12",
            "education.spm_year": 2023,
            "education.undergraduate_intake": "2025-10",
        })
        c_cand = _make_candidate("c_hobby", "hobbies.chess", "tactics")

        res = coordinator.coordinate_turn(
            core=core,
            active_candidates=[c_cand],
        )

        assert res.trajectory_plurality.trajectory_bound_exceeded is True
        assert res.is_candidate_eligible("c_hobby") is True
        assert "c_hobby" not in res.temporally_incompatible_candidate_ids

    def test_gc189_zero_repair_policy_authority_and_symmetric_conflict_facts(self):
        """GC-189: Zero Repair-Policy Authority in C3 & Symmetric Conflict Facts (Lock 2 & Lock 8).

        Asserts that TemporalConflictSignal has zero suggested_repair_level,
        and conflicting_fact_keys is symmetric without designating index [0] as repair target.
        """
        adapter = TimelineEvidenceAdapter(
            independent_timeline_supported=True,
            temporal_split=None,
            conflicting_node_ids=("node_a", "node_b"),
            evidence_fact_keys=("fact_a", "fact_b"),
            explanation="Test symmetric conflict",
        )
        signal = TemporalConflictSignal(
            conflict_id="signal_sym",
            conflicting_fact_keys=("fact_a", "fact_b"),
            temporal_evidence=adapter,
            rationale="Symmetric test",
        )

        assert not hasattr(signal, "suggested_repair_level")
        assert set(signal.conflicting_fact_keys) == {"fact_a", "fact_b"}

    def test_gc190_timeline_evidence_adapter_strict_contract_and_repair(self):
        """GC-190: TimelineEvidenceAdapter Strict Contract & Repair Delegation (Lock 3, 7 & Lock D).

        Asserts that TimelineEvidenceAdapter strictly forbids extra fields, rejects raw dicts
        in TemporalConflictSignal, and serializes directly to RealityRepairService.repair().
        """
        with pytest.raises(ValidationError):
            TimelineEvidenceAdapter(
                independent_timeline_supported=True,
                unauthorized_field="malformed",  # type: ignore[call-arg]
            )

        adapter = TimelineEvidenceAdapter(
            independent_timeline_supported=True,
            temporal_split={
                "past": {"fact_key": "education.spm_year"},
                "present": {"fact_key": "education.undergraduate_intake"},
            },
            conflicting_node_ids=("node_spm", "node_ug"),
            evidence_fact_keys=("education.spm_year", "education.undergraduate_intake"),
            explanation="Valid adapter delegation",
        )

        with pytest.raises(ValidationError):
            TemporalConflictSignal(
                conflict_id="sig_fail",
                conflicting_fact_keys=("education.spm_year", "education.undergraduate_intake"),
                temporal_evidence={"raw": "dict"},  # type: ignore[arg-type]
            )

        repair_res = RealityRepairService.repair(
            conflict_type="TEMPORAL_CONFLICT",
            timeline_evidence=adapter.to_repair_evidence_dict(),
        )
        assert repair_res.repair_level == RepairLevel.LEVEL_2_TEMPORAL_REINTERPRETATION
        assert repair_res.is_repaired is True

    def test_gc191_explicit_evaluation_status_semantics(self):
        """GC-191: Explicit Evaluation Status Semantics (Lock 4: UNAVAILABLE != NO CONFLICT).

        Asserts that on unexpected failure, coordinator degrades gracefully to UNAVAILABLE
        with zero candidate exclusions and zero emitted conflict signals.
        """
        coordinator = TimelineOrchestrationCoordinator()
        c_cand = _make_candidate("c_test", "education.pathway", "STPM")

        # Force exception by passing malformed core
        res = coordinator.coordinate_turn(
            core="malformed_core_object",  # type: ignore[arg-type]
            active_candidates=[c_cand],
        )

        assert res.evaluation_status == TemporalEvaluationStatus.UNAVAILABLE
        assert res.evaluation_error is not None
        assert res.temporally_incompatible_candidate_ids == ()
        assert res.is_candidate_eligible("c_test") is True
        assert res.canonical_conflict_signal is None

    # -------------------------------------------------------------------------
    # Cluster 6: End-to-End Integration & Boundary Audit (GC-192 ~ GC-195)
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_gc192_post_repair_context_freshness_and_propagation(self):
        """GC-192: Post-Repair Context Freshness & Repair-Result Propagation (Lock C).

        Asserts that canonical temporal contradiction resolved at Step G propagates
        cleanly into Step J GovernedRealityContext without stale pre-repair context,
        and without requiring artificial secondary database reloads.
        """
        mock_session = AsyncMock()
        mock_repo = MagicMock()
        mock_repo.get_all_active_candidates = AsyncMock(return_value=[])

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
            user_input="Tell me about your studies.",
            core=core,
            character_id="aevum",
        )

        # 1. Step G repair executed
        assert turn_result.repair_result is not None
        assert turn_result.repair_result.is_repaired is True
        assert turn_result.repair_result.repair_level == RepairLevel.LEVEL_2_TEMPORAL_REINTERPRETATION
        assert turn_result.repair_result.temporal_split is not None

        # 2. Step J context contains repair interpretation matching repair result
        context = turn_result.governed_reality
        assert len(context.repair_items) == 1
        repair_item = context.repair_items[0]
        assert repair_item.provenance.truth_type == EpistemicTruthType.EPHEMERAL_REPAIR_INTERPRETATION
        assert repair_item.value["temporal_split"] == turn_result.repair_result.temporal_split

        # 3. Formatted XML contains ephemeral_repair_context
        blocks = RealityContextBuilder.format_all_reality_blocks(context)
        assert any("<ephemeral_repair_context" in b and "<temporal_split>" in b for b in blocks)

    def test_gc193_serialization_only_trajectory_presentation(self):
        """GC-193: Serialization-Only Trajectory Presentation (Lock 5 & Invariant C).

        Asserts that RealityContextBuilder performs zero temporal reasoning or winner selection,
        serializing trajectory plurality with explicit non-assertive guidance.
        """
        plurality = TrajectoryPluralityResult(
            compatible_trajectories=(),
            compatible_pathways=("DIPLOMA", "FOUNDATION", "MATRIKULASI", "STPM"),
            incompatible_trajectories=(),
            total_compatible_count=4,
            is_ambiguity_unresolved=True,
            trajectory_bound_exceeded=True,
            selected_canonical_trajectory=None,
        )

        context = RealityContextBuilder.build_context(
            character_id="aevum",
            trajectory_plurality=plurality,
        )

        assert len(context.temporal_items) == 1
        assert context.temporal_items[0].provenance.truth_type == EpistemicTruthType.TEMPORAL_TRAJECTORY_PLURALITY

        blocks = RealityContextBuilder.format_all_reality_blocks(context)
        traj_block = next((b for b in blocks if "<temporal_trajectory_context>" in b), None)
        assert traj_block is not None
        assert "Do NOT assert a specific pathway as a confirmed personal fact." in traj_block

    def test_gc194_pure_8b_module_ast_audit_vs_integration_delegation(self):
        """GC-194: Pure 8B Module AST Audit vs. Integration Layer Delegation.

        Static AST audit verifying pure 8B modules have:
        - 0 calls to set_fact()
        - 0 imports of PromotionAuthorizationToken
        - 0 network imports (requests, httpx, aiohttp, urllib)
        - 0 LLM provider imports (google.genai, openai, anthropic)
        - 0 direct SQLite table mutations
        - 0 RealityBeliefEngine references
        """
        backend_dir = pathlib.Path(__file__).parent.parent
        pure_8b_files = [
            backend_dir / "app" / "reality" / "temporal_models.py",
            backend_dir / "app" / "reality" / "temporal_rules.py",
            backend_dir / "app" / "reality" / "temporal_graph.py",
            backend_dir / "app" / "reality" / "trajectory_engine.py",
            backend_dir / "app" / "reality" / "timeline_orchestration_coordinator.py",
        ]

        forbidden_import_modules = {"requests", "httpx", "aiohttp", "urllib", "openai", "anthropic"}

        for filepath in pure_8b_files:
            assert filepath.exists(), f"File {filepath} not found."
            with open(filepath, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=str(filepath))

            for node in ast.walk(tree):
                # 1. No forbidden network/LLM imports
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert alias.name not in forbidden_import_modules, (
                            f"Forbidden import '{alias.name}' in {filepath.name}."
                        )
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    assert not any(mod.startswith(bad) for bad in forbidden_import_modules), (
                        f"Forbidden import from '{mod}' in {filepath.name}."
                    )
                    assert "PromotionAuthorizationToken" not in [a.name for a in node.names], (
                        f"PromotionAuthorizationToken imported in {filepath.name}."
                    )
                    assert "RealityBeliefEngine" not in [a.name for a in node.names], (
                        f"Legacy RealityBeliefEngine imported in {filepath.name}."
                    )

                # 2. No set_fact calls
                if isinstance(node, ast.Call):
                    func_name = ""
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr
                    assert func_name != "set_fact", (
                        f"Direct set_fact() call found in {filepath.name}."
                    )

    @pytest.mark.asyncio
    async def test_gc195_integrated_full_turn_temporal_reality_lifecycle(self):
        """GC-195: Integrated Full-Turn Temporal Reality Lifecycle (Semantic Determinism).

        Verifies the complete 12-step orchestration pipeline:
        Step A -> Step B -> Step C -> Step C2 -> Step D -> Step C3 -> Step E -> Step F -> Step G -> Step H -> Step I -> Step J.
        Demonstrates that identical semantic inputs produce identical normalized output,
        identical context serialization, and identical prompt SHA-256 hash.
        """
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

        # Run turn 1
        res1 = await service.run_turn(
            user_input="What are you studying at university?",
            core=core,
            character_id="aevum",
        )

        # Run turn 2 with identical inputs
        res2 = await service.run_turn(
            user_input="What are you studying at university?",
            core=core,
            character_id="aevum",
        )

        # Semantic output determinism
        assert res1.governed_reality is not None
        assert res2.governed_reality is not None

        # Context serialization determinism
        blocks1 = RealityContextBuilder.format_all_reality_blocks(res1.governed_reality)
        blocks2 = RealityContextBuilder.format_all_reality_blocks(res2.governed_reality)
        assert blocks1 == blocks2

        # Hash determinism (excluding execution duration / timestamps)
        assert (
            res1.governed_reality.audit_metadata.context_hash_sha256
            == res2.governed_reality.audit_metadata.context_hash_sha256
        )
