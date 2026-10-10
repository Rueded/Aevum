"""
test_phase155_pragmatic_context.py — Phase 15.5 Pragmatic Context Assembly Tests

Verifies all gate criteria for Phase 15.5:
1. Valid XML generation (<pragmatic_epistemic_context>) with well-formed tags.
2. Constitutional Directives embedded (Rule 12, Watchpoint, Lock 5, Lock 6).
3. Lock 6 Anti-Compensatory Hallucination: <forbidden_compensatory_assumptions> rendered for tension.
4. Lock 5 Zero Lie-Detector Sycophancy: anti-interrogation directives present.
5. Bitwise determinism and SHA-256 hash stability.
6. Safe XML character escaping.
7. Pure Static AST Constitutional Boundary Audit (0 DB, 0 network, 0 LLM, 0 mutation authority).
"""

import ast
from pathlib import Path
import pytest

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
from app.reality.social_contradiction_models import (
    SocialArbiterContext,
    SocialDiscrepancyAnalysis,
    SocialDiscrepancyType,
    SocialRepairInquiryStrategy,
    TensionSeverity,
)
from app.reality.social_contradiction_arbiter import SocialContradictionArbiter
from app.reality.verification_dispatcher_models import (
    VerificationDispatcherContext,
    VerificationDispatchEnvelope,
    VerificationDispatchStatus,
)
from app.reality.verification_dispatcher import VerificationDispatcher
from app.reality.pragmatic_context_adapter import PragmaticContextAdapter


# ==============================================================================
# 1. XML Structure & Content Tests
# ==============================================================================


def test_render_xml_basic_assertion():
    """Verify basic assertion renders valid XML with speech act and epistemic treatment."""
    interp = PragmaticInterpretation(
        primary_act=SpeechActKind.ASSERTION,
        secondary_act=None,
        social_tone="matter_of_fact",
        literal_proposition="I ate chicken rice today.",
        pragmatic_intent_summary="Declarative statement about meals.",
    )
    treatment = EpistemicTreatmentDecision(
        treatment=EpistemicTreatmentKind.ACCEPT_SOCIAL,
        rationale="Low consequence claim.",
        working_context_accept=True,
    )

    xml_out = PragmaticContextAdapter.render_xml(interp, treatment)

    assert "<pragmatic_epistemic_context>" in xml_out
    assert "</pragmatic_epistemic_context>" in xml_out
    assert "<constitutional_directives>" in xml_out
    assert 'kind="ACCEPT_SOCIAL"' in xml_out
    assert 'working_context_accept="true"' in xml_out
    assert 'primary="ASSERTION"' in xml_out


def test_lock_6_forbidden_bridge_facts_rendered_in_xml():
    """Lock 6: Extreme commute tension must render <forbidden_compensatory_assumptions>."""
    user_text = "I drive from KL to Penang every morning for an 8 AM class."
    eval_ctx = SpeechActEvaluationContext(user_text=user_text)
    interp = SpeechActClassifier.classify(eval_ctx)
    policy_ctx = EpistemicPolicyContext(
        interpretation=interp,
        evaluation_context=eval_ctx,
        has_spatial_temporal_tension=True,
    )
    treatment = EpistemicPolicyEngine.evaluate(policy_ctx)

    arbiter_ctx = SocialArbiterContext(
        user_text=user_text,
        treatment_decision=treatment,
        daily_commute_claimed_km=720,
    )
    analysis = SocialContradictionArbiter.arbitrate(arbiter_ctx)

    xml_out = PragmaticContextAdapter.render_xml(
        interpretation=interp,
        treatment=treatment,
        contradiction_analysis=analysis,
    )

    assert "<forbidden_compensatory_assumptions>" in xml_out
    assert "<prohibited>Do NOT assume user attends online or remote classes</prohibited>" in xml_out
    assert "<prohibited>Do NOT assume classes were cancelled or moved</prohibited>" in xml_out
    assert 'genuine_contradiction="false"' in xml_out


def test_lock_5_anti_interrogation_directives_present():
    """Lock 5: Directives must instruct LLM never to act as interrogator or polygraph."""
    interp = PragmaticInterpretation(
        primary_act=SpeechActKind.ASSERTION,
        social_tone="matter_of_fact",
        pragmatic_intent_summary="test",
    )
    treatment = EpistemicTreatmentDecision(
        treatment=EpistemicTreatmentKind.ACCEPT_SOCIAL,
        rationale="test",
        working_context_accept=True,
    )
    xml_out = PragmaticContextAdapter.render_xml(interp, treatment)

    assert "NEVER act as a courtroom interrogator, polygraph, or adversarial fact-checker" in xml_out


