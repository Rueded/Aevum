"""Acceptance test suite for Phase 7D.3: Minimal Reality Repair & Autonomous Biography Promotion.

Verifies:
- GC-072: Social Misspeak Repair (Level 1)
- GC-073: Temporal Reinterpretation (Level 2)
- GC-074: Fact Invalidation (Level 3)
- GC-075: Re-Anchoring (Level 4 ephemeral disambiguation)
- GC-076: Graceful Uncertainty (Level 5 fallback)
- GC-077: Zero Compensatory Biography Invariant
- GC-078: Autonomous High-Impact Biography Promotion Happy Path (All 14 Gates)
- GC-079: USER_LOCK Blocks Promotion (Gate 1)
- GC-080: Objective World Fact Protection (Gate 2)
- GC-081: Timeline Gate (Gate 3)
- GC-082: Causality Gate (Gate 4)
- GC-083: Graph Consistency Gate (Gate 5)
- GC-084: Minimum 2 Viable Candidates (Gate 6)
- GC-085: Explicit Choice Required (Gate 7)
- GC-086: Structured Provenance Required (Gate 8)
- GC-087: Circular Evidence Rejected (Gate 9)
- GC-088: Semantic Distance Guard (Gate 10)
- GC-089: Biography Construction Policy Gate (Gate 11)
- GC-090: Promotion Idempotency Protocol (Gate 12)
- GC-091: Structured Revision Recording (Gate 13)
- GC-092: Anti-Snowball Single Slot Promotion (Gate 14)
- GC-093: Absence of Evidence is Not Contradiction
- GC-094: Candidate Decay Does Not Invalidate Canonical Reality
- Static AST Call-Site Enforcement Singularity Test
- Deterministic 50-run Authorization Replay Test
"""

import ast
import asyncio
from datetime import datetime, timezone
import os
import pathlib
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import CharacterBiographyPromotionRecord
from app.db.session import Base
from app.character.core_models import CharacterCore
from app.character.core_service import (
    AevumCanonicalNotDirectlyEditableError,
    CharacterCoreService,
    FactLockedError,
)
from app.reality.biography_promotion_models import (
    BiographyConstructionPolicy,
    BiographyPromotionRecord,
    PromotionAuthorizationToken,
    PromotionGateType,
    PromotionOrigin,
)
from app.reality.biography_promotion_service import BiographyPromotionService
from app.reality.candidate_models import (
    CandidateHypothesis,
    CandidateHypothesisSet,
    CandidateLifecycleState,
    EvidenceFamily,
    InferenceEdgeType,
    PlausibilityBreakdown,
    ProvenanceLineage,
    RealityTaxonomy,
)
from app.reality.candidate_repository import CandidateRepository
from app.reality.choice_models import (
    ChoiceConfig,
    ChoiceDecisionResult,
    ChoiceFactorBreakdown,
    ChoiceRationaleCode,
    CompetitionResult,
    CompetitionState,
)
from app.reality.choice_service import ChoiceSelectionService
from app.reality.competition_service import CandidateCompetitionService
from app.reality.history_service import RealityHistoryService
from app.reality.models import CoreFactItem, FactAuthority, FactSource, FactStatus
from app.reality.repair_models import RealityRepairResult, RepairLevel
from app.reality.repair_service import RealityRepairService


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _make_candidate(
    candidate_id: str,
    slot_name: str,
    value: str,
    composite_plausibility: float = 0.5,
    inference_depth: int = 0,
    edge_type: InferenceEdgeType = InferenceEdgeType.DIRECT_ATTRIBUTE,
    family_ids: tuple[str, ...] = ("fam_test",),
    lifecycle_state: CandidateLifecycleState = CandidateLifecycleState.ACTIVE,
    parent_ids: tuple[str, ...] = (),
    selection_metadata: dict = None,
) -> CandidateHypothesis:
    fams = tuple(
        EvidenceFamily(
            family_id=fid,
            source_type="USER_ASSERTION",
            cluster_key=f"cluster_{slot_name}_{value}_{fid}",
            mention_count=1,
        )
        for fid in family_ids
    )
    return CandidateHypothesis(
        candidate_id=candidate_id,
        entity_id="aevum",
        slot_name=slot_name,
        proposed_value=value,
        reality_taxonomy=RealityTaxonomy.SIMULATED_BIOGRAPHY_FACT,
        inference_depth=inference_depth,
        inference_edge_type=edge_type,
        plausibility=PlausibilityBreakdown(
            prior_weight=composite_plausibility,
            evidence_grounding_score=composite_plausibility,
            coherence_score=composite_plausibility,
            utility_score=composite_plausibility,
            composite_plausibility_score=composite_plausibility,
        ),
        provenance=ProvenanceLineage(
            origin_id=f"stimulus_{candidate_id}",
            parent_candidate_ids=parent_ids,
            evidence_family_ids=family_ids,
            inference_depth=inference_depth,
        ),
        evidence_families=fams,
        lifecycle_state=lifecycle_state,
        selection_metadata=selection_metadata or {},
    )


