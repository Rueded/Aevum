"""Phase 14.3 — Reality Construction Orchestrator & Governance Gate Tests.

Tests cover:
  1. CycleIsolationLedger (Lock 12: in-memory candidate tracking and cycle clearance)
  2. RCLGovernanceGate:
     - Lock 12: same-cycle candidate structurally blocked from promotion
     - Lock 2: earlier-cycle candidate is eligible (eligibility boundary, not promotion condition)
     - Decision D2: velocity cap (max 1 promotion per cycle)
     - Lock 8: canonical fact cannot be demoted or overwritten by construction
  3. RealityConstructionOrchestrator:
     - Full cycle lifecycle: opportunity -> constraint -> hypothesis -> ledger -> persist -> compete -> gate -> promote
     - Lock 12 end-to-end: new candidates generated in cycle N are saved but NOT promoted in cycle N
     - Lock 7: failure isolation (exceptions caught, loop_skipped_reason="RCL_EXCEPTION", no crash)
  4. RCLAdapter (Lock 9: single construction authority, supersedes C2)
  5. Authority boundary AST audit (0 set_fact, 0 token minting, single promotion authority)

Golden Suite 14 Cluster 3: GC-362 ~ GC-366 (5 constitutional acceptance benchmarks)
"""

import ast
from pathlib import Path
from typing import Any, Optional, Sequence
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.character.core_models import CharacterCore
from app.reality.candidate_models import (
    CandidateHypothesis,
    CandidateLifecycleState,
    EvidenceFamily,
    InferenceEdgeType,
    PlausibilityBreakdown,
    ProvenanceLineage,
    RealityTaxonomy,
)
from app.reality.choice_models import ChoiceDecisionResult, CompetitionResult
from app.reality.models import CoreFactItem, FactAuthority, FactSource, FactStatus
from app.reality.rcl_orchestrator import (
    CycleIsolationLedger,
    GovernanceGateResult,
    RCLAdapter,
    RCLGovernanceGate,
    RealityConstructionOrchestrator,
)
from app.reality.rcl_scheduler import (
    RCLCycleContext,
    RCLCycleResult,
    RCLScheduler,
    RCLTriggerKind,
)


# ---------------------------------------------------------------------------
# Helpers & Fixtures
# ---------------------------------------------------------------------------

def _make_candidate(
    cid: str,
    slot: str = "education.major",
    val: str = "Computer Science",
    lifecycle: CandidateLifecycleState = CandidateLifecycleState.GENERATED,
) -> CandidateHypothesis:
    plausibility = PlausibilityBreakdown.create(
        prior_weight=0.5,
        evidence_grounding_score=0.8,
        coherence_score=0.9,
        utility_score=0.7,
        composite_plausibility_score=0.75,
    )
    provenance = ProvenanceLineage(
        origin_id="test_origin",
        parent_candidate_ids=(),
        evidence_family_ids=(),
        inference_depth=1,
        derivation_path=("test",),
    )
    return CandidateHypothesis(
        candidate_id=cid,
        entity_id="aevum",
        slot_name=slot,
        proposed_value=val,
        reality_taxonomy=RealityTaxonomy.SIMULATED_BIOGRAPHY_FACT,
        inference_depth=1,
        inference_edge_type=InferenceEdgeType.BEHAVIORAL_CORRELATE,
        plausibility=plausibility,
        provenance=provenance,
        evidence_families=(),
        lifecycle_state=lifecycle,
        is_quarantined=False,
    )


def _make_core(
    facts_dict: dict[str, tuple[Any, bool]],  # key -> (value, is_locked)
) -> CharacterCore:
    facts = {}
    for k, (val, locked) in facts_dict.items():
        category = k.split(".")[0]
        authority = FactAuthority.USER_LOCKED if locked else FactAuthority.AEVUM_CANONICAL
        facts[k] = CoreFactItem(
            key=k,
            value=val,
            category=category,
            source=FactSource.SYSTEM_BASELINE,
            authority=authority,
            status=FactStatus.CANONICAL,
            locked=locked,
        )
    return CharacterCore(character_id="aevum", facts=facts)


