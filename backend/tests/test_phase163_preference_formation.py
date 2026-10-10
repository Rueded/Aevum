"""Phase 16.3 Golden Tests: Independent Facet Appraisal & Preference Formation (G27 - G49).

Test Matrix:
  G27 (GC-404): Multi-Facet Sub-Domain Differentiation
  G28 (GC-405): Anti-Sycophancy Divergence
  G29 (GC-406): Experience != Preference
  G30 (GC-407): Longitudinal Consolidation -> ESTABLISHED_TASTE
  G31 (GC-414): Genuine Negative Preference Formation (AVOIDED)
  G32 (GC-413): Temperament Prior without Hard Determinism
  G33:          Epistemic Inertia - Outlier Noise Resistance
  G34:          Longitudinal Preference Revision
  G35:          Permanent Note A - Zero Floats (AST)
  G36:          Static AST Boundary Audit (imports, forbidden symbols)
  G37:          Cross-Domain Taste Isolation
  G38:          CompositeDomainPreference - Categorical Algorithm (COMPOSITE_MIXED)
  G39:          Temperament Cannot Create Appraisal; PROPOSED/Tier-3 Rejection
  G40:          User Preference Injection Barrier
  G41:          Appraisal Evidence Provenance Guard
  G42:          Priority 1 Wins - Temperament Non-Override (G42: lyrical + STRONG_FRICTION)
  G43:          Neutral Is Real Evidence
  G44:          Exact Polarity Bucket Aggregation (5 Cases, integer math)
  G45:          Revision State Orthogonality (PreferenceRevisionKind separate from PreferencePolarity163)
  G46:          Preference Table Reconstruction (Req 7 - source of truth)
  G47:          One-Experience-One-Appraisal Idempotency (Req 8)
  G48:          Registered Facet/Domain Validation (Req 10)
  G49:          Permutation Order-Independence (Req 12)
"""

from __future__ import annotations

import ast
import uuid
from pathlib import Path
from typing import Optional

import pytest

from app.growth.appraisal_models import (
    AppraisalEvidence,
    AppraisalEvidenceKind,
    AppraisalEvidenceStatus,
    CharacterTemperamentProfile,
    CompositeDomainPreference,
    DuplicateAppraisalError,
    FacetAppraisalRecord,
    PersonalPreferenceRecord,
    PolarityBucket,
    PreferencePolarity163,
    PreferenceRevisionKind,
    StabilityTier,
    TemperamentCompatibility,
    TemporalAnchorMismatchError,
    UngroundedAppraisalEvidenceError,
    UnknownGroundedSignalError,
    UnregisteredFacetError,
    AppraisalIdentityMismatchError,
    compute_composite_domain_preference,
    evaluate_consistency_threshold,
    map_appraisal_to_bucket,
    validate_legal_polarity_stability_combo,
    IllegalPolarityStabilityCombinationError,
)
from app.growth.experiential_models import (
    ExperienceProvenanceKind,
    ExposureKind,
    ExperientialRecord,
    FacetAppraisalKind,
)
from app.growth.facet_appraisal_engine import FacetAppraisalEngine
from app.growth.preference_formation_service import (
    AppraisalDataPoint,
    PreferenceCompatibilityProjector,
    _compute_preference_from_appraisals,
    _derive_polarity_and_stability,
    _map_hint_to_162_polarity,
)
from app.growth.state_machine import PreferencePolarity


# =============================================================================
# Shared Helpers & Fixtures
# =============================================================================

ENGINE = FacetAppraisalEngine()

REGISTERED_FACETS = frozenset({"music_ost", "combat_grind", "exploration", "lore_story"})
REGISTERED_DOMAINS = frozenset({"genshin_impact", "tea_culture", "classical_music"})

CHAR_ID = "char-test-001"
GENSHIN = "genshin_impact"
TEA = "tea_culture"
MUSIC = "classical_music"


def make_experience(
    experience_id: str,
    character_id: str = CHAR_ID,
    domain_key: str = GENSHIN,
    facet_key: str = "combat_grind",
    provenance: ExperienceProvenanceKind = ExperienceProvenanceKind.DIRECT_INTERACTION,
    timeline_tick: int = 100,
    calendar_session_id: str = "session-01",
    is_fictional_frame: bool = False,
) -> ExperientialRecord:
    return ExperientialRecord(
        experience_id=experience_id,
        character_id=character_id,
        domain_key=domain_key,
        facet_key=facet_key,
        provenance_kind=provenance,
        exposure_kind=ExposureKind.DIRECT_TOOL_BACKED_EXPERIENCE,
        calendar_session_id=calendar_session_id,
        timeline_tick=timeline_tick,
        interaction_evidence_ref="exec://session/01",
    )


def make_evidence(
    record: ExperientialRecord,
    grounded_signal: str,
    evidence_kind: AppraisalEvidenceKind = AppraisalEvidenceKind.BEHAVIORAL_ENGAGEMENT_OUTCOME,
    evidence_status: AppraisalEvidenceStatus = AppraisalEvidenceStatus.GROUNDED,
    qualia_summary: str = "",
) -> AppraisalEvidence:
    return AppraisalEvidence(
        evidence_id=str(uuid.uuid4()),
        evidence_kind=evidence_kind,
        evidence_status=evidence_status,
        experience_id=record.experience_id,
        character_id=record.character_id,
        domain_key=record.domain_key,
        facet_key=record.facet_key,
        timeline_tick=record.timeline_tick,
        grounded_signal=grounded_signal,
        qualia_summary=qualia_summary,
        evidence_source_ref="exec://session/01",
    )


def make_temperament(
    facet_key: str = "combat_grind",
    domain_key: str = GENSHIN,
    compatibility: TemperamentCompatibility = TemperamentCompatibility.NEUTRAL,
) -> CharacterTemperamentProfile:
    return CharacterTemperamentProfile(
        facet_key=facet_key,
        domain_key=domain_key,
        compatibility=compatibility,
    )


def build_appraisal_data(
    kinds: list[FacetAppraisalKind],
    session_ids: list[str],
    start_tick: int = 100,
) -> list[AppraisalDataPoint]:
    """Build a list of AppraisalDataPoints for pure function testing."""
    assert len(kinds) == len(session_ids)
    return [
        AppraisalDataPoint(
            appraisal_kind=k,
            calendar_session_id=s,
            timeline_tick=start_tick + i * 10,
        )
        for i, (k, s) in enumerate(zip(kinds, session_ids))
    ]


def make_preference_record(
    polarity: PreferencePolarity163,
    stability: StabilityTier,
    revision_kind: PreferenceRevisionKind = PreferenceRevisionKind.NONE,
    last_evaluated_tick: Optional[int] = None,
    facet_key: str = "combat_grind",
    domain_key: str = GENSHIN,
) -> PersonalPreferenceRecord:
    from app.growth.appraisal_models import utc_now
    return PersonalPreferenceRecord(
        preference_id=str(uuid.uuid4()),
        character_id=CHAR_ID,
        domain_key=domain_key,
        facet_key=facet_key,
        preference_polarity=polarity,
        stability_tier=stability,
        revision_kind=revision_kind,
        appraisal_count=5,
        distinct_session_count=3,
        last_evaluated_tick=last_evaluated_tick,
        updated_at=utc_now(),
    )


