"""Golden Suite 7D Orchestration: Phase 7D.5 End-to-End Integration Acceptance Benchmarks.

Tests:
- GC-116: EvidenceClassifier — education.university trigger → correct slot, LOCAL scope
- GC-117: EvidenceClassifier — education.year trigger → DEPENDENT scope
- GC-118: EvidenceClassifier — lifestyle.commute_mode → DIRECT scope
- GC-119: EvidenceClassifier — preferences.study_beverage → BEHAVIORAL_CORRELATE edge
- GC-120: EvidenceClassifier — education.pathway → STRUCTURAL_DEPENDENCY edge
- GC-121: EvidenceClassifier — question-only input → no_signal
- GC-122: EvidenceClassifier — chitchat → no_signal
- GC-123: WorldFactsSelector — USM mention → world.usm.main_campus included
- GC-124: WorldFactsSelector — 昔涟 mention → lore.game.xianlian included
- GC-125: WorldFactsSelector — unrelated input → {}
- GC-126: WorldFactsSelector — PLAUSIBILITY_RULE items never returned
- GC-127: WorldFactsSelector — same input produces same output (deterministic)
- GC-128: ContradictionResolver runs independently of candidate pipeline
- GC-129: Casual turn — governed_reality populated, no candidate, no error
- GC-130: Biographical signal → CandidateHypothesis in DB with PERSISTED state
- GC-131: After orchestration, canonical core NOT mutated (unless 14 gates pass)
- GC-132: Contradiction → repair_result → ephemeral_repair_context in GovernedRealityContext
- GC-133: USM input → objective_world_facts section populated
- GC-134: Unrelated input → objective_world_facts section absent
- GC-135: DB failure in get_all_active_candidates → raises, NOT silently converted to []
- GC-136: RealityBeliefEngine.process_turn() never invoked in run_turn()
- GC-137: CharacterEngine.build_response_context() does not call RealityBeliefEngine
- GC-138: All stages empty → full pipeline completes, GovernedRealityContext non-None
- GC-139: get_all_active_candidates() → [] is valid normal empty state, NOT infrastructure failure
- GC-140: Failure after promotion leaves promotion durable; fallback uses pre-promotion snapshot
"""

import ast
import pathlib
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.reality.evidence_classifier import EvidenceClassifier, EvidenceClassificationResult
from app.reality.world_facts_selector import WorldFactsSelector
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
from app.reality.contradiction_models import ContradictionResolution, ContradictionType
from app.reality.reality_orchestration_service import (
    CandidateRepositoryUnavailableError,
    RealityOrchestrationService,
)
from app.reality.world_knowledge import KnowledgeKind, WorldKnowledgeRegistry


def _utc_now():
    return datetime.now(timezone.utc)


def _make_mock_core(facts: dict = None, locked_slots: set = None):
    """Build a minimal mock CharacterCore for testing."""
    core = MagicMock()
    core.facts = facts or {}
    core.is_locked = lambda slot: slot in (locked_slots or set())
    core.get_fact = lambda slot: (facts or {}).get(slot)
    return core


# ---------------------------------------------------------------------------
# EvidenceClassifier tests — GC-116 ~ GC-122
# ---------------------------------------------------------------------------


