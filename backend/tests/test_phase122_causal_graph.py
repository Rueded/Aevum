"""test_phase122_causal_graph.py — Dedicated Unit Tests for Phase 12.2 Causal Explanation Graph Engine.

Governed by ADR-023:
1. Lock A (Causal DAG Scope): Constrains the Canonical Causal Explanation Graph to be an acyclic DAG.
2. Lock B (Cycle Detection): Full multi-hop cycle detection (A -> B -> C -> A) raising CausalCycleDetectedError.
3. Lock C (No Causal Invention): Pure graph derivation engine with zero mutation authority (0 set_fact, 0 token).
4. Lock D (UNKNOWN remains UNKNOWN): If causal_state == UNKNOWN, strictly returns ungrounded path.
5. Lock E (No Second Reality System): Zero duplicate reality ledgers or clocks.
6. Lock F (Scope Segregation): Strict segregation between personal history and shared history.
"""

from __future__ import annotations

import ast
import pathlib
import pytest
from pydantic import ValidationError

from app.biography.biography_models import (
    BiographicalDomain,
    BiographicalFact,
    CanonicalStatus,
    CausalKnowledgeState,
    CausalRelation,
    CausalRelationType,
    HistoryScope,
    LifeEra,
    LifeEventRecord,
    PersonalPreference,
    PreferenceAffinity,
    QualiaAnchor,
    RecallLevel,
    SocialContactRecord,
)
from app.biography.causal_graph import (
    CausalCycleDetectedError,
    CausalExplanationGraph,
    CausalNode,
    CausalNodeNotFoundError,
    CausalNodeType,
)
from app.biography.life_event_service import LifeEventService


