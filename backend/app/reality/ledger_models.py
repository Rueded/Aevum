"""Data models for Reality Ledger visual projection and audit."""

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.reality.models import FactAuthority, FactSource, FactStatus, LedgerTier


class LedgerItem(BaseModel):
    """Visual projection of an individual reality fact in the Reality Ledger."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str = Field(..., description="Dot-notated fact key")
    category: str = Field(..., description="Fact domain category")
    value: Any = Field(..., description="Current value of the fact")
    tier: LedgerTier = Field(..., description="Categorization tier: Green, Yellow, or Red")
    source: FactSource = Field(..., description="Provenance origin")
    authority: FactAuthority = Field(..., description="Authority level")
    status: FactStatus = Field(..., description="Lifecycle status")
    confidence: float = Field(..., description="Epistemic confidence [0.0, 1.0]")
    locked: bool = Field(..., description="Whether locked by user")
    explanation: Optional[str] = Field(default=None, description="Inference or bridge explanation")
    created_at: str = Field(..., description="ISO 8601 created timestamp")
    updated_at: str = Field(..., description="ISO 8601 updated timestamp")


class RealityLedgerProjection(BaseModel):
    """Aggregate multi-tier projection of Aevum's complete reality state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    character_id: str = Field(default="aevum", description="Target character identifier")
    green_user_editable: list[LedgerItem] = Field(
        default_factory=list,
        description="User-configurable identity, family, and baseline facts.",
    )
    yellow_aevum_emergent: list[LedgerItem] = Field(
        default_factory=list,
        description="Aevum-inferred facts, lifestyle traits, and candidate proposals.",
    )
    red_system_integrity: list[LedgerItem] = Field(
        default_factory=list,
        description="Foundational system baseline anchors and integrity constraints.",
    )
    total_facts: int = Field(default=0, description="Total facts in reality ledger")
    locked_count: int = Field(default=0, description="Total user-locked facts")
    candidate_count: int = Field(default=0, description="Total unconfirmed candidate facts")
    average_confidence: float = Field(default=1.0, description="Mean epistemic confidence across facts")
