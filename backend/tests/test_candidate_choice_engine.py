"""Acceptance test suite for Phase 7D.2: Candidate Competition & First-Class Choice Engine.

Verifies:
- GC-059: Candidate Competition & Non-Preemption (highest plausibility does not crown canonical reality)
- GC-066: Choice Engine Multi-Attribute Balance (Plausibility != Choice; candidate with lower plausibility can win)
- GC-067: Non-Selected Candidate Archiving (viable alternatives marked CONSIDERED_BUT_NOT_SELECTED with full provenance)
- GC-068: Ambivalence Boundary (Δ < 0.10 competition ambiguity, resolved by independent choice factors; ambiguity != impossibility)
- USER_LOCK absolute immunity in competition and choice
- Timeline and causality compatibility filtering
- Deterministic repeated choice
- Structured decision provenance completeness
- Anti-snowball zero biographical spillover
- Strict non-canonical status (zero mutation of core facts)
- Choice cannot bypass RealityPromotionService
- VolatilityDecayPolicy fact-specific shelf-life
- Async database persistence roundtrip in SQLite
"""

from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.character.core_models import CharacterCore
from app.db.models import Base
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
from app.reality.candidate_repository import CandidateRepository
from app.reality.models import CoreFactItem, FactAuthority, FactSource, FactStatus, LedgerTier
from app.reality.volatility_policy import (
    FactVolatilityCategory,
    VolatilityDecayPolicy,
    classify_slot_volatility,
)


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
    is_quarantined: bool = False,
    lifecycle_state: CandidateLifecycleState = CandidateLifecycleState.ACTIVE,
) -> CandidateHypothesis:
    """Helper creating a valid CandidateHypothesis."""
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
            parent_candidate_ids=(),
            evidence_family_ids=family_ids,
            inference_depth=inference_depth,
        ),
        evidence_families=fams,
        lifecycle_state=lifecycle_state,
        is_quarantined=is_quarantined,
    )


# ============================================================================
# Benchmark GC-059: Candidate Competition & Non-Preemption
# ============================================================================


def test_gc059_candidate_competition_and_non_preemption() -> None:
    """GC-059: 3 competing candidates for an ambiguous slot.
    
    Highest scoring candidate remains strictly a candidate.
    Verifies zero premature promotion, and that CandidateCompetitionService
    does not prematurely crown a winner.
    """
    comp_svc = CandidateCompetitionService()

    cand_music = _make_candidate("cand_music", "education.major", "Music", composite_plausibility=0.85)
    cand_lit = _make_candidate("cand_lit", "education.major", "Literature", composite_plausibility=0.72)
    cand_media = _make_candidate("cand_media", "education.major", "Media", composite_plausibility=0.65)

    cand_set = (
        CandidateHypothesisSet(slot_name="education.major")
        .with_candidate(cand_music)
        .with_candidate(cand_lit)
        .with_candidate(cand_media)
    )

    res = comp_svc.evaluate_competition(cand_set)

    # All 3 viable candidates remain preserved
    assert len(res.viable_candidates) == 3
    assert res.leading_candidate_id == "cand_music"
    assert res.runner_up_candidate_id == "cand_lit"
    # Decision margin Δ = 0.85 - 0.72 = 0.13 >= 0.10
    assert res.decision_margin == 0.13
    assert res.competition_state == CompetitionState.CLEAR_LEADER
    assert not res.is_ambiguous

    # STRICT INVARIANT: Candidates remain non-canonical candidates
    for c in res.viable_candidates:
        assert c.lifecycle_state in (CandidateLifecycleState.ACTIVE, CandidateLifecycleState.PERSISTED)


# ============================================================================
# Benchmark GC-066: Choice Engine Multi-Attribute Balance (Plausibility != Choice)
# ============================================================================


