"""
verification_models.py — Epistemic Verification Data Contracts & Schemas

Phase 9.1 Deliverable under Architecture Gate v0.2:
- Pure immutable data contracts, enums, and provenance schemas.
- Decouples ClaimDomain from SourceAuthority (Two-Dimensional Matrix).
- Decouples VerificationJobStatus (task lifecycle) from ClaimEpistemicStatus (epistemic outcome).
- Strict non-probabilistic representation: zero float confidence scores or pseudo-probabilities.
- Preserves complete evaluation and observation provenance.
- Decouples physical observation (ExternalObservation) from cognitive evaluation.
- Enforces Entity Binding Isolation (Lock 8) and Zero Mutation Authority (Lock 1).

Zero network calls, zero database writes, zero LLM dependencies, zero mutation authority.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ==============================================================================
# 1. Epistemic Categorical Enums
# ==============================================================================


class ClaimDomain(str, Enum):
    """
    Categorical domain of the proposition being verified.
    Orthogonal to source authority.
    """
    PERSONAL_REALITY = "PERSONAL_REALITY"  # First-person subjective biography, life events, personal relationships
    WORLD_REALITY = "WORLD_REALITY"        # Institutional rules, academic calendars, objective external facts, geography


class SourceAuthority(str, Enum):
    """
    Authoritative standing of an information source.
    Authority is domain-relative and does NOT directly equate to absolute truth.
    """
    FIRST_PARTY_PERSONAL = "FIRST_PARTY_PERSONAL"       # User explicit statement or primary character self-assertion
    PRIMARY_INSTITUTIONAL = "PRIMARY_INSTITUTIONAL"     # Official university syllabus, government registrar, accredited authority
    OFFICIAL_PUBLIC_RECORD = "OFFICIAL_PUBLIC_RECORD"   # Public gazette, government statistics, official public registries
    CORROBORATED_SECONDARY = "CORROBORATED_SECONDARY"   # Reputable reporting, multiple concordant secondary sources
    UNVERIFIED_EXTERNAL = "UNVERIFIED_EXTERNAL"         # General web page, blog, social media, unvetted external source


class SourceKind(str, Enum):
    """Physical or operational origin of an observation."""
    USER_DIALOGUE = "USER_DIALOGUE"
    INSTITUTIONAL_PORTAL = "INSTITUTIONAL_PORTAL"
    PUBLIC_REGISTRY = "PUBLIC_REGISTRY"
    WEB_DOCUMENT = "WEB_DOCUMENT"
    SYSTEM_INTERNAL = "SYSTEM_INTERNAL"


class VerificationJobStatus(str, Enum):
    """
    Operational lifecycle of the verification task itself.
    Strictly decoupled from epistemic claim status.
    """
    QUEUED = "QUEUED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    SUPPRESSED_BY_POLICY = "SUPPRESSED_BY_POLICY"


class ClaimEpistemicStatus(str, Enum):
    """
    Cognitive/epistemic finding regarding the verified claim.
    Strictly decoupled from job execution status.
    """
    SUPPORTED = "SUPPORTED"                      # Evidence corroborates the claim within its target scope
    CONTRADICTED = "CONTRADICTED"                # Evidence refutes/contradicts the claim within its target scope
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE" # Retrieved evidence lacks sufficient signal to assess
    AMBIGUOUS_CONFLICT = "AMBIGUOUS_CONFLICT"    # Multiple conflicting sources cannot be deterministically resolved
    OUT_OF_SCOPE = "OUT_OF_SCOPE"                # Observation does not apply to the specific claim/temporal window


class VerificationScope(str, Enum):
    """Degree of alignment between the observation and the claim specification."""
    EXACT_MATCH = "EXACT_MATCH"          # Direct entity + attribute + temporal window alignment
    PARTIAL_OVERLAP = "PARTIAL_OVERLAP"  # Overlapping domain or timeframe requiring explicit bounded extrapolation
    GENERAL_ANALOGY = "GENERAL_ANALOGY"  # General institutional pattern, not specific instance
    UNMATCHED = "UNMATCHED"              # No meaningful scope alignment


class VerificationUrgency(str, Enum):
    """Operational urgency of the verification request."""
    IMMEDIATE_TURN = "IMMEDIATE_TURN"          # High-priority blocker for active decision
    BACKGROUND_ROUTINE = "BACKGROUND_ROUTINE"  # Deferred routine verification
    SCHEDULED_OFFLINE = "SCHEDULED_OFFLINE"    # Run during idle maintenance window


class EvidenceFreshness(str, Enum):
    """Temporal validity and freshness of the retrieved evidence."""
    CURRENT = "CURRENT"                          # Actively valid for the target temporal interval
    HISTORICAL_RECORD = "HISTORICAL_RECORD"      # Accurate for a past epoch, may or may not hold currently
    SUPERSEDED_OUTDATED = "SUPERSEDED_OUTDATED"  # Known to have been replaced by a newer standard/rule
    UNDETERMINED = "UNDETERMINED"                # Temporal freshness cannot be verified


class ConsequenceTier(str, Enum):
    """
    Impact level of the claim if verified, refuted, or erroneously updated.
    Guides verification policy gating and required evidence rigor.
    """
    LOW = "LOW"            # Conversational preference, minor trivia, benign interest
    MEDIUM = "MEDIUM"      # Secondary life activity, minor hobby, general knowledge
    HIGH = "HIGH"          # Core academic standing, primary biography, sensitive relationship
    CRITICAL = "CRITICAL"  # Core character identity inviolability, legal/institutional status


# ==============================================================================
# 2. Immutable Provenance & Physical Observation Contracts
# ==============================================================================


class VerificationProvenance(BaseModel):
    """
    Immutable lineage record for an external observation.
    Captures source identity, authority, and retrieval timestamps without evaluation judgments.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: str = Field(..., description="Unique deterministic identifier for the source")
    source_authority: SourceAuthority = Field(..., description="Categorical authority level of the source")
    source_kind: SourceKind = Field(..., description="Operational kind of source")
    retrieval_timestamp: datetime = Field(..., description="Timestamp when observation was retrieved")
    source_uri_or_identifier: Optional[str] = Field(None, description="URI, document path, or reference identifier")
    raw_content_digest_sha256: Optional[str] = Field(None, description="SHA-256 hash of raw observed text/payload")


