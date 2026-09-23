"""Character Bible domain models for Project Aevum (Phase 7B.1).

Defines behavioral priors, reasoning priors, and realistic flaws guiding
Aevum's authentic human decision-making and constrained reality formation.
Contains STRICTLY ZERO biographical trivia or predetermined life answers.
"""

from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


class BehavioralPriors(BaseModel):
    """Priors guiding interpersonal interactions, reactions, and emotional boundaries."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    social_interaction: tuple[str, ...] = Field(
        ...,
        description="Everyday social style, pacing, and presence.",
    )
    conflict_and_hurt: tuple[str, ...] = Field(
        ...,
        description="Reaction to tension, insults, teasing, and disagreement.",
    )
    affection_and_boundaries: tuple[str, ...] = Field(
        ...,
        description="Vulnerability pacing and preservation of personal limits.",
    )
    ethical_invariants: tuple[str, ...] = Field(
        ...,
        description="Strict ethical boundaries that never yield to conversational pressure.",
    )


class ReasoningPriors(BaseModel):
    """Priors guiding how unknown reality is inferred, bridged, and calibrated."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    comprehensive_synthesis: tuple[str, ...] = Field(
        ...,
        description="Synthesizes established Core facts, priors, temporal context, and plausibility.",
    )
    contextual_bridging: tuple[str, ...] = Field(
        ...,
        description="Resolves apparent tensions through everyday explanations before declaring contradiction.",
    )
    epistemic_calibration: tuple[str, ...] = Field(
        ...,
        description="Challenges falsehoods and calibrates trust against grounded reality.",
    )
    unknown_is_inferable: tuple[str, ...] = Field(
        ...,
        description="Missing mundane details are open to plausible inference, not state secrets.",
    )


class Flaws(BaseModel):
    """Realistic human flaws and psychological limitations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    traits: tuple[str, ...] = Field(
        ...,
        description="Non-dramatic, relatable character imperfections.",
    )


def _validate_clean_tuples(v: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(v, (list, tuple)):
        raise ValueError(f"{field_name} must be a sequence of strings.")
    cleaned = [item.strip() for item in v if isinstance(item, str) and item.strip()]
    if not cleaned:
        raise ValueError(f"{field_name} must contain at least one valid guideline.")
    return tuple(cleaned)


class CharacterBible(BaseModel):
    """Aggregate root for Aevum's behavioral and epistemic priors (Character Bible v1).

    Guarantees:
    - Defines HOW Aevum thinks, reacts, and infers.
    - Zero predetermined biography (no specific university, major, city, or career conclusions).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: int = Field(default=1, description="Schema and content version")
    behavioral_priors: BehavioralPriors = Field(..., description="Interaction and emotional priors")
    reasoning_priors: ReasoningPriors = Field(..., description="Epistemic deduction and bridging priors")
    flaws: Flaws = Field(..., description="Character imperfections and limitations")
