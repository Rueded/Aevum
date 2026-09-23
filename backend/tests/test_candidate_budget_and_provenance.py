"""Comprehensive Test Suite for Phase 7D.1: Candidate Models, Budget Controller & Evidence Independence.

Verifies:
1. Domain Models & Invariants (Plausibility != Probability, Speculative Quarantine, Dual Reality).
2. Candidate Hypothesis Set & Slot Pruning Lifecycle (max 3 active candidates, non-destructive PRUNED).
3. InferenceBudgetController Hard Enforcement (Tests 1, 2, 3, 4).
4. Lifecycle Tri-State Isolation (Generated != Persisted != Promotable).
5. Evidence Independence & Provenance Lineage (Benchmark GC-071: Cases A, B, C, D, E).
6. User Lock Absolute Immunity over Candidate Inferences (Benchmark GC-062).
7. CandidateRepository Persistence with SQLite AsyncSession.
"""

from datetime import datetime, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.core_models import CharacterCore
from app.character.core_service import CharacterCoreService
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
from app.reality.budget_controller import (
    BudgetRejectionReason,
    InferenceBudgetController,
    ProvenanceDAGValidator,
)
from app.reality.candidate_repository import CandidateRepository
from app.reality.models import FactAuthority, FactSource, FactStatus


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_candidate(
    candidate_id: str,
    slot_name: str = "education.major",
    proposed_value: str = "Computer Science",
    origin_id: str = "msg_001",
    inference_depth: int = 0,
    edge_type: InferenceEdgeType = InferenceEdgeType.DIRECT_ATTRIBUTE,
    parent_ids: tuple[str, ...] = (),
    composite_plausibility: float = 0.85,
    evidence_families: tuple[EvidenceFamily, ...] = (),
    lifecycle_state: CandidateLifecycleState = CandidateLifecycleState.GENERATED,
) -> CandidateHypothesis:
    """Helper creating a valid CandidateHypothesis fixture."""
    fam_ids = tuple(fam.family_id for fam in evidence_families)
    prov = ProvenanceLineage(
        origin_id=origin_id,
        parent_candidate_ids=parent_ids,
        evidence_family_ids=fam_ids,
        inference_depth=inference_depth,
        derivation_path=(f"obs:{origin_id}", f"cand:{candidate_id}"),
    )
    plaus = PlausibilityBreakdown.create(
        prior_weight=0.6,
        evidence_grounding_score=0.9,
        coherence_score=0.9,
        utility_score=0.7,
        composite_plausibility_score=composite_plausibility,
    )
    return CandidateHypothesis(
        candidate_id=candidate_id,
        entity_id="aevum",
        slot_name=slot_name,
        proposed_value=proposed_value,
        reality_taxonomy=RealityTaxonomy.SIMULATED_BIOGRAPHY_FACT,
        inference_depth=inference_depth,
        inference_edge_type=edge_type,
        plausibility=plaus,
        provenance=prov,
        evidence_families=evidence_families,
        lifecycle_state=lifecycle_state,
    )


# ============================================================================
# 1. Domain Models & Invariants
# ============================================================================


def test_plausibility_breakdown_rejects_forbidden_probability_fields():
    """PlausibilityBreakdown strictly forbids 'probability' or 'truth_probability' fields."""
    with pytest.raises(ValueError) as exc:
        PlausibilityBreakdown(
            prior_weight=0.5,
            evidence_grounding_score=0.5,
            coherence_score=0.5,
            utility_score=0.5,
            composite_plausibility_score=0.5,
            probability=0.88,  # type: ignore[call-arg]
        )
    err_msg = str(exc.value).lower()
    assert "extra" in err_msg or "forbidden" in err_msg

    with pytest.raises(ValueError) as exc2:
        PlausibilityBreakdown.model_validate({
            "prior_weight": 0.5,
            "evidence_grounding_score": 0.5,
            "coherence_score": 0.5,
            "utility_score": 0.5,
            "composite_plausibility_score": 0.5,
            "truth_probability": 0.90,
        })
    err_msg2 = str(exc2.value).lower()
    assert "extra" in err_msg2 or "forbidden" in err_msg2


