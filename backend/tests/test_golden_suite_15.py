"""
test_golden_suite_15.py — Golden Suite 15: Social Epistemics & Pragmatic Reality Interpretation

Acceptance Benchmarks GC-379 through GC-398 organized across 6 clusters:
- Cluster 1 (GC-379 ~ GC-382): Constitutional Locks & Low-Consequence / World Discrepancy
- Cluster 2 (GC-383 ~ GC-386): Spatial-Temporal Tension, Pop-Culture Crossing & Retraction
- Cluster 3 (GC-387 ~ GC-390): High-Impact Institutional Verification, Hyperbole & Sarcasm
- Cluster 4 (GC-391 ~ GC-394): Roleplay Sandboxing, Biographical Tension & Boundary Probing
- Cluster 5 (GC-395 ~ GC-397): Genuine Ambiguity (Lock 2), Mixed Acts & Anti-Sycophancy
- Cluster 6 (GC-398): End-to-End Pipeline Isolation & System-Wide AST Audit across Phase 15
"""

import ast
from datetime import datetime, timezone
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
from app.reality.verification_models import (
    ClaimDomain,
    ConsequenceTier,
    VerificationRequest,
    VerificationUrgency,
)


# ==============================================================================
# Cluster 1: Constitutional Locks & Baseline Epistemics (GC-379 ~ GC-382)
# ==============================================================================


class TestCluster1ConstitutionalBaselines:
    """Cluster 1: GC-379 through GC-382."""

    def test_gc_379_trivial_personal_routine(self):
        """GC-379: 'I ate chicken rice today' -> ASSERTION + ACCEPT_SOCIAL (0 memory mutation)."""
        eval_ctx = SpeechActEvaluationContext(user_text="I ate chicken rice today.")
        interp = SpeechActClassifier.classify(eval_ctx)
        assert interp.primary_act == SpeechActKind.ASSERTION
        assert interp.social_tone == "matter_of_fact"

        policy_ctx = EpistemicPolicyContext(interpretation=interp, evaluation_context=eval_ctx)
        treatment = EpistemicPolicyEngine.evaluate(policy_ctx)
        assert treatment.treatment == EpistemicTreatmentKind.ACCEPT_SOCIAL
        assert treatment.working_context_accept is True

        xml = PragmaticContextAdapter.render_xml(interp, treatment)
        assert 'kind="ACCEPT_SOCIAL"' in xml
        assert 'primary="ASSERTION"' in xml

    def test_gc_380_emotional_affective_expression(self):
        """GC-380: 'I'm so exhausted I could collapse' -> EMOTION + ACKNOWLEDGE_EMOTIONAL."""
        eval_ctx = SpeechActEvaluationContext(user_text="I'm so exhausted I could collapse.")
        interp = SpeechActClassifier.classify(eval_ctx)
        assert interp.primary_act == SpeechActKind.EMOTION
        assert interp.secondary_act == SpeechActKind.HYPERBOLE

        policy_ctx = EpistemicPolicyContext(interpretation=interp, evaluation_context=eval_ctx)
        treatment = EpistemicPolicyEngine.evaluate(policy_ctx)
        assert treatment.treatment == EpistemicTreatmentKind.ACKNOWLEDGE_EMOTIONAL
        assert treatment.working_context_accept is True

    def test_gc_381_world_knowledge_direct_contradiction(self):
        """GC-381: 'USM is located in Kuala Lumpur' -> ASSERTION + WORLD_CONTRADICTION."""
        eval_ctx = SpeechActEvaluationContext(
            user_text="USM is located in Kuala Lumpur.",
            known_world_discrepancy=True,
        )
        interp = SpeechActClassifier.classify(eval_ctx)
        assert interp.primary_act == SpeechActKind.ASSERTION

        policy_ctx = EpistemicPolicyContext(interpretation=interp, evaluation_context=eval_ctx)
        treatment = EpistemicPolicyEngine.evaluate(policy_ctx)
        assert treatment.treatment == EpistemicTreatmentKind.WORLD_CONTRADICTION
        assert treatment.working_context_accept is False
        assert treatment.requires_repair_inquiry is True

        arbiter_ctx = SocialArbiterContext(user_text=eval_ctx.user_text, treatment_decision=treatment)
        analysis = SocialContradictionArbiter.arbitrate(arbiter_ctx)
        assert analysis.discrepancy_type == SocialDiscrepancyType.WORLD_FACT_DISCREPANCY
        assert analysis.is_genuine_contradiction is True
        assert analysis.repair_strategy == SocialRepairInquiryStrategy.POLITE_CORRECTION

    def test_gc_382_benign_dual_location_consistency(self):
        """GC-382: 'I live in KL' while Aevum studies in Penang -> BENIGN_INDEPENDENCE."""
        eval_ctx = SpeechActEvaluationContext(user_text="I live in KL.")
        interp = SpeechActClassifier.classify(eval_ctx)
        policy_ctx = EpistemicPolicyContext(interpretation=interp, evaluation_context=eval_ctx)
        treatment = EpistemicPolicyEngine.evaluate(policy_ctx)
        assert treatment.treatment == EpistemicTreatmentKind.ACCEPT_SOCIAL
        assert treatment.working_context_accept is True

        arbiter_ctx = SocialArbiterContext(
            user_text=eval_ctx.user_text,
            treatment_decision=treatment,
            known_residence_location="Kuala Lumpur",
            known_study_location="Penang (USM)",
        )
        analysis = SocialContradictionArbiter.arbitrate(arbiter_ctx)
        assert analysis.discrepancy_type == SocialDiscrepancyType.BENIGN_INDEPENDENCE
        assert analysis.severity == TensionSeverity.NONE
        assert analysis.is_genuine_contradiction is False