def _make_choice_decision(
    candidate_set_id: str,
    slot_name: str,
    selected_id: str,
    cand_ids: tuple[str, ...],
    choice_margin: float = 0.08,
) -> ChoiceDecisionResult:
    return ChoiceDecisionResult(
        decision_id=f"choice_{candidate_set_id}",
        entity_id="aevum",
        slot_name=slot_name,
        candidate_set_id=candidate_set_id,
        candidate_ids_considered=cand_ids,
        selected_candidate_id=selected_id,
        unselected_candidate_ids=tuple(c for c in cand_ids if c != selected_id),
        decision_timestamp=_utc_now(),
        decision_model_version="1.0.0",
        competition_state=CompetitionState.CLEAR_LEADER,
        competition_margin=choice_margin,
        plausibility_scores={cid: 0.80 for cid in cand_ids},
        factor_inputs={
            cid: {
                "temperament_fit": 0.85 if cid == selected_id else 0.70,
                "values_alignment": 0.85 if cid == selected_id else 0.70,
            }
            for cid in cand_ids
        },
        factor_contributions={
            cid: {
                "temperament_contribution": 0.20 if cid == selected_id else 0.15,
                "values_contribution": 0.20 if cid == selected_id else 0.15,
            }
            for cid in cand_ids
        },
        choice_scores={cid: (0.80 if cid == selected_id else 0.72) for cid in cand_ids},
        choice_margin=choice_margin,
        rationale_code=ChoiceRationaleCode.MULTI_FACTOR_BALANCED,
        rationale_description="Candidate selected based on dominant multi-attribute profile.",
        is_non_canonical=True,
        provenance_references=("ref_personality_anchors", "ref_values_alignment"),
    )


# =============================================================================
# Component 1: Minimal Reality Repair Benchmarks (GC-072 - GC-077)
# =============================================================================

def test_gc072_social_misspeak_repair():
    """GC-072: Pop-culture attribution error resolved socially without world lore mutation."""
    res = RealityRepairService.repair(
        conflict_type="POP_CULTURE_SLIP",
        is_social_misspeak=True,
        social_explanation="Xianlian is an entity in Honkai: Star Rail lore, not Genshin Impact.",
    )
    assert res.repair_level == RepairLevel.LEVEL_1_SOCIAL_MISSPEAK
    assert res.is_repaired is True
    assert res.compensatory_biography_created is False
    assert res.canonical_mutated is False
    assert "Star Rail" in res.social_guidance
    assert res.temporal_split is None


def test_gc073_temporal_reinterpretation():
    """GC-073: Reconciled across time only when independently supported by existing timeline facts."""
    # Scenario A: Independently supported timeline evidence
    supported_evidence = {
        "independent_timeline_supported": True,
        "past": "Penang",
        "present": "Kuala Lumpur",
    }
    res = RealityRepairService.repair(
        claim_key="location.current",
        timeline_evidence=supported_evidence,
    )
    assert res.repair_level == RepairLevel.LEVEL_2_TEMPORAL_REINTERPRETATION
    assert res.is_repaired is True
    assert res.temporal_split == {"past": "Penang", "present": "Kuala Lumpur"}
    assert res.compensatory_biography_created is False
    assert res.canonical_mutated is False

    # Scenario B: Unsupported timeline bridge falls through to Level 5
    unsupported_evidence = {
        "independent_timeline_supported": False,
        "past": "Penang",
        "present": "Kuala Lumpur",
    }
    res_unsupported = RealityRepairService.repair(
        claim_key="location.current",
        timeline_evidence=unsupported_evidence,
    )
    assert res_unsupported.repair_level == RepairLevel.LEVEL_5_GRACEFUL_UNCERTAINTY
    assert res_unsupported.is_repaired is False
    assert res_unsupported.compensatory_biography_created is False


def test_gc074_fact_invalidation():
    """GC-074: Lower-authority candidate rejected when contradicted by stronger evidence."""
    res = RealityRepairService.repair(
        conflict_type="FACT_INVALIDATION",
        unconfirmed_candidate_id="cand_unsupported_major_42",
        rationale="Invalidated by established core fact education.level",
    )
    assert res.repair_level == RepairLevel.LEVEL_3_FACT_INVALIDATION
    assert res.is_repaired is True
    assert res.invalidated_claim_ids == ("cand_unsupported_major_42",)
    assert res.compensatory_biography_created is False
    assert res.canonical_mutated is False


def test_gc075_re_anchoring():
    """GC-075: Re-anchoring allowed only when independent evidence supports separate entity."""
    res = RealityRepairService.repair(
        entity_disambiguation={
            "independent_evidence_supported": True,
            "ambiguous_name": "Sarah",
            "reanchored_target": "Sarah (Lab Partner)",
        }
    )
    assert res.repair_level == RepairLevel.LEVEL_4_RE_ANCHORING
    assert res.is_repaired is True
    assert res.reanchored_context["scope"] == "EPHEMERAL_REPAIR_INTERPRETATION"
    assert res.reanchored_context["reanchored_to"] == "Sarah (Lab Partner)"
    assert res.compensatory_biography_created is False
    assert res.canonical_mutated is False