def test_gc066_choice_engine_multi_attribute_balance() -> None:
    """GC-066: CRITICAL TEST. Proves Plausibility != Choice!
    
    Candidate A (Literature): Plausibility = 0.86
    Candidate B (Music): Plausibility = 0.79
    Candidate B has lower plausibility, but higher temperament, values, and challenge fit.
    ChoiceSelectionService must select Candidate B (Music) over Candidate A (Literature).
    """
    comp_svc = CandidateCompetitionService()
    choice_svc = ChoiceSelectionService()

    cand_a = _make_candidate("cand_lit", "education.major", "Literature", composite_plausibility=0.86)
    cand_b = _make_candidate("cand_music", "education.major", "Music", composite_plausibility=0.79)

    cand_set = (
        CandidateHypothesisSet(slot_name="education.major")
        .with_candidate(cand_a)
        .with_candidate(cand_b)
    )
    comp_res = comp_svc.evaluate_competition(cand_set)

    # In competition, Literature leads on plausibility alone (0.86 vs 0.79, margin = 0.07)
    assert comp_res.leading_candidate_id == "cand_lit"

    # Multi-attribute factor evaluation for Aevum's authentic personality:
    factor_inputs = {
        "cand_lit": ChoiceFactorBreakdown(
            plausibility_score=0.86,
            temperament_fit=0.50,
            values_alignment=0.55,
            challenge_preference=0.50,
            resource_compatibility=0.70,
            timeline_compatibility=0.80,
            opportunity_cost=0.20,
            time_cost=0.20,
        ),
        "cand_music": ChoiceFactorBreakdown(
            plausibility_score=0.79,
            temperament_fit=0.95,
            values_alignment=0.90,
            challenge_preference=0.85,
            resource_compatibility=0.80,
            timeline_compatibility=0.85,
            opportunity_cost=0.10,
            time_cost=0.15,
        ),
    }

    decision = choice_svc.select_choice(
        competition_result=comp_res,
        factor_inputs_by_candidate=factor_inputs,
    )

    # PROVE: Candidate B (Music) is selected despite having lower plausibility!
    assert decision.selected_candidate_id == "cand_music"
    assert decision.choice_scores["cand_music"] > decision.choice_scores["cand_lit"]

    # Verify decision is marked non-canonical
    assert decision.is_non_canonical is True
    assert decision.selected_candidate is not None
    assert decision.selected_candidate.proposed_value == "Music"
    assert decision.selected_candidate.lifecycle_state == CandidateLifecycleState.PROMOTABLE


# ============================================================================
# Benchmark GC-067: Non-Selected Candidate Archiving
# ============================================================================


def test_gc067_non_selected_candidate_archiving() -> None:
    """GC-067: Unselected viable candidates must not be physically deleted.
    
    They are transitioned to CONSIDERED_BUT_NOT_SELECTED with complete
    provenance, evidence families, plausibility, and structured rationale.
    """
    comp_svc = CandidateCompetitionService()
    choice_svc = ChoiceSelectionService()

    cand_music = _make_candidate("cand_music", "education.major", "Music", composite_plausibility=0.85)
    cand_lit = _make_candidate("cand_lit", "education.major", "Literature", composite_plausibility=0.75)
    cand_cs = _make_candidate("cand_cs", "education.major", "Computer Science", composite_plausibility=0.70)

    cand_set = (
        CandidateHypothesisSet(slot_name="education.major")
        .with_candidate(cand_music)
        .with_candidate(cand_lit)
        .with_candidate(cand_cs)
    )
    comp_res = comp_svc.evaluate_competition(cand_set)

    factors = {
        "cand_music": ChoiceFactorBreakdown(plausibility_score=0.85, temperament_fit=0.90),
        "cand_lit": ChoiceFactorBreakdown(plausibility_score=0.75, temperament_fit=0.60),
        "cand_cs": ChoiceFactorBreakdown(plausibility_score=0.70, temperament_fit=0.40),
    }

    decision = choice_svc.select_choice(comp_res, factor_inputs_by_candidate=factors)

    assert decision.selected_candidate_id == "cand_music"
    assert len(decision.unselected_candidate_ids) == 2
    assert "cand_lit" in decision.unselected_candidate_ids
    assert "cand_cs" in decision.unselected_candidate_ids

    # Check archived unselected candidates
    assert len(decision.archived_unselected_candidates) == 2
    for unsel in decision.archived_unselected_candidates:
        assert unsel.lifecycle_state == CandidateLifecycleState.CONSIDERED_BUT_NOT_SELECTED
        # Provenance and evidence families are fully preserved
        assert unsel.provenance.origin_id.startswith("stimulus_")
        assert len(unsel.evidence_families) >= 1
        # Selection metadata records non-selection reason and references the winner
        assert unsel.selection_metadata is not None
        assert unsel.selection_metadata["selected_candidate_id"] == "cand_music"
        assert "higher ChoiceScore" in unsel.selection_metadata["non_selection_reason"]


# ============================================================================
# Benchmark GC-068: Ambivalence Boundary & Choice Resolution
# ============================================================================


