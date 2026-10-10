"""
verification_reconciler.py — Evidence Reconciliation & Refutation Routing

Phase 9.5 Deliverable under Architecture Gate v0.2:
- Connects asynchronous VerificationEvidenceInbox outcomes into the existing governed reality pipeline.
- Anti-Shortcut Invariant (Anti-Magical-Promotion):
    - VerificationFinding -> VerificationEvidencePayload -> Existing Reality Pipeline -> Canonical Reality.
    - Zero direct mutation of canonical reality (no set_fact(), no PromotionAuthorizationToken).
- ADR-020 Item 21 Lock:
    - Domain-Gated Reconciliation Routing: WORLD_REALITY findings strictly cannot enter personal
      candidate, repair, or biography-promotion pipeline. 0 world-fact mutation in 9.5.
- ADR-020 Item 22 Lock:
    - Reconciler Routing != Repair Decision: Reconciler never selects RepairLevel.
      RealityRepairService owns the 5-level repair hierarchy.
- ADR-020 Item 23 Lock:
    - Evaluation-Level Candidate Exclusion != Candidate Lifecycle Mutation.
      EXCLUDE_CANDIDATE_FROM_COMPETITION generates candidate_ids_to_exclude for current-turn
      derived competition view. Zero candidate lifecycle mutation, all_candidates remains intact.
- ADR-020 Item 24 Lock:
    - Multi-Factor Candidate Matching (ClaimDomain, claim_key, claim_value, entity_binding_anchor,
      reality_taxonomy/slot_name).
- ADR-020 Item 25 Lock:
    - Ambiguity Preservation & Typed Repair Boundary: AMBIGUOUS_CONFLICT preserves uncertainty (zero repair).
      All repair requests use strictly typed VerificationRepairRequest without dict[str, Any].
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any, Optional, Sequence
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.character.core_models import CharacterCore
from app.reality.candidate_models import (
    CandidateHypothesis,
    CandidateLifecycleState,
    EvidenceFamily,
    InferenceEdgeType,
    PlausibilityBreakdown,
    ProvenanceLineage,
    RealityTaxonomy,
)
from app.reality.verification_models import (
    ClaimDomain,
    ClaimEpistemicStatus,
    VerificationEvidencePayload,
    VerificationFinding,
    VerificationInboxItem,
)


class ReconciliationActionType(str, enum.Enum):
    """Categorical reconciliation routing action."""

    AUGMENT_CANDIDATE = "AUGMENT_CANDIDATE"
    PROPOSE_CANDIDATE = "PROPOSE_CANDIDATE"
    EXCLUDE_CANDIDATE_FROM_COMPETITION = "EXCLUDE_CANDIDATE_FROM_COMPETITION"
    ROUTE_TO_REPAIR = "ROUTE_TO_REPAIR"
    PRESERVE_UNCERTAINTY = "PRESERVE_UNCERTAINTY"
    NO_ACTION = "NO_ACTION"


class VerificationTemporalSplitContext(BaseModel):
    """Typed temporal interval context for temporal conflict repair."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    conflicting_interval: Optional[tuple[int, int]] = Field(
        None, description="Conflicting temporal interval [start_year, end_year]"
    )
    observed_interval: Optional[tuple[int, int]] = Field(
        None, description="Observed temporal interval [start_year, end_year]"
    )
    temporal_relation: str = Field(
        ...,
        description="Categorical temporal relation (e.g. 'PAST_VS_PRESENT', 'DISJOINT', 'SUPERSEDED')",
    )