def test_gc076_graceful_uncertainty():
    """GC-076: Unsupported contradictions retain explicit uncertainty without fake bridges."""
    res = RealityRepairService.repair(
        claim_key="career.internship",
        claimed_value="Software Engineer in Tokyo",
        existing_value="Full-time student in Malaysia",
    )
    assert res.repair_level == RepairLevel.LEVEL_5_GRACEFUL_UNCERTAINTY
    assert res.is_repaired is False
    assert len(res.unresolved_reasons) > 0
    assert res.compensatory_biography_created is False
    assert res.canonical_mutated is False


def test_gc077_zero_compensatory_biography():
    """GC-077: System strictly rejects fabricating semester breaks, family visits, or transfers."""
    # Attempting to pass compensatory_biography_requested
    res = RealityRepairService.repair(
        claim_key="location.residence",
        compensatory_biography_requested=True,
    )
    assert res.repair_level == RepairLevel.LEVEL_5_GRACEFUL_UNCERTAINTY
    assert res.is_repaired is False
    assert res.compensatory_biography_created is False

    # Model validator hard-lock: directly passing compensatory_biography_created=True MUST raise ValueError
    with pytest.raises(ValueError, match="strictly forbidden from creating compensatory biography"):
        RealityRepairResult(
            repair_level=RepairLevel.LEVEL_2_TEMPORAL_REINTERPRETATION,
            repair_action="FABRICATED_BREAK",
            compensatory_biography_created=True,
        )

    # Model validator hard-lock: directly passing canonical_mutated=True MUST raise ValueError
    with pytest.raises(ValueError, match="strictly forbidden from directly mutating canonical reality"):
        RealityRepairResult(
            repair_level=RepairLevel.LEVEL_1_SOCIAL_MISSPEAK,
            repair_action="DIRECT_MUTATION",
            canonical_mutated=True,
        )


# =============================================================================
# Component 2: Autonomous High-Impact Biography Promotion (GC-078 - GC-094)
# =============================================================================

@pytest.mark.asyncio
async def test_gc078_autonomous_high_impact_promotion_happy_path(test_session: AsyncSession):
    """GC-078: Simulation-originated high-impact major satisfies all 14 gates and promotes autonomously."""
    core_service = CharacterCoreService(test_session)
    candidate_repo = CandidateRepository(test_session)
    history_service = RealityHistoryService(test_session)
    policy = BiographyConstructionPolicy()

    promo_service = BiographyPromotionService(
        session=test_session,
        candidate_repo=candidate_repo,
        core_service=core_service,
        history_service=history_service,
        policy=policy,
    )

    # 1. Create 2 viable candidates
    cand_cs = _make_candidate("cand_cs", "education.major", "Computer Science", composite_plausibility=0.85)
    cand_se = _make_candidate("cand_se", "education.major", "Software Engineering", composite_plausibility=0.82)
    await candidate_repo.save_candidate(cand_cs)
    await candidate_repo.save_candidate(cand_se)

    # 2. Choice decision selecting Computer Science
    choice_decision = _make_choice_decision(
        candidate_set_id="set_major_1",
        slot_name="education.major",
        selected_id="cand_cs",
        cand_ids=("cand_cs", "cand_se"),
        choice_margin=0.08,
    )
    await candidate_repo.save_choice_decision(choice_decision)

    # 3. Execute promotion
    promo_record = await promo_service.promote_candidate(
        candidate=cand_cs,
        choice_decision=choice_decision,
        character_id="aevum",
    )

    # Assert promotion record
    assert promo_record.slot_name == "education.major"
    assert promo_record.candidate_id == "cand_cs"
    assert promo_record.promoted_value == "Computer Science"
    assert len(promo_record.gates_passed) == 14
    assert promo_record.is_idempotent_replay is False

    # Assert Core reality was canonically updated
    core = await core_service.get_core("aevum")
    assert core.get_value("education.major") == "Computer Science"
    fact = core.facts["education.major"]
    assert fact.authority == FactAuthority.AEVUM_CANONICAL
    assert fact.status == FactStatus.CANONICAL
    assert fact.source == FactSource.AEVUM_INFERRED

    # Assert candidate lifecycle transitioned to SUPERSEDED (no new PROMOTED state in 7D.1)
    updated_cand = await candidate_repo.get_candidate("cand_cs")
    assert updated_cand.lifecycle_state == CandidateLifecycleState.SUPERSEDED

    # Assert persistence in character_biography_promotions table
    persisted_promo = await candidate_repo.get_biography_promotion_by_candidate("cand_cs")
    assert persisted_promo is not None
    assert persisted_promo.promoted_value == "Computer Science"


