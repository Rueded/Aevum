"""
test_phase93_source_evaluation.py — Phase 9.3 Observation Adapters & Epistemic Source Evaluation Test Suite

Verifies:
1. Four-Layer Epistemic Hierarchy preservation:
   ExternalObservation != Evidence != VerificationFinding != Truth != Canonical Reality
2. Decoupled Observation Adapters (Issue 5: adapters produce ExternalObservation only).
3. Lock 3: Source Authority != Truth (High authority is input factor, not automatic truth).
4. Lock 8: Identity Binding Isolation (External entity match != Aevum match; unanchored homonyms rejected).
5. Deterministic Conflict Resolution (Issue 3 / ADR-020.3: Authority dominance, Freshness dominance,
   Zero majority count, Symmetrical conflicts strictly AMBIGUOUS_CONFLICT).
6. World vs. Personal domain evaluation consistency (Lock 4).
7. Zero float scores / probabilities (Permanent Note A).
8. Pure static AST boundary audit across observation_adapters.py and epistemic_source_evaluator.py.
"""

import ast
from datetime import datetime, timezone
from pathlib import Path
import pytest
from pydantic import ValidationError

from app.reality.verification_models import (
    ClaimDomain,
    SourceAuthority,
    SourceKind,
    ClaimEpistemicStatus,
    VerificationScope,
    VerificationUrgency,
    EvidenceFreshness,
    ConsequenceTier,
    VerificationProvenance,
    ExternalObservation,
    VerificationRequest,
    VerificationFinding,
)
from app.reality.verification_policy_engine import (
    VerificationPrivacyScope,
    QuietHoursBehavior,
    RateLimitClass,
    VerificationCostBudget,
    VerificationDecision,
)
from app.reality.observation_adapters import (
    WorldKnowledgeObservationAdapter,
    InMemoryObservationAdapter,
)
from app.reality.epistemic_source_evaluator import (
    EpistemicSourceEvaluator,
    IdentityBindingEvaluation,
)


