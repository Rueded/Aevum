"""Unit tests for Phase 8B.2 World Academic Calendars and Temporal Rules.

Verifies:
1. Typed constraint payloads: DurationBoundValue, CalendarWindowValue, AgeWindowValue, StagePrecedenceValue.
2. TemporalRuleItem schema validation, frozen immutability, extra="forbid".
3. TemporalRuleScope enforcement (avoiding global hardcoded constants).
4. TemporalRuleRegistry querying, filtering, and deterministic sorting.
5. Backward compatibility mirror to WorldKnowledgeRegistry (KnowledgeKind.TEMPORAL_RULE).
6. Baseline seed rules verification (SPM age, STPM, Matrikulasi, Foundation, Diploma, Degree, USM intake, Stage precedences).
7. Invariant F (World Temporal Rule != Personal Fact):
   - Rule lookup/evaluation produces zero mutations to CharacterCore.
   - Institutional duration or calendar rules are never written directly into CharacterCore.
   - Temporal rules carry no FactAuthority or canonical reality status.
8. Advisory vs Hard rejection semantics (is_hard_rejection=False for typical durations/intakes, True for absolute biological/stage precedence).
9. AST Boundary Audit: Zero set_fact, zero tokens, zero RBE, zero network imports in temporal_rules.py.
"""

from __future__ import annotations

import ast
import pathlib
import pytest

from app.character.core_models import CharacterCore
from app.reality.models import FactAuthority, FactSource, FactStatus
from app.reality.temporal_models import LifeStage
from app.reality.temporal_rules import (
    AgeWindowValue,
    CalendarWindowValue,
    DurationBoundValue,
    StagePrecedenceValue,
    TemporalConstraintType,
    TemporalRuleItem,
    TemporalRuleRegistry,
    TemporalRuleScope,
)
from app.reality.world_knowledge import KnowledgeKind, WorldKnowledgeRegistry