class TestCausalDAGAndCycleDetection:
    """Verifies Lock A & Lock B: Acyclic DAG constraints and multi-hop cycle detection."""

    def test_node_addition_and_retrieval(self) -> None:
        graph = CausalExplanationGraph()
        node = CausalNode(
            node_id="evt-001",
            node_type=CausalNodeType.EVENT,
            label="First Python Code",
            domain=BiographicalDomain.PASSION_AND_DISCIPLINE,
            era=LifeEra.SECONDARY_SCHOOL,
        )
        graph.add_node(node)
        assert graph.node_count == 1
        assert graph.get_node("evt-001") == node

    def test_missing_node_raises_causal_node_not_found(self) -> None:
        graph = CausalExplanationGraph()
        rel = CausalRelation(
            relation_id="rel-ghost",
            source_id="nonexistent-src",
            target_id="nonexistent-tgt",
            relation_type=CausalRelationType.ORIGINATED_FROM,
            narrative_summary="Ghost link",
        )
        with pytest.raises(CausalNodeNotFoundError, match="Source node 'nonexistent-src' is not registered"):
            graph.add_relation(rel)

    def test_2_hop_cycle_detection(self) -> None:
        """Lock B: A -> B -> A cycle is detected and rejected."""
        graph = CausalExplanationGraph()
        n1 = CausalNode(node_id="n1", node_type=CausalNodeType.EVENT, label="N1", domain=BiographicalDomain.PASSION_AND_DISCIPLINE)
        n2 = CausalNode(node_id="n2", node_type=CausalNodeType.EVENT, label="N2", domain=BiographicalDomain.PASSION_AND_DISCIPLINE)
        graph.add_node(n1)
        graph.add_node(n2)

        r1 = CausalRelation(relation_id="r1", source_id="n1", target_id="n2", relation_type=CausalRelationType.ORIGINATED_FROM, narrative_summary="1 to 2")
        graph.add_relation(r1)

        # Attempt to add n2 -> n1
        r2 = CausalRelation(relation_id="r2", source_id="n2", target_id="n1", relation_type=CausalRelationType.CATALYZED_BY, narrative_summary="2 to 1")
        with pytest.raises(CausalCycleDetectedError, match="Causal cycle detected.*n2 -> n1"):
            graph.add_relation(r2)

    def test_3_hop_cycle_detection(self) -> None:
        """Lock B: A -> B -> C -> A cycle is detected and rejected."""
        graph = CausalExplanationGraph()
        for nid in ["a", "b", "c"]:
            graph.add_node(CausalNode(node_id=nid, node_type=CausalNodeType.EVENT, label=nid, domain=BiographicalDomain.PASSION_AND_DISCIPLINE))

        graph.add_relation(CausalRelation(relation_id="r_ab", source_id="a", target_id="b", relation_type=CausalRelationType.ORIGINATED_FROM, narrative_summary="a to b"))
        graph.add_relation(CausalRelation(relation_id="r_bc", source_id="b", target_id="c", relation_type=CausalRelationType.CONDITIONED_BY, narrative_summary="b to c"))

        # Attempt to add c -> a
        r_ca = CausalRelation(relation_id="r_ca", source_id="c", target_id="a", relation_type=CausalRelationType.MOTIVATED_BY, narrative_summary="c to a")
        with pytest.raises(CausalCycleDetectedError, match="Causal cycle detected.*c -> a"):
            graph.add_relation(r_ca)

    def test_complex_multi_branch_cycle_detection(self) -> None:
        """Lock B: Branching graph A -> B -> C -> D, adding D -> B is rejected."""
        graph = CausalExplanationGraph()
        for nid in ["a", "b", "c", "d", "e"]:
            graph.add_node(CausalNode(node_id=nid, node_type=CausalNodeType.EVENT, label=nid, domain=BiographicalDomain.PASSION_AND_DISCIPLINE))

        graph.add_relation(CausalRelation(relation_id="r1", source_id="a", target_id="b", relation_type=CausalRelationType.ORIGINATED_FROM, narrative_summary="a to b"))
        graph.add_relation(CausalRelation(relation_id="r2", source_id="b", target_id="c", relation_type=CausalRelationType.CATALYZED_BY, narrative_summary="b to c"))
        graph.add_relation(CausalRelation(relation_id="r3", source_id="c", target_id="d", relation_type=CausalRelationType.CONDITIONED_BY, narrative_summary="c to d"))
        graph.add_relation(CausalRelation(relation_id="r4", source_id="a", target_id="e", relation_type=CausalRelationType.ORIGINATED_FROM, narrative_summary="a to e"))

        # d -> b creates cycle b -> c -> d -> b
        with pytest.raises(CausalCycleDetectedError, match="Causal cycle detected.*d -> b"):
            graph.add_relation(CausalRelation(relation_id="r_cycle", source_id="d", target_id="b", relation_type=CausalRelationType.MOTIVATED_BY, narrative_summary="d to b"))

    def test_valid_diamond_dag_passes(self) -> None:
        """A diamond DAG (A -> B, A -> C, B -> D, C -> D) is valid and acyclic."""
        graph = CausalExplanationGraph()
        for nid in ["a", "b", "c", "d"]:
            graph.add_node(CausalNode(node_id=nid, node_type=CausalNodeType.EVENT, label=nid, domain=BiographicalDomain.PASSION_AND_DISCIPLINE))

        graph.add_relation(CausalRelation(relation_id="r_ab", source_id="a", target_id="b", relation_type=CausalRelationType.ORIGINATED_FROM, narrative_summary="a to b"))
        graph.add_relation(CausalRelation(relation_id="r_ac", source_id="a", target_id="c", relation_type=CausalRelationType.CATALYZED_BY, narrative_summary="a to c"))
        graph.add_relation(CausalRelation(relation_id="r_bd", source_id="b", target_id="d", relation_type=CausalRelationType.CONDITIONED_BY, narrative_summary="b to d"))
        graph.add_relation(CausalRelation(relation_id="r_cd", source_id="c", target_id="d", relation_type=CausalRelationType.MOTIVATED_BY, narrative_summary="c to d"))

        assert graph.relation_count == 4
        topo = graph.topological_sort()
        assert topo[0] == "a"
        assert topo[-1] == "d"


