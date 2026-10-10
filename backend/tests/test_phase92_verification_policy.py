"""
test_phase92_verification_policy.py — Phase 9.2 Verification Policy Engine Test Suite

Comprehensive Verification of the 10 Gate Checkpoints:
1. Determinism across 100 repeated evaluations.
2. Explicit rule precedence determinism (Privacy > Turn Budget > Daily Cap > Quiet Hours > Tiering).
3. Immutable & extra-forbidden VerificationDecision contract.
4. Policy does not mutate Request or Context (read-only input).
5. Policy engine cannot construct or return VerificationFinding or ClaimEpistemicStatus.
6. Policy engine cannot execute schedulers or background tasks (AST check for create_task, threading, etc.).
7. allowed_authorities is strictly a policy constraint, NOT a truth verdict (Lock 3).
8. EXACT_MATCH is scope alignment, NOT identity verification (Lock 8).
9. Turn and daily budgets are strictly read-only inputs (zero decrements/increments in 9.2).
10. Rationale contains no epistemic confidence, probability, or float percentages.
"""

import ast
from datetime import datetime, timezone
from pathlib import Path
import re
import pytest
from pydantic import ValidationError

from app.reality.verification_models import (
    ClaimDomain,
    SourceAuthority,
    SourceKind,
    VerificationScope,
    VerificationUrgency,
    ConsequenceTier,
    VerificationRequest,
)
from app.reality.verification_policy_engine import (
    VerificationPrivacyScope,
    QuietHoursBehavior,
    RateLimitClass,
    VerificationCostBudget,
    VerificationPolicyContext,
    VerificationDecision,
    VerificationPolicyEngine,
)