class VerificationEntityDisambiguationContext(BaseModel):
    """Typed entity anchor context for entity disambiguation / re-anchoring repair."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    observed_entity_anchor: str = Field(
        ..., description="Explicit entity anchor in external observation"
    )
    canonical_entity_anchor: str = Field(
        ..., description="Explicit entity anchor in canonical reality / candidate"
    )
    ambiguity_reason: str = Field(
        ..., description="Categorical reason for entity disambiguation / alias divergence"
    )


class VerificationRepairRequest(BaseModel):
    """
    Typed, immutable contract packaging factual contradiction context for RealityRepairService.
    Reconciler provides strictly factual inputs; NEVER chooses RepairLevel (ADR-020 Item 22).
    `claimed_value` and `existing_value` are opaque domain values, strictly NOT control structures.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    inbox_id: str = Field(..., description="Source inbox item identifier")
    finding_id: str = Field(..., description="Source verification finding identifier")
    claim_domain: ClaimDomain = Field(
        ..., description="Must be PERSONAL_REALITY for personal repair"
    )
    claim_key: str = Field(..., description="Canonical fact key facing repair")
    claimed_value: Any = Field(..., description="Opaque domain value observed/verified")
    existing_value: Any = Field(..., description="Opaque domain value in CharacterCore")
    evidence_payload: VerificationEvidencePayload = Field(..., description="Typed evidence payload")
    target_canonical_fact_key: Optional[str] = Field(None, description="Exact key in CharacterCore")
    target_candidate_id: Optional[str] = Field(
        None, description="Candidate ID if unconfirmed candidate is refuted"
    )
    temporal_split_context: Optional[VerificationTemporalSplitContext] = Field(
        None, description="Typed timeline context if temporal evidence exists"
    )
    entity_disambiguation_context: Optional[VerificationEntityDisambiguationContext] = Field(
        None, description="Typed disambiguation context if entity evidence exists"
    )
    compensatory_biography_requested: bool = Field(
        default=False, description="Strictly False: no lore fabrication"
    )
    rationale: str = Field(..., description="Audit rationale explaining the contradiction")


class ReconciliationRoutingItem(BaseModel):
    """Immutable routing instruction for a single reconciled inbox finding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    action_type: ReconciliationActionType = Field(...)
    inbox_id: str = Field(...)
    finding_id: str = Field(...)
    claim_domain: ClaimDomain = Field(...)
    claim_key: str = Field(...)
    evidence_payload: VerificationEvidencePayload = Field(...)
    target_candidate_id: Optional[str] = Field(None)
    target_canonical_fact_key: Optional[str] = Field(None)
    repair_request: Optional[VerificationRepairRequest] = Field(None)
    rationale: str = Field(...)


class VerificationReconciliationResult(BaseModel):
    """Aggregate result of reconciling all drained inbox items for a turn."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    consumer_turn_id: str = Field(...)
    consumer_turn_sequence: Optional[int] = Field(None, ge=0)
    routing_items: tuple[ReconciliationRoutingItem, ...] = Field(default_factory=tuple)
    candidate_hypotheses_to_inject: tuple[CandidateHypothesis, ...] = Field(
        default_factory=tuple
    )
    candidate_ids_to_exclude: tuple[str, ...] = Field(default_factory=tuple)
    repair_requests: tuple[VerificationRepairRequest, ...] = Field(default_factory=tuple)
    reconciled_at: datetime = Field(...)