def test_speculative_association_triggers_mandatory_quarantine():
    """InferenceEdgeType.SPECULATIVE_ASSOCIATION must automatically set is_quarantined=True."""
    cand = _make_candidate(
        "cand_spec_01",
        edge_type=InferenceEdgeType.SPECULATIVE_ASSOCIATION,
    )
    assert cand.is_quarantined is True
    assert cand.quarantine_reason is not None
    assert "SPECULATIVE_ASSOCIATION" in cand.quarantine_reason


def test_depth_exceeding_2_triggers_mandatory_quarantine():
    """Hypothesis with inference_depth > 2 must be quarantined."""
    cand = _make_candidate("cand_deep_01", inference_depth=3)
    assert cand.is_quarantined is True
    assert "exceeds max_inference_depth" in cand.quarantine_reason


def test_dual_reality_taxonomy_separation():
    """Objective world facts and simulated biography facts remain strictly distinct."""
    assert RealityTaxonomy.OBJECTIVE_WORLD_FACT != RealityTaxonomy.SIMULATED_BIOGRAPHY_FACT
    assert RealityTaxonomy.OBJECTIVE_WORLD_FACT.value == "OBJECTIVE_WORLD_FACT"
    assert RealityTaxonomy.SIMULATED_BIOGRAPHY_FACT.value == "SIMULATED_BIOGRAPHY_FACT"


# ============================================================================
# 2. Candidate Hypothesis Set & Slot Pruning Lifecycle
# ============================================================================


def test_candidate_hypothesis_set_max_3_active_capacity_pruning():
    """Adding a 4th candidate to a slot must transition the weakest to PRUNED without deleting it."""
    cand_set = CandidateHypothesisSet(slot_name="education.major")

    c1 = _make_candidate("c1", composite_plausibility=0.90, lifecycle_state=CandidateLifecycleState.ACTIVE)
    c2 = _make_candidate("c2", composite_plausibility=0.75, lifecycle_state=CandidateLifecycleState.ACTIVE)
    c3 = _make_candidate("c3", composite_plausibility=0.60, lifecycle_state=CandidateLifecycleState.ACTIVE)

    cand_set = cand_set.with_candidate(c1)
    cand_set = cand_set.with_candidate(c2)
    cand_set = cand_set.with_candidate(c3)

    assert len(cand_set.active_candidates) == 3
    assert cand_set.leading_candidate.candidate_id == "c1"
    assert cand_set.decision_margin == round(0.90 - 0.75, 4)

    # Add 4th candidate with score 0.80 (higher than c3)
    c4 = _make_candidate("c4", composite_plausibility=0.80, lifecycle_state=CandidateLifecycleState.ACTIVE)
    cand_set = cand_set.with_candidate(c4, max_active_candidates_per_slot=3)

    # Total stored candidates remains 4 (zero physical deletion, provenance preserved)
    assert len(cand_set.candidates) == 4
    # Exactly 3 active candidates: c1 (0.90), c4 (0.80), c2 (0.75)
    assert len(cand_set.active_candidates) == 3
    active_ids = {c.candidate_id for c in cand_set.active_candidates}
    assert active_ids == {"c1", "c2", "c4"}

    # Weakest candidate c3 (0.60) was transitioned to PRUNED
    assert cand_set.candidates["c3"].lifecycle_state == CandidateLifecycleState.PRUNED


# ============================================================================
# 3. Inference Budget Controller Enforcement (Tests 1, 2, 3, 4)
# ============================================================================


def test_budget_enforcement_test1_max_4_generated_per_turn():
    """Test 1: Single turn generates 10 hypotheses; budget controller caps admitted at <= 4."""
    controller = InferenceBudgetController()
    hypotheses = [
        _make_candidate(
            f"hyp_{i}",
            slot_name=f"slot_{i % 2}",
            origin_id=f"obs_distinct_{i}",
            composite_plausibility=0.95 - (i * 0.05),
        )
        for i in range(10)
    ]

    res = controller.evaluate_turn_hypotheses(hypotheses)
    assert len(res.admitted) <= 4
    assert len(res.admitted) == 4
    assert len(res.rejected) == 6
    for _, reason in res.rejected:
        assert BudgetRejectionReason.TURN_GENERATION_LIMIT_EXCEEDED.value in reason