def test_verification_dispatch_block_rendered_when_present():
    """Verify <verification_dispatch> block is rendered when envelope is passed."""
    interp = PragmaticInterpretation(
        primary_act=SpeechActKind.ASSERTION,
        social_tone="matter_of_fact",
        pragmatic_intent_summary="Claim about university closure",
    )
    treatment = EpistemicTreatmentDecision(
        treatment=EpistemicTreatmentKind.DISPATCH_VERIFICATION,
        rationale="High impact claim.",
        working_context_accept=False,
        dispatch_verification_recommended=True,
    )
    disp_ctx = VerificationDispatcherContext(
        turn_id="turn-809",
        user_text="All universities in Malaysia closed tomorrow for haze.",
        treatment_decision=treatment,
        pragmatic_interpretation=interp,
    )
    envelope = VerificationDispatcher.create_dispatch_envelope(disp_ctx)

    xml_out = PragmaticContextAdapter.render_xml(
        interpretation=interp,
        treatment=treatment,
        dispatch_envelope=envelope,
    )

    assert "<verification_dispatch" in xml_out
    assert 'status="DISPATCHED"' in xml_out
    assert 'request_id="vreq_turn-809_' in xml_out


def test_bitwise_determinism_and_hash_stability():
    """Verify identical inputs yield exact same XML and SHA-256 hash."""
    interp = PragmaticInterpretation(
        primary_act=SpeechActKind.SARCASM,
        secondary_act=SpeechActKind.ASSERTION,
        social_tone="sarcastic_self_deprecating",
        literal_proposition="deleted database",
        pragmatic_intent_summary="User deleted production database.",
    )
    treatment = EpistemicTreatmentDecision(
        treatment=EpistemicTreatmentKind.BANTER_TEASE,
        rationale="Self-deprecating irony.",
        working_context_accept=True,
        teasing_tone_recommended=True,
    )

    xml_1 = PragmaticContextAdapter.render_xml(interp, treatment)
    xml_2 = PragmaticContextAdapter.render_xml(interp, treatment)

    assert xml_1 == xml_2
    hash_1 = PragmaticContextAdapter.compute_context_hash(xml_1)
    hash_2 = PragmaticContextAdapter.compute_context_hash(xml_2)
    assert hash_1 == hash_2
    assert len(hash_1) == 64


def test_safe_xml_character_escaping():
    """Special characters in user proposition or rationale must be escaped."""
    interp = PragmaticInterpretation(
        primary_act=SpeechActKind.ASSERTION,
        social_tone="test",
        literal_proposition="A < B & C > 'D' \"E\"",
        pragmatic_intent_summary="Testing <escaped> & 'quoted' characters.",
    )
    treatment = EpistemicTreatmentDecision(
        treatment=EpistemicTreatmentKind.ACCEPT_SOCIAL,
        rationale="Testing <tags> & 'quotes'",
        working_context_accept=True,
    )
    xml_out = PragmaticContextAdapter.render_xml(interp, treatment)

    assert "A &lt; B &amp; C &gt; &apos;D&apos; &quot;E&quot;" in xml_out or "A &lt; B &amp; C &gt; 'D' \"E\"" in xml_out
    assert "&lt;tags&gt;" in xml_out


# ==============================================================================
# 2. Pure Static AST Constitutional Boundary Audit
# ==============================================================================


def test_pure_static_ast_boundary_audit_phase155():
    """
    Audit pragmatic_context_adapter.py via AST:
    - 0 database imports / operations
    - 0 network / HTTP imports (requests, httpx, urllib, aiohttp)
    - 0 LLM client imports (openai, anthropic, google)
    - 0 mutation authority tokens or set_fact calls
    """
    repo_root = Path(__file__).resolve().parent.parent
    target_file = repo_root / "app" / "reality" / "pragmatic_context_adapter.py"

    forbidden_imports = {
        "sqlite3", "sqlalchemy", "databases", "orm",
        "requests", "httpx", "urllib", "aiohttp",
        "openai", "anthropic", "google.generativeai",
    }
    forbidden_call_names = {
        "set_fact", "PromotionAuthorizationToken", "execute", "commit",
    }

    assert target_file.exists(), f"File not found: {target_file}"
    source = target_file.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(target_file))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for forbidden in forbidden_imports:
                    assert forbidden not in alias.name, (
                        f"Forbidden import '{alias.name}' in {target_file.name}:{node.lineno}"
                    )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for forbidden in forbidden_imports:
                assert forbidden not in module, (
                    f"Forbidden import from '{module}' in {target_file.name}:{node.lineno}"
                )
        elif isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            for forbidden_call in forbidden_call_names:
                assert func_name != forbidden_call, (
                    f"Forbidden function call '{func_name}' in {target_file.name}:{node.lineno}"
                )