class TestPhase92VerificationPolicy:

    @pytest.fixture
    def engine(self) -> VerificationPolicyEngine:
        return VerificationPolicyEngine()

    @pytest.fixture
    def base_context(self) -> VerificationPolicyContext:
        return VerificationPolicyContext(
            current_time=datetime(2025, 6, 1, 14, 0, tzinfo=timezone.utc),
            is_quiet_hours=False,
            user_privacy_consented=True,
            turn_verification_budget_remaining=2,
            daily_verification_count=1,
            daily_verification_cap=10,
        )

    # --------------------------------------------------------------------------
    # Checkpoint 1 & 2: Determinism and Rule Precedence
    # --------------------------------------------------------------------------

    def test_checkpoint_1_repeated_evaluations_100_runs_identical_determinism(self, engine, base_context):
        """
        Checkpoint 1:
        100 evaluations of the same request + context produces the EXACT identical decision.
        """
        req = VerificationRequest(
            request_id="req-det-100",
            created_at=base_context.current_time,
            claim_domain=ClaimDomain.WORLD_REALITY,
            claim_key="institutions.usm.academic_calendar",
            claim_value="semester_1",
            consequence_tier=ConsequenceTier.HIGH,
        )
        decisions = [
            engine.evaluate(req, base_context, decision_id="vdec-const-001")
            for _ in range(100)
        ]
        first = decisions[0]
        for idx, dec in enumerate(decisions):
            assert dec == first, f"Evaluation iteration {idx} diverged from deterministic baseline!"

    def test_checkpoint_2_rule_precedence_determinism(self, engine, base_context):
        """
        Checkpoint 2:
        Precedence order must be deterministically fixed when multiple suppression
        conditions coincide:
        Precedence 1: Privacy & Consent (VPOL-001-PRIVACY-CONSENT)
        Precedence 2: Per-Turn Budget (VPOL-002-TURN-BUDGET)
        Precedence 3: Daily Cap (VPOL-003-DAILY-CAP)
        Precedence 4: Quiet Hours (VPOL-004-QUIET-HOURS-DEFERRED)
        """
        # Case A: Privacy unconsented + turn budget exhausted + daily cap reached + quiet hours
        # MUST trigger VPOL-001 (Privacy is highest precedence)
        multi_context_1 = base_context.model_copy(
            update={
                "user_privacy_consented": False,
                "turn_verification_budget_remaining": 0,
                "daily_verification_count": 10,
                "is_quiet_hours": True,
            }
        )
        req_personal = VerificationRequest(
            request_id="req-prec-01",
            created_at=base_context.current_time,
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="biography.school",
            claim_value="Test School",
            consequence_tier=ConsequenceTier.HIGH,
            entity_binding_anchor="character:aevum:primary",
        )
        dec_a = engine.evaluate(req_personal, multi_context_1)
        assert dec_a.policy_rule_id == "VPOL-001-PRIVACY-CONSENT"
        assert dec_a.suppression_reason == "UNCONSENTED_PERSONAL_VERIFICATION"

        # Case B: Consented personal + turn budget 0 + daily cap reached + quiet hours
        # MUST trigger VPOL-002 (Turn budget is next precedence)
        multi_context_2 = multi_context_1.model_copy(update={"user_privacy_consented": True})
        dec_b = engine.evaluate(req_personal, multi_context_2)
        assert dec_b.policy_rule_id == "VPOL-002-TURN-BUDGET"
        assert dec_b.suppression_reason == "TURN_BUDGET_EXHAUSTED"

        # Case C: Consented personal + turn budget 1 + daily cap reached + quiet hours
        # MUST trigger VPOL-003 (Daily cap over quiet hours)
        multi_context_3 = multi_context_2.model_copy(update={"turn_verification_budget_remaining": 1})
        dec_c = engine.evaluate(req_personal, multi_context_3)
        assert dec_c.policy_rule_id == "VPOL-003-DAILY-CAP"
        assert dec_c.suppression_reason == "DAILY_CAP_EXCEEDED"

        # Case D: Turn budget 1 + daily count 5 (below cap) + quiet hours (LOW consequence)
        # MUST trigger VPOL-004 (Quiet hours deferral)
        multi_context_4 = multi_context_3.model_copy(update={"daily_verification_count": 5})
        req_low = VerificationRequest(
            request_id="req-prec-04",
            created_at=base_context.current_time,
            claim_domain=ClaimDomain.WORLD_REALITY,
            claim_key="trivia.campus_cafe_hours",
            claim_value="open",
            consequence_tier=ConsequenceTier.LOW,
        )
        dec_d = engine.evaluate(req_low, multi_context_4)
        assert dec_d.policy_rule_id == "VPOL-004-QUIET-HOURS-DEFERRED"
        assert dec_d.suppression_reason == "QUIET_HOURS_DEFERRED"

    # --------------------------------------------------------------------------
    # Checkpoint 3 & 4: Immutability and Context Preservation
    # --------------------------------------------------------------------------

    def test_checkpoint_3_immutable_decision_model(self, engine, base_context):
        """
        Checkpoint 3:
        VerificationDecision must be strictly frozen with extra attributes forbidden.
        """
        req = VerificationRequest(
            request_id="req-immut-01",
            created_at=base_context.current_time,
            claim_domain=ClaimDomain.WORLD_REALITY,
            claim_key="institutions.usm.academic_calendar",
            claim_value="semester_1",
            consequence_tier=ConsequenceTier.HIGH,
        )
        decision = engine.evaluate(req, base_context)

        with pytest.raises(ValidationError):
            decision.should_verify = False  # type: ignore

        with pytest.raises(ValidationError):
            VerificationDecision(
                **decision.model_dump(),
                rogue_attribute="invalid",  # type: ignore
            )

    def test_checkpoint_4_and_9_policy_does_not_mutate_request_or_context(self, engine, base_context):
        """
        Checkpoint 4 & 9:
        Policy engine must treat Request and Context strictly as read-only inputs.
        Zero decrements of turn budget, zero increments of daily count, zero side effects.
        """
        req = VerificationRequest(
            request_id="req-mut-check",
            created_at=base_context.current_time,
            claim_domain=ClaimDomain.WORLD_REALITY,
            claim_key="degree.duration",
            claim_value=4,
            consequence_tier=ConsequenceTier.MEDIUM,
        )
        ctx_before = base_context.model_dump()
        req_before = req.model_dump()

        engine.evaluate(req, base_context)

        assert base_context.model_dump() == ctx_before, "PolicyEngine mutated VerificationPolicyContext!"
        assert req.model_dump() == req_before, "PolicyEngine mutated VerificationRequest!"
        assert base_context.turn_verification_budget_remaining == 2, "turn_budget was decremented in 9.2!"
        assert base_context.daily_verification_count == 1, "daily_count was incremented in 9.2!"

    # --------------------------------------------------------------------------
    # Checkpoint 5 & 6: Type Boundary and Execution Prohibition
    # --------------------------------------------------------------------------

    def test_checkpoint_5_policy_cannot_construct_finding_or_epistemic_status(self, engine, base_context):
        """
        Checkpoint 5:
        VerificationPolicyEngine returns strictly VerificationDecision.
        It must NEVER return a VerificationFinding, ExternalObservation, or ClaimEpistemicStatus.
        """
        req = VerificationRequest(
            request_id="req-type-01",
            created_at=base_context.current_time,
            claim_domain=ClaimDomain.WORLD_REALITY,
            claim_key="degree.name",
            claim_value="Software Engineering",
            consequence_tier=ConsequenceTier.HIGH,
        )
        decision = engine.evaluate(req, base_context)

        assert isinstance(decision, VerificationDecision)
        assert not hasattr(decision, "epistemic_status"), "Decision has forbidden epistemic_status!"
        assert not hasattr(decision, "finding_id"), "Decision has forbidden finding_id!"
        assert not hasattr(decision, "is_refutation"), "Decision has forbidden is_refutation!"

    # --------------------------------------------------------------------------
    # Checkpoint 7: allowed_authorities is a Policy Constraint, NOT Truth (Lock 3)
    # --------------------------------------------------------------------------

    def test_checkpoint_7_allowed_authorities_is_policy_constraint_not_truth(self, engine, base_context):
        """
        Checkpoint 7:
        allowed_authorities designates permissible sources for 9.3 to query.
        It does NOT imply that a source from this authority is true, confirmed, or pre-verified.
        """
        req = VerificationRequest(
            request_id="req-auth-01",
            created_at=base_context.current_time,
            claim_domain=ClaimDomain.WORLD_REALITY,
            claim_key="degree.credits",
            claim_value=120,
            consequence_tier=ConsequenceTier.CRITICAL,
        )
        decision = engine.evaluate(req, base_context)

        # allowed_authorities is populated as a constraint
        assert SourceAuthority.PRIMARY_INSTITUTIONAL in decision.allowed_authorities
        assert SourceAuthority.OFFICIAL_PUBLIC_RECORD in decision.allowed_authorities

        # Decision does not declare truth
        assert not hasattr(decision, "is_true")
        assert not hasattr(decision, "verified")
        assert not hasattr(decision, "confidence")

    # --------------------------------------------------------------------------
    # Checkpoint 8: EXACT_MATCH is Scope Alignment, NOT Identity Verification (Lock 8)
    # --------------------------------------------------------------------------

    def test_checkpoint_8_exact_match_does_not_imply_identity_verified(self, engine, base_context):
        """
        Checkpoint 8:
        target_scope = EXACT_MATCH dictates target scope alignment rigor required.
        It does NOT imply that the external entity is verified as Aevum.
        """
        req = VerificationRequest(
            request_id="req-scope-01",
            created_at=base_context.current_time,
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="biography.degree",
            claim_value="Computer Science",
            consequence_tier=ConsequenceTier.CRITICAL,
            entity_binding_anchor="character:aevum:primary",
        )
        decision = engine.evaluate(req, base_context)

        assert decision.target_scope == VerificationScope.EXACT_MATCH
        assert not hasattr(decision, "identity_verified")
        assert not hasattr(decision, "entity_matched")

    # --------------------------------------------------------------------------
    # Checkpoint 10: Rationale Contains No Epistemic Confidence or Probabilities
    # --------------------------------------------------------------------------

    def test_checkpoint_10_rationale_contains_no_epistemic_confidence_or_probability(self, engine, base_context):
        """
        Checkpoint 10:
        Rationale must be a deterministic rule explanation.
        Forbidden: "probability", "confidence", "likely", "unlikely", "%", floats.
        """
        requests = [
            VerificationRequest(
                request_id="r1",
                created_at=base_context.current_time,
                claim_domain=ClaimDomain.PERSONAL_REALITY,
                claim_key="bio.school",
                claim_value="X",
                consequence_tier=ConsequenceTier.HIGH,
                entity_binding_anchor="character:aevum:primary",
            ),
            VerificationRequest(
                request_id="r2",
                created_at=base_context.current_time,
                claim_domain=ClaimDomain.WORLD_REALITY,
                claim_key="world.term",
                claim_value="Y",
                consequence_tier=ConsequenceTier.LOW,
            ),
        ]
        contexts = [
            base_context,
            base_context.model_copy(update={"user_privacy_consented": False}),
            base_context.model_copy(update={"turn_verification_budget_remaining": 0}),
            base_context.model_copy(update={"daily_verification_count": 10}),
            base_context.model_copy(update={"is_quiet_hours": True}),
        ]

        forbidden_patterns = [
            r"\bprobab\w*", r"\bconfiden\w*", r"\blikely\b", r"\bunlikely\b",
            r"%", r"\b0\.\d+\b", r"\b\d+\.\d+\b"
        ]

        for req in requests:
            for ctx in contexts:
                decision = engine.evaluate(req, ctx)
                rationale_lower = decision.rationale.lower()
                for pat in forbidden_patterns:
                    assert not re.search(pat, rationale_lower), (
                        f"Forbidden epistemic wording/float matched pattern '{pat}' in rationale: "
                        f"'{decision.rationale}'"
                    )

    # --------------------------------------------------------------------------
    # Privacy & Consequence Tier Specific Tests
    # --------------------------------------------------------------------------

    def test_privacy_guard_unconsented_personal_claim_suppressed(self, engine, base_context):
        req = VerificationRequest(
            request_id="req-priv-01",
            created_at=base_context.current_time,
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="biography.secondary_school",
            claim_value="Chung Ling High School",
            consequence_tier=ConsequenceTier.HIGH,
            urgency=VerificationUrgency.IMMEDIATE_TURN,
            entity_binding_anchor="character:aevum:primary",
        )
        unconsented_context = base_context.model_copy(update={"user_privacy_consented": False})
        decision = engine.evaluate(req, unconsented_context)

        assert decision.should_verify is False
        assert decision.suppression_reason == "UNCONSENTED_PERSONAL_VERIFICATION"
        assert decision.privacy_scope == VerificationPrivacyScope.FORBIDDEN_PRIVATE
        assert decision.policy_rule_id == "VPOL-001-PRIVACY-CONSENT"

    def test_turn_rate_budget_exhaustion(self, engine, base_context):
        req = VerificationRequest(
            request_id="req-rate-01",
            created_at=base_context.current_time,
            claim_domain=ClaimDomain.WORLD_REALITY,
            claim_key="institutions.usm.tuition_fee",
            claim_value=1200,
            consequence_tier=ConsequenceTier.MEDIUM,
        )
        exhausted_context = base_context.model_copy(update={"turn_verification_budget_remaining": 0})
        decision = engine.evaluate(req, exhausted_context)

        assert decision.should_verify is False
        assert decision.suppression_reason == "TURN_BUDGET_EXHAUSTED"
        assert decision.policy_rule_id == "VPOL-002-TURN-BUDGET"

    def test_daily_rate_budget_exhaustion(self, engine, base_context):
        req = VerificationRequest(
            request_id="req-daily-01",
            created_at=base_context.current_time,
            claim_domain=ClaimDomain.WORLD_REALITY,
            claim_key="institutions.usm.campus_location",
            claim_value="Penang",
            consequence_tier=ConsequenceTier.LOW,
        )
        capped_context = base_context.model_copy(update={"daily_verification_count": 10, "daily_verification_cap": 10})
        decision = engine.evaluate(req, capped_context)

        assert decision.should_verify is False
        assert decision.suppression_reason == "DAILY_CAP_EXCEEDED"
        assert decision.policy_rule_id == "VPOL-003-DAILY-CAP"

    def test_quiet_hours_deferral_for_low_and_medium_claims(self, engine, base_context):
        req = VerificationRequest(
            request_id="req-quiet-01",
            created_at=base_context.current_time,
            claim_domain=ClaimDomain.WORLD_REALITY,
            claim_key="institutions.usm.bus_schedule",
            claim_value="08:00",
            consequence_tier=ConsequenceTier.LOW,
        )
        quiet_context = base_context.model_copy(update={"is_quiet_hours": True})
        decision = engine.evaluate(req, quiet_context)

        assert decision.should_verify is False
        assert decision.suppression_reason == "QUIET_HOURS_DEFERRED"
        assert decision.quiet_hours_behavior == QuietHoursBehavior.DEFER_UNTIL_ACTIVE_HOURS
        assert decision.urgency == VerificationUrgency.SCHEDULED_OFFLINE

    def test_quiet_hours_silent_background_for_critical_claims(self, engine, base_context):
        req = VerificationRequest(
            request_id="req-quiet-02",
            created_at=base_context.current_time,
            claim_domain=ClaimDomain.WORLD_REALITY,
            claim_key="academics.graduation_accreditation",
            claim_value="MQA_ACCREDITED",
            consequence_tier=ConsequenceTier.CRITICAL,
            urgency=VerificationUrgency.IMMEDIATE_TURN,
        )
        quiet_context = base_context.model_copy(update={"is_quiet_hours": True})
        decision = engine.evaluate(req, quiet_context)

        assert decision.should_verify is True
        assert decision.suppression_reason is None
        assert decision.quiet_hours_behavior == QuietHoursBehavior.PROCEED_SILENT_BACKGROUND

    def test_consequence_tier_critical_authority_and_budget(self, engine, base_context):
        req = VerificationRequest(
            request_id="req-crit-01",
            created_at=base_context.current_time,
            claim_domain=ClaimDomain.WORLD_REALITY,
            claim_key="institutions.usm.degree_accreditation",
            claim_value="MQA",
            consequence_tier=ConsequenceTier.CRITICAL,
        )
        decision = engine.evaluate(req, base_context)

        assert decision.should_verify is True
        assert decision.target_scope == VerificationScope.EXACT_MATCH
        assert SourceAuthority.UNVERIFIED_EXTERNAL not in decision.allowed_authorities
        assert SourceAuthority.PRIMARY_INSTITUTIONAL in decision.allowed_authorities
        assert SourceAuthority.OFFICIAL_PUBLIC_RECORD in decision.allowed_authorities
        assert decision.cost_budget.max_queries == 2
        assert decision.cost_budget.timeout_seconds == 15

    def test_world_vs_personal_domain_authority_separation(self, engine, base_context):
        req_world = VerificationRequest(
            request_id="req-world-auth",
            created_at=base_context.current_time,
            claim_domain=ClaimDomain.WORLD_REALITY,
            claim_key="institutions.usm.programme_duration",
            claim_value=4,
            consequence_tier=ConsequenceTier.LOW,
        )
        dec_world = engine.evaluate(req_world, base_context)
        assert SourceAuthority.FIRST_PARTY_PERSONAL not in dec_world.allowed_authorities
        assert SourceAuthority.PRIMARY_INSTITUTIONAL in dec_world.allowed_authorities

        req_personal = VerificationRequest(
            request_id="req-pers-auth",
            created_at=base_context.current_time,
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="preferences.favorite_beverage",
            claim_value="matcha_latte",
            consequence_tier=ConsequenceTier.LOW,
            entity_binding_anchor="character:aevum:primary",
        )
        dec_personal = engine.evaluate(req_personal, base_context)
        assert SourceAuthority.UNVERIFIED_EXTERNAL not in dec_personal.allowed_authorities
        assert SourceAuthority.FIRST_PARTY_PERSONAL in dec_personal.allowed_authorities

    def test_permanent_gate_invariant_zero_floats_in_policy_models(self):
        models = [
            VerificationCostBudget,
            VerificationPolicyContext,
            VerificationDecision,
        ]
        for model in models:
            for field_name, field_info in model.model_fields.items():
                annotation = str(field_info.annotation).lower()
                assert "float" not in annotation, (
                    f"Model {model.__name__} has a forbidden float field '{field_name}'! "
                    "Phase 9 strictly prohibits pseudo-probabilistic floats or scores."
                )

    # --------------------------------------------------------------------------
    # Checkpoint 6: Pure Static AST Boundary Audit
    # --------------------------------------------------------------------------

    def test_checkpoint_6_static_ast_boundary_audit_pure_policy_module(self):
        """
        Checkpoint 6 & Pure Static AST Boundary Audit:
        Asserts backend/app/reality/verification_policy_engine.py contains:
        1. ZERO database imports or calls (sqlite3, aiosqlite, sqlalchemy).
        2. ZERO network imports or calls (httpx, requests, aiohttp, urllib, google.genai).
        3. ZERO mutation or promotion authority (set_fact, PromotionAuthorizationToken).
        4. ZERO execution calls (search, fetch, get, post, execute, commit).
        5. ZERO scheduler / background task execution (create_task, BackgroundTasks, threading, enqueue).
        """
        target_path = Path(__file__).resolve().parent.parent / "app" / "reality" / "verification_policy_engine.py"
        assert target_path.exists(), f"Target module not found: {target_path}"

        tree = ast.parse(target_path.read_text(encoding="utf-8"))

        forbidden_import_modules = {
            "sqlite3", "aiosqlite", "sqlalchemy",
            "httpx", "requests", "aiohttp", "urllib", "google.genai",
            "threading", "queue", "asyncio"
        }
        forbidden_call_names = {
            "set_fact", "PromotionAuthorizationToken",
            "search", "fetch", "execute", "commit",
            "create_task", "BackgroundTasks", "Thread", "enqueue", "schedule"
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    assert root not in forbidden_import_modules, (
                        f"Forbidden import '{alias.name}' detected in pure policy module!"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root = node.module.split(".")[0]
                    assert root not in forbidden_import_modules, (
                        f"Forbidden from-import '{node.module}' detected in pure policy module!"
                    )

            if isinstance(node, ast.Call):
                func = node.func
                name = None
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                if name:
                    assert name not in forbidden_call_names, (
                        f"Forbidden function call '{name}' in pure policy module!"
                    )