class ExternalObservation(BaseModel):
    """
    Immutable representation of an external physical observation ("What did I observe?").
    Strictly decoupled from cognitive evaluation ("What is this worth?").
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    observation_id: str = Field(..., description="Unique deterministic identifier for this observation")
    source_provenance: VerificationProvenance = Field(..., description="Lineage and authority metadata")
    observed_content_snippet: str = Field(..., description="Raw text or formatted excerpt observed")
    structured_payload: dict[str, Any] = Field(default_factory=dict, description="Parsed structured data, if any")
    observed_at: datetime = Field(..., description="Timestamp when observation was made")
    temporal_anchor: Optional[datetime] = Field(None, description="Inherent temporal anchor of observed fact, if known")
    observed_entity_name: Optional[str] = Field(
        None,
        description="Name of entity mentioned in observation. NOTE: Lock 8 dictates entity match != Aevum match!"
    )


# ==============================================================================
# 3. Verification Request Contract
# ==============================================================================


class VerificationRequest(BaseModel):
    """
    Structured, immutable request to seek external verification for an uncertain claim.
    Emitted by reality orchestration or policy engine; possesses zero execution authority.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    request_id: str = Field(..., description="Unique identifier for this verification request")
    created_at: datetime = Field(..., description="Timestamp when request was formulated")
    claim_domain: ClaimDomain = Field(..., description="Domain of proposition to verify")
    claim_key: str = Field(..., description="Key of claim (e.g., 'education.usm.programme_duration')")
    claim_value: Any = Field(..., description="Asserted value to be tested")
    consequence_tier: ConsequenceTier = Field(..., description="Consequence tier guiding policy rigor")
    urgency: VerificationUrgency = Field(default=VerificationUrgency.BACKGROUND_ROUTINE)
    target_temporal_interval: Optional[Tuple[datetime, datetime]] = Field(
        None,
        description="Target (start, end) interval for which claim must hold"
    )
    entity_binding_anchor: Optional[str] = Field(
        None,
        description="Required explicit identity anchor for personal claims (Lock 8)"
    )
    initiating_turn_id: Optional[str] = Field(
        None,
        description="ID of the reality turn that spawned this request (for temporal isolation tracking)"
    )

    @field_validator("claim_key")
    @classmethod
    def validate_claim_key_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("claim_key must not be empty or blank")
        return v.strip()

    @model_validator(mode="after")
    def validate_temporal_interval_and_entity_binding(self) -> VerificationRequest:
        if self.target_temporal_interval is not None:
            start, end = self.target_temporal_interval
            if start > end:
                raise ValueError(f"target_temporal_interval start ({start}) cannot be after end ({end})")

        # Lock 8 enforcement: Personal reality claims require an explicit entity binding anchor
        if self.claim_domain == ClaimDomain.PERSONAL_REALITY and not self.entity_binding_anchor:
            raise ValueError(
                "Personal reality claims require an explicit entity_binding_anchor to prevent "
                "unanchored entity-name aliasing (Lock 8 Entity Binding Isolation)."
            )
        return self