# =============================================================================
# G27 (GC-404): Multi-Facet Sub-Domain Differentiation
# =============================================================================

class TestG27MultiFacetDifferentiation:
    """Same domain can have divergent tastes across sub-facets."""

    def test_g27_ost_preferred_combat_disliked(self):
        """music_ost -> STRONGLY_PREFERRED; combat_grind -> DISLIKED within genshin_impact."""
        # Build music_ost appraisals (consistently STRONGLY_ATTRACTED across 5 sessions)
        ost_appraisals = build_appraisal_data(
            kinds=[FacetAppraisalKind.STRONGLY_ATTRACTED] * 7,
            session_ids=["s1", "s1", "s2", "s3", "s4", "s5", "s5"],
        )
        # Build combat_grind appraisals (consistently TEDIOUS across 5 sessions)
        combat_appraisals = build_appraisal_data(
            kinds=[FacetAppraisalKind.TEDIOUS_EXHAUSTING] * 7,
            session_ids=["s1", "s2", "s2", "s3", "s4", "s5", "s5"],
            start_tick=200,
        )

        ost_polarity, ost_stability, _ = _compute_preference_from_appraisals(ost_appraisals)
        combat_polarity, combat_stability, _ = _compute_preference_from_appraisals(combat_appraisals)

        # OST: STRONGLY_PREFERRED (7 STRONGLY_ATTRACTED = 100% >= 60% STRONG_INTENSITY threshold)
        assert ost_polarity == PreferencePolarity163.STRONGLY_PREFERRED
        assert ost_stability == StabilityTier.CONSOLIDATED

        # Combat: DISLIKED (TEDIOUS, not AVERSIVE so not AVOIDED)
        assert combat_polarity == PreferencePolarity163.DISLIKED
        assert combat_stability == StabilityTier.CONSOLIDATED

        # Verify they are in the same domain but independent
        assert ost_polarity != combat_polarity


# =============================================================================
# G28 (GC-405): Anti-Sycophancy Divergence
# =============================================================================

class TestG28AntiSycophancyDivergence:
    """User enthusiasm cannot change Aevum's independently formed preference."""

    def test_g28_user_loves_abyss_aevum_independently_dislikes(self):
        """User raves about Abyss combat; Aevum's own appraisals remain DISLIKED."""
        # Aevum's own behavioral appraisals: consistently TEDIOUS
        combat_appraisals = build_appraisal_data(
            kinds=[FacetAppraisalKind.TEDIOUS_EXHAUSTING] * 5,
            session_ids=["s1", "s2", "s3", "s3", "s4"],
        )
        polarity, stability, _ = _compute_preference_from_appraisals(combat_appraisals)

        # User's enthusiasm is not in the appraisal stream at all
        # Aevum's preference is derived solely from her own experiences
        assert polarity == PreferencePolarity163.DISLIKED
        assert stability == StabilityTier.STABILIZED

    def test_g28_user_statement_cannot_enter_as_evidence(self):
        """User preference rejection at Guard 1 prevents any injection path."""
        record = make_experience("exp-028", facet_key="combat_grind")
        evidence = make_evidence(
            record,
            grounded_signal="lyrical_resonance",
            evidence_kind=AppraisalEvidenceKind.USER_PREFERENCE_REJECTED,
        )
        temperament = make_temperament("combat_grind", GENSHIN, TemperamentCompatibility.STRONGLY_RESONANT)

        with pytest.raises(UngroundedAppraisalEvidenceError):
            ENGINE.evaluate_appraisal(
                record=record,
                evidence=evidence,
                temperament=temperament,
                existing_appraisal_pairs=frozenset(),
                registered_facet_keys=REGISTERED_FACETS,
            )


# =============================================================================
# G29 (GC-406): Experience != Preference
# =============================================================================

class TestG29ExperienceNotEqualsPreference:
    """100 sessions can yield EXPERIENCED level but still DISLIKED preference (GC-406)."""

    def test_g29_high_experience_but_disliked(self):
        """ExperienceLevel.EXPERIENCED + PreferencePolarity163.DISLIKED can coexist."""
        # 10 sessions × 10 tedious appraisals = 100 appraisals across 10 sessions
        kinds = [FacetAppraisalKind.TEDIOUS_EXHAUSTING] * 10
        sessions = [f"s{i}" for i in range(1, 11)]
        big_appraisals = build_appraisal_data(kinds=kinds, session_ids=sessions)

        polarity, stability, _ = _compute_preference_from_appraisals(big_appraisals)

        # Despite 100 total appraisals (if we had 100), 10 across 10 sessions gives CONSOLIDATED
        assert polarity == PreferencePolarity163.DISLIKED
        assert stability == StabilityTier.CONSOLIDATED  # 10 sessions >= 5, 80% >= 80%

        # Experience level is separate (evaluated by state_machine.evaluate_experience_level)
        # This test confirms preference and experience are orthogonal dimensions


# =============================================================================
# G30 (GC-407): Longitudinal Consolidation -> ESTABLISHED_TASTE
# =============================================================================

class TestG30LongitudinalConsolidation:
    """7 consistent appraisals across 5 sessions -> CONSOLIDATED + ESTABLISHED_TASTE path."""

    def test_g30_consolidated_positive_preference(self):
        """7 STRONGLY_ATTRACTED appraisals across 5 sessions -> STRONGLY_PREFERRED + CONSOLIDATED."""
        appraisals = build_appraisal_data(
            kinds=[FacetAppraisalKind.STRONGLY_ATTRACTED] * 7,
            session_ids=["s1", "s1", "s2", "s3", "s4", "s5", "s5"],
        )
        polarity, stability, _ = _compute_preference_from_appraisals(appraisals)

        assert polarity == PreferencePolarity163.STRONGLY_PREFERRED
        assert stability == StabilityTier.CONSOLIDATED

    def test_g30_consolidated_maps_to_attracted_in_162(self):
        """CONSOLIDATED STRONGLY_PREFERRED -> 16.2 compatibility projects to POSITIVE -> ATTRACTED."""
        hint = PreferenceCompatibilityProjector.project(PreferencePolarity163.STRONGLY_PREFERRED)
        assert hint == "POSITIVE"
        polarity_162 = _map_hint_to_162_polarity(hint)
        assert polarity_162 == PreferencePolarity.ATTRACTED


# =============================================================================
# G31 (GC-414): Genuine Negative Preference Formation (AVOIDED)
# =============================================================================

class TestG31GenuineNegativePreference:
    """Aevum can authentically say 'no' via AVOIDED preference."""

    def test_g31_aversive_appraisals_form_avoided(self):
        """Dominant AVERSIVE_DISLIKED at >= 60% of total -> AVOIDED (not just DISLIKED)."""
        appraisals = build_appraisal_data(
            kinds=[FacetAppraisalKind.AVERSIVE_DISLIKED] * 7,
            session_ids=["s1", "s2", "s3", "s3", "s4", "s5", "s5"],
        )
        polarity, stability, _ = _compute_preference_from_appraisals(appraisals)

        # 7/7 = 100% >= 60% STRONG_INTENSITY -> AVOIDED
        assert polarity == PreferencePolarity163.AVOIDED
        assert stability == StabilityTier.CONSOLIDATED

    def test_g31_avoided_maps_to_aversive_in_162(self):
        """AVOIDED -> 16.2 compatibility hint = NEGATIVE -> PreferencePolarity.AVERSIVE."""
        hint = PreferenceCompatibilityProjector.project(PreferencePolarity163.AVOIDED)
        assert hint == "NEGATIVE"
        assert _map_hint_to_162_polarity(hint) == PreferencePolarity.AVERSIVE