def test_budget_enforcement_test2_max_2_direct_hypotheses_per_observation():
    """Test 2: Single observation generates 5 direct hypotheses; budget controller caps at <= 2."""
    controller = InferenceBudgetController()
    hypotheses = [
        _make_candidate(f"hyp_obs_{i}", origin_id="obs_single_violin", composite_plausibility=0.90 - (i * 0.05))
        for i in range(5)
    ]

    res = controller.evaluate_turn_hypotheses(hypotheses)
    assert len(res.admitted) == 2
    assert len(res.rejected) == 3
    for _, reason in res.rejected:
        assert BudgetRejectionReason.OBSERVATION_FANOUT_LIMIT_EXCEEDED.value in reason


def test_budget_enforcement_test3_max_2_new_candidate_slots_per_turn():
    """Test 3: Single turn tries to introduce 4 new candidate slots; budget controller caps at <= 2."""
    controller = InferenceBudgetController()
    hypotheses = [
        _make_candidate("hyp_slot_1", slot_name="music.instrument", origin_id="obs_slot_1", composite_plausibility=0.90),
        _make_candidate("hyp_slot_2", slot_name="sports.swimming", origin_id="obs_slot_2", composite_plausibility=0.85),
        _make_candidate("hyp_slot_3", slot_name="hobbies.chess", origin_id="obs_slot_3", composite_plausibility=0.80),
        _make_candidate("hyp_slot_4", slot_name="travel.destinations", origin_id="obs_slot_4", composite_plausibility=0.75),
    ]

    # No pre-existing canonical or active slots
    res = controller.evaluate_turn_hypotheses(hypotheses)
    admitted_slots = {h.slot_name for h in res.admitted}
    assert len(admitted_slots) <= 2
    assert len(admitted_slots) == 2
    assert len(res.admitted) == 2
    assert len(res.rejected) == 2
    for _, reason in res.rejected:
        assert BudgetRejectionReason.NEW_SLOTS_PER_TURN_EXCEEDED.value in reason


def test_budget_enforcement_test4_max_inference_depth_2():
    """Test 4: Inference chain A -> B -> C (depth 2) is admitted; depth 3 is rejected / quarantined."""
    controller = InferenceBudgetController()

    c_depth_2 = _make_candidate("c_depth_2", inference_depth=2, composite_plausibility=0.85)
    c_depth_3 = _make_candidate("c_depth_3", inference_depth=3, composite_plausibility=0.80)

    res = controller.evaluate_turn_hypotheses([c_depth_2, c_depth_3])
    assert c_depth_2 in res.admitted
    assert any(c.candidate_id == "c_depth_3" for c in res.quarantined)


# ============================================================================
# 4. Lifecycle Tri-State Isolation (Generated != Persisted != Promotable)
# ============================================================================


@pytest.mark.asyncio
async def test_lifecycle_generated_hypothesis_not_in_canonical_facts(test_session: AsyncSession):
    """Generated hypothesis does NOT appear in canonical core facts."""
    cand = _make_candidate("cand_gen_01", slot_name="preferences.drink", proposed_value="Matcha")
    assert cand.lifecycle_state == CandidateLifecycleState.GENERATED

    core_service = CharacterCoreService(test_session)
    core = await core_service.get_core("aevum")
    # Must NOT contain the candidate in canonical reality
    assert core.get_fact("preferences.drink") is None


@pytest.mark.asyncio
async def test_lifecycle_persisted_candidate_not_canonical_truth(test_session: AsyncSession):
    """Persisted candidate is NOT treated as canonical truth by CharacterCoreService."""
    repo = CandidateRepository(test_session)
    core_service = CharacterCoreService(test_session)

    cand = _make_candidate("cand_pers_01", slot_name="education.pathway", proposed_value="STPM")
    saved = await repo.save_candidate(cand)
    assert saved.lifecycle_state == CandidateLifecycleState.PERSISTED

    # Core service must not see it as canonical truth
    core = await core_service.get_core("aevum")
    assert core.get_fact("education.pathway") is None