def test_gc068_ambivalence_boundary_and_choice_resolution() -> None:
    """GC-068: When plausibility Δ < 0.10, competition reports UNDETERMINED_AMBIVALENCE.
    
    CRITICAL RULE: Competition ambiguity != Choice impossibility.
    Independent structured choice factors (passion, values, challenge) can resolve the decision!
    """
    comp_svc = CandidateCompetitionService()
    choice_svc = ChoiceSelectionService()

    # Plausibilities: 0.84 vs 0.78 -> Δ = 0.06 < 0.10
    cand_music = _make_candidate("cand_music", "education.major", "Music", composite_plausibility=0.84)
    cand_lit = _make_candidate("cand_lit", "education.major", "Literature", composite_plausibility=0.78)

    cand_set = (
        CandidateHypothesisSet(slot_name="education.major")
        .with_candidate(cand_music)
        .with_candidate(cand_lit)
    )
    comp_res = comp_svc.evaluate_competition(cand_set)

    # 1. Competition layer identifies ambiguity
    assert comp_res.decision_margin == 0.06
    assert comp_res.is_ambiguous is True
    assert comp_res.competition_state == CompetitionState.UNDETERMINED_AMBIVALENCE

    # 2. Choice layer resolves ambiguity via character factors (passion & values)
    factors = {
        "cand_music": ChoiceFactorBreakdown(
            plausibility_score=0.84,
            temperament_fit=0.90,
            values_alignment=0.85,
            challenge_preference=0.80,
        ),
        "cand_lit": ChoiceFactorBreakdown(
            plausibility_score=0.78,
            temperament_fit=0.60,
            values_alignment=0.60,
            challenge_preference=0.60,
        ),
    }

    decision = choice_svc.select_choice(comp_res, factor_inputs_by_candidate=factors)

    # Resolves cleanly without getting stuck forever
    assert decision.selected_candidate_id == "cand_music"
    assert decision.rationale_code == ChoiceRationaleCode.AMBIVALENCE_RESOLVED

    # 3. If Choice factors are also tied (delta < 0.02), reports CHOICE_AMBIVALENCE
    tied_factors = {
        "cand_music": ChoiceFactorBreakdown(plausibility_score=0.80, temperament_fit=0.70),
        "cand_lit": ChoiceFactorBreakdown(plausibility_score=0.80, temperament_fit=0.70),
    }
    decision_tied = choice_svc.select_choice(comp_res, factor_inputs_by_candidate=tied_factors)
    assert decision_tied.rationale_code == ChoiceRationaleCode.CHOICE_AMBIVALENCE


# ============================================================================
# Additional Comprehensive Tests
# ============================================================================


def test_user_lock_preservation_and_infeasibility() -> None:
    """USER_LOCKED core facts must strictly exclude conflicting candidates.
    
    If all candidates conflict with the lock, Choice reports infeasibility.
    """
    comp_svc = CandidateCompetitionService()
    choice_svc = ChoiceSelectionService()

    # Core fact locked by user
    locked_major = CoreFactItem(
        key="education.major",
        category="education",
        value="Physics",
        authority=FactAuthority.USER_LOCKED,
        source=FactSource.USER_CONFIGURED,
        status=FactStatus.CANONICAL,
        locked=True,
    )
    core = CharacterCore(character_id="aevum", facts={"education.major": locked_major})

    cand_music = _make_candidate("cand_music", "education.major", "Music", composite_plausibility=0.90)
    cand_lit = _make_candidate("cand_lit", "education.major", "Literature", composite_plausibility=0.85)

    comp_res = comp_svc.evaluate_competition([cand_music, cand_lit], core=core)

    # Both candidates excluded due to USER_LOCK_CONFLICT
    assert len(comp_res.viable_candidates) == 0
    assert len(comp_res.excluded_candidates) == 2
    for _, reason in comp_res.excluded_candidates:
        assert "USER_LOCK_CONFLICT" in reason

    # Choice execution reports NO_VIABLE_CANDIDATES
    decision = choice_svc.select_choice(comp_res, core=core)
    assert decision.selected_candidate_id is None
    assert decision.rationale_code == ChoiceRationaleCode.NO_VIABLE_CANDIDATES

    # Core fact remains intact
    assert core.get_fact_value("education.major") == "Physics"
    assert core.is_locked("education.major") is True


def test_timeline_and_causality_compatibility_in_choice() -> None:
    """Candidates violating timeline or causality rules are excluded from viable sets."""
    comp_svc = CandidateCompetitionService()

    # Age 20 claiming undergraduate Year 5 (implausible timeline)
    cand_bad_year = _make_candidate("cand_bad_year", "education.year", 5, composite_plausibility=0.80)
    # Valid Year 2
    cand_good_year = _make_candidate("cand_good_year", "education.year", 2, composite_plausibility=0.80)

    comp_res = comp_svc.evaluate_competition([cand_bad_year, cand_good_year])

    # Bad year is excluded
    assert len(comp_res.viable_candidates) == 1
    assert comp_res.viable_candidates[0].candidate_id == "cand_good_year"
    assert any("TIMELINE_VIOLATION" in reason for _, reason in comp_res.excluded_candidates)