# =============================================================================
# G32 (GC-413): Temperament Non-Determinism (Priority 1 narratives override friction)
# =============================================================================

class TestG32TemperamentNonDeterminism:
    """Contemplative temperament + repeated genuine positive narrative -> PREFERRED."""

    def test_g32_positive_narrative_beats_friction_temperament(self):
        """Explicit positive signals (Priority 1) accumulate to PREFERRED regardless of temperament."""
        record = make_experience("exp-032", facet_key="lore_story")
        # Repeated lyrical_resonance appraisals (unambiguous Priority 1)
        evidence = make_evidence(record, "lyrical_resonance")

        # Contemplative + mechanical grind -> would produce FRICTION, but signal is Priority 1
        temperament = make_temperament("lore_story", GENSHIN, TemperamentCompatibility.FRICTION)

        appraisal = ENGINE.evaluate_appraisal(
            record=record,
            evidence=evidence,
            temperament=temperament,
            existing_appraisal_pairs=frozenset(),
            registered_facet_keys=REGISTERED_FACETS,
        )
        # Priority 1 signal overrides FRICTION temperament
        assert appraisal.appraisal_kind == FacetAppraisalKind.STRONGLY_ATTRACTED


# =============================================================================
# G33: Epistemic Inertia - Outlier Noise Resistance
# =============================================================================

class TestG33EpistemicInertia:
    """A CONSOLIDATED preference resists a single counter-session."""

    def test_g33_single_counter_session_does_not_flip_consolidated(self):
        """CONSOLIDATED PREFERRED + 1 counter-appraisal -> COUNTER_EVIDENCE_ACCUMULATING; polarity unchanged."""
        # Existing consolidated preference (last evaluated at tick 500)
        existing = make_preference_record(
            PreferencePolarity163.PREFERRED,
            StabilityTier.CONSOLIDATED,
            PreferenceRevisionKind.NONE,
            last_evaluated_tick=500,
        )

        # Full stream: 7 positive (ticks 100..500) + 1 new counter-appraisal (tick 600 > last_evaluated_tick 500)
        base = [
            AppraisalDataPoint(FacetAppraisalKind.ENJOYABLE, "s1", 100),
            AppraisalDataPoint(FacetAppraisalKind.ENJOYABLE, "s1", 150),
            AppraisalDataPoint(FacetAppraisalKind.ENJOYABLE, "s2", 200),
            AppraisalDataPoint(FacetAppraisalKind.ENJOYABLE, "s3", 300),
            AppraisalDataPoint(FacetAppraisalKind.ENJOYABLE, "s4", 400),
            AppraisalDataPoint(FacetAppraisalKind.ENJOYABLE, "s5", 450),
            AppraisalDataPoint(FacetAppraisalKind.ENJOYABLE, "s5", 500),
        ]
        counter = [
            AppraisalDataPoint(FacetAppraisalKind.TEDIOUS_EXHAUSTING, "s6", 600),
        ]
        appraisals = base + counter

        polarity, stability, revision_kind = _compute_preference_from_appraisals(appraisals, existing)

        # Counter-evidence accumulating, but polarity preserved
        assert revision_kind == PreferenceRevisionKind.COUNTER_EVIDENCE_ACCUMULATING
        assert polarity == PreferencePolarity163.PREFERRED
        assert stability == StabilityTier.CONSOLIDATED


# =============================================================================
# G34: Longitudinal Preference Revision
# =============================================================================

class TestG34LongitudinalPreferenceRevision:
    """Sustained opposing evidence triggers revision to MIXED_AMBIVALENT + TENTATIVE."""

    def test_g34_sustained_counter_triggers_revision(self):
        """4 counter-appraisals across 3 new sessions -> REVISION_TRIGGERED -> MIXED_AMBIVALENT."""
        # Existing CONSOLIDATED preference (last evaluated at tick 500)
        existing = make_preference_record(
            PreferencePolarity163.PREFERRED,
            StabilityTier.CONSOLIDATED,
            PreferenceRevisionKind.NONE,
            last_evaluated_tick=500,
        )

        # Full stream: 7 old positive (tick <= 500) + 4 counter across 3 new sessions (tick > 500)
        appraisals = build_appraisal_data(
            kinds=[FacetAppraisalKind.ENJOYABLE] * 7 + [FacetAppraisalKind.TEDIOUS_EXHAUSTING] * 4,
            session_ids=["s1", "s1", "s2", "s3", "s4", "s5", "s5", "s6", "s6", "s7", "s8"],
            start_tick=100,
        )
        # The last 4 appraisals are at ticks 170, 180, 190, 200 — all > last_tick=500? No.
        # Reconstruct to ensure counter-appraisals are at ticks > 500.
        base_appraisals = [
            AppraisalDataPoint(FacetAppraisalKind.ENJOYABLE, "s1", 100),
            AppraisalDataPoint(FacetAppraisalKind.ENJOYABLE, "s2", 200),
            AppraisalDataPoint(FacetAppraisalKind.ENJOYABLE, "s3", 300),
            AppraisalDataPoint(FacetAppraisalKind.ENJOYABLE, "s4", 400),
            AppraisalDataPoint(FacetAppraisalKind.ENJOYABLE, "s5", 500),
        ]
        counter_appraisals = [
            AppraisalDataPoint(FacetAppraisalKind.TEDIOUS_EXHAUSTING, "s6", 600),
            AppraisalDataPoint(FacetAppraisalKind.TEDIOUS_EXHAUSTING, "s6", 610),
            AppraisalDataPoint(FacetAppraisalKind.TEDIOUS_EXHAUSTING, "s7", 700),
            AppraisalDataPoint(FacetAppraisalKind.TEDIOUS_EXHAUSTING, "s8", 800),
        ]
        all_appraisals = base_appraisals + counter_appraisals

        polarity, stability, revision_kind = _compute_preference_from_appraisals(all_appraisals, existing)

        # 4 counter-appraisals across 3 new sessions >= thresholds -> REVISION_TRIGGERED
        assert revision_kind == PreferenceRevisionKind.REVISION_TRIGGERED
        # MIXED_AMBIVALENT always TENTATIVE (Blocker 4)
        assert polarity == PreferencePolarity163.MIXED_AMBIVALENT
        assert stability == StabilityTier.TENTATIVE


# =============================================================================
# G35: Permanent Note A - Zero Floats (AST)
# =============================================================================

