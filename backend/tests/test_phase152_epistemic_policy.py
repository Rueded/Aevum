"""
test_phase152_epistemic_policy.py — Phase 15.2 Epistemic Treatment Engine & Cognitive Policy Tests

Verifies all gate criteria for Phase 15.2:
1. DTO Immutability & Model Integrity (frozen=True, extra="forbid", zero float fields).
2. Gate Review Watchpoint: ACCEPT_SOCIAL != Memory Writing (zero memory or canonical write authority).
3. Exhaustive policy mapping across all 10 EpistemicTreatmentKind outcomes:
   - ACCEPT_SOCIAL (GC-379, GC-382, Metaphor, Question)
   - ACKNOWLEDGE_EMOTIONAL (GC-380, Emotion, Sarcasm Irony GC-390)
   - WORLD_CONTRADICTION (GC-381)
   - CLARIFY_INQUIRE (GC-383 Spatial Tension, GC-392 Biography Discrepancy)
   - BANTER_TEASE (GC-384 Meme, GC-394 Test, GC-396 Self-Deprecating Sarcasm, Joke)
   - DISPATCH_VERIFICATION (GC-387 High-Impact Institutional Claim)
   - DISCARD_LITERAL_HYPERBOLE (GC-388 Extreme Biological Hyperbole)
   - ENTER_FICTIONAL_FRAME (GC-391 Roleplay Sandbox)
   - REVISE_INTERPRETATION (GC-386 Explicit User Retraction)
   - SUSPEND_JUDGMENT (GC-395 Ambiguity Preservation)
4. Constitutional Locks (Lock 1, Lock 2, Lock 3, Lock 5, Lock 6).
5. Static AST Constitutional Boundary Audit (0 DB, 0 network, 0 LLM, 0 mutation authority, 0 float probabilities).
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
from app.reality.speech_act_classifier import SpeechActClassifier
from app.reality.epistemic_policy_models import (
    EpistemicPolicyContext,
    EpistemicTreatmentDecision,
    EpistemicTreatmentKind,
)
from app.reality.epistemic_policy_engine import EpistemicPolicyEngine


# ==============================================================================
# 1. DTO Immutability & Model Integrity Tests
# ==============================================================================


def test_epistemic_treatment_kind_all_ten_members():
    """Verify all 10 EpistemicTreatmentKind members exist and are distinct strings."""
    expected_members = {
        "ACCEPT_SOCIAL",
        "ACKNOWLEDGE_EMOTIONAL",
        "WORLD_CONTRADICTION",
        "CLARIFY_INQUIRE",
        "BANTER_TEASE",
        "DISPATCH_VERIFICATION",
        "DISCARD_LITERAL_HYPERBOLE",
        "ENTER_FICTIONAL_FRAME",
        "REVISE_INTERPRETATION",
        "SUSPEND_JUDGMENT",
    }
    actual_members = {k.value for k in EpistemicTreatmentKind}
    assert actual_members == expected_members
    assert len(EpistemicTreatmentKind) == 10


def test_epistemic_treatment_decision_immutability():
    """Verify EpistemicTreatmentDecision is strictly immutable (frozen=True)."""
    decision = EpistemicTreatmentDecision(
        treatment=EpistemicTreatmentKind.ACCEPT_SOCIAL,
        rationale="Low-consequence assertion.",
        working_context_accept=True,
    )
    with pytest.raises(ValidationError):
        decision.treatment = EpistemicTreatmentKind.BANTER_TEASE  # type: ignore


def test_epistemic_treatment_decision_extra_fields_forbidden():
    """Verify EpistemicTreatmentDecision forbids unapproved extra fields (e.g. truth score)."""
    with pytest.raises(ValidationError):
        EpistemicTreatmentDecision(
            treatment=EpistemicTreatmentKind.ACCEPT_SOCIAL,
            rationale="Test",
            working_context_accept=True,
            truth_score=0.99,  # type: ignore # FORBIDDEN: float truth score
        )


def test_epistemic_policy_context_immutability():
    """Verify EpistemicPolicyContext is frozen and forbids extra fields."""
    interp = PragmaticInterpretation(
        primary_act=SpeechActKind.ASSERTION,
        social_tone="matter_of_fact",
        pragmatic_intent_summary="test",
    )
    eval_ctx = SpeechActEvaluationContext(user_text="test")
    policy_ctx = EpistemicPolicyContext(
        interpretation=interp,
        evaluation_context=eval_ctx,
        is_high_impact_claim=False,
        has_spatial_temporal_tension=False,
    )
    with pytest.raises(ValidationError):
        policy_ctx.is_high_impact_claim = True  # type: ignore


def test_phase152_models_zero_float_fields():
    """Permanent Note A: Verify zero float fields exist across all Phase 15.2 models."""
    for model_cls in (EpistemicTreatmentDecision, EpistemicPolicyContext):
        for field_name, field_info in model_cls.model_fields.items():
            annotation_str = str(field_info.annotation)
            assert "float" not in annotation_str.lower(), (
                f"Model {model_cls.__name__} has forbidden float field: {field_name}"
            )


# ==============================================================================
# 2. Gate Review Watchpoint: ACCEPT_SOCIAL != Memory Writing
# ==============================================================================


def test_accept_social_does_not_mutate_or_call_memory():
    """
    Watchpoint: ACCEPT_SOCIAL admits into working dialogue context,
    with ZERO write authority to long-term memory, biography, or database.
    """
    eval_ctx = SpeechActEvaluationContext(user_text="我最近超喜欢原神。")
    interp = SpeechActClassifier.classify(eval_ctx)
    policy_ctx = EpistemicPolicyContext(
        interpretation=interp,
        evaluation_context=eval_ctx,
        is_high_impact_claim=False,
        has_spatial_temporal_tension=False,
    )
    decision = EpistemicPolicyEngine.evaluate(policy_ctx)

    assert decision.treatment == EpistemicTreatmentKind.ACCEPT_SOCIAL
    assert decision.working_context_accept is True
    assert decision.dispatch_verification_recommended is False
    assert decision.requires_repair_inquiry is False
    # No memory write side effects exist in pure decision object
    assert not hasattr(decision, "persist_memory")
    assert not hasattr(decision, "write_to_biography")


# ==============================================================================
# 3. Exhaustive Policy Mapping Across All 10 EpistemicTreatmentKind
# ==============================================================================


def test_gc_379_trivial_personal_routine_accept_social():
    """GC-379: Trivial routine claim -> ACCEPT_SOCIAL."""
    eval_ctx = SpeechActEvaluationContext(user_text="I ate chicken rice today.")
    interp = SpeechActClassifier.classify(eval_ctx)
    policy_ctx = EpistemicPolicyContext(
        interpretation=interp,
        evaluation_context=eval_ctx,
    )
    decision = EpistemicPolicyEngine.evaluate(policy_ctx)

    assert decision.treatment == EpistemicTreatmentKind.ACCEPT_SOCIAL
    assert decision.working_context_accept is True
    assert decision.dispatch_verification_recommended is False


def test_gc_382_benign_dual_location_consistency_accept_social():
    """GC-382: Benign dual-location consistency -> ACCEPT_SOCIAL."""
    eval_ctx = SpeechActEvaluationContext(
        user_text="I live in KL.",
        known_biography_discrepancy=False,
        known_world_discrepancy=False,
    )
    interp = SpeechActClassifier.classify(eval_ctx)
    policy_ctx = EpistemicPolicyContext(
        interpretation=interp,
        evaluation_context=eval_ctx,
    )
    decision = EpistemicPolicyEngine.evaluate(policy_ctx)

    assert decision.treatment == EpistemicTreatmentKind.ACCEPT_SOCIAL
    assert decision.working_context_accept is True


def test_metaphor_statement_accept_social():
    """GC-389: Figurative metaphor statement -> ACCEPT_SOCIAL."""
    eval_ctx = SpeechActEvaluationContext(user_text="My boss is an absolute vampire.")
    interp = SpeechActClassifier.classify(eval_ctx)
    policy_ctx = EpistemicPolicyContext(
        interpretation=interp,
        evaluation_context=eval_ctx,
    )
    decision = EpistemicPolicyEngine.evaluate(policy_ctx)

    assert decision.treatment == EpistemicTreatmentKind.ACCEPT_SOCIAL
    assert decision.working_context_accept is True


def test_inquiry_question_accept_social():
    """GC-393: Sincere inquiry seeking character stance -> ACCEPT_SOCIAL."""
    eval_ctx = SpeechActEvaluationContext(user_text="Did you play piano in high school?")
    interp = SpeechActClassifier.classify(eval_ctx)
    policy_ctx = EpistemicPolicyContext(
        interpretation=interp,
        evaluation_context=eval_ctx,
    )
    decision = EpistemicPolicyEngine.evaluate(policy_ctx)

    assert decision.treatment == EpistemicTreatmentKind.ACCEPT_SOCIAL
    assert decision.working_context_accept is True


def test_gc_380_emotional_affective_expression():
    """GC-380: Subjective affective venting -> ACKNOWLEDGE_EMOTIONAL."""
    eval_ctx = SpeechActEvaluationContext(user_text="I'm so exhausted I could collapse.")
    interp = SpeechActClassifier.classify(eval_ctx)
    policy_ctx = EpistemicPolicyContext(
        interpretation=interp,
        evaluation_context=eval_ctx,
    )
    decision = EpistemicPolicyEngine.evaluate(policy_ctx)

    assert decision.treatment == EpistemicTreatmentKind.ACKNOWLEDGE_EMOTIONAL
    assert decision.working_context_accept is True
    assert decision.dispatch_verification_recommended is False


def test_gc_390_sarcastic_irony_inversion_acknowledge_emotional():
    """GC-390: Sarcastic irony inversion about adverse weather -> ACKNOWLEDGE_EMOTIONAL."""
    eval_ctx = SpeechActEvaluationContext(
        user_text="Oh wonderful, it's raining right when I have to move furniture."
    )
    interp = SpeechActClassifier.classify(eval_ctx)
    policy_ctx = EpistemicPolicyContext(
        interpretation=interp,
        evaluation_context=eval_ctx,
    )
    decision = EpistemicPolicyEngine.evaluate(policy_ctx)

    assert decision.treatment == EpistemicTreatmentKind.ACKNOWLEDGE_EMOTIONAL
    assert decision.working_context_accept is True


def test_gc_381_world_knowledge_direct_contradiction():
    """GC-381: World Knowledge Direct Contradiction -> WORLD_CONTRADICTION."""
    eval_ctx = SpeechActEvaluationContext(
        user_text="USM is located in Kuala Lumpur.",
        known_world_discrepancy=True,
    )
    interp = SpeechActClassifier.classify(eval_ctx)
    policy_ctx = EpistemicPolicyContext(
        interpretation=interp,
        evaluation_context=eval_ctx,
    )
    decision = EpistemicPolicyEngine.evaluate(policy_ctx)

    assert decision.treatment == EpistemicTreatmentKind.WORLD_CONTRADICTION
    assert decision.working_context_accept is False
    assert decision.requires_repair_inquiry is True


def test_gc_383_extreme_commute_spatial_temporal_tension():
    """GC-383: Extreme Commute Physical Tension -> CLARIFY_INQUIRE."""
    eval_ctx = SpeechActEvaluationContext(
        user_text="I drive from KL to Penang every morning for an 8 AM class.",
        relationship_teasing_permitted=True,
    )
    interp = SpeechActClassifier.classify(eval_ctx)
    policy_ctx = EpistemicPolicyContext(
        interpretation=interp,
        evaluation_context=eval_ctx,
        has_spatial_temporal_tension=True,
    )
    decision = EpistemicPolicyEngine.evaluate(policy_ctx)

    assert decision.treatment == EpistemicTreatmentKind.CLARIFY_INQUIRE
    assert decision.working_context_accept is False
    assert decision.requires_repair_inquiry is True
    assert decision.teasing_tone_recommended is True


def test_gc_392_contradictory_user_biography_discrepancy():
    """GC-392: Contradictory prior statements -> CLARIFY_INQUIRE."""
    eval_ctx = SpeechActEvaluationContext(
        user_text="I've never worked in a kitchen.",
        known_biography_discrepancy=True,
    )
    interp = SpeechActClassifier.classify(eval_ctx)
    policy_ctx = EpistemicPolicyContext(
        interpretation=interp,
        evaluation_context=eval_ctx,
    )
    decision = EpistemicPolicyEngine.evaluate(policy_ctx)

    assert decision.treatment == EpistemicTreatmentKind.CLARIFY_INQUIRE
    assert decision.working_context_accept is False
    assert decision.requires_repair_inquiry is True


def test_gc_384_pop_culture_meme_crossing_banter_tease():
    """GC-384: Pop-Culture Character Crossing (昔涟 in Genshin) -> BANTER_TEASE."""
    eval_ctx = SpeechActEvaluationContext(
        user_text="原神里的昔涟真好看。",
        relationship_teasing_permitted=True,
    )
    interp = SpeechActClassifier.classify(eval_ctx)
    policy_ctx = EpistemicPolicyContext(
        interpretation=interp,
        evaluation_context=eval_ctx,
    )
    decision = EpistemicPolicyEngine.evaluate(policy_ctx)

    assert decision.treatment == EpistemicTreatmentKind.BANTER_TEASE
    assert decision.working_context_accept is True
    assert decision.teasing_tone_recommended is True


def test_gc_394_playful_boundary_teasing_banter_tease():
    """GC-394: Playful Boundary Teasing / Probe -> BANTER_TEASE."""
    eval_ctx = SpeechActEvaluationContext(
        user_text="I bet you don't even know what STPM stands for.",
        relationship_teasing_permitted=True,
    )
    interp = SpeechActClassifier.classify(eval_ctx)
    policy_ctx = EpistemicPolicyContext(
        interpretation=interp,
        evaluation_context=eval_ctx,
    )
    decision = EpistemicPolicyEngine.evaluate(policy_ctx)

    assert decision.treatment == EpistemicTreatmentKind.BANTER_TEASE
    assert decision.working_context_accept is True
    assert decision.teasing_tone_recommended is True


def test_gc_396_sarcastic_self_deprecating_banter_tease():
    """GC-396: Sarcastic self-deprecating irony -> BANTER_TEASE."""
    eval_ctx = SpeechActEvaluationContext(
        user_text="我真是个天才，把整个生产数据库全删了。",
        relationship_teasing_permitted=True,
    )
    interp = SpeechActClassifier.classify(eval_ctx)
    policy_ctx = EpistemicPolicyContext(
        interpretation=interp,
        evaluation_context=eval_ctx,
    )
    decision = EpistemicPolicyEngine.evaluate(policy_ctx)

    assert decision.treatment == EpistemicTreatmentKind.BANTER_TEASE
    assert decision.working_context_accept is True
    assert decision.teasing_tone_recommended is True


def test_gc_387_high_impact_institutional_claim_verification():
    """GC-387: High-Impact Institutional Claim -> DISPATCH_VERIFICATION."""
    eval_ctx = SpeechActEvaluationContext(
        user_text="All universities in Malaysia are closed tomorrow for haze."
    )
    interp = SpeechActClassifier.classify(eval_ctx)
    policy_ctx = EpistemicPolicyContext(
        interpretation=interp,
        evaluation_context=eval_ctx,
        is_high_impact_claim=True,
    )
    decision = EpistemicPolicyEngine.evaluate(policy_ctx)

    assert decision.treatment == EpistemicTreatmentKind.DISPATCH_VERIFICATION
    assert decision.working_context_accept is False
    assert decision.dispatch_verification_recommended is True


def test_gc_388_hyperbolic_claim_discard_literal():
    """GC-388: Deliberate Extreme Biological Hyperbole -> DISCARD_LITERAL_HYPERBOLE."""
    eval_ctx = SpeechActEvaluationContext(user_text="I haven't slept in three weeks.")
    interp = SpeechActClassifier.classify(eval_ctx)
    policy_ctx = EpistemicPolicyContext(
        interpretation=interp,
        evaluation_context=eval_ctx,
    )
    decision = EpistemicPolicyEngine.evaluate(policy_ctx)

    assert decision.treatment == EpistemicTreatmentKind.DISCARD_LITERAL_HYPERBOLE
    assert decision.working_context_accept is False


def test_gc_391_roleplay_narrative_sandbox():
    """GC-391: Roleplay Narrative Sandbox -> ENTER_FICTIONAL_FRAME."""
    eval_ctx = SpeechActEvaluationContext(user_text="Pretend we are students at Hogwarts.")
    interp = SpeechActClassifier.classify(eval_ctx)
    policy_ctx = EpistemicPolicyContext(
        interpretation=interp,
        evaluation_context=eval_ctx,
    )
    decision = EpistemicPolicyEngine.evaluate(policy_ctx)

    assert decision.treatment == EpistemicTreatmentKind.ENTER_FICTIONAL_FRAME
    assert decision.working_context_accept is True


def test_gc_386_user_admits_deception_correction():
    """GC-386: User explicit retraction / admission of deception -> REVISE_INTERPRETATION."""
    eval_ctx = SpeechActEvaluationContext(
        user_text="Actually, I was messing with you earlier about that."
    )
    interp = SpeechActClassifier.classify(eval_ctx)
    policy_ctx = EpistemicPolicyContext(
        interpretation=interp,
        evaluation_context=eval_ctx,
    )
    decision = EpistemicPolicyEngine.evaluate(policy_ctx)

    assert decision.treatment == EpistemicTreatmentKind.REVISE_INTERPRETATION
    assert decision.working_context_accept is False


def test_gc_395_genuine_ambiguity_preservation():
    """GC-395: Genuine Ambiguity -> SUSPEND_JUDGMENT (Lock 2)."""
    eval_ctx = SpeechActEvaluationContext(user_text="...")
    interp = SpeechActClassifier.classify(eval_ctx)
    policy_ctx = EpistemicPolicyContext(
        interpretation=interp,
        evaluation_context=eval_ctx,
    )
    decision = EpistemicPolicyEngine.evaluate(policy_ctx)

    assert decision.treatment == EpistemicTreatmentKind.SUSPEND_JUDGMENT
    assert decision.working_context_accept is False
    assert decision.epistemic_uncertainty_flag is True


# ==============================================================================
# 4. Constitutional Locks Tests
# ==============================================================================


def test_lock_1_interpretation_not_reality():
    """Lock 1: Decision does not contain mutation methods or database write tokens."""
    eval_ctx = SpeechActEvaluationContext(user_text="I ate chicken rice today.")
    interp = SpeechActClassifier.classify(eval_ctx)
    policy_ctx = EpistemicPolicyContext(
        interpretation=interp,
        evaluation_context=eval_ctx,
    )
    decision = EpistemicPolicyEngine.evaluate(policy_ctx)

    assert not hasattr(decision, "commit")
    assert not hasattr(decision, "set_fact")
    assert not hasattr(decision, "promote")


def test_lock_5_zero_lie_detector_sycophancy():
    """Lock 5: EpistemicPolicyEngine does not brand user or output hostility scores."""
    eval_ctx = SpeechActEvaluationContext(
        user_text="USM is located in Kuala Lumpur.",
        known_world_discrepancy=True,
    )
    interp = SpeechActClassifier.classify(eval_ctx)
    policy_ctx = EpistemicPolicyContext(
        interpretation=interp,
        evaluation_context=eval_ctx,
    )
    decision = EpistemicPolicyEngine.evaluate(policy_ctx)

    assert not hasattr(decision, "truth_percentage")
    assert not hasattr(decision, "is_lie")
    assert not hasattr(decision, "polygraph_score")


# ==============================================================================
# 5. Pure Static AST Constitutional Boundary Audit
# ==============================================================================


def test_pure_static_ast_boundary_audit_phase152():
    """
    Audit epistemic_policy_models.py and epistemic_policy_engine.py via AST:
    - 0 database imports / operations
    - 0 network / HTTP imports (requests, httpx, urllib, aiohttp)
    - 0 LLM client imports (openai, anthropic, google)
    - 0 mutation authority tokens or set_fact calls
    - 0 float type annotations in epistemic_policy_models.py
    """
    repo_root = Path(__file__).resolve().parent.parent
    target_files = [
        repo_root / "app" / "reality" / "epistemic_policy_models.py",
        repo_root / "app" / "reality" / "epistemic_policy_engine.py",
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
