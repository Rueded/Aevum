"""Domain models for Personal World & Epistemic Grounding."""

import enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class FactEpistemicStatus(str, enum.Enum):
    """Authoritative epistemic status of personal facts."""

    ESTABLISHED = "ESTABLISHED"
    PRIVATE = "PRIVATE"
    NONEXISTENT = "NONEXISTENT"
    UNKNOWN = "UNKNOWN"
    UNVERIFIED = "UNVERIFIED"


class BiographyFact(BaseModel):
    """Immutable domain model for a biographical fact."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    character_id: str
    domain: str
    subject: str
    status: FactEpistemicStatus
    canonical_value: str
    confidence: float = 1.0
    disclosure_min_trust: float = 0.0


class SocialContact(BaseModel):
    """Immutable domain model for a member of the character's social circle."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    character_id: str
    name: str
    relationship: str
    traits: str
    status: str = "ACTIVE"
    candidate_id: Optional[str] = None
    role_template_id: Optional[str] = None
    familiarity: float = 0.05
    comfort: float = 0.10
    respect: float = 0.50
    trust: float = 0.10
    first_met_at: Optional[datetime] = None


class WorldFact(BaseModel):
    """Immutable domain model for personal world knowledge, taste, or preference."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    character_id: str
    category: str
    item: str
    details: str
    importance: float = 0.5


class EpistemicDirective(BaseModel):
    """Instruction on how the LLM must treat an epistemic topic."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    subject: str
    status: FactEpistemicStatus
    guidance: str


class PersonalWorldContext(BaseModel):
    """Immutable semantic context for personal world facts and epistemic rules."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    biography_facts: tuple[BiographyFact, ...] = Field(
        default_factory=tuple,
        description="Factual biographical facts known to the character.",
    )
    social_contacts: tuple[SocialContact, ...] = Field(
        default_factory=tuple,
        description="Members of the character's external social circle.",
    )
    world_facts: tuple[WorldFact, ...] = Field(
        default_factory=tuple,
        description="Owned personal preferences, tastes, and environmental facts.",
    )
    epistemic_directives: tuple[EpistemicDirective, ...] = Field(
        default_factory=tuple,
        description="Strict instructions on epistemic handling for specific subjects.",
    )