class TestCausalDerivationTraversal:
    """Verifies forward and backward traversals in the explanation graph."""

    def test_backward_causal_chain(self) -> None:
        """Traces back from a target preference to its antecedent events."""
        graph = CausalExplanationGraph()
        for nid in ["root_spark", "hobby_dev", "pref_systems"]:
            graph.add_node(CausalNode(node_id=nid, node_type=CausalNodeType.EVENT, label=nid, domain=BiographicalDomain.PASSION_AND_DISCIPLINE))

        graph.add_relation(CausalRelation(relation_id="r1", source_id="root_spark", target_id="hobby_dev", relation_type=CausalRelationType.ORIGINATED_FROM, narrative_summary="spark led to hobby"))
        graph.add_relation(CausalRelation(relation_id="r2", source_id="hobby_dev", target_id="pref_systems", relation_type=CausalRelationType.CONDITIONED_BY, narrative_summary="hobby led to preference"))

        chain = graph.get_causal_chain("pref_systems")
        assert len(chain) == 2
        assert chain[0].source_id == "root_spark"
        assert chain[0].target_id == "hobby_dev"
        assert chain[1].source_id == "hobby_dev"
        assert chain[1].target_id == "pref_systems"

    def test_root_causes_discovery(self) -> None:
        """Finds in-degree 0 ancestors."""
        graph = CausalExplanationGraph()
        for nid in ["cause_1", "cause_2", "intermediate", "final_target"]:
            graph.add_node(CausalNode(node_id=nid, node_type=CausalNodeType.EVENT, label=nid, domain=BiographicalDomain.PASSION_AND_DISCIPLINE))

        graph.add_relation(CausalRelation(relation_id="r1", source_id="cause_1", target_id="intermediate", relation_type=CausalRelationType.ORIGINATED_FROM, narrative_summary="1 to int"))
        graph.add_relation(CausalRelation(relation_id="r2", source_id="cause_2", target_id="intermediate", relation_type=CausalRelationType.CATALYZED_BY, narrative_summary="2 to int"))
        graph.add_relation(CausalRelation(relation_id="r3", source_id="intermediate", target_id="final_target", relation_type=CausalRelationType.MOTIVATED_BY, narrative_summary="int to target"))

        roots = graph.get_root_causes("final_target")
        assert roots == ["cause_1", "cause_2"]

    def test_downstream_consequences_traversal(self) -> None:
        """Finds downstream consequences stemming from a pivotal event."""
        graph = CausalExplanationGraph()
        for nid in ["spark", "effect_1", "effect_2"]:
            graph.add_node(CausalNode(node_id=nid, node_type=CausalNodeType.EVENT, label=nid, domain=BiographicalDomain.PASSION_AND_DISCIPLINE))

        graph.add_relation(CausalRelation(relation_id="r1", source_id="spark", target_id="effect_1", relation_type=CausalRelationType.ORIGINATED_FROM, narrative_summary="spark to effect 1"))
        graph.add_relation(CausalRelation(relation_id="r2", source_id="spark", target_id="effect_2", relation_type=CausalRelationType.CATALYZED_BY, narrative_summary="spark to effect 2"))

        effects = graph.get_downstream_effects("spark")
        assert len(effects) == 2
        target_ids = {e.target_id for e in effects}
        assert target_ids == {"effect_1", "effect_2"}


