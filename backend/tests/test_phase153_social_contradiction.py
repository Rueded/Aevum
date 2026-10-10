"""
test_phase153_social_contradiction.py — Phase 15.3 Social Contradiction Arbiter Tests

Verifies all gate criteria for Phase 15.3:
1. DTO Immutability & Model Integrity (frozen=True, extra="forbid", zero float fields).
2. Gate Review Invariant: Tension != Contradiction != Falsehood.
   (Spatial commute tension and pop-culture slips carry is_genuine_contradiction=False).
3. Lock 6 (Anti-Compensatory Hallucination):
   forbidden_compensatory_assumptions explicitly prohibits inventing ungrounded bridge facts.
4. Comprehensive arbitration coverage:
   - GC-382: Benign dual-location consistency (BENIGN_INDEPENDENCE).
   - GC-383: Extreme daily commute physical tension (SPATIAL_TEMPORAL_TENSION).
   - GC-384: Pop-culture meme crossing (POP_CULTURE_MEME_CROSSING).
   - GC-381: World knowledge contradiction (WORLD_FACT_DISCREPANCY).
   - GC-392: Biographical statement tension (BIOGRAPHICAL_STATEMENT_TENSION).
   - GC-388: Biological hyperbole (ONTOLOGICAL_IMPOSSIBILITY).
5. Static AST Constitutional Boundary Audit (0 DB, 0 network, 0 LLM, 0 mutation authority).
"""

import ast
from pathlib import Path
import pytest
from pydantic import ValidationError

from app.reality.speech_act_models import (
    PragmaticInterpretation,
    SpeechActEvaluationContext,
    SpeechActKind,
)
from app.reality.epistemic_policy_models import (
    EpistemicPolicyContext,
    EpistemicTreatmentDecision,
    EpistemicTreatmentKind,
)
from app.reality.social_contradiction_models import (
    SocialArbiterContext,
    SocialDiscrepancyAnalysis,
    SocialDiscrepancyType,
    SocialRepairInquiryStrategy,
    TensionSeverity,
)
from app.reality.social_contradiction_arbiter import SocialContradictionArbiter


# ==============================================================================
# 1. DTO Immutability & Model Integrity Tests
# ==============================================================================


def test_social_discrepancy_type_all_six_members():
    """Verify all 6 SocialDiscrepancyType enum members exist and are distinct strings."""
    expected = {
        "BENIGN_INDEPENDENCE",
        "SPATIAL_TEMPORAL_TENSION",
        "WORLD_FACT_DISCREPANCY",
        "POP_CULTURE_MEME_CROSSING",
        "BIOGRAPHICAL_STATEMENT_TENSION",
        "ONTOLOGICAL_IMPOSSIBILITY",
    }
    actual = {m.value for m in SocialDiscrepancyType}
    assert actual == expected
    assert len(SocialDiscrepancyType) == 6


def test_tension_severity_all_five_members():
    """Verify all 5 TensionSeverity enum members exist."""
    expected = {"NONE", "MILD", "MODERATE", "HIGH", "CRITICAL"}
    actual = {m.value for m in TensionSeverity}
    assert actual == expected
    assert len(TensionSeverity) == 5


def test_social_repair_inquiry_strategy_all_five_members():
    """Verify all 5 SocialRepairInquiryStrategy enum members exist."""
    expected = {"NONE", "CASUAL_INQUIRY", "PLAYFUL_TEASE", "POLITE_CORRECTION", "EMPATHETIC_CHECK"}
    actual = {m.value for m in SocialRepairInquiryStrategy}
    assert actual == expected
    assert len(SocialRepairInquiryStrategy) == 5


def test_social_discrepancy_analysis_immutability():
    """Verify SocialDiscrepancyAnalysis is strictly immutable (frozen=True)."""
    analysis = SocialDiscrepancyAnalysis(
        discrepancy_type=SocialDiscrepancyType.BENIGN_INDEPENDENCE,
        severity=TensionSeverity.NONE,
        repair_strategy=SocialRepairInquiryStrategy.NONE,
        is_genuine_contradiction=False,
        inquiry_prompt_guidance="None",
        rationale="Consistent",
    )
    with pytest.raises(ValidationError):
        analysis.severity = TensionSeverity.HIGH  # type: ignore


def test_social_discrepancy_analysis_extra_fields_forbidden():
    """Verify SocialDiscrepancyAnalysis forbids unapproved extra fields."""
    with pytest.raises(ValidationError):
        SocialDiscrepancyAnalysis(
            discrepancy_type=SocialDiscrepancyType.BENIGN_INDEPENDENCE,
            severity=TensionSeverity.NONE,
            repair_strategy=SocialRepairInquiryStrategy.NONE,
            is_genuine_contradiction=False,
            inquiry_prompt_guidance="None",
            rationale="Consistent",
            hallucinated_bridge_fact="He was on holiday",  # type: ignore # FORBIDDEN
        )