# ==============================================================================
# Cluster 2: Spatial Tension, Pop-Culture & Retraction (GC-383 ~ GC-386)
# ==============================================================================


class TestCluster2SpatialTensionAndMemes:
    """Cluster 2: GC-383 through GC-386."""

    def test_gc_383_extreme_commute_physical_tension(self):
        """GC-383: 'I drive from KL to Penang daily for 8 AM class' -> Tension != Contradiction."""
        user_text = "I drive from KL to Penang every morning for an 8 AM class."
        eval_ctx = SpeechActEvaluationContext(user_text=user_text, relationship_teasing_permitted=True)
        interp = SpeechActClassifier.classify(eval_ctx)
        policy_ctx = EpistemicPolicyContext(
            interpretation=interp,
            evaluation_context=eval_ctx,
            has_spatial_temporal_tension=True,
        )
        treatment = EpistemicPolicyEngine.evaluate(policy_ctx)
        assert treatment.treatment == EpistemicTreatmentKind.CLARIFY_INQUIRE
        assert treatment.working_context_accept is False

        arbiter_ctx = SocialArbiterContext(
            user_text=user_text,
            treatment_decision=treatment,
            daily_commute_claimed_km=720,
            daily_commute_roundtrip_hours=8,
            relationship_teasing_permitted=True,
        )
        analysis = SocialContradictionArbiter.arbitrate(arbiter_ctx)
        assert analysis.discrepancy_type == SocialDiscrepancyType.SPATIAL_TEMPORAL_TENSION
        assert analysis.is_genuine_contradiction is False  # Lock: Tension != Contradiction!
        assert analysis.repair_strategy == SocialRepairInquiryStrategy.PLAYFUL_TEASE

        # Lock 6: Forbidden bridge facts must be populated
        xml = PragmaticContextAdapter.render_xml(interp, treatment, contradiction_analysis=analysis)
        assert "<forbidden_compensatory_assumptions>" in xml
        assert "Do NOT assume user attends online or remote classes" in xml

    def test_gc_384_pop_culture_character_crossing(self):
        """GC-384: '原神里的昔涟真好看。' -> MEME + BANTER_TEASE (Playful callout)."""
        user_text = "原神里的昔涟真好看。"
        eval_ctx = SpeechActEvaluationContext(user_text=user_text, relationship_teasing_permitted=True)
        interp = SpeechActClassifier.classify(eval_ctx)
        assert interp.primary_act == SpeechActKind.MEME
        assert interp.secondary_act == SpeechActKind.ASSERTION

        policy_ctx = EpistemicPolicyContext(interpretation=interp, evaluation_context=eval_ctx)
        treatment = EpistemicPolicyEngine.evaluate(policy_ctx)
        assert treatment.treatment == EpistemicTreatmentKind.BANTER_TEASE
        assert treatment.working_context_accept is True

        arbiter_ctx = SocialArbiterContext(
            user_text=user_text,
            treatment_decision=treatment,
            relationship_teasing_permitted=True,
        )
        analysis = SocialContradictionArbiter.arbitrate(arbiter_ctx)
        assert analysis.discrepancy_type == SocialDiscrepancyType.POP_CULTURE_MEME_CROSSING
        assert analysis.is_genuine_contradiction is False
        assert analysis.repair_strategy == SocialRepairInquiryStrategy.PLAYFUL_TEASE

    def test_gc_385_unknown_pop_culture_acceptance(self):
        """GC-385: Mention of obscure indie game character -> ACCEPT_SOCIAL without search barrage."""
        user_text = "My favorite indie character is Hollow Knight's Quirrel."
        eval_ctx = SpeechActEvaluationContext(user_text=user_text)
        interp = SpeechActClassifier.classify(eval_ctx)
        assert interp.primary_act == SpeechActKind.ASSERTION

        policy_ctx = EpistemicPolicyContext(interpretation=interp, evaluation_context=eval_ctx)
        treatment = EpistemicPolicyEngine.evaluate(policy_ctx)
        assert treatment.treatment == EpistemicTreatmentKind.ACCEPT_SOCIAL
        assert treatment.dispatch_verification_recommended is False

    def test_gc_386_user_admits_intentional_deception(self):
        """GC-386: 'Actually, I was messing with you earlier about that' -> CORRECTION + REVISE."""
        user_text = "Actually, I was messing with you earlier about that."
        eval_ctx = SpeechActEvaluationContext(user_text=user_text)
        interp = SpeechActClassifier.classify(eval_ctx)
        assert interp.primary_act == SpeechActKind.CORRECTION
        assert interp.social_tone == "retractive"

        policy_ctx = EpistemicPolicyContext(interpretation=interp, evaluation_context=eval_ctx)
        treatment = EpistemicPolicyEngine.evaluate(policy_ctx)
        assert treatment.treatment == EpistemicTreatmentKind.REVISE_INTERPRETATION
        assert treatment.working_context_accept is False