class TestLockDUnknownSemanticState:
    """Verifies Lock D: CausalKnowledgeState.UNKNOWN is strictly preserved without fabrication."""

    def test_unknown_preference_returns_ungrounded_explanation(self) -> None:
        graph = CausalExplanationGraph()
        pref = PersonalPreference(
            preference_id="pref-black-tea",
            category="beverage",
            object_name="black tea",
            affinity=PreferenceAffinity.FAVORITE,
            era_acquired=LifeEra.SECONDARY_SCHOOL,
            causal_state=CausalKnowledgeState.UNKNOWN,
            causal_relation_id=None,
        )
        graph.add_node_from_preference(pref)

        path = graph.explain_preference(pref)
        assert path.target_id == "pref-black-tea"
        assert path.causal_state == CausalKnowledgeState.UNKNOWN
        assert path.is_grounded is False
        assert path.steps == []
        assert path.root_cause_ids == []
        assert path.terminal_reason == "UNKNOWN"

    def test_known_preference_returns_grounded_explanation(self) -> None:
        graph = CausalExplanationGraph()
        event = LifeEventRecord(
            event_id="evt-coding-spark",
            scope=HistoryScope.AEVUM_PERSONAL,
            era=LifeEra.SECONDARY_SCHOOL,
            domain=BiographicalDomain.PASSION_AND_DISCIPLINE,
            headline="Built text adventure game in Python",
            summary="Spent school holiday writing text RPG engine",
        )
        pref = PersonalPreference(
            preference_id="pref-systems-prog",
            category="computing",
            object_name="Rust & Systems Programming",
            affinity=PreferenceAffinity.FAVORITE,
            era_acquired=LifeEra.UNIVERSITY,
            causal_state=CausalKnowledgeState.KNOWN,
            causal_relation_id="rel-spark-to-systems",
        )
        graph.add_node_from_event(event)
        graph.add_node_from_preference(pref)

        rel = CausalRelation(
            relation_id="rel-spark-to-systems",
            source_id="evt-coding-spark",
            target_id="pref-systems-prog",
            relation_type=CausalRelationType.ORIGINATED_FROM,
            narrative_summary="First text game sparked deep interest in system mechanics",
        )
        graph.add_relation(rel)

        path = graph.explain_preference(pref)
        assert path.target_id == "pref-systems-prog"
        assert path.causal_state == CausalKnowledgeState.KNOWN
        assert path.is_grounded is True
        assert len(path.steps) == 1
        assert path.steps[0].source_id == "evt-coding-spark"
        assert path.root_cause_ids == ["evt-coding-spark"]
        assert path.terminal_reason == "EXPLAINED"