class TestPhase8B2TemporalRules:
    """Comprehensive test suite for Phase 8B.2 temporal rules and calendars."""

    # -------------------------------------------------------------------------
    # 1. Typed Constraint Payloads & Invariant Validations
    # -------------------------------------------------------------------------
    def test_duration_bound_value_valid(self):
        """Construct valid DurationBoundValue with min/max bounds."""
        d = DurationBoundValue(min_years=1.5, max_years=2.0, min_months=18, max_months=24, typical_years=1.5)
        assert d.min_years == 1.5
        assert d.max_years == 2.0
        assert d.typical_years == 1.5

    def test_duration_bound_value_invalid_years_rejected(self):
        """min_years > max_years raises ValueError."""
        with pytest.raises(ValueError, match="min_years.*cannot be greater than max_years"):
            DurationBoundValue(min_years=3.0, max_years=2.0)

    def test_duration_bound_value_invalid_months_rejected(self):
        """min_months > max_months raises ValueError."""
        with pytest.raises(ValueError, match="min_months.*cannot be greater than max_months"):
            DurationBoundValue(min_months=36, max_months=24)

    def test_calendar_window_value_valid(self):
        """Construct valid CalendarWindowValue with intake and semester info."""
        cal = CalendarWindowValue(
            intake_months=(10,),
            academic_year_start_month=10,
            academic_year_end_month=7,
            semester_count=2,
        )
        assert cal.intake_months == (10,)
        assert cal.academic_year_start_month == 10
        assert cal.semester_count == 2

    def test_calendar_window_invalid_month_rejected(self):
        """Invalid month (<1 or >12) raises ValueError."""
        with pytest.raises(ValueError, match="must be between 1 and 12"):
            CalendarWindowValue(intake_months=(13,))

    def test_age_window_value_valid(self):
        """Construct valid AgeWindowValue."""
        age = AgeWindowValue(typical_age=17, min_age=16, max_age=19)
        assert age.typical_age == 17
        assert age.min_age == 16
        assert age.max_age == 19

    def test_age_window_invalid_bounds_rejected(self):
        """min_age > max_age raises ValueError."""
        with pytest.raises(ValueError, match="min_age.*cannot be greater than max_age"):
            AgeWindowValue(min_age=20, max_age=18)

    def test_stage_precedence_value_valid(self):
        """Construct valid StagePrecedenceValue."""
        prec = StagePrecedenceValue(
            required_preceding_stage=LifeStage.PRE_UNIVERSITY,
            target_stage=LifeStage.UNDERGRADUATE,
            minimum_gap_months=0,
            maximum_gap_months=48,
        )
        assert prec.required_preceding_stage == LifeStage.PRE_UNIVERSITY
        assert prec.target_stage == LifeStage.UNDERGRADUATE
        assert prec.maximum_gap_months == 48

    # -------------------------------------------------------------------------
    # 2. TemporalRuleItem Schema & Immutability
    # -------------------------------------------------------------------------
    def test_temporal_rule_item_valid_construction(self):
        """Construct a valid TemporalRuleItem."""
        rule = TemporalRuleItem(
            rule_id="RULE_TEST_CUSTOM",
            domain="education",
            subject="test_pathway",
            constraint_type=TemporalConstraintType.DURATION_BOUND,
            scope=TemporalRuleScope.PATHWAY_SPECIFIC,
            scope_target="TEST",
            constraint_value=DurationBoundValue(min_years=1.0, max_years=2.0),
            description="Test pathway rule.",
            provenance_source="TEST_FRAMEWORK",
            is_hard_rejection=False,
        )
        assert rule.rule_id == "RULE_TEST_CUSTOM"
        assert rule.scope == TemporalRuleScope.PATHWAY_SPECIFIC
        assert rule.is_hard_rejection is False

    def test_temporal_rule_item_immutability(self):
        """TemporalRuleItem is frozen; attribute mutation raises ValidationError."""
        from pydantic import ValidationError

        rule = TemporalRuleItem(
            rule_id="RULE_TEST_IMMUT",
            subject="test",
            constraint_type=TemporalConstraintType.DURATION_BOUND,
            scope=TemporalRuleScope.GENERAL_ACADEMIC,
            constraint_value=DurationBoundValue(min_years=1.0),
        )
        with pytest.raises(ValidationError, match="Instance is frozen"):
            rule.subject = "altered"  # type: ignore

    def test_temporal_rule_item_extra_fields_forbidden(self):
        """TemporalRuleItem rejects undeclared extra fields."""
        with pytest.raises(ValueError, match="Extra inputs are not permitted"):
            TemporalRuleItem(
                rule_id="RULE_EXTRA",
                subject="test",
                constraint_type=TemporalConstraintType.DURATION_BOUND,
                scope=TemporalRuleScope.GENERAL_ACADEMIC,
                constraint_value=DurationBoundValue(min_years=1.0),
                arbitrary_confidence=0.99,  # type: ignore - VIOLATION!
            )

    # -------------------------------------------------------------------------
    # 3. TemporalRuleRegistry Querying & Filtering
    # -------------------------------------------------------------------------
    def test_registry_contains_seed_rules(self):
        """Verify registry automatically loads baseline seed rules."""
        assert TemporalRuleRegistry.count() >= 10
        rule = TemporalRuleRegistry.get("RULE_MY_STPM_DURATION")
        assert rule is not None
        assert rule.subject == "stpm"
        assert rule.scope == TemporalRuleScope.PATHWAY_SPECIFIC

    def test_registry_filtering_by_scope(self):
        """Filter rules by TemporalRuleScope."""
        pathway_rules = TemporalRuleRegistry.find_rules(scope=TemporalRuleScope.PATHWAY_SPECIFIC)
        assert len(pathway_rules) >= 4
        subjects = {r.subject for r in pathway_rules}
        assert "stpm" in subjects
        assert "matrikulasi" in subjects
        assert "foundation" in subjects
        assert "diploma" in subjects

    def test_registry_filtering_by_constraint_type(self):
        """Filter rules by TemporalConstraintType."""
        duration_rules = TemporalRuleRegistry.find_rules(constraint_type=TemporalConstraintType.DURATION_BOUND)
        assert len(duration_rules) >= 5
        precedence_rules = TemporalRuleRegistry.find_rules(constraint_type=TemporalConstraintType.STAGE_PRECEDENCE)
        assert len(precedence_rules) >= 2

    def test_registry_mirror_to_world_knowledge(self):
        """Verify registered temporal rule is mirrored to WorldKnowledgeRegistry."""
        wk_item = WorldKnowledgeRegistry.lookup("temporal.rule.rule_my_stpm_duration")
        assert wk_item is not None
        assert wk_item.kind == KnowledgeKind.TEMPORAL_RULE
        assert wk_item.domain_category == "education"
        assert "min_years" in wk_item.value["constraint_value"]

    # -------------------------------------------------------------------------
    # 4. Baseline Educational Rules Semantics
    # -------------------------------------------------------------------------
    def test_spm_age_rule_semantics(self):
        """Verify SPM rule is an advisory prior, not a hard rejection."""
        rule = TemporalRuleRegistry.get("RULE_MY_SPM_AGE")
        assert rule is not None
        assert rule.constraint_type == TemporalConstraintType.TYPICAL_AGE_WINDOW
        assert rule.is_hard_rejection is False
        assert isinstance(rule.constraint_value, AgeWindowValue)
        assert rule.constraint_value.typical_age == 17
        assert rule.constraint_value.min_age == 16

    def test_stpm_duration_rule_semantics(self):
        """Verify STPM duration rule bounds [1.5, 2.0] years."""
        rule = TemporalRuleRegistry.get("RULE_MY_STPM_DURATION")
        assert rule is not None
        assert isinstance(rule.constraint_value, DurationBoundValue)
        assert rule.constraint_value.min_years == 1.5
        assert rule.constraint_value.max_years == 2.0
        assert rule.constraint_value.typical_years == 1.5

    def test_usm_intake_window_semantics(self):
        """Verify USM intake rule represents advisory institutional intake window."""
        rule = TemporalRuleRegistry.get("RULE_USM_INTAKE_WINDOW")
        assert rule is not None
        assert rule.scope == TemporalRuleScope.INSTITUTION_SPECIFIC
        assert rule.scope_target == "world.usm.main_campus"
        assert isinstance(rule.constraint_value, CalendarWindowValue)
        assert rule.constraint_value.intake_months == (10,)
        # Must be advisory prior, not absolute universal truth
        assert rule.is_hard_rejection is False

    def test_stage_precedence_semantics(self):
        """Verify stage precedence rules are hard requirements."""
        rule = TemporalRuleRegistry.get("RULE_PRECEDENCE_PRE_U_TO_UNDERGRAD")
        assert rule is not None
        assert rule.is_hard_rejection is True
        assert isinstance(rule.constraint_value, StagePrecedenceValue)
        assert rule.constraint_value.required_preceding_stage == LifeStage.PRE_UNIVERSITY
        assert rule.constraint_value.target_stage == LifeStage.UNDERGRADUATE

    # -------------------------------------------------------------------------
    # 5. Invariant F: World Temporal Rule != Personal Fact
    # -------------------------------------------------------------------------
    def test_invariant_f_rule_lookup_produces_zero_core_mutations(self):
        """Evaluating or looking up a world temporal rule leaves CharacterCore completely untouched."""
        core = CharacterCore(character_id="aevum")
        initial_facts_count = len(core.facts)

        # Query and inspect rules
        rules = TemporalRuleRegistry.find_rules(domain="education")
        assert len(rules) > 0
        rule = TemporalRuleRegistry.get("RULE_MY_STPM_DURATION")
        assert rule is not None

        # Core facts must remain 100% untouched
        assert len(core.facts) == initial_facts_count
        assert core.get_fact_value("education.stpm_duration") is None
        assert core.get_fact_value("education.usm_intake") is None

    def test_invariant_f_world_rule_cannot_be_injected_as_canonical_core_fact(self):
        """World rules are constraints for TCG; they do not carry FactAuthority or FactStatus."""
        rule = TemporalRuleRegistry.get("RULE_MY_STPM_DURATION")
        assert rule is not None

        # TemporalRuleItem has no FactAuthority and no FactStatus
        assert not hasattr(rule, "authority")
        assert not hasattr(rule, "status")

        # World rule value is an evaluative bound, not personal reality
        assert isinstance(rule.constraint_value, DurationBoundValue)
        assert rule.constraint_value.min_years == 1.5

    # -------------------------------------------------------------------------
    # 6. Lock 1 & Lock 5: Cross-Pathway Applicability & Precedence Tests
    # -------------------------------------------------------------------------
    def test_four_canonical_pathways_valid_and_distinguishable(self):
        """Verify that all 4 canonical pathways (STPM, Matrikulasi, Foundation, Diploma)

        are correctly scoped and evaluated without cross-pathway rejection.
        Specifically verifies:
        - STPM -> Undergraduate is scoped to PRE_U_PATHWAYS
        - Matrikulasi -> Undergraduate is scoped to PRE_U_PATHWAYS
        - Foundation -> Undergraduate is scoped to PRE_U_PATHWAYS
        - Diploma -> Undergraduate is scoped to DIPLOMA
        - Diploma -> Undergraduate is NOT rejected by Pre-U precedence rules.
        """
        rule_pre_u = TemporalRuleRegistry.get("RULE_PRECEDENCE_PRE_U_TO_UNDERGRAD")
        rule_diploma = TemporalRuleRegistry.get("RULE_PRECEDENCE_DIPLOMA_TO_UNDERGRAD")
        rule_sec_to_pre_u = TemporalRuleRegistry.get("RULE_PRECEDENCE_SECONDARY_TO_PRE_U")
        rule_sec_to_dip = TemporalRuleRegistry.get("RULE_PRECEDENCE_SECONDARY_TO_DIPLOMA")

        assert rule_pre_u is not None
        assert rule_diploma is not None
        assert rule_sec_to_pre_u is not None
        assert rule_sec_to_dip is not None

        # 1. STPM Pathway
        assert rule_sec_to_pre_u.applies_to_pathway("STPM") is True
        assert rule_pre_u.applies_to_pathway("STPM") is True
        assert rule_diploma.applies_to_pathway("STPM") is False
        assert rule_sec_to_dip.applies_to_pathway("STPM") is False

        # 2. Matrikulasi Pathway
        assert rule_sec_to_pre_u.applies_to_pathway("MATRIKULASI") is True
        assert rule_pre_u.applies_to_pathway("MATRIKULASI") is True
        assert rule_diploma.applies_to_pathway("MATRIKULASI") is False
        assert rule_sec_to_dip.applies_to_pathway("MATRIKULASI") is False

        # 3. Foundation Pathway
        assert rule_sec_to_pre_u.applies_to_pathway("FOUNDATION") is True
        assert rule_pre_u.applies_to_pathway("FOUNDATION") is True
        assert rule_diploma.applies_to_pathway("FOUNDATION") is False
        assert rule_sec_to_dip.applies_to_pathway("FOUNDATION") is False

        # 4. Diploma Pathway
        assert rule_sec_to_dip.applies_to_pathway("DIPLOMA") is True
        assert rule_diploma.applies_to_pathway("DIPLOMA") is True
        # Critical Lock 1 & 5 Assertion: Pre-U rule must NOT apply to Diploma
        assert rule_pre_u.applies_to_pathway("DIPLOMA") is False
        assert rule_sec_to_pre_u.applies_to_pathway("DIPLOMA") is False

    def test_diploma_stage_precedence_properties(self):
        """Verify Diploma precedence rules require LifeStage.DIPLOMA and LifeStage.SECONDARY_EDUCATION."""
        rule_sec_to_dip = TemporalRuleRegistry.get("RULE_PRECEDENCE_SECONDARY_TO_DIPLOMA")
        assert rule_sec_to_dip is not None
        assert isinstance(rule_sec_to_dip.constraint_value, StagePrecedenceValue)
        assert rule_sec_to_dip.constraint_value.required_preceding_stage == LifeStage.SECONDARY_EDUCATION
        assert rule_sec_to_dip.constraint_value.target_stage == LifeStage.DIPLOMA
        assert rule_sec_to_dip.constraint_value.applicable_pathways == ("DIPLOMA",)
        assert rule_sec_to_dip.is_hard_rejection is True

        rule_dip_to_ug = TemporalRuleRegistry.get("RULE_PRECEDENCE_DIPLOMA_TO_UNDERGRAD")
        assert rule_dip_to_ug is not None
        assert isinstance(rule_dip_to_ug.constraint_value, StagePrecedenceValue)
        assert rule_dip_to_ug.constraint_value.required_preceding_stage == LifeStage.DIPLOMA
        assert rule_dip_to_ug.constraint_value.target_stage == LifeStage.UNDERGRADUATE
        assert rule_dip_to_ug.constraint_value.applicable_pathways == ("DIPLOMA",)
        assert rule_dip_to_ug.is_hard_rejection is True

    # -------------------------------------------------------------------------
    # 7. Lock 2: World Rule Registry Authority (No Dual Store)
    # -------------------------------------------------------------------------
    def test_temporal_rule_registry_delegates_to_world_knowledge_registry(self):
        """TemporalRuleRegistry must be an adapter/view over WorldKnowledgeRegistry without private dual store."""
        # Check canonical world knowledge key
        wk_item = WorldKnowledgeRegistry.lookup("world.temporal.rule.rule_precedence_diploma_to_undergrad")
        assert wk_item is not None
        assert wk_item.kind == KnowledgeKind.TEMPORAL_RULE
        assert wk_item.value["rule_id"] == "RULE_PRECEDENCE_DIPLOMA_TO_UNDERGRAD"

        # Lookup via TemporalRuleRegistry returns typed view of same canonical data
        rule = TemporalRuleRegistry.get("RULE_PRECEDENCE_DIPLOMA_TO_UNDERGRAD")
        assert rule is not None
        assert rule.rule_id == "RULE_PRECEDENCE_DIPLOMA_TO_UNDERGRAD"
        assert isinstance(rule.constraint_value, StagePrecedenceValue)

    # -------------------------------------------------------------------------
    # 8. Lock 3 & Lock 4: Hard Constraint Semantics & UNKNOWN Handling
    # -------------------------------------------------------------------------
    def test_unknown_pathway_does_not_match_pathway_scoped_rules(self):
        """UNKNOWN pathway (None) does NOT match pathway-scoped rules (UNKNOWN != wildcard, UNKNOWN != false)."""
        rule_pre_u = TemporalRuleRegistry.get("RULE_PRECEDENCE_PRE_U_TO_UNDERGRAD")
        assert rule_pre_u is not None

        # When pathway is unknown (None), pathway-scoped rule does not apply
        assert rule_pre_u.applies_to_pathway(None) is False
        assert rule_pre_u.applies_to_pathway("") is False

        # When pathway is arbitrary unrecognized string, it also does not match
        assert rule_pre_u.applies_to_pathway("UNKNOWN_PATHWAY") is False

    # -------------------------------------------------------------------------
    # 9. Lock 6: Institution Scope
    # -------------------------------------------------------------------------
    def test_institution_scope_matching(self):
        """Verify institution-specific rules do NOT match unrecorded (None) or non-matching institutions."""
        rule_usm = TemporalRuleRegistry.get("RULE_USM_INTAKE_WINDOW")
        assert rule_usm is not None
        assert rule_usm.scope == TemporalRuleScope.INSTITUTION_SPECIFIC

        # Matches designated institution
        assert rule_usm.applies_to_institution("world.usm.main_campus") is True
        assert rule_usm.applies_to_institution("WORLD.USM.MAIN_CAMPUS") is True

        # Rejects other institutions
        assert rule_usm.applies_to_institution("world.um.main_campus") is False
        assert rule_usm.applies_to_institution("world.ukm.main_campus") is False

        # Rejects unrecorded / unknown institution (Lock 6)
        assert rule_usm.applies_to_institution(None) is False
        assert rule_usm.applies_to_institution("") is False

        # General academic rules apply regardless of institution
        rule_degree = TemporalRuleRegistry.get("RULE_MY_DEGREE_DURATION")
        assert rule_degree is not None
        assert rule_degree.scope == TemporalRuleScope.GENERAL_ACADEMIC
        assert rule_degree.applies_to_institution("world.usm.main_campus") is True
        assert rule_degree.applies_to_institution("world.um.main_campus") is True
        assert rule_degree.applies_to_institution(None) is True

    # -------------------------------------------------------------------------
    # 6. AST Boundary Audit
    # -------------------------------------------------------------------------
    def test_ast_audit_temporal_rules(self):
        """Verify temporal_rules.py contains 0 network imports, 0 DB calls, 0 RBE, 0 set_fact."""
        target_path = pathlib.Path(__file__).parent.parent / "app" / "reality" / "temporal_rules.py"
        assert target_path.exists(), "temporal_rules.py must exist"

        content = target_path.read_text(encoding="utf-8")

        # 1. No RealityBeliefEngine
        assert "RealityBeliefEngine" not in content

        # 2. No set_fact
        assert "set_fact" not in content

        # 3. No token minting
        assert "PromotionAuthorizationToken" not in content

        # 4. No network client imports
        forbidden_modules = {"requests", "httpx", "aiohttp", "urllib", "urllib3", "sqlalchemy"}
        tree = ast.parse(content, filename=str(target_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod_root = alias.name.split(".")[0]
                    assert mod_root not in forbidden_modules, f"Forbidden import: {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    mod_root = node.module.split(".")[0]
                    assert mod_root not in forbidden_modules, f"Forbidden import from: {node.module}"
