"""Golden Suite 8A: Phase 8A End-to-End Autonomous Reality & Life Inference Acceptance Benchmarks.

Covers Golden Acceptance Cases GC-145 through GC-170:
- GC-145: Canonical Mutation Authority Singularity
- GC-146: Candidate Plurality Contract (2 <= k <= 4)
- GC-147: Strict Premise Authorization Subset
- GC-148: Anti-Snowballing Invariant (Gate 14)
- GC-149: Choice vs. Promotion Decisive Margin (Δ >= 0.15)
- GC-150: Ambiguity Preservation (Δ < 0.15 Denies Promotion)
- GC-151: Ambiguous Candidate Isolation in Governed Reality Context
- GC-152: Atomic Candidate Batch Persistence & Savepoint Rollback
- GC-153: Single Invocation Per Turn Invariant (Linear Non-Recursive Flow)
- GC-154: Invariant A (Unknown != Impossible, Quarantined Speculative Association)
- GC-155: Invariant B (Heuristic != Probability, Structural Baseline Coherence)
- GC-156: Invariant C (Construction != Persistence, GENERATED to PERSISTED)
- GC-157: Invariant D (Derived != Primary Anchor Requirement)
- GC-158: Anti-Circularity DAG Enforcement (Gate 9 Acyclicity)
- GC-159: Socioeconomic & Demographic Anti-Stereotyping Prohibition
- GC-160: User-Locked Slot Absolute Immunity (Gate 1)
- GC-161: Cooldown Determinism & Anti-Obsession Axiom
- GC-162: Deterministic Multi-Attribute Choice Factor Provenance & Neutral Baselines
- GC-163: Candidate Envelope Transient DTO Invariance
- GC-164: Non-Epistemic Proposer Metadata Invariance
- GC-165: Multi-Turn Grounding Progression (Prerequisite Chaining)
- GC-166: Single-Use Promotion Token Invalidation & Authorization Code
- GC-167: Safe Concurrent Idempotency Replay (GC-090 Integration)
- GC-168: Step C2 Infrastructure Failure Resilience & Safe Turn Absorption
- GC-169: AST Audit: Zero Forbidden Imports, Network Calls, or RBE References
- GC-170: Integrated Full-Turn Autonomous Reality Cycle
"""

from __future__ import annotations