# ---------------------------------------------------------------------------
# 1. CycleIsolationLedger Tests (Lock 12)
# ---------------------------------------------------------------------------

class TestCycleIsolationLedger:
    """Gate 1: Ephemeral ledger tracks candidates per cycle and clears properly."""

    def test_record_and_query_cycle_candidates(self):
        ledger = CycleIsolationLedger()
        ledger.record_generated_candidates("cycle-1", ["cand_a", "cand_b"])

        assert ledger.is_generated_in_current_cycle("cycle-1", "cand_a") is True
        assert ledger.is_generated_in_current_cycle("cycle-1", "cand_b") is True
        assert ledger.is_generated_in_current_cycle("cycle-1", "cand_c") is False

    def test_distinct_cycles_are_isolated(self):
        ledger = CycleIsolationLedger()
        ledger.record_generated_candidates("cycle-1", ["cand_a"])
        ledger.record_generated_candidates("cycle-2", ["cand_b"])

        assert ledger.is_generated_in_current_cycle("cycle-1", "cand_a") is True
        assert ledger.is_generated_in_current_cycle("cycle-1", "cand_b") is False
        assert ledger.is_generated_in_current_cycle("cycle-2", "cand_b") is True

    def test_clear_cycle_purges_only_target_cycle(self):
        ledger = CycleIsolationLedger()
        ledger.record_generated_candidates("cycle-1", ["cand_a"])
        ledger.record_generated_candidates("cycle-2", ["cand_b"])

        ledger.clear_cycle("cycle-1")
        assert ledger.is_generated_in_current_cycle("cycle-1", "cand_a") is False
        assert ledger.is_generated_in_current_cycle("cycle-2", "cand_b") is True


# ---------------------------------------------------------------------------
# 2. RCLGovernanceGate Tests (Lock 2, Lock 12, Velocity Cap D2, Lock 8)
# ---------------------------------------------------------------------------