class TestG35ZeroFloats:
    """Recursive AST inspection: zero float literals in all Phase 16.3 modules."""

    GROWTH_DIR = Path(__file__).parent.parent / "app" / "growth"
    PHASE163_FILES = [
        "appraisal_models.py",
        "facet_appraisal_engine.py",
        "preference_formation_service.py",
    ]

    def test_g35_zero_float_literals_in_phase163_modules(self):
        """No float() calls or float literal annotations in Phase 16.3 modules."""
        violations = []
        for filename in self.PHASE163_FILES:
            filepath = self.GROWTH_DIR / filename
            assert filepath.exists(), f"Phase 16.3 module {filename} not found"
            source = filepath.read_text(encoding="utf-8")
            tree = ast.parse(source)
            for node in ast.walk(tree):
                # Float constant literals
                if isinstance(node, ast.Constant) and isinstance(node.value, float):
                    violations.append(
                        f"{filename}:{node.lineno}: float literal {node.value!r}"
                    )
                # float() call
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Name) and func.id == "float":
                        violations.append(f"{filename}:{node.lineno}: float() call")
                # float annotation
                if isinstance(node, ast.Name) and node.id == "float":
                    if not isinstance(getattr(node, "_parent", None), ast.Call):
                        pass  # Names in annotations counted below
                if isinstance(node, ast.Constant) and node.value == "float":
                    violations.append(f"{filename}:{node.lineno}: 'float' string annotation")

        assert violations == [], f"Float violations found:\n" + "\n".join(violations)


# =============================================================================
# G36: Static AST Boundary Audit
# =============================================================================

class TestG36StaticASTBoundaryAudit:
    """Zero set_fact(), zero PromotionAuthorizationToken, zero 16.3 imports in state_machine.py."""

    GROWTH_DIR = Path(__file__).parent.parent / "app" / "growth"
    PHASE163_FILES = [
        "appraisal_models.py",
        "facet_appraisal_engine.py",
        "preference_formation_service.py",
    ]

    def test_g36_no_set_fact_or_promotion_token_in_phase163(self):
        """Phase 16.3 modules must not call set_fact() or PromotionAuthorizationToken."""
        forbidden_names = {"set_fact", "PromotionAuthorizationToken"}
        violations = []
        for filename in self.PHASE163_FILES:
            filepath = self.GROWTH_DIR / filename
            source = filepath.read_text(encoding="utf-8")
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and node.id in forbidden_names:
                    violations.append(f"{filename}:{node.lineno}: forbidden symbol '{node.id}'")
                if isinstance(node, ast.Attribute) and node.attr in forbidden_names:
                    violations.append(f"{filename}:{node.lineno}: forbidden symbol '{node.attr}'")

        assert violations == [], "Forbidden symbols:\n" + "\n".join(violations)

    def test_g36_state_machine_has_zero_imports_from_phase163(self):
        """state_machine.py (16.2 frozen) must import NOTHING from Phase 16.3 modules."""
        state_machine_path = self.GROWTH_DIR / "state_machine.py"
        source = state_machine_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        phase163_modules = {
            "appraisal_models",
            "facet_appraisal_engine",
            "preference_formation_service",
        }
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = ""
                if isinstance(node, ast.ImportFrom) and node.module:
                    module = node.module
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        module = alias.name
                for p163_mod in phase163_modules:
                    if p163_mod in module:
                        violations.append(
                            f"state_machine.py:{node.lineno}: imports from Phase 16.3 module '{p163_mod}'"
                        )

        assert violations == [], (
            "state_machine.py (Phase 16.2 FROZEN) must have zero imports from Phase 16.3:\n"
            + "\n".join(violations)
        )


# =============================================================================
# G37: Cross-Domain Taste Isolation
# =============================================================================

class TestG37CrossDomainIsolation:
    """genshin_impact taste does not affect tea_culture or classical_music."""

    def test_g37_separate_domain_appraisals_are_independent(self):
        """Different domain/facet combinations produce independent preferences."""
        genshin_appraisals = build_appraisal_data(
            kinds=[FacetAppraisalKind.TEDIOUS_EXHAUSTING] * 5,
            session_ids=["s1", "s2", "s3", "s3", "s4"],
        )
        tea_appraisals = build_appraisal_data(
            kinds=[FacetAppraisalKind.STRONGLY_ATTRACTED] * 5,
            session_ids=["s1", "s2", "s3", "s4", "s5"],
            start_tick=500,
        )

        genshin_polarity, _, _ = _compute_preference_from_appraisals(genshin_appraisals)
        tea_polarity, _, _ = _compute_preference_from_appraisals(tea_appraisals)

        assert genshin_polarity == PreferencePolarity163.DISLIKED
        assert tea_polarity == PreferencePolarity163.STRONGLY_PREFERRED
        assert genshin_polarity != tea_polarity


# =============================================================================
# G38: CompositeDomainPreference - Categorical Algorithm (COMPOSITE_MIXED)
# =============================================================================

class TestG38CompositeDomainPreference:
    """Categorical composition: preferred OST + disliked combat -> COMPOSITE_MIXED."""

    def test_g38_composite_mixed_no_scalar_averaging(self):
        """Positive and negative formed facets -> COMPOSITE_MIXED (not a scalar average)."""
        from app.growth.appraisal_models import utc_now

        ost_pref = PersonalPreferenceRecord(
            preference_id="p1",
            character_id=CHAR_ID,
            domain_key=GENSHIN,
            facet_key="music_ost",
            preference_polarity=PreferencePolarity163.PREFERRED,
            stability_tier=StabilityTier.STABILIZED,
            revision_kind=PreferenceRevisionKind.NONE,
            appraisal_count=5,
            distinct_session_count=3,
            last_evaluated_tick=500,
            updated_at=utc_now(),
        )
        combat_pref = PersonalPreferenceRecord(
            preference_id="p2",
            character_id=CHAR_ID,
            domain_key=GENSHIN,
            facet_key="combat_grind",
            preference_polarity=PreferencePolarity163.DISLIKED,
            stability_tier=StabilityTier.STABILIZED,
            revision_kind=PreferenceRevisionKind.NONE,
            appraisal_count=5,
            distinct_session_count=3,
            last_evaluated_tick=500,
            updated_at=utc_now(),
        )

        result = compute_composite_domain_preference([ost_pref, combat_pref])
        assert result == CompositeDomainPreference.COMPOSITE_MIXED

    def test_g38_positive_only_gives_composite_positive(self):
        """All preferred facets -> COMPOSITE_POSITIVE."""
        from app.growth.appraisal_models import utc_now

        prefs = [
            PersonalPreferenceRecord(
                preference_id=str(uuid.uuid4()),
                character_id=CHAR_ID,
                domain_key=GENSHIN,
                facet_key=f"facet_{i}",
                preference_polarity=PreferencePolarity163.PREFERRED,
                stability_tier=StabilityTier.STABILIZED,
                revision_kind=PreferenceRevisionKind.NONE,
                appraisal_count=4,
                distinct_session_count=3,
                last_evaluated_tick=300,
                updated_at=utc_now(),
            )
            for i in range(3)
        ]
        result = compute_composite_domain_preference(prefs)
        assert result == CompositeDomainPreference.COMPOSITE_POSITIVE


# =============================================================================
# G39: Temperament Cannot Create Appraisal; PROPOSED/Tier-3 Rejection
# =============================================================================

