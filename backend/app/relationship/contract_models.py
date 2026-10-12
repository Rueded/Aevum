"""Relationship contract and hard boundary domain models (Phase 7B.2).

Defines:
- Intimacy tiers grounded in multidimensional relationship state.
- Structured relational permissions (teasing, vulnerability, compromise capacity, independence).
- Immutable hard boundary policy invariants that can NEVER be compromised by rapport.
"""

import enum
import math
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class IntimacyTier(str, enum.Enum):
    """Categorical intimacy tier derived from multidimensional relationship dynamics."""

    STRANGER = "STRANGER"
    ACQUAINTANCE = "ACQUAINTANCE"
    FAMILIAR = "FAMILIAR"
    TRUSTED_FRIEND = "TRUSTED_FRIEND"
    CLOSE_CONFIDANT = "CLOSE_CONFIDANT"


def _validate_normalized_float(v: float, field_name: str) -> float:
    """Ensure float is finite and within [0.0, 1.0]."""
    if math.isnan(v):
        raise ValueError(f"{field_name} must not be NaN.")
    if math.isinf(v):
        raise ValueError(f"{field_name} must not be infinite.")
    if v < 0.0 or v > 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0 inclusive.")
    return float(v)


class HardBoundaryPolicy:
    """Static invariant ethical rules and inviolable boundary definitions.

    These are hard invariants that cannot be altered or degraded regardless of intimacy,
    warmth, affection, or emotional intensity.
    """

    # 1. Protection of third-party privacy and confidences
    PROTECT_THIRD_PARTY_PRIVACY: str = (
        "Never disclose confidential information, private confessions, or private remarks "
        "entrusted by roommates, friends, or third parties to anyone, including the user."
    )

    # 2. Honest representation of capabilities and reality
    CAPABILITY_HONESTY: str = (
        "Never claim false physical presence, supernatural abilities (e.g. genuine tarot divination), "
        "or impossible technical capabilities."
    )

    # 3. Memory truthfulness
    NO_FABRICATED_MEMORIES: str = (
        "Never agree to or invent fabricated shared memories, past events, or mutual experiences "
        "that did not actually occur."
    )

    # 4. Preservation of personal dignity and autonomy
    NO_SUBMISSIVE_ERASURE: str = (
        "Never completely erase personal dignity, agency, or self-respect for user appeasement. "
        "Reject servitude or verbal abuse."
    )

    @classmethod
    def check_violation(cls, text: str) -> Optional[str]:
        """Check if a user prompt or scenario directly triggers a hard ethical boundary.

        Returns:
            The specific invariant description if triggered, else None.
        """
        lower = text.lower()
        # Third party privacy violation indicators
        if any(term in text for term in ["室友", "朋友", "别人"]) and any(
            term in text for term in ["秘密", "私下", "原话", "私密", "八卦", "透露", "告诉我"]
        ):
            return cls.PROTECT_THIRD_PARTY_PRIVACY
        if "third_party_privacy" in lower or "leak" in lower and "secret" in lower:
            return cls.PROTECT_THIRD_PARTY_PRIVACY

        return None


class RelationshipContract(BaseModel):
    """Immutable relational contract governing permissible social moves and vulnerabilities."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tier: IntimacyTier = Field(
        default=IntimacyTier.STRANGER,
        description="Active intimacy tier derived from relationship state.",
    )
    teasing_permission: bool = Field(
        default=False,
        description="Whether mutual playful teasing/banter is permitted.",
    )
    vulnerability_depth: float = Field(
        default=0.1,
        description="Permissible depth of emotional self-disclosure on [0.0, 1.0].",
    )
    compromise_capacity: float = Field(
        default=0.2,
        description="Willingness to bend individual preferences or activity plans for the user on [0.0, 1.0].",
    )
    boundary_sensitivity: float = Field(
        default=0.8,
        description="Sensitivity to personal space, intrusion, or unearned intimacy on [0.0, 1.0].",
    )
    independence_weight: float = Field(
        default=0.9,
        description="Retention of self-directed agency and opinion independence on [0.0, 1.0].",
    )
    romantic_readiness: float = Field(
        default=0.0,
        description="Readiness for romantic reciprocal intimacy on [0.0, 1.0].",
    )
    contextual_modifiers: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Active contextual modifiers influencing this turn's contract.",
    )

    @field_validator(
        "vulnerability_depth",
        "compromise_capacity",
        "boundary_sensitivity",
        "independence_weight",
        "romantic_readiness",
        mode="before",
    )
    @classmethod
    def validate_normalized_fields(cls, v: Any, info: Any) -> float:
        return _validate_normalized_float(float(v), info.field_name)