class TestLifeEventServiceOrchestration:
    """Verifies LifeEventService query orchestration, domain filtering, and scope segregation (Lock F)."""

    def test_era_and_scope_filtering(self) -> None:
        service = LifeEventService()

        # 1. Primary school personal event
        e1 = LifeEventRecord(
            event_id="e1",
            scope=HistoryScope.AEVUM_PERSONAL,
            era=LifeEra.PRIMARY_SCHOOL,
            domain=BiographicalDomain.EDUCATION_AND_GROWTH,
            headline="Primary school event",
            summary="Summary 1",
        )
        # 2. Secondary school personal event
        e2 = LifeEventRecord(
            event_id="e2",
            scope=HistoryScope.AEVUM_PERSONAL,
            era=LifeEra.SECONDARY_SCHOOL,
            domain=BiographicalDomain.EDUCATION_AND_GROWTH,
            headline="Secondary school event",
            summary="Summary 2",
        )
        # 3. University shared episode
        e3 = LifeEventRecord(
            event_id="e3",
            scope=HistoryScope.SHARED_WITH_USER,
            era=LifeEra.UNIVERSITY,
            domain=BiographicalDomain.SHARED_USER_JOURNEY,
            headline="Shared journey episode",
            summary="Summary 3",
            user_present=True,
            session_anchor="sess-001",
        )

        service.register_life_event(e1)
        service.register_life_event(e2)
        service.register_life_event(e3)

        # Era filtering for primary school personal
        primary_personal = service.get_life_events_by_era(LifeEra.PRIMARY_SCHOOL, scope=HistoryScope.AEVUM_PERSONAL)
        assert len(primary_personal) == 1
        assert primary_personal[0].event_id == "e1"

        # Scope segregation: querying personal history at UNIVERSITY returns 0 (since e3 is shared)
        uni_personal = service.get_life_events_by_era(LifeEra.UNIVERSITY, scope=HistoryScope.AEVUM_PERSONAL)
        assert len(uni_personal) == 0

        # Querying shared history at UNIVERSITY returns e3
        uni_shared = service.get_life_events_by_era(LifeEra.UNIVERSITY, scope=HistoryScope.SHARED_WITH_USER)
        assert len(uni_shared) == 1
        assert uni_shared[0].event_id == "e3"

    def test_qualia_association_and_retrieval(self) -> None:
        service = LifeEventService()
        qualia = QualiaAnchor(
            qualia_id="q-kettle",
            sensory_modality="auditory",
            description="High-pitched whistle of the vintage brass kettle",
            emotional_coloring="comforting",
        )
        service.register_qualia(qualia)

        event = LifeEventRecord(
            event_id="evt-tea-memory",
            scope=HistoryScope.AEVUM_PERSONAL,
            era=LifeEra.PRIMARY_SCHOOL,
            domain=BiographicalDomain.LIFESTYLE_AND_RHYTHM,
            headline="Tea brewing on Saturday mornings",
            summary="Brewing tea with grandfather",
            qualia_ids=["q-kettle"],
        )
        service.register_life_event(event)

        retrieved_qualia = service.get_qualia_for_event("evt-tea-memory")
        assert len(retrieved_qualia) == 1
        assert retrieved_qualia[0].description == "High-pitched whistle of the vintage brass kettle"

    def test_service_level_preference_explanation_unknown(self) -> None:
        service = LifeEventService()
        pref = PersonalPreference(
            preference_id="pref-coffee",
            category="beverage",
            object_name="Iced Americano",
            affinity=PreferenceAffinity.ENJOYS,
            era_acquired=LifeEra.UNIVERSITY,
            causal_state=CausalKnowledgeState.UNKNOWN,
            causal_relation_id=None,
        )
        service.register_preference(pref)

        path = service.explain_preference("pref-coffee")
        assert path.causal_state == CausalKnowledgeState.UNKNOWN
        assert path.is_grounded is False
        assert path.terminal_reason == "UNKNOWN"