class TestRCLGovernanceGate:
    """Gate 2: Constitutional governance gates on candidate promotion."""

    def test_lock_12_same_cycle_candidate_is_structurally_blocked(self):
        ledger = CycleIsolationLedger()
        ledger.record_generated_candidates("cycle-100", ["cand_new"])
        gate = RCLGovernanceGate(ledger=ledger)

        cand = _make_candidate("cand_new")
        result = gate.evaluate(
            candidate=cand,
            current_cycle_id="cycle-100",
            promotions_in_current_cycle=0,
        )

        assert result.is_eligible is False
        assert result.lock_rule_id == "LOCK_12_SAME_CYCLE_BLOCKED"
        assert "Lock 12" in result.reason

    def test_lock_2_earlier_cycle_candidate_is_eligible_boundary(self):
        ledger = CycleIsolationLedger()
        # Candidate was generated in cycle-99, current cycle is cycle-100
        ledger.record_generated_candidates("cycle-99", ["cand_prior"])
        gate = RCLGovernanceGate(ledger=ledger)

        cand = _make_candidate("cand_prior")
        result = gate.evaluate(
            candidate=cand,
            current_cycle_id="cycle-100",
            promotions_in_current_cycle=0,
            core=_make_core({}),  # Empty core, compatible
        )

        assert result.is_eligible is True
        assert result.lock_rule_id is None

    def test_lock_2_prior_cycle_candidate_fails_when_current_canonical_premises_contradict(self):
        """Lock 2: Candidate age alone is NOT an authorization for promotion.

        If a candidate from cycle N-1 is evaluated in cycle N, but the current
        canonical snapshot has changed such that it now violates a hard constraint,
        fresh re-evaluation MUST reject it.
        """
        ledger = CycleIsolationLedger()
        ledger.record_generated_candidates("cycle-99", ["cand_mining"])
        gate = RCLGovernanceGate(ledger=ledger)

        # In cycle 99, cand_mining was proposed for education.major="Mining Engineering"
        cand = _make_candidate("cand_mining", slot="education.major", val="Mining Engineering")

        # In cycle 100, the user has since locked education.major to "Computer Science"
        core_with_locked_cs = _make_core({"education.major": ("Computer Science", True)})

        result = gate.evaluate(
            candidate=cand,
            current_cycle_id="cycle-100",
            promotions_in_current_cycle=0,
            core=core_with_locked_cs,
        )

        # MUST be rejected due to independent re-evaluation failure against CURRENT premises!
        assert result.is_eligible is False
        assert result.lock_rule_id == "LOCK_2_RE_EVALUATION_FAILED"
        assert "Lock 2" in result.reason

    def test_decision_d2_velocity_cap_blocks_second_promotion(self):
        ledger = CycleIsolationLedger()
        gate = RCLGovernanceGate(ledger=ledger)

        cand = _make_candidate("cand_prior")
        result = gate.evaluate(
            candidate=cand,
            current_cycle_id="cycle-100",
            promotions_in_current_cycle=1,  # Already 1 promotion in this cycle
        )

        assert result.is_eligible is False
        assert result.lock_rule_id == "DECISION_D2_VELOCITY_CAP"
        assert "Velocity cap" in result.reason

    def test_lock_8_canonical_demotion_blocked(self):
        ledger = CycleIsolationLedger()
        gate = RCLGovernanceGate(ledger=ledger)

        # Core already has canonical major "Physics"
        core = _make_core({"education.major": ("Physics", False)})
        cand = _make_candidate("cand_diff", slot="education.major", val="Philosophy")

        result = gate.evaluate(
            candidate=cand,
            current_cycle_id="cycle-100",
            promotions_in_current_cycle=0,
            core=core,
        )

        assert result.is_eligible is False
        assert result.lock_rule_id == "LOCK_8_CANONICAL_DEMOTION_BLOCKED"


# ---------------------------------------------------------------------------
# 3. RealityConstructionOrchestrator Lifecycle Tests
# ---------------------------------------------------------------------------