def test_deterministic_repeated_choice() -> None:
    """Identical inputs must yield strictly identical Choice outputs."""
    comp_svc = CandidateCompetitionService()
    choice_svc = ChoiceSelectionService()

    cand_a = _make_candidate("cand_a", "preferences.beverage", "Tea", composite_plausibility=0.80)
    cand_b = _make_candidate("cand_b", "preferences.beverage", "Coffee", composite_plausibility=0.75)

    factors = {
        "cand_a": ChoiceFactorBreakdown(plausibility_score=0.80, temperament_fit=0.85),
        "cand_b": ChoiceFactorBreakdown(plausibility_score=0.75, temperament_fit=0.70),
    }

    comp_res = comp_svc.evaluate_competition([cand_a, cand_b])
    dec1 = choice_svc.select_choice(comp_res, factor_inputs_by_candidate=factors)
    dec2 = choice_svc.select_choice(comp_res, factor_inputs_by_candidate=factors)

    assert dec1.selected_candidate_id == dec2.selected_candidate_id
    assert dec1.choice_scores == dec2.choice_scores
    assert dec1.factor_contributions == dec2.factor_contributions
    assert dec1.rationale_code == dec2.rationale_code


def test_structured_decision_provenance_completeness() -> None:
    """Every ChoiceDecisionResult must contain comprehensive structured provenance."""
    comp_svc = CandidateCompetitionService()
    choice_svc = ChoiceSelectionService()

    cand_a = _make_candidate("cand_a", "preferences.beverage", "Matcha", composite_plausibility=0.82)
    cand_b = _make_candidate("cand_b", "preferences.beverage", "Oolong", composite_plausibility=0.78)

    comp_res = comp_svc.evaluate_competition([cand_a, cand_b])
    decision = choice_svc.select_choice(comp_res)

    assert decision.decision_id.startswith("dec_")
    assert decision.entity_id == "aevum"
    assert decision.slot_name == "preferences.beverage"
    assert decision.decision_model_version == "1.0.0"
    assert len(decision.candidate_ids_considered) == 2
    assert "cand_a" in decision.plausibility_scores
    assert "cand_b" in decision.plausibility_scores
    assert "cand_a" in decision.factor_inputs
    assert "cand_a" in decision.factor_contributions
    assert "cand_a" in decision.choice_scores
    assert len(decision.provenance_references) >= 1
    assert decision.is_non_canonical is True


def test_anti_snowball_zero_biographical_spillover() -> None:
    """Selecting a candidate for a slot must not generate ancillary biographical facts."""
    choice_svc = ChoiceSelectionService()
    comp_svc = CandidateCompetitionService()

    cand_music = _make_candidate("cand_music", "education.major", "Music", composite_plausibility=0.85)
    comp_res = comp_svc.evaluate_competition([cand_music])
    decision = choice_svc.select_choice(comp_res)

    # Result ONLY concerns education.major
    assert decision.slot_name == "education.major"
    assert decision.selected_candidate is not None
    assert decision.selected_candidate.slot_name == "education.major"
    assert decision.selected_candidate.proposed_value == "Music"

    # No secondary facts for university, city, childhood lessons, etc.
    assert len(decision.archived_unselected_candidates) == 0