# ==============================================================================
# 4. Evaluation Provenance & Finding Contracts
# ==============================================================================


class VerificationEvaluationProvenance(BaseModel):
    """Audit lineage for an epistemic evaluation performed on observations."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluator_name: str = Field(..., description="Name of the evaluator component")
    evaluator_version: str = Field(..., description="Version of the evaluator ruleset")
    evaluated_at: datetime = Field(..., description="Timestamp when evaluation was executed")
    rule_ids_applied: tuple[str, ...] = Field(default_factory=tuple, description="IDs of rules triggered")
    rationale: str = Field(..., description="Categorical rationale explanation for the verdict")


class VerificationFinding(BaseModel):
    """
    Immutable cognitive outcome of evaluating external observations against a claim.
    Possesses ZERO mutation authority; strictly advisory finding for existing reality machinery.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str = Field(..., description="Unique identifier for this finding")
    request_id: str = Field(..., description="Associated VerificationRequest ID")
    claim_domain: ClaimDomain = Field(..., description="Domain of verified claim")
    claim_key: str = Field(..., description="Key of verified claim")
    epistemic_status: ClaimEpistemicStatus = Field(..., description="Categorical epistemic conclusion")
    scope: VerificationScope = Field(..., description="Degree of scope alignment")
    freshness: EvidenceFreshness = Field(..., description="Temporal freshness assessment")
    contributing_observation_ids: tuple[str, ...] = Field(
        default_factory=tuple,
        description="IDs of ExternalObservation items that contributed to this finding"
    )
    provenance: VerificationEvaluationProvenance = Field(..., description="Evaluation audit trail")
    contradiction_details: Optional[str] = Field(
        None,
        description="Structured explanation if epistemic_status is CONTRADICTED or AMBIGUOUS_CONFLICT"
    )
    claim_value: Optional[Any] = Field(None, description="Observed or verified claim value")
    entity_binding_anchor: Optional[str] = Field(None, description="Explicit entity anchor (Lock 8)")


# ==============================================================================
# 5. Pipeline Ingestion & Evidence Inbox Payloads
# ==============================================================================