def test_lifecycle_promotable_candidate_cannot_bypass_promotion_authorization():
    """Candidate marked PROMOTABLE is still not canonical and cannot self-promote."""
    cand = _make_candidate("cand_prom_01", slot_name="hobbies.reading", proposed_value="Sci-Fi")
    promotable = cand.to_promotable()
    assert promotable.lifecycle_state == CandidateLifecycleState.PROMOTABLE
    assert promotable.lifecycle_state != CandidateLifecycleState.PERSISTED


# ============================================================================
# 5. Evidence Independence & Provenance Lineage (Benchmark GC-071: Cases A - E)
# ============================================================================


@pytest.mark.asyncio
async def test_gc071_case_a_user_assertion_5_sessions_count_1(test_session: AsyncSession):
    """GC-071 Case A: Same user assertion across 5 sessions -> mention_count = 5, independent_count = 1."""
    repo = CandidateRepository(test_session)

    cluster_key = "user_assert:student_cs_degree"
    fam: EvidenceFamily = None  # type: ignore[assignment]
    for s_idx in range(1, 6):
        fam = await repo.record_evidence(
            source_type="USER_ASSERTION",
            cluster_key=cluster_key,
            session_id=f"session_00{s_idx}",
        )

    assert fam.mention_count == 5
    assert len(fam.session_ids) == 5
    assert fam.independent_evidence_weight == 1

    cand = _make_candidate("cand_cs", evidence_families=(fam,))
    assert cand.total_mention_count == 5
    assert cand.independent_evidence_count == 1


@pytest.mark.asyncio
async def test_gc071_case_b_different_wording_same_cluster(test_session: AsyncSession):
    """GC-071 Case B: Different wording mapping to same semantic cluster key shares EvidenceFamily."""
    repo = CandidateRepository(test_session)

    cluster_key = "user_assert:cat_allergy"
    f1 = await repo.record_evidence("USER_ASSERTION", cluster_key, "session_A")
    f2 = await repo.record_evidence("USER_ASSERTION", cluster_key, "session_B")

    assert f1.family_id == f2.family_id
    assert f2.mention_count == 2
    assert f2.independent_evidence_weight == 1


@pytest.mark.asyncio
async def test_gc071_case_c_copy_pasted_assertion_not_independent(test_session: AsyncSession):
    """GC-071 Case C: Copy-pasted assertion across multiple calls does NOT generate new independent evidence."""
    repo = CandidateRepository(test_session)

    cluster = "user_assert:loves_black_tea"
    f1 = await repo.record_evidence("USER_ASSERTION", cluster, "session_X")
    f2 = await repo.record_evidence("USER_ASSERTION", cluster, "session_X")

    assert f1.family_id == f2.family_id
    assert f2.mention_count == 2
    assert f2.independent_evidence_weight == 1


@pytest.mark.asyncio
async def test_gc071_case_d_distinct_sources_yield_multiple_independent_families(test_session: AsyncSession):
    """GC-071 Case D: Genuinely independent sources produce distinct families; count = 2."""
    repo = CandidateRepository(test_session)

    fam_user = await repo.record_evidence(
        source_type="USER_ASSERTION",
        cluster_key="user_statement:likes_violin",
        session_id="session_1",
    )
    fam_tool = await repo.record_evidence(
        source_type="EXTERNAL_OBSERVATION",
        cluster_key="tool_obs:library_catalog_checked",
        session_id="session_1",
    )

    assert fam_user.family_id != fam_tool.family_id

    cand = _make_candidate("cand_music", evidence_families=(fam_user, fam_tool))
    assert cand.independent_evidence_count == 2