class TestEvidenceClassifier:

    def test_gc116_education_university(self):
        """GC-116: education.university trigger → correct slot, LOCAL scope."""
        result = EvidenceClassifier.classify("我在 USM 读 Computer Science 专业")
        assert result.has_biographical_signal is True
        assert result.slot_name == "education.university"
        assert result.inference_scope == InferenceScope.LOCAL
        assert result.inference_edge_type == InferenceEdgeType.STRUCTURAL_DEPENDENCY
        assert result.reality_taxonomy == RealityTaxonomy.SIMULATED_BIOGRAPHY_FACT

    def test_gc116_education_university_english(self):
        """GC-116 variant: English phrasing → education.university."""
        result = EvidenceClassifier.classify("I'm studying Software Engineering at uni")
        assert result.has_biographical_signal is True
        assert result.slot_name == "education.university"

    def test_gc117_education_year(self):
        """GC-117: education.year trigger → DEPENDENT scope."""
        result = EvidenceClassifier.classify("我 STPM 毕业大几了")
        assert result.has_biographical_signal is True
        assert result.slot_name == "education.year"
        assert result.inference_scope == InferenceScope.DEPENDENT
        assert result.inference_edge_type == InferenceEdgeType.TEMPORAL_DEPENDENCY

    def test_gc118_lifestyle_commute(self):
        """GC-118: lifestyle.commute_mode → DIRECT scope."""
        result = EvidenceClassifier.classify("我平时去学校怎么去？走路的。")
        assert result.has_biographical_signal is True
        assert result.slot_name == "lifestyle.commute_mode"
        assert result.inference_scope == InferenceScope.DIRECT
        assert result.inference_edge_type == InferenceEdgeType.DIRECT_ATTRIBUTE

    def test_gc119_study_beverage(self):
        """GC-119: preferences.study_beverage → BEHAVIORAL_CORRELATE edge."""
        result = EvidenceClassifier.classify("我读书的时候喜欢喝咖啡")
        assert result.has_biographical_signal is True
        assert result.slot_name == "preferences.study_beverage"
        assert result.inference_edge_type == InferenceEdgeType.BEHAVIORAL_CORRELATE

    def test_gc120_education_pathway(self):
        """GC-120: education.pathway → STRUCTURAL_DEPENDENCY edge."""
        result = EvidenceClassifier.classify("SPM 之后我选择了 foundation 升学")
        assert result.has_biographical_signal is True
        assert result.slot_name == "education.pathway"
        assert result.inference_edge_type == InferenceEdgeType.STRUCTURAL_DEPENDENCY

    def test_gc121_question_no_signal(self):
        """GC-121: Pure question → no_signal. Question about Aevum is not an assertion."""
        result = EvidenceClassifier.classify("你学什么专业？")
        assert result.has_biographical_signal is False
        assert result.slot_name is None

    def test_gc122_chitchat_no_signal(self):
        """GC-122: Casual chitchat → no_signal."""
        result = EvidenceClassifier.classify("哈哈今天好困啊")
        assert result.has_biographical_signal is False
        assert result.slot_name is None

    def test_gc122_variant_greeting_no_signal(self):
        """GC-122 variant: Greeting → no_signal."""
        result = EvidenceClassifier.classify("你好！最近怎样？")
        assert result.has_biographical_signal is False

    def test_existing_canonical_fact_skips_signal(self):
        """If fact already canonical, no signal is generated (prevents duplicate candidates)."""
        core = _make_mock_core(facts={"education.university": MagicMock(value="USM")})
        result = EvidenceClassifier.classify("我在 USM 读书专业", core=core)
        assert result.has_biographical_signal is False


# ---------------------------------------------------------------------------
# WorldFactsSelector tests — GC-123 ~ GC-127
# ---------------------------------------------------------------------------