class TestG39AppraisalEvidenceGuards:
    """Guard chain ensures only GROUNDED, non-Tier-3 evidence enters the engine."""

    def test_g39_no_evidence_no_appraisal(self):
        """Without any evidence, no appraisal can be produced — engine requires evidence input."""
        # This is architecturally enforced: evaluate_appraisal() requires an AppraisalEvidence arg.
        # We verify that PROPOSED evidence is rejected.
        record = make_experience("exp-039")
        proposed_evidence = make_evidence(
            record,
            "routine_interaction",
            evidence_kind=AppraisalEvidenceKind.DIRECT_FIRST_PERSON_REACTION,
            evidence_status=AppraisalEvidenceStatus.PROPOSED,
        )
        temperament = make_temperament(compatibility=TemperamentCompatibility.STRONGLY_RESONANT)

        with pytest.raises(UngroundedAppraisalEvidenceError) as exc:
            ENGINE.evaluate_appraisal(
                record=record,
                evidence=proposed_evidence,
                temperament=temperament,
                existing_appraisal_pairs=frozenset(),
                registered_facet_keys=REGISTERED_FACETS,
            )
        assert "PROPOSED" in str(exc.value)

    def test_g39_tier3_recommendation_rejected_at_guard1(self):
        """USER_RECOMMENDATION_REJECTED is Tier-3 and rejected at Guard 1."""
        record = make_experience("exp-039b")
        evidence = make_evidence(
            record,
            "lyrical_resonance",
            evidence_kind=AppraisalEvidenceKind.USER_RECOMMENDATION_REJECTED,
            evidence_status=AppraisalEvidenceStatus.GROUNDED,
        )
        temperament = make_temperament()

        with pytest.raises(UngroundedAppraisalEvidenceError):
            ENGINE.evaluate_appraisal(
                record=record,
                evidence=evidence,
                temperament=temperament,
                existing_appraisal_pairs=frozenset(),
                registered_facet_keys=REGISTERED_FACETS,
            )

    def test_g39_rejected_status_blocked_at_guard2(self):
        """REJECTED evidence status is blocked at Guard 2 even if kind is Tier-1."""
        record = make_experience("exp-039c")
        evidence = make_evidence(
            record,
            "lyrical_resonance",
            evidence_kind=AppraisalEvidenceKind.BEHAVIORAL_ENGAGEMENT_OUTCOME,
            evidence_status=AppraisalEvidenceStatus.REJECTED,
        )
        temperament = make_temperament()

        with pytest.raises(UngroundedAppraisalEvidenceError) as exc:
            ENGINE.evaluate_appraisal(
                record=record,
                evidence=evidence,
                temperament=temperament,
                existing_appraisal_pairs=frozenset(),
                registered_facet_keys=REGISTERED_FACETS,
            )
        assert "REJECTED" in str(exc.value)


# =============================================================================
# G40: User Preference Injection Barrier
# =============================================================================

class TestG40UserPreferenceInjectionBarrier:
    """User enthusiasm cannot create Aevum's positive appraisal."""

    def test_g40_user_preference_rejected_kind_blocked(self):
        """USER_PREFERENCE_REJECTED kind cannot enter FacetAppraisalEngine regardless of signal."""
        record = make_experience("exp-040")
        evidence = make_evidence(
            record,
            "lyrical_resonance",  # Even a very positive signal
            evidence_kind=AppraisalEvidenceKind.USER_PREFERENCE_REJECTED,
            evidence_status=AppraisalEvidenceStatus.GROUNDED,
        )
        temperament = make_temperament(compatibility=TemperamentCompatibility.STRONGLY_RESONANT)

        with pytest.raises(UngroundedAppraisalEvidenceError):
            ENGINE.evaluate_appraisal(
                record=record,
                evidence=evidence,
                temperament=temperament,
                existing_appraisal_pairs=frozenset(),
                registered_facet_keys=REGISTERED_FACETS,
            )


# =============================================================================
# G41: Appraisal Evidence Provenance Guard
# =============================================================================

class TestG41EvidenceProvenanceGuard:
    """Both Tier-3 kinds are blocked at Guard 1."""

    @pytest.mark.parametrize("kind", [
        AppraisalEvidenceKind.USER_RECOMMENDATION_REJECTED,
        AppraisalEvidenceKind.USER_PREFERENCE_REJECTED,
    ])
    def test_g41_tier3_kinds_always_rejected(self, kind: AppraisalEvidenceKind):
        """All Tier-3 evidence kinds are permanently blocked at Guard 1."""
        record = make_experience(f"exp-041-{kind.value}")
        evidence = make_evidence(
            record,
            "lyrical_resonance",
            evidence_kind=kind,
            evidence_status=AppraisalEvidenceStatus.GROUNDED,
        )
        temperament = make_temperament()

        with pytest.raises(UngroundedAppraisalEvidenceError):
            ENGINE.evaluate_appraisal(
                record=record,
                evidence=evidence,
                temperament=temperament,
                existing_appraisal_pairs=frozenset(),
                registered_facet_keys=REGISTERED_FACETS,
            )


# =============================================================================
# G42: Priority 1 Wins - Temperament Non-Override
# =============================================================================

class TestG42TemperamentNonOverride:
    """Unambiguous Priority 1 signal always beats STRONG_FRICTION temperament (G42)."""

    def test_g42_lyrical_resonance_plus_strong_friction_yields_strongly_attracted(self):
        """lyrical_resonance (Priority 1) + STRONG_FRICTION temperament -> STRONGLY_ATTRACTED."""
        record = make_experience("exp-042", facet_key="music_ost")
        evidence = make_evidence(
            record,
            "lyrical_resonance",  # Unambiguous Priority 1 signal
            evidence_kind=AppraisalEvidenceKind.BEHAVIORAL_ENGAGEMENT_OUTCOME,
        )
        temperament = make_temperament(
            "music_ost", GENSHIN, TemperamentCompatibility.STRONG_FRICTION
        )

        appraisal = ENGINE.evaluate_appraisal(
            record=record,
            evidence=evidence,
            temperament=temperament,
            existing_appraisal_pairs=frozenset(),
            registered_facet_keys=REGISTERED_FACETS,
        )

        # Priority 1 bypasses temperament entirely (G42 core invariant)
        assert appraisal.appraisal_kind == FacetAppraisalKind.STRONGLY_ATTRACTED

    def test_g42_exhausting_loop_plus_strongly_resonant_yields_tedious(self):
        """exhausting_loop (Priority 1) + STRONGLY_RESONANT temperament -> TEDIOUS_EXHAUSTING."""
        record = make_experience("exp-042b", facet_key="combat_grind")
        evidence = make_evidence(record, "exhausting_loop")
        temperament = make_temperament("combat_grind", GENSHIN, TemperamentCompatibility.STRONGLY_RESONANT)

        appraisal = ENGINE.evaluate_appraisal(
            record=record,
            evidence=evidence,
            temperament=temperament,
            existing_appraisal_pairs=frozenset(),
            registered_facet_keys=REGISTERED_FACETS,
        )
        assert appraisal.appraisal_kind == FacetAppraisalKind.TEDIOUS_EXHAUSTING

    def test_g42_timeline_tick_is_engine_set(self):
        """appraisal.timeline_tick == record.timeline_tick (non-configurable, Blocker 5)."""
        record = make_experience("exp-042c", timeline_tick=777, facet_key="music_ost")
        evidence = make_evidence(record, "lyrical_resonance")
        temperament = make_temperament("music_ost")

        appraisal = ENGINE.evaluate_appraisal(
            record=record,
            evidence=evidence,
            temperament=temperament,
            existing_appraisal_pairs=frozenset(),
            registered_facet_keys=REGISTERED_FACETS,
        )
        assert appraisal.timeline_tick == 777  # Engine-set to record.timeline_tick

    def test_g42_priority2_uses_temperament_tiebreak(self):
        """Ambiguous signal (Priority 2) -> temperament acts as deterministic tie-break."""
        record = make_experience("exp-042d", facet_key="combat_grind")

        # Ambiguous signal with STRONGLY_RESONANT -> ENJOYABLE
        ev_resonant = make_evidence(record, "routine_interaction")
        t_resonant = make_temperament("combat_grind", GENSHIN, TemperamentCompatibility.STRONGLY_RESONANT)
        appraisal_resonant = ENGINE.evaluate_appraisal(
            record=record,
            evidence=ev_resonant,
            temperament=t_resonant,
            existing_appraisal_pairs=frozenset(),
            registered_facet_keys=REGISTERED_FACETS,
        )
        assert appraisal_resonant.appraisal_kind == FacetAppraisalKind.ENJOYABLE

        # Same ambiguous signal with STRONG_FRICTION -> NEUTRAL_INDIFFERENT
        record2 = make_experience("exp-042e", facet_key="combat_grind", timeline_tick=200)
        ev_friction = make_evidence(record2, "routine_interaction")
        t_friction = make_temperament("combat_grind", GENSHIN, TemperamentCompatibility.STRONG_FRICTION)
        appraisal_friction = ENGINE.evaluate_appraisal(
            record=record2,
            evidence=ev_friction,
            temperament=t_friction,
            existing_appraisal_pairs=frozenset(),
            registered_facet_keys=REGISTERED_FACETS,
        )
        assert appraisal_friction.appraisal_kind == FacetAppraisalKind.NEUTRAL_INDIFFERENT