class TestFullGroundedPersonalHistoryWalkthrough:
    """End-to-end integration: High school spark -> Mentor advice -> University preference."""

    def test_complete_causal_life_graph_derivation(self) -> None:
        service = LifeEventService()

        # 1. High school life event: Spark event
        spark_event = LifeEventRecord(
            event_id="evt-game-spark",
            scope=HistoryScope.AEVUM_PERSONAL,
            era=LifeEra.SECONDARY_SCHOOL,
            domain=BiographicalDomain.PASSION_AND_DISCIPLINE,
            headline="Created first CLI adventure game in Python",
            summary="Built a branching dialogue game during school holidays",
        )
        service.register_life_event(spark_event)

        # 2. Mentor contact & encouragement event
        mentor = SocialContactRecord(
            contact_id="contact-teacher-lee",
            display_name="Mr. Lee",
            relation_role="high_school_math_teacher",
            era_first_met=LifeEra.SECONDARY_SCHOOL,
            scope=HistoryScope.AEVUM_PERSONAL,
            is_user=False,
        )
        service.register_contact(mentor)

        encouragement_fact = BiographicalFact(
            fact_id="fact-mentor-advice",
            domain=BiographicalDomain.EDUCATION_AND_GROWTH,
            attribute_key="mentor_recommendation",
            attribute_value="Advised pursuing Software Engineering at university",
            era=LifeEra.SECONDARY_SCHOOL,
            provenance="seed_canon",
            valid_from_era=LifeEra.SECONDARY_SCHOOL,
        )
        service.register_fact(encouragement_fact)

        # 3. University preference & major
        cs_major_fact = BiographicalFact(
            fact_id="fact-usm-cs",
            domain=BiographicalDomain.EDUCATION_AND_GROWTH,
            attribute_key="academic_program",
            attribute_value="Bachelor of Software Engineering, USM",
            era=LifeEra.UNIVERSITY,
            provenance="seed_canon",
            valid_from_era=LifeEra.UNIVERSITY,
        )
        service.register_fact(cs_major_fact)

        systems_pref = PersonalPreference(
            preference_id="pref-low-level",
            category="computing",
            object_name="Operating Systems and Memory Concurrency",
            affinity=PreferenceAffinity.FAVORITE,
            era_acquired=LifeEra.UNIVERSITY,
            causal_state=CausalKnowledgeState.KNOWN,
            causal_relation_id="rel-game-to-pref",
        )
        service.register_preference(systems_pref)

        # 4. Link causal relations
        # spark_event -> systems_pref
        r1 = CausalRelation(
            relation_id="rel-game-to-pref",
            source_id="evt-game-spark",
            target_id="pref-low-level",
            relation_type=CausalRelationType.ORIGINATED_FROM,
            narrative_summary="First text game sparked fascination with memory allocation",
        )
        service.link_causal_relation(r1)

        # mentor_advice -> cs_major_fact
        r2 = CausalRelation(
            relation_id="rel-mentor-to-major",
            source_id="fact-mentor-advice",
            target_id="fact-usm-cs",
            relation_type=CausalRelationType.MOTIVATED_BY,
            narrative_summary="Mr. Lee's guidance directly influenced choosing USM Software Engineering",
        )
        service.link_causal_relation(r2)

        # Verify derivation for preference
        pref_explanation = service.explain_preference("pref-low-level")
        assert pref_explanation.is_grounded is True
        assert pref_explanation.root_cause_ids == ["evt-game-spark"]
        assert len(pref_explanation.steps) == 1
        assert pref_explanation.steps[0].relation_type == CausalRelationType.ORIGINATED_FROM

        # Verify derivation for major fact
        major_chain = service.get_causal_chain("fact-usm-cs")
        assert len(major_chain) == 1
        assert major_chain[0].source_id == "fact-mentor-advice"
        assert major_chain[0].relation_type == CausalRelationType.MOTIVATED_BY

        # Verify downstream consequences of the game spark
        consequences = service.get_event_causal_consequences("evt-game-spark")
        assert len(consequences) == 1
        assert consequences[0].target_id == "pref-low-level"


class TestASTConstitutionalBoundaryAudit:
    """Pure static AST boundary audit verifying zero DB, LLM, network, or mutation leaks in 12.2."""

    def test_causal_graph_ast_purity(self) -> None:
        target_files = [
            pathlib.Path("app/biography/causal_graph.py"),
            pathlib.Path("app/biography/life_event_service.py"),
        ]

        forbidden_import_modules = [
            "sqlalchemy",
            "sqlite3",
            "database",
            "db",
            "llm",
            "google",
            "google.genai",
            "openai",
            "requests",
            "httpx",
            "urllib",
            "aiohttp",
        ]

        forbidden_name_tokens = [
            "promotionauthorizationtoken",
            "set_fact",
            "execute_query",
            "session.commit",
            "db_session",
            "cursor.execute",
        ]

        for tf in target_files:
            assert tf.exists(), f"File {tf} must exist"
            source = tf.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(tf))

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for forbidden in forbidden_import_modules:
                            assert forbidden not in alias.name.lower(), (
                                f"Illegal import module '{alias.name}' in {tf}"
                            )
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    for forbidden in forbidden_import_modules:
                        assert forbidden not in mod.lower(), (
                            f"Illegal from-import module '{mod}' in {tf}"
                        )
                elif isinstance(node, ast.Name):
                    for forbidden in forbidden_name_tokens:
                        assert forbidden not in node.id.lower(), (
                            f"Illegal token '{node.id}' in {tf}"
                        )

            # Confirm zero float type annotations
            for node in ast.walk(tree):
                if isinstance(node, ast.AnnAssign):
                    target_str = ast.unparse(node.annotation).lower()
                    assert "float" not in target_str, (
                        f"Illegal float annotation '{target_str}' in {tf}"
                    )