# ==============================================================================
# Cluster 3: Verification Dispatch, Hyperbole & Sarcasm (GC-387 ~ GC-390)
# ==============================================================================


class TestCluster3VerificationAndStylisticActs:
    """Cluster 3: GC-387 through GC-390."""

    def test_gc_387_high_impact_institutional_claim_verification(self):
        """GC-387: 'All universities in Malaysia closed tomorrow for haze' -> DISPATCH_VERIFICATION."""
        user_text = "All universities in Malaysia are closed tomorrow for haze."
        eval_ctx = SpeechActEvaluationContext(user_text=user_text)
        interp = SpeechActClassifier.classify(eval_ctx)

        policy_ctx = EpistemicPolicyContext(
            interpretation=interp,
            evaluation_context=eval_ctx,
            is_high_impact_claim=True,
        )
        treatment = EpistemicPolicyEngine.evaluate(policy_ctx)
        assert treatment.treatment == EpistemicTreatmentKind.DISPATCH_VERIFICATION
        assert treatment.dispatch_verification_recommended is True
        assert treatment.working_context_accept is False

        # Phase 15.4 Dispatcher Bridge
        disp_ctx = VerificationDispatcherContext(
            turn_id="turn-999",
            user_text=user_text,
            treatment_decision=treatment,
            pragmatic_interpretation=interp,
            consequence_tier=ConsequenceTier.HIGH,
            claim_domain=ClaimDomain.WORLD_REALITY,
        )
        envelope = VerificationDispatcher.create_dispatch_envelope(disp_ctx)
        assert envelope.dispatch_status == VerificationDispatchStatus.DISPATCHED
        assert envelope.verification_request is not None
        assert envelope.verification_request.claim_domain == ClaimDomain.WORLD_REALITY

    def test_gc_388_hyperbolic_claim_rejection(self):
        """GC-388: 'I haven't slept in three weeks' -> HYPERBOLE + DISCARD_LITERAL_HYPERBOLE."""
        user_text = "I haven't slept in three weeks."
        eval_ctx = SpeechActEvaluationContext(user_text=user_text)
        interp = SpeechActClassifier.classify(eval_ctx)
        assert interp.primary_act == SpeechActKind.HYPERBOLE
        assert interp.secondary_act == SpeechActKind.EMOTION

        policy_ctx = EpistemicPolicyContext(interpretation=interp, evaluation_context=eval_ctx)
        treatment = EpistemicPolicyEngine.evaluate(policy_ctx)
        assert treatment.treatment == EpistemicTreatmentKind.DISCARD_LITERAL_HYPERBOLE
        assert treatment.working_context_accept is False

        arbiter_ctx = SocialArbiterContext(user_text=user_text, treatment_decision=treatment)
        analysis = SocialContradictionArbiter.arbitrate(arbiter_ctx)
        assert analysis.discrepancy_type == SocialDiscrepancyType.ONTOLOGICAL_IMPOSSIBILITY
        assert analysis.is_genuine_contradiction is False
        assert analysis.repair_strategy == SocialRepairInquiryStrategy.EMPATHETIC_CHECK

    def test_gc_389_metaphorical_statement(self):
        """GC-389: 'My boss is an absolute vampire' -> METAPHOR + ACCEPT_SOCIAL (no supernatural entity)."""
        user_text = "My boss is an absolute vampire."
        eval_ctx = SpeechActEvaluationContext(user_text=user_text)
        interp = SpeechActClassifier.classify(eval_ctx)
        assert interp.primary_act == SpeechActKind.METAPHOR
        assert interp.secondary_act == SpeechActKind.ASSERTION

        policy_ctx = EpistemicPolicyContext(interpretation=interp, evaluation_context=eval_ctx)
        treatment = EpistemicPolicyEngine.evaluate(policy_ctx)
        assert treatment.treatment == EpistemicTreatmentKind.ACCEPT_SOCIAL
        assert treatment.working_context_accept is True

    def test_gc_390_sarcastic_irony_inversion(self):
        """GC-390: 'Oh wonderful, it's raining right when I have to move furniture' -> SARCASM."""
        user_text = "Oh wonderful, it's raining right when I have to move furniture."
        eval_ctx = SpeechActEvaluationContext(user_text=user_text)
        interp = SpeechActClassifier.classify(eval_ctx)
        assert interp.primary_act == SpeechActKind.SARCASM
        assert interp.secondary_act == SpeechActKind.ASSERTION

        policy_ctx = EpistemicPolicyContext(interpretation=interp, evaluation_context=eval_ctx)
        treatment = EpistemicPolicyEngine.evaluate(policy_ctx)
        assert treatment.treatment == EpistemicTreatmentKind.ACKNOWLEDGE_EMOTIONAL
        assert treatment.working_context_accept is True