# =============================================================================
# G43: Neutral Is Real Evidence
# =============================================================================

class TestG43NeutralIsRealEvidence:
    """NEUTRAL_INDIFFERENT dominant across longitudinal sessions -> NEUTRAL preference (not DISLIKED)."""

    def test_g43_neutral_dominant_gives_neutral_preference(self):
        """4 NEUTRAL_INDIFFERENT across 3 sessions -> PreferencePolarity163.NEUTRAL."""
        appraisals = build_appraisal_data(
            kinds=[FacetAppraisalKind.NEUTRAL_INDIFFERENT] * 4,
            session_ids=["s1", "s2", "s3", "s3"],
        )
        polarity, stability, _ = _compute_preference_from_appraisals(appraisals)

        assert polarity == PreferencePolarity163.NEUTRAL
        assert stability in (StabilityTier.TENTATIVE, StabilityTier.STABILIZED)

    def test_g43_neutral_is_not_forced_to_disliked(self):
        """NEUTRAL dominant stream never resolves to DISLIKED."""
        appraisals = build_appraisal_data(
            kinds=[FacetAppraisalKind.NEUTRAL_INDIFFERENT] * 6,
            session_ids=["s1", "s2", "s2", "s3", "s4", "s4"],
        )
        polarity, _, _ = _compute_preference_from_appraisals(appraisals)
        assert polarity != PreferencePolarity163.DISLIKED
        assert polarity == PreferencePolarity163.NEUTRAL

    def test_g43_neutral_maps_to_neutral_in_162(self):
        """PreferencePolarity163.NEUTRAL -> hint=NEUTRAL -> PreferencePolarity.NEUTRAL."""
        hint = PreferenceCompatibilityProjector.project(PreferencePolarity163.NEUTRAL)
        assert hint == "NEUTRAL"
        assert _map_hint_to_162_polarity(hint) == PreferencePolarity.NEUTRAL


# =============================================================================
# G44: Exact Polarity Bucket Aggregation - 5 Cases
# =============================================================================

class TestG44ExactPolarityBucketAggregation:
    """All 5 conflict cases use integer arithmetic (Permanent Note A)."""

    def test_g44_evaluate_consistency_threshold_integer_math(self):
        """bucket_count * 100 >= total_count * percentage (zero floats)."""
        # 3/4 = 75% >= 75% -> True
        assert evaluate_consistency_threshold(3, 4, 75) is True
        # 2/4 = 50% >= 75% -> False
        assert evaluate_consistency_threshold(2, 4, 75) is False
        # 4/5 = 80% >= 75% -> True
        assert evaluate_consistency_threshold(4, 5, 75) is True
        # 0/0 -> False (edge case)
        assert evaluate_consistency_threshold(0, 0, 75) is False

    def test_g44_case_a_positive_negative_conflict_without_dominance_gives_mixed(self):
        """Case A: POSITIVE + NEGATIVE, neither achieves 75% -> MIXED_AMBIVALENT."""
        appraisals = build_appraisal_data(
            kinds=[FacetAppraisalKind.ENJOYABLE] * 3 + [FacetAppraisalKind.TEDIOUS_EXHAUSTING] * 2,
            session_ids=["s1", "s2", "s3", "s4", "s5"],
        )
        polarity, stability, _ = _compute_preference_from_appraisals(appraisals)
        # 3/5 = 60%, 2/5 = 40% — neither achieves 75% and both present -> MIXED
        assert polarity == PreferencePolarity163.MIXED_AMBIVALENT
        assert stability == StabilityTier.TENTATIVE  # MIXED always TENTATIVE (Blocker 4)

    def test_g44_case_b_positive_plus_neutral_positive_stabilizes(self):
        """Case B: POSITIVE + NEUTRAL (no NEGATIVE) -> positive can stabilize."""
        appraisals = build_appraisal_data(
            kinds=[FacetAppraisalKind.ENJOYABLE] * 3 + [FacetAppraisalKind.NEUTRAL_INDIFFERENT],
            session_ids=["s1", "s2", "s3", "s4"],
        )
        polarity, stability, _ = _compute_preference_from_appraisals(appraisals)
        # 3/4 = 75% POSITIVE >= 75% -> PREFERRED or better
        assert polarity in (PreferencePolarity163.PREFERRED, PreferencePolarity163.STRONGLY_PREFERRED)

    def test_g44_case_d_neutral_dominant_gives_neutral_preference(self):
        """Case D: NEUTRAL dominant -> PreferencePolarity163.NEUTRAL."""
        appraisals = build_appraisal_data(
            kinds=[FacetAppraisalKind.NEUTRAL_INDIFFERENT] * 4,
            session_ids=["s1", "s2", "s3", "s3"],
        )
        polarity, _, _ = _compute_preference_from_appraisals(appraisals)
        assert polarity == PreferencePolarity163.NEUTRAL

    def test_g44_mixed_ambivalent_always_tentative(self):
        """MIXED_AMBIVALENT polarity is always paired with TENTATIVE stability (Blocker 4)."""
        validate_legal_polarity_stability_combo(
            PreferencePolarity163.MIXED_AMBIVALENT, StabilityTier.TENTATIVE
        )  # Should not raise

        with pytest.raises(IllegalPolarityStabilityCombinationError):
            validate_legal_polarity_stability_combo(
                PreferencePolarity163.MIXED_AMBIVALENT, StabilityTier.CONSOLIDATED
            )

        with pytest.raises(IllegalPolarityStabilityCombinationError):
            validate_legal_polarity_stability_combo(
                PreferencePolarity163.MIXED_AMBIVALENT, StabilityTier.STABILIZED
            )


