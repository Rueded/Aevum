from pydantic import BaseModel, ConfigDict, Field
from typing import Optional

class CharacterLifeContext(BaseModel):
    """Immutable semantic context for Character Engine representing Aevum's life state."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    current_activity_summary: Optional[str] = Field(
        default=None,
        description="Concise summary of what Aevum is currently doing."
    )
    current_location_summary: str = Field(
        ...,
        description="Concise summary of where Aevum currently is."
    )
    recent_experience_summary: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Factual descriptions of recent LifeEvents."
    )
    life_guidance: tuple[str, ...] = Field(
        ...,
        description="Behavioral guidance generated from the current life state."
    )
