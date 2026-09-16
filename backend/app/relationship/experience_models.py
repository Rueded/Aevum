"""Relationship experience and history models for Aevum Core.

Represents discrete historical relationship-relevant events and interpretations.
Distinguishes 'what an interaction meant for the relationship' from current numerical state
and episodic memory.

Guarantees:
- Zero raw relationship score/metric fields (trust, affection, comfort, etc.).
- Immutable, bounded representation (frozen=True, extra="forbid").
- Bounded summary text (max 500 chars, no credentials/secrets).
- Deterministic signal-to-experience mapping.
"""

from datetime import datetime, timezone
from enum import Enum
import math
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.memory.curation_policy import contains_obvious_credentials
from app.relationship.models import (
    DEFAULT_RELATIONSHIP_ID,
    RelationshipSignal,
    RelationshipSignalSource,
    RelationshipSignalType,
)

MAX_EXPERIENCE_SUMMARY_LENGTH: int = 500


def utc_now() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def _validate_normalized_float(v: float, field_name: str) -> float:
    """Validate that a float metric is finite and in [0.0, 1.0]."""
    if not isinstance(v, (int, float)):
        raise ValueError(f"{field_name} must be a numeric value, got {type(v).__name__}.")
    if math.isnan(v) or math.isinf(v):
        raise ValueError(f"{field_name} cannot be NaN or Infinite.")
    if v < 0.0 or v > 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0 inclusive (got {v}).")
    return float(v)


class RelationshipExperienceType(str, Enum):
    """Controlled vocabulary of discrete relationship-relevant interaction experience types."""

    BOUNDARY_RESPECTED = "BOUNDARY_RESPECTED"
    BOUNDARY_VIOLATED = "BOUNDARY_VIOLATED"
    PERSONAL_DISCLOSURE = "PERSONAL_DISCLOSURE"
    SUPPORT_RECEIVED = "SUPPORT_RECEIVED"
    SUPPORT_GIVEN = "SUPPORT_GIVEN"
    DISAGREEMENT = "DISAGREEMENT"
    REPAIR_ATTEMPT = "REPAIR_ATTEMPT"
    RELIABILITY_SHOWN = "RELIABILITY_SHOWN"
    SHARED_INTEREST = "SHARED_INTEREST"
    PLAYFUL_CONNECTION = "PLAYFUL_CONNECTION"
    APPRECIATION = "APPRECIATION"


class RelationshipExperienceSource(str, Enum):
    """Source that initiated or observed the relationship experience."""

    SYSTEM = "SYSTEM"
    LLM = "LLM"
    MANUAL = "MANUAL"


def _validate_summary_text(v: str) -> str:
    """Sanitize and validate experience summary text."""
    stripped = v.strip()
    if not stripped:
        raise ValueError("Experience summary must not be empty or whitespace-only.")
    if len(stripped) > MAX_EXPERIENCE_SUMMARY_LENGTH:
        raise ValueError(
            f"Experience summary exceeds maximum length of {MAX_EXPERIENCE_SUMMARY_LENGTH} characters."
        )
    if contains_obvious_credentials(stripped):
        raise ValueError("Experience summary contains prohibited credential or secret patterns.")
    return stripped


class RelationshipExperienceCreate(BaseModel):
    """Input payload to record a new relationship experience."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    relationship_id: str = Field(
        default=DEFAULT_RELATIONSHIP_ID,
        description="Target relationship identifier.",
    )
    experience_type: RelationshipExperienceType = Field(
        ...,
        description="Categorical type of relational experience.",
    )
    source: RelationshipExperienceSource = Field(
        default=RelationshipExperienceSource.SYSTEM,
        description="Originator of the experience observation.",
    )
    summary: str = Field(
        ...,
        description="Concise description of the relational event (max 500 chars, no secrets).",
    )
    significance: float = Field(
        ...,
        description="Significance or weight of the event as a historical milestone (0.0 to 1.0).",
    )
    confidence: float = Field(
        ...,
        description="Certainty that the event occurred as described (0.0 to 1.0).",
    )

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, v: str) -> str:
        return _validate_summary_text(v)

    @field_validator("significance", "confidence")
    @classmethod
    def validate_metrics(cls, v: float, info: Any) -> float:
        return _validate_normalized_float(v, info.field_name)


class RelationshipExperience(BaseModel):
    """Immutable domain aggregate representing a persistent relationship experience record."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for the experience instance.",
    )
    relationship_id: str = Field(
        default=DEFAULT_RELATIONSHIP_ID,
        description="Target relationship identifier.",
    )
    experience_type: RelationshipExperienceType = Field(
        ...,
        description="Categorical type of relational experience.",
    )
    source: RelationshipExperienceSource = Field(
        default=RelationshipExperienceSource.SYSTEM,
        description="Originator of the experience observation.",
    )
    summary: str = Field(
        ...,
        description="Concise description of the relational event (max 500 chars).",
    )
    significance: float = Field(
        ...,
        description="Historical significance of the event (0.0 to 1.0).",
    )
    confidence: float = Field(
        ...,
        description="Confidence that the event occurred (0.0 to 1.0).",
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        description="UTC timestamp when the experience occurred.",
    )

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, v: str) -> str:
        return _validate_summary_text(v)

    @field_validator("significance", "confidence")
    @classmethod
    def validate_metrics(cls, v: float, info: Any) -> float:
        return _validate_normalized_float(v, info.field_name)


