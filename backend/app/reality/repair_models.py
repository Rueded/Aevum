"""Domain models for Minimal Reality Repair (Phase 7D.3).

Defines the 5-level repair hierarchy, structured repair results, and
strict invariants prohibiting compensatory biography invention.
"""

from datetime import datetime, timezone
import enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RepairLevel(str, enum.Enum):
    """Deterministic 5-level hierarchy for Minimal Reality Repair.
    
    The resolver must attempt the lowest-cost valid repair first:
    LEVEL 1 -> LEVEL 2 -> LEVEL 3 -> LEVEL 4 -> LEVEL 5.
    """

    LEVEL_1_SOCIAL_MISSPEAK = "SOCIAL_MISSPEAK"
    LEVEL_2_TEMPORAL_REINTERPRETATION = "TEMPORAL_REINTERPRETATION"
    LEVEL_3_FACT_INVALIDATION = "FACT_INVALIDATION"
    LEVEL_4_RE_ANCHORING = "RE_ANCHORING"
    LEVEL_5_GRACEFUL_UNCERTAINTY = "GRACEFUL_UNCERTAINTY"


class RealityRepairResult(BaseModel):
    """Structured resolution produced by RealityRepairService.

    Hard Invariants:
    - canonical_mutated is strictly FALSE for all repair operations.
    - compensatory_biography_created is strictly FALSE (no fake semester breaks,
      family visits, transfers, or commuting arrangements).
    - Level 4 re-anchoring is an EPHEMERAL_REPAIR_INTERPRETATION for the current turn only.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    repair_level: RepairLevel = Field(..., description="Determined level in 5-level hierarchy.")
    is_repaired: bool = Field(default=True, description="Whether contradiction was resolved at this level.")
    repair_action: str = Field(..., description="Machine-auditable description of repair action taken.")
    invalidated_claim_ids: tuple[str, ...] = Field(
        default_factory=tuple,
        description="IDs of unconfirmed claims/candidates invalidated under Level 3.",
    )
    temporal_split: Optional[dict[str, Any]] = Field(
        default=None,
        description="Independently supported temporal assignments under Level 2.",
    )
    reanchored_context: Optional[dict[str, Any]] = Field(
        default=None,
        description="Ephemeral contextual entity re-anchoring for current reasoning turn (Level 4).",
    )
    social_guidance: Optional[str] = Field(
        default=None,
        description="Instruction for conversational response without mutating facts (Level 1).",
    )
    unresolved_reasons: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Diagnostic explanation when unresolved under Level 5.",
    )
    compensatory_biography_created: bool = Field(
        default=False,
        description="Hard lock: Repair MUST NEVER fabricate compensatory biography.",
    )
    canonical_mutated: bool = Field(
        default=False,
        description="Hard lock: Repair operations never directly mutate canonical reality.",
    )
    rationale: str = Field(
        default="",
        description="Explainable audit reasoning synthesized from structured conditions.",
    )
    created_at: datetime = Field(default_factory=_utc_now, description="UTC creation timestamp.")

    @field_validator("compensatory_biography_created")
    @classmethod
    def validate_no_compensatory_biography(cls, v: bool) -> bool:
        if v is True:
            raise ValueError(
                "Violation of Hard Invariant: Reality Repair is strictly forbidden from "
                "creating compensatory biography."
            )
        return v

    @field_validator("canonical_mutated")
    @classmethod
    def validate_no_canonical_mutation(cls, v: bool) -> bool:
        if v is True:
            raise ValueError(
                "Violation of Hard Invariant: Reality Repair is strictly forbidden from "
                "directly mutating canonical reality."
            )
        return v
