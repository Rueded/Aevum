"""Test suite for Phase 16.2 — Interest Domain State Machine & Temporal Gating.

Covers:
- All 13 Golden Test Cases (G14 ~ G26)
- Anti-Chat-Turn Invariant (GC-403)
- Session Separation & Longitudinal Progression
- Zero State Masking in Lifecycle Derivation
- Curiosity Provenance Distinction & Temporal Precedence
- Multi-Facet Requirement for Familiarity
- Experience / Familiarity Orthogonality Lock
- Provenance Eligibility & Autobiographical Claim Scope Invariance
- Permanent Note A: Absolute Zero Floats
- Static AST Boundary Audit (Zero set_fact(), zero tokens, zero network, zero LLM)
"""

import ast
import inspect
from pathlib import Path
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.db.session import Base
from app.growth.experiential_models import (
    AutobiographicalClaimScope,
    ExperienceProvenanceKind,
    ExperientialRecord,
    ExposureKind,
    ExposureState,
    FamiliarityLevel,
    InterestDomainRecord,
)
from app.growth.experience_repository import ExperienceRepository
from app.growth.state_machine import (
    ActivityState,
    CuriosityEvidence,
    CuriosityEvidenceKind,
    CuriosityState,
    ExperienceLevel,
    LifecycleStage,
    PersonalGrowthState,
    PreferencePolarity,
    UnanchoredCuriosityEvidenceError,
    derive_curiosity_state,
    derive_lifecycle_stage,
    evaluate_experience_level,
    evaluate_familiarity_level,
    is_eligible_personal_experience,
    project_autobiographical_claim_support,
    validate_curiosity_evidence_anchoring,
)
from app.growth.interest_domain_service import InterestDomainService