# Deterministic mapping between signal vocabulary and experience vocabulary
SIGNAL_TO_EXPERIENCE_TYPE_MAP: dict[RelationshipSignalType, RelationshipExperienceType] = {
    RelationshipSignalType.APPRECIATION: RelationshipExperienceType.APPRECIATION,
    RelationshipSignalType.SHARED_INTEREST: RelationshipExperienceType.SHARED_INTEREST,
    RelationshipSignalType.PERSONAL_DISCLOSURE: RelationshipExperienceType.PERSONAL_DISCLOSURE,
    RelationshipSignalType.SUPPORT_RECEIVED: RelationshipExperienceType.SUPPORT_RECEIVED,
    RelationshipSignalType.SUPPORT_GIVEN: RelationshipExperienceType.SUPPORT_GIVEN,
    RelationshipSignalType.RESPECT_BOUNDARY: RelationshipExperienceType.BOUNDARY_RESPECTED,
    RelationshipSignalType.BOUNDARY_VIOLATION: RelationshipExperienceType.BOUNDARY_VIOLATED,
    RelationshipSignalType.DISAGREEMENT: RelationshipExperienceType.DISAGREEMENT,
    RelationshipSignalType.REPAIR_ATTEMPT: RelationshipExperienceType.REPAIR_ATTEMPT,
    RelationshipSignalType.PLAYFUL_CONNECTION: RelationshipExperienceType.PLAYFUL_CONNECTION,
    RelationshipSignalType.RELIABILITY: RelationshipExperienceType.RELIABILITY_SHOWN,
}

# Safe deterministic fallback summaries when signal explanation reason is absent
DEFAULT_EXPERIENCE_SUMMARIES: dict[RelationshipExperienceType, str] = {
    RelationshipExperienceType.BOUNDARY_RESPECTED: "A relationship-relevant boundary was respected.",
    RelationshipExperienceType.BOUNDARY_VIOLATED: "A relationship boundary was violated.",
    RelationshipExperienceType.PERSONAL_DISCLOSURE: "A personal experience or perspective was shared.",
    RelationshipExperienceType.SUPPORT_RECEIVED: "Emotional or practical support was received.",
    RelationshipExperienceType.SUPPORT_GIVEN: "Emotional support or care was offered.",
    RelationshipExperienceType.DISAGREEMENT: "A respectful disagreement occurred.",
    RelationshipExperienceType.REPAIR_ATTEMPT: "An attempt was made to repair conversational friction.",
    RelationshipExperienceType.RELIABILITY_SHOWN: "Reliability and follow-through were demonstrated.",
    RelationshipExperienceType.SHARED_INTEREST: "A shared interest or mutual enthusiasm was explored.",
    RelationshipExperienceType.PLAYFUL_CONNECTION: "A moment of playful banter or humor was shared.",
    RelationshipExperienceType.APPRECIATION: "Appreciation and gratitude were expressed.",
}


def map_signal_to_experience_create(
    signal: RelationshipSignal,
    relationship_id: str = DEFAULT_RELATIONSHIP_ID,
) -> RelationshipExperienceCreate:
    """Deterministically map a validated RelationshipSignal to a RelationshipExperienceCreate model."""
    exp_type = SIGNAL_TO_EXPERIENCE_TYPE_MAP[signal.signal_type]

    # Map source
    if signal.source == RelationshipSignalSource.LLM:
        exp_source = RelationshipExperienceSource.LLM
    elif signal.source == RelationshipSignalSource.MANUAL:
        exp_source = RelationshipExperienceSource.MANUAL
    else:
        exp_source = RelationshipExperienceSource.SYSTEM

    # Summary: use sanitized reason if present, else deterministic fallback
    if signal.reason and signal.reason.strip():
        summary = signal.reason.strip()
        if len(summary) > MAX_EXPERIENCE_SUMMARY_LENGTH:
            summary = summary[: MAX_EXPERIENCE_SUMMARY_LENGTH - 3] + "..."
    else:
        summary = DEFAULT_EXPERIENCE_SUMMARIES[exp_type]

    return RelationshipExperienceCreate(
        relationship_id=relationship_id,
        experience_type=exp_type,
        source=exp_source,
        summary=summary,
        significance=signal.strength,
        confidence=signal.confidence,
    )
