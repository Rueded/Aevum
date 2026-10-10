"""
test_phase94_gateway_orchestration.py — Phase 9.4 Gateway & Async Orchestration Test Suite

Verifies all 19 Gate invariants under Architecture Gate v0.2 & ADR-020:
1. Gateway != Policy (decision constraints strictly enforced; no scope expansion).
2. Gateway != Evaluator (Gateway collects raw observations; delegates cognitive evaluation).
3. Physical Temporal Wall (Checkpoint 1 & ADR-020 Item 17): origin_turn_id physically shields
   findings from being drained in their origin turn, even if the worker completes instantly.
4. Canonical Deterministic Deduplication (Checkpoint 6 & ADR-020 Item 18):
   Sorted JSON + SHA-256 deduplication key. Deduplication != Evidence Truth.
5. Job-to-Inbox Idempotency & Partial-Success Safety (Checkpoint 3 & ADR-020 Item 19):
   Tracking source_job_id guarantees at most 1 inbox item per job; retry never duplicates evidence.
6. Failure Semantics (Checkpoint 8): TIMED_OUT / FAILED != CONTRADICTED / INSUFFICIENT_EVIDENCE.
7. Request <-> Decision Identity Binding (Checkpoint 5): TOCTOU protection.
8. Dual-Boundary Adapter Filtering (Checkpoint 6): checks both SourceKind and SourceAuthority.
9. Permanent Gate Invariant: Zero floats across all 9.4 models.
10. Pure Static AST Boundary Audit: Zero DB, zero network, zero mutation authority.
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pytest
from pydantic import BaseModel

from app.reality.epistemic_source_evaluator import EpistemicSourceEvaluator
from app.reality.observation_adapters import InMemoryObservationAdapter
from app.reality.verification_gateway import AdapterDescriptor, VerificationGateway
from app.reality.verification_models import (
    ClaimDomain,
    ClaimEpistemicStatus,
    ConsequenceTier,
    EvidenceFreshness,
    ExternalObservation,
    SourceAuthority,
    SourceKind,
    VerificationDispatchResult,
    VerificationEvaluationProvenance,
    VerificationFinding,
    VerificationInboxItem,
    VerificationJob,
    VerificationJobStatus,
    VerificationProvenance,
    VerificationRequest,
    VerificationScope,
    VerificationUrgency,
)
from app.reality.verification_orchestrator import (
    VerificationAsyncOrchestrator,
    VerificationEvidenceInbox,
    compute_deduplication_key,
)
from app.reality.verification_policy_engine import (
    QuietHoursBehavior,
    VerificationCostBudget,
    VerificationDecision,
    VerificationPrivacyScope,
)


class TestPhase94GatewayOrchestration:
    """Test suite for Phase 9.4 Gateway & Async Orchestration."""

    @pytest.fixture
    def evaluator(self) -> EpistemicSourceEvaluator:
        return EpistemicSourceEvaluator()

    @pytest.fixture
    def base_world_request(self) -> VerificationRequest:
        return VerificationRequest(
            request_id="req-world-94-01",
            created_at=datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc),
            claim_domain=ClaimDomain.WORLD_REALITY,
            claim_key="education.usm.programme_duration",
            claim_value=4,
            consequence_tier=ConsequenceTier.HIGH,
            urgency=VerificationUrgency.BACKGROUND_ROUTINE,
        )

    @pytest.fixture
    def base_world_decision(self, base_world_request: VerificationRequest) -> VerificationDecision:
        return VerificationDecision(
            decision_id="dec-world-94-01",
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
            ),
            allowed_source_kinds=(
                SourceKind.INSTITUTIONAL_PORTAL,
                SourceKind.PUBLIC_REGISTRY,
            ),
            cost_budget=VerificationCostBudget(max_queries=2, timeout_seconds=10),
            quiet_hours_behavior=QuietHoursBehavior.PROCEED_SILENT_BACKGROUND,
            policy_rule_id="VPOL-005-HIGH",
            rationale="World reality authorized for verification.",
            evaluated_at=datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc),
        )

    # --------------------------------------------------------------------------
    # 1. Gateway Constraint & Boundary Enforcement
    # --------------------------------------------------------------------------

    def test_gateway_strictly_adheres_to_policy_allowed_sources(
        self, base_world_request, base_world_decision
    ):
        """
        Verify Checkpoint 2: Gateway != Policy.
        Gateway queries ONLY descriptors matching allowed_source_kinds.
        """
        now = datetime.now(timezone.utc)
        obs_portal = ExternalObservation(
            observation_id="obs-portal",
            source_provenance=VerificationProvenance(
                source_id="src-portal",
                source_authority=SourceAuthority.PRIMARY_INSTITUTIONAL,
                source_kind=SourceKind.INSTITUTIONAL_PORTAL,
                retrieval_timestamp=now,
            ),
            observed_content_snippet="4 years duration",
            structured_payload={"key": "education.usm.programme_duration", "value": 4},
            observed_at=now,
        )
        obs_dialogue = ExternalObservation(
            observation_id="obs-dialogue",
            source_provenance=VerificationProvenance(
                source_id="src-dialogue",
                source_authority=SourceAuthority.FIRST_PARTY_PERSONAL,
                source_kind=SourceKind.USER_DIALOGUE,
                retrieval_timestamp=now,
            ),
            observed_content_snippet="User said 4 years",
            structured_payload={"key": "education.usm.programme_duration", "value": 4},
            observed_at=now,
        )

        desc_portal = AdapterDescriptor(
            adapter_id="adapter-portal",
            source_kind=SourceKind.INSTITUTIONAL_PORTAL,
            source_authority=SourceAuthority.PRIMARY_INSTITUTIONAL,
            adapter=InMemoryObservationAdapter([obs_portal]),
        )
        desc_dialogue = AdapterDescriptor(
            adapter_id="adapter-dialogue",
            source_kind=SourceKind.USER_DIALOGUE,
            source_authority=SourceAuthority.FIRST_PARTY_PERSONAL,
            adapter=InMemoryObservationAdapter([obs_dialogue]),
        )

        gateway = VerificationGateway([desc_portal, desc_dialogue])
        results = gateway.execute_verification(base_world_request, base_world_decision)

        # Only portal observation is queried; dialogue is strictly filtered out
        assert len(results) == 1
        assert results[0].observation_id == "obs-portal"

    def test_gateway_budget_max_queries_enforcement(
        self, base_world_request, base_world_decision
    ):
        """
        Verify Gateway truncates query fan-out strictly to cost_budget.max_queries.
        """
        now = datetime.now(timezone.utc)
        observations = [
            ExternalObservation(
                observation_id=f"obs-{i}",
                source_provenance=VerificationProvenance(
                    source_id=f"src-{i}",
                    source_authority=SourceAuthority.PRIMARY_INSTITUTIONAL,
                    source_kind=SourceKind.INSTITUTIONAL_PORTAL,
                    retrieval_timestamp=now,
                ),
                observed_content_snippet=f"Snippet {i}",
                structured_payload={"key": "education.usm.programme_duration", "value": 4},
                observed_at=now,
            )
            for i in range(5)
        ]
        desc = AdapterDescriptor(
            adapter_id="adapter-multi",
            source_kind=SourceKind.INSTITUTIONAL_PORTAL,
            source_authority=SourceAuthority.PRIMARY_INSTITUTIONAL,
            adapter=InMemoryObservationAdapter(observations),
        )

        gateway = VerificationGateway([desc])
        results = gateway.execute_verification(base_world_request, base_world_decision)

        # base_world_decision cost_budget max_queries is 2
        assert len(results) == 2

    def test_gateway_suppressed_decision_produces_zero_queries(
        self, base_world_request, base_world_decision
    ):
        """
        Verify Gateway produces zero queries when decision.should_verify is False.
        """
        suppressed_decision = base_world_decision.model_copy(
            update={"should_verify": False, "suppression_reason": "Turn rate limit reached"}
        )
        gateway = VerificationGateway([])
        results = gateway.execute_verification(base_world_request, suppressed_decision)
        assert results == ()

    def test_gateway_rejects_request_decision_identity_mismatch(
        self, base_world_request, base_world_decision
    ):
        """
        Verify Checkpoint 5: TOCTOU protection.
        decision.request_id != request.request_id raises ValueError immediately.
        """
        mismatched_request = base_world_request.model_copy(update={"request_id": "req-different"})
        gateway = VerificationGateway([])
        with pytest.raises(ValueError, match="Verification authorization mismatch"):
            gateway.execute_verification(mismatched_request, base_world_decision)

    def test_gateway_enforces_allowed_authority_boundary(
        self, base_world_request, base_world_decision
    ):
        """
        Verify Checkpoint 6: Dual-boundary filtering.
        Descriptor matching SourceKind but possessing disallowed SourceAuthority is blocked.
        """
        now = datetime.now(timezone.utc)
        obs = ExternalObservation(
            observation_id="obs-unverified-reg",
            source_provenance=VerificationProvenance(
                source_id="unverified-blog",
                source_authority=SourceAuthority.UNVERIFIED_EXTERNAL,
                source_kind=SourceKind.PUBLIC_REGISTRY,
                retrieval_timestamp=now,
            ),
            observed_content_snippet="Blog registry",
            structured_payload={"key": "education.usm.programme_duration", "value": 4},
            observed_at=now,
        )
        # Descriptor has SourceKind.PUBLIC_REGISTRY (allowed by decision), but UNVERIFIED_EXTERNAL (not allowed by decision)
        desc = AdapterDescriptor(
            adapter_id="adapter-unverified-reg",
            source_kind=SourceKind.PUBLIC_REGISTRY,
            source_authority=SourceAuthority.UNVERIFIED_EXTERNAL,
            adapter=InMemoryObservationAdapter([obs]),
        )

        gateway = VerificationGateway([desc])
        results = gateway.execute_verification(base_world_request, base_world_decision)

        # Blocked because UNVERIFIED_EXTERNAL is not in allowed_authorities
        assert results == ()

    # --------------------------------------------------------------------------
    # 2. Asynchronous Orchestration & Non-Blocking Enqueue
    # --------------------------------------------------------------------------

    def test_non_blocking_enqueue_temporal_wall_zero_same_turn_leak(
        self, evaluator, base_world_request, base_world_decision
    ):
        """
        Verify Checkpoint 3: Zero Same-Turn Leak.
        enqueue_verification_job returns immediately with status=QUEUED without awaiting worker.
        """
        gateway = VerificationGateway([])
        orchestrator = VerificationAsyncOrchestrator(gateway=gateway, evaluator=evaluator)

        result = orchestrator.enqueue_verification_job(
            request=base_world_request,
            decision=base_world_decision,
            origin_turn_id="turn-100",
        )

        assert isinstance(result, VerificationDispatchResult)
        assert result.status == VerificationJobStatus.QUEUED
        assert result.is_duplicate is False

        # Job is recorded in queue as QUEUED
        job = orchestrator.get_job(result.job_id)
        assert job is not None
        assert job.status == VerificationJobStatus.QUEUED
        assert job.origin_turn_id == "turn-100"

    def test_repeated_enqueue_same_logical_request_is_deterministically_coalesced(
        self, evaluator, base_world_request, base_world_decision
    ):
        """
        Verify Checkpoint 6: Canonical SHA-256 Deduplication.
        Repeated enqueue of logically identical request coalesces into existing job.
        """
        gateway = VerificationGateway([])
        orchestrator = VerificationAsyncOrchestrator(gateway=gateway, evaluator=evaluator)

        res1 = orchestrator.enqueue_verification_job(base_world_request, base_world_decision)
        res2 = orchestrator.enqueue_verification_job(base_world_request, base_world_decision)

        assert res1.is_duplicate is False
        assert res2.is_duplicate is True
        assert res2.job_id == res1.job_id
        assert res2.deduplication_key == res1.deduplication_key

        # Key is a deterministic 64-char hex SHA-256
        assert len(res1.deduplication_key) == 64

    def test_same_claim_different_turn_is_not_deduplicated(
        self, evaluator, base_world_request, base_world_decision
    ):
        """
        Verify ADR-020 Item 18 (Gate Fix ①):
        Claim identity != Job identity.
        Repeated enqueue of claim X in Turn N is deduplicated/coalesced.
        Fresh enqueue of claim X in Turn N+1 is NOT deduplicated and creates a fresh Job B.
        """
        gateway = VerificationGateway([])
        orchestrator = VerificationAsyncOrchestrator(gateway=gateway, evaluator=evaluator)

        # Turn 100: first submission -> Job A created
        res_t100_1 = orchestrator.enqueue_verification_job(
            request=base_world_request,
            decision=base_world_decision,
            origin_turn_id="turn-100",
        )
        assert res_t100_1.is_duplicate is False
        job_a_id = res_t100_1.job_id

        # Turn 100: duplicate submission within same turn -> coalesced into Job A
        res_t100_2 = orchestrator.enqueue_verification_job(
            request=base_world_request,
            decision=base_world_decision,
            origin_turn_id="turn-100",
        )
        assert res_t100_2.is_duplicate is True
        assert res_t100_2.job_id == job_a_id
        assert res_t100_2.deduplication_key == res_t100_1.deduplication_key

        # Turn 101: subsequent turn submits the same claim -> fresh Job B created (NOT duplicate)
        res_t101 = orchestrator.enqueue_verification_job(
            request=base_world_request,
            decision=base_world_decision,
            origin_turn_id="turn-101",
        )
        assert res_t101.is_duplicate is False
        assert res_t101.job_id != job_a_id
        # Canonical claim dedup key remains identical
        assert res_t101.deduplication_key == res_t100_1.deduplication_key

        # Both jobs exist independently in orchestrator
        job_a = orchestrator.get_job(job_a_id)
        job_b = orchestrator.get_job(res_t101.job_id)
        assert job_a is not None and job_b is not None
        assert job_a.origin_turn_id == "turn-100"
        assert job_b.origin_turn_id == "turn-101"

    # --------------------------------------------------------------------------
    # 3. Physical Temporal Wall (Checkpoint 1 & ADR-020 Item 17)
    # --------------------------------------------------------------------------

    def test_worker_completion_before_turn_n_response_cannot_leak_same_turn(
        self, evaluator, base_world_request, base_world_decision
    ):
        """
        CRITICAL TEST — Checkpoint 1 & ADR-020 Item 17:
        Simulate worker completing in 1ms BEFORE Turn N finishes.
        VerificationEvidenceInbox physically shields the finding from being drained in Turn N.
        """
        now = datetime.now(timezone.utc)
        obs = ExternalObservation(
            observation_id="obs-fast-complete",
            source_provenance=VerificationProvenance(
                source_id="src-fast",
                source_authority=SourceAuthority.PRIMARY_INSTITUTIONAL,
                source_kind=SourceKind.INSTITUTIONAL_PORTAL,
                retrieval_timestamp=now,
            ),
            observed_content_snippet="Duration is 4 years.",
            structured_payload={"key": "education.usm.programme_duration", "value": 4},
            observed_at=now,
        )
        desc = AdapterDescriptor(
            adapter_id="adapter-fast",
            source_kind=SourceKind.INSTITUTIONAL_PORTAL,
            source_authority=SourceAuthority.PRIMARY_INSTITUTIONAL,
            adapter=InMemoryObservationAdapter([obs]),
        )
        gateway = VerificationGateway([desc])
        inbox = VerificationEvidenceInbox()
        orchestrator = VerificationAsyncOrchestrator(gateway=gateway, evaluator=evaluator, inbox=inbox)

        # Step 1: Enqueue in Turn 100
        dispatch = orchestrator.enqueue_verification_job(
            request=base_world_request,
            decision=base_world_decision,
            origin_turn_id="turn-100",
        )

        # Step 2: Worker executes immediately (before Turn 100 response finishes)
        job_done = orchestrator.process_next_job(now=now)
        assert job_done is not None
        assert job_done.status == VerificationJobStatus.COMPLETED

        # Finding is in the inbox
        assert len(inbox.peek_unconsumed()) == 1

        # Step 3: Turn 100 attempts to drain the inbox!
        # MUST RETURN EMPTY — Physical Temporal Wall prevents same-turn leak!
        drained_turn_100 = inbox.drain_for_turn(consumer_turn_id="turn-100", now=now)
        assert len(drained_turn_100) == 0

        # Step 4: Turn 101 starts and drains the inbox
        # Finding is now unlocked and delivered for Turn 101!
        drained_turn_101 = inbox.drain_for_turn(consumer_turn_id="turn-101", now=now)
        assert len(drained_turn_101) == 1
        assert drained_turn_101[0].finding.epistemic_status == ClaimEpistemicStatus.SUPPORTED
        assert drained_turn_101[0].consumed_by_turn_id == "turn-101"

    def test_inbox_item_is_not_consumable_before_eligible_turn(self, evaluator):
        """
        Verify that an item with eligible_from_turn_id='turn-102' cannot be drained in 'turn-101'.
        """
        inbox = VerificationEvidenceInbox()
        now = datetime.now(timezone.utc)
        finding = VerificationFinding(
            finding_id="find-delayed",
            request_id="req-delayed",
            claim_domain=ClaimDomain.WORLD_REALITY,
            claim_key="test.key",
            epistemic_status=ClaimEpistemicStatus.SUPPORTED,
            scope=VerificationScope.EXACT_MATCH,
            freshness=EvidenceFreshness.CURRENT,
            provenance=VerificationEvaluationProvenance(
                evaluator_name="TestEvaluator",
                evaluator_version="1.0.0",
                evaluated_at=now,
                rule_ids_applied=("TEST-01",),
                rationale="Delayed test evaluation",
            ),
            contradiction_details=None,
        )
        inbox.deposit(
            source_job_id="job-delayed",
            finding=finding,
            origin_turn_id="turn-100",
            eligible_from_turn_id="turn-102",
            now=now,
        )

        # Attempt drain in turn-101
        drained_101 = inbox.drain_for_turn(consumer_turn_id="turn-101", now=now)
        assert len(drained_101) == 0

        # Drain in turn-102 succeeds
        drained_102 = inbox.drain_for_turn(consumer_turn_id="turn-102", now=now)
        assert len(drained_102) == 1
        assert drained_102[0].inbox_id is not None

    def test_eligible_from_turn_true_earliest_semantics(self, evaluator):
        """
        Verify ADR-020 Item 17 (Gate Fix ②):
        Scheme B — True 'Earliest Turn' Semantics:
        If an item has eligible_from_turn_sequence = 102:
        - Turn 100 cannot drain (origin turn blocked by Temporal Wall).
        - Turn 101 cannot drain (101 < 102).
        - Turn 102 CAN drain (102 >= 102).
        - If Turn 102 did NOT drain (e.g. idle/silent turn), Turn 103 CAN drain (103 >= 102).
        """
        inbox = VerificationEvidenceInbox()
        now = datetime.now(timezone.utc)
        finding = VerificationFinding(
            finding_id="find-earliest-01",
            request_id="req-earliest-01",
            claim_domain=ClaimDomain.WORLD_REALITY,
            claim_key="education.usm.programme_duration",
            epistemic_status=ClaimEpistemicStatus.SUPPORTED,
            scope=VerificationScope.EXACT_MATCH,
            freshness=EvidenceFreshness.CURRENT,
            provenance=VerificationEvaluationProvenance(
                evaluator_name="TestEvaluator",
                evaluator_version="1.0.0",
                evaluated_at=now,
                rule_ids_applied=("TEST-01",),
                rationale="Earliest test evaluation",
            ),
            contradiction_details=None,
        )
        inbox.deposit(
            source_job_id="job-earliest",
            finding=finding,
            origin_turn_id="turn-100",
            eligible_from_turn_id="turn-102",
            now=now,
        )

        # 1. Turn 100 cannot drain (Temporal Wall)
        assert len(inbox.drain_for_turn(consumer_turn_id="turn-100", now=now)) == 0

        # 2. Turn 101 cannot drain (prior to earliest turn 102)
        assert len(inbox.drain_for_turn(consumer_turn_id="turn-101", now=now)) == 0

        # 3. Simulate Turn 102 does NOT drain (e.g., character is asleep / quiet hours)
        # 4. Turn 103 drains -> SUCCESS (true earliest turn, 103 >= 102)
        drained_103 = inbox.drain_for_turn(consumer_turn_id="turn-103", now=now)
        assert len(drained_103) == 1
        assert drained_103[0].consumed_by_turn_id == "turn-103"

        # 5. Subsequent drain in Turn 104 -> 0 items (already consumed)
        assert len(inbox.drain_for_turn(consumer_turn_id="turn-104", now=now)) == 0

    def test_temporal_wall_invariant_sequence_order(self):
        """
        Verify model validator rejects invalid temporal ordering:
        eligible_from_turn_sequence must be strictly > origin_turn_sequence.
        """
        now = datetime.now(timezone.utc)
        finding = VerificationFinding(
            finding_id="find-inv-01",
            request_id="req-inv-01",
            claim_domain=ClaimDomain.WORLD_REALITY,
            claim_key="test.key",
            epistemic_status=ClaimEpistemicStatus.SUPPORTED,
            scope=VerificationScope.EXACT_MATCH,
            freshness=EvidenceFreshness.CURRENT,
            provenance=VerificationEvaluationProvenance(
                evaluator_name="TestEvaluator",
                evaluator_version="1.0.0",
                evaluated_at=now,
                rule_ids_applied=("TEST-01",),
                rationale="Invariant test",
            ),
            contradiction_details=None,
        )

        # Invariant rejection: eligible <= origin
        with pytest.raises(ValueError, match="Temporal Wall Invariant Violated"):
            VerificationInboxItem(
                inbox_id="inbox-fail-01",
                source_job_id="job-fail-01",
                finding=finding,
                origin_turn_id="turn-100",
                eligible_from_turn_id="turn-100",
                origin_turn_sequence=100,
                eligible_from_turn_sequence=100,
                enqueued_at=now,
            )

        with pytest.raises(ValueError, match="Temporal Wall Invariant Violated"):
            VerificationInboxItem(
                inbox_id="inbox-fail-02",
                source_job_id="job-fail-02",
                finding=finding,
                origin_turn_id="turn-100",
                eligible_from_turn_id="turn-99",
                origin_turn_sequence=100,
                eligible_from_turn_sequence=99,
                enqueued_at=now,
            )

    # --------------------------------------------------------------------------
    # 4. Job -> Inbox Idempotency & Partial-Success Retry Safety
    # --------------------------------------------------------------------------

    def test_retry_after_successful_deposit_is_idempotent(self, evaluator):
        """
        CRITICAL TEST — Checkpoint 3 & ADR-020 Item 19:
        Simulate partial success: deposit succeeded, but status write failed, triggering retry.
        Subsequent deposit with identical source_job_id MUST return existing item idempotently.
        """
        inbox = VerificationEvidenceInbox()
        now = datetime.now(timezone.utc)
        finding1 = VerificationFinding(
            finding_id="find-idemp-01",
            request_id="req-idemp-01",
            claim_domain=ClaimDomain.WORLD_REALITY,
            claim_key="education.usm.programme_duration",
            epistemic_status=ClaimEpistemicStatus.SUPPORTED,
            scope=VerificationScope.EXACT_MATCH,
            freshness=EvidenceFreshness.CURRENT,
            provenance=VerificationEvaluationProvenance(
                evaluator_name="TestEvaluator",
                evaluator_version="1.0.0",
                evaluated_at=now,
                rule_ids_applied=("TEST-01",),
                rationale="Idempotency test evaluation",
            ),
            contradiction_details=None,
        )

        item1 = inbox.deposit(
            source_job_id="vjob-crash-test",
            finding=finding1,
            origin_turn_id="turn-100",
            eligible_from_turn_id="turn-101",
            now=now,
        )

        # Second deposit attempt (retry after crash) with same job ID
        item2 = inbox.deposit(
            source_job_id="vjob-crash-test",
            finding=finding1,
            origin_turn_id="turn-100",
            eligible_from_turn_id="turn-101",
            now=now,
        )

        # Exact same item returned; inbox length remains 1
        assert item1.inbox_id == item2.inbox_id
        assert len(inbox.peek_unconsumed()) == 1

    def test_retry_semantics_does_not_manufacture_duplicate_findings(
        self, evaluator, base_world_request, base_world_decision
    ):
        """
        Verify Checkpoint 7: Retry does not create duplicate findings.
        Adapter fails on attempt 1 and attempt 2, succeeds on attempt 3.
        Inbox receives EXACTLY 1 item upon final success.
        """
        call_count = 0
        now = datetime.now(timezone.utc)

        class FlakyAdapter:
            def observe(self, *args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    raise ConnectionError("Transient network failure")
                return (
                    ExternalObservation(
                        observation_id="obs-flaky-success",
                        source_provenance=VerificationProvenance(
                            source_id="src-flaky",
                            source_authority=SourceAuthority.PRIMARY_INSTITUTIONAL,
                            source_kind=SourceKind.INSTITUTIONAL_PORTAL,
                            retrieval_timestamp=now,
                        ),
                        observed_content_snippet="Programme duration is 4 years.",
                        structured_payload={"key": "education.usm.programme_duration", "value": 4},
                        observed_at=now,
                    ),
                )

        desc = AdapterDescriptor(
            adapter_id="adapter-flaky",
            source_kind=SourceKind.INSTITUTIONAL_PORTAL,
            source_authority=SourceAuthority.PRIMARY_INSTITUTIONAL,
            adapter=FlakyAdapter(),
        )
        gateway = VerificationGateway([desc])
        inbox = VerificationEvidenceInbox()
        orchestrator = VerificationAsyncOrchestrator(gateway=gateway, evaluator=evaluator, inbox=inbox)

        dispatch = orchestrator.enqueue_verification_job(base_world_request, base_world_decision)
        job_id = dispatch.job_id

        # Attempt 1 -> fails, retried
        j1 = orchestrator.process_next_job(now=now)
        assert j1.status == VerificationJobStatus.QUEUED
        assert j1.attempt_count == 1
        assert len(inbox.peek_unconsumed()) == 0

        # Attempt 2 -> fails, retried
        j2 = orchestrator.process_next_job(now=now)
        assert j2.status == VerificationJobStatus.QUEUED
        assert j2.attempt_count == 2
        assert len(inbox.peek_unconsumed()) == 0

        # Attempt 3 -> succeeds
        j3 = orchestrator.process_next_job(now=now)
        assert j3.status == VerificationJobStatus.COMPLETED
        assert j3.attempt_count == 3

        # Exactly 1 finding deposited in the inbox!
        assert len(inbox.peek_unconsumed()) == 1

    # --------------------------------------------------------------------------
    # 5. Operational Failure Separation (Checkpoint 8)
    # --------------------------------------------------------------------------

    def test_failure_semantics_timeout_does_not_produce_contradicted_finding(
        self, evaluator, base_world_request, base_world_decision
    ):
        """
        Verify Checkpoint 8: TIMED_OUT != CONTRADICTED.
        Execution timeout yields job status TIMED_OUT. Zero epistemic finding constructed!
        """
        class TimeoutAdapter:
            def observe(self, *args, **kwargs):
                raise TimeoutError("Adapter execution deadline expired")

        desc = AdapterDescriptor(
            adapter_id="adapter-timeout",
            source_kind=SourceKind.INSTITUTIONAL_PORTAL,
            source_authority=SourceAuthority.PRIMARY_INSTITUTIONAL,
            adapter=TimeoutAdapter(),
        )
        gateway = VerificationGateway([desc])
        inbox = VerificationEvidenceInbox()
        orchestrator = VerificationAsyncOrchestrator(gateway=gateway, evaluator=evaluator, inbox=inbox)

        # Enqueue with max_attempts=1 to force immediate terminal timeout
        decision_1_try = base_world_decision.model_copy()
        dispatch = orchestrator.enqueue_verification_job(base_world_request, decision_1_try)

        # Force max_attempts=1 for test speed
        orchestrator._jobs[dispatch.job_id] = orchestrator._jobs[dispatch.job_id].model_copy(
            update={"max_attempts": 1}
        )

        job = orchestrator.process_next_job()
        assert job.status == VerificationJobStatus.TIMED_OUT
        assert "timed out" in job.error_message.lower()

        # Crucial: Inbox receives ZERO findings! Timeout is NOT a contradiction!
        assert len(inbox.peek_unconsumed()) == 0

    def test_failure_semantics_adapter_error_does_not_mutate_reality(
        self, evaluator, base_world_request, base_world_decision
    ):
        """
        Verify Checkpoint 8: FAILED != INSUFFICIENT_EVIDENCE / CONTRADICTED.
        Terminal operational failure produces job status FAILED and does not touch inbox.
        """
        class CrashAdapter:
            def observe(self, *args, **kwargs):
                raise RuntimeError("Hardware/OS socket crash")

        desc = AdapterDescriptor(
            adapter_id="adapter-crash",
            source_kind=SourceKind.INSTITUTIONAL_PORTAL,
            source_authority=SourceAuthority.PRIMARY_INSTITUTIONAL,
            adapter=CrashAdapter(),
        )
        gateway = VerificationGateway([desc])
        inbox = VerificationEvidenceInbox()
        orchestrator = VerificationAsyncOrchestrator(gateway=gateway, evaluator=evaluator, inbox=inbox)

        dispatch = orchestrator.enqueue_verification_job(base_world_request, base_world_decision)
        orchestrator._jobs[dispatch.job_id] = orchestrator._jobs[dispatch.job_id].model_copy(
            update={"max_attempts": 1}
        )

        job = orchestrator.process_next_job()
        assert job.status == VerificationJobStatus.FAILED
        assert "socket crash" in job.error_message

        # Inbox has 0 items
        assert len(inbox.peek_unconsumed()) == 0

    # --------------------------------------------------------------------------
    # 6. Inbox Consumption & Authority Isolation
    # --------------------------------------------------------------------------

    def test_inbox_temporal_isolation_turn_n_to_turn_n_plus_1(
        self, evaluator, base_world_request, base_world_decision
    ):
        """
        Standard turn boundary isolation test.
        """
        now = datetime.now(timezone.utc)
        obs = ExternalObservation(
            observation_id="obs-std",
            source_provenance=VerificationProvenance(
                source_id="src-std",
                source_authority=SourceAuthority.PRIMARY_INSTITUTIONAL,
                source_kind=SourceKind.INSTITUTIONAL_PORTAL,
                retrieval_timestamp=now,
            ),
            observed_content_snippet="Duration is 4 years.",
            structured_payload={"key": "education.usm.programme_duration", "value": 4},
            observed_at=now,
        )
        desc = AdapterDescriptor(
            adapter_id="adapter-std",
            source_kind=SourceKind.INSTITUTIONAL_PORTAL,
            source_authority=SourceAuthority.PRIMARY_INSTITUTIONAL,
            adapter=InMemoryObservationAdapter([obs]),
        )
        gateway = VerificationGateway([desc])
        orchestrator = VerificationAsyncOrchestrator(gateway=gateway, evaluator=evaluator)

        orchestrator.enqueue_verification_job(base_world_request, base_world_decision, origin_turn_id="turn-5")
        orchestrator.process_next_job(now=now)

        # In Turn 5, draining returns empty
        assert len(orchestrator.inbox.drain_for_turn("turn-5", now=now)) == 0

        # In Turn 6, draining returns the finding
        items = orchestrator.inbox.drain_for_turn("turn-6", now=now)
        assert len(items) == 1
        assert items[0].finding.epistemic_status == ClaimEpistemicStatus.SUPPORTED

    def test_inbox_consumption_does_not_grant_promotion_token(self, evaluator):
        """
        Verify Checkpoint 5: Consumption != Promotion Authorization.
        Draining inbox yields VerificationInboxItem, possesses ZERO promotion authority.
        """
        inbox = VerificationEvidenceInbox()
        now = datetime.now(timezone.utc)
        finding = VerificationFinding(
            finding_id="find-no-promo",
            request_id="req-no-promo",
            claim_domain=ClaimDomain.WORLD_REALITY,
            claim_key="education.usm.programme_duration",
            epistemic_status=ClaimEpistemicStatus.SUPPORTED,
            scope=VerificationScope.EXACT_MATCH,
            freshness=EvidenceFreshness.CURRENT,
            provenance=VerificationEvaluationProvenance(
                evaluator_name="TestEvaluator",
                evaluator_version="1.0.0",
                evaluated_at=now,
                rule_ids_applied=("TEST-01",),
                rationale="No promo test evaluation",
            ),
            contradiction_details=None,
        )
        inbox.deposit("job-np", finding, origin_turn_id="turn-1", now=now)

        items = inbox.drain_for_turn("turn-2", now=now)
        assert len(items) == 1
        item = items[0]

        assert isinstance(item, VerificationInboxItem)
        assert not hasattr(item, "promotion_token")
        assert not hasattr(item, "token")
        assert not hasattr(item, "authorize_promotion")

    def test_background_silent_verification_retains_privacy_constraints(
        self, evaluator
    ):
        """
        Verify Checkpoint 9: Background silent verification carries privacy bounds.
        """
        now = datetime.now(timezone.utc)
        req_pers = VerificationRequest(
            request_id="req-silent-priv",
            created_at=now,
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="biography.secret_hobby",
            claim_value="Skydiving",
            consequence_tier=ConsequenceTier.CRITICAL,
            entity_binding_anchor="character:aevum:primary",
        )
        decision_silent = VerificationDecision(
            decision_id="dec-silent-priv",
            request_id=req_pers.request_id,
            claim_key=req_pers.claim_key,
            claim_domain=req_pers.claim_domain,
            consequence_tier=req_pers.consequence_tier,
            should_verify=True,
            target_scope=VerificationScope.EXACT_MATCH,
            urgency=VerificationUrgency.BACKGROUND_ROUTINE,
            privacy_scope=VerificationPrivacyScope.PUBLIC_DATA_ONLY,  # Restricted to public data!
            allowed_authorities=(SourceAuthority.PRIMARY_INSTITUTIONAL,),
            allowed_source_kinds=(SourceKind.PUBLIC_REGISTRY,),
            cost_budget=VerificationCostBudget(max_queries=1, timeout_seconds=5),
            quiet_hours_behavior=QuietHoursBehavior.PROCEED_SILENT_BACKGROUND,
            policy_rule_id="VPOL-005-CRITICAL",
            rationale="Silent background allowed",
            evaluated_at=now,
        )

        gateway = VerificationGateway([])
        orchestrator = VerificationAsyncOrchestrator(gateway=gateway, evaluator=evaluator)
        dispatch = orchestrator.enqueue_verification_job(req_pers, decision_silent)

        job = orchestrator.get_job(dispatch.job_id)
        assert job.decision.privacy_scope == VerificationPrivacyScope.PUBLIC_DATA_ONLY
        assert job.decision.allowed_source_kinds == (SourceKind.PUBLIC_REGISTRY,)

    # --------------------------------------------------------------------------
    # 7. Permanent Gate Invariant: Zero Floats
    # --------------------------------------------------------------------------

    def test_permanent_gate_invariant_zero_floats_in_jobs_and_inbox(
        self, base_world_request, base_world_decision, evaluator
    ):
        """
        Recursively verify zero float fields in VerificationJob, DispatchResult, and InboxItem.
        """
        now = datetime.now(timezone.utc)
        finding = VerificationFinding(
            finding_id="find-zf",
            request_id=base_world_request.request_id,
            claim_domain=base_world_request.claim_domain,
            claim_key=base_world_request.claim_key,
            epistemic_status=ClaimEpistemicStatus.SUPPORTED,
            scope=VerificationScope.EXACT_MATCH,
            freshness=EvidenceFreshness.CURRENT,
            provenance=VerificationEvaluationProvenance(
                evaluator_name="TestEvaluator",
                evaluator_version="1.0.0",
                evaluated_at=now,
                rule_ids_applied=("TEST-01",),
                rationale="Zero float test evaluation",
            ),
            contradiction_details=None,
        )
        job = VerificationJob(
            job_id="job-zf",
            request_id=base_world_request.request_id,
            request=base_world_request,
            decision=base_world_decision,
            status=VerificationJobStatus.COMPLETED,
            deduplication_key=compute_deduplication_key(base_world_request),
            origin_turn_id="turn-1",
            created_at=now,
            finding_id=finding.finding_id,
        )
        dispatch = VerificationDispatchResult(
            job_id="job-zf",
            status=VerificationJobStatus.QUEUED,
            is_duplicate=False,
            deduplication_key=job.deduplication_key,
            dispatched_at=now,
            rationale="Dispatched",
        )
        inbox_item = VerificationInboxItem(
            inbox_id="inbox-zf",
            source_job_id=job.job_id,
            finding=finding,
            origin_turn_id="turn-1",
            eligible_from_turn_id="turn-2",
            enqueued_at=now,
        )

        def assert_no_floats(obj: Any, path: str = "") -> None:
            if isinstance(obj, float):
                raise AssertionError(f"Permanent Gate Invariant Violation: float found at '{path}' ({obj})!")
            elif isinstance(obj, BaseModel):
                for k, v in obj.__dict__.items():
                    assert_no_floats(v, f"{path}.{k}" if path else k)
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    assert_no_floats(v, f"{path}[{k}]")
            elif isinstance(obj, (list, tuple)):
                for i, v in enumerate(obj):
                    assert_no_floats(v, f"{path}[{i}]")

        assert_no_floats(job, "VerificationJob")
        assert_no_floats(dispatch, "VerificationDispatchResult")
        assert_no_floats(inbox_item, "VerificationInboxItem")

    # --------------------------------------------------------------------------
    # 8. Pure Static AST Boundary Audits
    # --------------------------------------------------------------------------

    def test_static_ast_boundary_audit_verification_gateway(self):
        """
        Asserts verification_gateway.py contains:
        1. ZERO database imports or calls (sqlite3, aiosqlite, sqlalchemy).
        2. ZERO network imports (httpx, requests, aiohttp, urllib, google.genai).
        3. ZERO mutation or promotion authority (set_fact, PromotionAuthorizationToken).
        """
        path = Path(__file__).resolve().parent.parent / "app" / "reality" / "verification_gateway.py"
        assert path.exists()

        tree = ast.parse(path.read_text(encoding="utf-8"))
        forbidden_import_modules = {
            "sqlite3", "aiosqlite", "sqlalchemy",
            "httpx", "requests", "aiohttp", "urllib", "google.genai",
        }
        forbidden_call_names = {
            "set_fact", "PromotionAuthorizationToken", "create_task", "Thread"
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

    def test_static_ast_boundary_audit_verification_orchestrator(self):
        """
        Asserts verification_orchestrator.py contains:
        1. ZERO database imports or calls (sqlite3, aiosqlite, sqlalchemy).
        2. ZERO network imports (httpx, requests, aiohttp, urllib, google.genai).
        3. ZERO mutation or promotion authority (set_fact, PromotionAuthorizationToken).
        4. ZERO unauthorized background threading (threading.Thread).
        """
        path = Path(__file__).resolve().parent.parent / "app" / "reality" / "verification_orchestrator.py"
        assert path.exists()

        tree = ast.parse(path.read_text(encoding="utf-8"))
        forbidden_import_modules = {
            "sqlite3", "aiosqlite", "sqlalchemy",
            "httpx", "requests", "aiohttp", "urllib", "google.genai",
            "threading",
        }
        forbidden_call_names = {
            "set_fact", "PromotionAuthorizationToken", "Thread"
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
