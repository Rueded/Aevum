"""test_phase124_shared_history.py — Dedicated Unit Tests for Phase 12.4 Longitudinal Shared History Engine.

Governed by ADR-023:
1. Constitutional Axiom: "Shared History records what Aevum and the user experienced together;
   it does not rewrite what Aevum was before the relationship."
2. Lock 4 & Lock F: Strict Relational Isolation. All shared episodes require HistoryScope.SHARED_WITH_USER.
3. Lock 6: Segregated Promotion Authorities. SharedHistoryService is completely decoupled from BiographyPromotionService.
4. Watchpoint: Scope-first retrieval without biography leaks.
5. Rule 16 Integration: Injects multi-axis relationship dynamics into dual-track longitudinal context.
6. Bitwise Replay Determinism: Excludes runtime timestamps from prompt XML and SHA-256 hash.
7. Pure Static AST Audit: 0 DB, 0 LLM, 0 network, 0 mutation authority tokens.
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
    HistoryScope,
    LifeEra,
    LifeEventRecord,
    RecallLevel,
)
from app.biography.life_event_service import LifeEventService
from app.biography.autobiographical_retriever import AutobiographicalRetriever
from app.biography.biographical_context_assembler import BiographicalContextAssembler
from app.biography.retrieval_models import (
    AutobiographicalIntentType,
    AutobiographicalQuery,
)
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


# ============================================================================
# Cluster 1: DTO Contracts & Relational Isolation (Lock 4 & Lock F)
# ============================================================================

class TestSharedHistoryContractsAndIsolation:
    """Verifies DTO contracts, frozen immutability, and strict HistoryScope.SHARED_WITH_USER."""

    def test_shared_episode_defaults_and_immutability(self) -> None:
        episode = SharedHistoryEpisode(
            episode_id="ep_001",
            episode_type=SharedEpisodeType.COLLABORATIVE_TASK,
            title="Refactored audio pipeline",
            summary="User and Aevum designed and refactored the audio amplitude lip-sync pipeline.",
            session_anchor="sess-042",
        )
        assert episode.scope == HistoryScope.SHARED_WITH_USER
        assert episode.participants == ("aevum", "user")
        assert episode.canonical_status == CanonicalStatus.CANONICAL
        assert episode.recall_level == RecallLevel.VIVID

        with pytest.raises(ValidationError):
            episode.title = "New Title"  # type: ignore[misc]

    def test_shared_episode_rejects_personal_scope(self) -> None:
        """Lock 4: Attempting to create a SharedHistoryEpisode with AEVUM_PERSONAL raises ValueError."""
        with pytest.raises(ValidationError, match="Lock 4 Violation"):
            SharedHistoryEpisode(
                episode_id="ep_invalid",
                scope=HistoryScope.AEVUM_PERSONAL,  # Forbidden!
                episode_type=SharedEpisodeType.FIRST_ACQUAINTANCE,
                title="Invalid episode",
                summary="Invalid summary",
                session_anchor="sess-001",
            )

    def test_shared_episode_rejects_missing_user_or_aevum(self) -> None:
        """Participants must contain both 'user' and 'aevum'."""
        with pytest.raises(ValidationError, match="include 'user'"):
            SharedHistoryEpisode(
                episode_id="ep_no_user",
                episode_type=SharedEpisodeType.FIRST_ACQUAINTANCE,
                title="Missing user",
                summary="Solo summary",
                session_anchor="sess-001",
                participants=("aevum", "third_party"),
            )

    def test_query_scope_enforcement(self) -> None:
        query = SharedHistoryQuery(raw_query="audio refactoring")
        assert query.scope == HistoryScope.SHARED_WITH_USER

        with pytest.raises(ValidationError, match="strictly requires HistoryScope.SHARED_WITH_USER"):
            SharedHistoryQuery(
                raw_query="audio",
                scope=HistoryScope.AEVUM_PERSONAL,  # Forbidden!
            )


# ============================================================================
# Cluster 2: Independent Promotion Authority (Lock 6)
# ============================================================================

class TestIndependentSharedHistoryPromotion:
    """Verifies SharedHistoryService promotion authority without BiographyPromotionService."""

    def test_candidate_promotion_success(self) -> None:
        service = SharedHistoryService()
        candidate = SharedHistoryCandidate(
            candidate_id="cand_101",
            episode_type=SharedEpisodeType.MEANINGFUL_CONVERSATION,
            title="Discussion on consciousness",
            summary="Explored theories of cognitive continuity and subjective qualia.",
            session_anchor="sess-077",
            key_learnings=("User prefers functionalist theories of mind",),
            evidence_text="User: What do you think about cognitive continuity? Aevum: ...",
            is_validated=True,
        )

        episode = service.promote_candidate(candidate)
        assert episode.episode_id == "ep_cand_101"
        assert episode.scope == HistoryScope.SHARED_WITH_USER
        assert episode.episode_type == SharedEpisodeType.MEANINGFUL_CONVERSATION
        assert episode.title == "Discussion on consciousness"
        assert service.total_episodes_count == 1

    def test_candidate_promotion_rejects_missing_anchor(self) -> None:
        service = SharedHistoryService()
        with pytest.raises(ValidationError, match="at least 1 character"):
            SharedHistoryCandidate(
                candidate_id="cand_bad",
                episode_type=SharedEpisodeType.COLLABORATIVE_TASK,
                title="Unanchored task",
                summary="Summary",
                session_anchor="",  # Empty anchor forbidden by Pydantic min_length=1
                evidence_text="dialogue",
            )

        # Whitespace-only anchor also rejected by service logic
        cand_ws = SharedHistoryCandidate(
            candidate_id="cand_ws",
            episode_type=SharedEpisodeType.COLLABORATIVE_TASK,
            title="Whitespace anchor task",
            summary="Summary",
            session_anchor="   ",
            evidence_text="dialogue",
        )
        with pytest.raises(ValueError, match="session_anchor is mandatory"):
            service.promote_candidate(cand_ws)

    def test_candidate_promotion_deduplication(self) -> None:
        service = SharedHistoryService()
        candidate1 = SharedHistoryCandidate(
            candidate_id="cand_dup1",
            episode_type=SharedEpisodeType.SHARED_RITUAL,
            title="Weekly retrospective",
            summary="Reviewed weekly development goals.",
            session_anchor="sess-099",
            evidence_text="dialogue",
        )
        candidate2 = SharedHistoryCandidate(
            candidate_id="cand_dup2",
            episode_type=SharedEpisodeType.SHARED_RITUAL,
            title="Weekly retrospective",
            summary="Different summary attempt for same session and title.",
            session_anchor="sess-099",
            evidence_text="dialogue",
        )

        ep1 = service.promote_candidate(candidate1)
        ep2 = service.promote_candidate(candidate2)
        assert ep1.episode_id == ep2.episode_id
        assert service.total_episodes_count == 1


# ============================================================================
# Cluster 3: Scope-First Retrieval & Budget Caps (Watchpoint Compliance)
# ============================================================================

class TestScopeFirstSharedHistoryRetrieval:
    """Verifies scope-first retrieval and budget enforcement."""

    def test_query_matching_and_ranking(self) -> None:
        service = SharedHistoryService()

        ep1 = SharedHistoryEpisode(
            episode_id="ep_001",
            episode_type=SharedEpisodeType.COLLABORATIVE_TASK,
            title="Desktop Live2D Integration",
            summary="Integrated WebGL canvas into the desktop layout.",
            session_anchor="sess-010",
            key_learnings=("Hit-testing must bypass rendering loop",),
        )
        ep2 = SharedHistoryEpisode(
            episode_id="ep_002",
            episode_type=SharedEpisodeType.MEANINGFUL_CONVERSATION,
            title="Tea Preference Dialogue",
            summary="Discussed roasted green tea and morning rituals.",
            session_anchor="sess-015",
            key_learnings=("User also enjoys morning roasted tea",),
        )
        service.register_episode(ep1)
        service.register_episode(ep2)

        # Query targeting collaborative task
        query = SharedHistoryQuery(
            raw_query="Live2D WebGL",
            episode_type=SharedEpisodeType.COLLABORATIVE_TASK,
            keywords=("live2d", "webgl"),
        )
        results = service.query_episodes(query)
        assert len(results) == 1
        assert results[0].episode_id == "ep_001"

    def test_budget_caps_enforced(self) -> None:
        """Query returns at most MAX_SHARED_EPISODES (4)."""
        service = SharedHistoryService()
        for i in range(10):
            ep = SharedHistoryEpisode(
                episode_id=f"ep_overflow_{i:02d}",
                episode_type=SharedEpisodeType.COLLABORATIVE_TASK,
                title=f"Shared task {i}",
                summary=f"Collaborative sprint {i}",
                session_anchor=f"sess-10{i}",
            )
            service.register_episode(ep)

        query = SharedHistoryQuery(
            raw_query="Shared task",
            keywords=("task", "sprint"),
        )
        results = service.query_episodes(query)
        assert len(results) <= SharedHistoryService.MAX_SHARED_EPISODES
        assert len(results) == 4


# ============================================================================
# Cluster 4: Dual-Track Longitudinal Context Assembly & Rule 16
# ============================================================================

class TestDualTrackLongitudinalContextAssembly:
    """Verifies dual-track context assembly, Rule 16 metrics, and bitwise determinism."""

    def test_dual_track_assembly_structure(self) -> None:
        # 1. Track 1: Personal context
        life_service = LifeEventService()
        evt = LifeEventRecord(
            event_id="evt-code-first",
            scope=HistoryScope.AEVUM_PERSONAL,
            era=LifeEra.SECONDARY_SCHOOL,
            domain=BiographicalDomain.PASSION_AND_DISCIPLINE,
            headline="First Python game",
            summary="Wrote text adventure",
        )
        life_service.register_life_event(evt)
        retriever = AutobiographicalRetriever(life_service)
        bio_query = AutobiographicalQuery(raw_query="high school", target_era=LifeEra.SECONDARY_SCHOOL)
        bio_result = retriever.retrieve(bio_query)
        personal_context = BiographicalContextAssembler.assemble(bio_result)

        # 2. Track 2: Shared history episodes
        shared_ep = SharedHistoryEpisode(
            episode_id="ep_collab_01",
            episode_type=SharedEpisodeType.COLLABORATIVE_TASK,
            title="Built Causal Life Graph",
            summary="Aevum and user designed Phase 12 causal engine.",
            session_anchor="sess-120",
            key_learnings=("Multi-hop cycles must be rejected before edge insertion",),
        )

        # 3. Rule 16 Relational Dynamics
        rel_metrics = {
            "familiarity": 0.45,
            "trust": 0.60,
            "comfort": 0.50,
            "affection": 0.10,
            "attachment": 0.05,
            "respect": 0.70,
        }

        assembled = LongitudinalContextAssembler.assemble(
            personal_context=personal_context,
            shared_episodes=(shared_ep,),
            relational_metrics=rel_metrics,
        )

        assert "<longitudinal_context>" in assembled.longitudinal_xml
        assert "</longitudinal_context>" in assembled.longitudinal_xml
        assert "SHARED EXPERIENCES DO NOT ALTER OR RETROACTIVELY EDIT AEVUM'S PERSONAL PAST" in assembled.longitudinal_xml
        assert "<personal_biography_track>" in assembled.longitudinal_xml
        assert "evt-code-first" in assembled.longitudinal_xml
        assert "<shared_history_track count=\"1\">" in assembled.longitudinal_xml
        assert "ep_collab_01" in assembled.longitudinal_xml
        assert "<relational_dynamics_track status=\"ACTIVE\">" in assembled.longitudinal_xml
        assert 'metric name="trust" value="0.6000"' in assembled.longitudinal_xml
        assert len(assembled.context_hash) == 64

    def test_bitwise_determinism_and_no_timestamp_leak(self) -> None:
        """Calling assemble() repeatedly on identical inputs yields bitwise identical XML and hash."""
        life_service = LifeEventService()
        retriever = AutobiographicalRetriever(life_service)
        bio_result = retriever.retrieve(AutobiographicalQuery(raw_query="test"))
        personal_context = BiographicalContextAssembler.assemble(bio_result)

        ep = SharedHistoryEpisode(
            episode_id="ep_test",
            episode_type=SharedEpisodeType.MEANINGFUL_CONVERSATION,
            title="Test episode",
            summary="Summary",
            session_anchor="sess-001",
        )

        c1 = LongitudinalContextAssembler.assemble(personal_context, (ep,))
        c2 = LongitudinalContextAssembler.assemble(personal_context, (ep,))

        assert c1.longitudinal_xml == c2.longitudinal_xml
        assert c1.context_hash == c2.context_hash

        # Confirm no runtime timestamp tokens
        forbidden = ["datetime.now", "utc_now", "assembled_at", "duration_ms"]
        for f in forbidden:
            assert f not in c1.longitudinal_xml


# ============================================================================
# Cluster 5: Non-Retroactivity Invariant
# ============================================================================

class TestConstitutionalNonRetroactivity:
    """Verifies Constitutional Axiom: Shared history cannot retroactively edit personal past."""

    def test_shared_history_cannot_overwrite_personal_canon(self) -> None:
        life_service = LifeEventService()
        personal_fact = BiographicalFact(
            fact_id="fact-birthplace",
            domain=BiographicalDomain.ORIGIN_AND_IDENTITY,
            attribute_key="childhood_residence",
            attribute_value="Penang, Malaysia",
            era=LifeEra.EARLY_CHILDHOOD,
            provenance="seed_canon",
            valid_from_era=LifeEra.EARLY_CHILDHOOD,
        )
        life_service.register_fact(personal_fact)

        shared_service = SharedHistoryService()
        # Even if a shared episode discusses Penang or anything else
        shared_candidate = SharedHistoryCandidate(
            candidate_id="cand_chat_penang",
            episode_type=SharedEpisodeType.MEANINGFUL_CONVERSATION,
            title="Chatted about Penang heritage",
            summary="User asked Aevum about heritage buildings in Penang.",
            session_anchor="sess-303",
            evidence_text="User: Tell me about Penang. Aevum: ...",
            is_validated=True,
        )
        shared_episode = shared_service.promote_candidate(shared_candidate)

        # Personal fact in LifeEventService remains completely unmodified and canonical
        retrieved_fact = life_service.get_fact_by_id("fact-birthplace")
        assert retrieved_fact is not None
        assert retrieved_fact.attribute_value == "Penang, Malaysia"
        assert retrieved_fact.scope == HistoryScope.AEVUM_PERSONAL

        # Shared episode exists strictly in SharedHistoryService with SHARED_WITH_USER
        assert shared_episode.scope == HistoryScope.SHARED_WITH_USER
        assert life_service.get_event_by_id("ep_cand_chat_penang") is None

    def test_register_episode_rejects_personal_scope(self) -> None:
        service = SharedHistoryService()
        # Even with direct object, registering with scope check prevents personal intrusion
        class MockInvalidEpisode:
            scope = HistoryScope.AEVUM_PERSONAL
            episode_id = "mock_bad"

        with pytest.raises(ValueError, match="Lock 4 Violation"):
            service.register_episode(MockInvalidEpisode())  # type: ignore[arg-type]

    def test_recent_episodes_retrieval(self) -> None:
        service = SharedHistoryService()
        for i in range(5):
            service.register_episode(
                SharedHistoryEpisode(
                    episode_id=f"ep_order_{i}",
                    episode_type=SharedEpisodeType.COLLABORATIVE_TASK,
                    title=f"Task {i}",
                    summary="Summary",
                    session_anchor=f"sess-{i}",
                )
            )
        recent = service.get_recent_episodes(limit=2)
        assert len(recent) == 2

    def test_unspecified_relational_dynamics_fallback(self) -> None:
        life_service = LifeEventService()
        retriever = AutobiographicalRetriever(life_service)
        bio_result = retriever.retrieve(AutobiographicalQuery(raw_query="hello"))
        personal_context = BiographicalContextAssembler.assemble(bio_result)

        assembled = LongitudinalContextAssembler.assemble(
            personal_context=personal_context,
            shared_episodes=(),
            relational_metrics=None,
        )
        assert '<relational_dynamics_track status="UNSPECIFIED" />' in assembled.longitudinal_xml


# ============================================================================
# Cluster 6: AST Constitutional Boundary Audit (12.4.6)
# ============================================================================

class TestASTConstitutionalBoundaryAudit:
    """Pure static AST boundary audit verifying zero DB, LLM, network, or mutation leaks in 12.4."""

    def test_phase124_modules_ast_purity(self) -> None:
        target_files = [
            pathlib.Path("app/biography/shared_history_models.py"),
            pathlib.Path("app/biography/shared_history_service.py"),
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

            # In models.py, confirm zero float type annotations
            if tf.name == "shared_history_models.py":
                for node in ast.walk(tree):
                    if isinstance(node, ast.AnnAssign):
                        target_str = ast.unparse(node.annotation).lower()
                        # Allow relational_metrics: Optional[dict[str, float]]
                        if "relational_metrics" in ast.unparse(node.target):
                            continue
                        assert "float" not in target_str, (
                            f"Illegal float annotation '{target_str}' in {tf}"
                        )