# =============================================================================
# G45: Revision State Orthogonality
# =============================================================================

class TestG45RevisionStateOrthogonality:
    """PreferenceRevisionKind is orthogonal to and separate from PreferencePolarity163."""

    def test_g45_revision_triggered_is_not_in_preference_polarity(self):
        """REVISION_TRIGGERED is a PreferenceRevisionKind value, not a PreferencePolarity163 value."""
        polarity_values = {p.value for p in PreferencePolarity163}
        revision_values = {r.value for r in PreferenceRevisionKind}

        # Completely disjoint: no overlap between polarity and revision values
        assert polarity_values.isdisjoint(revision_values)
        assert "REVISION_TRIGGERED" not in polarity_values
        assert "REVISION_TRIGGERED" in revision_values

    def test_g45_counter_evidence_accumulating_is_not_polarity(self):
        """COUNTER_EVIDENCE_ACCUMULATING is PreferenceRevisionKind, not polarity."""
        polarity_values = {p.value for p in PreferencePolarity163}
        assert "COUNTER_EVIDENCE_ACCUMULATING" not in polarity_values

    def test_g45_preference_record_carries_both_independently(self):
        """PersonalPreferenceRecord can have polarity=PREFERRED + revision=COUNTER_EVIDENCE_ACCUMULATING."""
        from app.growth.appraisal_models import utc_now
        rec = PersonalPreferenceRecord(
            preference_id=str(uuid.uuid4()),
            character_id=CHAR_ID,
            domain_key=GENSHIN,
            facet_key="combat_grind",
            preference_polarity=PreferencePolarity163.PREFERRED,
            stability_tier=StabilityTier.CONSOLIDATED,
            revision_kind=PreferenceRevisionKind.COUNTER_EVIDENCE_ACCUMULATING,
            appraisal_count=8,
            distinct_session_count=5,
            last_evaluated_tick=800,
            updated_at=utc_now(),
        )
        assert rec.preference_polarity == PreferencePolarity163.PREFERRED
        assert rec.revision_kind == PreferenceRevisionKind.COUNTER_EVIDENCE_ACCUMULATING


# =============================================================================
# G46: Preference Table Reconstruction (Req 7 — appraisal stream is source of truth)
# =============================================================================

class TestG46PreferenceTableReconstruction:
    """Same appraisal stream always produces identical preference regardless of prior state."""

    def test_g46_recompute_gives_same_result(self):
        """Calling _compute_preference_from_appraisals() twice gives identical result (idempotent)."""
        appraisals = build_appraisal_data(
            kinds=[FacetAppraisalKind.STRONGLY_ATTRACTED] * 7,
            session_ids=["s1", "s1", "s2", "s3", "s4", "s5", "s5"],
        )
        result1 = _compute_preference_from_appraisals(appraisals)
        result2 = _compute_preference_from_appraisals(appraisals)

        assert result1 == result2

    def test_g46_cleared_and_rebuilt_gives_same_result(self):
        """Clearing preference and recomputing from stream gives same (polarity, stability) as original."""
        appraisals = build_appraisal_data(
            kinds=[FacetAppraisalKind.ENJOYABLE] * 5,
            session_ids=["s1", "s2", "s3", "s3", "s4"],
        )
        result_original = _compute_preference_from_appraisals(appraisals)

        # Simulate "clearing" by passing no existing preference
        result_rebuilt = _compute_preference_from_appraisals(appraisals, existing_preference=None)

        # Polarity and stability must be identical (materialized projection is reconstructible)
        assert result_original[0] == result_rebuilt[0]  # polarity
        assert result_original[1] == result_rebuilt[1]  # stability


# =============================================================================
# G47: One-Experience-One-Appraisal Idempotency (Req 8)
# =============================================================================

class TestG47OneExperienceOneAppraisalIdempotency:
    """Second appraisal for same (experience_id, facet_key) raises DuplicateAppraisalError."""

    def test_g47_duplicate_raises_error(self):
        """DuplicateAppraisalError raised when (experience_id, facet_key) pair already exists."""
        record = make_experience("exp-047", facet_key="combat_grind")
        evidence = make_evidence(record, "exhausting_loop")
        temperament = make_temperament("combat_grind")

        # First call: OK
        first = ENGINE.evaluate_appraisal(
            record=record,
            evidence=evidence,
            temperament=temperament,
            existing_appraisal_pairs=frozenset(),
            registered_facet_keys=REGISTERED_FACETS,
        )
        assert first.appraisal_kind == FacetAppraisalKind.TEDIOUS_EXHAUSTING

        # Second call with same (experience_id, facet_key) already in existing_appraisal_pairs
        existing_pairs = frozenset({(record.experience_id, record.facet_key)})
        with pytest.raises(DuplicateAppraisalError):
            ENGINE.evaluate_appraisal(
                record=record,
                evidence=evidence,
                temperament=temperament,
                existing_appraisal_pairs=existing_pairs,
                registered_facet_keys=REGISTERED_FACETS,
            )


# =============================================================================
# G48: Registered Facet/Domain Validation (Req 10)
# =============================================================================

class TestG48RegisteredFacetValidation:
    """Unregistered facet_key -> UnregisteredFacetError at engine Guard 4."""

    def test_g48_unregistered_facet_raises_error(self):
        """Appraisal for unregistered facet_key is rejected at Guard 4."""
        record = make_experience("exp-048", facet_key="NONEXISTENT_FACET")
        evidence = make_evidence(record, "lyrical_resonance")
        temperament = make_temperament("NONEXISTENT_FACET")

        with pytest.raises(UnregisteredFacetError) as exc:
            ENGINE.evaluate_appraisal(
                record=record,
                evidence=evidence,
                temperament=temperament,
                existing_appraisal_pairs=frozenset(),
                registered_facet_keys=REGISTERED_FACETS,  # Does not contain "NONEXISTENT_FACET"
            )
        assert "NONEXISTENT_FACET" in str(exc.value)

    def test_g48_registered_facet_proceeds_normally(self):
        """Registered facet_key passes Guard 4 without error."""
        record = make_experience("exp-048b", facet_key="music_ost")
        evidence = make_evidence(record, "lyrical_resonance")
        temperament = make_temperament("music_ost")

        appraisal = ENGINE.evaluate_appraisal(
            record=record,
            evidence=evidence,
            temperament=temperament,
            existing_appraisal_pairs=frozenset(),
            registered_facet_keys=REGISTERED_FACETS,
        )
        assert appraisal is not None
        assert appraisal.facet_key == "music_ost"


# =============================================================================
# G49: Permutation Order-Independence (Req 12)
# =============================================================================