class TestRealityConstructionOrchestrator:
    """Gate 3: Full RCL sequence execution, Lock 12 generation isolation & Lock 7 failure isolation."""

    @pytest.mark.asyncio
    async def test_no_opportunity_completes_cleanly(self):
        session = AsyncMock()
        repo = AsyncMock()
        repo.get_all_active_candidates.return_value = []

        detector = MagicMock()
        detector.detect_opportunity.return_value = None

        scheduler = RCLScheduler(debug_bypass_enabled=True)
        orchestrator = RealityConstructionOrchestrator(
            session=session,
            candidate_repo=repo,
            scheduler=scheduler,
            detector=detector,
        )

        core = _make_core({})
        result = await orchestrator.run_rcl_cycle(
            character_id="aevum",
            core=core,
            trigger_kind=RCLTriggerKind.MANUAL_DEBUG,
        )

        assert result.candidates_generated == 0
        assert result.candidates_promoted == 0
        assert result.loop_skipped_reason is None

    @pytest.mark.asyncio
    async def test_newly_generated_candidates_not_promoted_in_same_cycle(self):
        """Lock 12: New candidates generated in cycle N are saved but NOT promoted in cycle N."""
        session = AsyncMock()
        repo = AsyncMock()
        repo.get_all_active_candidates.return_value = []

        # Opportunity detector returns a valid request
        mock_req = MagicMock()
        mock_req.target_slot = "education.major"
        mock_req.inference_cycle_id = "test_cycle"
        detector = MagicMock()
        detector.detect_opportunity.return_value = mock_req

        # Proposer returns 2 candidate envelopes
        env1 = MagicMock()
        env1.proposed_value = "Computer Science"
        env2 = MagicMock()
        env2.proposed_value = "Information Systems"
        proposer = MagicMock()
        proposer.propose_hypotheses.return_value = [env1, env2]

        cand1 = _make_candidate("cand_cs_new", val="Computer Science")
        cand2 = _make_candidate("cand_is_new", val="Information Systems")
        evaluator = MagicMock()
        evaluator.evaluate_envelopes.return_value = [cand1, cand2]

        # After saving, get_active_candidates_for_slot returns these new candidates
        repo.get_active_candidates_for_slot.return_value = [cand1, cand2]

        # Competition selects cand1 as winner
        comp_service = MagicMock()
        comp_res = MagicMock()
        comp_res.leading_candidate = cand1
        comp_service.compete_slot.return_value = comp_res

        choice_service = MagicMock()
        choice_res = MagicMock()
        choice_res.chosen_candidate = cand1
        choice_service.select_choice.return_value = choice_res

        # Promotion service mock
        promo_service = AsyncMock()

        scheduler = RCLScheduler(debug_bypass_enabled=True)
        orchestrator = RealityConstructionOrchestrator(
            session=session,
            candidate_repo=repo,
            scheduler=scheduler,
            detector=detector,
            proposer=proposer,
            evaluator=evaluator,
            competition_service=comp_service,
            choice_service=choice_service,
            promotion_service=promo_service,
        )

        core = _make_core({})
        result = await orchestrator.run_rcl_cycle(
            character_id="aevum",
            core=core,
            trigger_kind=RCLTriggerKind.MANUAL_DEBUG,
        )

        # 2 candidates generated
        assert result.candidates_generated == 2
        # BUT 0 promoted (Lock 12: same-cycle promotion blocked!)
        assert result.candidates_promoted == 0
        assert result.candidates_suppressed == 1
        # Promotion service was NEVER called for the same-cycle candidate!
        promo_service.promote_candidate.assert_not_called()

    @pytest.mark.asyncio
    async def test_prior_cycle_candidate_can_be_promoted(self):
        """Lock 2: A candidate from prior cycle CAN be promoted (max 1 per D2)."""
        session = AsyncMock()
        repo = AsyncMock()
        repo.get_all_active_candidates.return_value = []

        mock_req = MagicMock()
        mock_req.target_slot = "education.major"
        detector = MagicMock()
        detector.detect_opportunity.return_value = mock_req

        cand_new1 = _make_candidate("cand_new1")
        cand_new2 = _make_candidate("cand_new2")
        env1 = MagicMock(proposed_value="CS")
        env2 = MagicMock(proposed_value="IS")
        proposer = MagicMock()
        proposer.propose_hypotheses.return_value = [env1, env2]
        evaluator = MagicMock()
        evaluator.evaluate_envelopes.return_value = [cand_new1, cand_new2]

        # Prior cycle candidate already in DB
        cand_prior = _make_candidate("cand_prior_winner", val="Data Science")
        # get_active_candidates_for_slot returns prior candidate + new candidates
        repo.get_active_candidates_for_slot.return_value = [cand_prior, cand_new1, cand_new2]

        # Competition selects cand_prior as winner
        comp_service = MagicMock()
        comp_res = MagicMock()
        comp_res.leading_candidate = cand_prior
        comp_service.compete_slot.return_value = comp_res

        choice_service = MagicMock()
        choice_res = MagicMock()
        choice_res.chosen_candidate = cand_prior
        choice_service.select_choice.return_value = choice_res

        promo_service = AsyncMock()
        promo_service.promote_candidate.return_value = MagicMock()  # success record

        scheduler = RCLScheduler(debug_bypass_enabled=True)
        orchestrator = RealityConstructionOrchestrator(
            session=session,
            candidate_repo=repo,
            scheduler=scheduler,
            detector=detector,
            proposer=proposer,
            evaluator=evaluator,
            competition_service=comp_service,
            choice_service=choice_service,
            promotion_service=promo_service,
        )

        core = _make_core({})
        result = await orchestrator.run_rcl_cycle(
            character_id="aevum",
            core=core,
            trigger_kind=RCLTriggerKind.MANUAL_DEBUG,
        )

        assert result.candidates_generated == 2
        # Prior cycle candidate is promoted!
        assert result.candidates_promoted == 1
        promo_service.promote_candidate.assert_called_once_with(
            candidate_id="cand_prior_winner",
            choice_result=choice_res,
            character_id="aevum",
        )

    @pytest.mark.asyncio
    async def test_lock_7_failure_isolation_does_not_crash(self):
        """Lock 7: Unexpected exception in cycle body is caught and returns skipped result."""
        session = AsyncMock()
        repo = AsyncMock()
        # Simulate unexpected DB failure
        repo.get_all_active_candidates.side_effect = RuntimeError("Database connection lost")

        scheduler = RCLScheduler(debug_bypass_enabled=True)
        orchestrator = RealityConstructionOrchestrator(
            session=session,
            candidate_repo=repo,
            scheduler=scheduler,
        )

        core = _make_core({})
        # Must not raise RuntimeError
        result = await orchestrator.run_rcl_cycle(
            character_id="aevum",
            core=core,
            trigger_kind=RCLTriggerKind.MANUAL_DEBUG,
        )

        assert result.loop_skipped_reason == "RCL_EXCEPTION"
        assert "Database connection lost" in (result.exception_detail or "")
        # Character lock must be released
        assert scheduler.is_character_locked("aevum") is False


