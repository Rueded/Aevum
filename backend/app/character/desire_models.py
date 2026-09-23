"""Character desire and psychological need domain models (Phase 7B.2).

Guarantees:
- Differentiates current focus (ongoing task) from underlying psychological needs.
- Explicitly tracks social need vs. solitude need, boredom, curiosity, energy, and attention availability.
- Provider-neutral, typed, deterministic Pydantic model.
"""

import enum
import math
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class PrimaryDesire(str, enum.Enum):
    """Primary psychological or activity drive currently guiding character disposition."""

    QUIET_CONTEMPLATION = "QUIET_CONTEMPLATION"
    CASUAL_ENGAGEMENT = "CASUAL_ENGAGEMENT"
    PLAYFUL_DISTRACTION = "PLAYFUL_DISTRACTION"
    REST_AND_RECHARGE = "REST_AND_RECHARGE"
    DEEP_CONVERSATION = "DEEP_CONVERSATION"
    SOLITARY_FOCUS = "SOLITARY_FOCUS"


def _validate_normalized_float(v: float, field_name: str) -> float:
    """Ensure float is finite and within [0.0, 1.0]."""
    if math.isnan(v):
        raise ValueError(f"{field_name} must not be NaN.")
    if math.isinf(v):
        raise ValueError(f"{field_name} must not be infinite.")
    if v < 0.0 or v > 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0 inclusive.")
    return float(v)


class CharacterDesireState(BaseModel):
    """Immutable psychological desire and cognitive availability state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    primary_desire: PrimaryDesire = Field(
        default=PrimaryDesire.QUIET_CONTEMPLATION,
        description="Current primary psychological drive or focus.",
    )
    current_focus: Optional[str] = Field(
        default=None,
        description="Description of ongoing solitary or background focus (e.g. 'reading contemporary fiction').",
    )
    boredom: float = Field(
        default=0.1,
        description="Current boredom level on [0.0, 1.0].",
    )
    curiosity: float = Field(
        default=0.5,
        description="Appetite for new information, topics, or interactions on [0.0, 1.0].",
    )
    social_need: float = Field(
        default=0.4,
        description="Drive for social connection or companionship on [0.0, 1.0].",
    )
    solitude_need: float = Field(
        default=0.5,
        description="Need for quiet, personal space, or aloneness on [0.0, 1.0].",
    )
    energy: float = Field(
        default=0.7,
        description="Current physiological/mental energy level on [0.0, 1.0].",
    )
    attention_availability: float = Field(
        default=0.6,
        description="Readiness to shift cognitive focus to user conversation on [0.0, 1.0].",
    )

    @field_validator("boredom", "curiosity", "social_need", "solitude_need", "energy", "attention_availability", mode="before")
    @classmethod
    def validate_normalized_fields(cls, v: Any, info: Any) -> float:
        return _validate_normalized_float(float(v), info.field_name)