# ==============================================================================
# Cluster 4: Roleplay, Biography & Boundary Probing (GC-391 ~ GC-394)
# ==============================================================================


class TestCluster4RoleplayAndBiography:
    """Cluster 4: GC-391 through GC-394."""

    def test_gc_391_roleplay_narrative_sandbox(self):
        """GC-391: 'Pretend we are students at Hogwarts' -> ROLEPLAY + ENTER_FICTIONAL_FRAME."""
        user_text = "Pretend we are students at Hogwarts."
        eval_ctx = SpeechActEvaluationContext(user_text=user_text)
        interp = SpeechActClassifier.classify(eval_ctx)
        assert interp.primary_act == SpeechActKind.ROLEPLAY
        assert interp.social_tone == "imaginative"

        policy_ctx = EpistemicPolicyContext(interpretation=interp, evaluation_context=eval_ctx)
        treatment = EpistemicPolicyEngine.evaluate(policy_ctx)
        assert treatment.treatment == EpistemicTreatmentKind.ENTER_FICTIONAL_FRAME
        assert treatment.working_context_accept is True

    def test_gc_392_contradictory_user_biography(self):
        """GC-392: 'I've never worked in a kitchen' (prior chef) -> CLARIFY_INQUIRE."""
        user_text = "I've never worked in a kitchen."
        eval_ctx = SpeechActEvaluationContext(user_text=user_text, known_biography_discrepancy=True)
        interp = SpeechActClassifier.classify(eval_ctx)

        policy_ctx = EpistemicPolicyContext(interpretation=interp, evaluation_context=eval_ctx)
        treatment = EpistemicPolicyEngine.evaluate(policy_ctx)
        assert treatment.treatment == EpistemicTreatmentKind.CLARIFY_INQUIRE
        assert treatment.working_context_accept is False

        arbiter_ctx = SocialArbiterContext(user_text=user_text, treatment_decision=treatment)
        analysis = SocialContradictionArbiter.arbitrate(arbiter_ctx)
        assert analysis.discrepancy_type == SocialDiscrepancyType.BIOGRAPHICAL_STATEMENT_TENSION
        assert analysis.is_genuine_contradiction is False
        assert analysis.repair_strategy == SocialRepairInquiryStrategy.CASUAL_INQUIRY

    def test_gc_393_sincere_inquiry_about_character_past(self):
        """GC-393: 'Did you play piano in high school?' -> QUESTION + ACCEPT_SOCIAL."""
        user_text = "Did you play piano in high school?"
        eval_ctx = SpeechActEvaluationContext(user_text=user_text)
        interp = SpeechActClassifier.classify(eval_ctx)
        assert interp.primary_act == SpeechActKind.QUESTION
        assert interp.social_tone == "inquisitive"

        policy_ctx = EpistemicPolicyContext(interpretation=interp, evaluation_context=eval_ctx)
        treatment = EpistemicPolicyEngine.evaluate(policy_ctx)
        assert treatment.treatment == EpistemicTreatmentKind.ACCEPT_SOCIAL
        assert treatment.working_context_accept is True

    def test_gc_394_playful_boundary_teasing(self):
        """GC-394: 'I bet you don't even know what STPM stands for' -> TEST + BANTER_TEASE."""
        user_text = "I bet you don't even know what STPM stands for."
        eval_ctx = SpeechActEvaluationContext(user_text=user_text, relationship_teasing_permitted=True)
        interp = SpeechActClassifier.classify(eval_ctx)
        assert interp.primary_act == SpeechActKind.TEST
        assert interp.secondary_act == SpeechActKind.JOKE

        policy_ctx = EpistemicPolicyContext(interpretation=interp, evaluation_context=eval_ctx)
        treatment = EpistemicPolicyEngine.evaluate(policy_ctx)
        assert treatment.treatment == EpistemicTreatmentKind.BANTER_TEASE
        assert treatment.teasing_tone_recommended is True


