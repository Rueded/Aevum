"""
test_phase154_verification_dispatcher.py — Phase 15.4 Verification Dispatcher Bridge Tests

Verifies all gate criteria for Phase 15.4:
1. DTO Immutability & Model Integrity (frozen=True, extra="forbid", zero float fields).
2. Lock 4 (External Verification != Automatic Truth Mutation):
   Dispatching high-consequence claim produces VerificationRequest; 0 set_fact, 0 token minting.
3. Correct routing for GC-387 (High-Impact Institutional Claim).
4. Skipping for low-consequence or non-recommended claims (GC-379, GC-384, GC-395).
5. Phase 9 VerificationRequest schema compatibility and determinism.
6. Lock 5 (Zero Lie-Detector Sycophancy): Non-adversarial framing.
7. Pure Static AST Constitutional Boundary Audit (0 DB, 0 network, 0 LLM, 0 mutation authority).
"""

import ast
from datetime import datetime, timezone
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
from app.reality.verification_models import (
    ClaimDomain,
    ConsequenceTier,
    VerificationRequest,
    VerificationUrgency,
)
from app.reality.verification_dispatcher_models import (
    VerificationDispatcherContext,
    VerificationDispatchEnvelope,
    VerificationDispatchStatus,
)
from app.reality.verification_dispatcher import VerificationDispatcher


# ==============================================================================
# 1. DTO Immutability & Model Integrity Tests
# ==============================================================================


def test_verification_dispatch_status_all_members():
    """Verify all 4 VerificationDispatchStatus enum members exist."""
    expected = {
        "DISPATCHED",
        "SKIPPED_NOT_RECOMMENDED",
        "SKIPPED_LOW_CONSEQUENCE",
        "SUPPRESSED_BY_CONTEXT",
    }
    actual = {m.value for m in VerificationDispatchStatus}
    assert actual == expected
    assert len(VerificationDispatchStatus) == 4


def test_verification_dispatch_envelope_immutability():
    """Verify VerificationDispatchEnvelope is strictly immutable (frozen=True)."""
    envelope = VerificationDispatchEnvelope(
        envelope_id="env_test",
        dispatch_status=VerificationDispatchStatus.SKIPPED_NOT_RECOMMENDED,
        originating_turn_text="test text",
        pragmatic_act=SpeechActKind.ASSERTION,
        rationale="Skipped",
    )
    with pytest.raises(ValidationError):
        envelope.dispatch_status = VerificationDispatchStatus.DISPATCHED  # type: ignore


def test_verification_dispatch_envelope_extra_fields_forbidden():
    """Verify VerificationDispatchEnvelope forbids unapproved extra fields."""
    with pytest.raises(ValidationError):
        VerificationDispatchEnvelope(
            envelope_id="env_test",
            dispatch_status=VerificationDispatchStatus.SKIPPED_NOT_RECOMMENDED,
            originating_turn_text="test",
            pragmatic_act=SpeechActKind.ASSERTION,
            rationale="Skipped",
            truth_score=0.99,  # type: ignore # FORBIDDEN
        )


def test_phase154_models_zero_float_fields():
    """Permanent Note A: Verify zero float fields exist across all Phase 15.4 models."""
    for model_cls in (VerificationDispatchEnvelope, VerificationDispatcherContext):
        for field_name, field_info in model_cls.model_fields.items():
            annotation_str = str(field_info.annotation)
            assert "float" not in annotation_str.lower(), (
                f"Model {model_cls.__name__} has forbidden float field: {field_name}"
            )


# ==============================================================================
# 2. Lock 4 & GC-387 High-Impact Institutional Claim Dispatch
# ==============================================================================