def test_phase153_models_zero_float_fields():
    """Permanent Note A: Verify zero float fields exist across all Phase 15.3 models."""
    for model_cls in (SocialDiscrepancyAnalysis, SocialArbiterContext):
        for field_name, field_info in model_cls.model_fields.items():
            annotation_str = str(field_info.annotation)
            assert "float" not in annotation_str.lower(), (
                f"Model {model_cls.__name__} has forbidden float field: {field_name}"
            )


# ==============================================================================
# 2. Gate Watchpoint: Tension != Contradiction != Falsehood
# ==============================================================================


def test_tension_is_not_contradiction_nor_falsehood():
    """
    Gate Watchpoint: An extreme commute claim creates spatial-temporal tension,
    but is_genuine_contradiction MUST be False!
    """
    treatment_decision = EpistemicTreatmentDecision(
        treatment=EpistemicTreatmentKind.CLARIFY_INQUIRE,
        rationale="Spatial-temporal tension.",
        working_context_accept=False,
        requires_repair_inquiry=True,
    )
    context = SocialArbiterContext(
        user_text="I drive from KL to Penang every morning for an 8 AM class.",
        treatment_decision=treatment_decision,
        known_residence_location="Kuala Lumpur",
        known_study_location="Penang (USM)",
        daily_commute_claimed_km=720,
        daily_commute_roundtrip_hours=8,
        relationship_teasing_permitted=True,
    )
    analysis = SocialContradictionArbiter.arbitrate(context)

    assert analysis.discrepancy_type == SocialDiscrepancyType.SPATIAL_TEMPORAL_TENSION
    assert analysis.severity == TensionSeverity.CRITICAL
    # Crucial Gate Invariant:
    assert analysis.is_genuine_contradiction is False
    assert analysis.repair_strategy == SocialRepairInquiryStrategy.PLAYFUL_TEASE


# ==============================================================================
# 3. Lock 6 (Anti-Compensatory Hallucination) Tests
# ==============================================================================


def test_lock_6_anti_compensatory_assumptions_forbids_bridge_facts():
    """
    Lock 6: System must explicitly list forbidden bridge facts
    and must not invent excuses (e.g. online classes, dropped out).
    """
    treatment_decision = EpistemicTreatmentDecision(
        treatment=EpistemicTreatmentKind.CLARIFY_INQUIRE,
        rationale="Spatial tension.",
        working_context_accept=False,
        requires_repair_inquiry=True,
    )
    context = SocialArbiterContext(
        user_text="I drive from KL to Penang daily.",
        treatment_decision=treatment_decision,
        daily_commute_claimed_km=720,
    )
    analysis = SocialContradictionArbiter.arbitrate(context)

    # Must contain explicit prohibitions
    assert len(analysis.forbidden_compensatory_assumptions) >= 3
    forbidden_text = " ".join(analysis.forbidden_compensatory_assumptions).lower()
    assert "online" in forbidden_text
    assert "cancelled" in forbidden_text
    assert "lives on campus" in forbidden_text


# ==============================================================================
# 4. Comprehensive Golden Scenarios Arbitration Tests
# ==============================================================================


def test_gc_382_benign_dual_location_consistency():
    """GC-382: User lives in KL while Aevum studies in Penang -> BENIGN_INDEPENDENCE."""
    treatment_decision = EpistemicTreatmentDecision(
        treatment=EpistemicTreatmentKind.ACCEPT_SOCIAL,
        rationale="Consistent personal claim.",
        working_context_accept=True,
    )
    context = SocialArbiterContext(
        user_text="I live in KL.",
        treatment_decision=treatment_decision,
        known_residence_location="Kuala Lumpur",
        known_study_location="Penang (USM)",
    )
    analysis = SocialContradictionArbiter.arbitrate(context)

    assert analysis.discrepancy_type == SocialDiscrepancyType.BENIGN_INDEPENDENCE
    assert analysis.severity == TensionSeverity.NONE
    assert analysis.is_genuine_contradiction is False
    assert analysis.repair_strategy == SocialRepairInquiryStrategy.NONE


def test_gc_384_pop_culture_meme_crossing():
    """GC-384: Pop-culture Character Crossing (昔涟 in Genshin) -> POP_CULTURE_MEME_CROSSING."""
    treatment_decision = EpistemicTreatmentDecision(
        treatment=EpistemicTreatmentKind.BANTER_TEASE,
        rationale="Pop-culture meme.",
        working_context_accept=True,
        teasing_tone_recommended=True,
    )
    context = SocialArbiterContext(
        user_text="原神里的昔涟真好看。",
        treatment_decision=treatment_decision,
        target_universe="Genshin Impact",
        actual_universe="Honkai: Star Rail",
        relationship_teasing_permitted=True,
    )
    analysis = SocialContradictionArbiter.arbitrate(context)

    assert analysis.discrepancy_type == SocialDiscrepancyType.POP_CULTURE_MEME_CROSSING
    assert analysis.severity == TensionSeverity.MILD
    assert analysis.is_genuine_contradiction is False
    assert analysis.repair_strategy == SocialRepairInquiryStrategy.PLAYFUL_TEASE
    assert "teasing" in analysis.inquiry_prompt_guidance.lower()