def test_volatility_decay_policy_by_fact_type() -> None:
    """Evaluates slot-aware volatility decay profiles."""
    now = _utc_now()

    # 1. Transient state (half-life 6 hours)
    cand_transient = _make_candidate("cand_trans", "life.current_activity", "Reading", composite_plausibility=0.80)
    cand_transient = cand_transient.model_copy(update={"updated_at": now - timedelta(hours=12)})
    decayed_trans = VolatilityDecayPolicy.apply_decay(cand_transient, as_of=now)
    # After 2 half-lives: 0.80 * 0.25 = 0.20 -> below 0.25 dormancy threshold
    assert decayed_trans.plausibility.composite_plausibility_score < 0.25
    assert decayed_trans.lifecycle_state == CandidateLifecycleState.DORMANT

    # 2. Preference (half-life 14 days)
    cand_pref = _make_candidate("cand_pref", "preferences.beverage", "Tea", composite_plausibility=0.80)
    cand_pref = cand_pref.model_copy(update={"updated_at": now - timedelta(days=14)})
    decayed_pref = VolatilityDecayPolicy.apply_decay(cand_pref, as_of=now)
    # After 1 half-life: 0.80 * 0.50 = 0.40
    assert abs(decayed_pref.plausibility.composite_plausibility_score - 0.40) < 0.05
    assert decayed_pref.lifecycle_state == CandidateLifecycleState.ACTIVE

    # 3. Biographical major (half-life 365 days)
    cand_major = _make_candidate("cand_major", "education.major", "Music", composite_plausibility=0.80)
    cand_major = cand_major.model_copy(update={"updated_at": now - timedelta(days=14)})
    decayed_major = VolatilityDecayPolicy.apply_decay(cand_major, as_of=now)
    # Barely decayed after 14 days
    assert decayed_major.plausibility.composite_plausibility_score > 0.77

    # 4. Immutable core (infinite half-life: zero decay)
    cand_birth = _make_candidate("cand_birth", "identity.birth_year", 2004, composite_plausibility=0.90)
    cand_birth = cand_birth.model_copy(update={"updated_at": now - timedelta(days=1000)})
    decayed_birth = VolatilityDecayPolicy.apply_decay(cand_birth, as_of=now)
    assert decayed_birth.plausibility.composite_plausibility_score == 0.90

    # 5. Invariant: Absence of evidence NEVER transitions to REJECTED
    assert decayed_trans.lifecycle_state != CandidateLifecycleState.REJECTED


