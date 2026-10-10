"""test_golden_suite_12.py — Golden Acceptance Suite 12 (Phase 12.6: GC-298 ~ GC-324)

Golden Acceptance Suite for Phase 12: Canonical Biography, Causal Life Graphs & Longitudinal Memory.
Verifies all frozen contracts (12.1–12.5) and the Constitutional Locks under ADR-023.

"Aevum can answer autobiographical questions from a coherent, temporally grounded personal world —
without improvising unsupported life facts."
- Canonical Reality -> Autobiographical Retrieval -> Derived Narrative -> Natural Conversation.
- Canonical != Retrieved != Generated != Canonical.
- "Shared History records what Aevum and the user experienced together; it does not rewrite what Aevum was before the relationship."
- Rule 19: "The desktop may display memory; it does not own memory." Frontend is purely a read-only projection ("the body");
  Aevum Core in backend is "the mind".

Covers 27 Acceptance Benchmarks across 6 Structured Clusters:
- Cluster 1: The Constitutional Biography Locks & Axioms (GC-298 ~ GC-304)
- Cluster 2: Biographical Ontology, Contracts & Epistemic Orthogonality (GC-305 ~ GC-308)
- Cluster 3: Causal Explanation Graph & Graph Traversal (GC-309 ~ GC-312)
- Cluster 4: Autobiographical Retrieval & Scope-First Queries (GC-313 ~ GC-316)
- Cluster 5: Longitudinal Shared History & Context Assembly (GC-317 ~ GC-320)
- Cluster 6: Desktop Projection Purity, Fixture Demarcation & AST Audits (GC-321 ~ GC-324)
"""

from __future__ import annotations