# ---------------------------------------------------------------------------
# 4. RCLAdapter Tests (Lock 9: One Construction Authority)
# ---------------------------------------------------------------------------

class TestRCLAdapter:
    """Gate 4: RCLAdapter bridges into reality orchestration without competing paths."""

    @pytest.mark.asyncio
    async def test_adapter_delegates_to_orchestrator(self):
        orchestrator = AsyncMock()
        cand = _make_candidate("cand-1")
        orchestrator._candidate_repo.get_all_active_candidates.return_value = [cand]

        result_mock = MagicMock()
        result_mock.loop_skipped_reason = None
        result_mock.candidates_generated = 2
        orchestrator.run_rcl_cycle.return_value = result_mock

        adapter = RCLAdapter(orchestrator=orchestrator)
        core = _make_core({})

        candidates = await adapter.coordinate_post_turn(core, character_id="aevum")
        assert len(candidates) == 1
        assert candidates[0].candidate_id == "cand-1"
        orchestrator.run_rcl_cycle.assert_called_once_with(
            character_id="aevum",
            core=core,
            trigger_kind=RCLTriggerKind.POST_CONVERSATION,
        )

    @pytest.mark.asyncio
    async def test_adapter_returns_empty_when_cycle_skipped(self):
        orchestrator = AsyncMock()
        result_mock = MagicMock()
        result_mock.loop_skipped_reason = "COOLDOWN_ACTIVE"
        result_mock.candidates_generated = 0
        orchestrator.run_rcl_cycle.return_value = result_mock

        adapter = RCLAdapter(orchestrator=orchestrator)
        core = _make_core({})

        candidates = await adapter.coordinate_post_turn(core, character_id="aevum")
        assert candidates == ()

    @pytest.mark.asyncio
    async def test_lock_9_orchestration_service_wires_rcl_adapter_as_sole_inference_coordinator(self):
        """Lock 9: When rcl_adapter is supplied, RealityOrchestrationService executes it exclusively."""
        from app.reality.reality_orchestration_service import RealityOrchestrationService
        session = AsyncMock()
        adapter_mock = AsyncMock()
        adapter_mock.run_inference_cycle.return_value = ()

        svc = RealityOrchestrationService(
            session=session,
            rcl_adapter=adapter_mock,
        )

        assert svc._inference_coordinator is adapter_mock


# ---------------------------------------------------------------------------
# 5. Authority Boundary AST Audit
# ---------------------------------------------------------------------------