@pytest_asyncio.fixture
async def async_test_session():
    """In-memory SQLite async engine & session fixture with full table metadata."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


def make_record(
    experience_id: str,
    domain_key: str = "genshin_impact",
    facet_key: str = "combat",
    provenance_kind: ExperienceProvenanceKind = ExperienceProvenanceKind.DIRECT_INTERACTION,
    exposure_kind: ExposureKind = ExposureKind.DIRECT_TOOL_BACKED_EXPERIENCE,
    calendar_session_id: str = "session_001",
    timeline_tick: int = 100,
    evidence_ref: str = "tool://genshin_runner/combat_01",
    is_fictional_frame: bool = False,
) -> ExperientialRecord:
    """Helper creating a valid immutable ExperientialRecord."""
    return ExperientialRecord(
        experience_id=experience_id,
        character_id="aevum",
        domain_key=domain_key,
        facet_key=facet_key,
        provenance_kind=provenance_kind,
        exposure_kind=exposure_kind,
        calendar_session_id=calendar_session_id,
        timeline_tick=timeline_tick,
        interaction_evidence_ref=evidence_ref,
        is_fictional_frame=is_fictional_frame,
    )


# =============================================================================
# G14 ~ G26 Acceptance Tests
# =============================================================================

@pytest.mark.asyncio
async def test_g14_anti_chat_turn_invariant(async_test_session: AsyncSession):
    """G14 (GC-403): Pure conversational turns do NOT create experiences.

    10 dialogue turns discussing Genshin Impact without any tool-executed
    ExperientialRecord leaves experience_level = UNEXPERIENCED and count = 0.
    """
    repo = ExperienceRepository(async_test_session)
    service = InterestDomainService(repo)

    # Simulate exposure via dialogue mention without creating ExperientialRecord
    await repo.register_domain(
        InterestDomainRecord(
            domain_key="genshin_impact",
            character_id="aevum",
            display_name="Genshin Impact",
            exposure_state=ExposureState.EXPOSED,
            created_at_tick=10,
        )
    )

    state = await service.evaluate_growth_state("aevum", "genshin_impact")
    assert state.experience_level == ExperienceLevel.UNEXPERIENCED
    assert state.total_experience_count == 0
    assert state.distinct_session_count == 0
    assert state.familiarity_level == FamiliarityLevel.SURFACE_AWARE

    stage = derive_lifecycle_stage(state)
    assert stage == LifecycleStage.EXPOSED


@pytest.mark.asyncio
async def test_g15_single_session_burst_gating():
    """G15: 5 experiences recorded within a single session cannot advance beyond NOVICE.

    Single session burst engagement does not satisfy multi-session longitudinal requirement.
    """
    records = [
        make_record(f"exp_{i}", calendar_session_id="session_burst", timeline_tick=100 + i)
        for i in range(5)
    ]

    exp_level = evaluate_experience_level(records)
    assert exp_level == ExperienceLevel.NOVICE

    fam_level = evaluate_familiarity_level(ExposureState.DIRECTLY_ENCOUNTERED, records)
    assert fam_level == FamiliarityLevel.SURFACE_AWARE


@pytest.mark.asyncio
async def test_g16_multi_session_longitudinal_progression():
    """G16: At least 3 eligible personal experiences across at least 2 distinct sessions -> PRACTICED.

    Also verifies 3 distinct sessions with only 2 experiences remains NOVICE.
    """
    # 3 sessions, but only 2 experiences -> NOVICE
    records_under_count = [
        make_record("exp_1", calendar_session_id="session_A", timeline_tick=100),
        make_record("exp_2", calendar_session_id="session_B", timeline_tick=200),
    ]
    assert evaluate_experience_level(records_under_count) == ExperienceLevel.NOVICE

    # 3 experiences across 2 distinct sessions -> PRACTICED
    records_practiced = [
        make_record("exp_1", calendar_session_id="session_A", timeline_tick=100),
        make_record("exp_2", calendar_session_id="session_A", timeline_tick=101),
        make_record("exp_3", calendar_session_id="session_B", timeline_tick=200),
    ]
    assert evaluate_experience_level(records_practiced) == ExperienceLevel.PRACTICED

    # 7 experiences across 4 distinct sessions -> EXPERIENCED
    records_experienced = [
        make_record("exp_1", calendar_session_id="session_1", timeline_tick=100),
        make_record("exp_2", calendar_session_id="session_1", timeline_tick=101),
        make_record("exp_3", calendar_session_id="session_2", timeline_tick=200),
        make_record("exp_4", calendar_session_id="session_2", timeline_tick=201),
        make_record("exp_5", calendar_session_id="session_3", timeline_tick=300),
        make_record("exp_6", calendar_session_id="session_4", timeline_tick=400),
        make_record("exp_7", calendar_session_id="session_4", timeline_tick=401),
    ]
    assert evaluate_experience_level(records_experienced) == ExperienceLevel.EXPERIENCED


def test_g17_zero_state_masking_in_lifecycle_derivation():
    """G17: Truth table test verifying deterministic, unmasked lifecycle stage derivation."""
    # 1. Baseline unexposed
    s_unexposed = PersonalGrowthState(
        character_id="aevum",
        domain_key="unknown_domain",
        exposure_state=ExposureState.UNEXPOSED,
        experience_level=ExperienceLevel.UNEXPERIENCED,
        familiarity_level=FamiliarityLevel.UNAWARE,
    )
    assert derive_lifecycle_stage(s_unexposed) == LifecycleStage.UNEXPOSED

    # 2. Exposed / Invited
    s_exposed = PersonalGrowthState(
        character_id="aevum",
        domain_key="test_domain",
        exposure_state=ExposureState.EXPOSED,
        experience_level=ExperienceLevel.UNEXPERIENCED,
        familiarity_level=FamiliarityLevel.SURFACE_AWARE,
        curiosity_state=CuriosityState.INVITED,
    )
    assert derive_lifecycle_stage(s_exposed) == LifecycleStage.EXPOSED

    # 3. Curious (self-expressed inquiry)
    s_curious = PersonalGrowthState(
        character_id="aevum",
        domain_key="test_domain",
        exposure_state=ExposureState.EXPOSED,
        experience_level=ExperienceLevel.UNEXPERIENCED,
        familiarity_level=FamiliarityLevel.SURFACE_AWARE,
        curiosity_state=CuriosityState.SELF_EXPRESSED,
    )
    assert derive_lifecycle_stage(s_curious) == LifecycleStage.CURIOUS

    # 4. Exploring (has experiences)
    s_exploring = PersonalGrowthState(
        character_id="aevum",
        domain_key="test_domain",
        exposure_state=ExposureState.DIRECTLY_ENCOUNTERED,
        experience_level=ExperienceLevel.NOVICE,
        familiarity_level=FamiliarityLevel.SURFACE_AWARE,
        curiosity_state=CuriosityState.RESOLVED,
        total_experience_count=1,
    )
    assert derive_lifecycle_stage(s_exploring) == LifecycleStage.EXPLORING

    # 5. Familiar (broad multi-facet understanding)
    s_familiar = PersonalGrowthState(
        character_id="aevum",
        domain_key="test_domain",
        exposure_state=ExposureState.DIRECTLY_ENCOUNTERED,
        experience_level=ExperienceLevel.PRACTICED,
        familiarity_level=FamiliarityLevel.CONCEPTUALLY_GROUNDED,
        total_experience_count=4,
    )
    assert derive_lifecycle_stage(s_familiar) == LifecycleStage.FAMILIAR


def test_g18_curiosity_provenance_distinction():
    """G18: Recommendation sets INVITED -> EXPOSED; Aevum inquiry sets SELF_EXPRESSED -> CURIOUS;
    subsequent experience resolves curiosity -> EXPLORING.
    """
    rec_ev = CuriosityEvidence(
        evidence_kind=CuriosityEvidenceKind.USER_RECOMMENDATION,
        domain_key="genshin_impact",
        timeline_tick=100,
        evidence_source_ref="speech_act://gc-384",
    )
    # Recommendation alone
    c_state_1 = derive_curiosity_state([rec_ev], eligible_experience_records=[])
    assert c_state_1 == CuriosityState.INVITED

    s1 = PersonalGrowthState(
        character_id="aevum",
        domain_key="genshin_impact",
        exposure_state=ExposureState.EXPOSED,
        experience_level=ExperienceLevel.UNEXPERIENCED,
        familiarity_level=FamiliarityLevel.SURFACE_AWARE,
        curiosity_state=c_state_1,
    )
    assert derive_lifecycle_stage(s1) == LifecycleStage.EXPOSED

    # Aevum explicit inquiry
    inquiry_ev = CuriosityEvidence(
        evidence_kind=CuriosityEvidenceKind.AEVUM_EXPLICIT_INQUIRY,
        domain_key="genshin_impact",
        timeline_tick=200,
        evidence_source_ref="turn://dialogue/42",
        expression_snippet="How does elemental reaction combat work?",
    )
    c_state_2 = derive_curiosity_state([rec_ev, inquiry_ev], eligible_experience_records=[])
    assert c_state_2 == CuriosityState.SELF_EXPRESSED

    s2 = PersonalGrowthState(
        character_id="aevum",
        domain_key="genshin_impact",
        exposure_state=ExposureState.EXPOSED,
        experience_level=ExperienceLevel.UNEXPERIENCED,
        familiarity_level=FamiliarityLevel.SURFACE_AWARE,
        curiosity_state=c_state_2,
    )
    assert derive_lifecycle_stage(s2) == LifecycleStage.CURIOUS

    # Subsequent eligible experience at tick 300 resolves curiosity
    exp = make_record("exp_1", domain_key="genshin_impact", timeline_tick=300)
    c_state_3 = derive_curiosity_state([rec_ev, inquiry_ev], eligible_experience_records=[exp])
    assert c_state_3 == CuriosityState.RESOLVED

    s3 = PersonalGrowthState(
        character_id="aevum",
        domain_key="genshin_impact",
        exposure_state=ExposureState.DIRECTLY_ENCOUNTERED,
        experience_level=ExperienceLevel.NOVICE,
        familiarity_level=FamiliarityLevel.SURFACE_AWARE,
        curiosity_state=c_state_3,
        total_experience_count=1,
    )
    assert derive_lifecycle_stage(s3) == LifecycleStage.EXPLORING


def test_g19_multi_facet_requirement_for_familiarity():
    """G19: Single facet engagement is capped at SURFACE_AWARE regardless of count;
    adding a second facet across >= 2 sessions unlocks CONCEPTUALLY_GROUNDED;
    further expansion across >= 4 sessions and >= 6 count unlocks PROFICIENT.
    """
    # 1. 10 experiences in solely "combat" across 4 distinct sessions
    single_facet_records = [
        make_record(f"exp_{i}", facet_key="combat", calendar_session_id=f"session_{i % 4}", timeline_tick=100 + i)
        for i in range(10)
    ]
    assert evaluate_experience_level(single_facet_records) == ExperienceLevel.EXPERIENCED
    # Strictly capped at SURFACE_AWARE because distinct_facets = 1 < 2
    assert evaluate_familiarity_level(ExposureState.DIRECTLY_ENCOUNTERED, single_facet_records) == FamiliarityLevel.SURFACE_AWARE

    # 2. 3 experiences across 2 sessions in 2 facets -> CONCEPTUALLY_GROUNDED
    grounded_records = [
        make_record("exp_c1", facet_key="combat", calendar_session_id="session_1", timeline_tick=100),
        make_record("exp_c2", facet_key="combat", calendar_session_id="session_1", timeline_tick=101),
        make_record("exp_m1", facet_key="lore_music", calendar_session_id="session_2", timeline_tick=200),
    ]
    assert evaluate_familiarity_level(ExposureState.DIRECTLY_ENCOUNTERED, grounded_records) == FamiliarityLevel.CONCEPTUALLY_GROUNDED

    # 3. Expanding to 6+ experiences across 4+ sessions in 2+ facets -> PROFICIENT
    proficient_records = list(single_facet_records) + [
        make_record("exp_lore_1", facet_key="lore_music", calendar_session_id="session_lore", timeline_tick=300),
    ]
    assert evaluate_familiarity_level(ExposureState.DIRECTLY_ENCOUNTERED, proficient_records) == FamiliarityLevel.PROFICIENT


def test_g20_permanent_note_a_zero_floats():
    """G20: Permanent Note A - Zero floats across state_machine and interest_domain_service."""
    import app.growth.state_machine as sm_mod
    import app.growth.interest_domain_service as ids_mod

    for mod in (sm_mod, ids_mod):
        source = inspect.getsource(mod)
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "float":
                pytest.fail(f"Found forbidden 'float' annotation in {mod.__name__} at line {node.lineno}")
            if isinstance(node, ast.Constant) and isinstance(node.value, float):
                pytest.fail(f"Found forbidden float literal {node.value} in {mod.__name__} at line {node.lineno}")


def test_g21_static_ast_boundary_audit():
    """G21: Static AST boundary audit verifying zero constitutional violations."""
    root_growth_dir = Path(__file__).parent.parent / "app" / "growth"
    modules_to_audit = [
        root_growth_dir / "state_machine.py",
        root_growth_dir / "interest_domain_service.py",
    ]

    forbidden_identifiers = {
        "set_fact",
        "PromotionAuthorizationToken",
        "requests",
        "httpx",
        "urllib",
        "openai",
        "anthropic",
    }

    for path in modules_to_audit:
        assert path.exists(), f"File {path} must exist"
        tree = ast.parse(path.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in forbidden_identifiers:
                pytest.fail(f"Constitutional Violation: {node.id} found in {path} at line {node.lineno}")
            if isinstance(node, ast.Attribute) and node.attr in forbidden_identifiers:
                pytest.fail(f"Constitutional Violation: {node.attr} found in {path} at line {node.lineno}")


def test_g22_experience_does_not_force_familiarity():
    """G22 (Blocker 1 Resolution): ExperienceLevel does not force FamiliarityLevel.

    3+ distinct sessions in a single facet yields PRACTICED but remains SURFACE_AWARE.
    """
    records = [
        make_record("exp_1", facet_key="combat", calendar_session_id="session_1", timeline_tick=100),
        make_record("exp_2", facet_key="combat", calendar_session_id="session_2", timeline_tick=200),
        make_record("exp_3", facet_key="combat", calendar_session_id="session_3", timeline_tick=300),
    ]

    exp_level = evaluate_experience_level(records)
    fam_level = evaluate_familiarity_level(ExposureState.DIRECTLY_ENCOUNTERED, records)

    assert exp_level == ExperienceLevel.PRACTICED
    assert fam_level == FamiliarityLevel.SURFACE_AWARE


def test_g23_familiarity_does_not_force_experience():
    """G23 (Blocker 1 Resolution): FamiliarityLevel does not force ExperienceLevel.

    2+ facets explored within a single session cannot reach CONCEPTUALLY_GROUNDED
    because longitudinal multi-session dispersion is lacking.
    """
    records = [
        make_record("exp_1", facet_key="combat", calendar_session_id="session_single", timeline_tick=100),
        make_record("exp_2", facet_key="music", calendar_session_id="session_single", timeline_tick=101),
        make_record("exp_3", facet_key="exploration", calendar_session_id="session_single", timeline_tick=102),
    ]

    exp_level = evaluate_experience_level(records)
    fam_level = evaluate_familiarity_level(ExposureState.DIRECTLY_ENCOUNTERED, records)

    assert exp_level == ExperienceLevel.NOVICE
    assert fam_level == FamiliarityLevel.SURFACE_AWARE


def test_g24_phase162_production_operational_path_boundaries():
    """G24 (Precision Fixed): Future lifecycle stages unreachable through Phase 16.2 production construction path.

    Under Phase 16.2 production construction contract, PersonalGrowthState is constructed
    with preference_polarity=UNFORMED and activity_state=ACTIVE.
    """
    # A maximally progressed state in Phase 16.2
    max_162_state = PersonalGrowthState(
        character_id="aevum",
        domain_key="genshin_impact",
        exposure_state=ExposureState.DIRECTLY_ENCOUNTERED,
        experience_level=ExperienceLevel.EXPERIENCED,
        familiarity_level=FamiliarityLevel.PROFICIENT,
        curiosity_state=CuriosityState.RESOLVED,
        preference_polarity=PreferencePolarity.UNFORMED,
        activity_state=ActivityState.ACTIVE,
        total_experience_count=20,
        distinct_session_count=10,
        distinct_facet_count_experienced=4,
    )

    stage = derive_lifecycle_stage(max_162_state)
    assert stage == LifecycleStage.FAMILIAR
    assert stage not in (
        LifecycleStage.ESTABLISHED_TASTE,
        LifecycleStage.PREFERENCE_FORMING,
        LifecycleStage.SATIATED,
        LifecycleStage.DORMANT,
    )


def test_g25_provenance_eligibility_and_scope_projection():
    """G25 (Scope Invariant & Provenance Barrier):
    Non-eligible provenances do NOT contribute to personal experience.
    Both DIRECT and SHARED count toward objective growth state invariantly.
    Autobiographical claim scope is evaluated via decoupled projection.
    """
    # 1. Non-eligible provenances
    non_eligible = [
        make_record("exp_u", provenance_kind=ExperienceProvenanceKind.USER_REPORTED),
        make_record("exp_o", provenance_kind=ExperienceProvenanceKind.OBSERVED_MEDIA),
        make_record("exp_v", provenance_kind=ExperienceProvenanceKind.VICARIOUS_DESCRIPTION),
        make_record("exp_s", provenance_kind=ExperienceProvenanceKind.SIMULATED),
        make_record("exp_k", provenance_kind=ExperienceProvenanceKind.UNKNOWN),
        make_record("exp_f", provenance_kind=ExperienceProvenanceKind.DIRECT_INTERACTION, is_fictional_frame=True),
    ]

    for rec in non_eligible:
        assert not is_eligible_personal_experience(rec)

    assert evaluate_experience_level(non_eligible) == ExperienceLevel.UNEXPERIENCED
    assert evaluate_familiarity_level(ExposureState.EXPOSED, non_eligible) == FamiliarityLevel.SURFACE_AWARE

    # 2. SHARED_INTERACTION is an eligible lived personal experience (objective growth fact)
    shared_records = [
        make_record("exp_sh_1", provenance_kind=ExperienceProvenanceKind.SHARED_INTERACTION, calendar_session_id="s1", timeline_tick=100),
        make_record("exp_sh_2", provenance_kind=ExperienceProvenanceKind.SHARED_INTERACTION, calendar_session_id="s1", timeline_tick=101),
        make_record("exp_sh_3", provenance_kind=ExperienceProvenanceKind.SHARED_INTERACTION, calendar_session_id="s2", timeline_tick=200),
    ]
    for rec in shared_records:
        assert is_eligible_personal_experience(rec)

    # PersonalGrowthState evaluates identically regardless of caller context
    assert evaluate_experience_level(shared_records) == ExperienceLevel.PRACTICED

    # 3. Decoupled autobiographical claim projection
    # SHARED_INTERACTION can support SHARED claim ("We played together")
    assert project_autobiographical_claim_support(shared_records, AutobiographicalClaimScope.SHARED) is True
    # SHARED_INTERACTION CANNOT support SOLITARY claim ("I played alone")
    assert project_autobiographical_claim_support(shared_records, AutobiographicalClaimScope.SOLITARY) is False

    # DIRECT_INTERACTION supports both
    direct_records = [
        make_record("exp_dir_1", provenance_kind=ExperienceProvenanceKind.DIRECT_INTERACTION, calendar_session_id="s1", timeline_tick=100),
    ]
    assert project_autobiographical_claim_support(direct_records, AutobiographicalClaimScope.SHARED) is True
    assert project_autobiographical_claim_support(direct_records, AutobiographicalClaimScope.SOLITARY) is True


def test_g26_curiosity_temporal_precedence_and_authority():
    """G26: Sequential curiosity evidence ordering by timeline_tick, domain isolation, and authority validation."""
    # 1. Authority validation checks
    with pytest.raises(UnanchoredCuriosityEvidenceError, match="Unauthorized curiosity evidence reference"):
        validate_curiosity_evidence_anchoring(
            CuriosityEvidence(
                evidence_kind=CuriosityEvidenceKind.AEVUM_EXPLICIT_INQUIRY,
                domain_key="genshin_impact",
                timeline_tick=100,
                evidence_source_ref="speech_act://fake",
                expression_snippet="fake snippet",
            )
        )

    with pytest.raises(UnanchoredCuriosityEvidenceError, match="requires non-empty expression_snippet"):
        validate_curiosity_evidence_anchoring(
            CuriosityEvidence(
                evidence_kind=CuriosityEvidenceKind.AEVUM_EXPLICIT_INQUIRY,
                domain_key="genshin_impact",
                timeline_tick=100,
                evidence_source_ref="turn://dialogue/10",
                expression_snippet="   ",
            )
        )

    # 2. Chronological sequence: Recommendation at tick 100 -> INVITED
    ev_rec = CuriosityEvidence(
        evidence_kind=CuriosityEvidenceKind.USER_RECOMMENDATION,
        domain_key="genshin_impact",
        timeline_tick=100,
        evidence_source_ref="speech_act://rec/1",
    )
    assert derive_curiosity_state([ev_rec], eligible_experience_records=[], domain_key="genshin_impact") == CuriosityState.INVITED

    # 3. Subsequent Aevum inquiry at tick 200 -> SELF_EXPRESSED
    ev_inq = CuriosityEvidence(
        evidence_kind=CuriosityEvidenceKind.AEVUM_EXPLICIT_INQUIRY,
        domain_key="genshin_impact",
        timeline_tick=200,
        evidence_source_ref="turn://dialogue/25",
        expression_snippet="Tell me how Fontaine's story begins.",
    )
    assert derive_curiosity_state([ev_rec, ev_inq], eligible_experience_records=[], domain_key="genshin_impact") == CuriosityState.SELF_EXPRESSED

    # 4. Domain Isolation: experience in "cooking" at tick 250 does NOT resolve curiosity for "genshin_impact"
    cooking_exp = make_record("exp_cook", domain_key="cooking", timeline_tick=250)
    assert derive_curiosity_state([ev_rec, ev_inq], eligible_experience_records=[cooking_exp], domain_key="genshin_impact") == CuriosityState.SELF_EXPRESSED

    # 5. Matching domain experience in "genshin_impact" at tick 300 resolves curiosity
    genshin_exp = make_record("exp_genshin", domain_key="genshin_impact", timeline_tick=300)
    assert derive_curiosity_state([ev_rec, ev_inq], eligible_experience_records=[cooking_exp, genshin_exp], domain_key="genshin_impact") == CuriosityState.RESOLVED