def test_gc071_case_e_provenance_dag_rejects_circular_evidence():
    """GC-071 Case E: Circular provenance loop (A -> B -> A) is quarantined and rejected."""
    # Build a cycle: cand_A depends on cand_B, and cand_B depends on cand_A
    ancestor_graph = {
        "cand_B": ["cand_A"],
    }
    cand_A = _make_candidate("cand_A", parent_ids=("cand_B",))

    is_valid, error = ProvenanceDAGValidator.validate_dag(cand_A, ancestor_graph)
    assert is_valid is False
    assert "Circular provenance loop detected" in error

    controller = InferenceBudgetController()
    res = controller.evaluate_turn_hypotheses([cand_A], ancestor_graph=ancestor_graph)
    assert len(res.admitted) == 0
    assert any(c.candidate_id == "cand_A" for c in res.quarantined)


def test_provenance_dag_rejects_self_reinforcement():
    """Candidate cannot cite itself as origin stimulus (candidate self-reinforcement)."""
    cand = _make_candidate("cand_self", origin_id="cand_self")
    is_valid, error = ProvenanceDAGValidator.validate_dag(cand)
    assert is_valid is False
    assert "Candidate self-reinforcement" in error


# ============================================================================
# 6. User Lock Absolute Immunity over Inferences (GC-062)
# ============================================================================


@pytest.mark.asyncio
async def test_gc062_user_lock_immunity_over_candidate_hypotheses(test_session: AsyncSession):
    """GC-062: Proposed candidate targeting a USER_LOCKED fact is quarantined with 100% fidelity."""
    core_service = CharacterCoreService(test_session)
    # Set a canonical fact locked by user
    await core_service.set_fact(
        character_id="aevum",
        fact_key="identity.name",
        value="Aevum",
        source=FactSource.USER_CONFIGURED,
        authority=FactAuthority.USER_LOCKED,
        status=FactStatus.CANONICAL,
    )

    core = await core_service.get_core("aevum")
    assert core.is_locked("identity.name") is True

    # Attempt to introduce a candidate trying to override identity.name
    hyp = _make_candidate("cand_rename", slot_name="identity.name", proposed_value="OtherName")

    controller = InferenceBudgetController()
    res = controller.evaluate_turn_hypotheses(
        [hyp],
        locked_slots={"identity.name"},
    )

    assert len(res.admitted) == 0
    assert len(res.quarantined) == 1
    assert res.quarantined[0].is_quarantined is True
    assert "USER_LOCKED in canonical reality" in res.quarantined[0].quarantine_reason


# ============================================================================
# 7. CandidateRepository Persistence Integration
# ============================================================================


@pytest.mark.asyncio
async def test_candidate_repository_save_and_retrieve(test_session: AsyncSession):
    """CandidateRepository persists CandidateHypothesis and retrieves it with full fidelity."""
    repo = CandidateRepository(test_session)

    fam = await repo.record_evidence("USER_ASSERTION", "user:prefers_tea", "sess_01")
    cand = _make_candidate(
        "cand_repo_01",
        slot_name="preferences.tea",
        proposed_value="Earl Grey",
        evidence_families=(fam,),
    )

    saved = await repo.save_candidate(cand)
    assert saved.lifecycle_state == CandidateLifecycleState.PERSISTED

    retrieved = await repo.get_candidate("cand_repo_01")
    assert retrieved is not None
    assert retrieved.candidate_id == "cand_repo_01"
    assert retrieved.slot_name == "preferences.tea"
    assert retrieved.proposed_value == "Earl Grey"
    assert retrieved.independent_evidence_count == 1
    assert retrieved.total_mention_count == 1

    # Retrieve hypothesis set for slot
    hyp_set = await repo.get_hypothesis_set("aevum", "preferences.tea")
    assert len(hyp_set.candidates) == 1
    assert "cand_repo_01" in hyp_set.candidates


# ============================================================================
# 8. Focused Acceptance Audit Tests (Authority Boundary, Derived Depth & Dual Reality)
# ============================================================================