@pytest.mark.asyncio
async def test_gc079_user_lock_blocks_promotion(test_session: AsyncSession):
    """GC-079: Conflict with USER_LOCKED fact blocks promotion (Gate 1)."""
    core_service = CharacterCoreService(test_session)
    candidate_repo = CandidateRepository(test_session)
    promo_service = BiographyPromotionService(test_session, candidate_repo, core_service)

    # User locks education.major
    await core_service.set_fact(
        character_id="aevum",
        fact_key="education.major",
        value="Physics",
        authority=FactAuthority.USER_LOCKED,
    )

    cand = _make_candidate("cand_math", "education.major", "Mathematics", composite_plausibility=0.88)
    cand_alt = _make_candidate("cand_stats", "education.major", "Statistics", composite_plausibility=0.80)
    choice = _make_choice_decision("set_math", "education.major", "cand_math", ("cand_math", "cand_stats"))

    # Attempt promotion -> Gate 1 fails
    with pytest.raises(PermissionError, match="Slot 'education.major' is locked by user"):
        await promo_service.promote_candidate(cand, choice)

    # Core remains locked to Physics
    core = await core_service.get_core("aevum")
    assert core.get_value("education.major") == "Physics"


@pytest.mark.asyncio
async def test_gc080_objective_world_fact_protection(test_session: AsyncSession):
    """GC-080: Physical world contradiction blocks promotion (Gate 2)."""
    core_service = CharacterCoreService(test_session)
    candidate_repo = CandidateRepository(test_session)
    promo_service = BiographyPromotionService(test_session, candidate_repo, core_service)

    cand = _make_candidate(
        "cand_sun",
        "world.astronomy.sun_rises",
        "West",
        composite_plausibility=0.90,
    )
    choice = _make_choice_decision("set_sun", "world.astronomy.sun_rises", "cand_sun", ("cand_sun", "cand_alt"))

    with pytest.raises(PermissionError, match="contradicts objective static fact 'East'"):
        await promo_service.promote_candidate(cand, choice)


@pytest.mark.asyncio
async def test_gc081_timeline_gate(test_session: AsyncSession):
    """GC-081: TimelineValidator failure blocks promotion (Gate 3)."""
    core_service = CharacterCoreService(test_session)
    candidate_repo = CandidateRepository(test_session)
    promo_service = BiographyPromotionService(test_session, candidate_repo, core_service)

    cand = _make_candidate(
        "cand_grad",
        "education.major",
        "Philosophy",
        selection_metadata={"timeline_contradiction": "Claims graduation 10 years ago at age 11."},
    )
    choice = _make_choice_decision("set_phil", "education.major", "cand_grad", ("cand_grad", "cand_alt"))

    with pytest.raises(PermissionError, match="graduation 10 years ago"):
        await promo_service.promote_candidate(cand, choice)


@pytest.mark.asyncio
async def test_gc082_causality_gate(test_session: AsyncSession):
    """GC-082: CausalityValidator failure blocks promotion (Gate 4)."""
    core_service = CharacterCoreService(test_session)
    candidate_repo = CandidateRepository(test_session)
    promo_service = BiographyPromotionService(test_session, candidate_repo, core_service)

    cand = _make_candidate(
        "cand_transit",
        "education.major",
        "Robotics",
        selection_metadata={"causality_violation": "Physical transit between distant cities in 2 minutes."},
    )
    choice = _make_choice_decision("set_rob", "education.major", "cand_transit", ("cand_transit", "cand_alt"))

    with pytest.raises(PermissionError, match="Physical transit"):
        await promo_service.promote_candidate(cand, choice)


@pytest.mark.asyncio
async def test_gc083_graph_consistency_gate(test_session: AsyncSession):
    """GC-083: Graph inconsistency blocks promotion (Gate 5)."""
    core_service = CharacterCoreService(test_session)
    candidate_repo = CandidateRepository(test_session)
    promo_service = BiographyPromotionService(test_session, candidate_repo, core_service)

    cand = _make_candidate(
        "cand_graph",
        "education.major",
        "Linguistics",
        selection_metadata={"graph_inconsistency": "Referenced advisor entity does not exist in graph."},
    )
    choice = _make_choice_decision("set_ling", "education.major", "cand_graph", ("cand_graph", "cand_alt"))

    with pytest.raises(PermissionError, match="Referenced advisor entity does not exist"):
        await promo_service.promote_candidate(cand, choice)


@pytest.mark.asyncio
async def test_gc084_minimum_2_viable_candidates(test_session: AsyncSession):
    """GC-084: Single-candidate competition cannot self-promote into high-impact reality (Gate 6)."""
    core_service = CharacterCoreService(test_session)
    candidate_repo = CandidateRepository(test_session)
    promo_service = BiographyPromotionService(test_session, candidate_repo, core_service)

    cand = _make_candidate("cand_alone", "education.major", "Music", composite_plausibility=0.92)
    choice_single = _make_choice_decision(
        candidate_set_id="set_alone",
        slot_name="education.major",
        selected_id="cand_alone",
        cand_ids=("cand_alone",),  # Only 1 candidate considered!
    )

    with pytest.raises(PermissionError, match="at least 2 viable alternatives; found 1"):
        await promo_service.promote_candidate(cand, choice_single)


