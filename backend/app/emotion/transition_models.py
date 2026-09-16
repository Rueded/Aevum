"""Emotion transition models for Aevum Core.

Represents an immutable, side-effect free proposal for an emotional state transition:
"Application state owns reality.
 Emotion evaluation proposes a possible next state.
 Persistence/application happens in a later phase."

Guarantees:
- Single dominant emotion: Operates strictly within Aevum's single-dominant-emotion architecture.
- Proposal only: Does NOT mutate EmotionState, CharacterState, or RelationshipState.
- Fully validated: Intensities strictly in [0.0, 1.0], no NaN/inf, bounded clean reason.
- Immutable domain model (frozen=True, extra="forbid").
- Traceable: Preserves IDs of all influences considered during evaluation.
"""

import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.emotion.emotion_models import EmotionType
from app.memory.curation_policy import contains_obvious_credentials

MAX_TRANSITION_REASON_LENGTH: int = 500


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


def _validate_reason_text(v: str) -> str:
    """Sanitize and validate transition proposal reason text."""
    if not isinstance(v, str):
        raise ValueError("reason must be a string.")
    stripped = v.strip()
    if not stripped:
        raise ValueError("reason must not be empty or whitespace.")
    if len(stripped) > MAX_TRANSITION_REASON_LENGTH:
        raise ValueError(
            f"reason length ({len(stripped)}) exceeds maximum allowed ({MAX_TRANSITION_REASON_LENGTH})."
        )
    if contains_obvious_credentials(stripped):
        raise ValueError("reason contains prohibited credential or secret patterns.")
    return stripped


class EmotionTransitionProposal(BaseModel):
    """Immutable domain representation of a proposed next emotional state.

    This proposal is an evaluation artifact, NOT authoritative state. It does not
    modify EmotionState, CharacterState, or RelationshipState.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    current_emotion: EmotionType = Field(
        ...,
        description="Current dominant emotion prior to evaluation.",
    )
    current_intensity: float = Field(
        ...,
        description="Current emotional intensity in [0.0, 1.0].",
    )
    proposed_emotion: EmotionType = Field(
        ...,
        description="Proposed dominant emotion for the next state.",
    )
    proposed_intensity: float = Field(
        ...,
        description="Proposed emotional intensity in [0.0, 1.0].",
    )
    considered_influence_ids: list[str] = Field(
        default_factory=list,
        description="List of influence IDs examined during transition evaluation in deterministic order.",
    )
    reason: str = Field(
        ...,
        description="Concise deterministic explanation of the transition proposal.",
    )

    @field_validator("current_intensity", "proposed_intensity")
    @classmethod
    def validate_intensities(cls, v: float, info: Any) -> float:
        return _validate_intensity(v, info.field_name)

    @field_validator("considered_influence_ids")
    @classmethod
    def validate_considered_ids(cls, v: list[str]) -> list[str]:
        if not isinstance(v, (list, tuple)):
            raise ValueError("considered_influence_ids must be a list of string IDs.")
        cleaned: list[str] = []
        for item in v:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("considered_influence_ids contains invalid empty or non-string ID.")
            cleaned.append(item.strip())
        return cleaned

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        return _validate_reason_text(v)
