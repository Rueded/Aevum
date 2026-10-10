"""Relationship domain models for Aevum Core.

Defines provider-independent, immutable models representing how Aevum currently relates
to the user across orthogonal, normalized dimensions.

Guarantees:
- Multidimensional: Independent axes (familiarity, trust, comfort, affection, attachment, respect).
- No single relationship score or "relationship level".
- No boolean romance flags (is_girlfriend, is_romantic, is_partner) or hardcoded affection.
- No jealousy score.
- Strictly decoupled from CharacterState (who/how she is), Emotion (momentary feelings),
  and Memory (historical facts).
"""

from datetime import datetime
import math
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DEFAULT_RELATIONSHIP_ID: str = "user"
DEFAULT_USER_ID: str = "user"

# Deterministic bootstrap baseline values for initial relationship state.
# Represents newly acquainted individuals / strangers.
# Affection and attachment start strictly at 0.0 (no initial romantic bias).
# Respect starts at a healthy baseline (0.50).
BOOTSTRAP_FAMILIARITY: float = 0.05
BOOTSTRAP_TRUST: float = 0.20
BOOTSTRAP_COMFORT: float = 0.10
BOOTSTRAP_AFFECTION: float = 0.00
BOOTSTRAP_ATTACHMENT: float = 0.00
BOOTSTRAP_RESPECT: float = 0.50


def _validate_normalized_float(v: float, field_name: str) -> float:
    """Ensure float is a finite normalized number between 0.0 and 1.0 inclusive."""
    if math.isnan(v):
        raise ValueError(f"{field_name} must not be NaN.")
    if math.isinf(v):
        raise ValueError(f"{field_name} must not be infinite.")
    if v < 0.0 or v > 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0 inclusive.")
    return float(v)


class RelationshipState(BaseModel):
    """Immutable aggregate representing current multidimensional relationship state.

    Distinctions:
    - CharacterDefinition = WHO Aevum is (stable identity, traits, boundaries).
    - CharacterState = HOW Aevum currently is (mood, energy, activity, location).
    - Emotion = HOW Aevum feels right now (transient affect, reaction).
    - Memory = WHAT Aevum remembers happened / learned.
    - RelationshipState = HOW Aevum currently relates to the user across independent dimensions.

    Each metric is normalized [0.0, 1.0] and represents an independent relational axis.
    They are never collapsed into a single composite score or romantic stage enum.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(
        default=DEFAULT_RELATIONSHIP_ID,
        description="Stable deterministic identifier for the relationship record.",
    )
    user_id: str = Field(
        default=DEFAULT_USER_ID,
        description="Identifier of the user in this relationship (single-user architecture).",
    )
    version: int = Field(
        default=1,
        ge=1,
        description="Monotonically increasing version counter for optimistic concurrency.",
    )
    created_at: datetime = Field(
        description="Immutable UTC timestamp when the relationship was established.",
    )
    updated_at: datetime = Field(
        description="UTC timestamp of the most recent relationship state update.",
    )

    # Multidimensional relational axes (0.0 - 1.0)
    familiarity: float = Field(
        default=BOOTSTRAP_FAMILIARITY,
        description="Depth and breadth of mutual knowledge and shared history (0.0 = total stranger, 1.0 = deeply known).",
    )
    trust: float = Field(
        default=BOOTSTRAP_TRUST,
        description="Belief in user reliability, honesty, and safety in vulnerability (0.0 = zero trust, 1.0 = absolute trust).",
    )
    comfort: float = Field(
        default=BOOTSTRAP_COMFORT,
        description="Ease and lack of tension or wariness in presence of the user (0.0 = tense/guarded, 1.0 = completely at ease).",
    )
    affection: float = Field(
        default=BOOTSTRAP_AFFECTION,
        description="Emotional warmth and fondness developed through interaction (0.0 = neutral/none, 1.0 = deep fond affection).",
    )
    attachment: float = Field(
        default=BOOTSTRAP_ATTACHMENT,
        description="Relational bondedness and emotional reliance (0.0 = independent/unbonded, 1.0 = deeply bonded).",
    )
    respect: float = Field(
        default=BOOTSTRAP_RESPECT,
        description="Esteem for the user's boundaries, integrity, and competence (0.0 = no respect, 1.0 = profound respect).",
    )

    @field_validator("familiarity", "trust", "comfort", "affection", "attachment", "respect")
    @classmethod
    def validate_metrics(cls, v: float, info: Any) -> float:
        return _validate_normalized_float(v, info.field_name)


class RelationshipStateUpdate(BaseModel):
    """Immutable, validated partial replacement request for RelationshipState.

    Used by trusted internal application subsystems (e.g. future Relationship/Event engines).
    Updates represent explicit target values, NOT delta additions.
    Empty mutation requests with zero specified fields are rejected.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    familiarity: float | None = None
    trust: float | None = None
    comfort: float | None = None
    affection: float | None = None
    attachment: float | None = None
    respect: float | None = None

    @field_validator("familiarity", "trust", "comfort", "affection", "attachment", "respect")
    @classmethod
    def validate_optional_metrics(cls, v: float | None, info: Any) -> float | None:
        if v is not None:
            return _validate_normalized_float(v, info.field_name)
        return None

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "RelationshipStateUpdate":
        has_any_field = any(
            getattr(self, field_name) is not None
            for field_name in [
                "familiarity",
                "trust",
                "comfort",
                "affection",
                "attachment",
                "respect",
            ]
        )
        if not has_any_field:
            raise ValueError("RelationshipStateUpdate must contain at least one field to update.")
        return self