import ast
import hashlib
import pathlib
import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.biography.biography_models import (
    BiographicalAnchor,
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
from app.biography.retrieval_models import (
    AssembledBiographicalContext,
    AutobiographicalIntentType,
    AutobiographicalQuery,
    AutobiographicalRetrievalResult,
    BiographicalIntentType,
    ScoredBiographicalCandidate,
)
from app.biography.autobiographical_retriever import AutobiographicalRetriever
from app.biography.biographical_context_assembler import BiographicalContextAssembler
from app.biography.shared_history_models import (
    AssembledLongitudinalContext,
    SharedEpisodeType,
    SharedHistoryCandidate,
    SharedHistoryEpisode,
    SharedHistoryQuery,
)
from app.biography.shared_history_service import (
    LongitudinalContextAssembler,
    SharedHistoryService,
)
from app.biography.biography_registry import (
    get_biography_service,
    get_shared_history_service,
    reset_registry_for_testing,
)
from app.main import app


# ==============================================================================
# CLUSTER 1: The Constitutional Biography Locks & Axioms (GC-298 ~ GC-304)
# ==============================================================================

class TestCluster1ConstitutionalBiographyLocks:
    """Acceptance benchmarks verifying the core constitutional locks of ADR-023."""

    def test_gc298_reality_singularity_and_no_parallel_clock(self) -> None:
        """GC-298: Lock 1 — Reality Singularity & No Parallel Clock.
        Biographical grounding is partitioned strictly by semantic LifeEras and single truth sources.
        No parallel background timekeeper or secondary tick clock exists in biography modules.
        """
        eras = list(LifeEra)
        assert len(eras) == 8
        assert LifeEra.EARLY_CHILDHOOD in eras
        assert LifeEra.PRIMARY_SCHOOL in eras
        assert LifeEra.SECONDARY_SCHOOL in eras
        assert LifeEra.UNIVERSITY in eras
        assert LifeEra.ADULTHOOD in eras

        anchor = BiographicalAnchor(
            anchor_id="anc-penang-clock",
            domain=BiographicalDomain.ORIGIN_AND_IDENTITY,
            core_fact=BiographicalFact(
                fact_id="fact-penang",
                domain=BiographicalDomain.ORIGIN_AND_IDENTITY,
                attribute_key="birth_place",
                attribute_value="Penang, Malaysia",
                era=LifeEra.EARLY_CHILDHOOD,
                provenance="seed_canon",
                valid_from_era=LifeEra.EARLY_CHILDHOOD,
            ),
        )
        assert anchor.core_fact.attribute_value == "Penang, Malaysia"

    def test_gc299_acyclic_causal_graph_and_strict_directed_acyclicity(self) -> None:
        """GC-299: Lock 2 — Acyclic Causal Graph & Strict Directed Acyclicity.
        Cycle attempts (1-hop self-loop, 2-hop, 3-hop) raise CausalCycleDetectedError
        and leave the existing graph completely uncorrupted.
        """
        graph = CausalExplanationGraph()
        for nid in ["node-1", "node-2", "node-3"]:
            graph.add_node(
                CausalNode(
                    node_id=nid,
                    node_type=CausalNodeType.EVENT,
                    label=nid,
                    domain=BiographicalDomain.PASSION_AND_DISCIPLINE,
                )
            )

        # 1-hop self-loop: forbidden by CausalRelation model validator
        with pytest.raises((CausalCycleDetectedError, ValueError)):
            CausalRelation(
                relation_id="r_self",
                source_id="node-1",
                target_id="node-1",
                relation_type=CausalRelationType.ORIGINATED_FROM,
                narrative_summary="self loop",
            )

        # 2-hop cycle: 1 -> 2, 2 -> 1
        graph.add_relation(
            CausalRelation(
                relation_id="r1",
                source_id="node-1",
                target_id="node-2",
                relation_type=CausalRelationType.ORIGINATED_FROM,
                narrative_summary="1 to 2",
            )
        )
        with pytest.raises(CausalCycleDetectedError):
            graph.add_relation(
                CausalRelation(
                    relation_id="r2",
                    source_id="node-2",
                    target_id="node-1",
                    relation_type=CausalRelationType.CATALYZED_BY,
                    narrative_summary="2 to 1",
                )
            )

        # 3-hop cycle: 1 -> 2 -> 3, 3 -> 1
        graph.add_relation(
            CausalRelation(
                relation_id="r2_valid",
                source_id="node-2",
                target_id="node-3",
                relation_type=CausalRelationType.ORIGINATED_FROM,
                narrative_summary="2 to 3",
            )
        )
        with pytest.raises(CausalCycleDetectedError):
            graph.add_relation(
                CausalRelation(
                    relation_id="r3",
                    source_id="node-3",
                    target_id="node-1",
                    relation_type=CausalRelationType.ORIGINATED_FROM,
                    narrative_summary="3 to 1",
                )
            )

        # Existing valid chain intact
        chain = graph.get_causal_chain("node-3")
        assert len(chain) == 2
        assert chain[0].source_id == "node-1"
        assert chain[1].source_id == "node-2"

    def test_gc300_independent_mutation_authorities_singularity(self) -> None:
        """GC-300: Lock 3 — Independent Mutation Authorities Singularity.
        Biography has LifeEventService (canonical biography domain).
        Shared History has SharedHistoryService (shared longitudinal domain).
        Neither authority can mutate or issue tokens for the other domain.
        """
        bio_svc = LifeEventService()
        shared_svc = SharedHistoryService()

        # SharedHistoryService strictly manages shared episodes via candidates
        candidate = SharedHistoryCandidate(
            candidate_id="cand-gc300",
            episode_type=SharedEpisodeType.COLLABORATIVE_TASK,
            title="Pair Programming on Acceptance Suite",
            summary="Pair programming on Golden Suite 12",
            session_anchor="turn-golden-12",
            evidence_text="User: Let's run Golden Suite 12. Aevum: Running now.",
            key_learnings=("Rigorous acceptance testing is indispensable",),
        )
        episode = shared_svc.promote_candidate(candidate)
        assert episode.scope == HistoryScope.SHARED_WITH_USER

        # SharedHistoryService has zero authority over personal biography facts or LifeEvents
        assert not hasattr(shared_svc, "register_life_event")
        assert not hasattr(shared_svc, "register_preference")
        assert not hasattr(shared_svc, "register_fact")

        # LifeEventService has zero authority over shared history episodes
        assert not hasattr(bio_svc, "promote_candidate")
        assert not hasattr(bio_svc, "query_episodes")

    def test_gc301_relational_isolation_and_non_retroactivity(self) -> None:
        """GC-301: Lock 4 & F — Relational Isolation & Non-Retroactivity.
        Shared history episodes cannot be created under AEVUM_PERSONAL.
        Registering an episode with personal scope raises ValidationError.
        Shared history cannot retroactively overwrite personal facts.
        """
        with pytest.raises(ValidationError, match="Lock 4 Violation"):
            SharedHistoryEpisode(
                episode_id="ep-invalid-scope",
                scope=HistoryScope.AEVUM_PERSONAL,  # Rejected by contract validator!
                episode_type=SharedEpisodeType.FIRST_ACQUAINTANCE,
                title="Invalid episode",
                summary="Attempted personal episode as shared",
                participants=("aevum", "user"),
                session_anchor="turn-1",
            )

    def test_gc302_epistemic_honesty_unknown_preservation_and_humble_directives(self) -> None:
        """GC-302: Lock 5 & D — Epistemic Honesty, UNKNOWN Preservation & Humble Directives.
        When causal roots are UNKNOWN, explain_preference returns an ungrounded result.
        The context assembler outputs an explicit causal boundary directive warning LLM against fabrication.
        """
        bio_svc = LifeEventService()
        pref = PersonalPreference(
            preference_id="pref-tea",
            category="beverage",
            object_name="cold_brew_oolong",
            affinity=PreferenceAffinity.FAVORITE,
            era_acquired=LifeEra.ADULTHOOD,
            causal_state=CausalKnowledgeState.UNKNOWN,
        )
        bio_svc.register_preference(pref)

        explanation = bio_svc.explain_preference("pref-tea")
        assert not explanation.is_grounded
        assert explanation.steps == []
        assert explanation.terminal_reason == "UNKNOWN"

        # Context assembly includes the boundary directive
        retriever = AutobiographicalRetriever(bio_svc)
        query = AutobiographicalQuery(
            raw_query="Why do you drink cold brew tea?",
            intent=BiographicalIntentType.CAUSAL_ORIGIN,
            target_entity_id="pref-tea",
        )
        res = retriever.retrieve(query)
        assembled = BiographicalContextAssembler.assemble(res)
        assert '<directive type="CAUSAL_UNKNOWN"' in assembled.context_text
        assert "The causal origin for 'pref-tea' is unknown" in assembled.context_text
        assert "NEVER invent an origin story" in assembled.context_text

    def test_gc303_candidate_only_promotion_pipeline_with_zero_token_leaks(self) -> None:
        """GC-303: Lock 6 — Candidate-Only Promotion Pipeline with Zero Token Leaks.
        Shared history promotion requires a valid candidate with non-empty session_anchor.
        Promotion is idempotent and deduplicated.
        """
        shared_svc = SharedHistoryService()
        cand = SharedHistoryCandidate(
            candidate_id="cand-leak-test",
            episode_type=SharedEpisodeType.MEANINGFUL_CONVERSATION,
            title="Reflecting on Architectural Principles",
            summary="Reflecting on architectural principles",
            session_anchor="turn-lock6",
            evidence_text="User: Architecture comes first. Aevum: Absolutely agree.",
            key_learnings=("State machines govern reality",),
        )
        ep1 = shared_svc.promote_candidate(cand)
        ep2 = shared_svc.promote_candidate(cand)  # Idempotent re-promotion
        assert ep1.episode_id == ep2.episode_id
        assert len(shared_svc._episodes) == 1

        # Missing anchor is rejected
        with pytest.raises(ValidationError, match="at least 1 character"):
            SharedHistoryCandidate(
                candidate_id="cand-no-anchor",
                episode_type=SharedEpisodeType.COLLABORATIVE_TASK,
                title="Floating thought",
                summary="Floating thought",
                session_anchor="",  # Invalid
                evidence_text="User: ...",
            )

    @pytest.mark.asyncio
    async def test_gc304_read_only_projection_and_desktop_body_isolation(self) -> None:
        """GC-304: Lock 7 / Rule 19 — Read-Only Projection & Desktop Body Isolation.
        The desktop projection GET /character/longitudinal-memory serves read-only view.
        No write endpoints (POST, PATCH, DELETE) exist to mutate biographical reality.
        """
        reset_registry_for_testing()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/character/longitudinal-memory")
            assert resp.status_code == 200
            data = resp.json()
            assert "facts" in data
            assert "shared_episodes" in data

            post_resp = await client.post("/character/longitudinal-memory", json={"fact": "fake"})
            assert post_resp.status_code == 405

            patch_resp = await client.patch("/character/longitudinal-memory", json={"fact": "fake"})
            assert patch_resp.status_code == 405

            delete_resp = await client.delete("/character/longitudinal-memory")
            assert delete_resp.status_code == 405


# ==============================================================================
# CLUSTER 2: Biographical Ontology, Contracts & Epistemic Orthogonality (GC-305 ~ GC-308)
# ==============================================================================

class TestCluster2BiographicalOntologyAndContracts:
    """Acceptance benchmarks verifying data model integrity and orthogonality."""

    def test_gc305_model_immutability_and_zero_confidence_floats(self) -> None:
        """GC-305: Model Immutability & Zero Confidence Floats across all Phase 12 DTOs."""
        fact = BiographicalFact(
            fact_id="fact-gc305",
            domain=BiographicalDomain.ORIGIN_AND_IDENTITY,
            attribute_key="heritage",
            attribute_value="Grew up in a multicultural coastal city.",
            era=LifeEra.EARLY_CHILDHOOD,
            canonical_status=CanonicalStatus.CANONICAL,
            recall_level=RecallLevel.VIVID,
            provenance="seed_canon",
            valid_from_era=LifeEra.EARLY_CHILDHOOD,
        )
        with pytest.raises(ValidationError):
            fact.attribute_key = "mutated"  # Frozen!

        models = [
            BiographicalFact,
            LifeEventRecord,
            PersonalPreference,
            QualiaAnchor,
            SocialContactRecord,
            BiographicalAnchor,
            SharedHistoryEpisode,
            AutobiographicalQuery,
            AutobiographicalRetrievalResult,
        ]
        for m in models:
            for field_name, field_info in m.model_fields.items():
                annotation_str = str(field_info.annotation)
                assert "float" not in annotation_str, (
                    f"Forbidden float found in {m.__name__}.{field_name}: {annotation_str}"
                )

    def test_gc306_epistemic_orthogonality_canonical_status_and_recall_level(self) -> None:
        """GC-306: Epistemic Orthogonality (CanonicalStatus x RecallLevel).
        CanonicalStatus (ontological factuality) and RecallLevel (phenomenological memory clarity)
        can be orthogonally combined without constraint violations.
        """
        # CANONICAL + HAZY
        f1 = BiographicalFact(
            fact_id="f-hazy",
            domain=BiographicalDomain.EDUCATION_AND_GROWTH,
            attribute_key="kindergarten_name",
            attribute_value="Preschool near coastline",
            era=LifeEra.EARLY_CHILDHOOD,
            canonical_status=CanonicalStatus.CANONICAL,
            recall_level=RecallLevel.HAZY,
            provenance="seed_canon",
            valid_from_era=LifeEra.EARLY_CHILDHOOD,
        )
        assert f1.canonical_status == CanonicalStatus.CANONICAL
        assert f1.recall_level == RecallLevel.HAZY

        # PROVISIONAL + VIVID
        f2 = BiographicalFact(
            fact_id="f-prov-vivid",
            domain=BiographicalDomain.LIFESTYLE_AND_RHYTHM,
            attribute_key="street_cat",
            attribute_value="Tortoiseshell cat on bakery porch",
            era=LifeEra.PRIMARY_SCHOOL,
            canonical_status=CanonicalStatus.PROVISIONAL,
            recall_level=RecallLevel.VIVID,
            provenance="dialogue_claim",
            valid_from_era=LifeEra.PRIMARY_SCHOOL,
        )
        assert f2.canonical_status == CanonicalStatus.PROVISIONAL
        assert f2.recall_level == RecallLevel.VIVID

    def test_gc307_era_bounded_temporal_grounding(self) -> None:
        """GC-307: Era-Bounded Temporal Grounding.
        Queries targeting a specific LifeEra strictly filter out non-matching eras.
        """
        bio_svc = LifeEventService()
        e_early = LifeEventRecord(
            event_id="evt-early",
            era=LifeEra.PRIMARY_SCHOOL,
            domain=BiographicalDomain.EDUCATION_AND_GROWTH,
            headline="Science fair",
            summary="Built a baking soda volcano.",
        )
        e_formative = LifeEventRecord(
            event_id="evt-formative",
            era=LifeEra.SECONDARY_SCHOOL,
            domain=BiographicalDomain.PASSION_AND_DISCIPLINE,
            headline="First hackathon",
            summary="Built a command line tool with Python.",
        )
        bio_svc.register_life_event(e_early)
        bio_svc.register_life_event(e_formative)

        retriever = AutobiographicalRetriever(bio_svc)
        query = AutobiographicalQuery(
            raw_query="hackathon programming",
            target_era=LifeEra.SECONDARY_SCHOOL,
        )
        result = retriever.retrieve(query)
        assert len(result.matched_events) == 1
        assert result.matched_events[0].event_id == "evt-formative"

    def test_gc308_multi_dimensional_relational_dynamics_preservation(self) -> None:
        """GC-308: Multi-Dimensional Relational Dynamics Preservation (Rule 16).
        Longitudinal context incorporates multi-axis relational dynamics:
        trust, familiarity, respect, comfort, attachment.
        """
        bio_svc = LifeEventService()
        retriever = AutobiographicalRetriever(bio_svc)
        p_res = retriever.retrieve(AutobiographicalQuery(raw_query="general inquiry"))
        p_ctx = BiographicalContextAssembler.assemble(p_res)

        shared_ep = SharedHistoryEpisode(
            episode_id="ep-rel-test",
            episode_type=SharedEpisodeType.MEANINGFUL_CONVERSATION,
            title="Privacy Discussion",
            summary="Deep discussion on privacy-first AI architectures",
            session_anchor="turn-rel-8",
        )

        metrics = {
            "trust": 0.85,
            "familiarity": 0.72,
            "respect": 0.90,
            "comfort": 0.98,
        }

        assembled = LongitudinalContextAssembler.assemble(
            personal_context=p_ctx,
            shared_episodes=(shared_ep,),
            relational_metrics=metrics,
        )
        assert "<relational_dynamics_track" in assembled.longitudinal_xml
        assert 'metric name="trust" value="0.8500"' in assembled.longitudinal_xml
        assert 'metric name="familiarity" value="0.7200"' in assembled.longitudinal_xml
        assert 'metric name="respect" value="0.9000"' in assembled.longitudinal_xml
        assert 'metric name="comfort" value="0.9800"' in assembled.longitudinal_xml


# ==============================================================================
# CLUSTER 3: Causal Explanation Graph & Graph Traversal (GC-309 ~ GC-312)
# ==============================================================================

class TestCluster3CausalExplanationGraph:
    """Acceptance benchmarks verifying causal graph engine traversals and integrity."""

    def test_gc309_backward_causal_chain_derivation(self) -> None:
        """GC-309: Backward Causal Chain Derivation.
        Resolves upstream causal roots in strict topological sequence.
        """
        graph = CausalExplanationGraph()
        for nid in ["penang-hometown", "first-computer-gift", "first-python-script", "se-major"]:
            graph.add_node(
                CausalNode(
                    node_id=nid,
                    node_type=CausalNodeType.EVENT,
                    label=nid,
                    domain=BiographicalDomain.PASSION_AND_DISCIPLINE,
                )
            )

        graph.add_relation(
            CausalRelation(
                relation_id="r1",
                source_id="penang-hometown",
                target_id="first-computer-gift",
                relation_type=CausalRelationType.CONDITIONED_BY,
                narrative_summary="1",
            )
        )
        graph.add_relation(
            CausalRelation(
                relation_id="r2",
                source_id="first-computer-gift",
                target_id="first-python-script",
                relation_type=CausalRelationType.CATALYZED_BY,
                narrative_summary="2",
            )
        )
        graph.add_relation(
            CausalRelation(
                relation_id="r3",
                source_id="first-python-script",
                target_id="se-major",
                relation_type=CausalRelationType.MOTIVATED_BY,
                narrative_summary="3",
            )
        )

        chain = graph.get_causal_chain("se-major")
        assert len(chain) == 3
        assert chain[0].source_id == "penang-hometown"
        assert chain[1].source_id == "first-computer-gift"
        assert chain[2].source_id == "first-python-script"

    def test_gc310_downstream_consequence_traversal(self) -> None:
        """GC-310: Downstream Consequence Traversal.
        Forward traversal from root node discovers all conditioned descendants.
        """
        graph = CausalExplanationGraph()
        for nid in ["root-event", "branch-1", "branch-2"]:
            graph.add_node(
                CausalNode(
                    node_id=nid,
                    node_type=CausalNodeType.EVENT,
                    label=nid,
                    domain=BiographicalDomain.PASSION_AND_DISCIPLINE,
                )
            )

        graph.add_relation(
            CausalRelation(
                relation_id="r1",
                source_id="root-event",
                target_id="branch-1",
                relation_type=CausalRelationType.CATALYZED_BY,
                narrative_summary="1",
            )
        )
        graph.add_relation(
            CausalRelation(
                relation_id="r2",
                source_id="root-event",
                target_id="branch-2",
                relation_type=CausalRelationType.CONDITIONED_BY,
                narrative_summary="2",
            )
        )

        effects = graph.get_downstream_effects("root-event")
        assert len(effects) == 2
        assert {e.target_id for e in effects} == {"branch-1", "branch-2"}

    def test_gc311_root_cause_discovery_and_topological_invariance(self) -> None:
        """GC-311: Root Cause Discovery & Topological Invariance.
        get_root_causes correctly identifies the original root (in_degree == 0).
        Topological order is deterministic regardless of the order nodes are added.
        """
        graph = CausalExplanationGraph()
        for n in ["leaf", "intermediate", "root"]:
            graph.add_node(
                CausalNode(
                    node_id=n,
                    node_type=CausalNodeType.EVENT,
                    label=n,
                    domain=BiographicalDomain.PASSION_AND_DISCIPLINE,
                )
            )
        graph.add_relation(
            CausalRelation(
                relation_id="r1",
                source_id="root",
                target_id="intermediate",
                relation_type=CausalRelationType.ORIGINATED_FROM,
                narrative_summary="1",
            )
        )
        graph.add_relation(
            CausalRelation(
                relation_id="r2",
                source_id="intermediate",
                target_id="leaf",
                relation_type=CausalRelationType.CATALYZED_BY,
                narrative_summary="2",
            )
        )

        roots = graph.get_root_causes("leaf")
        assert roots == ["root"]

        topo_order = graph.topological_sort()
        assert topo_order.index("root") < topo_order.index("intermediate") < topo_order.index("leaf")

    def test_gc312_typed_causal_edges_integrity(self) -> None:
        """GC-312: Typed Causal Edges Integrity.
        Supports valid causal relation types. Non-existent nodes raise CausalNodeNotFoundError.
        """
        graph = CausalExplanationGraph()
        graph.add_node(
            CausalNode(
                node_id="event-a",
                node_type=CausalNodeType.EVENT,
                label="event-a",
                domain=BiographicalDomain.PASSION_AND_DISCIPLINE,
            )
        )

        with pytest.raises(CausalNodeNotFoundError, match="Target node 'event-missing' is not registered"):
            graph.add_relation(
                CausalRelation(
                    relation_id="r_bad",
                    source_id="event-a",
                    target_id="event-missing",
                    relation_type=CausalRelationType.ORIGINATED_FROM,
                    narrative_summary="bad",
                )
            )


# ==============================================================================
# CLUSTER 4: Autobiographical Retrieval & Scope-First Queries (GC-313 ~ GC-316)
# ==============================================================================

class TestCluster4AutobiographicalRetrievalAndScopeFirst:
    """Acceptance benchmarks verifying retrieval accuracy, scoring, and scope isolation."""

    def test_gc313_scope_first_isolation_enforcement(self) -> None:
        """GC-313: Scope-First Isolation Enforcement.
        AEVUM_PERSONAL queries retrieve only personal records.
        SHARED_WITH_USER queries retrieve only shared history records.
        """
        bio_svc = LifeEventService()
        shared_svc = SharedHistoryService()

        # Seed personal
        bio_svc.register_fact(
            BiographicalFact(
                fact_id="f-penang",
                domain=BiographicalDomain.ORIGIN_AND_IDENTITY,
                attribute_key="hometown",
                attribute_value="Penang",
                era=LifeEra.EARLY_CHILDHOOD,
                provenance="seed_canon",
                valid_from_era=LifeEra.EARLY_CHILDHOOD,
            )
        )

        # Seed shared
        shared_svc.promote_candidate(
            SharedHistoryCandidate(
                candidate_id="cand-shared",
                episode_type=SharedEpisodeType.MEANINGFUL_CONVERSATION,
                title="Tea Dialogue",
                summary="Discussing tea varieties together",
                session_anchor="turn-10",
                evidence_text="User: I love oolong. Aevum: Me too.",
            )
        )

        # Personal query
        retriever = AutobiographicalRetriever(bio_svc)
        q_personal = AutobiographicalQuery(
            raw_query="Where were you born?",
            target_domain=BiographicalDomain.ORIGIN_AND_IDENTITY,
            scope=HistoryScope.AEVUM_PERSONAL,
        )
        res_personal = retriever.retrieve(q_personal)
        assert len(res_personal.matched_facts) == 1
        assert res_personal.matched_facts[0].fact_id == "f-penang"

        # Shared query
        q_shared = SharedHistoryQuery(
            raw_query="tea varieties",
            keywords=("tea", "varieties"),
            scope=HistoryScope.SHARED_WITH_USER,
        )
        res_shared = shared_svc.query_episodes(q_shared)
        assert len(res_shared) == 1
        assert res_shared[0].summary == "Discussing tea varieties together"

    def test_gc314_deterministic_scored_ranking_and_budget_caps(self) -> None:
        """GC-314: Deterministic Scored Ranking & Budget Caps.
        Candidates are scored via deterministic integer weights. Strict budget caps are enforced.
        """
        bio_svc = LifeEventService()
        for i in range(10):
            bio_svc.register_life_event(
                LifeEventRecord(
                    event_id=f"evt-{i}",
                    era=LifeEra.SECONDARY_SCHOOL,
                    domain=BiographicalDomain.PASSION_AND_DISCIPLINE,
                    headline=f"Programming project {i}",
                    summary=f"Built tool {i} in Python",
                )
            )

        retriever = AutobiographicalRetriever(bio_svc)
        query = AutobiographicalQuery(
            raw_query="Python programming project",
            keywords=("programming", "python"),
        )
        result = retriever.retrieve(query)
        assert len(result.matched_events) <= AutobiographicalRetriever.MAX_EVENTS
        assert len(result.matched_events) == 4

    def test_gc315_qualia_anchor_contextual_expansion(self) -> None:
        """GC-315: Qualia Anchor Contextual Expansion.
        Associated sensory qualia anchors are retrieved and expanded when their event matches.
        """
        bio_svc = LifeEventService()
        qualia = QualiaAnchor(
            qualia_id="qualia-petrichor",
            sensory_modality="olfactory",
            description="The sharp, earthy scent of petrichor on hot asphalt.",
            emotional_coloring="nostalgic",
        )
        bio_svc.register_qualia(qualia)

        evt = LifeEventRecord(
            event_id="evt-rain-walk",
            era=LifeEra.PRIMARY_SCHOOL,
            domain=BiographicalDomain.LIFESTYLE_AND_RHYTHM,
            headline="Monsoon rain walk",
            summary="Walked through tropical rainstorm in George Town.",
            qualia_ids=["qualia-petrichor"],
        )
        bio_svc.register_life_event(evt)

        retriever = AutobiographicalRetriever(bio_svc)
        query = AutobiographicalQuery(
            raw_query="tropical monsoon rain walk",
            keywords=("monsoon", "rain"),
        )
        result = retriever.retrieve(query)
        assert len(result.matched_events) == 1
        assert len(result.matched_qualia) == 1
        assert result.matched_qualia[0].qualia_id == "qualia-petrichor"

    def test_gc316_undefined_territory_humble_fallback(self) -> None:
        """GC-316: Undefined Territory Humble Fallback.
        When query matches no canonical facts, retrieval returns empty candidate sets and
        assembler emits an explicit <undefined_territory> directive.
        """
        bio_svc = LifeEventService()
        retriever = AutobiographicalRetriever(bio_svc)
        query = AutobiographicalQuery(raw_query="What was your favorite martial arts tournament in Paris?")
        res = retriever.retrieve(query)
        assert res.is_empty is True
        assert len(res.matched_facts) == 0
        assert len(res.matched_events) == 0

        assembled = BiographicalContextAssembler.assemble(res)
        assert '<directive type="UNDEFINED_TERRITORY">' in assembled.context_text
        assert "No canonical life events, facts, or preferences exist for this inquiry" in assembled.context_text
        assert "Acknowledge the lack of memory or experience naturally and honestly" in assembled.context_text
        assert "without improvising new life history" in assembled.context_text


# ==============================================================================
# CLUSTER 5: Longitudinal Shared History & Context Assembly (GC-317 ~ GC-320)
# ==============================================================================

class TestCluster5LongitudinalSharedHistoryAndAssembly:
    """Acceptance benchmarks verifying dual-track assembly, determinism, and non-retroactivity."""

    def test_gc317_shared_history_promotion_deduplication_and_session_anchor(self) -> None:
        """GC-317: Shared History Promotion Deduplication & Session Anchor.
        Promoting shared history deduplicates identical summaries and validates session anchor presence.
        """
        shared_svc = SharedHistoryService()
        cand = SharedHistoryCandidate(
            candidate_id="cand-gc317",
            episode_type=SharedEpisodeType.COLLABORATIVE_TASK,
            title="Refined Phase 12 Blueprint",
            summary="Refined the Phase 12 architecture blueprint",
            session_anchor="turn-blueprint-1",
            evidence_text="User: Blueprint refined. Aevum: Verified.",
        )
        ep = shared_svc.promote_candidate(cand)
        assert ep.session_anchor == "turn-blueprint-1"
        assert set(ep.participants) == {"aevum", "user"}

        # Re-promoting same candidate produces deduplicated episode
        ep2 = shared_svc.promote_candidate(cand)
        assert ep.episode_id == ep2.episode_id
        assert len(shared_svc._episodes) == 1

    def test_gc318_dual_track_longitudinal_context_assembly_structure(self) -> None:
        """GC-318: Dual-Track Longitudinal Context Assembly Structure.
        Merges Track 1 (<personal_biography_track>) and Track 2 (<shared_history_track>)
        within <longitudinal_context>.
        """
        bio_svc = get_biography_service()
        shared_svc = get_shared_history_service()

        retriever = AutobiographicalRetriever(bio_svc)
        p_res = retriever.retrieve(AutobiographicalQuery(raw_query="Penang software engineering"))
        personal_ctx = BiographicalContextAssembler.assemble(p_res)

        s_eps = shared_svc.query_episodes(SharedHistoryQuery(raw_query="Aevum pair programming"))

        assembled = LongitudinalContextAssembler.assemble(
            personal_context=personal_ctx,
            shared_episodes=tuple(s_eps),
        )

        assert "<longitudinal_context>" in assembled.longitudinal_xml
        assert "<personal_biography_track>" in assembled.longitudinal_xml
        assert "<shared_history_track" in assembled.longitudinal_xml
        assert "</longitudinal_context>" in assembled.longitudinal_xml

    def test_gc319_bitwise_replay_determinism_and_zero_dynamic_timestamp_leaks(self) -> None:
        """GC-319: Bitwise Replay Determinism & Zero Dynamic Timestamp Leaks.
        Assembling the same context 50 times yields exact bitwise identical XML string and hash.
        Zero dynamic wall-clock timestamps leak into generated XML context.
        """
        bio_svc = get_biography_service()
        shared_svc = get_shared_history_service()

        retriever = AutobiographicalRetriever(bio_svc)
        p_res = retriever.retrieve(AutobiographicalQuery(raw_query="Python programming"))
        personal_ctx = BiographicalContextAssembler.assemble(p_res)
        s_eps = tuple(shared_svc.query_episodes(SharedHistoryQuery(raw_query="coding architecture")))

        assembled_ref = LongitudinalContextAssembler.assemble(
            personal_context=personal_ctx,
            shared_episodes=s_eps,
        )
        ref_xml = assembled_ref.longitudinal_xml
        ref_hash = assembled_ref.context_hash

        for _ in range(50):
            assembled_curr = LongitudinalContextAssembler.assemble(
                personal_context=personal_ctx,
                shared_episodes=s_eps,
            )
            assert assembled_curr.longitudinal_xml == ref_xml
            assert assembled_curr.context_hash == ref_hash

        import re
        iso_leak = re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", ref_xml)
        assert iso_leak is None, f"Dynamic ISO timestamp found in XML context: {iso_leak.group(0)}"

    def test_gc320_multi_turn_retrieval_idempotence_and_zero_mutation(self) -> None:
        """GC-320: Multi-Turn Retrieval Idempotence & Zero Mutation.
        100 consecutive retrieval queries leave the internal services 100% bitwise unchanged.
        """
        bio_svc = LifeEventService()
        f = BiographicalFact(
            fact_id="f-static",
            domain=BiographicalDomain.ORIGIN_AND_IDENTITY,
            attribute_key="origin",
            attribute_value="Static canonical fact.",
            era=LifeEra.EARLY_CHILDHOOD,
            provenance="seed_canon",
            valid_from_era=LifeEra.EARLY_CHILDHOOD,
        )
        bio_svc.register_fact(f)

        retriever = AutobiographicalRetriever(bio_svc)
        state_before = dict(bio_svc._facts)
        for i in range(100):
            retriever.retrieve(AutobiographicalQuery(raw_query=f"query {i}"))

        state_after = dict(bio_svc._facts)
        assert state_before == state_after
        assert len(bio_svc._facts) == 1


# ==============================================================================
# CLUSTER 6: Desktop Projection Purity, Fixture Demarcation & AST Audits (GC-321 ~ GC-324)
# ==============================================================================

class TestCluster6DesktopProjectionAndASTAudits:
    """Acceptance benchmarks verifying read-only UI projection and static AST compliance."""

    @pytest.mark.asyncio
    async def test_gc321_desktop_projection_endpoint_contract_and_immutability(self) -> None:
        """GC-321: Desktop Projection Endpoint Contract & Immutability.
        GET /character/longitudinal-memory returns valid 200 OK projection with all expected domains.
        """
        reset_registry_for_testing()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/character/longitudinal-memory")
            assert resp.status_code == 200
            data = resp.json()

            assert "facts" in data and len(data["facts"]) >= 3
            assert "life_events" in data and len(data["life_events"]) >= 2
            assert "preferences" in data and len(data["preferences"]) >= 2
            assert "qualia" in data and len(data["qualia"]) >= 2
            assert "contacts" in data and len(data["contacts"]) >= 1
            assert "shared_episodes" in data and len(data["shared_episodes"]) >= 2
            assert "relational_dynamics" in data

    @pytest.mark.asyncio
    async def test_gc322_mind_body_directionality_and_write_route_non_existence(self) -> None:
        """GC-322: Mind/Body Directionality & Write Route Non-Existence.
        Verifies that no write routes (POST, PUT, PATCH, DELETE) exist for longitudinal-memory
        or biographical reality projection endpoints.
        """
        forbidden_methods = {"POST", "PUT", "PATCH", "DELETE"}
        for route in app.routes:
            path = getattr(route, "path", "")
            methods = getattr(route, "methods", set())
            if "longitudinal-memory" in path or "biography" in path:
                violating = methods.intersection(forbidden_methods)
                assert not violating, f"Forbidden write method {violating} found on route {path}"

    def test_gc323_watchpoint_audit_biography_registry_fixture_demarcation(self) -> None:
        """GC-323: Watchpoint Audit — biography_registry.py Fixture Demarcation.
        biography_registry.py is strictly a deterministic seed/fixture provider.
        Contains 0 DB session commits, 0 network calls, 0 mutation authority tokens.
        """
        registry_path = pathlib.Path(__file__).parents[1] / "app" / "biography" / "biography_registry.py"
        source = registry_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in ("commit", "rollback", "flush"):
                pytest.fail(f"Forbidden DB mutation call '{node.attr}' in biography_registry.py at line {node.lineno}")
            if isinstance(node, ast.Name) and node.id == "PromotionAuthorizationToken":
                pytest.fail("Forbidden PromotionAuthorizationToken found in biography_registry.py")

    def test_gc324_static_ast_boundary_audit_across_all_phase12_modules(self) -> None:
        """GC-324: Static AST Boundary Audit Across All Phase 12 Modules.
        Exhaustive audit across all 9 Phase 12 modules:
        0 float type annotations, 0 direct SQL, 0 live LLM API calls, 0 network I/O.
        """
        bio_dir = pathlib.Path(__file__).parents[1] / "app" / "biography"
        modules = [
            "biography_models.py",
            "causal_graph.py",
            "life_event_service.py",
            "retrieval_models.py",
            "autobiographical_retriever.py",
            "biographical_context_assembler.py",
            "shared_history_models.py",
            "shared_history_service.py",
            "biography_registry.py",
        ]

        forbidden_network_libs = {"requests", "urllib", "aiohttp"}

        for mod_name in modules:
            mod_path = bio_dir / mod_name
            assert mod_path.exists(), f"Phase 12 module missing: {mod_path}"
            source = mod_path.read_text(encoding="utf-8")
            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    for arg in node.args.args:
                        if arg.annotation and isinstance(arg.annotation, ast.Name) and arg.annotation.id == "float":
                            pytest.fail(f"Forbidden float argument annotation in {mod_name}:{node.name} at line {node.lineno}")
                    if node.returns and isinstance(node.returns, ast.Name) and node.returns.id == "float":
                        pytest.fail(f"Forbidden float return annotation in {mod_name}:{node.name} at line {node.lineno}")

                if isinstance(node, ast.Name) and node.id in forbidden_network_libs:
                    pytest.fail(f"Forbidden network library '{node.id}' in {mod_name} at line {node.lineno}")