class VerificationReconciler:
    """
    Deterministic cognitive reconciler routing asynchronous verification findings
    into the existing governed reality pipeline (Phase 9.5 Deliverable).
    """

    def __init__(self) -> None:
        pass

    def reconcile(
        self,
        inbox_items: Sequence[VerificationInboxItem],
        core: CharacterCore,
        active_candidates: Sequence[CandidateHypothesis],
        consumer_turn_id: str = "turn-0",
        consumer_turn_sequence: Optional[int] = None,
        now: Optional[datetime] = None,
    ) -> VerificationReconciliationResult:
        """
        Reconcile a sequence of drained VerificationInboxItem objects for the current turn.
        Returns immutable VerificationReconciliationResult containing routing instructions,
        candidates to inject/exclude from current-turn competition, and typed repair requests.
        """
        reconcile_time = now or datetime.now(timezone.utc)
        routing_items: list[ReconciliationRoutingItem] = []
        candidates_to_inject: list[CandidateHypothesis] = []
        candidate_ids_to_exclude: list[str] = []
        repair_requests: list[VerificationRepairRequest] = []

        for item in inbox_items:
            finding = item.finding

            # ------------------------------------------------------------------
            # ADR-020 Item 21 Lock: Domain-Gated Routing Gate
            # WORLD_REALITY findings MUST NOT enter the personal candidate,
            # repair, or biography-promotion pipeline. Phase 9.5 performs no
            # world-knowledge mutation; such findings may only be preserved as
            # verification provenance/context for a separately governed process.
            # ------------------------------------------------------------------
            if finding.claim_domain == ClaimDomain.WORLD_REALITY:
                payload = VerificationEvidencePayload(
                    payload_id=f"vev-{uuid4().hex[:10]}",
                    finding_id=finding.finding_id,
                    claim_domain=finding.claim_domain,
                    claim_key=finding.claim_key,
                    claim_value=finding.claim_value,
                    entity_binding_anchor=finding.entity_binding_anchor,
                    epistemic_status=finding.epistemic_status,
                    evidence_text=f"World observation for '{finding.claim_key}': {finding.epistemic_status.value}",
                    is_refutation=(finding.epistemic_status == ClaimEpistemicStatus.CONTRADICTED),
                    target_candidate_id=None,
                    target_canonical_fact_key=None,
                    created_at=reconcile_time,
                )
                routing_item = ReconciliationRoutingItem(
                    action_type=ReconciliationActionType.NO_ACTION,
                    inbox_id=item.inbox_id,
                    finding_id=finding.finding_id,
                    claim_domain=finding.claim_domain,
                    claim_key=finding.claim_key,
                    evidence_payload=payload,
                    target_candidate_id=None,
                    target_canonical_fact_key=None,
                    repair_request=None,
                    rationale=(
                        "WORLD_REALITY finding preserved as non-personal verification context only; "
                        "strictly barred from personal candidate, repair, or promotion pipeline (Lock 21)."
                    ),
                )
                routing_items.append(routing_item)
                continue

            # ------------------------------------------------------------------
            # Personal Reality Processing (ClaimDomain.PERSONAL_REALITY)
            # ------------------------------------------------------------------
            claim_val = finding.claim_value
            anchor = finding.entity_binding_anchor

            # Case A: SUPPORTED
            if finding.epistemic_status == ClaimEpistemicStatus.SUPPORTED:
                matched_cand = self._match_candidate(finding, active_candidates)

                if matched_cand is not None:
                    # Augment existing candidate with verified external evidence
                    payload = VerificationEvidencePayload(
                        payload_id=f"vev-{uuid4().hex[:10]}",
                        finding_id=finding.finding_id,
                        claim_domain=finding.claim_domain,
                        claim_key=finding.claim_key,
                        claim_value=claim_val,
                        entity_binding_anchor=anchor,
                        epistemic_status=ClaimEpistemicStatus.SUPPORTED,
                        evidence_text=f"External verification corroborates candidate fact '{finding.claim_key}'.",
                        is_refutation=False,
                        target_candidate_id=matched_cand.candidate_id,
                        target_canonical_fact_key=None,
                        created_at=reconcile_time,
                    )
                    augmented_cand = self._build_augmented_candidate(matched_cand, payload, reconcile_time)
                    candidates_to_inject.append(augmented_cand)
                    candidate_ids_to_exclude.append(matched_cand.candidate_id)

                    routing_item = ReconciliationRoutingItem(
                        action_type=ReconciliationActionType.AUGMENT_CANDIDATE,
                        inbox_id=item.inbox_id,
                        finding_id=finding.finding_id,
                        claim_domain=finding.claim_domain,
                        claim_key=finding.claim_key,
                        evidence_payload=payload,
                        target_candidate_id=matched_cand.candidate_id,
                        target_canonical_fact_key=None,
                        repair_request=None,
                        rationale=f"Candidate '{matched_cand.candidate_id}' augmented with verified external evidence.",
                    )
                    routing_items.append(routing_item)

                else:
                    # No matching candidate: check if valid personal anchor exists to propose new candidate
                    if anchor:
                        payload = VerificationEvidencePayload(
                            payload_id=f"vev-{uuid4().hex[:10]}",
                            finding_id=finding.finding_id,
                            claim_domain=finding.claim_domain,
                            claim_key=finding.claim_key,
                            claim_value=claim_val,
                            entity_binding_anchor=anchor,
                            epistemic_status=ClaimEpistemicStatus.SUPPORTED,
                            evidence_text=f"External verification supports personal claim '{finding.claim_key}'.",
                            is_refutation=False,
                            target_candidate_id=None,
                            target_canonical_fact_key=None,
                            created_at=reconcile_time,
                        )
                        proposed_cand = self._build_proposed_candidate(finding, anchor, payload, reconcile_time)
                        candidates_to_inject.append(proposed_cand)

                        routing_item = ReconciliationRoutingItem(
                            action_type=ReconciliationActionType.PROPOSE_CANDIDATE,
                            inbox_id=item.inbox_id,
                            finding_id=finding.finding_id,
                            claim_domain=finding.claim_domain,
                            claim_key=finding.claim_key,
                            evidence_payload=payload,
                            target_candidate_id=proposed_cand.candidate_id,
                            target_canonical_fact_key=None,
                            repair_request=None,
                            rationale="New candidate proposed into competition based on verified personal claim.",
                        )
                        routing_items.append(routing_item)
                    else:
                        payload = VerificationEvidencePayload(
                            payload_id=f"vev-{uuid4().hex[:10]}",
                            finding_id=finding.finding_id,
                            claim_domain=finding.claim_domain,
                            claim_key=finding.claim_key,
                            claim_value=claim_val,
                            entity_binding_anchor=None,
                            epistemic_status=ClaimEpistemicStatus.SUPPORTED,
                            evidence_text="Claim supported but lacks entity anchor; cannot propose candidate.",
                            is_refutation=False,
                            target_candidate_id=None,
                            target_canonical_fact_key=None,
                            created_at=reconcile_time,
                        )
                        routing_item = ReconciliationRoutingItem(
                            action_type=ReconciliationActionType.NO_ACTION,
                            inbox_id=item.inbox_id,
                            finding_id=finding.finding_id,
                            claim_domain=finding.claim_domain,
                            claim_key=finding.claim_key,
                            evidence_payload=payload,
                            target_candidate_id=None,
                            target_canonical_fact_key=None,
                            repair_request=None,
                            rationale="Unanchored personal claim supported; cannot propose candidate without anchor.",
                        )
                        routing_items.append(routing_item)

            # Case B: CONTRADICTED
            elif finding.epistemic_status == ClaimEpistemicStatus.CONTRADICTED:
                matched_cand = self._match_candidate(finding, active_candidates)

                if matched_cand is not None:
                    # Refutation of unconfirmed candidate: exclude from current-turn competition view
                    # ADR-020 Item 23: Evaluation-level exclusion ONLY. Zero candidate lifecycle mutation!
                    payload = VerificationEvidencePayload(
                        payload_id=f"vev-{uuid4().hex[:10]}",
                        finding_id=finding.finding_id,
                        claim_domain=finding.claim_domain,
                        claim_key=finding.claim_key,
                        claim_value=claim_val,
                        entity_binding_anchor=anchor,
                        epistemic_status=ClaimEpistemicStatus.CONTRADICTED,
                        evidence_text=f"External verification refutes unconfirmed candidate for '{finding.claim_key}'.",
                        is_refutation=True,
                        target_candidate_id=matched_cand.candidate_id,
                        target_canonical_fact_key=None,
                        created_at=reconcile_time,
                    )
                    candidate_ids_to_exclude.append(matched_cand.candidate_id)

                    repair_req = VerificationRepairRequest(
                        inbox_id=item.inbox_id,
                        finding_id=finding.finding_id,
                        claim_domain=finding.claim_domain,
                        claim_key=finding.claim_key,
                        claimed_value=claim_val if claim_val is not None else "VERIFIED_REFUTATION",
                        existing_value=matched_cand.proposed_value,
                        evidence_payload=payload,
                        target_canonical_fact_key=None,
                        target_candidate_id=matched_cand.candidate_id,
                        temporal_split_context=None,
                        entity_disambiguation_context=None,
                        compensatory_biography_requested=False,
                        rationale=f"Unconfirmed candidate '{matched_cand.candidate_id}' refuted by external observation.",
                    )
                    repair_requests.append(repair_req)

                    routing_item = ReconciliationRoutingItem(
                        action_type=ReconciliationActionType.EXCLUDE_CANDIDATE_FROM_COMPETITION,
                        inbox_id=item.inbox_id,
                        finding_id=finding.finding_id,
                        claim_domain=finding.claim_domain,
                        claim_key=finding.claim_key,
                        evidence_payload=payload,
                        target_candidate_id=matched_cand.candidate_id,
                        target_canonical_fact_key=None,
                        repair_request=repair_req,
                        rationale=f"Candidate '{matched_cand.candidate_id}' excluded from competition view due to refutation.",
                    )
                    routing_items.append(routing_item)

                else:
                    # Check if a canonical personal fact exists in CharacterCore
                    existing_canonical_val = core.facts.get(finding.claim_key)
                    if existing_canonical_val is not None:
                        # Refutation of canonical personal fact: route to RealityRepairService
                        payload = VerificationEvidencePayload(
                            payload_id=f"vev-{uuid4().hex[:10]}",
                            finding_id=finding.finding_id,
                            claim_domain=finding.claim_domain,
                            claim_key=finding.claim_key,
                            claim_value=claim_val,
                            entity_binding_anchor=anchor,
                            epistemic_status=ClaimEpistemicStatus.CONTRADICTED,
                            evidence_text=f"External verification contradicts canonical fact '{finding.claim_key}'.",
                            is_refutation=True,
                            target_candidate_id=None,
                            target_canonical_fact_key=finding.claim_key,
                            created_at=reconcile_time,
                        )
                        repair_req = VerificationRepairRequest(
                            inbox_id=item.inbox_id,
                            finding_id=finding.finding_id,
                            claim_domain=finding.claim_domain,
                            claim_key=finding.claim_key,
                            claimed_value=claim_val if claim_val is not None else "VERIFIED_REFUTATION",
                            existing_value=existing_canonical_val,
                            evidence_payload=payload,
                            target_canonical_fact_key=finding.claim_key,
                            target_candidate_id=None,
                            temporal_split_context=None,
                            entity_disambiguation_context=None,
                            compensatory_biography_requested=False,
                            rationale=f"Canonical fact '{finding.claim_key}' contradicts verified external observation.",
                        )
                        repair_requests.append(repair_req)

                        routing_item = ReconciliationRoutingItem(
                            action_type=ReconciliationActionType.ROUTE_TO_REPAIR,
                            inbox_id=item.inbox_id,
                            finding_id=finding.finding_id,
                            claim_domain=finding.claim_domain,
                            claim_key=finding.claim_key,
                            evidence_payload=payload,
                            target_candidate_id=None,
                            target_canonical_fact_key=finding.claim_key,
                            repair_request=repair_req,
                            rationale=f"Canonical contradiction on '{finding.claim_key}' routed to RealityRepairService.",
                        )
                        routing_items.append(routing_item)
                    else:
                        payload = VerificationEvidencePayload(
                            payload_id=f"vev-{uuid4().hex[:10]}",
                            finding_id=finding.finding_id,
                            claim_domain=finding.claim_domain,
                            claim_key=finding.claim_key,
                            claim_value=claim_val,
                            entity_binding_anchor=anchor,
                            epistemic_status=ClaimEpistemicStatus.CONTRADICTED,
                            evidence_text=f"Contradiction on '{finding.claim_key}' has no active candidate or canonical fact.",
                            is_refutation=True,
                            target_candidate_id=None,
                            target_canonical_fact_key=None,
                            created_at=reconcile_time,
                        )
                        routing_item = ReconciliationRoutingItem(
                            action_type=ReconciliationActionType.NO_ACTION,
                            inbox_id=item.inbox_id,
                            finding_id=finding.finding_id,
                            claim_domain=finding.claim_domain,
                            claim_key=finding.claim_key,
                            evidence_payload=payload,
                            target_candidate_id=None,
                            target_canonical_fact_key=None,
                            repair_request=None,
                            rationale="Refuted claim does not correspond to any active candidate or canonical fact.",
                        )
                        routing_items.append(routing_item)

            # Case C: AMBIGUOUS_CONFLICT
            elif finding.epistemic_status == ClaimEpistemicStatus.AMBIGUOUS_CONFLICT:
                # ADR-020 Item 25: Ambiguity preservation. Zero repair invocation, zero invalidation, zero fact modification.
                payload = VerificationEvidencePayload(
                    payload_id=f"vev-{uuid4().hex[:10]}",
                    finding_id=finding.finding_id,
                    claim_domain=finding.claim_domain,
                    claim_key=finding.claim_key,
                    claim_value=claim_val,
                    entity_binding_anchor=anchor,
                    epistemic_status=ClaimEpistemicStatus.AMBIGUOUS_CONFLICT,
                    evidence_text=f"Identity ambiguity on '{finding.claim_key}'; preserving uncertainty.",
                    is_refutation=False,
                    target_candidate_id=None,
                    target_canonical_fact_key=None,
                    created_at=reconcile_time,
                )
                routing_item = ReconciliationRoutingItem(
                    action_type=ReconciliationActionType.PRESERVE_UNCERTAINTY,
                    inbox_id=item.inbox_id,
                    finding_id=finding.finding_id,
                    claim_domain=finding.claim_domain,
                    claim_key=finding.claim_key,
                    evidence_payload=payload,
                    target_candidate_id=None,
                    target_canonical_fact_key=None,
                    repair_request=None,
                    rationale=(
                        "Identity ambiguity or conflicting observations detected. Preserving uncertainty; "
                        "zero repair invocation, zero candidate invalidation (Lock 8 & Lock 25)."
                    ),
                )
                routing_items.append(routing_item)

            # Case D: INSUFFICIENT_EVIDENCE or OUT_OF_SCOPE
            else:
                payload = VerificationEvidencePayload(
                    payload_id=f"vev-{uuid4().hex[:10]}",
                    finding_id=finding.finding_id,
                    claim_domain=finding.claim_domain,
                    claim_key=finding.claim_key,
                    claim_value=claim_val,
                    entity_binding_anchor=anchor,
                    epistemic_status=finding.epistemic_status,
                    evidence_text=f"Epistemic status is {finding.epistemic_status.value}; maintaining status quo.",
                    is_refutation=False,
                    target_candidate_id=None,
                    target_canonical_fact_key=None,
                    created_at=reconcile_time,
                )
                routing_item = ReconciliationRoutingItem(
                    action_type=ReconciliationActionType.NO_ACTION,
                    inbox_id=item.inbox_id,
                    finding_id=finding.finding_id,
                    claim_domain=finding.claim_domain,
                    claim_key=finding.claim_key,
                    evidence_payload=payload,
                    target_candidate_id=None,
                    target_canonical_fact_key=None,
                    repair_request=None,
                    rationale=f"Epistemic status is {finding.epistemic_status.value}; maintaining status quo.",
                )
                routing_items.append(routing_item)

        return VerificationReconciliationResult(
            consumer_turn_id=consumer_turn_id,
            consumer_turn_sequence=consumer_turn_sequence,
            routing_items=tuple(routing_items),
            candidate_hypotheses_to_inject=tuple(candidates_to_inject),
            candidate_ids_to_exclude=tuple(candidate_ids_to_exclude),
            repair_requests=tuple(repair_requests),
            reconciled_at=reconcile_time,
        )

    def _match_candidate(
        self,
        finding: VerificationFinding,
        active_candidates: Sequence[CandidateHypothesis],
    ) -> Optional[CandidateHypothesis]:
        """
        Multi-Factor Candidate Matching (ADR-020 Item 24):
        Strictly requires alignment across:
        1. ClaimDomain (must be PERSONAL_REALITY -> SIMULATED_BIOGRAPHY_FACT)
        2. claim_key == candidate.slot_name
        3. entity_binding_anchor == candidate.entity_id (Lock 8 Entity Binding Isolation)
        4. claim_value == candidate.proposed_value (if claim_value provided)
        """
        anchor = finding.entity_binding_anchor

        for cand in active_candidates:
            # 1. Slot alignment
            if cand.slot_name != finding.claim_key:
                continue

            # 2. Taxonomy alignment
            if cand.reality_taxonomy != RealityTaxonomy.SIMULATED_BIOGRAPHY_FACT:
                continue

            # 3. Entity binding anchor alignment (Lock 8)
            # Anchor is strictly required for personal candidates!
            if not anchor or anchor != cand.entity_id:
                continue

            # 4. Value alignment (if claim_value was recorded)
            if finding.claim_value is not None:
                if str(cand.proposed_value).strip().lower() != str(finding.claim_value).strip().lower():
                    continue

            return cand

        return None

    def _build_augmented_candidate(
        self,
        candidate: CandidateHypothesis,
        payload: VerificationEvidencePayload,
        now: datetime,
    ) -> CandidateHypothesis:
        """Create an augmented CandidateHypothesis enriched with external verification evidence."""
        ext_family = EvidenceFamily(
            family_id=f"evfam_verif_{uuid4().hex[:8]}",
            source_type="EXTERNAL_VERIFICATION",
            cluster_key=f"{candidate.entity_id}.{candidate.slot_name}.verified",
            mention_count=1,
            session_ids=(),
            first_observed_at=now,
            last_observed_at=now,
        )
        new_families = candidate.evidence_families + (ext_family,)

        augmented_plausibility = PlausibilityBreakdown.create(
            prior_weight=candidate.plausibility.prior_weight,
            evidence_grounding_score=0.90,
            coherence_score=max(candidate.plausibility.coherence_score, 0.85),
            utility_score=candidate.plausibility.utility_score,
        )

        return candidate.model_copy(
            update={
                "evidence_families": new_families,
                "plausibility": augmented_plausibility,
                "updated_at": now,
            }
        )

    def _build_proposed_candidate(
        self,
        finding: VerificationFinding,
        anchor: str,
        payload: VerificationEvidencePayload,
        now: datetime,
    ) -> CandidateHypothesis:
        """Create a new CandidateHypothesis based on a verified personal claim."""
        ext_family = EvidenceFamily(
            family_id=f"evfam_prop_{uuid4().hex[:8]}",
            source_type="EXTERNAL_VERIFICATION",
            cluster_key=f"{anchor}.{finding.claim_key}.verified",
            mention_count=1,
            session_ids=(),
            first_observed_at=now,
            last_observed_at=now,
        )
        provenance = ProvenanceLineage(
            origin_id=f"verif_prop_{uuid4().hex[:8]}",
            evidence_family_ids=(ext_family.family_id,),
            inference_depth=0,
            derivation_path=("External observation verified personal reality claim",),
        )
        plausibility = PlausibilityBreakdown.create(
            prior_weight=0.50,
            evidence_grounding_score=0.85,
            coherence_score=0.80,
            utility_score=0.50,
        )
        return CandidateHypothesis(
            candidate_id=f"cand_verif_{uuid4().hex[:10]}",
            entity_id=anchor,
            slot_name=finding.claim_key,
            proposed_value=finding.claim_value if finding.claim_value is not None else "VERIFIED_FACT",
            reality_taxonomy=RealityTaxonomy.SIMULATED_BIOGRAPHY_FACT,
            inference_depth=0,
            inference_edge_type=InferenceEdgeType.DIRECT_ATTRIBUTE,
            plausibility=plausibility,
            provenance=provenance,
            evidence_families=(ext_family,),
            lifecycle_state=CandidateLifecycleState.GENERATED,
            is_quarantined=False,
            quarantine_reason=None,
            created_at=now,
            updated_at=now,
        )