# =============================================================================
# Phase 4.2: Relationship Interaction Signal Models
# =============================================================================

import enum
import uuid
from app.db.models import utc_now
from app.memory.curation_policy import contains_obvious_credentials

MAX_REASON_LENGTH: int = 300
MAX_RELATIONSHIP_SIGNALS_PER_INTERACTION: int = 3


class RelationshipSignalType(str, enum.Enum):
    """Categorical types of meaningful relational interactions observed in dialogue."""

    APPRECIATION = "APPRECIATION"
    SHARED_INTEREST = "SHARED_INTEREST"
    PERSONAL_DISCLOSURE = "PERSONAL_DISCLOSURE"
    SUPPORT_RECEIVED = "SUPPORT_RECEIVED"
    SUPPORT_GIVEN = "SUPPORT_GIVEN"
    RESPECT_BOUNDARY = "RESPECT_BOUNDARY"
    BOUNDARY_VIOLATION = "BOUNDARY_VIOLATION"
    DISAGREEMENT = "DISAGREEMENT"
    REPAIR_ATTEMPT = "REPAIR_ATTEMPT"
    PLAYFUL_CONNECTION = "PLAYFUL_CONNECTION"
    RELIABILITY = "RELIABILITY"


class RelationshipSignalSource(str, enum.Enum):
    """Origin source of a relationship signal proposal."""

    SYSTEM = "SYSTEM"
    LLM = "LLM"
    MANUAL = "MANUAL"


def _validate_proposal_reason(v: str | None) -> str | None:
    """Validate proposal explanation reason length without raising on credential detection."""
    if v is None:
        return None
    stripped = v.strip()
    if not stripped:
        return None
    if len(stripped) > MAX_REASON_LENGTH:
        raise ValueError(f"Signal reason exceeds maximum length of {MAX_REASON_LENGTH} characters.")
    return stripped


def _validate_signal_reason(v: str | None) -> str | None:
    """Validate and sanitize signal explanation reason."""
    if v is None:
        return None
    stripped = v.strip()
    if not stripped:
        return None
    if len(stripped) > MAX_REASON_LENGTH:
        raise ValueError(f"Signal reason exceeds maximum length of {MAX_REASON_LENGTH} characters.")
    if contains_obvious_credentials(stripped):
        raise ValueError("Signal reason contains prohibited credential or secret patterns.")
    return stripped


class RelationshipSignalProposal(BaseModel):
    """Untrusted signal proposal emitted by LLM extraction before policy application."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    signal_type: RelationshipSignalType = Field(
        ...,
        description="Type of observed interaction signal.",
    )
    confidence: float = Field(
        ...,
        description="Certainty that the signal actually occurred (0.0 to 1.0).",
    )
    strength: float = Field(
        ...,
        description="Meaningfulness/intensity of the interaction if it occurred (0.0 to 1.0).",
    )
    reason: str | None = Field(
        default=None,
        description="Concise description of the observed behavior (max 300 chars, no secrets).",
    )

    @field_validator("confidence", "strength")
    @classmethod
    def validate_proposal_metrics(cls, v: float, info: Any) -> float:
        return _validate_normalized_float(v, info.field_name)

    @field_validator("reason")
    @classmethod
    def validate_proposal_reason(cls, v: str | None) -> str | None:
        return _validate_proposal_reason(v)


class RelationshipSignalPayload(BaseModel):
    """Schema for structured LLM response during signal extraction."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    signals: list[RelationshipSignalProposal] = Field(
        default_factory=list,
        description="List of proposed interaction signals observed in the conversation.",
    )


class RelationshipSignal(BaseModel):
    """Immutable aggregate representing a validated interaction observation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier of the signal instance.",
    )
    signal_type: RelationshipSignalType = Field(
        ...,
        description="Categorical type of interaction signal.",
    )
    source: RelationshipSignalSource = Field(
        default=RelationshipSignalSource.LLM,
        description="Source of the signal proposal.",
    )
    confidence: float = Field(
        ...,
        description="Confidence that the signal exists (0.0 to 1.0).",
    )
    strength: float = Field(
        ...,
        description="Meaningfulness/magnitude of the signal (0.0 to 1.0).",
    )
    reason: str | None = Field(
        default=None,
        description="Optional brief explanation of the observation.",
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        description="UTC timestamp when the signal was formed.",
    )

    @field_validator("confidence", "strength")
    @classmethod
    def validate_signal_metrics(cls, v: float, info: Any) -> float:
        return _validate_normalized_float(v, info.field_name)

    @field_validator("reason")
    @classmethod
    def validate_signal_reason(cls, v: str | None) -> str | None:
        return _validate_signal_reason(v)


class RelationshipSignalExtractionResult(BaseModel):
    """Immutable result of an interaction signal extraction attempt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    signals: tuple[RelationshipSignal, ...] = Field(
        default=(),
        description="Extracted, validated, and filtered relationship signals.",
    )
    is_success: bool = Field(
        default=True,
        description="Whether the extraction process completed without unhandled failure.",
    )
    error_message: str | None = Field(
        default=None,
        description="Error details if extraction failed.",
    )