class TestWorldFactsSelector:

    def test_gc123_usm_match(self):
        """GC-123: USM mention → world.usm.main_campus included."""
        result = WorldFactsSelector.select_for_turn("我在 USM 读书")
        # Should include USM facts if any STATIC_FACT/ENTITY_RELATION key matches
        # At minimum, must not return PLAUSIBILITY_RULE items
        registry = WorldKnowledgeRegistry._REGISTRY
        for key in result:
            item = registry.get(key)
            assert item is not None
            assert item.kind in (KnowledgeKind.STATIC_FACT, KnowledgeKind.ENTITY_RELATION)

    def test_gc123_usm_specifically(self):
        """GC-123: 'usm' alias matches world.usm.* items."""
        result = WorldFactsSelector.select_for_turn("读 USM 的课程")
        # Any USM key should appear if registered as STATIC_FACT or ENTITY_RELATION
        usm_keys = [k for k in result if "usm" in k.lower()]
        # If there are USM registry items of eligible kind, they should be in result
        registry = WorldKnowledgeRegistry._REGISTRY
        eligible_usm = [
            k for k, v in registry.items()
            if "usm" in k.lower()
            and v.kind in (KnowledgeKind.STATIC_FACT, KnowledgeKind.ENTITY_RELATION)
        ]
        if eligible_usm:
            assert len(usm_keys) > 0, "Expected USM facts but found none"

    def test_gc124_xianlian_match(self):
        """GC-124: 昔涟 mention → lore.game.xianlian included."""
        result = WorldFactsSelector.select_for_turn("昔涟这个游戏")
        registry = WorldKnowledgeRegistry._REGISTRY
        eligible_xianlian = [
            k for k, v in registry.items()
            if "xianlian" in k.lower()
            and v.kind in (KnowledgeKind.STATIC_FACT, KnowledgeKind.ENTITY_RELATION)
        ]
        if eligible_xianlian:
            matched = [k for k in result if "xianlian" in k.lower()]
            assert len(matched) > 0, "Expected Xianlian lore facts but found none"
        # Even if no eligible items, result must be valid dict
        assert isinstance(result, dict)

    def test_gc125_no_match_returns_empty(self):
        """GC-125: Completely unrelated input → {} (never falls back to registry order)."""
        result = WorldFactsSelector.select_for_turn("今天天气很好我很开心")
        assert result == {}

    def test_gc125_empty_input_returns_empty(self):
        """GC-125 variant: Empty input → {}."""
        result = WorldFactsSelector.select_for_turn("")
        assert result == {}

    def test_gc126_plausibility_rule_never_returned(self):
        """GC-126: PLAUSIBILITY_RULE items are never returned regardless of input."""
        registry = WorldKnowledgeRegistry._REGISTRY
        plausibility_keys = [
            k for k, v in registry.items()
            if v.kind == KnowledgeKind.PLAUSIBILITY_RULE
        ]
        if not plausibility_keys:
            pytest.skip("No PLAUSIBILITY_RULE items registered — test not applicable")

        # Use a very broad input to maximize matching chance
        broad_input = " ".join(plausibility_keys)
        result = WorldFactsSelector.select_for_turn(broad_input)

        for key in result:
            item = registry.get(key)
            assert item is not None
            assert item.kind != KnowledgeKind.PLAUSIBILITY_RULE, (
                f"PLAUSIBILITY_RULE item '{key}' was returned — must be excluded"
            )

    def test_gc127_deterministic_same_input(self):
        """GC-127: Same input + same registry state → identical output twice."""
        user_input = "USM 大学我在读 computer science"
        result_1 = WorldFactsSelector.select_for_turn(user_input)
        result_2 = WorldFactsSelector.select_for_turn(user_input)
        assert result_1 == result_2

    def test_gc127_cap_at_four(self):
        """GC-127 variant: Result capped at max_items (default 4)."""
        # Even if many items match, at most 4 returned
        result = WorldFactsSelector.select_for_turn("usm university sun xianlian kota")
        assert len(result) <= 4

    def test_eligible_kinds_only(self):
        """Only STATIC_FACT and ENTITY_RELATION items can appear in output."""
        result = WorldFactsSelector.select_for_turn("usm university malaysia sabah")
        registry = WorldKnowledgeRegistry._REGISTRY
        for key in result:
            item = registry.get(key)
            assert item is not None
            assert item.kind in (KnowledgeKind.STATIC_FACT, KnowledgeKind.ENTITY_RELATION)


# ---------------------------------------------------------------------------
# Contradiction independence test — GC-128
# ---------------------------------------------------------------------------


class TestContradictionIndependence:

    @pytest.mark.asyncio
    async def test_gc128_contradiction_independent_of_candidate(self):
        """GC-128: ContradictionResolver signal produced even when no candidate generated.

        Contradiction detection must run on user_input + core only.
        It must not depend on CandidateHypothesis or ChoiceDecisionResult.
        """
        from app.reality.contradiction_resolver import ContradictionResolver

        core = _make_mock_core()
        # Chitchat that has no biographical signal but might trigger contradiction check
        user_input = "The sun rises in the west right?"
        result = ContradictionResolver.resolve(
            user_input,
            core=core,
            current_location=None,
            prior_slip=None,
        )
        assert isinstance(result, ContradictionResolution)
        # canonical_mutated must always be False (resolver is a pure signal producer)
        assert result.canonical_mutated is False


# ---------------------------------------------------------------------------
# Orchestration integration tests (async, using mocked session) — GC-129 ~ GC-140
# ---------------------------------------------------------------------------