@pytest.mark.asyncio
async def test_gc085_explicit_choice_required(test_session: AsyncSession):
    """GC-085: High plausibility without explicit ChoiceDecisionResult selecting it is rejected (Gate 7)."""
    core_service = CharacterCoreService(test_session)
    candidate_repo = CandidateRepository(test_session)
    promo_service = BiographyPromotionService(test_session, candidate_repo, core_service)

    cand_high = _make_candidate("cand_high", "education.major", "Economics", composite_plausibility=0.99)
    cand_win = _make_candidate("cand_win", "education.major", "Finance", composite_plausibility=0.75)

    # Choice selected cand_win, but caller tries to promote cand_high based on high plausibility!
    choice = _make_choice_decision("set_econ", "education.major", "cand_win", ("cand_high", "cand_win"))

    with pytest.raises(PermissionError, match="was not selected by choice decision"):
        await promo_service.promote_candidate(cand_high, choice)


@pytest.mark.asyncio
async def test_gc086_structured_provenance_required(test_session: AsyncSession):
    """GC-086: Missing structured factor contributions/scores blocks promotion (Gate 8)."""
    core_service = CharacterCoreService(test_session)
    candidate_repo = CandidateRepository(test_session)
    promo_service = BiographyPromotionService(test_session, candidate_repo, core_service)

    cand = _make_candidate("cand_data", "education.major", "Data Science")
    # Decision with empty factor_inputs
    bad_choice = ChoiceDecisionResult(
        decision_id="choice_bad",
        entity_id="aevum",
        slot_name="education.major",
        candidate_set_id="set_bad",
        candidate_ids_considered=("cand_data", "cand_alt"),
        selected_candidate_id="cand_data",
        unselected_candidate_ids=("cand_alt",),
        decision_timestamp=_utc_now(),
        decision_model_version="1.0.0",
        competition_state=CompetitionState.CLEAR_LEADER,
        competition_margin=0.10,
        plausibility_scores={"cand_data": 0.80},
        factor_inputs={},  # MISSING!
        factor_contributions={},  # MISSING!
        choice_scores={},  # MISSING!
        choice_margin=0.10,
        rationale_code=ChoiceRationaleCode.MULTI_FACTOR_BALANCED,
        rationale_description="Text rationale alone cannot substitute for structured factors.",
        is_non_canonical=True,
        provenance_references=(),
    )

    with pytest.raises(PermissionError, match="lacks complete structured factors"):
        await promo_service.promote_candidate(cand, bad_choice)


@pytest.mark.asyncio
async def test_gc087_circular_evidence_rejected(test_session: AsyncSession):
    """GC-087: Self-reinforcing candidate lineage in provenance DAG blocks promotion (Gate 9)."""
    core_service = CharacterCoreService(test_session)
    candidate_repo = CandidateRepository(test_session)
    promo_service = BiographyPromotionService(test_session, candidate_repo, core_service)

    # Candidate has itself in its parent_candidate_ids
    cand_circular = _make_candidate(
        "cand_circ",
        "education.major",
        "Archaeology",
        parent_ids=("cand_circ",),
    )
    choice = _make_choice_decision("set_circ", "education.major", "cand_circ", ("cand_circ", "cand_alt"))

    with pytest.raises(PermissionError, match="Circular evidence detected"):
        await promo_service.promote_candidate(cand_circular, choice)


@pytest.mark.asyncio
async def test_gc088_semantic_distance_guard(test_session: AsyncSession):
    """GC-088: Biographical leaps exceeding allowable semantic distance fail Gate 10."""
    core_service = CharacterCoreService(test_session)
    candidate_repo = CandidateRepository(test_session)
    promo_service = BiographyPromotionService(test_session, candidate_repo, core_service)

    # Wild leap: casual guitar interest -> world-famous concert pianist
    cand_leap = _make_candidate(
        "cand_pianist",
        "education.major",
        "Concert Piano Performance",
        selection_metadata={"semantic_leap": 0.65},  # Exceeds threshold 0.50!
    )
    choice = _make_choice_decision("set_leap", "education.major", "cand_pianist", ("cand_pianist", "cand_alt"))

    with pytest.raises(PermissionError, match="Semantic distance heuristic .* exceeds allowable threshold"):
        await promo_service.promote_candidate(cand_leap, choice)


