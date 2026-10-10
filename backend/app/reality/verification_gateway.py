"""
verification_gateway.py — Verification Gateway & Adapter Orchestration

Phase 9.4 Deliverable under Architecture Gate v0.2:
- Dispatches and coordinates external observation adapters.
- Strictly adheres to Lock 2 & Checkpoint 2: Gateway != Policy.
    - Policy decision constraints are non-negotiable hard bounds.
    - Gateway cannot expand source kinds, authorities, or cost budgets.
- Strictly adheres to Checkpoint 1: Gateway != Evaluator.
    - Gateway gathers raw ExternalObservation items; it NEVER judges credibility or truth.
- Dual-boundary adapter filtering: checks both SourceKind and SourceAuthority via AdapterDescriptor.
- Request-Decision binding enforcement: rejects authorization context substitution (TOCTOU protection).
- Bounded execution semantics: honors max_queries and passes execution deadline (timeout_seconds).
- Zero mutation authority, zero direct reality updates, zero database writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Protocol, Sequence

from app.reality.observation_adapters import ObservationAdapterProtocol
from app.reality.verification_models import (
    ClaimDomain,
    ExternalObservation,
    SourceAuthority,
    SourceKind,
    VerificationRequest,
)
from app.reality.verification_policy_engine import VerificationDecision


@dataclass(frozen=True)
class AdapterDescriptor:
    """
    Metadata binding an observation adapter to its source kind and authority.
    Enables VerificationGateway to enforce dual-boundary policy constraints.
    """
    adapter_id: str
    source_kind: SourceKind
    source_authority: SourceAuthority
    adapter: ObservationAdapterProtocol


class VerificationGatewayProtocol(Protocol):
    """Protocol for observation gateways."""

    def execute_verification(
        self,
        request: VerificationRequest,
        decision: VerificationDecision,
        now: Optional[datetime] = None,
    ) -> tuple[ExternalObservation, ...]:
        """Collect observations strictly within decision bounds."""
        ...


class VerificationGateway:
    """
    Central dispatcher coordinating external observation adapters.
    Pure bounded observation collection without epistemic evaluation authority.
    """

    def __init__(self, descriptors: Optional[Sequence[AdapterDescriptor]] = None) -> None:
        self._descriptors: list[AdapterDescriptor] = list(descriptors or [])

    def register_adapter(self, descriptor: AdapterDescriptor) -> None:
        """Register a new adapter descriptor with kind and authority metadata."""
        self._descriptors.append(descriptor)

    def get_descriptors(self) -> tuple[AdapterDescriptor, ...]:
        """Return registered adapter descriptors."""
        return tuple(self._descriptors)

    def execute_verification(
        self,
        request: VerificationRequest,
        decision: VerificationDecision,
        now: Optional[datetime] = None,
    ) -> tuple[ExternalObservation, ...]:
        """
        Execute observation collection strictly bounded by VerificationDecision constraints.
        Enforces TOCTOU binding, dual-boundary filtering, and cost budgets.
        """
        # ----------------------------------------------------------------------
        # Checkpoint 5: Request <-> Decision Identity Binding (TOCTOU Guard)
        # ----------------------------------------------------------------------
        if decision.request_id != request.request_id:
            raise ValueError(
                f"Verification authorization mismatch: decision.request_id '{decision.request_id}' "
                f"does not match request.request_id '{request.request_id}'. Execution rejected."
            )

        # ----------------------------------------------------------------------
        # Checkpoint 2: Gateway != Policy (Honor suppression and should_verify)
        # ----------------------------------------------------------------------
        if not decision.should_verify:
            return ()

        # ----------------------------------------------------------------------
        # Checkpoint 6: Dual-Boundary Enforcement (SourceKind AND SourceAuthority)
        # ----------------------------------------------------------------------
        eligible_descriptors = [
            desc
            for desc in self._descriptors
            if desc.source_kind in decision.allowed_source_kinds
            and desc.source_authority in decision.allowed_authorities
        ]

        if not eligible_descriptors:
            return ()

        # ----------------------------------------------------------------------
        # Bounded Execution & Cost Budget Fan-out Enforcement
        # ----------------------------------------------------------------------
        max_queries = max(1, decision.cost_budget.max_queries)
        timeout_seconds = decision.cost_budget.timeout_seconds
        target_entity = "Aevum" if request.claim_domain == ClaimDomain.PERSONAL_REALITY else None

        collected: list[ExternalObservation] = []

        last_error: Optional[Exception] = None

        for desc in eligible_descriptors:
            if len(collected) >= max_queries:
                break

            remaining_limit = max_queries - len(collected)
            try:
                observations = desc.adapter.observe(
                    claim_key=request.claim_key,
                    allowed_source_kinds=decision.allowed_source_kinds,
                    limit=remaining_limit,
                    target_entity_name=target_entity,
                    timeout_seconds=timeout_seconds,
                )
            except TimeoutError:
                raise
            except Exception as exc:
                last_error = exc
                continue

            for obs in observations:
                collected.append(obs)
                if len(collected) >= max_queries:
                    break

        if not collected and last_error is not None:
            raise last_error

        return tuple(collected)
