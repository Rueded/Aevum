"""
verification_orchestrator.py — Verification Queue, Orchestrator & Evidence Inbox

Phase 9.4 Deliverable under Architecture Gate v0.2:
- Physical Temporal Wall (Checkpoint 1 & ADR-020 Item 17):
    - Verification findings are physically forbidden from being drained in their origin turn.
    - Zero Same-Turn Leak guaranteed at the data model level (origin_turn_id != consumer_turn_id).
- Canonical Deterministic Deduplication (Checkpoint 6 & ADR-020 Item 18):
    - Canonical sorted JSON serialization + SHA-256.
    - Deduplication is an identity key for verification work, NOT for evidence truth.
- Job-to-Inbox Idempotency (Checkpoint 3 & ADR-020 Item 19):
    - Tracks source_job_id; deposit is strictly idempotent, preventing duplicate findings on retry.
- Operational Failure Separation (Checkpoint 8 & ADR-020):
    - TIMED_OUT != CONTRADICTED; FAILED != INSUFFICIENT_EVIDENCE.
    - Job status remains decoupled from epistemic status.
- Single-step deterministic worker execution for 100% testable unit orchestration.
- Zero mutation authority, zero database writes, zero LLM dependencies.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from app.reality.epistemic_source_evaluator import EpistemicSourceEvaluator
from app.reality.verification_gateway import VerificationGatewayProtocol
from app.reality.verification_models import (
    VerificationDispatchResult,
    VerificationFinding,
    VerificationInboxItem,
    VerificationJob,
    VerificationJobStatus,
    VerificationRequest,
)
from app.reality.verification_policy_engine import VerificationDecision


def compute_deduplication_key(request: VerificationRequest) -> str:
    """
    Canonical deterministic SHA-256 deduplication key.
    Strictly an identity key for verification scheduling, NOT evidence truth (ADR-020 Item 18).
    """
    payload = {
        "claim_domain": request.claim_domain.value,
        "claim_key": request.claim_key,
        "claim_value": str(request.claim_value),
        "entity_binding_anchor": request.entity_binding_anchor or "",
    }
    canonical_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


def extract_turn_sequence(turn_id: Optional[str]) -> Optional[int]:
    """Extract integer sequence from turn identifier (e.g. 'turn-102' -> 102)."""
    if not turn_id:
        return None
    parts = turn_id.replace("_", "-").split("-")
    for p in reversed(parts):
        if p.isdigit():
            return int(p)
    return None


class VerificationEvidenceInbox:
    """
    In-memory, deterministic Evidence Inbox container.
    Maintains Physical Temporal Wall across turn boundaries.
    """

    def __init__(self) -> None:
        self._items: dict[str, VerificationInboxItem] = {}
        self._job_to_inbox_id: dict[str, str] = {}

    def deposit(
        self,
        source_job_id: str,
        finding: VerificationFinding,
        origin_turn_id: Optional[str] = None,
        eligible_from_turn_id: Optional[str] = None,
        origin_turn_sequence: Optional[int] = None,
        eligible_from_turn_sequence: Optional[int] = None,
        now: Optional[datetime] = None,
    ) -> VerificationInboxItem:
        """
        Idempotently deposit a VerificationFinding into the Inbox.
        Within this inbox instance lifecycle, each source_job_id is idempotently associated
        with at most one InboxItem (ADR-020 Item 19).
        """
        enqueued_time = now or datetime.now(timezone.utc)

        # Idempotency check: prevent duplicate evidence on partial-success worker retry
        if source_job_id and source_job_id in self._job_to_inbox_id:
            existing_id = self._job_to_inbox_id[source_job_id]
            return self._items[existing_id]

        # Derive sequences if not provided
        if origin_turn_sequence is None:
            origin_turn_sequence = extract_turn_sequence(origin_turn_id)
        if eligible_from_turn_sequence is None:
            eligible_from_turn_sequence = extract_turn_sequence(eligible_from_turn_id)
            if eligible_from_turn_sequence is None and origin_turn_sequence is not None:
                eligible_from_turn_sequence = origin_turn_sequence + 1
                if eligible_from_turn_id is None:
                    eligible_from_turn_id = f"turn-{eligible_from_turn_sequence}"

        inbox_id = f"inbox-{uuid4().hex[:10]}"
        item = VerificationInboxItem(
            inbox_id=inbox_id,
            source_job_id=source_job_id,
            finding=finding,
            origin_turn_id=origin_turn_id,
            eligible_from_turn_id=eligible_from_turn_id,
            origin_turn_sequence=origin_turn_sequence,
            eligible_from_turn_sequence=eligible_from_turn_sequence,
            enqueued_at=enqueued_time,
            consumed_at=None,
            consumed_by_turn_id=None,
        )
        self._items[inbox_id] = item
        if source_job_id:
            self._job_to_inbox_id[source_job_id] = inbox_id
        return item

    def peek_unconsumed(self) -> tuple[VerificationInboxItem, ...]:
        """Read-only view of all unconsumed inbox items regardless of turn."""
        return tuple(item for item in self._items.values() if item.consumed_at is None)

    def drain_for_turn(
        self,
        consumer_turn_id: str,
        consumer_turn_sequence: Optional[int] = None,
        now: Optional[datetime] = None,
    ) -> tuple[VerificationInboxItem, ...]:
        """
        Drain eligible unconsumed findings for the consumer turn.
        PHYSICAL TEMPORAL WALL ENFORCEMENT (ADR-020 Item 17):
        - Items originating in consumer_turn_id are strictly invisible and unconsumable.
        - Earliest Eligible Turn Semantics: An item is consumable in eligible_from_turn_sequence
          or any subsequent turn (consumer_sequence >= eligible_sequence).
        """
        drain_time = now or datetime.now(timezone.utc)
        eligible_items: list[VerificationInboxItem] = []

        if consumer_turn_sequence is None:
            consumer_turn_sequence = extract_turn_sequence(consumer_turn_id)

        for inbox_id, item in list(self._items.items()):
            if item.consumed_at is not None:
                continue

            # 1. Physical Temporal Wall: item cannot be consumed in its origin turn!
            if item.origin_turn_id is not None and item.origin_turn_id == consumer_turn_id:
                continue
            if item.origin_turn_sequence is not None and consumer_turn_sequence is not None:
                if item.origin_turn_sequence == consumer_turn_sequence:
                    continue

            # 2. Earliest eligible turn enforcement (Scheme B: true earliest turn semantics)
            if item.eligible_from_turn_sequence is not None and consumer_turn_sequence is not None:
                if consumer_turn_sequence < item.eligible_from_turn_sequence:
                    continue
            elif item.eligible_from_turn_id is not None:
                # Fallback for opaque IDs without numerical sequence:
                if item.eligible_from_turn_id != consumer_turn_id:
                    continue

            # Mark as consumed
            updated_item = item.model_copy(
                update={
                    "consumed_at": drain_time,
                    "consumed_by_turn_id": consumer_turn_id,
                }
            )
            self._items[inbox_id] = updated_item
            eligible_items.append(updated_item)

        return tuple(eligible_items)

    def get_item(self, inbox_id: str) -> Optional[VerificationInboxItem]:
        """Retrieve an inbox item by ID."""
        return self._items.get(inbox_id)

    def get_by_job_id(self, job_id: str) -> Optional[VerificationInboxItem]:
        """Retrieve an inbox item by source job ID."""
        inbox_id = self._job_to_inbox_id.get(job_id)
        return self._items.get(inbox_id) if inbox_id else None


class VerificationAsyncOrchestrator:
    """
    Deterministic asynchronous orchestrator managing verification jobs and evidence inbox.
    Guarantees non-blocking enqueue in Turn N and isolation across turn boundaries.
    """

    def __init__(
        self,
        gateway: VerificationGatewayProtocol,
        evaluator: EpistemicSourceEvaluator,
        inbox: Optional[VerificationEvidenceInbox] = None,
    ) -> None:
        self._gateway = gateway
        self._evaluator = evaluator
        self._inbox = inbox or VerificationEvidenceInbox()
        self._jobs: dict[str, VerificationJob] = {}
        # Queue dedup index: (origin_turn_id, claim_dedup_key) -> active job_id
        # Differentiates claim identity from job scheduling identity across turns (ADR-020 Item 18).
        self._active_turn_job_index: dict[tuple[Optional[str], str], str] = {}

    @property
    def inbox(self) -> VerificationEvidenceInbox:
        """Access the underlying Evidence Inbox."""
        return self._inbox

    @property
    def _dedup_index(self) -> dict[Any, str]:
        """Backwards-compatibility view of active turn job index."""
        return self._active_turn_job_index

    def enqueue_verification_job(
        self,
        request: VerificationRequest,
        decision: VerificationDecision,
        origin_turn_id: Optional[str] = None,
        origin_turn_sequence: Optional[int] = None,
        now: Optional[datetime] = None,
    ) -> VerificationDispatchResult:
        """
        Synchronously and non-blockingly enqueue a verification job during Turn N.
        Zero same-turn leak: Turn N returns immediately without waiting for observation results.
        """
        dispatch_time = now or datetime.now(timezone.utc)
        claim_dedup_key = compute_deduplication_key(request)
        if origin_turn_sequence is None:
            origin_turn_sequence = extract_turn_sequence(origin_turn_id)

        job_scope_key = (origin_turn_id, claim_dedup_key)

        # ----------------------------------------------------------------------
        # Checkpoint 6: Turn-Scoped Deduplication & Idempotency
        # Coalesces identical verification requests within the SAME turn.
        # Different turns are permitted to launch fresh verifications (ADR-020 Item 18).
        # ----------------------------------------------------------------------
        if job_scope_key in self._active_turn_job_index:
            existing_job_id = self._active_turn_job_index[job_scope_key]
            existing_job = self._jobs.get(existing_job_id)
            if existing_job and existing_job.status in (
                VerificationJobStatus.QUEUED,
                VerificationJobStatus.IN_PROGRESS,
            ):
                return VerificationDispatchResult(
                    job_id=existing_job.job_id,
                    status=existing_job.status,
                    is_duplicate=True,
                    deduplication_key=claim_dedup_key,
                    dispatched_at=dispatch_time,
                    rationale="Coalesced with active in-flight verification job for same turn.",
                )

        job_id = f"vjob-{uuid4().hex[:10]}"

        # ----------------------------------------------------------------------
        # Policy Suppression Handling
        # ----------------------------------------------------------------------
        if not decision.should_verify:
            suppressed_job = VerificationJob(
                job_id=job_id,
                request_id=request.request_id,
                request=request,
                decision=decision,
                status=VerificationJobStatus.SUPPRESSED_BY_POLICY,
                deduplication_key=claim_dedup_key,
                origin_turn_id=origin_turn_id,
                origin_turn_sequence=origin_turn_sequence,
                created_at=dispatch_time,
                completed_at=dispatch_time,
                error_message=decision.suppression_reason or "Suppressed by policy",
            )
            self._jobs[job_id] = suppressed_job
            return VerificationDispatchResult(
                job_id=job_id,
                status=VerificationJobStatus.SUPPRESSED_BY_POLICY,
                is_duplicate=False,
                deduplication_key=claim_dedup_key,
                dispatched_at=dispatch_time,
                rationale=f"Job suppressed: {decision.suppression_reason or 'Policy restricted'}.",
            )

        new_job = VerificationJob(
            job_id=job_id,
            request_id=request.request_id,
            request=request,
            decision=decision,
            status=VerificationJobStatus.QUEUED,
            deduplication_key=claim_dedup_key,
            origin_turn_id=origin_turn_id,
            origin_turn_sequence=origin_turn_sequence,
            created_at=dispatch_time,
        )
        self._jobs[job_id] = new_job
        self._active_turn_job_index[job_scope_key] = job_id

        return VerificationDispatchResult(
            job_id=job_id,
            status=VerificationJobStatus.QUEUED,
            is_duplicate=False,
            deduplication_key=claim_dedup_key,
            dispatched_at=dispatch_time,
            rationale="Enqueued for asynchronous background verification.",
        )

    def process_next_job(self, now: Optional[datetime] = None) -> Optional[VerificationJob]:
        """
        Deterministic single-step background worker execution.
        Executes gateway observation and evaluator assessment, depositing finding into inbox.
        """
        exec_time = now or datetime.now(timezone.utc)

        # Find first QUEUED job
        target_job: Optional[VerificationJob] = None
        for job in self._jobs.values():
            if job.status == VerificationJobStatus.QUEUED:
                target_job = job
                break

        if target_job is None:
            return None

        # Transition QUEUED -> IN_PROGRESS
        in_progress_job = target_job.model_copy(
            update={
                "status": VerificationJobStatus.IN_PROGRESS,
                "started_at": exec_time,
                "attempt_count": target_job.attempt_count + 1,
            }
        )
        self._jobs[target_job.job_id] = in_progress_job

        try:
            # 1. Gateway observation
            observations = self._gateway.execute_verification(
                request=in_progress_job.request,
                decision=in_progress_job.decision,
                now=exec_time,
            )

            # 2. Epistemic source evaluation
            finding = self._evaluator.evaluate_observations(
                request=in_progress_job.request,
                decision=in_progress_job.decision,
                observations=observations,
                now=exec_time,
            )

            # 3. Determine eligible consumer turn (default next turn if origin is turn-N)
            origin_turn = in_progress_job.origin_turn_id
            origin_seq = in_progress_job.origin_turn_sequence or extract_turn_sequence(origin_turn)
            eligible_seq = (origin_seq + 1) if origin_seq is not None else None
            eligible_turn = f"turn-{eligible_seq}" if eligible_seq is not None else None

            # 4. Idempotently deposit into Inbox
            self._inbox.deposit(
                source_job_id=in_progress_job.job_id,
                finding=finding,
                origin_turn_id=origin_turn,
                eligible_from_turn_id=eligible_turn,
                origin_turn_sequence=origin_seq,
                eligible_from_turn_sequence=eligible_seq,
                now=exec_time,
            )

            # 5. Transition to COMPLETED
            completed_job = in_progress_job.model_copy(
                update={
                    "status": VerificationJobStatus.COMPLETED,
                    "completed_at": exec_time,
                    "finding_id": finding.finding_id,
                }
            )
            self._jobs[target_job.job_id] = completed_job
            job_scope_key = (in_progress_job.origin_turn_id, in_progress_job.deduplication_key)
            self._active_turn_job_index.pop(job_scope_key, None)
            return completed_job

        except TimeoutError as exc:
            # Bounded execution deadline expired
            return self._handle_job_failure(
                job=in_progress_job,
                error_msg=f"Execution timed out: {str(exc)}",
                is_timeout=True,
                now=exec_time,
            )
        except Exception as exc:
            # Operational failure
            return self._handle_job_failure(
                job=in_progress_job,
                error_msg=f"Operational failure: {str(exc)}",
                is_timeout=False,
                now=exec_time,
            )

    def _handle_job_failure(
        self,
        job: VerificationJob,
        error_msg: str,
        is_timeout: bool,
        now: datetime,
    ) -> VerificationJob:
        """
        Handle retry vs terminal failure.
        Checkpoint 8: FAILED/TIMED_OUT is purely operational; NEVER manufactures CONTRADICTED finding!
        """
        if job.attempt_count < job.max_attempts:
            # Retryable: place back into QUEUED
            retried_job = job.model_copy(
                update={
                    "status": VerificationJobStatus.QUEUED,
                    "error_message": f"{error_msg} (queued for retry {job.attempt_count}/{job.max_attempts})",
                }
            )
            self._jobs[job.job_id] = retried_job
            return retried_job

        # Terminal operational failure
        terminal_status = VerificationJobStatus.TIMED_OUT if is_timeout else VerificationJobStatus.FAILED
        failed_job = job.model_copy(
            update={
                "status": terminal_status,
                "completed_at": now,
                "error_message": error_msg,
            }
        )
        self._jobs[job.job_id] = failed_job
        job_scope_key = (job.origin_turn_id, job.deduplication_key)
        self._active_turn_job_index.pop(job_scope_key, None)
        return failed_job

    def get_job(self, job_id: str) -> Optional[VerificationJob]:
        """Retrieve a job by ID."""
        return self._jobs.get(job_id)