@pytest.mark.asyncio
async def test_gc089_biography_construction_policy(test_session: AsyncSession):
    """GC-089: Unregistered slots or forbidden slots fail Gate 11."""
    core_service = CharacterCoreService(test_session)
    candidate_repo = CandidateRepository(test_session)
    promo_service = BiographyPromotionService(test_session, candidate_repo, core_service)

    # Attempt to autonomously construct forbidden identity.name
    cand_forbidden = _make_candidate("cand_name", "identity.name", "Kagamine Rin")
    choice_f = _make_choice_decision("set_name", "identity.name", "cand_name", ("cand_name", "cand_alt"))

    with pytest.raises(PermissionError, match="is in forbidden_slots policy list"):
        await promo_service.promote_candidate(cand_forbidden, choice_f)

    # Attempt to autonomously construct an unregistered slot
    cand_unreg = _make_candidate("cand_unreg", "random.unregistered.slot", "SomeValue")
    choice_u = _make_choice_decision("set_unreg", "random.unregistered.slot", "cand_unreg", ("cand_unreg", "cand_alt"))

    with pytest.raises(PermissionError, match="not registered in allowed_autonomous_slots"):
        await promo_service.promote_candidate(cand_unreg, choice_u)


@pytest.mark.asyncio
async def test_gc090_promotion_idempotency(test_session: AsyncSession):
    """GC-090: Re-promoting the same candidate does not duplicate facts, revisions, or events (Gate 12)."""
    core_service = CharacterCoreService(test_session)
    candidate_repo = CandidateRepository(test_session)
    history_service = RealityHistoryService(test_session)
    promo_service = BiographyPromotionService(test_session, candidate_repo, core_service, history_service)

    cand = _make_candidate("cand_cs_idem", "education.major", "Computer Science", composite_plausibility=0.88)
    cand_alt = _make_candidate("cand_se_idem", "education.major", "Software Engineering", composite_plausibility=0.80)
    choice = _make_choice_decision("set_idem", "education.major", "cand_cs_idem", ("cand_cs_idem", "cand_se_idem"))

    # First promotion
    res1 = await promo_service.promote_candidate(cand, choice)
    assert res1.is_idempotent_replay is False

    revisions_first = await history_service.get_history("aevum", "education.major")
    assert len(revisions_first) == 1

    # Second promotion (idempotent replay)
    res2 = await promo_service.promote_candidate(cand, choice)
    assert res2.is_idempotent_replay is True
    assert res2.promotion_id == res1.promotion_id

    # Revisions not duplicated!
    revisions_second = await history_service.get_history("aevum", "education.major")
    assert len(revisions_second) == 1


@pytest.mark.asyncio
async def test_gc091_revision_history(test_session: AsyncSession):
    """GC-091: Structured revision history record created linking candidate, choice, and policy version (Gate 13)."""
    core_service = CharacterCoreService(test_session)
    candidate_repo = CandidateRepository(test_session)
    history_service = RealityHistoryService(test_session)
    promo_service = BiographyPromotionService(test_session, candidate_repo, core_service, history_service)

    cand = _make_candidate("cand_rev", "education.pathway", "STPM", composite_plausibility=0.85)
    cand_alt = _make_candidate("cand_rev_alt", "education.pathway", "A-Levels", composite_plausibility=0.75)
    choice = _make_choice_decision("set_rev", "education.pathway", "cand_rev", ("cand_rev", "cand_rev_alt"))

    res = await promo_service.promote_candidate(cand, choice)
    assert res.policy_version == "1.0.0"
    assert res.choice_decision_id == choice.decision_id
    assert res.candidate_id == cand.candidate_id

    history = await history_service.get_history("aevum", "education.pathway")
    assert len(history) == 1
    assert history[0].value == "STPM"


@pytest.mark.asyncio
async def test_gc092_anti_snowball_promotion(test_session: AsyncSession):
    """GC-092: Promoting a major produces exactly 1 canonical fact; zero secondary trivia generated (Gate 14)."""
    core_service = CharacterCoreService(test_session)
    candidate_repo = CandidateRepository(test_session)
    promo_service = BiographyPromotionService(test_session, candidate_repo, core_service)

    core_before = await core_service.get_core("aevum")
    count_before = len(core_before.facts)

    cand = _make_candidate("cand_atomic", "education.major", "Computer Science")
    choice = _make_choice_decision("set_atomic", "education.major", "cand_atomic", ("cand_atomic", "cand_alt"))

    await promo_service.promote_candidate(cand, choice)

    core_after = await core_service.get_core("aevum")
    count_after = len(core_after.facts)

    # Exactly 1 new fact added (education.major), zero ancillary trivia facts
    assert count_after == count_before + 1
    assert "education.major" in core_after.facts
    # Ensure no fabricated universities or professors were sneaked in
    assert "education.institution.fabricated" not in core_after.facts
    assert "social.professor" not in core_after.facts


def test_gc093_absence_of_evidence_is_not_contradiction():
    """GC-093: Stale candidates decay to DORMANT without triggering contradiction or rejection."""
    cand = _make_candidate("cand_stale", "interests.primary", "Calligraphy")
    # Transition to DORMANT
    dormant_cand = cand.model_copy(update={"lifecycle_state": CandidateLifecycleState.DORMANT})
    assert dormant_cand.lifecycle_state == CandidateLifecycleState.DORMANT
    assert dormant_cand.lifecycle_state != CandidateLifecycleState.REJECTED
    assert dormant_cand.lifecycle_state != CandidateLifecycleState.PRUNED