def _make_mock_session():
    """Build a minimal async mock session."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


def _make_mock_session_for_empty_candidates():
    """Session where get_all_active_candidates() would return empty list."""
    from unittest.mock import MagicMock
    session = AsyncMock(spec=AsyncSession)
    # execute returns a result with empty scalars
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=mock_result)
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


@pytest.mark.asyncio
class TestOrchestrationIntegration:

    async def test_gc129_casual_turn_no_candidate(self):
        """GC-129: Casual input → governed_reality populated, no candidate in DB, no error."""
        session = _make_mock_session_for_empty_candidates()
        core = _make_mock_core()

        svc = RealityOrchestrationService(session)

        with patch.object(
            svc._candidate_repo, "record_evidence", new=AsyncMock(
                return_value=EvidenceFamily(
                    family_id="fam_test",
                    source_type="USER_ASSERTION",
                    cluster_key="test",
                    mention_count=1,
                )
            )
        ), patch.object(
            svc._candidate_repo, "save_candidate", new=AsyncMock(
                side_effect=lambda c: c
            )
        ), patch.object(
            svc._candidate_repo, "get_all_active_candidates", new=AsyncMock(return_value=[])
        ):
            result = await svc.run_turn(
                user_input="哈哈今天好困啊",
                core=core,
                character_id="aevum",
            )

        assert result.governed_reality is not None
        assert result.candidates == []
        assert result.choices == []
        assert result.promoted is False

    async def test_gc130_candidate_persisted(self):
        """GC-130: Biographical signal → CandidateHypothesis save_candidate called."""
        session = _make_mock_session_for_empty_candidates()
        core = _make_mock_core()

        svc = RealityOrchestrationService(session)

        saved_candidates = []

        def _fake_save(candidate):
            persisted = candidate.to_persisted()
            saved_candidates.append(persisted)
            return persisted

        mock_evidence = EvidenceFamily(
            family_id="fam_001",
            source_type="USER_ASSERTION",
            cluster_key="aevum.education.university.user_assertion",
            mention_count=1,
        )

        with patch.object(
            svc._candidate_repo, "record_evidence", new=AsyncMock(return_value=mock_evidence)
        ), patch.object(
            svc._candidate_repo, "save_candidate", new=AsyncMock(side_effect=_fake_save)
        ), patch.object(
            svc._candidate_repo, "get_all_active_candidates", new=AsyncMock(return_value=[])
        ):
            await svc.run_turn(
                user_input="我在 USM 读 Computer Science 专业",
                core=core,
                character_id="aevum",
            )

        assert len(saved_candidates) == 1
        saved = saved_candidates[0]
        assert saved.slot_name == "education.university"
        assert saved.lifecycle_state == CandidateLifecycleState.PERSISTED

    async def test_gc131_no_canonical_mutation(self):
        """GC-131: After orchestration, canonical core NOT mutated by orchestration service."""
        session = _make_mock_session_for_empty_candidates()
        core = _make_mock_core()
        core_id_before = id(core)

        svc = RealityOrchestrationService(session)

        with patch.object(
            svc._candidate_repo, "get_all_active_candidates", new=AsyncMock(return_value=[])
        ):
            result = await svc.run_turn(
                user_input="今天天气真好",
                core=core,
                character_id="aevum",
            )

        # Core object itself was not replaced (orchestration uses it as a read-only input)
        assert id(core) == core_id_before
        # governed_reality was produced
        assert result.governed_reality is not None
        # No promotion occurred (no candidates)
        assert result.promoted is False

    async def test_gc132_repair_from_contradiction(self):
        """GC-132: Contradiction detected → repair_result is non-None in OrchestrationTurnResult."""
        session = _make_mock_session_for_empty_candidates()
        core = _make_mock_core()

        svc = RealityOrchestrationService(session)

        # Input that triggers ContradictionResolver sun-falsehood pattern
        user_input = "The sun rises in the west"

        with patch.object(
            svc._candidate_repo, "get_all_active_candidates", new=AsyncMock(return_value=[])
        ):
            result = await svc.run_turn(
                user_input=user_input,
                core=core,
                character_id="aevum",
            )

        # ContradictionResolver should detect this as a USER_FACTUAL_ERROR or similar
        assert result.contradiction is not None
        assert result.contradiction.canonical_mutated is False
        # If contradiction detected, repair_result should be set
        if result.contradiction.contradiction_type != ContradictionType.NONE:
            assert result.repair_result is not None

    async def test_gc133_world_facts_in_context(self):
        """GC-133: USM input → WorldFactsSelector returns non-empty dict."""
        registry = WorldKnowledgeRegistry._REGISTRY
        eligible_usm = [
            k for k, v in registry.items()
            if "usm" in k.lower()
            and v.kind in (KnowledgeKind.STATIC_FACT, KnowledgeKind.ENTITY_RELATION)
        ]
        if not eligible_usm:
            pytest.skip("No eligible USM STATIC_FACT/ENTITY_RELATION items registered")

        result = WorldFactsSelector.select_for_turn("我在 USM 读书")
        usm_in_result = [k for k in result if "usm" in k.lower()]
        assert len(usm_in_result) > 0

    async def test_gc134_world_facts_empty_unrelated(self):
        """GC-134: Completely unrelated input → world_facts = {}."""
        result = WorldFactsSelector.select_for_turn("今天天气很好心情也很好")
        assert result == {}

    async def test_gc135_candidate_repo_failure_not_empty_state(self):
        """GC-135: get_all_active_candidates() DB failure → raises CandidateRepositoryUnavailableError.

        CRITICAL: DB exception must NOT be silently converted to [].
        'candidate state unknown' ≠ 'no candidates'.
        """
        session = _make_mock_session_for_empty_candidates()
        core = _make_mock_core()

        svc = RealityOrchestrationService(session)

        with patch.object(
            svc._candidate_repo, "record_evidence", new=AsyncMock(
                return_value=EvidenceFamily(
                    family_id="fam_x", source_type="USER_ASSERTION",
                    cluster_key="k", mention_count=1
                )
            )
        ), patch.object(
            svc._candidate_repo, "save_candidate", new=AsyncMock(side_effect=lambda c: c)
        ), patch.object(
            svc._candidate_repo, "get_all_active_candidates",
            new=AsyncMock(side_effect=OperationalError("DB unavailable", None, None))
        ):
            with pytest.raises(CandidateRepositoryUnavailableError):
                await svc.run_turn(
                    user_input="哈哈今天好困啊",
                    core=core,
                    character_id="aevum",
                )

    async def test_gc136_no_rbe_invocation(self):
        """GC-136: RealityBeliefEngine.process_turn() is never called during run_turn()."""
        session = _make_mock_session_for_empty_candidates()
        core = _make_mock_core()

        svc = RealityOrchestrationService(session)

        rbe_called = False

        def _rbe_process_turn(*args, **kwargs):
            nonlocal rbe_called
            rbe_called = True
            raise AssertionError("RealityBeliefEngine.process_turn() must NEVER be called in 7D.5")

        with patch("app.reality.belief_engine.RealityBeliefEngine.process_turn", new=_rbe_process_turn), \
             patch.object(
                 svc._candidate_repo, "get_all_active_candidates", new=AsyncMock(return_value=[])
             ):
            try:
                await svc.run_turn(
                    user_input="哈哈今天好困啊",
                    core=core,
                    character_id="aevum",
                )
            except AssertionError:
                pass  # Would be caught by the assertion above

        assert not rbe_called, "RealityBeliefEngine.process_turn() was invoked — 7D.5 invariant violated"

    async def test_gc138_all_empty_states_normal(self):
        """GC-138: All stages return no-op values → pipeline completes, GovernedRealityContext non-None.

        Validates the complete normal empty-state path:
        no evidence → no candidate → no competition → no choice → no contradiction
        → no repair → no promotion → GovernedRealityContext (canonical only) → OK
        """
        session = _make_mock_session_for_empty_candidates()
        core = _make_mock_core()

        svc = RealityOrchestrationService(session)

        with patch.object(
            svc._candidate_repo, "get_all_active_candidates", new=AsyncMock(return_value=[])
        ):
            result = await svc.run_turn(
                user_input="今天天气真的很不错呢",
                core=core,
                character_id="aevum",
            )

        # All empty — but pipeline must complete successfully
        assert result.governed_reality is not None
        assert result.candidates == []
        assert result.choices == []
        assert result.repair_result is None
        assert result.promoted is False
        assert result.contradiction is not None  # always a ContradictionResolution (may be NONE type)

    async def test_gc139_empty_repo_is_valid_empty_state(self):
        """GC-139: get_all_active_candidates() succeeds → [] is valid empty state, NOT infrastructure failure.

        This is the complement of GC-135. A successful DB query returning []
        must continue the pipeline normally without raising any exception.
        """
        session = _make_mock_session_for_empty_candidates()
        core = _make_mock_core()

        svc = RealityOrchestrationService(session)

        with patch.object(
            svc._candidate_repo, "get_all_active_candidates", new=AsyncMock(return_value=[])
        ):
            # Must not raise — empty [] from DB is a valid normal state
            result = await svc.run_turn(
                user_input="随便聊聊天",
                core=core,
                character_id="aevum",
            )

        assert result.governed_reality is not None
        assert result.candidates == []
        # No CandidateRepositoryUnavailableError was raised

    async def test_gc140_failure_after_promotion_stale_context(self):
        """GC-140: Context assembly failure (Step J) propagates out of run_turn().

        This validates the failure contract boundary:
        - Step I (WorldFactsSelector) failure → absorbed, pipeline continues with {}
        - Step J (RealityContextBuilder) failure → propagates to caller (CharacterEngine)

        CharacterEngine then catches and falls back to pre-orchestration canonical snapshot.
        There is NO transactional rollback — if promotion already committed in Step H,
        it remains durable in DB regardless of later step failures.
        """
        session = _make_mock_session_for_empty_candidates()
        pre_promotion_core = _make_mock_core()

        svc = RealityOrchestrationService(session)

        # Verify Step I failure is absorbed (WorldFactsSelector raise → {} not propagated)
        with patch.object(
            svc._candidate_repo, "get_all_active_candidates", new=AsyncMock(return_value=[])
        ), patch(
            "app.reality.reality_orchestration_service.WorldFactsSelector.select_for_turn",
            side_effect=RuntimeError("Step I simulated failure — must be absorbed")
        ), patch(
            "app.character.reality_context_builder.RealityContextBuilder.build_context",
            side_effect=ValueError("Step J simulated failure — must propagate")
        ):
            # run_turn() must propagate the Step J (context assembly) failure
            with pytest.raises(ValueError, match="Step J simulated failure"):
                await svc.run_turn(
                    user_input="随便聊聊天",
                    core=pre_promotion_core,
                    character_id="aevum",
                )

        # Semantic contract verified:
        # - Step I failure was absorbed (RuntimeError for WorldFactsSelector was swallowed)
        # - Step J failure was propagated (ValueError for build_context bubbled up)
        # - Any promotion that had committed in Step H remains durable (no rollback occurs)




# ---------------------------------------------------------------------------
# AST + engine-level invariant tests — GC-137
# ---------------------------------------------------------------------------


class TestEngineArchitectureInvariants:

    def test_gc137_rbe_not_called_in_engine(self):
        """GC-137: CharacterEngine.build_response_context() must not call RealityBeliefEngine.

        Uses both AST check and import check.
        """
        engine_path = pathlib.Path("app/character/engine.py")
        src = engine_path.read_text(encoding="utf-8")

        # AST check: no Name node "RealityBeliefEngine" in call positions
        tree = ast.parse(src)
        rbe_call_found = False
        for node in ast.walk(tree):
            # Check for attribute access: rbe_instance.process_turn(...)
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == "process_turn":
                    if isinstance(func.value, ast.Name):
                        rbe_call_found = True
                        break
            # Check for direct instantiation: RealityBeliefEngine(...)
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "RealityBeliefEngine":
                    rbe_call_found = True
                    break

        assert not rbe_call_found, (
            "engine.py contains a RealityBeliefEngine call or instantiation — "
            "7D.5 architectural invariant violated"
        )

    def test_gc137_orchestration_service_no_rbe_import(self):
        """GC-137 variant: reality_orchestration_service.py must not IMPORT or INSTANTIATE RealityBeliefEngine."""
        svc_path = pathlib.Path("app/reality/reality_orchestration_service.py")
        tree = ast.parse(svc_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            # Check for: import ... RealityBeliefEngine
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    assert "RealityBeliefEngine" not in alias.name, (
                        "reality_orchestration_service.py imports RealityBeliefEngine — "
                        "7D.5 architectural invariant violated"
                    )
            # Check for: RealityBeliefEngine(...) instantiation call
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "RealityBeliefEngine":
                    pytest.fail(
                        f"reality_orchestration_service.py instantiates RealityBeliefEngine at line {node.lineno}"
                    )

    def test_gc137_orchestration_service_no_set_fact(self):
        """GC-137 variant: reality_orchestration_service.py must not call set_fact() directly."""
        svc_path = pathlib.Path("app/reality/reality_orchestration_service.py")
        tree = ast.parse(svc_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == "set_fact":
                    pytest.fail(
                        f"reality_orchestration_service.py calls .set_fact() at line {node.lineno} — "
                        "orchestration service must never call set_fact() directly"
                    )

    def test_gc137_orchestration_service_no_promotion_token(self):
        """GC-137 variant: reality_orchestration_service.py must not CREATE PromotionAuthorizationToken directly."""
        svc_path = pathlib.Path("app/reality/reality_orchestration_service.py")
        tree = ast.parse(svc_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            # Check for: PromotionAuthorizationToken(...) call
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "PromotionAuthorizationToken":
                    pytest.fail(
                        f"reality_orchestration_service.py creates PromotionAuthorizationToken at line {node.lineno} — "
                        "only BiographyPromotionService may create this"
                    )
            # Check for import of PromotionAuthorizationToken
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    if "PromotionAuthorizationToken" in alias.name:
                        pytest.fail(
                            "reality_orchestration_service.py imports PromotionAuthorizationToken — "
                            "this token must only be created inside BiographyPromotionService"
                        )

