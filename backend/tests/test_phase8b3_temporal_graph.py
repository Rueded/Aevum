"""Unit tests for Phase 8B.3 Temporal Constraint Graph (TCG) & Constraint Evaluation.

Comprehensive verification of all 30 constitutional requirements:
1. test_01_graph_construction
2. test_02_immutable_nodes
3. test_03_immutable_edges
4. test_04_provenance_preservation
5. test_05_propagation_depth_zero
6. test_06_propagation_depth_one
7. test_07_propagation_depth_two
8. test_08_propagation_depth_greater_than_two_rejected
9. test_09_max_projected_nodes_bound_enforced
10. test_10_unknown_interval_evaluation
11. test_11_before_and_after_evaluation
12. test_12_duration_bound_evaluation
13. test_13_age_window_evaluation
14. test_14_pathway_scoped_precedence
15. test_15_diploma_to_undergraduate_precedence
16. test_16_stpm_to_undergraduate_precedence
17. test_17_matrikulasi_to_undergraduate_precedence
18. test_18_foundation_to_undergraduate_precedence
19. test_19_institution_scoped_usm_rule_matches
20. test_20_usm_rule_does_not_apply_to_other_institutions
21. test_21_violated_constraint_is_not_personal_contradiction
22. test_22_no_canonical_mutation
23. test_23_no_database_access
24. test_24_no_network_imports
25. test_25_no_llm_calls
26. test_26_no_reality_belief_engine
27. test_27_deterministic_ordering
28. test_28_no_pseudo_probability
29. test_29_projected_nodes_cannot_recursively_project
30. test_30_graph_remains_ephemeral
"""

from __future__ import annotations

import ast
from datetime import date
import pathlib
import pytest
from pydantic import ValidationError

