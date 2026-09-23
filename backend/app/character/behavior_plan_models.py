"""Behavior plan and decision trace domain models (Phase 7B.2).

Defines:
- BehaviorPlan: Concrete behavioral constraints (micro-actions, negative constraints/forbidden patterns, target warmth/directness).
- BehaviorDecisionTrace: Structured explainable audit trace of how internal state synthesized into action.
"""

import math
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.character.intention_models import BehaviorPrimitive, SocialPosture


def _validate_normalized_float(v: float, field_name: str) -> float:
    """Ensure float is finite and within [0.0, 1.0]."""
    if math.isnan(v):
        raise ValueError(f"{field_name} must not be NaN.")
    if math.isinf(v):
        raise ValueError(f"{field_name} must not be infinite.")
    if v < 0.0 or v > 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0 inclusive.")
    return float(v)


class BehaviorPlan(BaseModel):
    """Authoritative behavioral plan passed to LLM generation context."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    primary_move: BehaviorPrimitive = Field(
        ...,
        description="Target universal behavioral primitive.",
    )
    posture: SocialPosture = Field(
        ...,
        description="Target affective/social posture.",
    )
    target_warmth: float = Field(
        ...,
        description="Target social warmth on [0.0, 1.0].",
    )
    target_directness: float = Field(
        ...,
        description="Target communicative directness on [0.0, 1.0].",
    )
    allowed_micro_actions: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Specific behavioral gestures or communicative micro-moves permitted/encouraged.",
    )
    forbidden_patterns: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Speech patterns, rhetorical tropes, or behaviors strictly prohibited.",
    )
    conversation_hook: Optional[str] = Field(
        default=None,
        description="Specific communicative intent directive or conversational opening.",
    )

    @field_validator("target_warmth", "target_directness", mode="before")
    @classmethod
    def validate_normalized_fields(cls, v: Any, info: Any) -> float:
        return _validate_normalized_float(float(v), info.field_name)


class BehaviorDecisionTrace(BaseModel):
    """Structured diagnostic trace of internal psychological and relational decision making."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    stimulus_summary: str = Field(
        ...,
        description="Summary of the user input or situational stimulus.",
    )
    desire_focus: Optional[str] = Field(
        default=None,
        description="Active solitary or psychological focus.",
    )
    social_need: float = Field(
        ...,
        description="Current social need level [0.0, 1.0].",
    )
    solitude_need: float = Field(
        ...,
        description="Current solitude need level [0.0, 1.0].",
    )
    intimacy_tier: str = Field(
        ...,
        description="Active intimacy tier name.",
    )
    compromise_capacity: float = Field(
        ...,
        description="Relationship contract compromise capacity [0.0, 1.0].",
    )
    hard_boundary_checked: bool = Field(
        default=True,
        description="Whether hard boundary invariant checks were executed.",
    )
    hard_boundary_triggered: bool = Field(
        default=False,
        description="Whether a hard boundary invariant was triggered.",
    )
    primary_move: str = Field(
        ...,
        description="Selected behavior primitive string.",
    )
    posture: str = Field(
        ...,
        description="Selected social posture string.",
    )
    compromise_level: float = Field(
        ...,
        description="Synthesized compromise level [0.0, 1.0].",
    )
    rationale: str = Field(
        ...,
        description="Explainable summary of why this behavioral decision was made.",
    )