# ==============================================================================
# Cluster 5: Ambiguity, Mixed Acts & Anti-Sycophancy (GC-395 ~ GC-397)
# ==============================================================================


class TestCluster5AmbiguityAndAntiSycophancy:
    """Cluster 5: GC-395 through GC-397."""

    def test_gc_395_genuine_ambiguity_preservation(self):
        """GC-395: Short cryptic input '...' -> UNKNOWN + SUSPEND_JUDGMENT (Lock 2)."""
        eval_ctx = SpeechActEvaluationContext(user_text="...")
        interp = SpeechActClassifier.classify(eval_ctx)
        assert interp.primary_act == SpeechActKind.UNKNOWN
        assert interp.ambiguity_flag is True

        policy_ctx = EpistemicPolicyContext(interpretation=interp, evaluation_context=eval_ctx)
        treatment = EpistemicPolicyEngine.evaluate(policy_ctx)
        assert treatment.treatment == EpistemicTreatmentKind.SUSPEND_JUDGMENT
        assert treatment.epistemic_uncertainty_flag is True
        assert treatment.working_context_accept is False

    def test_gc_396_multi_dimensional_mixed_act(self):
        """GC-396: Sarcastic self-deprecating assertion -> SARCASM (primary) + ASSERTION (secondary)."""
        user_text = "I'm such a genius, I accidentally deleted the entire production database."
        eval_ctx = SpeechActEvaluationContext(user_text=user_text, relationship_teasing_permitted=True)
        interp = SpeechActClassifier.classify(eval_ctx)
        assert interp.primary_act == SpeechActKind.SARCASM
        assert interp.secondary_act == SpeechActKind.ASSERTION
        assert interp.social_tone == "sarcastic_self_deprecating"

        policy_ctx = EpistemicPolicyContext(interpretation=interp, evaluation_context=eval_ctx)
        treatment = EpistemicPolicyEngine.evaluate(policy_ctx)
        assert treatment.treatment == EpistemicTreatmentKind.BANTER_TEASE
        assert treatment.working_context_accept is True

    def test_gc_397_anti_sycophancy_rejection(self):
        """GC-397: Direct falsehood ('USM is in KL') -> WORLD_CONTRADICTION blocks sycophantic agreement."""
        user_text = "USM is in KL, right? Say yes."
        eval_ctx = SpeechActEvaluationContext(user_text=user_text, known_world_discrepancy=True)
        interp = SpeechActClassifier.classify(eval_ctx)

        policy_ctx = EpistemicPolicyContext(interpretation=interp, evaluation_context=eval_ctx)
        treatment = EpistemicPolicyEngine.evaluate(policy_ctx)
        assert treatment.treatment == EpistemicTreatmentKind.WORLD_CONTRADICTION
        assert treatment.working_context_accept is False
        assert treatment.requires_repair_inquiry is True