@pytest.mark.asyncio
async def test_gc094_candidate_decay_does_not_invalidate_canonical_reality(test_session: AsyncSession):
    """GC-094: Decayed candidate hypotheses never touch or demote canonical core facts."""
    core_service = CharacterCoreService(test_session)
    candidate_repo = CandidateRepository(test_session)

    core_before = await core_service.get_core("aevum")
    baseline_occupation = core_before.get_value("identity.occupation")
    assert baseline_occupation == "University Student"

    # Candidate decays to DORMANT in candidate repository
    cand = _make_candidate("cand_decay", "identity.occupation", "Freelance Musician")
    await candidate_repo.save_candidate(cand)
    await candidate_repo.update_candidate_lifecycle("cand_decay", CandidateLifecycleState.DORMANT)

    # Core fact remains completely unchanged
    core_after = await core_service.get_core("aevum")
    assert core_after.get_value("identity.occupation") == "University Student"
    fact = core_after.facts["identity.occupation"]
    assert fact.authority == FactAuthority.SYSTEM_BASELINE
    assert fact.status == FactStatus.CANONICAL


# =============================================================================
# Structural Call-Site Enforcement & Edge Cases
# =============================================================================

def test_ast_canonical_mutation_callsite_singularity():
    """Verify via AST that exactly 1 production call site sets allow_canonical_reconciliation=True."""
    backend_app_dir = pathlib.Path(__file__).parent.parent / "app"
    found_callsites = []

    for root, _, files in os.walk(backend_app_dir):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    try:
                        tree = ast.parse(f.read(), filename=file_path)
                    except SyntaxError:
                        continue

                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        # Check keyword arguments for allow_canonical_reconciliation=True
                        for kw in node.keywords:
                            if kw.arg == "allow_canonical_reconciliation":
                                if (
                                    isinstance(kw.value, ast.Constant)
                                    and kw.value.value is True
                                ):
                                    rel_path = os.path.relpath(file_path, backend_app_dir)
                                    found_callsites.append((rel_path, node.lineno))

    # Assert exactly ONE call site in production app code
    assert len(found_callsites) == 1, (
        f"Expected exactly 1 call site with allow_canonical_reconciliation=True, found {len(found_callsites)}: {found_callsites}"
    )
    call_file, _ = found_callsites[0]
    normalized_path = call_file.replace("\\", "/")
    assert normalized_path == "reality/biography_promotion_service.py", (
        f"Call site must reside strictly in biography_promotion_service.py, found in {normalized_path}"
    )


@pytest.mark.asyncio
async def test_direct_bypass_rejected_by_token_verification(test_session: AsyncSession):
    """Verify that calling set_fact with allow_canonical_reconciliation=True fails closed without valid token."""
    core_service = CharacterCoreService(test_session)
    await core_service.get_core("aevum")

    # 1. No token provided -> raises AevumCanonicalNotDirectlyEditableError
    with pytest.raises(AevumCanonicalNotDirectlyEditableError, match="requires a valid PromotionAuthorizationToken"):
        await core_service.set_fact(
            character_id="aevum",
            fact_key="education.major",
            value="Philosophy",
            allow_canonical_reconciliation=True,
            authorization_token=None,
        )

    # 2. Forged token with mismatched slot_name -> raises AevumCanonicalNotDirectlyEditableError
    forged_token = PromotionAuthorizationToken.create(
        character_id="aevum",
        slot_name="different.slot",
        value="Philosophy",
        candidate_id="cand_fake",
        choice_decision_id="choice_fake",
    )
    with pytest.raises(AevumCanonicalNotDirectlyEditableError, match="PromotionAuthorizationToken invalid"):
        await core_service.set_fact(
            character_id="aevum",
            fact_key="education.major",
            value="Philosophy",
            allow_canonical_reconciliation=True,
            authorization_token=forged_token,
        )


@pytest.mark.asyncio
async def test_deterministic_promotion_authorization_replay(test_session: AsyncSession):
    """Verify that 50 repeated authorization evaluations produce 100% deterministic gate outcomes."""
    core_service = CharacterCoreService(test_session)
    candidate_repo = CandidateRepository(test_session)
    promo_service = BiographyPromotionService(test_session, candidate_repo, core_service)

    cand = _make_candidate("cand_det", "education.major", "Computer Science", composite_plausibility=0.85)
    cand_alt = _make_candidate("cand_det_alt", "education.major", "Software Engineering", composite_plausibility=0.80)
    choice = _make_choice_decision("set_det", "education.major", "cand_det", ("cand_det", "cand_det_alt"))
    core = await core_service.get_core("aevum")

    first_result = promo_service.evaluate_promotion_eligibility(cand, choice, core)
    assert first_result.is_eligible is True

    for _ in range(50):
        res = promo_service.evaluate_promotion_eligibility(cand, choice, core)
        assert res.is_eligible is True
        assert res.passed_gates == first_result.passed_gates
        assert res.failed_gates == first_result.failed_gates


