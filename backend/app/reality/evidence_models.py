"""Evidence domain models for Reality & Belief Engine (Phase 7B.3).

Tracks atomic evidence provenance: what was observed, who stated it, when, and via what mode.
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


class EvidenceSource(str, enum.Enum):
    """Source channel where evidence originated."""

    USER_CONVERSATION = "USER_CONVERSATION"
    AEVUM_STATEMENT = "AEVUM_STATEMENT"
    LIFE_ACTIVITY = "LIFE_ACTIVITY"
    WORLD_KNOWLEDGE = "WORLD_KNOWLEDGE"
    SYSTEM_BASELINE = "SYSTEM_BASELINE"


class EvidenceExtractionMode(str, enum.Enum):
    """Method by which evidence was extracted from the source channel."""

    EXPLICIT_ASSERTION = "EXPLICIT_ASSERTION"
    INFERRED_PREFERENCE = "INFERRED_PREFERENCE"
    TEMPORAL_DEDUCTION = "TEMPORAL_DEDUCTION"
    RECONCILIATION_BRIDGE = "RECONCILIATION_BRIDGE"


class EvidenceRecord(BaseModel):
    """Immutable audit record of a specific piece of observed evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(..., description="Deterministic or unique identifier for this evidence record.")
    source: EvidenceSource = Field(..., description="Source origin of the evidence.")
    raw_text: str = Field(..., description="Verbatim text or statement that constitutes the evidence.")
    speaker: str = Field(..., description="Attributed speaker or entity: AEVUM, USER, NPC, or WORLD.")
    observed_at: datetime = Field(default_factory=_utc_now, description="UTC timestamp when evidence was observed.")
    confidence: float = Field(default=1.0, description="Confidence in this evidence extraction [0.0, 1.0].")
    extraction_mode: EvidenceExtractionMode = Field(
        default=EvidenceExtractionMode.EXPLICIT_ASSERTION,
        description="Mode of extraction from the source.",
    )
    context_id: Optional[str] = Field(default=None, description="Optional message ID, turn ID, or activity ID.")

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, v: Any, info: Any) -> float:
        return _validate_normalized_float(float(v), info.field_name)

    @field_validator("id", "raw_text", "speaker")
    @classmethod
    def validate_non_empty(cls, v: str, info: Any) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"{info.field_name} must not be empty or whitespace.")
        return v.strip()
