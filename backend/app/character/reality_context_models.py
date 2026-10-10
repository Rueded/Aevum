"""Typed Data Transfer Objects (DTOs) for Governed Reality Context Assembly (Phase 7D.4).

Hard Architectural Invariants:
1. Truth Type != Authority != Plausibility != Probability != Choice != Authorization.
2. FactAuthority is a categorical classification enum; numerical scores MUST NOT participate
   in truth ranking, candidate scoring, choice selection, or canonical promotion.
3. No raw unverified evidence is injected as canonical facts; evidence is represented
   strictly as structured evidence references.
4. Choice decisions carry explicit non-canonical status (SELECTED_BUT_NOT_PROMOTED).
   Free-form rationale_description is strictly excluded from character-world context.
5. No uncalibrated confidence float on canonical facts.
6. Replay determinism: Runtime timestamps (assembled_at) exist exclusively in audit
   metadata and MUST NOT be serialized into prompt payloads or prompt SHA-256 hashes.
"""

from datetime import datetime, timezone
import enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.reality.models import FactAuthority, FactSource
from app.reality.volatility_policy import FactVolatilityCategory


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EpistemicTruthType(str, enum.Enum):
    """Categorical boundary distinguishing truth varieties across reality subsystems."""

    OBJECTIVE_WORLD_FACT = "OBJECTIVE_WORLD_FACT"
    SIMULATED_BIOGRAPHY_FACT = "SIMULATED_BIOGRAPHY_FACT"
    USER_ASSERTION = "USER_ASSERTION"
    EVIDENCE_REFERENCE = "EVIDENCE_REFERENCE"
    CANDIDATE_HYPOTHESIS = "CANDIDATE_HYPOTHESIS"
    CHOICE_DECISION = "CHOICE_DECISION"
    EPHEMERAL_REPAIR_INTERPRETATION = "EPHEMERAL_REPAIR_INTERPRETATION"
    CONVERSATION_LOCAL = "CONVERSATION_LOCAL"
    TEMPORAL_TRAJECTORY_PLURALITY = "TEMPORAL_TRAJECTORY_PLURALITY"
    LONGITUDINAL_TEMPORAL_CONTEXT = "LONGITUDINAL_TEMPORAL_CONTEXT"


class RealityItemProvenance(BaseModel):
    """Immutable structured audit provenance attached to every projected reality item.

    Hard Invariants:
    - Zero numerical authority truth scoring.
    - Zero uncalibrated confidence floats.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    item_id: str = Field(..., description="Deterministic item identifier.")
    fact_key: str = Field(..., description="Dot-notated slot or attribute key.")
    truth_type: EpistemicTruthType = Field(..., description="Categorical truth classification.")
    authority: FactAuthority = Field(..., description="Categorical authority classification.")
    source_type: FactSource = Field(..., description="Origin source classification.")
    evidence_family_ids: tuple[str, ...] = Field(default_factory=tuple, description="IDs of corroborating evidence families.")
    candidate_id: Optional[str] = Field(default=None, description="Linked candidate hypothesis ID, if applicable.")
    choice_decision_id: Optional[str] = Field(default=None, description="Linked choice decision ID, if applicable.")
    promotion_id: Optional[str] = Field(default=None, description="Linked promotion record ID, if applicable.")
    volatility_class: FactVolatilityCategory = Field(default=FactVolatilityCategory.IMMUTABLE_CORE, description="Temporal volatility class.")


class GovernedRealityItem(BaseModel):
    """Single item projected into prompt context with internal structured provenance."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provenance: RealityItemProvenance = Field(..., description="Immutable provenance metadata.")
    value: Any = Field(..., description="Underlying domain value.")
    is_canonical: bool = Field(default=False, description="Whether item holds canonical ground truth authority.")


class ContextBudgetMetrics(BaseModel):
    """Metrics tracking presentation budget adherence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_canonical_facts: int = Field(default=0, description="Total canonical facts presented.")
    total_candidates_presented: int = Field(default=0, description="Candidates displayed within presentation budget.")
    total_choice_decisions_presented: int = Field(default=0, description="Choice decisions displayed.")
    total_memories_presented: int = Field(default=0, description="Memories displayed.")
    total_repair_items_presented: int = Field(default=0, description="Ephemeral repair items displayed.")
    pruned_candidates_count: int = Field(default=0, description="Candidates excluded by presentation budget.")
    pruned_memories_count: int = Field(default=0, description="Memories excluded by presentation budget.")


class ContextAuditMetadata(BaseModel):
    """Runtime audit metadata kept OUTSIDE prompt serialization to preserve replay determinism.

    Hard Invariant:
    assembled_at and execution timings MUST NOT be serialized into prompt envelopes or prompt hashes.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    assembled_at: datetime = Field(default_factory=_utc_now, description="UTC assembly timestamp (audit only).")
    execution_duration_ms: float = Field(default=0.0, description="Context assembly latency in ms.")
    context_hash_sha256: str = Field(..., description="Deterministic SHA-256 hash of the canonical prompt payload.")
    character_id: str = Field(default="aevum", description="Character entity identifier.")


class GovernedRealityContext(BaseModel):
    """Authoritative DTO holding structured provenance for all projected context items."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    canonical_items: tuple[GovernedRealityItem, ...] = Field(default_factory=tuple, description="Canonical reality facts.")
    world_knowledge_items: tuple[GovernedRealityItem, ...] = Field(default_factory=tuple, description="Objective external world facts.")
    candidate_items: tuple[GovernedRealityItem, ...] = Field(default_factory=tuple, description="Active candidate hypotheses (non-canonical).")
    choice_items: tuple[GovernedRealityItem, ...] = Field(default_factory=tuple, description="Selected choices awaiting promotion (non-canonical).")
    repair_items: tuple[GovernedRealityItem, ...] = Field(default_factory=tuple, description="Turn-scoped ephemeral repair items.")
    evidence_items: tuple[GovernedRealityItem, ...] = Field(default_factory=tuple, description="Structured evidence references.")
    user_claim_items: tuple[GovernedRealityItem, ...] = Field(default_factory=tuple, description="Unverified user claim observations.")
    memory_items: tuple[GovernedRealityItem, ...] = Field(default_factory=tuple, description="Retrieved memory reference items.")
    temporal_items: tuple[GovernedRealityItem, ...] = Field(default_factory=tuple, description="Temporal trajectory plurality items (non-canonical).")
    longitudinal_items: tuple[GovernedRealityItem, ...] = Field(default_factory=tuple, description="Longitudinal temporal context items (non-canonical).")
    budget_metrics: ContextBudgetMetrics = Field(..., description="Presentation budget metrics.")
    audit_metadata: ContextAuditMetadata = Field(..., description="Runtime audit metadata.")