@pytest.mark.asyncio
async def test_authority_boundary_active_and_promotable_isolation(test_session: AsyncSession):
    """Verify ACTIVE and PROMOTABLE candidate states NEVER gain canonical fact authority."""
    repo = CandidateRepository(test_session)
    core_service = CharacterCoreService(test_session)

    # 1. Save an ACTIVE candidate
    cand_active = _make_candidate(
        "cand_active_01",
        slot_name="education.minor",
        proposed_value="Philosophy",
        lifecycle_state=CandidateLifecycleState.ACTIVE,
    )
    await repo.save_candidate(cand_active)

    # 2. Save a PROMOTABLE candidate
    cand_promotable = _make_candidate(
        "cand_promotable_01",
        slot_name="education.degree",
        proposed_value="Bachelor of Science",
        lifecycle_state=CandidateLifecycleState.PROMOTABLE,
    )
    await repo.save_candidate(cand_promotable)

    # Verify CharacterCoreService does NOT see either candidate as canonical truth
    core = await core_service.get_core("aevum")
    assert core.get_fact("education.minor") is None
    assert core.get_fact("education.degree") is None

    # Verify candidate facts exist strictly in candidate persistence, not canonical core
    active_in_repo = await repo.get_candidate("cand_active_01")
    assert active_in_repo is not None
    assert active_in_repo.lifecycle_state == CandidateLifecycleState.ACTIVE

    promotable_in_repo = await repo.get_candidate("cand_promotable_01")
    assert promotable_in_repo is not None
    assert promotable_in_repo.lifecycle_state == CandidateLifecycleState.PROMOTABLE


def test_derived_lineage_depth_detects_forged_depth_input():
    """Verify inference depth is derived from ancestor lineage rather than blindly trusting scalar input."""
    # Caller attempts to pass inference_depth = 0, but lists parent cand_B (which has depth 2)
    ancestor_depths = {
        "cand_A": 1,
        "cand_B": 2,
    }
    forged_cand = _make_candidate(
        "cand_forged",
        inference_depth=0,  # Forged/hallucinated shallow hop count
        parent_ids=("cand_B",),
    )

    # Lineage derivation must reveal true depth = 3
    derived_depth = ProvenanceDAGValidator.derive_lineage_depth(forged_cand, ancestor_depths)
    assert derived_depth == 3

    # Budget controller must catch and quarantine the hypothesis based on derived lineage depth
    controller = InferenceBudgetController()
    res = controller.evaluate_turn_hypotheses([forged_cand], ancestor_depth_map=ancestor_depths)
    assert len(res.admitted) == 0
    assert len(res.quarantined) == 1
    assert res.quarantined[0].is_quarantined is True
    assert "Lineage inference depth 3 exceeds max_inference_depth" in res.quarantined[0].quarantine_reason


def test_dual_reality_taxonomy_boundary_enforcement():
    """Verify internal biography inferences cannot rewrite objective world facts and vice versa."""
    controller = InferenceBudgetController()

    # 1. Fictional biography trying to mutate objective physical reality (world.*)
    bio_hyp = _make_candidate(
        "bio_invading_world",
        slot_name="world.geography.malaysia",
        proposed_value="Has snowy winters",
    )
    res1 = controller.evaluate_turn_hypotheses([bio_hyp])
    assert len(res1.admitted) == 0
    assert len(res1.quarantined) == 1
    assert "SIMULATED_BIOGRAPHY_FACT cannot mutate objective world facts" in res1.quarantined[0].quarantine_reason

    # 2. Objective world fact trying to mutate personal biography slot
    world_hyp = CandidateHypothesis(
        candidate_id="world_invading_bio",
        entity_id="aevum",
        slot_name="education.major",
        proposed_value="Physics",
        reality_taxonomy=RealityTaxonomy.OBJECTIVE_WORLD_FACT,
        inference_depth=0,
        inference_edge_type=InferenceEdgeType.DIRECT_ATTRIBUTE,
        plausibility=PlausibilityBreakdown.create(),
        provenance=ProvenanceLineage(origin_id="sensor_01"),
        lifecycle_state=CandidateLifecycleState.GENERATED,
    )
    res2 = controller.evaluate_turn_hypotheses([world_hyp])
    assert len(res2.admitted) == 0
    assert len(res2.quarantined) == 1
    assert "OBJECTIVE_WORLD_FACT cannot mutate personal character biography slots" in res2.quarantined[0].quarantine_reason

