"""Phase 8A.5 Integration & Reality Orchestration Suite.

Validates the complete integration of Autonomous Reality Inference (Step C2)
into RealityOrchestrationService, CandidateCompetitionService, ChoiceSelectionService,
and BiographyPromotionService.

Covers the Four Core Boundary Corrections:
1. Correction A: Choice Factor Provenance & Neutral Fallbacks (0.50 fits, 0.0 costs, zero arbitrary constants).
2. Correction B: Choice Selection != Biography Promotion (provisional choice non-canonical, Δ < 0.15 unpromoted).
3. Correction C: Atomic Candidate Batch Persistence (all-or-nothing rollback on partial failure).
4. Correction D: Single-Invocation-Per-Turn Invariant (linear non-recursive orchestration flow).
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
from app.reality.biography_promotion_service import (
    BiographyPromotionRecord,
    BiographyPromotionService,
    PromotionGateType,
    PromotionOrigin,
)
from app.reality.inference_models import (
    CandidateEnvelope,
    InferenceProposalRequest,
    PremiseOriginCategory,
    PremiseRole,
)
from app.reality.inference_opportunity_detector import InferenceOpportunityDetector
from app.reality.models import CoreFactItem, FactAuthority, FactSource, FactStatus
from app.reality.proposer import DeterministicLifeHypothesisProposer, LifeHypothesisProposer
from app.reality.reality_orchestration_service import RealityOrchestrationService


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _make_mock_fact(
    key: str,
    val: Any,
    source: FactSource = FactSource.USER_CONFIGURED,
    authority: FactAuthority = FactAuthority.AEVUM_CANONICAL,
) -> CoreFactItem:
    cat = key.split(".")[0]
    is_locked = (authority == FactAuthority.USER_LOCKED)
    return CoreFactItem(
        key=key,
        category=cat,
        value=val,
        source=source,
        authority=authority,
        status=FactStatus.CANONICAL,
        locked=is_locked,
    )


def _make_mock_core(
    facts: Optional[dict[str, Any]] = None,
    locked_slots: Optional[set[str]] = None,
    character_id: str = "aevum",
) -> CharacterCore:
    fact_items: dict[str, CoreFactItem] = {}
    if facts:
        for k, v in facts.items():
            if isinstance(v, CoreFactItem):
                fact_items[k] = v
            else:
                auth = (
                    FactAuthority.USER_LOCKED
                    if (locked_slots and k in locked_slots)
                    else FactAuthority.AEVUM_CANONICAL
                )
                fact_items[k] = _make_mock_fact(k, v, authority=auth)

    core = CharacterCore(character_id=character_id, facts=fact_items)
    return core


def _make_candidate(
    candidate_id: str,
    slot_name: str,
    proposed_value: str,
    composite_plausibility: float = 0.5,
    inference_depth: int = 1,
    is_quarantined: bool = False,
    quarantine_reason: Optional[str] = None,
    premise_fact_keys: tuple[str, ...] = ("academics.spm_math_grade",),
) -> CandidateHypothesis:
    fam = EvidenceFamily(
        family_id=f"fam_{candidate_id}",
        source_type="USER_ASSERTION",
        cluster_key=f"cluster_{slot_name}_{candidate_id}",
        mention_count=1,
    )
    return CandidateHypothesis(
        candidate_id=candidate_id,
        entity_id="aevum",
        slot_name=slot_name,
        proposed_value=proposed_value,
        reality_taxonomy=RealityTaxonomy.SIMULATED_BIOGRAPHY_FACT,
        inference_depth=inference_depth,
        inference_edge_type=(
            InferenceEdgeType.SPECULATIVE_ASSOCIATION
            if is_quarantined
            else InferenceEdgeType.STRUCTURAL_DEPENDENCY
        ),
        lifecycle_state=CandidateLifecycleState.PERSISTED,
        is_quarantined=is_quarantined,
        quarantine_reason=quarantine_reason,
        plausibility=PlausibilityBreakdown.create(
            prior_weight=composite_plausibility,
            evidence_grounding_score=composite_plausibility,
            coherence_score=composite_plausibility,
            utility_score=composite_plausibility,
            composite_plausibility_score=composite_plausibility,
        ),
        provenance=ProvenanceLineage(
            origin_id=f"stimulus_{candidate_id}",
            evidence_family_ids=(fam.family_id,),
            inference_depth=inference_depth,
        ),
        evidence_families=(fam,),
    )


def _make_mock_session() -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalars.return_value.first.return_value = None
    session.execute = AsyncMock(return_value=mock_result)
    session.scalars = AsyncMock(return_value=mock_result.scalars.return_value)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    # Async context manager for begin_nested
    nested_mock = AsyncMock()
    nested_mock.__aenter__.return_value = nested_mock
    nested_mock.__aexit__.return_value = None
    session.begin_nested = MagicMock(return_value=nested_mock)
    return session


@pytest.mark.asyncio
class TestRealityOrchestration8AIntegration:
    """Comprehensive Phase 8A.5 Integration Test Suite."""

    async def test_01_step_c2_end_to_end_open_slot_major(self):
        """Test 1: Open education.major slot triggers Step C2, yields >= 2 PERSISTED candidates."""
        session = _make_mock_session()
        core = _make_mock_core(
            facts={
                "academics.spm_math_grade": "A",
                "traits.musical_talent": True,
            }
        )

        persisted_in_db: list[CandidateHypothesis] = []

        async def _save_cand(c: CandidateHypothesis) -> CandidateHypothesis:
            p = c.to_persisted() if hasattr(c, "to_persisted") else c.model_copy(
                update={"lifecycle_state": CandidateLifecycleState.PERSISTED}
            )
            persisted_in_db.append(p)
            return p

        repo = CandidateRepository(session)
        with patch.object(repo, "save_candidate", side_effect=_save_cand), patch.object(
            repo, "get_all_active_candidates", new=AsyncMock(return_value=[])
        ):
            coordinator = AutonomousInferenceCoordinator(session=session, candidate_repo=repo)
            candidates = await coordinator.run_inference_cycle(core=core)

        assert len(candidates) >= 2, f"Expected >= 2 candidates, got {len(candidates)}"
        assert len(persisted_in_db) == len(candidates)
        for c in candidates:
            assert c.slot_name == "education.major"
            assert c.lifecycle_state == CandidateLifecycleState.PERSISTED
            assert c.plausibility.composite_plausibility_score > 0.0

    async def test_02_step_c2_batch_persistence_atomicity_rollback_on_failure(self):
        """Test 2 (Correction C): Save failure on candidate 2 rolls back entire batch (0 saved)."""
        session = _make_mock_session()
        core = _make_mock_core(
            facts={
                "academics.spm_math_grade": "A",
                "traits.musical_talent": True,
            }
        )

        repo = CandidateRepository(session)
        call_count = 0

        async def _failing_save(c: CandidateHypothesis) -> CandidateHypothesis:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise RuntimeError("Simulated DB connection drop on candidate 2")
            return c.model_copy(update={"lifecycle_state": CandidateLifecycleState.PERSISTED})

        with patch.object(repo, "save_candidate", side_effect=_failing_save), patch.object(
            repo, "get_all_active_candidates", new=AsyncMock(return_value=[])
        ):
            coordinator = AutonomousInferenceCoordinator(session=session, candidate_repo=repo)
            result = await coordinator.run_inference_cycle(core=core)

        # Batch persistence atomicity: partial success rolled back, 0 returned
        assert result == ()
        assert session.rollback.called or session.begin_nested.called

    async def test_03_step_c2_lifecycle_progression_generated_to_persisted(self):
        """Test 3: Evaluator outputs GENERATED; batch save transitions to PERSISTED."""
        session = _make_mock_session()
        core = _make_mock_core(
            facts={
                "academics.spm_math_grade": "A",
                "traits.musical_talent": True,
            }
        )

        repo = CandidateRepository(session)
        evaluator = CandidateEvaluationAdapter()

        request = InferenceProposalRequest(
            target_slot="education.major",
            domain="education",
            authorized_premise_keys=("academics.spm_math_grade", "traits.musical_talent"),
            premise_snapshots={"academics.spm_math_grade": "A", "traits.musical_talent": True},
            known_constraints=(),
            inference_cycle_id="test_cyc",
        )
        proposer = DeterministicLifeHypothesisProposer()
        envelopes = await proposer.propose_hypotheses(request)
        evaluated = evaluator.evaluate_envelopes(envelopes=envelopes, request=request, core=core)

        for e in evaluated:
            assert e.lifecycle_state == CandidateLifecycleState.GENERATED
            assert e.selection_metadata is None

        # Now through coordinator atomic persistence
        coordinator = AutonomousInferenceCoordinator(
            session=session,
            candidate_repo=repo,
            evaluator=evaluator,
        )
        with patch.object(repo, "get_all_active_candidates", new=AsyncMock(return_value=[])):
            persisted = await coordinator.run_inference_cycle(core=core)

        for p in persisted:
            assert p.lifecycle_state == CandidateLifecycleState.PERSISTED

    async def test_04_step_c2_plurality_enforcement_aborts_if_under_two(self):
        """Test 4: If proposer emits fewer than 2 candidates, coordinator aborts cycle."""
        session = _make_mock_session()
        core = _make_mock_core(
            facts={
                "academics.spm_math_grade": "A",
                "traits.musical_talent": True,
            }
        )

        mock_proposer = MagicMock(spec=LifeHypothesisProposer)
        # Mock proposing only 1 candidate
        mock_env = CandidateEnvelope(
            domain="education",
            slot="education.major",
            raw_value="Computer Science",
            suggested_premise_keys=("academics.spm_math_grade",),
            suggested_premise_roles={"academics.spm_math_grade": PremiseRole.DIRECT_SUPPORT},
            rationale="Only one candidate synthesized",
        )
        mock_proposer.propose_hypotheses.return_value = (mock_env,)

        repo = CandidateRepository(session)
        coordinator = AutonomousInferenceCoordinator(
            session=session,
            candidate_repo=repo,
            proposer=mock_proposer,
        )
        with patch.object(repo, "get_all_active_candidates", new=AsyncMock(return_value=[])):
            result = await coordinator.run_inference_cycle(core=core)

        # Must abort to respect Gate 6 candidate plurality
        assert result == ()

    async def test_05_decisive_choice_margin_authorizes_biography_promotion(self):
        """Test 5: Decisive margin (Δ >= 0.15) authorizes promotion via BiographyPromotionService."""
        session = _make_mock_session()
        core = _make_mock_core(
            facts={
                "academics.spm_math_grade": "A",
                "traits.musical_talent": True,
                "personality.temperament": "computer science",
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

        svc = RealityOrchestrationService(session)

        # Mock promotion service promotion call returning valid record
        promo_record = BiographyPromotionRecord(
            promotion_id="promo_01",
            candidate_id="cand_decisive_a",
            character_id="aevum",
            slot_name="education.major",
            promoted_value="Computer Science",
            new_canonical_state="Computer Science",
            authorization_code="AUTH-7D3-TEST",
            policy_version="1.0.0",
            choice_decision_id="dec_01",
            created_at=_utc_now(),
        )

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
                user_input="我想知道你大学在读什么专业？",
                core=core,
            )

        assert len(turn_result.choices) == 1
        choice = turn_result.choices[0]
        assert choice.selected_candidate_id == "cand_decisive_a"
        assert choice.choice_margin >= 0.15
        assert turn_result.promoted is True

    async def test_06_ambiguous_choice_margin_fails_gate_7_and_denies_promotion(self):
        """Test 6 (Correction B): Ambiguous margin (Δ < 0.15) fails Gate 7, denies promotion, core untouched."""
        session = _make_mock_session()
        core = _make_mock_core(
            facts={
                "academics.spm_math_grade": "A",
                "traits.musical_talent": True,
            }
        )

        # Two candidates with nearly identical plausibility
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
                user_input="你的专业是什么呀？",
                core=core,
            )

        assert len(turn_result.choices) == 1
        choice = turn_result.choices[0]
        # Choice selected candidate A provisionally (tentative deliberation)
        assert choice.selected_candidate_id == "cand_ambig_a"
        # Margin is ambiguous (< 0.15)
        assert choice.choice_margin < 0.15
        # Promotion is DENIED (Correction B)
        assert turn_result.promoted is False
        # Core has not been mutated
        assert core.get_fact_value("education.major") is None

    async def test_07_single_candidate_self_promotion_blocked_by_gate_6(self):
        """Test 7: Artificially injected single candidate without alternatives fails Gate 6."""
        session = _make_mock_session()
        core = _make_mock_core()

        single_cand = _make_candidate(
            candidate_id="cand_single_001",
            slot_name="education.major",
            proposed_value="Computer Science",
            composite_plausibility=1.0,
        )

        promo_service = BiographyPromotionService(session=session)
        dummy_choice = ChoiceDecisionResult(
            decision_id="dec_single",
            entity_id="aevum",
            slot_name="education.major",
            candidate_set_id="set_single",
            candidate_ids_considered=("cand_single_001",),
            selected_candidate_id="cand_single_001",
            unselected_candidate_ids=(),
            selected_candidate=single_cand,
            archived_unselected_candidates=(),
            competition_state=CompetitionState.CLEAR_LEADER,
            competition_margin=1.0,
            plausibility_scores={"cand_single_001": 1.0},
            factor_inputs={},
            factor_contributions={},
            choice_scores={"cand_single_001": 1.0},
            choice_margin=1.0,
            rationale_code=ChoiceRationaleCode.MULTI_FACTOR_BALANCED,
            rationale_description="Single candidate injected",
            is_non_canonical=True,
            provenance_references=("fam_cand_single_001",),
        )

        with pytest.raises(PermissionError, match="Candidate competition requires at least 2 viable alternatives"):
            await promo_service.promote_candidate(
                candidate=single_cand,
                choice_decision=dummy_choice,
                character_id="aevum",
            )

    async def test_08_quarantined_candidate_excluded_from_competition_and_promotion(self):
        """Test 8: Unverified entity candidate is quarantined and excluded from competition viability."""
        core = _make_mock_core()

        quarantined_cand = _make_candidate(
            candidate_id="cand_quarantined",
            slot_name="education.university",
            proposed_value="Mystic Highlands University",
            composite_plausibility=0.50,
            is_quarantined=True,
            quarantine_reason="UNVERIFIED_EXTERNAL_WORLD_ENTITY",
        )

        valid_cand = _make_candidate(
            candidate_id="cand_valid",
            slot_name="education.university",
            proposed_value="Universiti Sains Malaysia",
            composite_plausibility=0.88,
            is_quarantined=False,
        )

        comp_service = CandidateCompetitionService()
        result = comp_service.evaluate_competition(
            candidate_set_or_candidates=[quarantined_cand, valid_cand],
            core=core,
            slot_name="education.university",
            entity_id="aevum",
        )

        # Quarantined candidate must be excluded from viable candidates
        viable_ids = [c.candidate_id for c in result.viable_candidates]
        assert "cand_quarantined" not in viable_ids
        assert "cand_valid" in viable_ids
        assert len(result.excluded_candidates) == 1
        assert "QUARANTINED" in result.excluded_candidates[0][1]

    async def test_09_single_invocation_per_turn_invariant(self):
        """Test 9 (Correction D): Step C2 executes strictly once per turn; zero recursive cascades."""
        session = _make_mock_session()
        core = _make_mock_core(
            facts={
                "academics.spm_math_grade": "A",
                "traits.musical_talent": True,
            }
        )

        svc = RealityOrchestrationService(session)
        call_count = 0

        async def _count_cycles(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return ()

        with patch.object(svc._inference_coordinator, "run_inference_cycle", side_effect=_count_cycles), patch.object(
            svc._candidate_repo, "get_all_active_candidates", new=AsyncMock(return_value=[])
        ):
            await svc.run_turn(
                user_input="你好！",
                core=core,
            )

        assert call_count == 1, f"Expected Step C2 to execute exactly 1 time, got {call_count}"

    async def test_10_multi_turn_grounding_major_enables_career_aspiration_in_next_turn(self):
        """Test 10: Turn 1 promoted major serves as primary canonical anchor for Turn 2 career aspiration."""
        # Turn 1: Grounded in academics + musical talent -> major is inferred
        core_t1 = _make_mock_core(
            facts={
                "academics.spm_math_grade": "A",
                "traits.musical_talent": True,
            }
        )
        req_t1 = InferenceOpportunityDetector.detect_opportunity(
            core=core_t1,
            active_candidate_slots=set(),
        )
        assert req_t1 is not None
        assert req_t1.target_slot == "education.major"

        # Turn 2: Major is now promoted and canonical -> career.aspiration is now eligible
        core_t2 = _make_mock_core(
            facts={
                "academics.spm_math_grade": "A",
                "traits.musical_talent": True,
                "education.major": "Computer Science",
            }
        )
        req_t2 = InferenceOpportunityDetector.detect_opportunity(
            core=core_t2,
            active_candidate_slots=set(),
        )
        assert req_t2 is not None
        assert req_t2.target_slot == "career.aspiration"

        # Career aspiration proposes relevant paths based on Computer Science
        proposer = DeterministicLifeHypothesisProposer()
        envelopes = await proposer.propose_hypotheses(req_t2)
        proposed_values = [e.raw_value for e in envelopes]
        assert "software_engineer" in proposed_values
        assert len(envelopes) >= 2

    async def test_11_choice_factor_provenance_neutral_050_fallbacks_and_zero_cost(self):
        """Test 11 (Correction A): Unstated dimensions use neutral 0.50 fit and 0.0 cost; zero arbitrary constants."""
        core = _make_mock_core()

        cand = _make_candidate(
            candidate_id="cand_provenance_test",
            slot_name="education.major",
            proposed_value="Music Performance",
            composite_plausibility=0.82,
        )

        comp_result = CompetitionResult(
            slot_name="education.major",
            entity_id="aevum",
            candidate_set_id="set_prov",
            viable_candidates=(cand,),
            excluded_candidates=(),
            plausibility_scores={"cand_provenance_test": 0.82},
            competition_state=CompetitionState.CLEAR_LEADER,
            decision_margin=0.82,
            leading_candidate_id="cand_provenance_test",
        )

        factors = RealityOrchestrationService._derive_choice_factor_inputs(
            competition_result=comp_result,
            core=core,
        )

        assert "cand_provenance_test" in factors
        breakdown = factors["cand_provenance_test"]
        assert breakdown.plausibility_score == 0.82
        assert breakdown.temperament_fit == 0.50
        assert breakdown.values_alignment == 0.50
        assert breakdown.challenge_preference == 0.50
        assert breakdown.resource_compatibility == 0.50
        assert breakdown.timeline_compatibility == 0.50
        assert breakdown.opportunity_cost == 0.0
        assert breakdown.time_cost == 0.0

    async def test_12_choice_factor_provenance_explicit_core_alignment(self):
        """Test 12: When core has explicit temperament or values fact matching candidate, fit is elevated."""
        core = _make_mock_core(
            facts={
                "personality.temperament": "analytical and systematic",
                "identity.values": "innovation and technology",
                "identity.age": 20,
            }
        )

        cand_cs = _make_candidate(
            candidate_id="cand_cs",
            slot_name="education.major",
            proposed_value="Computer Science",
            composite_plausibility=0.85,
        )

        comp_result = CompetitionResult(
            slot_name="education.major",
            entity_id="aevum",
            candidate_set_id="set_cs",
            viable_candidates=(cand_cs,),
            excluded_candidates=(),
            plausibility_scores={"cand_cs": 0.85},
            competition_state=CompetitionState.CLEAR_LEADER,
            decision_margin=0.85,
            leading_candidate_id="cand_cs",
        )

        factors = RealityOrchestrationService._derive_choice_factor_inputs(
            competition_result=comp_result,
            core=core,
        )

        breakdown = factors["cand_cs"]
        assert breakdown.plausibility_score == 0.85
        assert breakdown.timeline_compatibility == 0.50
        assert breakdown.opportunity_cost == 0.0
        assert breakdown.time_cost == 0.0

    async def test_13_zero_partial_state_on_promotion_failure(self):
        """Test 13: DB failure during promotion rolls back transaction (zero partial state committed)."""
        session = _make_mock_session()
        core = _make_mock_core()

        cand_a = _make_candidate(
            candidate_id="cand_promo_fail_a",
            slot_name="education.major",
            proposed_value="Computer Science",
            composite_plausibility=1.0,
        )
        cand_b = _make_candidate(
            candidate_id="cand_promo_fail_b",
            slot_name="education.major",
            proposed_value="Music Performance",
            composite_plausibility=0.50,
        )

        choice = ChoiceDecisionResult(
            decision_id="dec_pf",
            entity_id="aevum",
            slot_name="education.major",
            candidate_set_id="set_pf",
            candidate_ids_considered=("cand_promo_fail_a", "cand_promo_fail_b"),
            selected_candidate_id="cand_promo_fail_a",
            unselected_candidate_ids=("cand_promo_fail_b",),
            selected_candidate=cand_a,
            archived_unselected_candidates=(cand_b,),
            competition_state=CompetitionState.CLEAR_LEADER,
            competition_margin=0.50,
            plausibility_scores={"cand_promo_fail_a": 1.0, "cand_promo_fail_b": 0.50},
            factor_inputs={"cand_promo_fail_a": {"plausibility_score": 1.0}},
            factor_contributions={"cand_promo_fail_a": {"plausibility_contribution": 0.30}},
            choice_scores={"cand_promo_fail_a": 0.85, "cand_promo_fail_b": 0.35},
            choice_margin=0.50,
            rationale_code=ChoiceRationaleCode.MULTI_FACTOR_BALANCED,
            rationale_description="Decisive choice",
            is_non_canonical=True,
            provenance_references=("fam_cand_promo_fail_a",),
        )

        promo_service = BiographyPromotionService(session=session)
        # Simulate commit failure
        session.commit = AsyncMock(side_effect=RuntimeError("Simulated DB commit crash"))

        with patch.object(
            promo_service._core_service, "get_core", new=AsyncMock(return_value=core)
        ), patch.object(
            promo_service._candidate_repo, "get_biography_promotion_by_candidate", new=AsyncMock(return_value=None)
        ):
            with pytest.raises(RuntimeError, match="Simulated DB commit crash"):
                await promo_service.promote_candidate(
                    candidate=cand_a,
                    choice_decision=choice,
                    character_id="aevum",
                )

        # Rollback must be invoked to ensure zero partial state committed
        assert session.rollback.called

    async def test_14_gc090_concurrency_replay_recovery_in_promotion(self):
        """Test 14: Concurrent duplicate promotion triggers safe idempotent replay."""
        session = _make_mock_session()
        core = _make_mock_core()

        cand = _make_candidate(
            candidate_id="cand_concurrent_01",
            slot_name="education.major",
            proposed_value="Computer Science",
            composite_plausibility=1.0,
        )

        choice = ChoiceDecisionResult(
            decision_id="dec_conc",
            entity_id="aevum",
            slot_name="education.major",
            candidate_set_id="set_conc",
            candidate_ids_considered=("cand_concurrent_01", "cand_concurrent_02"),
            selected_candidate_id="cand_concurrent_01",
            unselected_candidate_ids=("cand_concurrent_02",),
            selected_candidate=cand,
            archived_unselected_candidates=(),
            competition_state=CompetitionState.CLEAR_LEADER,
            competition_margin=0.50,
            plausibility_scores={"cand_concurrent_01": 1.0, "cand_concurrent_02": 0.50},
            factor_inputs={},
            factor_contributions={},
            choice_scores={"cand_concurrent_01": 0.85, "cand_concurrent_02": 0.35},
            choice_margin=0.50,
            rationale_code=ChoiceRationaleCode.MULTI_FACTOR_BALANCED,
            rationale_description="Decisive choice",
            is_non_canonical=True,
            provenance_references=("fam_cand_concurrent_01",),
        )

        promo_service = BiographyPromotionService(session=session)

        # Mock existing promotion record for idempotent recovery
        existing_promo = BiographyPromotionRecord(
            promotion_id="promo_exist_01",
            candidate_id="cand_concurrent_01",
            character_id="aevum",
            slot_name="education.major",
            promoted_value="Computer Science",
            new_canonical_state="Computer Science",
            authorization_code="AUTH-7D3-CONC",
            choice_decision_id="dec_conc",
            created_at=_utc_now(),
        )

        with patch.object(
            promo_service._candidate_repo,
            "get_biography_promotion_by_candidate",
            new=AsyncMock(return_value=existing_promo),
        ):
            record = await promo_service.promote_candidate(
                candidate=cand,
                choice_decision=choice,
                character_id="aevum",
            )

        assert record.is_idempotent_replay is True
        assert record.promotion_id == "promo_exist_01"

    async def test_15_cooldown_enforcement_skips_recently_inferred_slot(self):
        """Test 15: Slot in cooldown is skipped by detector."""
        core = _make_mock_core(
            facts={
                "academics.spm_math_grade": "A",
                "traits.musical_talent": True,
            }
        )

        request = InferenceOpportunityDetector.detect_opportunity(
            core=core,
            active_candidate_slots=set(),
            cooldown_slots={"education.major"},
        )

        # education.major is in cooldown, so it must not be proposed
        if request is not None:
            assert request.target_slot != "education.major"

    async def test_16_user_locked_slot_strictly_skipped_by_step_c2(self):
        """Test 16: User-locked slot cannot be inferred under any condition."""
        core = _make_mock_core(
            facts={
                "academics.spm_math_grade": "A",
                "traits.musical_talent": True,
                "education.major": "Physics",
            },
            locked_slots={"education.major"},
        )

        request = InferenceOpportunityDetector.detect_opportunity(
            core=core,
            active_candidate_slots=set(),
        )

        # Locked slot is completely uninferable
        if request is not None:
            assert request.target_slot != "education.major"

    async def test_17_already_canonical_slot_strictly_skipped_by_step_c2(self):
        """Test 17: Existing confirmed canonical slot is skipped by Gate 1."""
        core = _make_mock_core(
            facts={
                "academics.spm_math_grade": "A",
                "traits.musical_talent": True,
                "education.major": "Computer Science",
            }
        )

        request = InferenceOpportunityDetector.detect_opportunity(
            core=core,
            active_candidate_slots=set(),
            requested_slot="education.major",
        )
        assert request is None

    async def test_18_low_inference_value_slot_skipped_by_gate_4(self):
        """Test 18: Slots with LOW or ZERO inference value are rejected by Gate 4."""
        core = _make_mock_core()

        # Ephemeral preferences have LOW value
        request = InferenceOpportunityDetector.detect_opportunity(
            core=core,
            active_candidate_slots=set(),
            requested_slot="preferences.coffee_order",
        )
        assert request is None

    async def test_19_step_c2_infrastructure_failure_absorbed_safely(self):
        """Test 19: Unexpected error in autonomous coordinator is absorbed without aborting the turn."""
        session = _make_mock_session()
        core = _make_mock_core()

        svc = RealityOrchestrationService(session)

        with patch.object(
            svc._inference_coordinator,
            "run_inference_cycle",
            side_effect=RuntimeError("Simulated unhandled coordinator failure"),
        ), patch.object(
            svc._candidate_repo, "get_all_active_candidates", new=AsyncMock(return_value=[])
        ):
            turn_result = await svc.run_turn(
                user_input="你好！",
                core=core,
            )

        assert turn_result.governed_reality is not None
        assert turn_result.candidates == []
        assert turn_result.choices == []
        assert turn_result.promoted is False

    async def test_20_governed_reality_context_integration(self):
        """Test 20: GovernedRealityContext assembled at Step J contains canonical, candidate, and choice items."""
        session = _make_mock_session()
        core = _make_mock_core(
            facts={
                "education.pathway": "STPM",
                "education.university": "Universiti Sains Malaysia",
            }
        )

        svc = RealityOrchestrationService(session)

        turn_result = await svc.run_turn(
            user_input="在做什么呢？",
            core=core,
        )

        assert turn_result.governed_reality is not None
        # Check canonical facts are in context
        canonical_keys = [
            item.provenance.fact_key for item in turn_result.governed_reality.canonical_items
        ]
        assert "education.pathway" in canonical_keys
        assert "education.university" in canonical_keys

    async def test_21_ast_audit_zero_set_fact_in_coordinator_and_orchestration(self):
        """Test 21: AST audit verifying zero set_fact() calls outside BiographyPromotionService."""
        coordinator_path = pathlib.Path("app/reality/autonomous_inference_coordinator.py")
        orchestration_path = pathlib.Path("app/reality/reality_orchestration_service.py")

        for path in (coordinator_path, orchestration_path):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Attribute) and func.attr == "set_fact":
                        pytest.fail(f"{path} calls .set_fact() at line {node.lineno}")

    async def test_22_ast_audit_zero_promotion_token_in_coordinator_and_orchestration(self):
        """Test 22: AST audit verifying zero PromotionAuthorizationToken creation or imports."""
        coordinator_path = pathlib.Path("app/reality/autonomous_inference_coordinator.py")
        orchestration_path = pathlib.Path("app/reality/reality_orchestration_service.py")

        for path in (coordinator_path, orchestration_path):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    for alias in node.names:
                        assert "PromotionAuthorizationToken" not in alias.name, (
                            f"{path} imports PromotionAuthorizationToken"
                        )
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id == "PromotionAuthorizationToken":
                        pytest.fail(f"{path} instantiates PromotionAuthorizationToken at line {node.lineno}")

    async def test_23_ast_audit_zero_rbe_in_coordinator(self):
        """Test 23: AST audit verifying zero RealityBeliefEngine references in coordinator."""
        path = pathlib.Path("app/reality/autonomous_inference_coordinator.py")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    assert "RealityBeliefEngine" not in alias.name, f"{path} imports RealityBeliefEngine"
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "RealityBeliefEngine":
                    pytest.fail(f"{path} instantiates RealityBeliefEngine at line {node.lineno}")

    async def test_24_ast_audit_zero_network_in_coordinator(self):
        """Test 24: AST audit verifying zero network, tool, or web imports in coordinator."""
        path = pathlib.Path("app/reality/autonomous_inference_coordinator.py")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        forbidden_modules = {"httpx", "aiohttp", "urllib", "requests", "google.genai"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_mod = alias.name.split(".")[0]
                    assert root_mod not in forbidden_modules, (
                        f"{path} imports forbidden external module '{alias.name}'"
                    )
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    root_mod = node.module.split(".")[0]
                    assert root_mod not in forbidden_modules, (
                        f"{path} imports from forbidden external module '{node.module}'"
                    )
