"""Inference domain models and transient contracts for Phase 8A (Autonomous Reality & Life Inference).

Strict Invariants:
- InferenceProposalRequest and CandidateEnvelope are transient DTOs (NEVER stored as DB models).
- Suggested premise roles in CandidateEnvelope are explicitly non-authoritative suggestions.
- Bounded input contracts: no raw transcripts, no unrestricted biography.
- Preserves distinct canonical origin semantics (PRIMARY_CANONICAL vs DERIVED_CANONICAL).
"""

from datetime import datetime, timezone
import enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from app.reality.models import CoreFactItem, FactSource, FactStatus


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PremiseRole(str, enum.Enum):
    """Categorical relevance role of a premise in motivating a candidate hypothesis.

    NOTE: Proposer-supplied roles in CandidateEnvelope are non-authoritative suggestions.
    The evaluation layer deterministically computes and validates premise weights.
    """

    DIRECT_SUPPORT = "DIRECT_SUPPORT"      # Directly aligns with and motivates choice
    CONTEXT_SUPPORT = "CONTEXT_SUPPORT"    # Provides enabling contextual or environmental backing
    CONSTRAINT = "CONSTRAINT"              # Institutional, financial, or prerequisite boundary
    CONTRADICTING = "CONTRADICTING"        # Known canonical fact working against this option


class PremiseOriginCategory(str, enum.Enum):
    """Categorical classification of canonical fact provenance for inference grounding.

    Enforces the Primary-Anchored Derivation Invariant:
    Every autonomous inference request must be grounded by at least one PRIMARY_CANONICAL fact.
    Purely derived (AEVUM_INFERRED -> AEVUM_INFERRED) chains without a primary anchor are forbidden.
    """

    PRIMARY_CANONICAL = "PRIMARY_CANONICAL"  # Grounded in user statements, observation, or system baseline
    DERIVED_CANONICAL = "DERIVED_CANONICAL"  # Grounded in prior autonomous inference (FactSource.AEVUM_INFERRED)
    NON_CANONICAL = "NON_CANONICAL"          # Candidate, unconfirmed, disputed, or non-canonical fact


def categorize_fact_origin(fact: CoreFactItem) -> PremiseOriginCategory:
    """Categorize a CoreFactItem's provenance to enforce primary-anchored premise rules."""
    if fact.status != FactStatus.CANONICAL:
        return PremiseOriginCategory.NON_CANONICAL

    if fact.source == FactSource.AEVUM_INFERRED:
        return PremiseOriginCategory.DERIVED_CANONICAL

    if fact.source in (FactSource.USER_CONFIGURED, FactSource.CONVERSATION, FactSource.SYSTEM_BASELINE):
        return PremiseOriginCategory.PRIMARY_CANONICAL

    return PremiseOriginCategory.NON_CANONICAL


class InferenceValueTier(str, enum.Enum):
    """Categorical structural significance tier of an attribute slot for autonomous inference."""

    HIGH = "HIGH"      # Central identity / life-stage milestones (e.g. major, pathway)
    MEDIUM = "MEDIUM"  # Meaningful lifestyle or vocational aspirations (e.g. career aspiration)
    LOW = "LOW"        # Trivial, low-impact preferences (e.g. beverage, commute mode)
    ZERO = "ZERO"      # Forbidden invariant slots or unanchored speculative narratives


class InferenceValueAssessment(BaseModel):
    """Deterministic outcome of evaluating whether a slot is worth inferring autonomously."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    slot_name: str = Field(..., description="Target attribute slot evaluated.")
    tier: InferenceValueTier = Field(..., description="Structural importance tier.")
    is_worth_inferring: bool = Field(..., description="True if eligible for autonomous inference opportunity.")
    reason: str = Field(..., description="Human-auditable explanation of assessment.")


class InferenceProposalRequest(BaseModel):
    """Immutable, transient proposal contract issued to a LifeHypothesisProposer.

    Strict Invariants:
    - Transient DTO only: never persisted as a database table or entity.
    - Bounded context: exposes only target slot, domain, authorized premise keys/snapshots,
      and known constraints.
    - Prohibits raw conversation transcripts and unrestricted biography dumps.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    target_slot: str = Field(..., description="Dot-notated attribute slot, e.g. 'education.major'.")
    domain: str = Field(..., description="Functional life domain, e.g. 'education', 'career'.")
    authorized_premise_keys: tuple[str, ...] = Field(
        ...,
        description="Keys of canonical facts authorizing this inference request.",
    )
    premise_snapshots: dict[str, Any] = Field(
        ...,
        description="Read-only serialized snapshot of canonical premise values.",
    )
    known_constraints: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Static institutional or temporal boundaries grounding the slot.",
    )
    inference_cycle_id: str = Field(
        ...,
        description="Deterministic identifier for this specific inference execution cycle.",
    )
    created_at: datetime = Field(
        default_factory=_utc_now,
        description="UTC creation timestamp.",
    )

    @field_validator("target_slot", "domain", "inference_cycle_id")
    @classmethod
    def validate_non_empty(cls, v: str, info: ValidationInfo) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"{info.field_name} must not be empty or whitespace.")
        return v.strip()

    @field_validator("target_slot")
    @classmethod
    def validate_dot_notation(cls, v: str) -> str:
        if "." not in v:
            raise ValueError(f"target_slot '{v}' must be dot-notated (e.g. 'education.major').")
        return v


class CandidateEnvelope(BaseModel):
    """Immutable, transient proposal DTO emitted by a LifeHypothesisProposer.

    Strict Invariants:
    - Transient DTO only: never persisted as a database record or ORM model.
    - Converted directly into Phase 7's CandidateHypothesis after validation and normalization.
    - suggested_premise_roles are NON-AUTHORITATIVE suggestions: they cannot directly
      inflate context support or scoring without deterministic validation.
    - rationale is display-only metadata: strictly non-epistemic (cannot be parsed as fact).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    domain: str = Field(..., description="Functional domain of proposed candidate.")
    slot: str = Field(..., description="Target attribute slot, e.g. 'education.major'.")
    raw_value: Any = Field(..., description="Raw proposed fact value prior to normalization.")
    suggested_premise_keys: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Canonical premise keys suggested by proposer as justification.",
    )
    suggested_premise_roles: dict[str, PremiseRole] = Field(
        default_factory=dict,
        description="Non-authoritative role suggestions (e.g. DIRECT_SUPPORT).",
    )
    rationale: str = Field(
        default="",
        description="Display-only narrative explanation (STRICTLY NON-EPISTEMIC).",
    )

    @field_validator("domain", "slot")
    @classmethod
    def validate_non_empty(cls, v: str, info: ValidationInfo) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"{info.field_name} must not be empty or whitespace.")
        return v.strip()

    @field_validator("slot")
    @classmethod
    def validate_dot_notation(cls, v: str) -> str:
        if "." not in v:
            raise ValueError(f"slot '{v}' must be dot-notated (e.g. 'education.major').")
        return v