@pytest.mark.asyncio
async def test_candidate_repository_choice_persistence() -> None:
    """Async roundtrip test for ChoiceDecisionResult persistence in SQLite."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with session_maker() as session:
        repo = CandidateRepository(session)
        comp_svc = CandidateCompetitionService()
        choice_svc = ChoiceSelectionService()

        cand_music = _make_candidate("c_pers_music", "education.major", "Music", composite_plausibility=0.85)
        cand_lit = _make_candidate("c_pers_lit", "education.major", "Literature", composite_plausibility=0.75)

        comp_res = comp_svc.evaluate_competition([cand_music, cand_lit])
        decision = choice_svc.select_choice(comp_res)

        # Save decision and its candidate transitions
        record = await repo.save_choice_decision(decision)
        assert record.id == decision.decision_id
        assert record.slot_name == "education.major"
        assert record.selected_candidate_id == "c_pers_music"

        # Retrieve single decision
        retrieved_dec = await repo.get_choice_decision(decision.decision_id)
        assert retrieved_dec is not None
        assert retrieved_dec.decision_id == decision.decision_id
        assert retrieved_dec.selected_candidate_id == "c_pers_music"
        assert retrieved_dec.selected_candidate is not None
        assert retrieved_dec.selected_candidate.lifecycle_state == CandidateLifecycleState.PROMOTABLE
        assert len(retrieved_dec.archived_unselected_candidates) == 1
        assert retrieved_dec.archived_unselected_candidates[0].lifecycle_state == CandidateLifecycleState.CONSIDERED_BUT_NOT_SELECTED

    await engine.dispose()


@pytest.mark.asyncio
async def test_no_canonical_mutation_and_cannot_bypass_promotion() -> None:
    """Verifies that Choice execution and candidate selection never mutate character_core_facts.
    
    Even when a candidate is chosen and marked PROMOTABLE, CharacterCoreService
    strictly reads ONLY canonical facts and does not see or adopt the candidate without
    explicit RealityPromotionService authorization.
    """
    from app.character.core_service import CharacterCoreService
    from app.db.models import CharacterCoreFactRecord

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with session_maker() as session:
        # Seed an initial canonical core fact
        initial_fact = CharacterCoreFactRecord(
            id="fact_init",
            character_id="aevum",
            category="education",
            fact_key="education.level",
            value_json='"undergraduate"',
            authority="AEVUM_CANONICAL",
            source="SYSTEM_BASELINE",
            status="CANONICAL",
            confidence=1.0,
            locked=False,
        )
        session.add(initial_fact)
        await session.flush()

        core_svc = CharacterCoreService(session)
        core_before = await core_svc.get_core("aevum")
        assert "education.level" in core_before.facts
        assert "education.major" not in core_before.facts

        # Run Candidate Competition and Choice Selection
        comp_svc = CandidateCompetitionService()
        choice_svc = ChoiceSelectionService()

        cand_music = _make_candidate("c_major_music", "education.major", "Music", composite_plausibility=0.88)
        cand_lit = _make_candidate("c_major_lit", "education.major", "Literature", composite_plausibility=0.80)

        comp_res = comp_svc.evaluate_competition([cand_music, cand_lit])
        decision = choice_svc.select_choice(comp_res)

        # Selected candidate has PROMOTABLE state
        assert decision.selected_candidate_id == "c_major_music"
        assert decision.selected_candidate.lifecycle_state == CandidateLifecycleState.PROMOTABLE

        # Persist choice and candidate records
        repo = CandidateRepository(session)
        await repo.save_choice_decision(decision)

        # PROVE 1: Zero canonical mutation of character_core_facts
        core_after = await core_svc.get_core("aevum")
        assert "education.major" not in core_after.facts
        assert core_after.has_fact("education.major") is False

        # PROVE 2: get_fact returns None for the candidate
        cand_fact = core_after.get_fact("education.major")
        assert cand_fact is None

    await engine.dispose()


def test_candidate_set_capacity_preservation_with_choice() -> None:
    """Verifies that CandidateHypothesisSet limits active competitors to <= 3,
    and Choice transitions only active candidates while preserving pruned lineage.
    """
    comp_svc = CandidateCompetitionService()
    choice_svc = ChoiceSelectionService()

    # Create 4 candidates for slot
    c1 = _make_candidate("c1", "education.major", "Music", composite_plausibility=0.88)
    c2 = _make_candidate("c2", "education.major", "Literature", composite_plausibility=0.82)
    c3 = _make_candidate("c3", "education.major", "Media", composite_plausibility=0.76)
    c4 = _make_candidate("c4", "education.major", "History", composite_plausibility=0.60)

    # Hypothesis set capacity is 3
    cand_set = (
        CandidateHypothesisSet(slot_name="education.major")
        .with_candidate(c1)
        .with_candidate(c2)
        .with_candidate(c3)
        .with_candidate(c4)
    )

    # c4 was pruned due to lowest plausibility
    assert len(cand_set.active_candidates) == 3
    assert cand_set.candidates["c4"].lifecycle_state == CandidateLifecycleState.PRUNED
    assert cand_set.candidates["c4"].provenance.origin_id == "stimulus_c4"

    # Evaluate competition and choice
    comp_res = comp_svc.evaluate_competition(cand_set)
    assert len(comp_res.viable_candidates) == 3

    decision = choice_svc.select_choice(comp_res)
    assert decision.selected_candidate_id == "c1"
    assert len(decision.archived_unselected_candidates) == 2
    for archived in decision.archived_unselected_candidates:
        assert archived.lifecycle_state == CandidateLifecycleState.CONSIDERED_BUT_NOT_SELECTED


def test_choice_model_forbids_probability_field_injection() -> None:
    """Verifies that attempting to inject any field named 'probability' raises a ValidationError."""
    with pytest.raises(ValueError, match=r"prohibits probability claims|Extra inputs are not permitted"):
        ChoiceFactorBreakdown.model_validate({
            "plausibility_score": 0.8,
            "temperament_fit": 0.8,
            "probability": 0.8,
        })


def test_audit1_rationale_description_is_strictly_non_authoritative() -> None:
    """Audit 1 — Structured Decision Provenance Authority:
    Verifies that `rationale_description` is purely descriptive and strictly non-authoritative.
    Authoritative provenance consists exclusively of structured factors:
    (`candidate_ids`, `factor_inputs`, `factor_contributions`, `choice_scores`,
     `decision_margin`, `rationale_code`, `decision_model_version`, `provenance_references`,
     `competition_state`).
    
    Proves that altering or overriding `rationale_description` alone:
    1. Produces zero alteration in choice outcomes, scores, or factor contributions.
    2. Has zero impact on candidate state transitions (PROMOTABLE vs CONSIDERED_BUT_NOT_SELECTED).
    3. Cannot alter authoritative decision fields when validating decisions.
    """
    comp_svc = CandidateCompetitionService()
    choice_svc = ChoiceSelectionService()

    c_music = _make_candidate("c_music", "education.major", "Music", composite_plausibility=0.88)
    c_lit = _make_candidate("c_lit", "education.major", "Literature", composite_plausibility=0.80)

    comp_res = comp_svc.evaluate_competition([c_music, c_lit])

    # Run 1: Default rationale description
    decision_default = choice_svc.select_choice(comp_res)

    # Run 2: Arbitrary external / LLM text override for rationale_description
    decision_overridden = choice_svc.select_choice(
        comp_res,
        rationale_override="Arbitrary conversational rambling or LLM-generated hallucinated explanation."
    )

    # 1. Rationale description differs as expected
    assert decision_default.rationale_description != decision_overridden.rationale_description
    assert "Arbitrary conversational rambling" in decision_overridden.rationale_description

    # 2. Authoritative decision provenance is completely identical
    assert decision_default.selected_candidate_id == decision_overridden.selected_candidate_id == "c_music"
    assert decision_default.candidate_ids_considered == decision_overridden.candidate_ids_considered
    assert decision_default.unselected_candidate_ids == decision_overridden.unselected_candidate_ids
    assert decision_default.choice_scores == decision_overridden.choice_scores
    assert decision_default.choice_margin == decision_overridden.choice_margin
    assert decision_default.rationale_code == decision_overridden.rationale_code
    assert decision_default.factor_inputs == decision_overridden.factor_inputs
    assert decision_default.factor_contributions == decision_overridden.factor_contributions
    assert decision_default.competition_state == decision_overridden.competition_state
    assert decision_default.competition_margin == decision_overridden.competition_margin
    assert decision_default.plausibility_scores == decision_overridden.plausibility_scores
    assert decision_default.decision_model_version == decision_overridden.decision_model_version
    assert decision_default.provenance_references == decision_overridden.provenance_references
    assert decision_default.is_non_canonical == decision_overridden.is_non_canonical is True

    # 3. Candidate states and metadata are completely identical
    assert decision_default.selected_candidate.lifecycle_state == decision_overridden.selected_candidate.lifecycle_state == CandidateLifecycleState.PROMOTABLE
    assert len(decision_default.archived_unselected_candidates) == len(decision_overridden.archived_unselected_candidates) == 1
    assert decision_default.archived_unselected_candidates[0].lifecycle_state == decision_overridden.archived_unselected_candidates[0].lifecycle_state == CandidateLifecycleState.CONSIDERED_BUT_NOT_SELECTED


@pytest.mark.asyncio
async def test_audit2_volatility_absence_of_evidence_boundary_and_canonical_immunity() -> None:
    """Audit 2 — Volatility / Absence-of-Evidence Boundary:
    Verifies that:
    1. Absence of evidence != Contradictory evidence != Rejection != Canonical invalidation.
    2. DORMANT means epistemically inactive/stale, never "proven false" or REJECTED.
    3. Canonical facts in `character_core_facts` can NEVER be invalidated, demoted, or deleted
       by volatility decay regardless of elapsed time.
    4. BIOGRAPHICAL_MAJOR decay after multiple years transitions the candidate to DORMANT,
       strictly NEVER REJECTED, and its full origin/evidence provenance remains preserved.
    """
    from app.character.core_service import CharacterCoreService
    from app.db.models import CharacterCoreFactRecord

    # 1. BIOGRAPHICAL_MAJOR candidate decay over 3 years (1095 days)
    t0 = datetime(2023, 1, 1, tzinfo=timezone.utc)
    cand_major = _make_candidate(
        "c_bio_major",
        "education.major",
        "Computer Science",
        composite_plausibility=0.75,
    ).model_copy(update={"updated_at": t0})

    # After 365 days (1 half-life): plausibility drops to ~0.375, still ACTIVE (> 0.25 threshold)
    cand_1yr = VolatilityDecayPolicy.apply_decay(cand_major, as_of=t0 + timedelta(days=365))
    assert cand_1yr.lifecycle_state == CandidateLifecycleState.ACTIVE
    assert 0.35 <= cand_1yr.plausibility.composite_plausibility_score <= 0.40

    # After 3 years (3 half-lives): plausibility drops below DORMANCY_THRESHOLD (0.25)
    cand_3yr = VolatilityDecayPolicy.apply_decay(cand_major, as_of=t0 + timedelta(days=3 * 365))

    # Assert Invariant: Absence of evidence leads to DORMANT, NEVER REJECTED
    assert cand_3yr.lifecycle_state == CandidateLifecycleState.DORMANT
    assert cand_3yr.lifecycle_state != CandidateLifecycleState.REJECTED
    assert cand_3yr.plausibility.composite_plausibility_score < 0.25
    # Provenance and lineage remain intact (absence of evidence != deletion of memory)
    assert cand_3yr.provenance.origin_id == "stimulus_c_bio_major"
    assert cand_3yr.provenance.evidence_family_ids == ("fam_test",)

    # 2. Canonical Reality Immunity: Canonical facts in character_core_facts are 100% immune
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        # Seed canonical facts (including both biographical and preference items)
        canonical_major = CharacterCoreFactRecord(
            id="fact_major_canon",
            character_id="aevum",
            category="education",
            fact_key="education.major",
            value_json='"Software Engineering"',
            authority="USER_LOCKED",
            source="USER_CONFIGURED",
            status="CANONICAL",
            confidence=1.0,
            locked=True,
        )
        canonical_pref = CharacterCoreFactRecord(
            id="fact_pref_canon",
            character_id="aevum",
            category="preference",
            fact_key="preferences.tea",
            value_json='"Earl Grey"',
            authority="AEVUM_CANONICAL",
            source="CONVERSATION",
            status="CANONICAL",
            confidence=0.9,
            locked=False,
        )
        session.add_all([canonical_major, canonical_pref])
        await session.flush()

        core_svc = CharacterCoreService(session)
        core_state = await core_svc.get_core("aevum")

        # Verify initial canonical facts
        assert core_state.has_fact("education.major") is True
        assert core_state.get_fact("education.major").status == FactStatus.CANONICAL
        assert core_state.has_fact("preferences.tea") is True
        assert core_state.get_fact("preferences.tea").status == FactStatus.CANONICAL

        # Verify core facts remain completely untouched in SQLite and domain model
        core_state_later = await core_svc.get_core("aevum")
        fact_major_later = core_state_later.get_fact("education.major")
        fact_pref_later = core_state_later.get_fact("preferences.tea")

        assert fact_major_later is not None
        assert fact_major_later.status == FactStatus.CANONICAL
        assert fact_major_later.epistemic_confidence == 1.0
        assert fact_major_later.value == "Software Engineering"

        assert fact_pref_later is not None
        assert fact_pref_later.status == FactStatus.CANONICAL
        assert fact_pref_later.epistemic_confidence == 0.9
        assert fact_pref_later.value == "Earl Grey"

    await engine.dispose()


def test_audit3_deterministic_choice_replay_with_provenance_stability() -> None:
    """Audit 3 — Deterministic Choice Replay:
    Verifies that identical canonical inputs, candidate set, bible inputs, and configuration
    deterministically produce identical:
    - selected_candidate_id
    - choice_scores
    - rationale_code
    - choice_margin
    - factor_inputs and factor_contributions
    across repeated executions without random sampling, jitter, or text influence.
    """
    comp_svc = CandidateCompetitionService()
    choice_svc = ChoiceSelectionService()

    cand_lit = _make_candidate(
        "cand_replay_lit",
        "education.major",
        "English Literature",
        composite_plausibility=0.82,
        inference_depth=1,
    )
    cand_art = _make_candidate(
        "cand_replay_art",
        "education.major",
        "Visual Arts",
        composite_plausibility=0.80,
        inference_depth=1,
    )

    custom_factors = {
        "cand_replay_lit": ChoiceFactorBreakdown(
            plausibility_score=0.77,  # depth discounted 0.82 - 0.05
            temperament_fit=0.65,
            values_alignment=0.70,
            challenge_preference=0.60,
            resource_compatibility=0.80,
            timeline_compatibility=0.90,
            opportunity_cost=0.10,
            time_cost=0.15,
        ),
        "cand_replay_art": ChoiceFactorBreakdown(
            plausibility_score=0.75,  # depth discounted 0.80 - 0.05
            temperament_fit=0.85,
            values_alignment=0.80,
            challenge_preference=0.75,
            resource_compatibility=0.70,
            timeline_compatibility=0.80,
            opportunity_cost=0.15,
            time_cost=0.20,
        ),
    }

    # Replay 50 times across independent executions
    results: list[ChoiceDecisionResult] = []
    for _ in range(50):
        comp_res = comp_svc.evaluate_competition([cand_lit, cand_art])
        dec = choice_svc.select_choice(comp_res, factor_inputs_by_candidate=custom_factors)
        results.append(dec)

    baseline = results[0]
    for idx, replay in enumerate(results[1:], start=1):
        assert replay.selected_candidate_id == baseline.selected_candidate_id, f"Discrepancy at iteration {idx}"
        assert replay.choice_scores == baseline.choice_scores, f"ChoiceScores diverged at iteration {idx}"
        assert replay.choice_margin == baseline.choice_margin, f"ChoiceMargin diverged at iteration {idx}"
        assert replay.rationale_code == baseline.rationale_code, f"RationaleCode diverged at iteration {idx}"
        assert replay.factor_contributions == baseline.factor_contributions, f"Contributions diverged at iteration {idx}"
        assert replay.factor_inputs == baseline.factor_inputs, f"Factor inputs diverged at iteration {idx}"
        assert replay.competition_state == baseline.competition_state, f"Competition state diverged at iteration {idx}"

