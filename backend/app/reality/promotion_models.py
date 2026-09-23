"""Promotion domain models for Reality & Belief Engine (Phase 7B.3).

Defines promotion decision structures, promotion types, and policy gating
for elevating candidate facts into canonical Character Core reality.
"""

from datetime import datetime, timezone
import enum
import math
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.reality.models import FactAuthority, FactStatus


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _validate_normalized_float(v: float, field_name: str) -> float:
    if math.isnan(v) or math.isinf(v):
        raise ValueError(f"{field_name} must be a finite number.")
    if v < 0.0 or v > 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0 inclusive.")
    return float(v)


class PromotionType(str, enum.Enum):
    """Categorical promotion pathway determining reality mutation behavior."""

    DIRECT_CANONICAL = "DIRECT_CANONICAL"          # Grounded low/med-impact fact immediately promoted
    CANDIDATE_ACCUMULATION = "CANDIDATE_ACCUMULATION"# Needs further evidence before promotion
    MANUAL_USER_GATED = "MANUAL_USER_GATED"        # High/Very-High impact fact requires user confirmation
    REJECT = "REJECT"                              # Inadmissible, contradicted, or speculative fact


class PromotionDecision(BaseModel):
    """Immutable domain representation of a reality promotion evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fact_key: str = Field(..., description="Dot-notated fact key, e.g. 'preferences.study_beverage'.")
    value: Any = Field(..., description="Proposed domain value to be recorded if promoted.")
    promotion_type: PromotionType = Field(..., description="Promotion classification.")
    promotion_score: float = Field(default=1.0, description="Computed promotion confidence score [0.0, 1.0].")
    validators_passed: tuple[str, ...] = Field(default_factory=tuple, description="Names of passed validators.")
    authority: FactAuthority = Field(default=FactAuthority.AEVUM_CANONICAL, description="Assigned authority level.")
    status: FactStatus = Field(default=FactStatus.CANONICAL, description="Lifecycle status assigned.")
    rationale: str = Field(..., description="Audit rationale explaining the promotion decision.")
    created_at: datetime = Field(default_factory=_utc_now, description="UTC decision timestamp.")

    @field_validator("promotion_score", mode="before")
    @classmethod
    def validate_score(cls, v: Any, info: Any) -> float:
        return _validate_normalized_float(float(v), info.field_name)

    @field_validator("fact_key", "rationale")
    @classmethod
    def validate_non_empty(cls, v: str, info: Any) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"{info.field_name} must not be empty or whitespace.")
        return v.strip()