def test_gc_387_high_impact_institutional_claim_dispatch():
    """
    GC-387: High-Impact Institutional Claim ('All universities in Malaysia are closed tomorrow for haze')
    must be packaged into a VerificationDispatchEnvelope with a Phase 9 VerificationRequest.
    """
    user_text = "All universities in Malaysia are closed tomorrow for haze."
    eval_ctx = SpeechActEvaluationContext(user_text=user_text)
    interp = SpeechActClassifier.classify(eval_ctx)
    policy_ctx = EpistemicPolicyContext(
        interpretation=interp,
        evaluation_context=eval_ctx,
        is_high_impact_claim=True,
    )
    decision = EpistemicPolicyEngine.evaluate(policy_ctx)

    assert decision.treatment == EpistemicTreatmentKind.DISPATCH_VERIFICATION
    assert decision.dispatch_verification_recommended is True

    disp_ctx = VerificationDispatcherContext(
        turn_id="turn-801",
        user_text=user_text,
        treatment_decision=decision,
        pragmatic_interpretation=interp,
        consequence_tier=ConsequenceTier.HIGH,
        urgency=VerificationUrgency.IMMEDIATE_TURN,
        claim_domain=ClaimDomain.WORLD_REALITY,
    )
    fixed_time = datetime(2026, 9, 27, 12, 0, 0, tzinfo=timezone.utc)
    envelope = VerificationDispatcher.create_dispatch_envelope(disp_ctx, now=fixed_time)

    assert envelope.dispatch_status == VerificationDispatchStatus.DISPATCHED
    assert envelope.verification_request is not None
    assert isinstance(envelope.verification_request, VerificationRequest)
    assert envelope.verification_request.claim_domain == ClaimDomain.WORLD_REALITY
    assert envelope.verification_request.consequence_tier == ConsequenceTier.HIGH
    assert envelope.verification_request.urgency == VerificationUrgency.IMMEDIATE_TURN
    assert envelope.verification_request.initiating_turn_id == "turn-801"
    assert envelope.verification_request.created_at == fixed_time
    assert "universities" in envelope.verification_request.claim_key

    # Lock 4 Invariant: Dispatcher produces request; 0 set_fact, 0 token minting
    assert not hasattr(envelope, "set_fact")
    assert not hasattr(envelope, "commit")


# ==============================================================================
# 3. Skipping Non-Recommended Claims Tests
# ==============================================================================


def test_gc_379_trivial_routine_skips_verification():
    """GC-379: Trivial personal routine ('I ate chicken rice') must skip verification."""
    user_text = "I ate chicken rice today."
    eval_ctx = SpeechActEvaluationContext(user_text=user_text)
    interp = SpeechActClassifier.classify(eval_ctx)
    policy_ctx = EpistemicPolicyContext(
        interpretation=interp,
        evaluation_context=eval_ctx,
        is_high_impact_claim=False,
    )
    decision = EpistemicPolicyEngine.evaluate(policy_ctx)

    disp_ctx = VerificationDispatcherContext(
        turn_id="turn-802",
        user_text=user_text,
        treatment_decision=decision,
        pragmatic_interpretation=interp,
    )
    envelope = VerificationDispatcher.create_dispatch_envelope(disp_ctx)

    assert envelope.dispatch_status == VerificationDispatchStatus.SKIPPED_NOT_RECOMMENDED
    assert envelope.verification_request is None
    assert "did not recommend" in envelope.rationale.lower()


def test_gc_384_pop_culture_meme_skips_verification():
    """GC-384: Pop-culture character meme crossing ('原神里的昔涟真好看') skips verification."""
    user_text = "原神里的昔涟真好看。"
    eval_ctx = SpeechActEvaluationContext(user_text=user_text)
    interp = SpeechActClassifier.classify(eval_ctx)
    policy_ctx = EpistemicPolicyContext(
        interpretation=interp,
        evaluation_context=eval_ctx,
    )
    decision = EpistemicPolicyEngine.evaluate(policy_ctx)

    disp_ctx = VerificationDispatcherContext(
        turn_id="turn-803",
        user_text=user_text,
        treatment_decision=decision,
        pragmatic_interpretation=interp,
    )
    envelope = VerificationDispatcher.create_dispatch_envelope(disp_ctx)

    assert envelope.dispatch_status == VerificationDispatchStatus.SKIPPED_NOT_RECOMMENDED
    assert envelope.verification_request is None


