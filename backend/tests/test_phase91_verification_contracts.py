"""
test_phase91_verification_contracts.py — Phase 9.1 Verification Contracts & Schemas Test Suite

Verifies:
1. Two-dimensional decoupling of ClaimDomain and SourceAuthority.
2. Decoupling of VerificationJobStatus from ClaimEpistemicStatus.
3. Strict non-probabilistic representation (Permanent Note A: ZERO float fields, zero probabilities).
4. Provenance preservation in VerificationFinding and VerificationProvenance (Permanent Note C).
5. Lock 8 Entity Binding Isolation (personal claims require explicit entity anchor).
6. Temporal interval & key validation invariants.
7. Strict Pydantic immutability & extra="forbid".
8. VerificationEvidencePayload and VerificationInboxItem contracts.
9. Pure static AST boundary audit (zero network, zero DB, zero LLM, zero set_fact, zero evaluation logic).
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
    VerificationJobStatus,
    ClaimEpistemicStatus,
    VerificationScope,
    VerificationUrgency,
    EvidenceFreshness,
    ConsequenceTier,
    VerificationProvenance,
    ExternalObservation,
    VerificationRequest,
    VerificationEvaluationProvenance,
    VerificationFinding,
    VerificationEvidencePayload,
    VerificationInboxItem,
)


class TestPhase91VerificationContracts:

    def test_enums_completeness_and_distinctness(self):
        """Assert all categorical enums have distinct, non-empty values."""
        enums_to_check = [
            ClaimDomain,
            SourceAuthority,
            SourceKind,
            VerificationJobStatus,
            ClaimEpistemicStatus,
            VerificationScope,
            VerificationUrgency,
            EvidenceFreshness,
            ConsequenceTier,
        ]
        for enum_cls in enums_to_check:
            values = [m.value for m in enum_cls]
            assert len(values) == len(set(values)), f"Duplicate enum values in {enum_cls.__name__}"
            assert len(values) > 0, f"Empty enum {enum_cls.__name__}"

    def test_two_dimensional_authority_orthogonality(self):
        """
        Verify Issue 1 & Lock 4:
        ClaimDomain (what is claimed) and SourceAuthority (who asserts it) are orthogonal.
        """
        # Personal claim can originate from first party personal or unverified external
        assert ClaimDomain.PERSONAL_REALITY != ClaimDomain.WORLD_REALITY
        assert SourceAuthority.FIRST_PARTY_PERSONAL != SourceAuthority.PRIMARY_INSTITUTIONAL

        # Cross combinations are structurally valid and distinct
        personal_first_party = (ClaimDomain.PERSONAL_REALITY, SourceAuthority.FIRST_PARTY_PERSONAL)
        world_institutional = (ClaimDomain.WORLD_REALITY, SourceAuthority.PRIMARY_INSTITUTIONAL)
        world_unverified = (ClaimDomain.WORLD_REALITY, SourceAuthority.UNVERIFIED_EXTERNAL)

        assert personal_first_party != world_institutional
        assert world_institutional != world_unverified

    def test_decoupling_job_status_from_epistemic_status(self):
        """
        Verify Permanent Note B:
        Job execution lifecycle (VerificationJobStatus) is strictly decoupled from
        the cognitive outcome of the claim (ClaimEpistemicStatus).
        """
        job_states = {s.value for s in VerificationJobStatus}
        epistemic_states = {s.value for s in ClaimEpistemicStatus}

        # A job being COMPLETED does not imply SUPPORTED or CONTRADICTED
        assert VerificationJobStatus.COMPLETED.value not in epistemic_states
        assert ClaimEpistemicStatus.SUPPORTED.value not in job_states
        assert ClaimEpistemicStatus.INSUFFICIENT_EVIDENCE.value not in job_states

        # Overlap must be empty to prevent conceptual conflation
        assert len(job_states.intersection(epistemic_states)) == 0

    def test_permanent_gate_invariant_zero_floats_in_all_models(self):
        """
        Verify Permanent Note A:
        Absolute ZERO float fields in any Phase 9.1 DTO.
        Heuristics != Probabilities. Epistemic status must be categorical, not a float score.
        """
        models_to_audit = [
            VerificationProvenance,
            ExternalObservation,
            VerificationRequest,
            VerificationEvaluationProvenance,
            VerificationFinding,
            VerificationEvidencePayload,
            VerificationInboxItem,
        ]
        for model in models_to_audit:
            for field_name, field_info in model.model_fields.items():
                annotation = str(field_info.annotation)
                assert "float" not in annotation.lower(), (
                    f"Model {model.__name__} has a forbidden float field '{field_name}'! "
                    "Phase 9 strictly prohibits pseudo-probabilistic floats or confidence scores."
                )

    def test_lock_8_entity_binding_isolation(self):
        """
        Verify Lock 8 & Issue 6:
        Personal reality claims require an explicit entity_binding_anchor to prevent
        unanchored entity-name aliasing. World claims do not require it.
        """
        now = datetime.now(timezone.utc)

        # 1. Personal claim WITHOUT entity_binding_anchor must be rejected
        with pytest.raises(ValidationError, match="Lock 8 Entity Binding Isolation"):
            VerificationRequest(
                request_id="req-001",
                created_at=now,
                claim_domain=ClaimDomain.PERSONAL_REALITY,
                claim_key="education.pre_u_status",
                claim_value="COMPLETED",
                consequence_tier=ConsequenceTier.HIGH,
                urgency=VerificationUrgency.IMMEDIATE_TURN,
                entity_binding_anchor=None,  # Missing anchor!
            )

        # 2. Personal claim WITH entity_binding_anchor is valid
        req_personal = VerificationRequest(
            request_id="req-002",
            created_at=now,
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="education.pre_u_status",
            claim_value="COMPLETED",
            consequence_tier=ConsequenceTier.HIGH,
            urgency=VerificationUrgency.IMMEDIATE_TURN,
            entity_binding_anchor="character:aevum:primary",
        )
        assert req_personal.entity_binding_anchor == "character:aevum:primary"

        # 3. World reality claim does NOT require an entity_binding_anchor
        req_world = VerificationRequest(
            request_id="req-003",
            created_at=now,
            claim_domain=ClaimDomain.WORLD_REALITY,
            claim_key="institutions.usm.academic_calendar.semester_1_start",
            claim_value="2024-10-01",
            consequence_tier=ConsequenceTier.LOW,
            urgency=VerificationUrgency.BACKGROUND_ROUTINE,
            entity_binding_anchor=None,
        )
        assert req_world.entity_binding_anchor is None

    def test_verification_request_validations(self):
        """Verify temporal interval sanity and non-empty key validation."""
        now = datetime(2024, 1, 1, tzinfo=timezone.utc)
        earlier = datetime(2023, 1, 1, tzinfo=timezone.utc)

        # Inverted interval must fail
        with pytest.raises(ValidationError, match="start .* cannot be after end"):
            VerificationRequest(
                request_id="req-bad-time",
                created_at=now,
                claim_domain=ClaimDomain.WORLD_REALITY,
                claim_key="world.term_dates",
                claim_value="autumn",
                consequence_tier=ConsequenceTier.MEDIUM,
                target_temporal_interval=(now, earlier),  # start > end
            )

        # Blank claim_key must fail
        with pytest.raises(ValidationError, match="claim_key must not be empty"):
            VerificationRequest(
                request_id="req-bad-key",
                created_at=now,
                claim_domain=ClaimDomain.WORLD_REALITY,
                claim_key="   ",
                claim_value="value",
                consequence_tier=ConsequenceTier.LOW,
            )

    def test_provenance_preservation_in_findings(self):
        """
        Verify Permanent Note C:
        VerificationFinding must preserve comprehensive evaluation provenance
        and contributing observation IDs.
        """
        now = datetime.now(timezone.utc)
        provenance = VerificationEvaluationProvenance(
            evaluator_name="InstitutionalCalendarEvaluator",
            evaluator_version="1.0.0",
            evaluated_at=now,
            rule_ids_applied=("RULE-CAL-001", "RULE-CAL-004"),
            rationale="Official academic portal document confirms semester start date matching claim.",
        )
        finding = VerificationFinding(
            finding_id="find-001",
            request_id="req-003",
            claim_domain=ClaimDomain.WORLD_REALITY,
            claim_key="institutions.usm.academic_calendar.semester_1_start",
            epistemic_status=ClaimEpistemicStatus.SUPPORTED,
            scope=VerificationScope.EXACT_MATCH,
            freshness=EvidenceFreshness.CURRENT,
            contributing_observation_ids=("obs-101", "obs-102"),
            provenance=provenance,
            contradiction_details=None,
        )
        assert finding.provenance.evaluator_name == "InstitutionalCalendarEvaluator"
        assert len(finding.contributing_observation_ids) == 2
        assert "RULE-CAL-001" in finding.provenance.rule_ids_applied

    def test_immutability_and_extra_attributes_forbidden(self):
        """Assert models are strictly frozen and forbid extra attributes."""
        now = datetime.now(timezone.utc)
        prov = VerificationProvenance(
            source_id="src-001",
            source_authority=SourceAuthority.PRIMARY_INSTITUTIONAL,
            source_kind=SourceKind.INSTITUTIONAL_PORTAL,
            retrieval_timestamp=now,
            source_uri_or_identifier="https://usm.my/calendar",
        )
        obs = ExternalObservation(
            observation_id="obs-001",
            source_provenance=prov,
            observed_content_snippet="Semester 1 commences October 2024.",
            structured_payload={"term": "Semester 1", "year": 2024},
            observed_at=now,
        )

        # Frozen immutability check
        with pytest.raises(ValidationError):
            obs.observed_content_snippet = "Modified snippet"  # type: ignore

        # Extra attribute forbidden check
        with pytest.raises(ValidationError):
            ExternalObservation(
                observation_id="obs-002",
                source_provenance=prov,
                observed_content_snippet="Text",
                observed_at=now,
                rogue_field="not_allowed",  # type: ignore
            )

    def test_evidence_payload_and_inbox_contract(self):
        """
        Verify VerificationEvidencePayload and VerificationInboxItem contracts
        maintaining Lock 7 Temporal Isolation.
        """
        now = datetime.now(timezone.utc)
        eval_prov = VerificationEvaluationProvenance(
            evaluator_name="TestEvaluator",
            evaluator_version="1.0.0",
            evaluated_at=now,
            rule_ids_applied=("TEST-01",),
            rationale="Contradiction observed.",
        )
        finding = VerificationFinding(
            finding_id="find-002",
            request_id="req-004",
            claim_domain=ClaimDomain.WORLD_REALITY,
            claim_key="degree.duration_years",
            epistemic_status=ClaimEpistemicStatus.CONTRADICTED,
            scope=VerificationScope.EXACT_MATCH,
            freshness=EvidenceFreshness.CURRENT,
            contributing_observation_ids=("obs-003",),
            provenance=eval_prov,
            contradiction_details="Official handbook lists duration as 4 years, asserted 3 years.",
        )

        # Build payload for pipeline ingestion
        payload = VerificationEvidencePayload(
            payload_id="payload-001",
            finding_id=finding.finding_id,
            claim_domain=finding.claim_domain,
            claim_key=finding.claim_key,
            epistemic_status=finding.epistemic_status,
            evidence_text="USM official handbook specifies Computer Science duration is 4 years.",
            is_refutation=True,
            target_canonical_fact_key="education.usm.programme_duration",
            created_at=now,
        )
        assert payload.is_refutation is True
        assert payload.target_canonical_fact_key == "education.usm.programme_duration"

        # Build inbox item for Turn N+1 delivery
        inbox_item = VerificationInboxItem(
            inbox_id="inbox-001",
            finding=finding,
            enqueued_at=now,
            consumed_at=None,
            consumed_by_turn_id=None,
        )
        assert inbox_item.consumed_at is None
        assert inbox_item.finding.finding_id == "find-002"

    def test_static_ast_boundary_audit_pure_contract_module(self):
        """
        Pure Static AST Boundary Audit:
        Asserts backend/app/reality/verification_models.py contains:
        1. ZERO database imports or calls (sqlite3, aiosqlite, sqlalchemy).
        2. ZERO network imports or calls (httpx, requests, aiohttp, urllib, google.genai).
        3. ZERO mutation or promotion authority (set_fact, PromotionAuthorizationToken).
        4. ZERO truth calculation or trust reasoning functions (must be pure DTOs).
        """
        target_path = Path(__file__).resolve().parent.parent / "app" / "reality" / "verification_models.py"
        assert target_path.exists(), f"Target module not found: {target_path}"

        tree = ast.parse(target_path.read_text(encoding="utf-8"))

        forbidden_import_modules = {
            "sqlite3", "aiosqlite", "sqlalchemy",
            "httpx", "requests", "aiohttp", "urllib", "google.genai"
        }
        forbidden_call_names = {
            "set_fact", "PromotionAuthorizationToken",
            "search", "get", "post", "fetch", "execute", "commit"
        }
        forbidden_func_prefixes = {
            "calculate_", "evaluate_", "resolve_", "verify_", "promote_"
        }

        for node in ast.walk(tree):
            # Check forbidden imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    assert root not in forbidden_import_modules, (
                        f"Forbidden import '{alias.name}' detected in pure contract module!"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root = node.module.split(".")[0]
                    assert root not in forbidden_import_modules, (
                        f"Forbidden from-import '{node.module}' detected in pure contract module!"
                    )

            # Check forbidden function definitions (9.1 is DTOs only, no calculation functions)
            if isinstance(node, ast.FunctionDef):
                for prefix in forbidden_func_prefixes:
                    assert not node.name.startswith(prefix), (
                        f"Forbidden calculation function '{node.name}' in 9.1 pure contract module! "
                        "Calculations belong in Phase 9.2 or 9.3."
                    )

            # Check forbidden function calls
            if isinstance(node, ast.Call):
                func = node.func
                name = None
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                if name:
                    assert name not in forbidden_call_names, (
                        f"Forbidden function call '{name}' in pure contract module!"
                    )