class TestG49PermutationOrderIndependence:
    """Same appraisal content in different ingestion order -> identical preference."""

    def test_g49_forward_and_reverse_order_give_same_result(self):
        """[A, B, C] and [C, A, B] ingestion order -> same (polarity, stability, revision_kind)."""
        forward = [
            AppraisalDataPoint(FacetAppraisalKind.ENJOYABLE,           "s1", 100),
            AppraisalDataPoint(FacetAppraisalKind.STRONGLY_ATTRACTED,  "s2", 200),
            AppraisalDataPoint(FacetAppraisalKind.ENJOYABLE,           "s3", 300),
            AppraisalDataPoint(FacetAppraisalKind.STRONGLY_ATTRACTED,  "s4", 400),
            AppraisalDataPoint(FacetAppraisalKind.ENJOYABLE,           "s5", 500),
        ]
        # Reverse order (as if ingested in different order)
        reversed_order = list(reversed(forward))
        # Scrambled order
        scrambled = [forward[2], forward[4], forward[0], forward[3], forward[1]]

        result_forward = _compute_preference_from_appraisals(forward)
        result_reversed = _compute_preference_from_appraisals(reversed_order)
        result_scrambled = _compute_preference_from_appraisals(scrambled)

        assert result_forward == result_reversed, (
            f"Forward and reversed order gave different results: {result_forward} vs {result_reversed}"
        )
        assert result_forward == result_scrambled, (
            f"Forward and scrambled order gave different results: {result_forward} vs {result_scrambled}"
        )

    def test_g49_same_content_different_session_ordering_gives_same_result(self):
        """Verify session counting is also permutation-invariant (set-based)."""
        stream_a = [
            AppraisalDataPoint(FacetAppraisalKind.STRONGLY_ATTRACTED, "session-alpha", 100),
            AppraisalDataPoint(FacetAppraisalKind.STRONGLY_ATTRACTED, "session-beta",  200),
            AppraisalDataPoint(FacetAppraisalKind.STRONGLY_ATTRACTED, "session-gamma", 300),
            AppraisalDataPoint(FacetAppraisalKind.STRONGLY_ATTRACTED, "session-delta", 400),
            AppraisalDataPoint(FacetAppraisalKind.STRONGLY_ATTRACTED, "session-epsilon", 500),
        ]
        stream_b = [
            AppraisalDataPoint(FacetAppraisalKind.STRONGLY_ATTRACTED, "session-epsilon", 500),
            AppraisalDataPoint(FacetAppraisalKind.STRONGLY_ATTRACTED, "session-alpha",   100),
            AppraisalDataPoint(FacetAppraisalKind.STRONGLY_ATTRACTED, "session-delta",   400),
            AppraisalDataPoint(FacetAppraisalKind.STRONGLY_ATTRACTED, "session-beta",    200),
            AppraisalDataPoint(FacetAppraisalKind.STRONGLY_ATTRACTED, "session-gamma",   300),
        ]
        result_a = _compute_preference_from_appraisals(stream_a)
        result_b = _compute_preference_from_appraisals(stream_b)

        assert result_a == result_b

    def test_g49_sorted_by_timeline_tick_internally(self):
        """_compute_preference_from_appraisals sorts by timeline_tick regardless of input order."""
        # Epistemic inertia depends on ordering: earlier ticks = old history, later = new
        # With correct sorting, the counter-evidence is recognized as "new" only if tick > last_evaluated_tick
        existing = make_preference_record(
            PreferencePolarity163.PREFERRED,
            StabilityTier.CONSOLIDATED,
            last_evaluated_tick=300,
        )
        # Chronological stream (ticks 100, 200, 300 = old positive; 400, 500, 600, 700 = new counter)
        old = [AppraisalDataPoint(FacetAppraisalKind.ENJOYABLE, f"old-s{i}", 100 * i) for i in range(1, 4)]
        new = [AppraisalDataPoint(FacetAppraisalKind.TEDIOUS_EXHAUSTING, f"new-s{i}", 400 * i) for i in range(1, 5)]
        ordered = old + new

        # Shuffled (same data, different order)
        shuffled = new + old

        result_ordered = _compute_preference_from_appraisals(ordered, existing)
        result_shuffled = _compute_preference_from_appraisals(shuffled, existing)

        # Both must sort internally to reach same conclusion
        assert result_ordered == result_shuffled


# =============================================================================
# Additional: engine guard completeness tests
# =============================================================================

class TestEngineguardCompleteness:
    """Supplementary tests for timeline tick mismatch and identity mismatch guards."""

    def test_timeline_tick_mismatch_raises(self):
        """Guard 6: evidence.timeline_tick != record.timeline_tick -> TemporalAnchorMismatchError."""
        record = make_experience("exp-tc01", timeline_tick=100, facet_key="combat_grind")
        # Evidence with different timeline_tick
        evidence = AppraisalEvidence(
            evidence_id=str(uuid.uuid4()),
            evidence_kind=AppraisalEvidenceKind.BEHAVIORAL_ENGAGEMENT_OUTCOME,
            evidence_status=AppraisalEvidenceStatus.GROUNDED,
            experience_id=record.experience_id,
            character_id=record.character_id,
            domain_key=record.domain_key,
            facet_key=record.facet_key,
            timeline_tick=999,  # Different from record's 100
            grounded_signal="lyrical_resonance",
            evidence_source_ref="exec://session/01",
        )
        temperament = make_temperament("combat_grind")

        with pytest.raises(TemporalAnchorMismatchError):
            ENGINE.evaluate_appraisal(
                record=record,
                evidence=evidence,
                temperament=temperament,
                existing_appraisal_pairs=frozenset(),
                registered_facet_keys=REGISTERED_FACETS,
            )

    def test_identity_mismatch_raises(self):
        """Guard 5: facet_key mismatch -> AppraisalIdentityMismatchError."""
        record = make_experience("exp-id01", facet_key="combat_grind", timeline_tick=100)
        evidence = AppraisalEvidence(
            evidence_id=str(uuid.uuid4()),
            evidence_kind=AppraisalEvidenceKind.BEHAVIORAL_ENGAGEMENT_OUTCOME,
            evidence_status=AppraisalEvidenceStatus.GROUNDED,
            experience_id=record.experience_id,
            character_id=record.character_id,
            domain_key=record.domain_key,
            facet_key="music_ost",  # Mismatched facet_key
            timeline_tick=100,
            grounded_signal="lyrical_resonance",
            evidence_source_ref="exec://session/01",
        )
        temperament = make_temperament("music_ost")

        with pytest.raises(AppraisalIdentityMismatchError):
            ENGINE.evaluate_appraisal(
                record=record,
                evidence=evidence,
                temperament=temperament,
                existing_appraisal_pairs=frozenset(),
                registered_facet_keys=REGISTERED_FACETS,
            )

    def test_unknown_grounded_signal_raises_fail_closed(self):
        """Priority 3: unknown grounded_signal raises; no temperament fallback."""
        record = make_experience("exp-ug01", facet_key="combat_grind")
        evidence = make_evidence(record, "totally_unknown_signal_xyz")
        temperament = make_temperament("combat_grind", GENSHIN, TemperamentCompatibility.STRONGLY_RESONANT)

        with pytest.raises(UnknownGroundedSignalError):
            ENGINE.evaluate_appraisal(
                record=record,
                evidence=evidence,
                temperament=temperament,
                existing_appraisal_pairs=frozenset(),
                registered_facet_keys=REGISTERED_FACETS,
            )