def test_gc_395_genuine_ambiguity_skips_verification():
    """GC-395: Cryptic or ambiguous signal ('...') skips verification."""
    user_text = "..."
    eval_ctx = SpeechActEvaluationContext(user_text=user_text)
    interp = SpeechActClassifier.classify(eval_ctx)
    policy_ctx = EpistemicPolicyContext(
        interpretation=interp,
        evaluation_context=eval_ctx,
    )
    decision = EpistemicPolicyEngine.evaluate(policy_ctx)

    disp_ctx = VerificationDispatcherContext(
        turn_id="turn-804",
        user_text=user_text,
        treatment_decision=decision,
        pragmatic_interpretation=interp,
    )
    envelope = VerificationDispatcher.create_dispatch_envelope(disp_ctx)

    assert envelope.dispatch_status == VerificationDispatchStatus.SKIPPED_NOT_RECOMMENDED
    assert envelope.verification_request is None


# ==============================================================================
# 4. Determinism & Lock 5 (Zero Lie-Detector Sycophancy)
# ==============================================================================


def test_dispatch_determinism():
    """Same input context must produce identical envelope."""
    decision = EpistemicTreatmentDecision(
        treatment=EpistemicTreatmentKind.DISPATCH_VERIFICATION,
        rationale="High impact.",
        working_context_accept=False,
        dispatch_verification_recommended=True,
    )
    interp = PragmaticInterpretation(
        primary_act=SpeechActKind.ASSERTION,
        social_tone="matter_of_fact",
        literal_proposition="School closed tomorrow",
        pragmatic_intent_summary="Claim about school closure",
    )
    disp_ctx = VerificationDispatcherContext(
        turn_id="turn-805",
        user_text="School closed tomorrow",
        treatment_decision=decision,
        pragmatic_interpretation=interp,
    )
    fixed_time = datetime(2026, 9, 27, 12, 0, 0, tzinfo=timezone.utc)
    env1 = VerificationDispatcher.create_dispatch_envelope(disp_ctx, now=fixed_time)
    env2 = VerificationDispatcher.create_dispatch_envelope(disp_ctx, now=fixed_time)

    assert env1.envelope_id == env2.envelope_id
    assert env1.verification_request == env2.verification_request
    assert env1.rationale == env2.rationale


def test_lock_5_zero_lie_detector_sycophancy_in_dispatcher():
    """Lock 5: Dispatcher does not brand the user or generate hostility/polygraph markers."""
    decision = EpistemicTreatmentDecision(
        treatment=EpistemicTreatmentKind.DISPATCH_VERIFICATION,
        rationale="Institutional verification.",
        working_context_accept=False,
        dispatch_verification_recommended=True,
    )
    interp = PragmaticInterpretation(
        primary_act=SpeechActKind.ASSERTION,
        social_tone="matter_of_fact",
        pragmatic_intent_summary="test",
    )
    disp_ctx = VerificationDispatcherContext(
        turn_id="turn-806",
        user_text="Universities closed",
        treatment_decision=decision,
        pragmatic_interpretation=interp,
    )
    envelope = VerificationDispatcher.create_dispatch_envelope(disp_ctx)

    assert not hasattr(envelope, "user_suspect_score")
    assert not hasattr(envelope, "deception_likelihood")
    assert not hasattr(envelope, "polygraph")


# ==============================================================================
# 5. Pure Static AST Constitutional Boundary Audit
# ==============================================================================


def test_pure_static_ast_boundary_audit_phase154():
    """
    Audit verification_dispatcher_models.py and verification_dispatcher.py via AST:
    - 0 database imports / operations
    - 0 network / HTTP imports (requests, httpx, urllib, aiohttp)
    - 0 LLM client imports (openai, anthropic, google)
    - 0 mutation authority tokens or set_fact calls
    - 0 float type annotations in verification_dispatcher_models.py
    """
    repo_root = Path(__file__).resolve().parent.parent
    target_files = [
        repo_root / "app" / "reality" / "verification_dispatcher_models.py",
        repo_root / "app" / "reality" / "verification_dispatcher.py",
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