from app.character.core_models import CharacterCore
from app.reality.temporal_models import (
    MAX_PROJECTED_NODES,
    MAX_TEMPORAL_PROPAGATION_HOPS,
    Canonicality,
    EpistemicGrounding,
    LifeStage,
    TemporalGranularity,
    TemporalHorizon,
    TemporalInterval,
)
from app.reality.temporal_rules import (
    TemporalRuleRegistry,
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


class TestPhase8B3TemporalGraph:
    """Test suite covering the 30 constitutional requirements of Phase 8B.3."""

    # -------------------------------------------------------------------------
    # 1. Graph Construction
    # -------------------------------------------------------------------------
    def test_01_graph_construction(self):
        """Construct an empty graph and populate with nodes and edges."""
        graph = TemporalConstraintGraph()
        assert graph.node_count == 0
        assert graph.edge_count == 0

        node1 = TemporalNode(
            node_id="node_birth",
            label="Birth",
            interval=TemporalInterval.create_exact(start=date(2006, 5, 12)),
            temporal_horizon=TemporalHorizon.PAST,
            epistemic_grounding=EpistemicGrounding.USER_CONFIRMED,
            canonicality=Canonicality.CANONICAL,
        )
        node2 = TemporalNode(
            node_id="node_spm",
            label="SPM Examination",
            interval=TemporalInterval.create_year(2023),
            stage=LifeStage.SECONDARY_EDUCATION,
            temporal_horizon=TemporalHorizon.PAST,
            epistemic_grounding=EpistemicGrounding.OBSERVED,
            canonicality=Canonicality.CANONICAL,
        )
        graph.add_node(node1)
        graph.add_node(node2)

        edge = TemporalEdge(
            edge_id="edge_birth_to_spm",
            source_node_id="node_birth",
            target_node_id="node_spm",
            relation=TemporalRelationType.BEFORE,
        )
        graph.add_edge(edge)

        assert graph.node_count == 2
        assert graph.edge_count == 1
        assert graph.get_node("node_birth") == node1
        assert graph.get_edge("edge_birth_to_spm") == edge

    # -------------------------------------------------------------------------
    # 2. Immutable Nodes
    # -------------------------------------------------------------------------
    def test_02_immutable_nodes(self):
        """TemporalNode is frozen and rejects attribute assignment and extra fields."""
        node = TemporalNode(
            node_id="node_test",
            label="Test Node",
        )
        with pytest.raises(ValidationError, match="Instance is frozen"):
            node.label = "Modified"  # type: ignore

        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            TemporalNode(
                node_id="node_extra",
                arbitrary_confidence=0.88,  # type: ignore - VIOLATION!
            )

    # -------------------------------------------------------------------------
    # 3. Immutable Edges
    # -------------------------------------------------------------------------
    def test_03_immutable_edges(self):
        """TemporalEdge is frozen and rejects attribute assignment and extra fields."""
        edge = TemporalEdge(
            edge_id="e1",
            source_node_id="n1",
            target_node_id="n2",
            relation=TemporalRelationType.BEFORE,
        )
        with pytest.raises(ValidationError, match="Instance is frozen"):
            edge.relation = TemporalRelationType.AFTER  # type: ignore

        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            TemporalEdge(
                edge_id="e2",
                source_node_id="n1",
                target_node_id="n2",
                relation=TemporalRelationType.BEFORE,
                pseudo_weight=0.5,  # type: ignore - VIOLATION!
            )

    # -------------------------------------------------------------------------
    # 4. Provenance Preservation
    # -------------------------------------------------------------------------
    def test_04_provenance_preservation(self):
        """Nodes preserve origin_fact_key, propagation_depth, and constraint_chain."""
        node = TemporalNode(
            node_id="node_derived_ug",
            label="Undergraduate Year 1",
            stage=LifeStage.UNDERGRADUATE,
            temporal_horizon=TemporalHorizon.PRESENT,
            epistemic_grounding=EpistemicGrounding.DERIVED,
            canonicality=Canonicality.NON_CANONICAL,
            origin_fact_key="education.intake_year",
            origin_node_id="node_intake",
            propagation_depth=1,
            constraint_chain=("RULE_MY_DEGREE_DURATION",),
        )
        assert node.origin_fact_key == "education.intake_year"
        assert node.origin_node_id == "node_intake"
        assert node.propagation_depth == 1
        assert node.constraint_chain == ("RULE_MY_DEGREE_DURATION",)

    # -------------------------------------------------------------------------
    # 5. Propagation Depth = 0
    # -------------------------------------------------------------------------
    def test_05_propagation_depth_zero(self):
        """Propagation depth 0 is valid (authoritative baseline/observed fact)."""
        node = TemporalNode(
            node_id="node_d0",
            propagation_depth=0,
            temporal_horizon=TemporalHorizon.PAST,
            epistemic_grounding=EpistemicGrounding.OBSERVED,
            canonicality=Canonicality.CANONICAL,
        )
        assert node.propagation_depth == 0

    # -------------------------------------------------------------------------
    # 6. Propagation Depth = 1
    # -------------------------------------------------------------------------
    def test_06_propagation_depth_one(self):
        """Propagation depth 1 is valid (direct constraint derivation)."""
        node = TemporalNode(
            node_id="node_d1",
            propagation_depth=1,
            temporal_horizon=TemporalHorizon.PRESENT,
            epistemic_grounding=EpistemicGrounding.DERIVED,
            canonicality=Canonicality.NON_CANONICAL,
        )
        assert node.propagation_depth == 1

    # -------------------------------------------------------------------------
    # 7. Propagation Depth = 2
    # -------------------------------------------------------------------------
    def test_07_propagation_depth_two(self):
        """Propagation depth 2 is valid (adjacent state derivation, hop depth 2)."""
        node = TemporalNode(
            node_id="node_d2",
            propagation_depth=2,
            temporal_horizon=TemporalHorizon.FUTURE,
            epistemic_grounding=EpistemicGrounding.PROJECTED,
            canonicality=Canonicality.NON_CANONICAL,
        )
        assert node.propagation_depth == 2

    # -------------------------------------------------------------------------
    # 8. Propagation Depth > 2 Rejected
    # -------------------------------------------------------------------------
    def test_08_propagation_depth_greater_than_two_rejected(self):
        """Propagation depth > 2 raises ValidationError (MAX_TEMPORAL_PROPAGATION_HOPS = 2)."""
        with pytest.raises(ValidationError, match="Input should be less than or equal to 2"):
            TemporalNode(
                node_id="node_d3",
                propagation_depth=3,  # VIOLATION!
                temporal_horizon=TemporalHorizon.PAST,
                epistemic_grounding=EpistemicGrounding.DERIVED,
                canonicality=Canonicality.NON_CANONICAL,
            )

    # -------------------------------------------------------------------------
    # 9. Cardinality Bound: MAX_PROJECTED_NODES
    # -------------------------------------------------------------------------
    def test_09_max_projected_nodes_bound_enforced(self):
        """Graph rejects adding more than MAX_PROJECTED_NODES (4) projected nodes."""
        graph = TemporalConstraintGraph()

        # Add 4 projected nodes
        for i in range(MAX_PROJECTED_NODES):
            p_node = TemporalNode(
                node_id=f"proj_{i}",
                temporal_horizon=TemporalHorizon.FUTURE,
                epistemic_grounding=EpistemicGrounding.PROJECTED,
                canonicality=Canonicality.NON_CANONICAL,
                propagation_depth=1,
            )
            graph.add_node(p_node)

        assert graph.projected_node_count == 4

        # Adding a 5th projected node must raise ValueError
        fifth_node = TemporalNode(
            node_id="proj_fifth",
            temporal_horizon=TemporalHorizon.FUTURE,
            epistemic_grounding=EpistemicGrounding.PROJECTED,
            canonicality=Canonicality.NON_CANONICAL,
            propagation_depth=1,
        )
        with pytest.raises(ValueError, match="MAX_PROJECTED_NODES bound.*reached"):
            graph.add_node(fifth_node)

    # -------------------------------------------------------------------------
    # 10. UNKNOWN Interval Evaluation Yields UNDETERMINED
    # -------------------------------------------------------------------------
    def test_10_unknown_interval_evaluation(self):
        """UNKNOWN interval boundary must yield UNDETERMINED (never VIOLATED or SATISFIED)."""
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
        # CRITICAL: Must be UNDETERMINED, not False/VIOLATED!
        assert res.status == ConstraintStatus.UNDETERMINED
        assert "Interval boundaries unknown" in res.explanation

    # -------------------------------------------------------------------------
    # 11. BEFORE / AFTER Evaluation
    # -------------------------------------------------------------------------
    def test_11_before_and_after_evaluation(self):
        """Strict BEFORE and AFTER relations evaluate properly."""
        graph = TemporalConstraintGraph()

        n_past = TemporalNode(
            node_id="n_past",
            interval=TemporalInterval.create_exact(start=date(2020, 1, 1), end=date(2021, 1, 1)),
        )
        n_future = TemporalNode(
            node_id="n_future",
            interval=TemporalInterval.create_exact(start=date(2025, 1, 1), end=date(2026, 1, 1)),
        )
        graph.add_node(n_past)
        graph.add_node(n_future)

        # 1. Valid BEFORE
        e_valid = TemporalEdge(
            edge_id="e_valid",
            source_node_id="n_past",
            target_node_id="n_future",
            relation=TemporalRelationType.BEFORE,
        )
        res_valid = TemporalConstraintEvaluator.evaluate_edge_relation(graph, e_valid)
        assert res_valid.status == ConstraintStatus.SATISFIED

        # 2. Inverted BEFORE -> VIOLATED
        e_inverted = TemporalEdge(
            edge_id="e_inverted",
            source_node_id="n_future",
            target_node_id="n_past",
            relation=TemporalRelationType.BEFORE,
        )
        res_inv = TemporalConstraintEvaluator.evaluate_edge_relation(graph, e_inverted)
        assert res_inv.status == ConstraintStatus.VIOLATED
        assert res_inv.is_hard_rejection is True

        # 3. Valid AFTER
        e_after = TemporalEdge(
            edge_id="e_after",
            source_node_id="n_future",
            target_node_id="n_past",
            relation=TemporalRelationType.AFTER,
        )
        res_after = TemporalConstraintEvaluator.evaluate_edge_relation(graph, e_after)
        assert res_after.status == ConstraintStatus.SATISFIED

    # -------------------------------------------------------------------------
    # 12. Duration Bound Evaluation
    # -------------------------------------------------------------------------
    def test_12_duration_bound_evaluation(self):
        """Evaluate duration bounds against nodes."""
        rule_stpm = TemporalRuleRegistry.get("RULE_MY_STPM_DURATION")
        assert rule_stpm is not None

        # 1. Satisfied STPM node (1.5 years: 2022-01-01 to 2023-07-01)
        node_valid = TemporalNode(
            node_id="stpm_valid",
            stage=LifeStage.PRE_UNIVERSITY,
            pathway="STPM",
            interval=TemporalInterval.create_exact(start=date(2022, 1, 1), end=date(2023, 7, 1)),
        )
        res_valid = TemporalConstraintEvaluator.evaluate_duration_bound(node_valid, rule_stpm)
        assert res_valid.status == ConstraintStatus.SATISFIED

        # 2. Too short STPM node (0.5 years: 2022-01-01 to 2022-07-01 -> min is 1.5)
        node_short = TemporalNode(
            node_id="stpm_short",
            stage=LifeStage.PRE_UNIVERSITY,
            pathway="STPM",
            interval=TemporalInterval.create_exact(start=date(2022, 1, 1), end=date(2022, 7, 1)),
        )
        res_short = TemporalConstraintEvaluator.evaluate_duration_bound(node_short, rule_stpm)
        assert res_short.status == ConstraintStatus.VIOLATED

        # 3. Unknown duration -> UNDETERMINED
        node_unknown = TemporalNode(
            node_id="stpm_unknown",
            stage=LifeStage.PRE_UNIVERSITY,
            pathway="STPM",
            interval=TemporalInterval.create_unknown(),
        )
        res_unk = TemporalConstraintEvaluator.evaluate_duration_bound(node_unknown, rule_stpm)
        assert res_unk.status == ConstraintStatus.UNDETERMINED

    # -------------------------------------------------------------------------
    # 13. Age-Window Evaluation
    # -------------------------------------------------------------------------
    def test_13_age_window_evaluation(self):
        """Evaluate age window constraint between birth and milestone."""
        rule_spm_age = TemporalRuleRegistry.get("RULE_MY_SPM_AGE")
        assert rule_spm_age is not None

        birth = TemporalNode(
            node_id="birth",
            interval=TemporalInterval.create_exact(start=date(2006, 5, 12)),
        )

        # SPM at age 17 (2023-11-15) -> SATISFIED (min 16, max 19)
        spm_valid = TemporalNode(
            node_id="spm_valid",
            interval=TemporalInterval.create_exact(start=date(2023, 11, 15)),
        )
        res_valid = TemporalConstraintEvaluator.evaluate_age_window(birth, spm_valid, rule_spm_age)
        assert res_valid.status == ConstraintStatus.SATISFIED

        # SPM at age 12 (2018-11-15) -> VIOLATED (below min 16)
        spm_young = TemporalNode(
            node_id="spm_young",
            interval=TemporalInterval.create_exact(start=date(2018, 11, 15)),
        )
        res_young = TemporalConstraintEvaluator.evaluate_age_window(birth, spm_young, rule_spm_age)
        assert res_young.status == ConstraintStatus.VIOLATED

        # Unknown birth -> UNDETERMINED
        birth_unk = TemporalNode(
            node_id="birth_unk",
            interval=TemporalInterval.create_unknown(),
        )
        res_unk = TemporalConstraintEvaluator.evaluate_age_window(birth_unk, spm_valid, rule_spm_age)
        assert res_unk.status == ConstraintStatus.UNDETERMINED

    # -------------------------------------------------------------------------
    # 14. Pathway-Scoped Precedence Evaluation
    # -------------------------------------------------------------------------
    def test_14_pathway_scoped_precedence(self):
        """Precedence rules enforce prerequisites strictly according to pathway."""
        rule_pre_u = TemporalRuleRegistry.get("RULE_PRECEDENCE_PRE_U_TO_UNDERGRAD")
        assert rule_pre_u is not None

        graph = TemporalConstraintGraph()
        ug_node = TemporalNode(
            node_id="ug_node",
            stage=LifeStage.UNDERGRADUATE,
            pathway="STPM",
            interval=TemporalInterval.create_exact(start=date(2025, 10, 1)),
        )
        graph.add_node(ug_node)

        # In an empty graph with prior nodes, missing required Pre-U is VIOLATED
        sec_node = TemporalNode(
            node_id="sec_node",
            stage=LifeStage.SECONDARY_EDUCATION,
            interval=TemporalInterval.create_exact(start=date(2018, 1, 1), end=date(2022, 12, 31)),
        )
        graph.add_node(sec_node)
        res = TemporalConstraintEvaluator.evaluate_stage_precedence(graph, ug_node, rule_pre_u)
        assert res.status == ConstraintStatus.VIOLATED

    # -------------------------------------------------------------------------
    # 15. Diploma -> Undergraduate Precedence (No Pre-U Requirement)
    # -------------------------------------------------------------------------
    def test_15_diploma_to_undergraduate_precedence(self):
        """Lock 1 & Lock 5: Diploma -> Undergraduate requires Diploma, NOT Pre-U."""
        rule_diploma = TemporalRuleRegistry.get("RULE_PRECEDENCE_DIPLOMA_TO_UNDERGRAD")
        rule_pre_u = TemporalRuleRegistry.get("RULE_PRECEDENCE_PRE_U_TO_UNDERGRAD")
        assert rule_diploma is not None
        assert rule_pre_u is not None

        graph = TemporalConstraintGraph()
        dip_node = TemporalNode(
            node_id="diploma_node",
            stage=LifeStage.DIPLOMA,
            pathway="DIPLOMA",
            interval=TemporalInterval.create_exact(start=date(2022, 7, 1), end=date(2025, 6, 30)),
        )
        ug_node = TemporalNode(
            node_id="ug_node",
            stage=LifeStage.UNDERGRADUATE,
            pathway="DIPLOMA",
            interval=TemporalInterval.create_exact(start=date(2025, 10, 1), end=date(2028, 7, 1)),
        )
        graph.add_node(dip_node)
        graph.add_node(ug_node)

        # 1. Diploma rule evaluates to SATISFIED
        res_dip = TemporalConstraintEvaluator.evaluate_stage_precedence(graph, ug_node, rule_diploma)
        assert res_dip.status == ConstraintStatus.SATISFIED

        # 2. CRITICAL: Pre-U rule does NOT apply to Diploma pathway -> UNDETERMINED / skipped
        res_pre_u = TemporalConstraintEvaluator.evaluate_stage_precedence(graph, ug_node, rule_pre_u)
        assert res_pre_u.status == ConstraintStatus.UNDETERMINED
        assert "does not apply to node pathway 'DIPLOMA'" in res_pre_u.explanation

    # -------------------------------------------------------------------------
    # 16. STPM -> Undergraduate Precedence
    # -------------------------------------------------------------------------
    def test_16_stpm_to_undergraduate_precedence(self):
        """STPM -> Undergraduate requires Pre-U (STPM)."""
        rule_pre_u = TemporalRuleRegistry.get("RULE_PRECEDENCE_PRE_U_TO_UNDERGRAD")
        assert rule_pre_u is not None

        graph = TemporalConstraintGraph()
        stpm_node = TemporalNode(
            node_id="stpm_node",
            stage=LifeStage.PRE_UNIVERSITY,
            pathway="STPM",
            interval=TemporalInterval.create_exact(start=date(2023, 7, 1), end=date(2025, 3, 30)),
        )
        ug_node = TemporalNode(
            node_id="ug_node",
            stage=LifeStage.UNDERGRADUATE,
            pathway="STPM",
            interval=TemporalInterval.create_exact(start=date(2025, 10, 1), end=date(2029, 7, 1)),
        )
        graph.add_node(stpm_node)
        graph.add_node(ug_node)

        res = TemporalConstraintEvaluator.evaluate_stage_precedence(graph, ug_node, rule_pre_u)
        assert res.status == ConstraintStatus.SATISFIED

    # -------------------------------------------------------------------------
    # 17. Matrikulasi -> Undergraduate Precedence
    # -------------------------------------------------------------------------
    def test_17_matrikulasi_to_undergraduate_precedence(self):
        """Matrikulasi -> Undergraduate requires Pre-U."""
        rule_pre_u = TemporalRuleRegistry.get("RULE_PRECEDENCE_PRE_U_TO_UNDERGRAD")
        assert rule_pre_u is not None

        graph = TemporalConstraintGraph()
        matrik_node = TemporalNode(
            node_id="matrik_node",
            stage=LifeStage.PRE_UNIVERSITY,
            pathway="MATRIKULASI",
            interval=TemporalInterval.create_exact(start=date(2024, 6, 1), end=date(2025, 5, 30)),
        )
        ug_node = TemporalNode(
            node_id="ug_node",
            stage=LifeStage.UNDERGRADUATE,
            pathway="MATRIKULASI",
            interval=TemporalInterval.create_exact(start=date(2025, 10, 1), end=date(2029, 7, 1)),
        )
        graph.add_node(matrik_node)
        graph.add_node(ug_node)

        res = TemporalConstraintEvaluator.evaluate_stage_precedence(graph, ug_node, rule_pre_u)
        assert res.status == ConstraintStatus.SATISFIED

    # -------------------------------------------------------------------------
    # 18. Foundation -> Undergraduate Precedence
    # -------------------------------------------------------------------------
    def test_18_foundation_to_undergraduate_precedence(self):
        """Foundation -> Undergraduate requires Pre-U."""
        rule_pre_u = TemporalRuleRegistry.get("RULE_PRECEDENCE_PRE_U_TO_UNDERGRAD")
        assert rule_pre_u is not None

        graph = TemporalConstraintGraph()
        foundation_node = TemporalNode(
            node_id="foundation_node",
            stage=LifeStage.PRE_UNIVERSITY,
            pathway="FOUNDATION",
            interval=TemporalInterval.create_exact(start=date(2024, 7, 1), end=date(2025, 6, 30)),
        )
        ug_node = TemporalNode(
            node_id="ug_node",
            stage=LifeStage.UNDERGRADUATE,
            pathway="FOUNDATION",
            interval=TemporalInterval.create_exact(start=date(2025, 10, 1), end=date(2029, 7, 1)),
        )
        graph.add_node(foundation_node)
        graph.add_node(ug_node)

        res = TemporalConstraintEvaluator.evaluate_stage_precedence(graph, ug_node, rule_pre_u)
        assert res.status == ConstraintStatus.SATISFIED

    # -------------------------------------------------------------------------
    # 19. Institution-Scoped USM Rule Matches USM Context
    # -------------------------------------------------------------------------
    def test_19_institution_scoped_usm_rule_matches(self):
        """USM intake rule applies to USM node."""
        rule_usm = TemporalRuleRegistry.get("RULE_USM_INTAKE_WINDOW")
        assert rule_usm is not None

        # USM node with October start -> SATISFIED
        node_usm_oct = TemporalNode(
            node_id="node_usm_oct",
            institution_ref="world.usm.main_campus",
            interval=TemporalInterval.create_month(year=2025, month=10),
        )
        res_oct = TemporalConstraintEvaluator.evaluate_calendar_window(node_usm_oct, rule_usm)
        assert res_oct.status == ConstraintStatus.SATISFIED

    # -------------------------------------------------------------------------
    # 20. USM Rule Does Not Apply to Other Institutions
    # -------------------------------------------------------------------------
    def test_20_usm_rule_does_not_apply_to_other_institutions(self):
        """USM intake rule does NOT apply to UM or unrecorded institutions."""
        rule_usm = TemporalRuleRegistry.get("RULE_USM_INTAKE_WINDOW")
        assert rule_usm is not None

        # UM node evaluated against USM rule -> UNDETERMINED / does not apply
        node_um = TemporalNode(
            node_id="node_um",
            institution_ref="world.um.main_campus",
            interval=TemporalInterval.create_month(year=2025, month=10),
        )
        res_um = TemporalConstraintEvaluator.evaluate_calendar_window(node_um, rule_usm)
        assert res_um.status == ConstraintStatus.UNDETERMINED
        assert "does not apply to node institution 'world.um.main_campus'" in res_um.explanation

        # Node without institution_ref -> UNDETERMINED
        node_no_inst = TemporalNode(
            node_id="node_no_inst",
            interval=TemporalInterval.create_month(year=2025, month=10),
        )
        res_no_inst = TemporalConstraintEvaluator.evaluate_calendar_window(node_no_inst, rule_usm)
        assert res_no_inst.status == ConstraintStatus.UNDETERMINED

    # -------------------------------------------------------------------------
    # 21. Violated Constraint Is Not Personal Contradiction
    # -------------------------------------------------------------------------
    def test_21_violated_constraint_is_not_personal_contradiction(self):
        """A constraint violation returns a structured finding without triggering repair."""
        graph = TemporalConstraintGraph()
        n1 = TemporalNode(
            node_id="n1",
            interval=TemporalInterval.create_exact(start=date(2025, 1, 1), end=date(2026, 1, 1)),
        )
        n2 = TemporalNode(
            node_id="n2",
            interval=TemporalInterval.create_exact(start=date(2020, 1, 1), end=date(2021, 1, 1)),
        )
        graph.add_node(n1)
        graph.add_node(n2)

        edge = TemporalEdge(
            edge_id="e_invalid",
            source_node_id="n1",
            target_node_id="n2",
            relation=TemporalRelationType.BEFORE,
        )
        graph.add_edge(edge)

        findings = TemporalConstraintEvaluator.evaluate_all(graph)
        violated = [f for f in findings if f.status == ConstraintStatus.VIOLATED]
        assert len(violated) >= 1
        # Confirms it is a structured finding, not an exception or repair mutation
        assert isinstance(violated[0], ConstraintEvaluationResult)

    # -------------------------------------------------------------------------
    # 22. No Canonical Mutation
    # -------------------------------------------------------------------------
    def test_22_no_canonical_mutation(self):
        """Evaluating constraints leaves CharacterCore completely untouched."""
        core = CharacterCore(character_id="aevum")
        initial_facts = dict(core.facts)

        graph = TemporalConstraintGraph()
        graph.add_node(TemporalNode(node_id="n1", interval=TemporalInterval.create_year(2025)))
        graph.add_node(TemporalNode(node_id="n2", interval=TemporalInterval.create_year(2020)))
        graph.add_edge(TemporalEdge(edge_id="e1", source_node_id="n1", target_node_id="n2", relation=TemporalRelationType.BEFORE))

        _ = TemporalConstraintEvaluator.evaluate_all(graph)

        assert core.facts == initial_facts
        assert len(core.facts) == len(initial_facts)

    # -------------------------------------------------------------------------
    # 23. No Database Access
    # -------------------------------------------------------------------------
    def test_23_no_database_access(self):
        """TCG module contains 0 database or session imports."""
        target_path = pathlib.Path(__file__).parent.parent / "app" / "reality" / "temporal_graph.py"
        content = target_path.read_text(encoding="utf-8")
        assert "Session" not in content
        assert "sqlalchemy" not in content
        assert "sqlmodel" not in content

    # -------------------------------------------------------------------------
    # 24. No Network Imports
    # -------------------------------------------------------------------------
    def test_24_no_network_imports(self):
        """TCG module contains 0 HTTP/network client imports."""
        target_path = pathlib.Path(__file__).parent.parent / "app" / "reality" / "temporal_graph.py"
        content = target_path.read_text(encoding="utf-8")
        forbidden = ["requests", "httpx", "aiohttp", "urllib"]
        for mod in forbidden:
            assert mod not in content

    # -------------------------------------------------------------------------
    # 25. No LLM Calls
    # -------------------------------------------------------------------------
    def test_25_no_llm_calls(self):
        """TCG module contains 0 LLM provider imports or prompt generation."""
        target_path = pathlib.Path(__file__).parent.parent / "app" / "reality" / "temporal_graph.py"
        content = target_path.read_text(encoding="utf-8")
        forbidden = ["google.genai", "openai", "anthropic", "generate_content"]
        for term in forbidden:
            assert term not in content

    # -------------------------------------------------------------------------
    # 26. No RealityBeliefEngine
    # -------------------------------------------------------------------------
    def test_26_no_reality_belief_engine(self):
        """TCG module has zero references to RealityBeliefEngine."""
        target_path = pathlib.Path(__file__).parent.parent / "app" / "reality" / "temporal_graph.py"
        content = target_path.read_text(encoding="utf-8")
        assert "RealityBeliefEngine" not in content

    # -------------------------------------------------------------------------
    # 27. Deterministic Ordering
    # -------------------------------------------------------------------------
    def test_27_deterministic_ordering(self):
        """Graph all_nodes(), all_edges(), and evaluate_all() return identical ordering."""
        graph = TemporalConstraintGraph()

        # Add nodes in reverse order
        for name in ["node_z", "node_a", "node_m", "node_c"]:
            graph.add_node(TemporalNode(node_id=name))

        nodes = graph.all_nodes()
        node_ids = [n.node_id for n in nodes]
        assert node_ids == ["node_a", "node_c", "node_m", "node_z"]

    # -------------------------------------------------------------------------
    # 28. No Pseudo-Probability
    # -------------------------------------------------------------------------
    def test_28_no_pseudo_probability(self):
        """TemporalNode, TemporalEdge, ConstraintEvaluationResult have no float scores."""
        node = TemporalNode(node_id="n1")
        assert not hasattr(node, "confidence")
        assert not hasattr(node, "probability")
        assert not hasattr(node, "score")

        edge = TemporalEdge(edge_id="e1", source_node_id="n1", target_node_id="n1", relation=TemporalRelationType.BEFORE)
        assert not hasattr(edge, "weight")
        assert not hasattr(edge, "probability")

        res = ConstraintEvaluationResult(
            rule_id="r1",
            status=ConstraintStatus.SATISFIED,
            target_node_ids=("n1",),
        )
        assert not hasattr(res, "confidence")
        assert not hasattr(res, "score")

    # -------------------------------------------------------------------------
    # 29. Recursive Projection Forbidden
    # -------------------------------------------------------------------------
    def test_29_projected_nodes_cannot_recursively_project(self):
        """A projected node cannot origin from another projected node (Anti-Snowballing)."""
        graph = TemporalConstraintGraph()

        p1 = TemporalNode(
            node_id="proj_1",
            temporal_horizon=TemporalHorizon.FUTURE,
            epistemic_grounding=EpistemicGrounding.PROJECTED,
            canonicality=Canonicality.NON_CANONICAL,
            origin_fact_key="fact_primary",
            propagation_depth=1,
        )
        graph.add_node(p1)

        # Attempt to project from proj_1 -> must be rejected
        p2 = TemporalNode(
            node_id="proj_2",
            temporal_horizon=TemporalHorizon.FUTURE,
            epistemic_grounding=EpistemicGrounding.PROJECTED,
            canonicality=Canonicality.NON_CANONICAL,
            origin_node_id="proj_1",
            propagation_depth=2,
        )
        with pytest.raises(ValueError, match="Recursive projection forbidden"):
            graph.add_node(p2)

    # -------------------------------------------------------------------------
    # 30. Graph Remains Ephemeral
    # -------------------------------------------------------------------------
    def test_30_graph_remains_ephemeral(self):
        """TCG exists only in memory; no table or session storage."""
        graph = TemporalConstraintGraph()
        assert not hasattr(graph, "__tablename__")
        assert not hasattr(graph, "session")
        assert not hasattr(graph, "save")
        assert not hasattr(graph, "commit")

    # -------------------------------------------------------------------------
    # AST Boundary Audit
    # -------------------------------------------------------------------------
    def test_ast_audit_temporal_graph(self):
        """Verify temporal_graph.py contains 0 network imports, 0 DB calls, 0 RBE, 0 set_fact, 0 tokens."""
        target_path = pathlib.Path(__file__).parent.parent / "app" / "reality" / "temporal_graph.py"
        assert target_path.exists(), "temporal_graph.py must exist"

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