class VerificationEvidencePayload(BaseModel):
    """
    Adapter payload formatted strictly for ingestion into the existing reality pipeline
    (CandidateHypothesisSet, RealityRepairService, or EvidenceRecord).
    Zero mutation authority; enters as Evidence only (Lock 9 & Lock 10).
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    payload_id: str = Field(..., description="Unique identifier for this evidence payload")
    finding_id: str = Field(..., description="Reference to origin VerificationFinding")
    claim_domain: ClaimDomain = Field(..., description="Domain of claim")
    claim_key: str = Field(..., description="Key of claim")
    claim_value: Optional[Any] = Field(None, description="Observed or verified claim value")
    entity_binding_anchor: Optional[str] = Field(None, description="Explicit entity anchor (Lock 8)")
    epistemic_status: ClaimEpistemicStatus = Field(..., description="Finding outcome")
    evidence_text: str = Field(..., description="Human/LLM-readable evidence statement")
    is_refutation: bool = Field(default=False, description="True if evidence contradicts an existing candidate/fact")
    target_candidate_id: Optional[str] = Field(None, description="Candidate ID being supported or refuted, if any")
    target_canonical_fact_key: Optional[str] = Field(None, description="Canonical fact key facing repair, if any")
    created_at: datetime = Field(..., description="Timestamp when evidence payload was assembled")


class VerificationInboxItem(BaseModel):
    """
    Immutable container representing an asynchronously completed finding in the Evidence Inbox.
    Maintains Physical Temporal Wall across turn boundaries (ADR-020 Item 17).
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    inbox_id: str = Field(..., description="Unique identifier for inbox entry")
    source_job_id: str = Field(default="", description="ID of VerificationJob that produced this finding (for idempotency)")
    finding: VerificationFinding = Field(..., description="Completed finding ready for ingestion")
    origin_turn_id: Optional[str] = Field(None, description="Turn ID where job was enqueued (cannot be drained here)")
    eligible_from_turn_id: Optional[str] = Field(None, description="Earliest turn ID allowed to consume this item")
    origin_turn_sequence: Optional[int] = Field(None, ge=0, description="Sequential integer index of origin turn")
    eligible_from_turn_sequence: Optional[int] = Field(None, ge=0, description="Earliest sequential turn index allowed to consume this item")
    enqueued_at: datetime = Field(..., description="Timestamp when finding was delivered to inbox")
    consumed_at: Optional[datetime] = Field(None, description="Timestamp when consumed in turn orchestration")
    consumed_by_turn_id: Optional[str] = Field(None, description="Turn ID that ingested this item")

    @model_validator(mode="after")
    def validate_temporal_wall_invariants(self) -> VerificationInboxItem:
        if self.origin_turn_id is not None and self.eligible_from_turn_id is not None:
            if self.origin_turn_id == self.eligible_from_turn_id:
                raise ValueError(
                    f"Temporal Wall Invariant Violated: origin_turn_id ({self.origin_turn_id}) "
                    f"cannot equal eligible_from_turn_id ({self.eligible_from_turn_id})."
                )
        if self.origin_turn_sequence is not None and self.eligible_from_turn_sequence is not None:
            if self.eligible_from_turn_sequence <= self.origin_turn_sequence:
                raise ValueError(
                    f"Temporal Wall Invariant Violated: eligible_from_turn_sequence ({self.eligible_from_turn_sequence}) "
                    f"must be strictly greater than origin_turn_sequence ({self.origin_turn_sequence})."
                )
        return self


class VerificationJob(BaseModel):
    """
    Asynchronous verification job lifecycle container.
    Decoupled from epistemic claim outcome.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    job_id: str = Field(..., description="Unique job identifier")
    request_id: str = Field(..., description="Associated VerificationRequest ID")
    request: VerificationRequest = Field(..., description="Original immutable request")
    decision: Any = Field(..., description="Immutable policy decision (VerificationDecision)")
    status: VerificationJobStatus = Field(default=VerificationJobStatus.QUEUED)
    attempt_count: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=3, ge=1)
    deduplication_key: str = Field(..., description="Canonical SHA-256 claim deduplication key")
    origin_turn_id: Optional[str] = Field(None, description="Turn where verification originated")
    origin_turn_sequence: Optional[int] = Field(None, ge=0, description="Sequential integer index of origin turn")
    created_at: datetime = Field(..., description="Job enqueue timestamp")
    started_at: Optional[datetime] = Field(None, description="Job execution start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Job terminal state timestamp")
    finding_id: Optional[str] = Field(None, description="Resulting finding ID upon successful evaluation")
    error_message: Optional[str] = Field(None, description="Operational failure reason if job failed")


class VerificationDispatchResult(BaseModel):
    """
    Immediate non-blocking return DTO from enqueue operations in Turn N.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    job_id: str = Field(..., description="Dispatched or reused job identifier")
    status: VerificationJobStatus = Field(..., description="Immediate queue status")
    is_duplicate: bool = Field(default=False, description="True if coalesced with existing active job")
    deduplication_key: str = Field(..., description="Applied deduplication key")
    dispatched_at: datetime = Field(..., description="Dispatch timestamp")
    rationale: str = Field(..., description="Categorical queue dispatch rationale")