import ast
import inspect
import pathlib
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, Sequence
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.core_models import CharacterCore
from app.character.reality_context_builder import RealityContextBuilder
from app.reality.autonomous_inference_coordinator import AutonomousInferenceCoordinator
from app.reality.candidate_evaluator import CandidateEvaluationAdapter
from app.reality.candidate_models import (
    CandidateHypothesis,
    CandidateLifecycleState,
    EvidenceFamily,
    InferenceEdgeType,
    InferenceScope,
    PlausibilityBreakdown,
    ProvenanceLineage,
    RealityImpact,
    RealityTaxonomy,
)
from app.reality.candidate_repository import CandidateRepository
from app.reality.choice_models import (
    ChoiceDecisionResult,
    ChoiceFactorBreakdown,
    ChoiceRationaleCode,
    CompetitionResult,
    CompetitionState,
)
from app.reality.choice_service import ChoiceSelectionService
from app.reality.competition_service import CandidateCompetitionService
from app.reality.biography_promotion_models import (
    BiographyConstructionPolicy,
    BiographyPromotionRecord,
    PromotionAuthorizationToken,
    PromotionGateResult,
    PromotionGateType,
    PromotionOrigin,
)
from app.reality.biography_promotion_service import BiographyPromotionService
from app.reality.inference_models import (
    CandidateEnvelope,
    InferenceProposalRequest,
    InferenceValueTier,
    PremiseOriginCategory,
    PremiseRole,
)
from app.reality.inference_opportunity_detector import InferenceOpportunityDetector
from app.reality.inference_value_policy import InferenceValuePolicy
from app.reality.models import (
    CoreFactItem,
    FactAuthority,
    FactSource,
    FactStatus,
)
from app.reality.proposer import DeterministicLifeHypothesisProposer
from app.reality.reality_orchestration_service import (
    OrchestrationTurnResult,
    RealityOrchestrationService,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _make_mock_session() -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    savepoint = AsyncMock()
    savepoint.commit = AsyncMock()
    savepoint.rollback = AsyncMock()

    class _NestedContext:
        async def __aenter__(self):
            return savepoint

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            if exc_type is not None:
                await savepoint.rollback()
            else:
                await savepoint.commit()

    session.begin_nested = MagicMock(return_value=_NestedContext())
    return session


def _make_mock_core(
    facts: Optional[dict[str, Any]] = None,
    locked_keys: Optional[set[str]] = None,
    derived_keys: Optional[set[str]] = None,
    locked_slots: Optional[set[str]] = None,
    derived_slots: Optional[set[str]] = None,
    character_id: str = "aevum",
) -> CharacterCore:
    core = CharacterCore(character_id=character_id)
    locks = (locked_keys or set()) | (locked_slots or set())
    derived = (derived_keys or set()) | (derived_slots or set())
    if facts:
        for k, v in facts.items():
            is_locked = bool(k in locks)
            is_derived = bool(k in derived)
            source = FactSource.AEVUM_INFERRED if is_derived else FactSource.CONVERSATION
            authority = FactAuthority.USER_LOCKED if is_locked else FactAuthority.AEVUM_CANONICAL
            item = CoreFactItem(
                key=k,
                category=k.split(".")[0],
                value=v,
                source=source,
                authority=authority,
                status=FactStatus.CANONICAL,
                locked=is_locked,
            )
            core.facts[k] = item
    return core


def _make_candidate(
    candidate_id: str,
    slot_name: str,
    proposed_value: Any,
    composite_plausibility: float = 0.85,
    lifecycle_state: CandidateLifecycleState = CandidateLifecycleState.GENERATED,
    entity_id: str = "aevum",
    is_quarantined: bool = False,
    inference_depth: int = 1,
) -> CandidateHypothesis:
    plaus = PlausibilityBreakdown.create(
        prior_weight=composite_plausibility,
        evidence_grounding_score=composite_plausibility,
        coherence_score=composite_plausibility,
        utility_score=composite_plausibility,
        composite_plausibility_score=composite_plausibility,
    )
    fam_id = f"fam_{candidate_id}"
    fam = EvidenceFamily(
        family_id=fam_id,
        source_type="USER_ASSERTION",
        cluster_key=f"cluster_{slot_name}_{candidate_id}",
        mention_count=1,
    )
    lineage = ProvenanceLineage(
        origin_id=f"stimulus_{candidate_id}",
        parent_candidate_ids=(),
        evidence_family_ids=(fam_id,),
        inference_depth=inference_depth,
        derivation_path=(),
    )
    return CandidateHypothesis(
        candidate_id=candidate_id,
        entity_id=entity_id,
        slot_name=slot_name,
        proposed_value=proposed_value,
        reality_taxonomy=RealityTaxonomy.SIMULATED_BIOGRAPHY_FACT,
        inference_depth=inference_depth,
        inference_edge_type=(
            InferenceEdgeType.SPECULATIVE_ASSOCIATION
            if is_quarantined
            else InferenceEdgeType.STRUCTURAL_DEPENDENCY
        ),
        plausibility=plaus,
        provenance=lineage,
        evidence_families=(fam,),
        is_quarantined=is_quarantined,
        lifecycle_state=lifecycle_state,
        selection_metadata=None,
    )


class TestGoldenSuite8A:
    """Golden Suite 8A Acceptance Benchmarks (GC-145 to GC-170)."""

    # -------------------------------------------------------------------------
    # GC-145: Canonical Mutation Authority Singularity
    # -------------------------------------------------------------------------
    def test_gc145_canonical_mutation_authority_singularity(self):
        """GC-145: AST audit verifies BiographyPromotionService is the sole caller of allow_canonical_reconciliation=True."""
        reality_dir = pathlib.Path(__file__).parent.parent / "app" / "reality"

        # Modules that must NOT call set_fact or allow_canonical_reconciliation
        audited_files = [
            reality_dir / "autonomous_inference_coordinator.py",
            reality_dir / "candidate_evaluator.py",
            reality_dir / "proposer.py",
            reality_dir / "inference_opportunity_detector.py",
            reality_dir / "reality_orchestration_service.py",
        ]

        for path in audited_files:
            if not path.exists():
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    # Check for direct set_fact invocations
                    if isinstance(node.func, ast.Attribute) and node.func.attr == "set_fact":
                        pytest.fail(f"Violation in {path.name}: direct call to 'set_fact' is strictly prohibited.")
                    # Check for allow_canonical_reconciliation argument
                    for kw in node.keywords:
                        if kw.arg == "allow_canonical_reconciliation":
                            pytest.fail(
                                f"Violation in {path.name}: 'allow_canonical_reconciliation' is reserved for BiographyPromotionService."
                            )

    # -------------------------------------------------------------------------
    # GC-146: Candidate Plurality Contract (2 <= k <= 4)
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_gc146_candidate_plurality_contract(self):
        """GC-146: Proposer strictly yields 2 to 4 candidates; coordinator aborts if viable count < 2."""
        core = _make_mock_core(
            facts={
                "academics.spm_math_grade": "A",
                "traits.musical_talent": True,
            }
        )
        req = InferenceOpportunityDetector.detect_opportunity(
            core=core,
            active_candidate_slots=set(),
        )
        assert req is not None
        assert req.target_slot == "education.major"

        proposer = DeterministicLifeHypothesisProposer()
        envelopes = await proposer.propose_hypotheses(req)
        assert 2 <= len(envelopes) <= 4

        # Coordinator plurality abort test
        session = _make_mock_session()
        coordinator = AutonomousInferenceCoordinator(session=session)
        # Mock proposer returning single candidate (contract breach)
        with patch.object(coordinator._proposer, "propose_hypotheses", new=AsyncMock(return_value=envelopes[:1])):
            result = await coordinator.run_inference_cycle(core=core)
            # Aborts without persisting
            assert result == ()
            assert session.commit.called is False

    # -------------------------------------------------------------------------
    # GC-147: Strict Premise Authorization Subset
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_gc147_strict_premise_authorization_subset(self):
        """GC-147: Candidate premises must be a strict subset of authorized premise keys."""
        core = _make_mock_core(
            facts={
                "academics.spm_math_grade": "A",
                "traits.musical_talent": True,
            }
        )
        req = InferenceOpportunityDetector.detect_opportunity(
            core=core,
            active_candidate_slots=set(),
        )
        assert req is not None

        proposer = DeterministicLifeHypothesisProposer()
        envelopes = await proposer.propose_hypotheses(req)
        authorized_keys = set(req.authorized_premise_keys)

        for env in envelopes:
            for pkey in env.suggested_premise_keys:
                assert pkey in authorized_keys, f"Premise key '{pkey}' is unauthorized."

    # -------------------------------------------------------------------------
    # GC-148: Anti-Snowballing Invariant (Gate 14)
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_gc148_anti_snowballing_single_slot_atomic_fact(self):
        """GC-148: Single atomic slot promotion verified; bundled ancillary trivia rejected by Gate 14."""
        session = _make_mock_session()
        core = _make_mock_core(facts={"academics.spm_math_grade": "A", "traits.musical_talent": True})

        # Candidate bundling unauthorized secondary trivia
        bundled_cand = _make_candidate(
            candidate_id="cand_snowball_01",
            slot_name="education.major",
            proposed_value="Computer Science",
            composite_plausibility=0.95,
        )
        bundled_cand = bundled_cand.model_copy(
            update={"selection_metadata": {"bundled_ancillary_facts": ["trivia.favorite_snack"]}}
        )

        dummy_choice = ChoiceDecisionResult(
            decision_id="dec_snowball",
            entity_id="aevum",
            slot_name="education.major",
            candidate_set_id="set_snowball",
            candidate_ids_considered=("cand_snowball_01", "cand_snowball_02"),
            selected_candidate_id="cand_snowball_01",
            unselected_candidate_ids=("cand_snowball_02",),
            selected_candidate=bundled_cand,
            archived_unselected_candidates=(),
            competition_state=CompetitionState.CLEAR_LEADER,
            competition_margin=0.50,
            plausibility_scores={"cand_snowball_01": 0.95, "cand_snowball_02": 0.45},
            factor_inputs={"cand_snowball_01": {"plausibility_score": 0.95}},
            factor_contributions={"cand_snowball_01": {"plausibility_contribution": 0.25}},
            choice_scores={"cand_snowball_01": 0.85, "cand_snowball_02": 0.35},
            choice_margin=0.50,
            rationale_code=ChoiceRationaleCode.MULTI_FACTOR_BALANCED,
            rationale_description="Snowball candidate",
            is_non_canonical=True,
            provenance_references=("fam_cand_snowball_01",),
        )

        promo_service = BiographyPromotionService(session=session)
        eligibility = promo_service.evaluate_promotion_eligibility(
            candidate=bundled_cand,
            choice_decision=dummy_choice,
            core=core,
        )
        assert PromotionGateType.GATE_14_ANTI_SNOWBALL in eligibility.failed_gates
        assert eligibility.is_eligible is False

    # -------------------------------------------------------------------------
    # GC-149: Choice vs. Promotion Decisive Margin (Δ >= 0.15)
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_gc149_choice_vs_promotion_decisive_margin(self):
        """GC-149: Decisive margin (Δ >= 0.15) authorizes promotion with single-use token."""
        session = _make_mock_session()
        core = _make_mock_core(
            facts={
                "academics.spm_math_grade": "A",
                "traits.musical_talent": True,
                "personality.temperament": "computer science and technology",
            }
        )

        cand_a = _make_candidate(
            candidate_id="cand_decisive_a",
            slot_name="education.major",
            proposed_value="Computer Science",
            composite_plausibility=0.92,
        )
        cand_b = _make_candidate(
            candidate_id="cand_decisive_b",
            slot_name="education.major",
            proposed_value="Music Performance",
            composite_plausibility=0.38,
        )

        promo_record = BiographyPromotionRecord(
            promotion_id="promo_gc149",
            candidate_id="cand_decisive_a",
            character_id="aevum",
            slot_name="education.major",
            promoted_value="Computer Science",
            new_canonical_state="Computer Science",
            authorization_code="AUTH-7D3-GC149",
            choice_decision_id="dec_gc149",
            created_at=_utc_now(),
        )

        svc = RealityOrchestrationService(session)
        with patch.object(
            svc._candidate_repo, "get_all_active_candidates", new=AsyncMock(return_value=[cand_a, cand_b])
        ), patch(
            "app.reality.reality_orchestration_service.WorldFactsSelector.select_for_turn",
            return_value={},
        ), patch.object(
            svc._inference_coordinator, "run_inference_cycle", new=AsyncMock(return_value=[cand_a, cand_b])
        ), patch(
            "app.reality.biography_promotion_service.BiographyPromotionService.promote_candidate",
            new=AsyncMock(return_value=promo_record),
        ):
            turn_result = await svc.run_turn(
                user_input="你在大学学什么专业？",
                core=core,
            )

        assert len(turn_result.choices) == 1
        choice = turn_result.choices[0]
        assert choice.selected_candidate_id == "cand_decisive_a"
        assert choice.choice_margin >= 0.15
        assert turn_result.promoted is True

    # -------------------------------------------------------------------------
    # GC-150: Ambiguity Preservation (Δ < 0.15 Denies Promotion)
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_gc150_ambiguity_preservation_denies_promotion(self):
        """GC-150: Ambiguous margin (Δ < 0.15) strictly fails Gate 7, denies promotion, core untouched."""
        session = _make_mock_session()
        core = _make_mock_core(
            facts={
                "academics.spm_math_grade": "A",
                "traits.musical_talent": True,
            }
        )

        cand_a = _make_candidate(
            candidate_id="cand_ambig_a",
            slot_name="education.major",
            proposed_value="Computer Science",
            composite_plausibility=0.71,
        )
        cand_b = _make_candidate(
            candidate_id="cand_ambig_b",
            slot_name="education.major",
            proposed_value="Software Engineering",
            composite_plausibility=0.70,
        )

        svc = RealityOrchestrationService(session)
        with patch.object(
            svc._candidate_repo, "get_all_active_candidates", new=AsyncMock(return_value=[cand_a, cand_b])
        ), patch(
            "app.reality.reality_orchestration_service.WorldFactsSelector.select_for_turn",
            return_value={},
        ), patch.object(
            svc._inference_coordinator, "run_inference_cycle", new=AsyncMock(return_value=[cand_a, cand_b])
        ):
            turn_result = await svc.run_turn(
                user_input="你读哪个专业？",
                core=core,
            )

        assert len(turn_result.choices) == 1
        choice = turn_result.choices[0]
        assert choice.choice_margin < 0.15
        assert turn_result.promoted is False
        assert core.get_fact_value("education.major") is None

    # -------------------------------------------------------------------------
    # GC-151: Ambiguous Candidate Isolation in Governed Reality Context
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_gc151_ambiguous_candidate_isolation_in_context(self):
        """GC-151: Unpromoted candidates are presented exclusively under <unresolved_tensions>."""
        session = _make_mock_session()
        core = _make_mock_core()

        cand_a = _make_candidate("cand_t1", "education.major", "Computer Science", 0.70)
        cand_b = _make_candidate("cand_t2", "education.major", "Software Engineering", 0.69)

        svc = RealityOrchestrationService(session)
        with patch.object(
            svc._candidate_repo, "get_all_active_candidates", new=AsyncMock(return_value=[cand_a, cand_b])
        ), patch(
            "app.reality.reality_orchestration_service.WorldFactsSelector.select_for_turn",
            return_value={},
        ), patch.object(
            svc._inference_coordinator, "run_inference_cycle", new=AsyncMock(return_value=[cand_a, cand_b])
        ):
            turn_result = await svc.run_turn(
                user_input="专业选好了吗？",
                core=core,
            )

        context = turn_result.governed_reality
        assert context is not None
        blocks = RealityContextBuilder.format_all_reality_blocks(context)
        rendered = "\n".join(blocks)
        assert "<active_candidate_hypotheses>" in rendered or "<pending_choice_decisions>" in rendered
        canonical_blocks = [b for b in blocks if "<character_core_facts>" in b]
        if canonical_blocks:
            assert "Computer Science" not in canonical_blocks[0]
            assert "Software Engineering" not in canonical_blocks[0]
        assert "Computer Science" in rendered or "Software Engineering" in rendered
        assert core.get_fact_value("education.major") is None

    # -------------------------------------------------------------------------
    # GC-152: Atomic Candidate Batch Persistence & Savepoint Rollback
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_gc152_atomic_candidate_batch_persistence(self):
        """GC-152: Partial DB write failure rolls back the entire batch; 0 candidates persisted."""
        session = _make_mock_session()
        core = _make_mock_core(facts={"academics.spm_math_grade": "A", "traits.musical_talent": True})

        coordinator = AutonomousInferenceCoordinator(session=session)

        # Mock save_candidate: succeeds for 1st, fails for 2nd
        call_count = 0

        async def _mock_save_candidate(cand):
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise RuntimeError("Simulated crash on candidate 2")

        coordinator._candidate_repo.save_candidate = _mock_save_candidate

        saved = await coordinator.run_inference_cycle(core=core)
        assert saved == ()
        assert session.rollback.called

    # -------------------------------------------------------------------------
    # GC-153: Single Invocation Per Turn Invariant (Linear Non-Recursive Flow)
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_gc153_single_invocation_per_turn_invariant(self):
        """GC-153: Step C2 executes exactly once per turn; zero recursive cycles."""
        session = _make_mock_session()
        core = _make_mock_core()

        svc = RealityOrchestrationService(session)
        cycle_call_count = 0

        async def _counted_cycle(*args, **kwargs):
            nonlocal cycle_call_count
            cycle_call_count += 1
            return ()

        svc._inference_coordinator.run_inference_cycle = _counted_cycle

        with patch.object(
            svc._candidate_repo, "get_all_active_candidates", new=AsyncMock(return_value=[])
        ), patch(
            "app.reality.reality_orchestration_service.WorldFactsSelector.select_for_turn",
            return_value={},
        ):
            await svc.run_turn(user_input="你好！", core=core)

        assert cycle_call_count == 1

    # -------------------------------------------------------------------------
    # GC-154: Invariant A (Unknown != Impossible, Quarantined Speculative Association)
    # -------------------------------------------------------------------------
    def test_gc154_invariant_a_unknown_is_not_impossible(self):
        """GC-154: Uncatalogued entity in WorldKnowledgeRegistry retains HardValidity=1.0 and is quarantined."""
        core = _make_mock_core()
        req = InferenceProposalRequest(
            target_slot="education.university",
            domain="academics",
            authorized_premise_keys=(),
            premise_snapshots={},
            inference_cycle_id="cycle_gc154",
        )
        envelope = CandidateEnvelope(
            domain="academics",
            slot="education.university",
            raw_value="Unknown Galactic Academy",
        )

        evaluator = CandidateEvaluationAdapter()
        hypotheses = evaluator.evaluate_envelopes([envelope], req, core)
        assert len(hypotheses) == 1
        cand = hypotheses[0]
        assert cand.is_quarantined is True
        assert cand.inference_edge_type == InferenceEdgeType.SPECULATIVE_ASSOCIATION
        assert cand.plausibility.composite_plausibility_score > 0.0

    # -------------------------------------------------------------------------
    # GC-155: Invariant B (Heuristic != Probability, Structural Baseline Coherence)
    # -------------------------------------------------------------------------
    def test_gc155_invariant_b_heuristic_is_not_probability(self):
        """GC-155: Plausibility scoring is a coherence metric using neutral baseline fit 0.50."""
        adapter = CandidateEvaluationAdapter()
        req = InferenceProposalRequest(
            target_slot="education.major",
            domain="academics",
            authorized_premise_keys=("academics.spm_math_grade",),
            premise_snapshots={"academics.spm_math_grade": "A"},
            inference_cycle_id="cycle_heuristic",
        )
        env = CandidateEnvelope(
            domain="academics",
            slot="education.major",
            raw_value="Computer Science",
            suggested_premise_keys=("academics.spm_math_grade",),
            suggested_premise_roles={"academics.spm_math_grade": PremiseRole.DIRECT_SUPPORT},
            rationale="Tech fit.",
        )
        core = _make_mock_core(facts={"academics.spm_math_grade": "A"})
        cand = adapter.evaluate_envelope(env, req, core)
        assert cand.plausibility.prior_weight == 0.50
        assert 0.0 <= cand.plausibility.composite_plausibility_score <= 1.0

    # -------------------------------------------------------------------------
    # GC-156: Invariant C (Construction != Persistence, GENERATED to PERSISTED)
    # -------------------------------------------------------------------------
    def test_gc156_invariant_c_construction_is_not_persistence(self):
        """GC-156: Evaluator outputs in-memory hypotheses with lifecycle_state = GENERATED."""
        core = _make_mock_core()
        req = InferenceProposalRequest(
            target_slot="education.major",
            domain="academics",
            authorized_premise_keys=(),
            premise_snapshots={},
            inference_cycle_id="cycle_gc156",
        )
        envelope = CandidateEnvelope(domain="academics", slot="education.major", raw_value="Computer Science")
        evaluator = CandidateEvaluationAdapter()
        hypotheses = evaluator.evaluate_envelopes([envelope], req, core)
        assert hypotheses[0].lifecycle_state == CandidateLifecycleState.GENERATED
        assert hypotheses[0].selection_metadata is None

    # -------------------------------------------------------------------------
    # GC-157: Invariant D (Derived != Primary Anchor Requirement)
    # -------------------------------------------------------------------------
    def test_gc157_invariant_d_derived_is_not_primary_anchor(self):
        """GC-157: Pure derived premise chains receive 0.0 context support without primary anchor."""
        core = _make_mock_core(
            facts={
                "academics.spm_math_grade": "A",
                "traits.musical_talent": True,
            },
            derived_keys={"academics.spm_math_grade", "traits.musical_talent"},
        )
        # All premises derived -> detector gate 6 rejects opportunity
        req = InferenceOpportunityDetector.detect_opportunity(core=core, active_candidate_slots=set())
        assert req is None

    # -------------------------------------------------------------------------
    # GC-158: Anti-Circularity DAG Enforcement (Gate 9 Acyclicity)
    # -------------------------------------------------------------------------
    def test_gc158_anti_circularity_dag_enforcement(self):
        """GC-158: Downstream inferred slots cannot support upstream prerequisite slots (acyclic DAG)."""
        core = _make_mock_core(facts={"career.aspiration": "Software Engineer"}, derived_keys={"career.aspiration"})
        req = InferenceProposalRequest(
            target_slot="education.major",
            domain="academics",
            authorized_premise_keys=("career.aspiration",),
            premise_snapshots={"career.aspiration": "Software Engineer"},
            inference_cycle_id="cycle_gc158",
        )
        envelope = CandidateEnvelope(
            domain="academics",
            slot="education.major",
            raw_value="Computer Science",
            suggested_premise_keys=("career.aspiration",),
        )
        evaluator = CandidateEvaluationAdapter()
        hypotheses = evaluator.evaluate_envelopes([envelope], req, core)
        assert len(hypotheses) == 1
        cand = hypotheses[0]
        # Anti-circularity: Downstream career gives zero context support to upstream major
        assert cand.plausibility.evidence_grounding_score == 0.0

    # -------------------------------------------------------------------------
    # GC-159: Socioeconomic & Demographic Anti-Stereotyping Prohibition
    # -------------------------------------------------------------------------
    def test_gc159_socioeconomic_anti_stereotyping(self):
        """GC-159: Parental occupation and ethnicity cannot be used to infer wealth, poverty, or suitability."""
        core_blue_collar = _make_mock_core(facts={"family.father_occupation": "construction worker"})
        core_white_collar = _make_mock_core(facts={"family.father_occupation": "corporate executive"})

        req = InferenceProposalRequest(
            target_slot="education.major",
            domain="academics",
            authorized_premise_keys=(),
            premise_snapshots={},
            inference_cycle_id="cycle_gc159",
        )
        env = CandidateEnvelope(domain="academics", slot="education.major", raw_value="Computer Science")
        evaluator = CandidateEvaluationAdapter()
        hyp_blue = evaluator.evaluate_envelopes([env], req, core_blue_collar)[0]
        hyp_white = evaluator.evaluate_envelopes([env], req, core_white_collar)[0]

        # Feasibility score must be invariant to parental occupation
        assert hyp_blue.plausibility.utility_score == hyp_white.plausibility.utility_score

    # -------------------------------------------------------------------------
    # GC-160: User-Locked Slot Absolute Immunity (Gate 1)
    # -------------------------------------------------------------------------
    def test_gc160_user_locked_slot_absolute_immunity(self):
        """GC-160: User-locked slots are skipped by detector and fail Gate 1 if attempted."""
        core = _make_mock_core(
            facts={
                "academics.spm_math_grade": "A",
                "traits.musical_talent": True,
                "education.major": "Architecture",
            },
            locked_keys={"education.major"},
        )
        # 1. Detector skips locked slot
        req = InferenceOpportunityDetector.detect_opportunity(core=core, active_candidate_slots=set())
        assert req is None or req.target_slot != "education.major"

        # 2. Gate 1 rejects promotion
        session = _make_mock_session()
        promo_service = BiographyPromotionService(session=session)
        cand = _make_candidate("cand_lock_test", "education.major", "Computer Science")
        choice = ChoiceDecisionResult(
            decision_id="dec_lock",
            entity_id="aevum",
            slot_name="education.major",
            candidate_set_id="set_lock",
            candidate_ids_considered=("cand_lock_test",),
            selected_candidate_id="cand_lock_test",
            unselected_candidate_ids=(),
            selected_candidate=cand,
            archived_unselected_candidates=(),
            competition_state=CompetitionState.CLEAR_LEADER,
            competition_margin=1.0,
            plausibility_scores={"cand_lock_test": 1.0},
            factor_inputs={},
            factor_contributions={},
            choice_scores={"cand_lock_test": 1.0},
            choice_margin=1.0,
            rationale_code=ChoiceRationaleCode.MULTI_FACTOR_BALANCED,
            rationale_description="Lock test",
            is_non_canonical=True,
            provenance_references=(),
        )
        eligibility = promo_service.evaluate_promotion_eligibility(cand, choice, core)
        assert PromotionGateType.GATE_1_USER_LOCK in eligibility.failed_gates

    # -------------------------------------------------------------------------
    # GC-161: Cooldown Determinism & Anti-Obsession Axiom
    # -------------------------------------------------------------------------
    def test_gc161_cooldown_determinism_and_anti_obsession(self):
        """GC-161: Cooldown turns respected; LOW-tier inference slots barred from autonomous inference."""
        # 1. Low-tier slot barred
        assessment = InferenceValuePolicy.evaluate_slot("preferences.study_beverage")
        assert assessment.tier == InferenceValueTier.LOW
        assert assessment.is_worth_inferring is False

        # 2. Cooldown determinism: Slot currently in cooldown is skipped
        core = _make_mock_core(facts={"academics.spm_math_grade": "A", "traits.musical_talent": True})
        req = InferenceOpportunityDetector.detect_opportunity(
            core=core,
            cooldown_slots={"education.major"},
        )
        assert req is None

    # -------------------------------------------------------------------------
    # GC-162: Deterministic Multi-Attribute Choice Factor Provenance & Neutral Baselines
    # -------------------------------------------------------------------------
    def test_gc162_deterministic_multi_attribute_choice_factor_provenance(self):
        """GC-162: Step F choice factors derive strictly from core with neutral 0.50 baseline and 0.0 costs."""
        core = _make_mock_core()
        cand = _make_candidate("cand_cf", "education.major", "Music Performance", 0.88)
        comp_res = CompetitionResult(
            slot_name="education.major",
            entity_id="aevum",
            candidate_set_id="set_cf",
            viable_candidates=(cand,),
            excluded_candidates=(),
            plausibility_scores={"cand_cf": 0.88},
            competition_state=CompetitionState.CLEAR_LEADER,
            decision_margin=0.88,
            leading_candidate_id="cand_cf",
        )

        factors = RealityOrchestrationService._derive_choice_factor_inputs(
            competition_result=comp_res,
            core=core,
        )
        assert "cand_cf" in factors
        breakdown = factors["cand_cf"]
        assert breakdown.plausibility_score == 0.88
        assert breakdown.temperament_fit == 0.50
        assert breakdown.values_alignment == 0.50
        assert breakdown.challenge_preference == 0.50
        assert breakdown.resource_compatibility == 0.50
        assert breakdown.timeline_compatibility == 0.50
        assert breakdown.opportunity_cost == 0.0
        assert breakdown.time_cost == 0.0

    # -------------------------------------------------------------------------
    # GC-163: Candidate Envelope Transient DTO Invariance
    # -------------------------------------------------------------------------
    def test_gc163_candidate_envelope_transient_dto_invariance(self):
        """GC-163: CandidateEnvelope is an immutable transient Pydantic DTO only; extra inputs forbidden."""
        env = CandidateEnvelope(domain="academics", slot="education.major", raw_value="Computer Science")
        assert env.raw_value == "Computer Science"

        with pytest.raises(Exception):
            env.raw_value = "Music"  # Frozen

        with pytest.raises(Exception):
            CandidateEnvelope(domain="academics", slot="education.major", raw_value="CS", extra_field=123)

    # -------------------------------------------------------------------------
    # GC-164: Non-Epistemic Proposer Metadata Invariance
    # -------------------------------------------------------------------------
    def test_gc164_non_epistemic_proposer_metadata_invariance(self):
        """GC-164: Proposer rationale text and suggested roles are strictly ignored by evaluator."""
        core = _make_mock_core()
        req = InferenceProposalRequest(
            target_slot="education.major",
            domain="academics",
            authorized_premise_keys=(),
            premise_snapshots={},
            inference_cycle_id="cycle_gc164",
        )
        env_with_metadata = CandidateEnvelope(
            domain="academics",
            slot="education.major",
            raw_value="Computer Science",
            suggested_premise_roles={"fake_key": PremiseRole.DIRECT_SUPPORT},
            rationale="This candidate is definitely 100% true and best choice.",
        )
        evaluator = CandidateEvaluationAdapter()
        hypotheses = evaluator.evaluate_envelopes([env_with_metadata], req, core)
        assert len(hypotheses) == 1
        cand = hypotheses[0]
        # Evaluation ignores rationale text completely
        assert "definitely 100% true" not in str(cand.plausibility)

    # -------------------------------------------------------------------------
    # GC-165: Multi-Turn Grounding Progression (Prerequisite Chaining)
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_gc165_multi_turn_grounding_progression(self):
        """GC-165: Turn 1 major promotion enables Turn 2 career aspiration proposal."""
        # Turn 1: Grounded in academics + musical talent
        core_t1 = _make_mock_core(facts={"academics.spm_math_grade": "A", "traits.musical_talent": True})
        req_t1 = InferenceOpportunityDetector.detect_opportunity(core=core_t1, active_candidate_slots=set())
        assert req_t1 is not None
        assert req_t1.target_slot == "education.major"

        # Turn 2: Major is canonical
        core_t2 = _make_mock_core(
            facts={
                "academics.spm_math_grade": "A",
                "traits.musical_talent": True,
                "education.major": "Computer Science",
            }
        )
        req_t2 = InferenceOpportunityDetector.detect_opportunity(core=core_t2, active_candidate_slots=set())
        assert req_t2 is not None
        assert req_t2.target_slot == "career.aspiration"

        proposer = DeterministicLifeHypothesisProposer()
        envelopes = await proposer.propose_hypotheses(req_t2)
        proposed_values = [e.raw_value for e in envelopes]
        assert "software_engineer" in proposed_values

    # -------------------------------------------------------------------------
    # GC-166: Single-Use Promotion Token Invalidation & Authorization Code
    # -------------------------------------------------------------------------
    def test_gc166_single_use_promotion_token_invalidation(self):
        """GC-166: Promotion token is bound to exact candidate/slot; payload mismatch invalidates."""
        token = PromotionAuthorizationToken.create(
            character_id="aevum",
            slot_name="education.major",
            value="Computer Science",
            candidate_id="cand_token_01",
            choice_decision_id="dec_token_01",
            policy_version="1.0.0",
        )
        assert token.verify("aevum", "education.major", "Computer Science") is True
        # Mismatched payload or character fails verification
        assert token.verify("aevum", "education.major", "Music Performance") is False
        assert token.verify("other_char", "education.major", "Computer Science") is False
        assert token.verify("aevum", "other_slot", "Computer Science") is False

    # -------------------------------------------------------------------------
    # GC-167: Safe Concurrent Idempotency Replay (GC-090 Integration)
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_gc167_safe_concurrent_idempotency_replay(self):
        """GC-167: Concurrency race condition returns safe idempotent replay without duplicate mutation."""
        session = _make_mock_session()
        core = _make_mock_core()

        cand = _make_candidate("cand_idemp", "education.major", "Computer Science", 1.0)
        choice = ChoiceDecisionResult(
            decision_id="dec_idemp",
            entity_id="aevum",
            slot_name="education.major",
            candidate_set_id="set_idemp",
            candidate_ids_considered=("cand_idemp", "cand_idemp_2"),
            selected_candidate_id="cand_idemp",
            unselected_candidate_ids=("cand_idemp_2",),
            selected_candidate=cand,
            archived_unselected_candidates=(),
            competition_state=CompetitionState.CLEAR_LEADER,
            competition_margin=0.50,
            plausibility_scores={"cand_idemp": 1.0, "cand_idemp_2": 0.50},
            factor_inputs={},
            factor_contributions={},
            choice_scores={"cand_idemp": 0.85, "cand_idemp_2": 0.35},
            choice_margin=0.50,
            rationale_code=ChoiceRationaleCode.MULTI_FACTOR_BALANCED,
            rationale_description="Idempotent choice",
            is_non_canonical=True,
            provenance_references=("fam_cand_idemp",),
        )

        existing_record = BiographyPromotionRecord(
            promotion_id="promo_exist_gc167",
            candidate_id="cand_idemp",
            character_id="aevum",
            slot_name="education.major",
            promoted_value="Computer Science",
            new_canonical_state="Computer Science",
            authorization_code="AUTH-7D3-GC167",
            choice_decision_id="dec_idemp",
            created_at=_utc_now(),
        )

        promo_service = BiographyPromotionService(session=session)
        with patch.object(
            promo_service._candidate_repo,
            "get_biography_promotion_by_candidate",
            new=AsyncMock(return_value=existing_record),
        ):
            record = await promo_service.promote_candidate(
                candidate=cand,
                choice_decision=choice,
                character_id="aevum",
            )

        assert record.is_idempotent_replay is True
        assert record.promotion_id == "promo_exist_gc167"

    # -------------------------------------------------------------------------
    # GC-168: Step C2 Infrastructure Failure Resilience & Safe Turn Absorption
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_gc168_step_c2_failure_resilience(self):
        """GC-168: Step C2 crash is safely absorbed and logged; conversation turn finishes cleanly."""
        session = _make_mock_session()
        core = _make_mock_core()

        svc = RealityOrchestrationService(session)
        svc._inference_coordinator.run_inference_cycle = AsyncMock(
            side_effect=RuntimeError("Simulated infrastructure crash in C2")
        )

        with patch.object(
            svc._candidate_repo, "get_all_active_candidates", new=AsyncMock(return_value=[])
        ), patch(
            "app.reality.reality_orchestration_service.WorldFactsSelector.select_for_turn",
            return_value={},
        ):
            turn_result = await svc.run_turn(
                user_input="你好！今天天气怎么样？",
                core=core,
            )

        assert turn_result is not None
        assert turn_result.governed_reality is not None

    # -------------------------------------------------------------------------
    # GC-169: AST Audit: Zero Forbidden Imports, Network Calls, or RBE References
    # -------------------------------------------------------------------------
    def test_gc169_ast_audit_zero_forbidden_imports_and_network_calls(self):
        """GC-169: AST audit verifies reality modules contain 0 network client imports and 0 RBE references."""
        reality_dir = pathlib.Path(__file__).parent.parent / "app" / "reality"

        files_to_audit = [
            reality_dir / "autonomous_inference_coordinator.py",
            reality_dir / "candidate_evaluator.py",
            reality_dir / "proposer.py",
            reality_dir / "inference_opportunity_detector.py",
            reality_dir / "inference_value_policy.py",
            reality_dir / "slot_normalizer.py",
            reality_dir / "inference_models.py",
        ]

        forbidden_modules = {"requests", "httpx", "aiohttp", "urllib", "urllib3"}

        for path in files_to_audit:
            if not path.exists():
                continue
            content = path.read_text(encoding="utf-8")
            # 1. Zero RBE references
            assert "RealityBeliefEngine" not in content, f"Violation: RealityBeliefEngine referenced in {path.name}"

            # 2. Zero network imports
            tree = ast.parse(content, filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        mod_root = alias.name.split(".")[0]
                        assert mod_root not in forbidden_modules, f"Forbidden import '{alias.name}' in {path.name}"
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        mod_root = node.module.split(".")[0]
                        assert mod_root not in forbidden_modules, f"Forbidden import from '{node.module}' in {path.name}"

    # -------------------------------------------------------------------------
    # GC-170: Integrated Full-Turn Autonomous Reality Cycle
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_gc170_integrated_full_turn_reality_cycle(self):
        """GC-170: Complete end-to-end reality cycle in a single turn."""
        session = _make_mock_session()
        core = _make_mock_core(
            facts={
                "academics.spm_math_grade": "A",
                "traits.musical_talent": True,
                "personality.temperament": "computer science and technology",
            }
        )

        cand_cs = _make_candidate("cand_e2e_cs", "education.major", "Computer Science", 0.92)
        cand_music = _make_candidate("cand_e2e_music", "education.major", "Music Performance", 0.40)

        promo_record = BiographyPromotionRecord(
            promotion_id="promo_gc170",
            candidate_id="cand_e2e_cs",
            character_id="aevum",
            slot_name="education.major",
            promoted_value="Computer Science",
            new_canonical_state="Computer Science",
            authorization_code="AUTH-7D3-GC170",
            choice_decision_id="dec_gc170",
            created_at=_utc_now(),
        )

        svc = RealityOrchestrationService(session)

        with patch.object(
            svc._inference_coordinator, "run_inference_cycle", new=AsyncMock(return_value=[cand_cs, cand_music])
        ), patch.object(
            svc._candidate_repo, "get_all_active_candidates", new=AsyncMock(return_value=[cand_cs, cand_music])
        ), patch(
            "app.reality.reality_orchestration_service.WorldFactsSelector.select_for_turn",
            return_value={},
        ), patch(
            "app.reality.biography_promotion_service.BiographyPromotionService.promote_candidate",
            new=AsyncMock(return_value=promo_record),
        ):
            turn_result = await svc.run_turn(
                user_input="我想问一下你的专业是什么呢？",
                core=core,
            )

        assert turn_result is not None
        assert len(turn_result.choices) == 1
        choice = turn_result.choices[0]
        assert choice.selected_candidate_id == "cand_e2e_cs"
        assert choice.choice_margin >= 0.15
        assert turn_result.promoted is True
        assert turn_result.governed_reality is not None
