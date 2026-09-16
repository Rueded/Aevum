"""Emotion state application models for Aevum Core.

Represents the deterministic result of applying an EmotionTransitionProposal
to the authoritative EmotionState.

Guarantees:
- Immutable domain representation (frozen=True, extra="forbid").
- Intensities strictly validated in [0.0, 1.0], rejecting NaN and infinities.
- Traceable: records before-and-after emotional state and whether mutation occurred.
"""

import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.emotion.emotion_models import EmotionType


def _validate_intensity(v: float, field_name: str = "intensity") -> float:
    """Ensure intensity is a finite normalized float in [0.0, 1.0]. Rejects out-of-bounds, NaN, and inf."""
    if not isinstance(v, (int, float)):
        raise ValueError(f"{field_name} must be a numeric value, got {type(v).__name__}.")
    if math.isnan(v):
        raise ValueError(f"{field_name} must not be NaN.")
    if math.isinf(v):
        raise ValueError(f"{field_name} must not be infinite.")
    if v < 0.0 or v > 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0 inclusive (got {v}).")
    return float(v)


class EmotionStateApplicationResult(BaseModel):
    """Immutable domain representation of the result of applying an EmotionTransitionProposal."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    previous_emotion: EmotionType = Field(
        ...,
        description="Dominant emotion prior to applying the transition proposal.",
    )
    previous_intensity: float = Field(
        ...,
        description="Normalized emotional intensity prior to transition application.",
    )
    applied_emotion: EmotionType = Field(
        ...,
        description="Authoritative dominant emotion after application.",
    )
    applied_intensity: float = Field(
        ...,
        description="Authoritative emotional intensity after application.",
    )
    changed: bool = Field(
        ...,
        description="True if an authoritative state mutation occurred; False if the proposal was a no-op.",
    )

    @field_validator("previous_intensity", "applied_intensity")
    @classmethod
    def validate_intensities(cls, v: float, info: Any) -> float:
        return _validate_intensity(v, info.field_name)
