"""Belief and Epistemic domain models for Reality & Belief Engine (Phase 7B.3).

Explicitly decouples Belief State (what Aevum currently believes) from Reality State
(canonical facts in Character Core). Tracks speaker attribution, Unknown classification,
temporal scopes, and belief supersession.
"""

from datetime import datetime, timezone
import enum
import math
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _validate_normalized_float(v: float, field_name: str) -> float:
    if math.isnan(v) or math.isinf(v):
        raise ValueError(f"{field_name} must be a finite number.")
    if v < 0.0 or v > 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0 inclusive.")
    return float(v)


class FactSubject(str, enum.Enum):
    """Authoritative subject attribution preventing identity cross-contamination."""

    AEVUM = "AEVUM"    # Pertains to Aevum's identity, preferences, lifestyle, biography
    USER = "USER"      # Pertains to the user's statements, life, preferences
    NPC = "NPC"        # Pertains to friends, roommates, family, third parties
    WORLD = "WORLD"    # Pertains to external reality, geographic facts, laws of physics, game lore


class EpistemicStatus(str, enum.Enum):
    """Confidence and verification status of a belief claim."""

    KNOWN = "KNOWN"                  # Grounded in confirmed core reality or verified world knowledge
    PLAUSIBLE = "PLAUSIBLE"          # Plausibly inferred from existing anchors, not yet canonical
    UNCERTAIN = "UNCERTAIN"          # Speculative, ambiguous, or lacks sufficient grounding
    CONTRADICTED = "CONTRADICTED"    # Conflicts with established reality, timeline, or world knowledge
    REJECTED = "REJECTED"            # Dismissed as false (e.g. user asserting impossible physics)


class UnknownType(str, enum.Enum):
    """Categorization of unspecified or missing knowledge (Unknown != Private)."""

    INFERABLE = "INFERABLE"                  # Harmless blank fields suitable for emergent taste formation
    UNVERIFIABLE = "UNVERIFIABLE"            # External anomalous claims requiring official evidence
    AMBIGUOUS = "AMBIGUOUS"                  # Requires conversational clarification
    HIGH_IMPACT = "HIGH_IMPACT"              # Major biographical claims requiring strict gating
    GENUINELY_PRIVATE = "GENUINELY_PRIVATE"  # Third-party confidences protected by HardBoundaryPolicy


class BeliefClaim(BaseModel):
    """Internal belief held by Aevum, tracking provenance, temporal scope, and revision history."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    belief_id: str = Field(..., description="Unique deterministic or generated identifier for this belief.")
    subject: FactSubject = Field(default=FactSubject.AEVUM, description="Attributed entity.")
    fact_key: str = Field(..., description="Dot-notated fact key, e.g. 'preferences.study_beverage'.")
    proposed_value: Any = Field(..., description="The value believed to be true.")
    epistemic_status: EpistemicStatus = Field(default=EpistemicStatus.PLAUSIBLE, description="Current epistemic state.")
    confidence: float = Field(default=0.8, description="Confidence in this belief [0.0, 1.0].")
    temporal_scope: Optional[str] = Field(default=None, description="e.g. PAST, CURRENT, HABITUAL, ETERNAL.")
    observed_at: datetime = Field(default_factory=_utc_now, description="When the claim/evidence was observed.")
    effective_from: Optional[str] = Field(default=None, description="When the belief/fact became true in life.")
    effective_until: Optional[str] = Field(default=None, description="When the belief/fact ceased being true (if any).")
    evidence_ids: tuple[str, ...] = Field(default_factory=tuple, description="Pointers to supporting EvidenceRecords.")
    supersedes_id: Optional[str] = Field(default=None, description="ID of prior belief superseded by this revision.")
    inference_permission: bool = Field(default=True, description="Whether Aevum is permitted to internally form this belief.")
    disclosure_permission: bool = Field(default=False, description="Whether Aevum is permitted to assert this to the user as fact.")
    created_at: datetime = Field(default_factory=_utc_now, description="UTC creation timestamp.")
    updated_at: datetime = Field(default_factory=_utc_now, description="UTC update timestamp.")

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, v: Any, info: Any) -> float:
        return _validate_normalized_float(float(v), info.field_name)

    @field_validator("belief_id", "fact_key")
    @classmethod
    def validate_non_empty(cls, v: str, info: Any) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"{info.field_name} must not be empty or whitespace.")
        return v.strip()