class TestRCLOrchestratorAuthorityBoundary:
    """Gate 5: rcl_orchestrator.py must not reference forbidden symbols."""

    _FORBIDDEN_NAMES = {
        "set_fact",
        "PromotionAuthorizationToken",
    }

    def _load_ast(self) -> ast.Module:
        path = Path(__file__).parent.parent / "app" / "reality" / "rcl_orchestrator.py"
        return ast.parse(path.read_text(encoding="utf-8"))

    def test_no_forbidden_mutation_calls(self):
        tree = self._load_ast()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in self._FORBIDDEN_NAMES:
                pytest.fail(f"Forbidden name '{node.id}' in rcl_orchestrator.py AST")
            elif isinstance(node, ast.Attribute) and node.attr in self._FORBIDDEN_NAMES:
                pytest.fail(f"Forbidden attribute '{node.attr}' in rcl_orchestrator.py AST")


# ---------------------------------------------------------------------------
# 6. Golden Suite 14 — Cluster 3: GC-362 ~ GC-366
# ---------------------------------------------------------------------------

class TestGoldenSuite14Cluster3:
    """GC-362 ~ GC-366 — Constitutional acceptance benchmarks for Phase 14.3."""

    def test_gc362_lock_12_same_cycle_promotion_structurally_blocked(self):
        """GC-362: Candidate generated in cycle N cannot be promoted in cycle N."""
        ledger = CycleIsolationLedger()
        ledger.record_generated_candidates("cycle-42", ["cand-x"])
        gate = RCLGovernanceGate(ledger=ledger)

        cand = _make_candidate("cand-x")
        res = gate.evaluate(cand, "cycle-42", 0)
        assert res.is_eligible is False
        assert res.lock_rule_id == "LOCK_12_SAME_CYCLE_BLOCKED"

    def test_gc363_lock_2_cycle_isolation_is_eligibility_boundary_not_promotion_condition(self):
        """GC-363: Earlier cycle candidate is eligible boundary, not auto-promoted."""
        ledger = CycleIsolationLedger()
        gate = RCLGovernanceGate(ledger=ledger)

        # Candidate from cycle-41 evaluated in cycle-42
        cand = _make_candidate("cand-prior-41")
        res = gate.evaluate(cand, "cycle-42", 0)
        # Passes gate eligibility
        assert res.is_eligible is True
        # Gate verdict is ELIGIBILITY only — not a canonical mutation

    def test_gc364_decision_d2_velocity_cap_strictly_one_promotion_per_cycle(self):
        """GC-364: Exactly 1 promotion allowed per cycle; second candidate blocked."""
        ledger = CycleIsolationLedger()
        gate = RCLGovernanceGate(ledger=ledger)

        cand = _make_candidate("cand-winner-2")
        res = gate.evaluate(cand, "cycle-42", promotions_in_current_cycle=1)
        assert res.is_eligible is False
        assert res.lock_rule_id == "DECISION_D2_VELOCITY_CAP"

    def test_gc365_lock_9_singular_construction_authority_via_adapter(self):
        """GC-365: RCLAdapter is single entry point, superseding independent C2."""
        orch = MagicMock()
        adapter = RCLAdapter(orchestrator=orch)
        assert adapter._orchestrator is orch

    def test_gc366_lock_7_failure_isolation_degrades_safely(self):
        """GC-366: RCL exception creates skipped result with RCL_EXCEPTION, no crash."""
        scheduler = RCLScheduler(debug_bypass_enabled=True)
        res = scheduler.make_skipped_result(
            character_id="aevum",
            trigger_kind=RCLTriggerKind.POST_CONVERSATION,
            skip_reason="RCL_EXCEPTION",
            exception_detail="Simulated catastrophic error",
        )
        assert res.loop_skipped_reason == "RCL_EXCEPTION"
        assert res.candidates_promoted == 0
        assert res.candidates_generated == 0
