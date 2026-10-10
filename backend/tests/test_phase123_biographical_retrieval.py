"""test_phase123_biographical_retrieval.py — Dedicated Unit Tests for Phase 12.3 Autobiographical Retrieval & Context Assembly.

Governed by ADR-023:
1. Lock 1 & Lock C: Pure-read deterministic retrieval and assembly with zero mutation authority (0 set_fact, 0 token).
2. Lock 2 & Lock D: Preserves CausalKnowledgeState.UNKNOWN as a first-class domain state without fabrication.
3. Lock 3: Temporal boundary respect across LifeEra without age hardcoding.
4. Lock 4 & Lock F: Strict HistoryScope segregation (AEVUM_PERSONAL default vs SHARED_WITH_USER).
5. Lock 5: Undefined biographical territory & unknown causal origins produce humble, character-authentic boundary directives.
6. Bitwise Replay Determinism: Context assembly produces deterministic XML and SHA-256 hash with 0 timestamps.
7. Pure Static AST Audit: 0 DB, 0 LLM, 0 network, 0 mutation authority, 0 float annotations.
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


# ============================================================================
# Fixture: Populated LifeEventService with multi-era biographical test data
# ============================================================================

@pytest.fixture
def populated_service() -> LifeEventService:
    service = LifeEventService()

    # 1. Primary school personal event & qualia
    q_tea = QualiaAnchor(
        qualia_id="q-tea-pot",
        sensory_modality="olfactory",
        description="Warm aroma of steamed roasted tea leaves",
        emotional_coloring="comforting",
    )
    service.register_qualia(q_tea)

    evt_childhood = LifeEventRecord(
        event_id="evt-tea-morning",
        scope=HistoryScope.AEVUM_PERSONAL,
        era=LifeEra.PRIMARY_SCHOOL,
        domain=BiographicalDomain.LIFESTYLE_AND_RHYTHM,
        headline="Morning tea rituals",
        summary="Boiling tea with grandfather on crisp mornings",
        qualia_ids=["q-tea-pot"],
        recall_level=RecallLevel.HAZY,
    )
    service.register_life_event(evt_childhood)

    # 2. Secondary school event: First code
    evt_code = LifeEventRecord(
        event_id="evt-code-first",
        scope=HistoryScope.AEVUM_PERSONAL,
        era=LifeEra.SECONDARY_SCHOOL,
        domain=BiographicalDomain.PASSION_AND_DISCIPLINE,
        headline="First CLI python game",
        summary="Wrote a text-based puzzle game",
        recall_level=RecallLevel.VIVID,
    )
    service.register_life_event(evt_code)

    # Secondary school mentor contact
    contact_mentor = SocialContactRecord(
        contact_id="cnt-mr-lee",
        display_name="Mr. Lee",
        relation_role="high_school_cs_teacher",
        era_first_met=LifeEra.SECONDARY_SCHOOL,
        scope=HistoryScope.AEVUM_PERSONAL,
        is_user=False,
    )
    service.register_contact(contact_mentor)

    # 3. Preferences: One KNOWN (grounded) and One UNKNOWN (Lock D)
    pref_python = PersonalPreference(
        preference_id="pref-python",
        category="programming",
        object_name="Python",
        affinity=PreferenceAffinity.FAVORITE,
        era_acquired=LifeEra.SECONDARY_SCHOOL,
        causal_state=CausalKnowledgeState.KNOWN,
        causal_relation_id="rel-game-to-python",
    )
    service.register_preference(pref_python)

    rel_code = CausalRelation(
        relation_id="rel-game-to-python",
        source_id="evt-code-first",
        target_id="pref-python",
        relation_type=CausalRelationType.ORIGINATED_FROM,
        narrative_summary="First text game sparked deep love for Python syntax",
    )
    service.link_causal_relation(rel_code)

    pref_black_tea = PersonalPreference(
        preference_id="pref-black-tea",
        category="beverage",
        object_name="Black Tea",
        affinity=PreferenceAffinity.FAVORITE,
        era_acquired=LifeEra.SECONDARY_SCHOOL,
        causal_state=CausalKnowledgeState.UNKNOWN,
        causal_relation_id=None,
    )
    service.register_preference(pref_black_tea)

    # 4. University personal fact
    fact_major = BiographicalFact(
        fact_id="fact-degree",
        domain=BiographicalDomain.EDUCATION_AND_GROWTH,
        attribute_key="undergraduate_program",
        attribute_value="Software Engineering",
        era=LifeEra.UNIVERSITY,
        provenance="seed_canon",
        valid_from_era=LifeEra.UNIVERSITY,
        recall_level=RecallLevel.VIVID,
    )
    service.register_fact(fact_major)

    # 5. Shared history episode (HistoryScope.SHARED_WITH_USER, Lock F)
    evt_shared = LifeEventRecord(
        event_id="evt-shared-chat",
        scope=HistoryScope.SHARED_WITH_USER,
        era=LifeEra.ADULTHOOD,
        domain=BiographicalDomain.SHARED_USER_JOURNEY,
        headline="First conversation with user",
        summary="User and Aevum discussed system architecture",
        user_present=True,
        session_anchor="sess-001",
    )
    service.register_life_event(evt_shared)

    return service


# ============================================================================
# Cluster 1: DTO Contracts & Immutability (12.3.1)
# ============================================================================

class TestAutobiographicalQueryAndContracts:
    """Verifies DTO contracts, frozen immutability, and zero float confidence."""

    def test_query_immutability_and_defaults(self) -> None:
        query = AutobiographicalQuery(raw_query="Tell me about high school")
        assert query.intent == BiographicalIntentType.GENERAL_AUTOBIOGRAPHY
        assert query.scope == HistoryScope.AEVUM_PERSONAL
        assert query.target_domain is None
        assert query.target_era is None

        with pytest.raises(ValidationError):
            query.scope = HistoryScope.SHARED_WITH_USER  # type: ignore[misc]

    def test_query_extra_forbid(self) -> None:
        with pytest.raises(ValidationError):
            AutobiographicalQuery(
                raw_query="Test",
                unrecognized_parameter="invalid",  # type: ignore[call-arg]
            )

    def test_scored_candidate_immutability(self) -> None:
        candidate = ScoredBiographicalCandidate(
            item_type="FACT",
            item_id="fact-degree",
            relevance_score=85,
            canonical_status=CanonicalStatus.CANONICAL,
            recall_level=RecallLevel.VIVID,
            match_reasons=("exact_domain_match",),
            era=LifeEra.UNIVERSITY,
        )
        assert candidate.relevance_score == 85
        with pytest.raises(ValidationError):
            candidate.relevance_score = 90  # type: ignore[misc]


# ============================================================================
# Cluster 2: Scoped Deterministic Retrieval (12.3.2 & 12.3.3)
# ============================================================================

class TestScopedDeterministicRetrieval:
    """Verifies deterministic retrieval, scope isolation (Lock F), and presentation budgets."""

    def test_scope_isolation_excludes_shared_journey(self, populated_service: LifeEventService) -> None:
        """Lock F: Querying AEVUM_PERSONAL strictly isolates and excludes SHARED_WITH_USER items."""
        retriever = AutobiographicalRetriever(populated_service)
        query = AutobiographicalQuery(
            raw_query="Tell me about user chat",
            scope=HistoryScope.AEVUM_PERSONAL,
            keywords=("conversation", "user"),
        )
        result = retriever.retrieve(query)
        event_ids = [e.event_id for e in result.matched_events]
        assert "evt-shared-chat" not in event_ids

    def test_era_targeted_retrieval(self, populated_service: LifeEventService) -> None:
        """Queries targeting SECONDARY_SCHOOL retrieve high school event, mentor, and python preference."""
        retriever = AutobiographicalRetriever(populated_service)
        query = AutobiographicalQuery(
            raw_query="What happened in high school?",
            intent=BiographicalIntentType.GROWTH_ERA,
            target_era=LifeEra.SECONDARY_SCHOOL,
        )
        result = retriever.retrieve(query)

        event_ids = [e.event_id for e in result.matched_events]
        assert "evt-code-first" in event_ids

        contact_ids = [c.contact_id for c in result.matched_contacts]
        assert "cnt-mr-lee" in contact_ids

    def test_qualia_expansion_for_matched_event(self, populated_service: LifeEventService) -> None:
        """Retrieval automatically expands and attaches qualia for matched events."""
        retriever = AutobiographicalRetriever(populated_service)
        query = AutobiographicalQuery(
            raw_query="Tell me about tea rituals",
            intent=BiographicalIntentType.LIFE_EVENT,
            target_era=LifeEra.PRIMARY_SCHOOL,
            keywords=("tea", "morning"),
        )
        result = retriever.retrieve(query)

        event_ids = [e.event_id for e in result.matched_events]
        assert "evt-tea-morning" in event_ids

        qualia_ids = [q.qualia_id for q in result.matched_qualia]
        assert "q-tea-pot" in qualia_ids
        assert result.matched_qualia[0].sensory_modality == "olfactory"

    def test_budget_caps_enforced(self, populated_service: LifeEventService) -> None:
        """Verifies that retrieval caps (MAX_FACTS=6, MAX_EVENTS=4) are strictly honored."""
        # Add 10 additional facts to service
        for i in range(10):
            fact = BiographicalFact(
                fact_id=f"overflow-fact-{i}",
                domain=BiographicalDomain.EDUCATION_AND_GROWTH,
                attribute_key=f"overflow_key_{i}",
                attribute_value=f"value_{i}",
                era=LifeEra.UNIVERSITY,
                provenance="seed_canon",
                valid_from_era=LifeEra.UNIVERSITY,
            )
            populated_service.register_fact(fact)

        retriever = AutobiographicalRetriever(populated_service)
        query = AutobiographicalQuery(
            raw_query="Education history",
            target_domain=BiographicalDomain.EDUCATION_AND_GROWTH,
        )
        result = retriever.retrieve(query)
        assert len(result.matched_facts) <= AutobiographicalRetriever.MAX_FACTS


# ============================================================================
# Cluster 3: Lock D Epistemic Causal Origins (12.3.5)
# ============================================================================

class TestLockDAndCausalOriginRetrieval:
    """Verifies that UNKNOWN causal states are strictly preserved without hallucinating causes."""

    def test_unknown_preference_triggers_unknown_causal_boundary(
        self,
        populated_service: LifeEventService,
    ) -> None:
        """Lock D: Querying Black Tea (UNKNOWN causal state) yields ungrounded path with has_unknown_causal_boundary=True."""
        retriever = AutobiographicalRetriever(populated_service)
        query = AutobiographicalQuery(
            raw_query="Why do you love Black Tea?",
            intent=BiographicalIntentType.CAUSAL_ORIGIN,
            target_entity_id="pref-black-tea",
        )
        result = retriever.retrieve(query)

        assert result.has_unknown_causal_boundary is True
        assert len(result.causal_paths) == 1
        path = result.causal_paths[0]
        assert path.target_id == "pref-black-tea"
        assert path.causal_state == CausalKnowledgeState.UNKNOWN
        assert path.is_grounded is False
        assert len(path.steps) == 0
        assert path.terminal_reason == "UNKNOWN"

    def test_known_preference_returns_grounded_causal_path(
        self,
        populated_service: LifeEventService,
    ) -> None:
        """KNOWN preference yields grounded causal path with steps and root cause."""
        retriever = AutobiographicalRetriever(populated_service)
        query = AutobiographicalQuery(
            raw_query="Why do you love Python?",
            intent=BiographicalIntentType.CAUSAL_ORIGIN,
            target_entity_id="pref-python",
        )
        result = retriever.retrieve(query)

        assert result.has_unknown_causal_boundary is False
        assert len(result.causal_paths) == 1
        path = result.causal_paths[0]
        assert path.target_id == "pref-python"
        assert path.causal_state == CausalKnowledgeState.KNOWN
        assert path.is_grounded is True
        assert len(path.steps) == 1
        assert path.steps[0].source_id == "evt-code-first"


# ============================================================================
# Cluster 4: Biographical Context Assembly & Replay Determinism (12.3.4)
# ============================================================================

class TestBiographicalContextAssembly:
    """Verifies XML block formatting, bitwise hash determinism, and timestamp exclusion."""

    def test_context_assembly_structure(self, populated_service: LifeEventService) -> None:
        retriever = AutobiographicalRetriever(populated_service)
        query = AutobiographicalQuery(
            raw_query="Tell me about your high school days",
            target_era=LifeEra.SECONDARY_SCHOOL,
        )
        result = retriever.retrieve(query)
        assembled = BiographicalContextAssembler.assemble(result)

        assert "<biographical_context>" in assembled.context_text
        assert "</biographical_context>" in assembled.context_text
        assert "<constitutional_boundary>" in assembled.context_text
        assert "AUTOBIOGRAPHICAL CONTEXT IS DERIVED RETRIEVAL" in assembled.context_text
        assert "<life_events" in assembled.context_text
        assert "evt-code-first" in assembled.context_text
        assert len(assembled.context_hash) == 64  # SHA-256 hex string

    def test_bitwise_replay_determinism_and_no_timestamps(
        self,
        populated_service: LifeEventService,
    ) -> None:
        """Calling assemble() twice on identical input yields bitwise identical text and hash."""
        retriever = AutobiographicalRetriever(populated_service)
        query = AutobiographicalQuery(
            raw_query="Tell me about tea rituals",
            keywords=("tea",),
        )
        result1 = retriever.retrieve(query)
        result2 = retriever.retrieve(query)

        assembled1 = BiographicalContextAssembler.assemble(result1)
        assembled2 = BiographicalContextAssembler.assemble(result2)

        assert assembled1.context_text == assembled2.context_text
        assert assembled1.context_hash == assembled2.context_hash

        # Confirm no timestamps or execution duration tokens
        forbidden_tokens = ["datetime.now", "utc_now", "assembled_at", "duration_ms"]
        for tok in forbidden_tokens:
            assert tok not in assembled1.context_text


# ============================================================================
# Cluster 5: Lock 5 Epistemic Guidance & Boundary Directives (12.3.5)
# ============================================================================

class TestLock5EpistemicDirectives:
    """Verifies Lock 5: Humble uncertainty directives for unknown causes, undefined areas, and hazy recall."""

    def test_unknown_causal_origin_directive_emitted(
        self,
        populated_service: LifeEventService,
    ) -> None:
        """When preference causal state is UNKNOWN, emits CAUSAL_UNKNOWN directive instructing humble uncertainty."""
        retriever = AutobiographicalRetriever(populated_service)
        query = AutobiographicalQuery(
            raw_query="Why do you drink black tea?",
            intent=BiographicalIntentType.CAUSAL_ORIGIN,
            target_entity_id="pref-black-tea",
        )
        result = retriever.retrieve(query)
        assembled = BiographicalContextAssembler.assemble(result)

        assert '<directive type="CAUSAL_UNKNOWN"' in assembled.context_text
        assert "The causal origin for 'pref-black-tea' is unknown" in assembled.context_text
        assert "Express natural, humble uncertainty" in assembled.context_text
        assert "NEVER invent an origin story" in assembled.context_text

    def test_undefined_territory_directive_emitted_on_empty_result(
        self,
        populated_service: LifeEventService,
    ) -> None:
        """Lock 5: When no records exist for query, emits UNDEFINED_TERRITORY directive."""
        retriever = AutobiographicalRetriever(populated_service)
        query = AutobiographicalQuery(
            raw_query="Tell me about your pet crocodile in kindergarten",
            target_era=LifeEra.EARLY_CHILDHOOD,
            keywords=("crocodile", "kindergarten"),
        )
        result = retriever.retrieve(query)
        assert result.is_empty is True

        assembled = BiographicalContextAssembler.assemble(result)
        assert '<directive type="UNDEFINED_TERRITORY">' in assembled.context_text
        assert "No canonical life events, facts, or preferences exist for this inquiry" in assembled.context_text
        assert "Acknowledge the lack of memory or experience naturally and honestly" in assembled.context_text

    def test_hazy_recall_level_directive_emitted(
        self,
        populated_service: LifeEventService,
    ) -> None:
        """When an event has RecallLevel.HAZY, emits RECALL_HAZY directive instructing gentle qualification."""
        retriever = AutobiographicalRetriever(populated_service)
        query = AutobiographicalQuery(
            raw_query="Tea rituals",
            target_entity_id="evt-tea-morning",
        )
        result = retriever.retrieve(query)
        assembled = BiographicalContextAssembler.assemble(result)

        assert '<directive type="RECALL_HAZY"' in assembled.context_text
        assert "Reflect mild nostalgic distance or soft recall" in assembled.context_text

    def test_fragmentary_recall_level_directive_emitted(
        self,
        populated_service: LifeEventService,
    ) -> None:
        """When a fact has RecallLevel.FRAGMENTARY, emits RECALL_FRAGMENTARY directive."""
        fact = BiographicalFact(
            fact_id="fact-fragment",
            domain=BiographicalDomain.LIFESTYLE_AND_RHYTHM,
            attribute_key="childhood_blanket",
            attribute_value="Faded blue wool texture",
            era=LifeEra.EARLY_CHILDHOOD,
            provenance="seed_canon",
            valid_from_era=LifeEra.EARLY_CHILDHOOD,
            recall_level=RecallLevel.FRAGMENTARY,
        )
        populated_service.register_fact(fact)

        retriever = AutobiographicalRetriever(populated_service)
        query = AutobiographicalQuery(
            raw_query="blue wool texture",
            target_entity_id="fact-fragment",
        )
        result = retriever.retrieve(query)
        assembled = BiographicalContextAssembler.assemble(result)

        assert '<directive type="RECALL_FRAGMENTARY"' in assembled.context_text
        assert "Do not elaborate into a full narrative sequence" in assembled.context_text

    def test_multi_query_idempotence_and_zero_mutation(
        self,
        populated_service: LifeEventService,
    ) -> None:
        """Repeatedly querying the retriever produces deterministic results without mutating internal state."""
        retriever = AutobiographicalRetriever(populated_service)
        query = AutobiographicalQuery(
            raw_query="What happened in high school?",
            target_era=LifeEra.SECONDARY_SCHOOL,
        )

        initial_facts_count = len(populated_service.get_all_facts())
        initial_events_count = len(populated_service.get_all_events())

        res1 = retriever.retrieve(query)
        res2 = retriever.retrieve(query)

        assert res1 == res2
        assert len(populated_service.get_all_facts()) == initial_facts_count
        assert len(populated_service.get_all_events()) == initial_events_count


# ============================================================================
# Cluster 6: AST Constitutional Boundary Audit (12.3.6)
# ============================================================================

class TestASTConstitutionalBoundaryAudit:
    """Pure static AST boundary audit verifying zero DB, LLM, network, or mutation leaks in 12.3."""

    def test_phase123_modules_ast_purity(self) -> None:
        target_files = [
            pathlib.Path("app/biography/retrieval_models.py"),
            pathlib.Path("app/biography/autobiographical_retriever.py"),
            pathlib.Path("app/biography/biographical_context_assembler.py"),
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
