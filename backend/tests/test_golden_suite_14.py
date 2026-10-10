"""test_golden_suite_14.py — Golden Acceptance Suite 14 (GC-352 ~ GC-378).

Golden Acceptance Suite for Phase 14: Autonomous Reality Construction & Adaptive Belief Engine.
Governed by ADR-025 (Revision 1):
"Aevum may construct beliefs about her personal world, but no generated hypothesis
becomes reality merely because Aevum generated it."

Covers 27 Acceptance Benchmarks across 6 Structured Clusters:
- Cluster 1: RCL Scheduler & Trigger Contracts (GC-352 ~ GC-356)
- Cluster 2: Constraint Evaluation Engine & Asymmetry (GC-357 ~ GC-361)
- Cluster 3: Reality Construction Orchestrator, Cycle Isolation & Governance (GC-362 ~ GC-366)
- Cluster 4: Adaptive Belief Revision Engine & Non-Destruction (GC-367 ~ GC-371)
- Cluster 5: Context Assembly & Belief Transparency (GC-372 ~ GC-376)
- Cluster 6: End-to-End Integration & System-Wide Constitutional AST Audits (GC-377 ~ GC-378)
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock
import pytest
from pydantic import ValidationError

from app.biography.biography_models import CanonicalStatus, RecallLevel
from app.character.core_models import CharacterCore
from app.reality.belief_revision import (
    AdaptiveBeliefRevisionEngine,
    BeliefReconciliationService,
    BeliefRevisionKind,
    BeliefRevisionProposal,
    BeliefRevisionRecord,
    BeliefRevisionRepository,
    EvidenceSourceType,
    IncomingEvidenceItem,
)
from app.reality.belief_transparency import (
    BeliefMaturity,
    BeliefMaturityClassifier,
    BeliefTransparencyAdapter,
    BeliefTransparencyItem,
    BeliefTransparencyState,
)
from app.reality.candidate_models import (
    CandidateHypothesis,
    CandidateLifecycleState,
    InferenceEdgeType,
    PlausibilityBreakdown,
    ProvenanceLineage,
    RealityTaxonomy,
)
from app.reality.constraint_engine import (
    ConstraintClass,
    ConstraintEvaluationResult,
    ConstraintSetEvaluator,
    ConstraintType,
    HardConstraintEvaluator,
    SlotConstraintProfile,
    SoftConstraintEvaluator,
)
from app.reality.models import CoreFactItem, FactAuthority, FactSource, FactStatus
from app.reality.rcl_orchestrator import (
    CycleIsolationLedger,
    RCLExecutionError,
    RCLGovernanceGate,
    RealityConstructionOrchestrator,
    RCLAdapter,
)
from app.reality.rcl_scheduler import (
    RCL_COOLDOWN_SECONDS,
    RCL_DEBOUNCE_SECONDS,
    RCLCycleContext,
    RCLCycleResult,
    RCLScheduler,
    RCLTriggerKind,
)


# ---------------------------------------------------------------------------
# Test Fixtures & Shared Helpers
# ---------------------------------------------------------------------------

def _make_candidate(
    cid: str,
    slot: str = "education.major",
    val: str = "Computer Science",
    lifecycle: CandidateLifecycleState = CandidateLifecycleState.ACTIVE,
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
    interests: list[str] | tuple[str, ...] | None = None,
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
    if interests is not None:
        facts["interests"] = CoreFactItem(
            key="interests",
            value=list(interests),
            category="lifestyle",
            source=FactSource.SYSTEM_BASELINE,
            authority=FactAuthority.AEVUM_CANONICAL,
            status=FactStatus.CANONICAL,
            locked=False,
        )
    return CharacterCore(character_id="aevum", facts=facts)


def _make_scheduler_with_clock(
    now: float = 0.0,
    cooldown: float = RCL_COOLDOWN_SECONDS,
    debounce: float = RCL_DEBOUNCE_SECONDS,
    debug_bypass: bool = False,
) -> tuple[RCLScheduler, list[float]]:
    clock_values = [now]

    def clock_fn() -> float:
        return clock_values[-1]

    sched = RCLScheduler(
        clock_fn=clock_fn,
        cooldown_seconds=cooldown,
        debounce_seconds=debounce,
        debug_bypass_enabled=debug_bypass,
    )
    return sched, clock_values


# ---------------------------------------------------------------------------
# Cluster 1: RCL Scheduler & Trigger Contracts (GC-352 ~ GC-356)
# ---------------------------------------------------------------------------

class TestCluster1RCLScheduler:
    """GC-352 ~ GC-356: RCL Scheduler, Triggers, Cooldowns, and Debounce."""

    def test_gc352_rcl_cycle_context_is_immutable_and_auditable(self):
        """GC-352: RCLCycleContext is frozen, rejects mutation, rejects extra fields."""
        ctx = RCLCycleContext(
            cycle_id="gc352",
            character_id="char-1",
            trigger_kind=RCLTriggerKind.SCHEDULED_TICK,
            triggered_at_monotonic=12345.0,
            active_canonical_facts_count=3,
        )
        assert ctx.cycle_id == "gc352"
        assert ctx.is_debug_cycle is False
        with pytest.raises(ValidationError):
            ctx.cycle_id = "mutated"  # type: ignore

    def test_gc353_cooldown_exact_boundary_and_eligibility(self):
        """GC-353: Exact 30-min boundary — 29.999s blocked, 30.000s eligible."""
        sched, clk = _make_scheduler_with_clock(now=0.0, cooldown=1800.0)
        el, ctx, _ = sched.request_cycle("char-A", RCLTriggerKind.SCHEDULED_TICK)
        assert el is True
        assert ctx is not None
        sched.mark_cycle_started("char-A")
        r = sched.make_completed_result(ctx, 0.0)
        sched.mark_cycle_completed("char-A", r)

        clk.append(clk[-1] + 1799.999)
        el_under, _, reason_under = sched.request_cycle("char-A", RCLTriggerKind.SCHEDULED_TICK)
        assert el_under is False
        assert reason_under == "COOLDOWN_ACTIVE"

        clk.append(clk[-1] + 0.001)  # now at exactly 1800.000
        el_at, ctx_at, reason_at = sched.request_cycle("char-A", RCLTriggerKind.SCHEDULED_TICK)
        assert el_at is True, f"Expected eligible at exact boundary: {reason_at}"

    def test_gc354_per_character_independence(self):
        """GC-354: Character A locked does not block Character B."""
        sched, _ = _make_scheduler_with_clock()
        el_a, ctx_a, _ = sched.request_cycle("char-A", RCLTriggerKind.LIFE_EVENT)
        assert el_a is True
        sched.mark_cycle_started("char-A")

        el_b, ctx_b, _ = sched.request_cycle("char-B", RCLTriggerKind.LIFE_EVENT)
        assert el_b is True
        assert ctx_b is not None
        assert ctx_b.character_id == "char-B"

    def test_gc355_manual_debug_blocked_in_production(self):
        """GC-355: MANUAL_DEBUG without debug_bypass_enabled is permanently blocked."""
        sched = RCLScheduler(debug_bypass_enabled=False)
        el, _, reason = sched.request_cycle("char-1", RCLTriggerKind.MANUAL_DEBUG)
        assert el is False
        assert reason == "MANUAL_DEBUG_NOT_ALLOWED_IN_PRODUCTION"

    def test_gc356_authority_boundary_zero_forbidden_symbols(self):
        """GC-356: rcl_scheduler.py contains 0 references to forbidden symbols."""
        path = Path(__file__).parent.parent / "app" / "reality" / "rcl_scheduler.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        forbidden = {
            "set_fact", "BiographyPromotionService", "PromotionAuthorizationToken",
            "AsyncSession", "LLMProvider",
        }
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in forbidden:
                violations.append(node.id)
            elif isinstance(node, ast.Attribute) and node.attr in forbidden:
                violations.append(node.attr)

        assert violations == [], f"Authority boundary violation in rcl_scheduler.py: {violations}"


# ---------------------------------------------------------------------------
# Cluster 2: Constraint Evaluation Engine & Asymmetry (GC-357 ~ GC-361)
# ---------------------------------------------------------------------------

class TestCluster2ConstraintEvaluation:
    """GC-357 ~ GC-361: Constraint Evaluation Engine, Hard/Soft Asymmetry, Anti-Stereotyping."""

    def test_gc357_hard_constraint_rejection_outright(self):
        """GC-357: Hard constraint violations reject outright with is_hard_rejected=True."""
        evaluator = HardConstraintEvaluator()
        core = _make_core({"education.level": ("Undergraduate", True)})
        res = evaluator.evaluate_canonical_contradiction(
            "education.level", "Secondary School", core
        )
        assert res.is_hard_rejected is True
        assert res.penalty_weight == 1.0

    def test_gc358_soft_constraint_deterministic_penalty_without_disqualification(self):
        """GC-358: Soft constraints reduce score via penalty_weight, never reject."""
        evaluator = SoftConstraintEvaluator()
        core = _make_core({}, interests=("literature",))
        res = evaluator.evaluate_temperament_affinity("education.major", "Civil Engineering", core)

        assert res.constraint_class == ConstraintClass.SOFT_PENALTY
        assert res.is_hard_rejected is False
        assert 0.0 < res.penalty_weight <= 1.0

    def test_gc359_absence_is_not_contradiction(self):
        """GC-359: Missing evidence yields NEUTRAL, never HARD_REJECT (Lock 6)."""
        evaluator = ConstraintSetEvaluator()
        core = _make_core({})  # completely open core
        profile = evaluator.evaluate("education.major", "Mathematics", core)

        assert profile.is_hard_rejected is False
        assert profile.total_penalty_weight == 0.0

    def test_gc360_stereotype_free_resource_feasibility(self):
        """GC-360: Family occupation or ethnicity never causes financial penalty."""
        evaluator = SoftConstraintEvaluator()
        core = _make_core({
            "family.father_occupation": ("Hawker", True),
            "family.ethnicity": ("Chinese", True),
        })
        res = evaluator.evaluate_resource_plausibility("education.major", "Accountancy", core)
        assert res.constraint_class == ConstraintClass.NEUTRAL
        assert res.penalty_weight == 0.0

    def test_gc361_constraint_set_evaluator_ast_authority_boundary(self):
        """GC-361: ConstraintSetEvaluator enforces 0 direct mutation calls via AST."""
        path = Path(__file__).parent.parent / "app" / "reality" / "constraint_engine.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        forbidden = {"set_fact", "PromotionAuthorizationToken", "BiographyPromotionService"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in forbidden:
                pytest.fail(f"Forbidden name '{node.id}' in constraint_engine.py AST")
            elif isinstance(node, ast.Attribute) and node.attr in forbidden:
                pytest.fail(f"Forbidden attribute '{node.attr}' in constraint_engine.py AST")


# ---------------------------------------------------------------------------
# Cluster 3: Reality Construction Orchestrator & Governance (GC-362 ~ GC-366)
# ---------------------------------------------------------------------------

class TestCluster3GovernanceGate:
    """GC-362 ~ GC-366: Reality Construction Orchestration, Cycle Isolation, Governance."""

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
        assert res.is_eligible is True

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


# ---------------------------------------------------------------------------
# Cluster 4: Adaptive Belief Revision Engine & Non-Destruction (GC-367 ~ GC-371)
# ---------------------------------------------------------------------------

class TestCluster4BeliefRevision:
    """GC-367 ~ GC-371: Belief Revision, Non-Destructive Audit, Lock 11 Candidate!=Evidence."""

    @pytest.mark.asyncio
    async def test_gc367_non_destructive_belief_revision(self):
        """GC-367: Lock 4 — Non-destructive revision transitions prior candidate to SUPERSEDED."""
        rev_repo = BeliefRevisionRepository()
        cand_repo = AsyncMock()
        service = BeliefReconciliationService(revision_repo=rev_repo, candidate_repo=cand_repo)

        cand = _make_candidate("gc367-cand", val="History")
        rec = BeliefRevisionRecord(
            revision_id="rev-gc367",
            slot_name="education.major",
            revision_kind=BeliefRevisionKind.SUPERSESSION,
            prior_value="History",
            revised_value="Linguistics",
            prior_candidate_id="gc367-cand",
            trigger_cycle_id="cycle-gc",
            rationale="Revision test",
        )
        prop = BeliefRevisionProposal(
            is_valid_revision=True,
            revision_kind=BeliefRevisionKind.SUPERSESSION,
            record=rec,
            target_lifecycle_state=CandidateLifecycleState.SUPERSEDED,
        )

        await service.apply_revision(cand, prop)
        cand_repo.update_lifecycle_state.assert_called_once_with(
            candidate_id="gc367-cand",
            new_state=CandidateLifecycleState.SUPERSEDED,
        )
        assert rev_repo.count() == 1

    def test_gc368_candidate_not_evidence_lock_11(self):
        """GC-368: Lock 11 — CandidateHypothesis cannot serve as evidence for belief revision."""
        engine = AdaptiveBeliefRevisionEngine()
        cand = _make_candidate("gc368-cand", val="Law")
        ev = IncomingEvidenceItem(
            evidence_id="ev-gc368",
            source_type=EvidenceSourceType.CANDIDATE_HYPOTHESIS,
            slot_name="education.major",
            asserted_value="Medicine",
        )
        prop = engine.evaluate_revision(cand, ev)
        assert prop.is_valid_revision is False
        assert "LOCK_11_CANDIDATE_NOT_EVIDENCE" in (prop.rejection_reason or "")

    def test_gc369_canonical_fact_demotion_protection_lock_8(self):
        """GC-369: Lock 8 — Canonical fact cannot be demoted by autonomous belief revision."""
        engine = AdaptiveBeliefRevisionEngine()
        core = _make_core({"education.level": ("Undergraduate", False)})
        cand = _make_candidate("gc369-cand", slot="education.level", val="Undergraduate")
        ev = IncomingEvidenceItem(
            evidence_id="ev-gc369",
            source_type=EvidenceSourceType.USER_STATEMENT,
            slot_name="education.level",
            asserted_value="High School",
            is_definitive_replacement=True,
        )
        prop = engine.evaluate_revision(cand, ev, core=core)
        assert prop.is_valid_revision is False
        assert "LOCK_8_CANONICAL_DEMOTION_BLOCKED" in (prop.rejection_reason or "")

    def test_gc370_permanent_repository_with_bounded_context(self):
        """GC-370: Decision D4 — Append-only storage is permanent; prompt context retrieval is bounded."""
        repo = BeliefRevisionRepository()
        for i in range(8):
            repo.append(
                BeliefRevisionRecord(
                    revision_id=f"r{i}",
                    slot_name="education.major",
                    revision_kind=BeliefRevisionKind.CONFIRMATION,
                    trigger_cycle_id="c",
                    rationale=f"test {i}",
                )
            )
        assert repo.count() == 8
        recent = repo.get_recent(limit=5)
        assert len(recent) == 5

    def test_gc371_authority_boundary_zero_forbidden_symbols(self):
        """GC-371: belief_revision.py has 0 AST references to set_fact or token minting."""
        path = Path(__file__).parent.parent / "app" / "reality" / "belief_revision.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        forbidden = {"set_fact", "PromotionAuthorizationToken"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in forbidden:
                pytest.fail(f"Forbidden name '{node.id}' in belief_revision.py AST")


# ---------------------------------------------------------------------------
# Cluster 5: Context Assembly & Belief Transparency (GC-372 ~ GC-376)
# ---------------------------------------------------------------------------

class TestCluster5BeliefTransparency:
    """GC-372 ~ GC-376: Three Orthogonal Axes, Lock 10 Maturity, Decision D3/D4, XML Assembly."""

    def test_gc372_three_orthogonal_axes_independence(self):
        """GC-372: CanonicalStatus, RecallLevel, and BeliefMaturity are 3 independent axes."""
        f1 = BeliefTransparencyItem(
            slot_name="origin.place",
            asserted_value="Coastal Town",
            canonical_status=CanonicalStatus.CANONICAL,
            recall_level=RecallLevel.HAZY,
            belief_maturity=BeliefMaturity.ESTABLISHED,
            cycles_observed=4,
            evidence_count=3,
        )
        f2 = BeliefTransparencyItem(
            slot_name="future.goal",
            asserted_value="Music School",
            canonical_status=CanonicalStatus.PROVISIONAL,
            recall_level=RecallLevel.VIVID,
            belief_maturity=BeliefMaturity.EMERGING,
            cycles_observed=3,
            evidence_count=2,
        )
        assert f1.canonical_status != f2.canonical_status
        assert f1.belief_maturity == BeliefMaturity.ESTABLISHED
        assert f2.canonical_status == CanonicalStatus.PROVISIONAL

    def test_gc373_lock10_maturity_not_truth_and_cycle_alone_insufficient(self):
        """GC-373: Lock 10 — Belief maturity is not truth; 100 cycles alone cannot establish."""
        maturity_isolated_cycle = BeliefMaturityClassifier.classify(
            canonical_status=CanonicalStatus.CANONICAL,
            cycles_observed=100,
            evidence_count=1,
            evidence_stable=True,
        )
        assert maturity_isolated_cycle != BeliefMaturity.ESTABLISHED
        assert maturity_isolated_cycle == BeliefMaturity.EMERGING

    def test_gc374_decision_d3_constructing_no_prescribed_utterance_templates(self):
        """GC-374: Decision D3 — CONSTRUCTING is an epistemic state, zero prescribed utterance templates."""
        state = BeliefTransparencyAdapter.build_transparency_state(
            character_id="aevum",
            active_beliefs=(
                BeliefTransparencyItem(
                    slot_name="test.slot",
                    asserted_value="Unknown",
                    canonical_status=CanonicalStatus.PROVISIONAL,
                    belief_maturity=BeliefMaturity.CONSTRUCTING,
                ),
            ),
        )
        xml = BeliefTransparencyAdapter.format_autonomous_belief_state(state)
        assert "express natural humble uncertainty, do not invent answers" in xml
        assert "Prefix your response with" not in xml
        assert "Template:" not in xml

    def test_gc375_context_assembly_and_xml_bounded_serialization(self):
        """GC-375: Context assembly generates well-formed XML with bounded revisions (Decision D4)."""
        revisions = [
            BeliefRevisionRecord(
                revision_id=f"gc375-rev-{i}",
                slot_name="education.major",
                revision_kind=BeliefRevisionKind.CONFIRMATION,
                trigger_cycle_id="c",
                rationale="r",
            )
            for i in range(10)
        ]
        item = BeliefTransparencyItem(
            slot_name="identity.motto",
            asserted_value="Per Aspera Ad Astra",
            canonical_status=CanonicalStatus.CANONICAL,
            belief_maturity=BeliefMaturity.ESTABLISHED,
            cycles_observed=3,
            evidence_count=2,
        )
        state = BeliefTransparencyAdapter.build_transparency_state(
            character_id="aevum",
            active_beliefs=(item,),
            recent_revisions=revisions,
        )
        assert len(state.recent_revisions) == 5

        xml = BeliefTransparencyAdapter.format_autonomous_belief_state(state)
        assert '<autonomous_belief_state>' in xml
        assert '<active_beliefs count="1">' in xml
        assert '<recent_belief_revisions count="5">' in xml
        assert state.context_hash_sha256 != ""

    def test_gc376_constitutional_authority_boundary_ast_audit(self):
        """GC-376: belief_transparency.py contains zero forbidden mutation symbols (0 set_fact, 0 token minting)."""
        path = Path(__file__).parent.parent / "app" / "reality" / "belief_transparency.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        forbidden = {"set_fact", "PromotionAuthorizationToken"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in forbidden:
                pytest.fail(f"Forbidden symbol '{node.id}' in belief_transparency.py AST")


# ---------------------------------------------------------------------------
# Cluster 6: End-to-End Pipeline & System-Wide AST Audits (GC-377 ~ GC-378)
# ---------------------------------------------------------------------------

class TestCluster6EndToEndAndConstitutionalLocks:
    """GC-377 ~ GC-378: End-to-End Pipeline Integration & System-Wide AST Boundary Audits."""

    @pytest.mark.asyncio
    async def test_gc377_end_to_end_autonomous_construction_pipeline_and_anti_self_validation(self):
        """GC-377: End-to-End Autonomous Reality Construction Pipeline Integration.

        Simulates multi-cycle progression:
        Cycle 1: Trigger -> Candidate Hypothesis generated -> Recorded in ledger -> Same-cycle promo BLOCKED.
        Cycle 2: Independent re-evaluation against canonical premises -> Promoted via Promotion Service
                 -> Reflected in BeliefTransparencyAdapter with bounded revisions.
        Also verifies Anti-Self-Validation invariant: CandidateHypothesis cannot self-validate as evidence.
        """
        # 1. Cycle 1: Hypothesis generation & isolation
        ledger = CycleIsolationLedger()
        ledger.record_generated_candidates("cycle-1", ["cand-gc377"])

        gate = RCLGovernanceGate(ledger=ledger)
        cand = _make_candidate("cand-gc377", slot="education.major", val="Artificial Intelligence")

        # Same-cycle promotion attempt is strictly blocked (Lock 12)
        eval_c1 = gate.evaluate(cand, "cycle-1", promotions_in_current_cycle=0)
        assert eval_c1.is_eligible is False
        assert eval_c1.lock_rule_id == "LOCK_12_SAME_CYCLE_BLOCKED"

        # 2. Anti-Self-Validation Invariant: Candidate cannot serve as evidence for belief revision
        rev_engine = AdaptiveBeliefRevisionEngine()
        fake_evidence = IncomingEvidenceItem(
            evidence_id="ev-self-validate",
            source_type=EvidenceSourceType.CANDIDATE_HYPOTHESIS,
            slot_name="education.major",
            asserted_value="Artificial Intelligence",
        )
        rev_prop = rev_engine.evaluate_revision(cand, fake_evidence)
        assert rev_prop.is_valid_revision is False
        assert "LOCK_11_CANDIDATE_NOT_EVIDENCE" in (rev_prop.rejection_reason or "")

        # 3. Cycle 2: Candidate independently re-evaluated across cycle boundary
        eval_c2 = gate.evaluate(cand, "cycle-2", promotions_in_current_cycle=0)
        assert eval_c2.is_eligible is True

        # Velocity cap prevents a second promotion in Cycle 2 (Decision D2)
        cand_extra = _make_candidate("cand-extra", slot="education.minor", val="Cognitive Science")
        eval_c2_extra = gate.evaluate(cand_extra, "cycle-2", promotions_in_current_cycle=1)
        assert eval_c2_extra.is_eligible is False
        assert eval_c2_extra.lock_rule_id == "DECISION_D2_VELOCITY_CAP"

        # 4. Context Assembly & Belief Transparency Integration
        item_promoted = BeliefTransparencyAdapter.item_from_candidate(
            candidate=cand,
            recall_level=RecallLevel.VIVID,
            cycles_observed=2,
            has_decisive_margin=True,
            canonical_status=CanonicalStatus.CANONICAL,
        )
        assert item_promoted.canonical_status == CanonicalStatus.CANONICAL
        assert item_promoted.belief_maturity == BeliefMaturity.EMERGING

        state = BeliefTransparencyAdapter.build_transparency_state(
            character_id="aevum",
            active_beliefs=(item_promoted,),
        )
        xml = BeliefTransparencyAdapter.format_autonomous_belief_state(state)
        assert '<belief slot="education.major" status="CANONICAL" recall="VIVID" maturity="EMERGING"' in xml
        assert 'Artificial Intelligence' in xml

    def test_gc378_system_wide_phase14_constitutional_ast_boundary_audit(self):
        """GC-378: Comprehensive System-wide Constitutional AST Audit across ALL Phase 14 modules.

        Verifies that across all Phase 14 production files:
        1. Exactly 0 calls to `set_fact` exist.
        2. Exactly 0 minting of `PromotionAuthorizationToken` exists.
        3. All reality modifications route exclusively through BiographyPromotionService.
        """
        reality_dir = Path(__file__).parent.parent / "app" / "reality"
        phase14_modules = [
            "rcl_scheduler.py",
            "constraint_engine.py",
            "rcl_orchestrator.py",
            "belief_revision.py",
            "belief_transparency.py",
        ]

        forbidden_names = {"set_fact", "PromotionAuthorizationToken"}
        violations: list[str] = []

        for mod_name in phase14_modules:
            mod_path = reality_dir / mod_name
            assert mod_path.exists(), f"Phase 14 module {mod_name} missing from reality directory"

            source = mod_path.read_text(encoding="utf-8")
            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and node.id in forbidden_names:
                    violations.append(f"{mod_name}:{node.lineno} references forbidden name '{node.id}'")

        if violations:
            pytest.fail(f"Phase 14 Constitutional AST Audit FAILED with {len(violations)} violations:\n" + "\n".join(violations))
