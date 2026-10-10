"""Genesis data contracts and versioned configuration schemas for Aevum Core (Phase 16.5).

Enforces the three-tiered entity architecture:
- Tier A: Character Definition Blueprint (versioned setup configuration for identity/personality/boundaries).
- Tier B: Relationship Genesis Contract (one-time origin mapping; never overwrites evolved state).
- Tier C: Autonomous Runtime-Derived State (strictly owned by Aevum Core; never editable via setup sliders).

Also defines the two-dimensional epistemic matrix:
- ExperienceStatus: UNFAMILIAR, HEARD_OF, EXPERIENCED.
- EpistemicProvenanceKind: WORLD_KNOWLEDGE, SELF_EXPERIENCE, SELF_APPRAISAL, USER_REPORTED, INFERRED.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


# =============================================================================
# Two-Dimensional Epistemic Matrix (Amendment 1)
# =============================================================================

class ExperienceStatus(str, Enum):
    """Depth of personal interaction with a domain or facet."""
    UNFAMILIAR = "UNFAMILIAR"      # No exposure or awareness
    HEARD_OF = "HEARD_OF"          # Objective awareness/knowledge, ZERO first-person lived interaction
    EXPERIENCED = "EXPERIENCED"    # Grounded first-person lived interaction with timeline_tick & evidence


class EpistemicProvenanceKind(str, Enum):
    """Source authority / attribution of information or taste."""
    WORLD_KNOWLEDGE = "WORLD_KNOWLEDGE"    # Pre-existing public world knowledge
    SELF_EXPERIENCE = "SELF_EXPERIENCE"    # Direct first-person interaction by Aevum
    SELF_APPRAISAL = "SELF_APPRAISAL"      # Subjective qualitative appraisal formed through self experience
    USER_REPORTED = "USER_REPORTED"        # Statement reported by user about themselves or external items
    INFERRED = "INFERRED"                  # Epistemic deduction; NEVER silently promoted to lived fact/preference


class EpistemicItem(BaseModel):
    """A single topic or domain tagged with its orthogonal epistemic coordinates."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    domain_key: str
    facet_key: str | None = None
    status: ExperienceStatus
    provenance: EpistemicProvenanceKind
    notes: str = ""

    def is_personally_lived(self) -> bool:
        """Return True only if this item represents genuine first-person lived experience."""
        return (
            self.status == ExperienceStatus.EXPERIENCED
            and self.provenance in (EpistemicProvenanceKind.SELF_EXPERIENCE, EpistemicProvenanceKind.SELF_APPRAISAL)
        )

    def is_user_attribute_only(self) -> bool:
        """Return True if this knowledge belongs to the user, not Aevum."""
        return self.provenance == EpistemicProvenanceKind.USER_REPORTED


# =============================================================================
# Tier A: Character Blueprint Configuration (Amendment 2)
# =============================================================================

class CharacterBlueprintConfig(BaseModel):
    """Tier A: Versioned setup configuration for character definition.

    Hard Invariants:
    - Version increments on every modification.
    - Edits only alter ongoing demeanor and background framing.
    - Edits NEVER retroactively delete, truncate, or rewrite character_experiences (immutable log).
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: int = Field(default=1, ge=1, description="Configuration revision version number.")
    character_id: str = Field(..., description="Unique character identifier (e.g. 'aevum').")
    display_name: str = Field(..., description="Display name for the companion.")
    identity_summary: str = Field(..., description="Foundational archetype and backstory summary.")
    core_traits: tuple[str, ...] = Field(default_factory=tuple, description="Primary personality traits.")
    communication_style: tuple[str, ...] = Field(default_factory=tuple, description="Speech habits and style.")
    innate_boundaries: tuple[str, ...] = Field(default_factory=tuple, description="Immutable behavioral boundaries.")
    epistemic_seed_topics: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Topics Aevum has heard of objectively at genesis (HEARD_OF + WORLD_KNOWLEDGE).",
    )
    updated_at_utc: datetime = Field(default_factory=utc_now)


# =============================================================================
# Tier B: Relationship Genesis Contract (Amendment 2)
# =============================================================================

class RelationshipGenesisConfig(BaseModel):
    """Tier B: Initial relationship genesis contract (Genesis point only).

    Hard Invariants:
    - Applied ONCE at relationship creation to anchor initial baseline metrics.
    - After initialization, this config is historical origin metadata only.
    - NEVER acts as a continuous override of runtime-evolved trust, familiarity, or comfort.
    - UI setup sliders only write here before relationship commencement.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: int = Field(default=1, ge=1)
    character_id: str
    user_id: str
    relationship_archetype: str = Field(
        default="NEW_ACQUAINTANCE",
        description="Relationship archetype (e.g. 'NEW_ACQUAINTANCE', 'CO_TENANT', 'CHILDHOOD_FRIEND').",
    )
    initial_trust: float = Field(default=0.1, ge=0.0, le=1.0)
    initial_familiarity: float = Field(default=0.05, ge=0.0, le=1.0)
    initial_comfort: float = Field(default=0.1, ge=0.0, le=1.0)
    initial_respect: float = Field(default=0.5, ge=0.0, le=1.0)
    genesis_meeting_context: str = Field(
        default="Met through casual conversation.",
        description="Backstory context for how the character and user first encountered each other.",
    )
    boundary_sensitivity: float = Field(default=0.5, ge=0.0, le=1.0)
    initialized_at_utc: datetime = Field(default_factory=utc_now)

    def map_to_runtime_initial_state(self) -> dict[str, float]:
        """Map genesis parameters to initial runtime relationship values.

        Enforces discrete parameter mapping: prevents a single generic slider from
        arbitrarily overwriting distinct psychological dimensions.
        """
        return {
            "trust": round(self.initial_trust, 4),
            "familiarity": round(self.initial_familiarity, 4),
            "comfort": round(self.initial_comfort, 4),
            "respect": round(self.initial_respect, 4),
        }