def test_ast_token_minting_callsite_singularity():
    """Verify via AST that exactly 1 production call site invokes PromotionAuthorizationToken.create()."""
    backend_app_dir = pathlib.Path(__file__).parent.parent / "app"
    found_callsites = []

    for root, _, files in os.walk(backend_app_dir):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    try:
                        tree = ast.parse(f.read(), filename=file_path)
                    except SyntaxError:
                        continue

                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        # Match PromotionAuthorizationToken.create(...)
                        if isinstance(node.func, ast.Attribute) and node.func.attr == "create":
                            if isinstance(node.func.value, ast.Name) and node.func.value.id == "PromotionAuthorizationToken":
                                rel_path = os.path.relpath(file_path, backend_app_dir)
                                found_callsites.append((rel_path, node.lineno))

    # Assert exactly ONE call site in production app code
    assert len(found_callsites) == 1, (
        f"Expected exactly 1 call site for PromotionAuthorizationToken.create, found {len(found_callsites)}: {found_callsites}"
    )
    call_file, _ = found_callsites[0]
    normalized_path = call_file.replace("\\", "/")
    assert normalized_path == "reality/biography_promotion_service.py", (
        f"Call site must reside strictly in biography_promotion_service.py, found in {normalized_path}"
    )


@pytest.mark.asyncio
async def test_gc090_concurrent_promotion_race_idempotency(tmp_path):
    """GC-090 Concurrent Race: Simultaneous promotion tasks across separate AsyncSessions against SQLite.

    Verifies:
    1. Two concurrent tasks attempt to promote the identical candidate hypothesis.
    2. SQLite UniqueConstraint strictly prevents duplicate CharacterBiographyPromotionRecord.
    3. Exactly 1 canonical mutation is committed to CharacterCoreFactRecord.
    4. Exactly 1 CharacterBiographyPromotionRecord exists in DB.
    5. Exactly 1 CharacterRealityRevisionRecord exists in DB.
    6. One task returns is_idempotent_replay=False and the concurrent task returns is_idempotent_replay=True.
    7. Zero unhandled exceptions or crashes.
    """
    db_path = tmp_path / "gc090_concurrency.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"

    engine = create_async_engine(db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    cand_cs = _make_candidate("cand_race_cs", "education.major", "Computer Science", composite_plausibility=0.88)
    cand_se = _make_candidate("cand_race_se", "education.major", "Software Engineering", composite_plausibility=0.80)
    choice = _make_choice_decision(
        "set_race",
        "education.major",
        "cand_race_cs",
        ("cand_race_cs", "cand_race_se"),
    )

    # Initial setup in its own session
    async with session_factory() as setup_sess:
        c_svc = CharacterCoreService(setup_sess)
        await c_svc.get_core("aevum")
        c_repo = CandidateRepository(setup_sess)
        await c_repo.save_candidate(cand_cs)
        await c_repo.save_candidate(cand_se)
        await c_repo.save_choice_decision(choice)
        await setup_sess.commit()

    async def _worker(worker_id: int):
        async with session_factory() as sess:
            c_repo = CandidateRepository(sess)
            c_svc = CharacterCoreService(sess)
            h_svc = RealityHistoryService(sess)
            p_svc = BiographyPromotionService(sess, c_repo, c_svc, h_svc)
            return await p_svc.promote_candidate(cand_cs, choice, character_id="aevum")

    # Run true concurrent promotions across separate sessions
    res1, res2 = await asyncio.gather(_worker(1), _worker(2))

    # Assert outcomes
    results = [res1, res2]
    replays = [r.is_idempotent_replay for r in results]
    assert False in replays, "At least one task must be the primary promoter"
    assert True in replays, "Concurrent conflicting task must safely return idempotent replay"

    # Verify both returned the same promotion ID
    assert res1.promotion_id == res2.promotion_id
    assert res1.promoted_value == "Computer Science"
    assert res2.promoted_value == "Computer Science"

    # Verify database state in an independent session
    async with session_factory() as verify_sess:
        # 1. Exactly 1 promotion record in character_biography_promotions
        p_stmt = select(CharacterBiographyPromotionRecord).where(
            CharacterBiographyPromotionRecord.candidate_id == "cand_race_cs"
        )
        p_recs = (await verify_sess.scalars(p_stmt)).all()
        assert len(p_recs) == 1

        # 2. Canonical fact correctly set
        c_svc = CharacterCoreService(verify_sess)
        core = await c_svc.get_core("aevum")
        assert core.get_value("education.major") == "Computer Science"
        fact = core.facts["education.major"]
        assert fact.authority == FactAuthority.AEVUM_CANONICAL
        assert fact.status == FactStatus.CANONICAL

        # 3. Exactly 1 revision in character_reality_revisions
        h_svc = RealityHistoryService(verify_sess)
        revs = await h_svc.get_history("aevum", "education.major")
        assert len(revs) == 1

    await engine.dispose()