class TestPhase93SourceEvaluation:

    @pytest.fixture
    def evaluator(self) -> EpistemicSourceEvaluator:
        return EpistemicSourceEvaluator(evaluator_version="1.0.0")

    @pytest.fixture
    def base_world_request(self) -> VerificationRequest:
        return VerificationRequest(
            request_id="req-world-01",
            created_at=datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc),
            claim_domain=ClaimDomain.WORLD_REALITY,
            claim_key="education.usm.programme_duration",
            claim_value=4,
            consequence_tier=ConsequenceTier.HIGH,
            urgency=VerificationUrgency.IMMEDIATE_TURN,
        )

    @pytest.fixture
    def base_world_decision(self, base_world_request) -> VerificationDecision:
        return VerificationDecision(
            decision_id="dec-world-01",
            request_id=base_world_request.request_id,
            claim_key=base_world_request.claim_key,
            claim_domain=base_world_request.claim_domain,
            consequence_tier=base_world_request.consequence_tier,
            should_verify=True,
            suppression_reason=None,
            target_scope=VerificationScope.EXACT_MATCH,
            urgency=base_world_request.urgency,
            privacy_scope=VerificationPrivacyScope.PUBLIC_DATA_ONLY,
            allowed_authorities=(
                SourceAuthority.PRIMARY_INSTITUTIONAL,
                SourceAuthority.OFFICIAL_PUBLIC_RECORD,
                SourceAuthority.CORROBORATED_SECONDARY,
                SourceAuthority.UNVERIFIED_EXTERNAL,
            ),
            allowed_source_kinds=(
                SourceKind.INSTITUTIONAL_PORTAL,
                SourceKind.PUBLIC_REGISTRY,
                SourceKind.WEB_DOCUMENT,
            ),
            cost_budget=VerificationCostBudget(max_queries=2, timeout_seconds=10),
            quiet_hours_behavior=QuietHoursBehavior.PROCEED_SILENT_BACKGROUND,
            policy_rule_id="VPOL-005-HIGH",
            rationale="World reality authorized for verification.",
            evaluated_at=datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc),
        )

    # --------------------------------------------------------------------------
    # 1. Decoupled Observation Adapters
    # --------------------------------------------------------------------------

    def test_world_knowledge_observation_adapter_pure_observation(self):
        """
        Verify Issue 5:
        Adapter packages WorldKnowledgeRegistry into ExternalObservation without evaluating truth.
        """
        adapter = WorldKnowledgeObservationAdapter()
        obs_tuple = adapter.observe(
            claim_key="geography.usm.campus_location",
            allowed_source_kinds=(SourceKind.PUBLIC_REGISTRY,),
            limit=3,
        )
        assert len(obs_tuple) > 0
        obs = obs_tuple[0]
        assert isinstance(obs, ExternalObservation)
        assert obs.source_provenance.source_authority == SourceAuthority.PRIMARY_INSTITUTIONAL
        assert obs.source_provenance.source_kind == SourceKind.PUBLIC_REGISTRY
        assert "Penang" in str(obs.structured_payload.get("value"))
        # Adapter does NOT declare truth or epistemic status
        assert not hasattr(obs, "epistemic_status")
        assert not hasattr(obs, "is_verified")

    def test_in_memory_observation_adapter_filtering(self):
        """
        Verify InMemoryObservationAdapter matches keys and filters by allowed source kinds.
        """
        now = datetime.now(timezone.utc)
        obs_valid = ExternalObservation(
            observation_id="obs-mock-01",
            source_provenance=VerificationProvenance(
                source_id="src-01",
                source_authority=SourceAuthority.PRIMARY_INSTITUTIONAL,
                source_kind=SourceKind.INSTITUTIONAL_PORTAL,
                retrieval_timestamp=now,
            ),
            observed_content_snippet="Programme duration is 4 years.",
            structured_payload={"key": "education.usm.programme_duration", "value": 4},
            observed_at=now,
        )
        obs_disallowed_kind = ExternalObservation(
            observation_id="obs-mock-02",
            source_provenance=VerificationProvenance(
                source_id="src-02",
                source_authority=SourceAuthority.UNVERIFIED_EXTERNAL,
                source_kind=SourceKind.USER_DIALOGUE,
                retrieval_timestamp=now,
            ),
            observed_content_snippet="Dialogue chat",
            structured_payload={"key": "education.usm.programme_duration", "value": 4},
            observed_at=now,
        )

        adapter = InMemoryObservationAdapter([obs_valid, obs_disallowed_kind])
        results = adapter.observe(
            claim_key="education.usm.programme_duration",
            allowed_source_kinds=(SourceKind.INSTITUTIONAL_PORTAL,),
        )
        assert len(results) == 1
        assert results[0].observation_id == "obs-mock-01"

    # --------------------------------------------------------------------------
    # 2. Lock 3: Source Authority != Truth
    # --------------------------------------------------------------------------

    def test_lock_3_primary_institutional_contradiction_yields_contradicted_not_truth(
        self, evaluator, base_world_request, base_world_decision
    ):
        """
        Verify Lock 3:
        A PRIMARY_INSTITUTIONAL source does NOT automatically mean the claim is SUPPORTED.
        If the institutional source asserts a different duration (3 years vs claimed 4),
        the verdict must be CONTRADICTED.
        """
        now = datetime.now(timezone.utc)
        obs_contradicting = ExternalObservation(
            observation_id="obs-usm-handbook",
            source_provenance=VerificationProvenance(
                source_id="usm_official_handbook",
                source_authority=SourceAuthority.PRIMARY_INSTITUTIONAL,
                source_kind=SourceKind.INSTITUTIONAL_PORTAL,
                retrieval_timestamp=now,
            ),
            observed_content_snippet="Official handbook lists Bachelor duration as 3 years.",
            structured_payload={"key": "education.usm.programme_duration", "value": 3},
            observed_at=now,
        )

        finding = evaluator.evaluate_observations(
            request=base_world_request,
            decision=base_world_decision,
            observations=[obs_contradicting],
            finding_id="find-lock3-01",
        )

        assert finding.epistemic_status == ClaimEpistemicStatus.CONTRADICTED
        assert "contradict asserted claim value '4'" in (finding.contradiction_details or "")
        assert finding.provenance.evaluator_name == "EpistemicSourceEvaluator"

    def test_out_of_scope_observations_yield_out_of_scope(
        self, evaluator, base_world_request, base_world_decision
    ):
        """
        Observations that do not relate to the claim key or asserted value yield OUT_OF_SCOPE.
        """
        now = datetime.now(timezone.utc)
        obs_irrelevant = ExternalObservation(
            observation_id="obs-weather",
            source_provenance=VerificationProvenance(
                source_id="usm_portal",
                source_authority=SourceAuthority.PRIMARY_INSTITUTIONAL,
                source_kind=SourceKind.INSTITUTIONAL_PORTAL,
                retrieval_timestamp=now,
            ),
            observed_content_snippet="Today campus temperature is 31 degrees Celsius.",
            structured_payload={"key": "weather.penang", "value": 31},
            observed_at=now,
        )

        finding = evaluator.evaluate_observations(
            request=base_world_request,
            decision=base_world_decision,
            observations=[obs_irrelevant],
        )

        assert finding.epistemic_status == ClaimEpistemicStatus.OUT_OF_SCOPE
        assert finding.scope == VerificationScope.UNMATCHED

    # --------------------------------------------------------------------------
    # 3. Lock 8: Identity Binding Isolation (External Entity != Aevum)
    # --------------------------------------------------------------------------

    def test_lock_8_external_entity_homonym_strictly_rejected(self, evaluator):
        """
        Verify Lock 8:
        An external observation mentions an entity with the exact same name ("Aevum"),
        but lacks the authenticated identity_binding_anchor.
        Evaluator strictly rejects binding it to Aevum's personal biography!
        """
        now = datetime.now(timezone.utc)
        req_personal = VerificationRequest(
            request_id="req-pers-lock8",
            created_at=now,
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="biography.hackathon_winner",
            claim_value=True,
            consequence_tier=ConsequenceTier.HIGH,
            entity_binding_anchor="character:aevum:primary",
        )
        decision_personal = VerificationDecision(
            decision_id="dec-pers-lock8",
            request_id=req_personal.request_id,
            claim_key=req_personal.claim_key,
            claim_domain=req_personal.claim_domain,
            consequence_tier=req_personal.consequence_tier,
            should_verify=True,
            suppression_reason=None,
            target_scope=VerificationScope.EXACT_MATCH,
            urgency=VerificationUrgency.IMMEDIATE_TURN,
            privacy_scope=VerificationPrivacyScope.FIRST_PARTY_CONSENTED,
            allowed_authorities=(
                SourceAuthority.FIRST_PARTY_PERSONAL,
                SourceAuthority.CORROBORATED_SECONDARY,
            ),
            allowed_source_kinds=(
                SourceKind.USER_DIALOGUE,
                SourceKind.PUBLIC_REGISTRY,
            ),
            cost_budget=VerificationCostBudget(),
            quiet_hours_behavior=QuietHoursBehavior.PROCEED_SILENT_BACKGROUND,
            policy_rule_id="VPOL-005-HIGH",
            rationale="Personal verification authorized.",
            evaluated_at=now,
        )

        # Observation with SAME NAME ("Aevum"), but WITHOUT entity_binding_anchor!
        obs_homonym = ExternalObservation(
            observation_id="obs-web-homonym",
            source_provenance=VerificationProvenance(
                source_id="news_article",
                source_authority=SourceAuthority.CORROBORATED_SECONDARY,
                source_kind=SourceKind.PUBLIC_REGISTRY,
                retrieval_timestamp=now,
            ),
            observed_content_snippet="Aevum won the national hackathon competition in 2024.",
            structured_payload={"key": "biography.hackathon_winner", "value": True},
            observed_at=now,
            observed_entity_name="Aevum",  # Homonym match only!
        )

        finding = evaluator.evaluate_observations(
            request=req_personal,
            decision=decision_personal,
            observations=[obs_homonym],
        )

        # Must NOT support personal biography!
        assert finding.epistemic_status == ClaimEpistemicStatus.AMBIGUOUS_CONFLICT
        assert "Lock 8 Rejection" in finding.provenance.rationale
        assert "EVAL-004-LOCK8-IDENTITY-BINDING" in finding.provenance.rule_ids_applied

    def test_lock_8_authenticated_entity_anchor_permitted(self, evaluator):
        """
        When observation explicitly carries the authenticated entity_binding_anchor,
        identity binding succeeds and can corroborate personal claims.
        """
        now = datetime.now(timezone.utc)
        req_personal = VerificationRequest(
            request_id="req-pers-auth",
            created_at=now,
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="biography.hackathon_winner",
            claim_value=True,
            consequence_tier=ConsequenceTier.HIGH,
            entity_binding_anchor="character:aevum:primary",
        )
        decision_personal = VerificationDecision(
            decision_id="dec-pers-auth",
            request_id=req_personal.request_id,
            claim_key=req_personal.claim_key,
            claim_domain=req_personal.claim_domain,
            consequence_tier=req_personal.consequence_tier,
            should_verify=True,
            suppression_reason=None,
            target_scope=VerificationScope.EXACT_MATCH,
            urgency=VerificationUrgency.IMMEDIATE_TURN,
            privacy_scope=VerificationPrivacyScope.FIRST_PARTY_CONSENTED,
            allowed_authorities=(
                SourceAuthority.FIRST_PARTY_PERSONAL,
                SourceAuthority.CORROBORATED_SECONDARY,
            ),
            allowed_source_kinds=(
                SourceKind.USER_DIALOGUE,
                SourceKind.PUBLIC_REGISTRY,
            ),
            cost_budget=VerificationCostBudget(),
            quiet_hours_behavior=QuietHoursBehavior.PROCEED_SILENT_BACKGROUND,
            policy_rule_id="VPOL-005-HIGH",
            rationale="Personal verification authorized.",
            evaluated_at=now,
        )

        # Observation with authenticated anchor in structured payload
        obs_authenticated = ExternalObservation(
            observation_id="obs-verified-cert",
            source_provenance=VerificationProvenance(
                source_id="student_registry_portal",
                source_authority=SourceAuthority.CORROBORATED_SECONDARY,
                source_kind=SourceKind.PUBLIC_REGISTRY,
                retrieval_timestamp=now,
            ),
            observed_content_snippet="Authenticated certificate for anchor:character:aevum:primary.",
            structured_payload={
                "key": "biography.hackathon_winner",
                "value": True,
                "entity_binding_anchor": "character:aevum:primary",
            },
            observed_at=now,
            observed_entity_name="Aevum",
        )

        finding = evaluator.evaluate_observations(
            request=req_personal,
            decision=decision_personal,
            observations=[obs_authenticated],
        )

        assert finding.epistemic_status == ClaimEpistemicStatus.SUPPORTED

    # --------------------------------------------------------------------------
    # 4. Issue 3: Deterministic Conflict Resolution (Zero Majority Voting)
    # --------------------------------------------------------------------------

    def test_conflict_resolution_authority_dominance_over_majority(
        self, evaluator, base_world_request, base_world_decision
    ):
        """
        Verify ADR-020.3 & Issue 3:
        1 PRIMARY_INSTITUTIONAL source (asserting 4 years)
        vs. 5 UNVERIFIED_EXTERNAL sources (asserting 3 years).
        Authority dominance rule dictates that PRIMARY_INSTITUTIONAL dominates!
        Claim is SUPPORTED, strictly rejecting the 5:1 majority vote!
        """
        now = datetime.now(timezone.utc)
        obs_institutional = ExternalObservation(
            observation_id="obs-usm-official-syllabus",
            source_provenance=VerificationProvenance(
                source_id="usm_official_portal",
                source_authority=SourceAuthority.PRIMARY_INSTITUTIONAL,
                source_kind=SourceKind.INSTITUTIONAL_PORTAL,
                retrieval_timestamp=now,
            ),
            observed_content_snippet="USM Official Syllabus: Computer Science requires 4 years.",
            structured_payload={"key": "education.usm.programme_duration", "value": 4},
            observed_at=now,
        )

        # 5 distinct unverified blog posts claiming 3 years
        obs_blogs = [
            ExternalObservation(
                observation_id=f"obs-blog-{i}",
                source_provenance=VerificationProvenance(
                    source_id=f"random_blog_{i}",
                    source_authority=SourceAuthority.UNVERIFIED_EXTERNAL,
                    source_kind=SourceKind.WEB_DOCUMENT,
                    retrieval_timestamp=now,
                ),
                observed_content_snippet="Blog says CS is 3 years.",
                structured_payload={"key": "education.usm.programme_duration", "value": 3},
                observed_at=now,
            )
            for i in range(5)
        ]

        all_obs = [obs_institutional] + obs_blogs

        finding = evaluator.evaluate_observations(
            request=base_world_request,
            decision=base_world_decision,
            observations=all_obs,
        )

        # Must be SUPPORTED by authority dominance, not CONTRADICTED by 5:1 majority!
        assert finding.epistemic_status == ClaimEpistemicStatus.SUPPORTED
        assert "EVAL-008-AUTHORITY-DOMINANCE-SUPPORT" in finding.provenance.rule_ids_applied

    def test_conflict_resolution_freshness_dominance(
        self, evaluator, base_world_request, base_world_decision
    ):
        """
        When authorities are equal, CURRENT evidence dominates SUPERSEDED_OUTDATED evidence.
        """
        now = datetime.now(timezone.utc)
        obs_current = ExternalObservation(
            observation_id="obs-gazette-current",
            source_provenance=VerificationProvenance(
                source_id="gazette_2025",
                source_authority=SourceAuthority.OFFICIAL_PUBLIC_RECORD,
                source_kind=SourceKind.PUBLIC_REGISTRY,
                retrieval_timestamp=now,
            ),
            observed_content_snippet="Gazette 2025: Duration is 4 years.",
            structured_payload={
                "key": "education.usm.programme_duration",
                "value": 4,
                "freshness": EvidenceFreshness.CURRENT.value,
            },
            observed_at=now,
        )
        obs_outdated = ExternalObservation(
            observation_id="obs-gazette-old",
            source_provenance=VerificationProvenance(
                source_id="gazette_2010",
                source_authority=SourceAuthority.OFFICIAL_PUBLIC_RECORD,
                source_kind=SourceKind.PUBLIC_REGISTRY,
                retrieval_timestamp=now,
            ),
            observed_content_snippet="Gazette 2010: Duration was 3 years.",
            structured_payload={
                "key": "education.usm.programme_duration",
                "value": 3,
                "freshness": EvidenceFreshness.SUPERSEDED_OUTDATED.value,
            },
            observed_at=now,
        )

        finding = evaluator.evaluate_observations(
            request=base_world_request,
            decision=base_world_decision,
            observations=[obs_current, obs_outdated],
        )

        assert finding.epistemic_status == ClaimEpistemicStatus.SUPPORTED
        assert "EVAL-009-FRESHNESS-DOMINANCE-SUPPORT" in finding.provenance.rule_ids_applied

    def test_conflict_resolution_equal_standing_yields_ambiguous_conflict(
        self, evaluator, base_world_request, base_world_decision
    ):
        """
        When conflicting sources have IDENTICAL authority rank and IDENTICAL freshness,
        the system strictly evaluates to AMBIGUOUS_CONFLICT without picking a winner.
        """
        now = datetime.now(timezone.utc)
        obs_a = ExternalObservation(
            observation_id="obs-inst-a",
            source_provenance=VerificationProvenance(
                source_id="usm_faculty_site",
                source_authority=SourceAuthority.PRIMARY_INSTITUTIONAL,
                source_kind=SourceKind.INSTITUTIONAL_PORTAL,
                retrieval_timestamp=now,
            ),
            observed_content_snippet="Faculty page says 4 years.",
            structured_payload={
                "key": "education.usm.programme_duration",
                "value": 4,
                "freshness": EvidenceFreshness.CURRENT.value,
            },
            observed_at=now,
        )
        obs_b = ExternalObservation(
            observation_id="obs-inst-b",
            source_provenance=VerificationProvenance(
                source_id="usm_admissions_site",
                source_authority=SourceAuthority.PRIMARY_INSTITUTIONAL,
                source_kind=SourceKind.INSTITUTIONAL_PORTAL,
                retrieval_timestamp=now,
            ),
            observed_content_snippet="Admissions page says 3 years.",
            structured_payload={
                "key": "education.usm.programme_duration",
                "value": 3,
                "freshness": EvidenceFreshness.CURRENT.value,
            },
            observed_at=now,
        )

        finding = evaluator.evaluate_observations(
            request=base_world_request,
            decision=base_world_decision,
            observations=[obs_a, obs_b],
        )

        assert finding.epistemic_status == ClaimEpistemicStatus.AMBIGUOUS_CONFLICT
        assert "EVAL-010-IRRESOLVABLE-CONFLICT-AMBIGUOUS" in finding.provenance.rule_ids_applied
        assert "Zero majority voting applied" in (finding.contradiction_details or "")

    # --------------------------------------------------------------------------
    # 5. Permanent Note A: Zero Floats
    # --------------------------------------------------------------------------

    def test_permanent_gate_invariant_zero_floats_in_findings(
        self, evaluator, base_world_request, base_world_decision
    ):
        """Assert VerificationFinding emitted by 9.3 has absolute zero float fields."""
        now = datetime.now(timezone.utc)
        obs = ExternalObservation(
            observation_id="obs-chk-float",
            source_provenance=VerificationProvenance(
                source_id="src-01",
                source_authority=SourceAuthority.PRIMARY_INSTITUTIONAL,
                source_kind=SourceKind.INSTITUTIONAL_PORTAL,
                retrieval_timestamp=now,
            ),
            observed_content_snippet="Duration is 4 years.",
            structured_payload={"key": "education.usm.programme_duration", "value": 4},
            observed_at=now,
        )
        finding = evaluator.evaluate_observations(
            request=base_world_request,
            decision=base_world_decision,
            observations=[obs],
        )

        for field_name, field_val in finding.model_dump().items():
            assert not isinstance(field_val, float), (
                f"Field '{field_name}' in VerificationFinding is a forbidden float ({field_val})!"
            )

    # --------------------------------------------------------------------------
    # 6. Pure Static AST Boundary Audit
    # --------------------------------------------------------------------------

    def test_static_ast_boundary_audit_observation_adapters(self):
        """
        Asserts observation_adapters.py contains:
        1. ZERO database imports or calls (sqlite3, aiosqlite, sqlalchemy).
        2. ZERO network imports or calls (httpx, requests, aiohttp, urllib, google.genai).
        3. ZERO mutation or promotion authority (set_fact, PromotionAuthorizationToken).
        4. ZERO scheduler / background task execution (create_task, threading, enqueue).
        """
        path = Path(__file__).resolve().parent.parent / "app" / "reality" / "observation_adapters.py"
        assert path.exists()

        tree = ast.parse(path.read_text(encoding="utf-8"))
        forbidden_import_modules = {
            "sqlite3", "aiosqlite", "sqlalchemy",
            "httpx", "requests", "aiohttp", "urllib", "google.genai",
            "threading", "queue", "asyncio"
        }
        forbidden_call_names = {
            "set_fact", "PromotionAuthorizationToken",
            "create_task", "BackgroundTasks", "Thread", "enqueue", "schedule"
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    assert root not in forbidden_import_modules, f"Forbidden import '{alias.name}'!"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root = node.module.split(".")[0]
                    assert root not in forbidden_import_modules, f"Forbidden from-import '{node.module}'!"
            if isinstance(node, ast.Call):
                name = None
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                if name:
                    assert name not in forbidden_call_names, f"Forbidden call '{name}'!"

    def test_static_ast_boundary_audit_epistemic_source_evaluator(self):
        """
        Asserts epistemic_source_evaluator.py contains:
        1. ZERO database imports or calls (sqlite3, aiosqlite, sqlalchemy).
        2. ZERO network imports or calls (httpx, requests, aiohttp, urllib, google.genai).
        3. ZERO mutation or promotion authority (set_fact, PromotionAuthorizationToken).
        4. ZERO scheduler / background task execution (create_task, threading, enqueue).
        """
        path = Path(__file__).resolve().parent.parent / "app" / "reality" / "epistemic_source_evaluator.py"
        assert path.exists()

        tree = ast.parse(path.read_text(encoding="utf-8"))
        forbidden_import_modules = {
            "sqlite3", "aiosqlite", "sqlalchemy",
            "httpx", "requests", "aiohttp", "urllib", "google.genai",
            "threading", "queue", "asyncio"
        }
        forbidden_call_names = {
            "set_fact", "PromotionAuthorizationToken",
            "create_task", "BackgroundTasks", "Thread", "enqueue", "schedule"
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    assert root not in forbidden_import_modules, f"Forbidden import '{alias.name}'!"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root = node.module.split(".")[0]
                    assert root not in forbidden_import_modules, f"Forbidden from-import '{node.module}'!"
            if isinstance(node, ast.Call):
                name = None
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                if name:
                    assert name not in forbidden_call_names, f"Forbidden call '{name}'!"

    # --------------------------------------------------------------------------
    # 7. Golden Semantic Invariant Tests (GC-9.3-A ~ GC-9.3-D)
    # --------------------------------------------------------------------------

    def test_gc_9_3_a_authority_does_not_override_scope(
        self, evaluator, base_world_request, base_world_decision
    ):
        """
        GC-9.3-A: Authority Does Not Override Scope.
        PRIMARY_INSTITUTIONAL + wrong programme / wrong jurisdiction -> OUT_OF_SCOPE.
        Official source about X != official evidence about Y.
        High authority rank NEVER overrides scope mismatch.
        """
        now = datetime.now(timezone.utc)
        # Institutional portal source, but discussing UK jurisdiction instead of USM/Malaysia
        obs_wrong_jurisdiction = ExternalObservation(
            observation_id="obs-wrong-jurisdiction",
            source_provenance=VerificationProvenance(
                source_id="oxford_official_handbook",
                source_authority=SourceAuthority.PRIMARY_INSTITUTIONAL,
                source_kind=SourceKind.INSTITUTIONAL_PORTAL,
                retrieval_timestamp=now,
            ),
            observed_content_snippet="Oxford official syllabus: duration is 4 years.",
            structured_payload={
                "key": "education.usm.programme_duration",
                "value": 4,
                "jurisdiction": "UK",
            },
            observed_at=now,
        )

        finding_jur = evaluator.evaluate_observations(
            request=base_world_request,
            decision=base_world_decision,
            observations=[obs_wrong_jurisdiction],
        )
        assert finding_jur.epistemic_status == ClaimEpistemicStatus.OUT_OF_SCOPE
        assert finding_jur.provenance.rule_ids_applied == ("EVAL-005-OUT-OF-SCOPE",)

        # Institutional portal source, but discussing Medicine programme instead of CS
        req_cs = VerificationRequest(
            request_id="req-usm-cs",
            created_at=now,
            claim_domain=ClaimDomain.WORLD_REALITY,
            claim_key="education.usm.cs.programme_duration",
            claim_value=4,
            consequence_tier=ConsequenceTier.HIGH,
        )
        dec_cs = VerificationDecision(
            decision_id="dec-usm-cs",
            request_id=req_cs.request_id,
            claim_key=req_cs.claim_key,
            claim_domain=req_cs.claim_domain,
            consequence_tier=req_cs.consequence_tier,
            should_verify=True,
            target_scope=VerificationScope.EXACT_MATCH,
            urgency=VerificationUrgency.BACKGROUND_ROUTINE,
            privacy_scope=VerificationPrivacyScope.PUBLIC_DATA_ONLY,
            allowed_authorities=(SourceAuthority.PRIMARY_INSTITUTIONAL,),
            allowed_source_kinds=(SourceKind.INSTITUTIONAL_PORTAL,),
            cost_budget=VerificationCostBudget(max_queries=2, timeout_seconds=10),
            quiet_hours_behavior=QuietHoursBehavior.PROCEED_SILENT_BACKGROUND,
            policy_rule_id="VPOL-005-HIGH",
            rationale="Authorized",
            evaluated_at=now,
        )
        obs_wrong_programme = ExternalObservation(
            observation_id="obs-wrong-programme",
            source_provenance=VerificationProvenance(
                source_id="usm_medicine_handbook",
                source_authority=SourceAuthority.PRIMARY_INSTITUTIONAL,
                source_kind=SourceKind.INSTITUTIONAL_PORTAL,
                retrieval_timestamp=now,
            ),
            observed_content_snippet="USM School of Medicine official MBBS handbook lists 5 years.",
            structured_payload={
                "key": "education.usm.cs.programme_duration",
                "value": 4,
                "programme": "Medicine",
            },
            observed_at=now,
        )
        finding_prog = evaluator.evaluate_observations(
            request=req_cs,
            decision=dec_cs,
            observations=[obs_wrong_programme],
        )
        assert finding_prog.epistemic_status == ClaimEpistemicStatus.OUT_OF_SCOPE
        assert finding_prog.provenance.rule_ids_applied == ("EVAL-005-OUT-OF-SCOPE",)

    def test_gc_9_3_b_authority_does_not_override_freshness(
        self, evaluator, base_world_request, base_world_decision
    ):
        """
        GC-9.3-B: Authority Does Not Override Freshness.
        PRIMARY_INSTITUTIONAL + SUPERSEDED vs CURRENT applicable source:
        An outdated / superseded source CANNOT dominate an active current source.
        """
        now = datetime.now(timezone.utc)
        # Outdated institutional handbook claiming 4 years
        obs_superseded_inst = ExternalObservation(
            observation_id="obs-old-handbook",
            source_provenance=VerificationProvenance(
                source_id="usm_handbook_2005",
                source_authority=SourceAuthority.PRIMARY_INSTITUTIONAL,
                source_kind=SourceKind.INSTITUTIONAL_PORTAL,
                retrieval_timestamp=now,
            ),
            observed_content_snippet="2005 Handbook lists Bachelor of CS as 4 years.",
            structured_payload={
                "key": "education.usm.programme_duration",
                "value": 4,
                "freshness": EvidenceFreshness.SUPERSEDED_OUTDATED.value,
            },
            observed_at=now,
        )
        # Current institutional senate gazette claiming 3 years
        obs_current_inst = ExternalObservation(
            observation_id="obs-new-senate-gazette",
            source_provenance=VerificationProvenance(
                source_id="usm_senate_gazette_2025",
                source_authority=SourceAuthority.PRIMARY_INSTITUTIONAL,
                source_kind=SourceKind.INSTITUTIONAL_PORTAL,
                retrieval_timestamp=now,
            ),
            observed_content_snippet="2025 Senate Gazette announces revised 3-year curriculum.",
            structured_payload={
                "key": "education.usm.programme_duration",
                "value": 3,
                "freshness": EvidenceFreshness.CURRENT.value,
            },
            observed_at=now,
        )

        finding = evaluator.evaluate_observations(
            request=base_world_request,
            decision=base_world_decision,
            observations=[obs_superseded_inst, obs_current_inst],
        )

        # The superseded source claiming 4 CANNOT dominate the current source claiming 3
        assert finding.epistemic_status == ClaimEpistemicStatus.CONTRADICTED
        assert finding.provenance.rule_ids_applied == ("EVAL-009-FRESHNESS-DOMINANCE-CONTRADICT",)
        assert finding.freshness == EvidenceFreshness.CURRENT

    def test_gc_9_3_c_identity_ambiguity_not_factual_contradiction(self, evaluator):
        """
        GC-9.3-C: Identity Ambiguity != Factual Contradiction.
        Missing identity anchor yields AMBIGUOUS_CONFLICT under EVAL-004-LOCK8-IDENTITY-BINDING.
        It is strictly an identity-binding failure, NOT a factual contradiction.
        It must never be classified as CONTRADICTED and must never trigger refutation routing.
        """
        now = datetime.now(timezone.utc)
        req_personal = VerificationRequest(
            request_id="req-pers-gc-c",
            created_at=now,
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="biography.published_first_author_paper",
            claim_value=True,
            consequence_tier=ConsequenceTier.HIGH,
            entity_binding_anchor="character:aevum:primary",
        )
        decision_personal = VerificationDecision(
            decision_id="dec-pers-gc-c",
            request_id=req_personal.request_id,
            claim_key=req_personal.claim_key,
            claim_domain=req_personal.claim_domain,
            consequence_tier=req_personal.consequence_tier,
            should_verify=True,
            target_scope=VerificationScope.EXACT_MATCH,
            urgency=VerificationUrgency.BACKGROUND_ROUTINE,
            privacy_scope=VerificationPrivacyScope.PUBLIC_DATA_ONLY,
            allowed_authorities=(SourceAuthority.OFFICIAL_PUBLIC_RECORD, SourceAuthority.PRIMARY_INSTITUTIONAL),
            allowed_source_kinds=(SourceKind.PUBLIC_REGISTRY,),
            cost_budget=VerificationCostBudget(max_queries=2, timeout_seconds=10),
            quiet_hours_behavior=QuietHoursBehavior.PROCEED_SILENT_BACKGROUND,
            policy_rule_id="VPOL-005-HIGH",
            rationale="Personal reality authorized with explicit anchor.",
            evaluated_at=now,
        )

        # Observation asserts False (no papers found), but entity is unanchored homonym
        obs_homonym = ExternalObservation(
            observation_id="obs-homonym-record",
            source_provenance=VerificationProvenance(
                source_id="dblp_registry",
                source_authority=SourceAuthority.OFFICIAL_PUBLIC_RECORD,
                source_kind=SourceKind.PUBLIC_REGISTRY,
                retrieval_timestamp=now,
            ),
            observed_content_snippet="Entity 'Aevum' has 0 indexed first-author publications.",
            structured_payload={"key": "biography.published_first_author_paper", "value": False},
            observed_at=now,
            observed_entity_name="Aevum",  # Homonym name without anchor!
        )

        finding = evaluator.evaluate_observations(
            request=req_personal,
            decision=decision_personal,
            observations=[obs_homonym],
        )

        # Crucial: Must be AMBIGUOUS_CONFLICT, NEVER CONTRADICTED!
        assert finding.epistemic_status == ClaimEpistemicStatus.AMBIGUOUS_CONFLICT
        assert finding.epistemic_status != ClaimEpistemicStatus.CONTRADICTED
        assert finding.provenance.rule_ids_applied == ("EVAL-004-LOCK8-IDENTITY-BINDING",)
        assert "Identity ambiguity must never be interpreted as factual contradiction" in finding.provenance.rationale

    def test_gc_9_3_d_finding_cannot_become_evidence_in_process(
        self, evaluator, base_world_request, base_world_decision
    ):
        """
        GC-9.3-D: Finding Cannot Become Evidence In-Process.
        Verifies:
        1. EpistemicSourceEvaluator produces VerificationFinding, NOT VerificationEvidencePayload.
        2. Evaluator has zero mutation authority: does not create CandidateFact,
           does not touch CandidateRepository, does not write to RealityLedger,
           does not touch canonical reality.
        3. Request and decision are completely unmodified.
        """
        now = datetime.now(timezone.utc)
        obs = ExternalObservation(
            observation_id="obs-pure-finding",
            source_provenance=VerificationProvenance(
                source_id="usm_official",
                source_authority=SourceAuthority.PRIMARY_INSTITUTIONAL,
                source_kind=SourceKind.INSTITUTIONAL_PORTAL,
                retrieval_timestamp=now,
            ),
            observed_content_snippet="Programme duration is 4 years.",
            structured_payload={"key": "education.usm.programme_duration", "value": 4},
            observed_at=now,
        )

        finding = evaluator.evaluate_observations(
            request=base_world_request,
            decision=base_world_decision,
            observations=[obs],
        )

        # Output is strictly VerificationFinding
        assert isinstance(finding, VerificationFinding)
        assert finding.__class__.__name__ == "VerificationFinding"
        assert not hasattr(finding, "evidence_id")
        assert not hasattr(finding, "candidate_id")
        assert not hasattr(finding, "target_candidate_key")

        # Zero mutation: Base request and decision remain untouched
        assert base_world_request.claim_value == 4
        assert base_world_decision.should_verify is True

    def test_world_knowledge_cannot_verify_personal_claim_without_anchor(self, evaluator):
        """
        WorldKnowledgeObservation cannot produce PERSONAL_REALITY VerificationFinding
        without explicit personal claim + authenticated identity binding.
        """
        now = datetime.now(timezone.utc)
        req_personal = VerificationRequest(
            request_id="req-pers-wk-leak",
            created_at=now,
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="biography.education_degree_years",
            claim_value=4,
            consequence_tier=ConsequenceTier.HIGH,
            entity_binding_anchor="character:aevum:primary",
        )
        decision_personal = VerificationDecision(
            decision_id="dec-pers-wk-leak",
            request_id=req_personal.request_id,
            claim_key=req_personal.claim_key,
            claim_domain=req_personal.claim_domain,
            consequence_tier=req_personal.consequence_tier,
            should_verify=True,
            target_scope=VerificationScope.EXACT_MATCH,
            urgency=VerificationUrgency.BACKGROUND_ROUTINE,
            privacy_scope=VerificationPrivacyScope.PUBLIC_DATA_ONLY,
            allowed_authorities=(SourceAuthority.PRIMARY_INSTITUTIONAL,),
            allowed_source_kinds=(SourceKind.PUBLIC_REGISTRY,),
            cost_budget=VerificationCostBudget(max_queries=2, timeout_seconds=10),
            quiet_hours_behavior=QuietHoursBehavior.PROCEED_SILENT_BACKGROUND,
            policy_rule_id="VPOL-005-HIGH",
            rationale="Personal verification",
            evaluated_at=now,
        )

        # Observation drawn from WorldKnowledge registry (objective world fact)
        wk_adapter = WorldKnowledgeObservationAdapter()
        obs_tuple = wk_adapter.observe(
            claim_key="world.usm.main_campus",
            allowed_source_kinds=(SourceKind.PUBLIC_REGISTRY,),
        )

        finding = evaluator.evaluate_observations(
            request=req_personal,
            decision=decision_personal,
            observations=obs_tuple,
        )

        # World knowledge observation cannot produce SUPPORTED personal finding!
        assert finding.epistemic_status != ClaimEpistemicStatus.SUPPORTED
        assert finding.epistemic_status in (
            ClaimEpistemicStatus.INSUFFICIENT_EVIDENCE,
            ClaimEpistemicStatus.OUT_OF_SCOPE,
            ClaimEpistemicStatus.AMBIGUOUS_CONFLICT,
        )