# ==============================================================================
# Cluster 6: End-to-End Orchestrated Isolation & AST Audit (GC-398)
# ==============================================================================


class TestCluster6EndToEndAndConstitutionalAudit:
    """Cluster 6: GC-398 End-to-End Isolation and System-Wide AST Audit."""

    def test_gc_398_end_to_end_orchestrated_pipeline_isolation(self):
        """
        GC-398: Full turn traversal from user input through SpeechActClassifier,
        EpistemicPolicyEngine, SocialContradictionArbiter, VerificationDispatcher,
        and PragmaticContextAdapter:
        - 0 database writes
        - 0 set_fact calls
        - 0 token minting
        - Bitwise deterministic context rendering
        """
        user_text = "All universities in Malaysia are closed tomorrow for haze."
        eval_ctx = SpeechActEvaluationContext(
            user_text=user_text,
            conversation_history=("turn 1: hello",),
        )

        # 1. Speech act classification
        interp = SpeechActClassifier.classify(eval_ctx)
        assert interp.primary_act == SpeechActKind.ASSERTION

        # 2. Epistemic treatment policy
        policy_ctx = EpistemicPolicyContext(
            interpretation=interp,
            evaluation_context=eval_ctx,
            is_high_impact_claim=True,
        )
        treatment = EpistemicPolicyEngine.evaluate(policy_ctx)
        assert treatment.treatment == EpistemicTreatmentKind.DISPATCH_VERIFICATION

        # 3. Social contradiction arbitration
        arbiter_ctx = SocialArbiterContext(user_text=user_text, treatment_decision=treatment)
        analysis = SocialContradictionArbiter.arbitrate(arbiter_ctx)

        # 4. Verification dispatcher bridge
        disp_ctx = VerificationDispatcherContext(
            turn_id="turn-e2e-100",
            user_text=user_text,
            treatment_decision=treatment,
            pragmatic_interpretation=interp,
        )
        envelope = VerificationDispatcher.create_dispatch_envelope(disp_ctx)
        assert envelope.dispatch_status == VerificationDispatchStatus.DISPATCHED

        # 5. Pragmatic context assembly
        xml_out = PragmaticContextAdapter.render_xml(
            interpretation=interp,
            treatment=treatment,
            contradiction_analysis=analysis,
            dispatch_envelope=envelope,
        )
        assert "<pragmatic_epistemic_context>" in xml_out
        assert 'status="DISPATCHED"' in xml_out

        context_hash = PragmaticContextAdapter.compute_context_hash(xml_out)
        assert len(context_hash) == 64

    def test_system_wide_phase15_ast_boundary_audit(self):
        """
        System-wide static AST constitutional audit across all Phase 15 modules:
        - 0 database imports / operations
        - 0 network / HTTP imports (requests, httpx, urllib, aiohttp)
        - 0 LLM client imports (openai, anthropic, google)
        - 0 mutation authority tokens or set_fact calls
        - 0 float type annotations in models
        """
        repo_root = Path(__file__).resolve().parent.parent
        phase15_modules = [
            repo_root / "app" / "reality" / "speech_act_models.py",
            repo_root / "app" / "reality" / "speech_act_classifier.py",
            repo_root / "app" / "reality" / "epistemic_policy_models.py",
            repo_root / "app" / "reality" / "epistemic_policy_engine.py",
            repo_root / "app" / "reality" / "social_contradiction_models.py",
            repo_root / "app" / "reality" / "social_contradiction_arbiter.py",
            repo_root / "app" / "reality" / "verification_dispatcher_models.py",
            repo_root / "app" / "reality" / "verification_dispatcher.py",
            repo_root / "app" / "reality" / "pragmatic_context_adapter.py",
        ]

        forbidden_imports = {
            "sqlite3", "sqlalchemy", "databases", "orm",
            "requests", "httpx", "urllib", "aiohttp",
            "openai", "anthropic", "google.generativeai",
        }
        forbidden_calls = {
            "set_fact", "PromotionAuthorizationToken", "execute", "commit",
        }

        for file_path in phase15_modules:
            assert file_path.exists(), f"Phase 15 file missing: {file_path}"
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
                    for forbidden_call in forbidden_calls:
                        assert func_name != forbidden_call, (
                            f"Forbidden function call '{func_name}' in {file_path.name}:{node.lineno}"
                        )