def test_gc_381_world_fact_discrepancy():
    """GC-381: World Knowledge Direct Contradiction -> WORLD_FACT_DISCREPANCY."""
    treatment_decision = EpistemicTreatmentDecision(
        treatment=EpistemicTreatmentKind.WORLD_CONTRADICTION,
        rationale="World contradiction.",
        working_context_accept=False,
        requires_repair_inquiry=True,
    )
    context = SocialArbiterContext(
        user_text="USM is located in Kuala Lumpur.",
        treatment_decision=treatment_decision,
    )
    analysis = SocialContradictionArbiter.arbitrate(context)

    assert analysis.discrepancy_type == SocialDiscrepancyType.WORLD_FACT_DISCREPANCY
    assert analysis.severity == TensionSeverity.MODERATE
    assert analysis.is_genuine_contradiction is True  # Mutually exclusive geographical fact
    assert analysis.repair_strategy == SocialRepairInquiryStrategy.POLITE_CORRECTION


def test_gc_392_biographical_statement_tension():
    """GC-392: Contradictory User Biography -> BIOGRAPHICAL_STATEMENT_TENSION."""
    treatment_decision = EpistemicTreatmentDecision(
        treatment=EpistemicTreatmentKind.CLARIFY_INQUIRE,
        rationale="Biography discrepancy.",
        working_context_accept=False,
        requires_repair_inquiry=True,
    )
    context = SocialArbiterContext(
        user_text="I've never worked in a kitchen.",
        treatment_decision=treatment_decision,
    )
    analysis = SocialContradictionArbiter.arbitrate(context)

    assert analysis.discrepancy_type == SocialDiscrepancyType.BIOGRAPHICAL_STATEMENT_TENSION
    assert analysis.severity == TensionSeverity.MODERATE
    assert analysis.is_genuine_contradiction is False
    assert analysis.repair_strategy == SocialRepairInquiryStrategy.CASUAL_INQUIRY


def test_gc_388_ontological_impossibility_hyperbole():
    """GC-388: Biological Extreme Hyperbole -> ONTOLOGICAL_IMPOSSIBILITY."""
    treatment_decision = EpistemicTreatmentDecision(
        treatment=EpistemicTreatmentKind.DISCARD_LITERAL_HYPERBOLE,
        rationale="Hyperbolic claim.",
        working_context_accept=False,
    )
    context = SocialArbiterContext(
        user_text="I haven't slept in three weeks.",
        treatment_decision=treatment_decision,
    )
    analysis = SocialContradictionArbiter.arbitrate(context)

    assert analysis.discrepancy_type == SocialDiscrepancyType.ONTOLOGICAL_IMPOSSIBILITY
    assert analysis.severity == TensionSeverity.MODERATE
    assert analysis.is_genuine_contradiction is False
    assert analysis.repair_strategy == SocialRepairInquiryStrategy.EMPATHETIC_CHECK


# ==============================================================================
# 5. Pure Static AST Constitutional Boundary Audit
# ==============================================================================


def test_pure_static_ast_boundary_audit_phase153():
    """
    Audit social_contradiction_models.py and social_contradiction_arbiter.py via AST:
    - 0 database imports / operations
    - 0 network / HTTP imports (requests, httpx, urllib, aiohttp)
    - 0 LLM client imports (openai, anthropic, google)
    - 0 mutation authority tokens or set_fact calls
    - 0 float type annotations in social_contradiction_models.py
    """
    repo_root = Path(__file__).resolve().parent.parent
    target_files = [
        repo_root / "app" / "reality" / "social_contradiction_models.py",
        repo_root / "app" / "reality" / "social_contradiction_arbiter.py",
    ]

    forbidden_imports = {
        "sqlite3", "sqlalchemy", "databases", "orm",
        "requests", "httpx", "urllib", "aiohttp",
        "openai", "anthropic", "google.generativeai",
    }
    forbidden_call_names = {
        "set_fact", "PromotionAuthorizationToken", "execute", "commit",
    }

    for file_path in target_files:
        assert file_path.exists(), f"File not found: {file_path}"
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in forbidden_imports:
                        assert forbidden not in alias.name, (
                            f"Forbidden import '{alias.name}' in {file_path.name}:{node.lineno}"
                        )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for forbidden in forbidden_imports:
                    assert forbidden not in module, (
                        f"Forbidden import from '{module}' in {file_path.name}:{node.lineno}"
                    )
            elif isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                for forbidden_call in forbidden_call_names:
                    assert func_name != forbidden_call, (
                        f"Forbidden function call '{func_name}' in {file_path.name}:{node.lineno}"
                    )
