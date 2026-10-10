"""retrieval_models.py — Phase 12.3 Autobiographical Retrieval & Context Assembly Contracts.

Governed by ADR-023:
1. Pure Immutable DTOs: Frozen Pydantic models with extra="forbid".
2. Epistemic Decoupling: Zero float confidence/probabilities. Scores are integer rankings.
3. Lock 1 & Lock C: Pure read and assembly contracts; zero mutation authority.
4. Lock 2 & Lock D: Causal UNKNOWN state is a first-class domain representation.
5. Lock 4 & Lock F: HistoryScope segregation (AEVUM_PERSONAL default).
6. Lock 5: Directives for character-authentic humble boundary expressions without canned scripts.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from app.biography.biography_models import (
    BiographicalDomain,
    BiographicalFact,
    CanonicalStatus,
    CausalKnowledgeState,
    HistoryScope,
    LifeEra,
    LifeEventRecord,
    PersonalPreference,
    QualiaAnchor,
    RecallLevel,
    SocialContactRecord,
)
from app.biography.causal_graph import CausalExplanationPath


class BiographicalIntentType(str, Enum):
    """Classifies the primary autobiographical intent of an inquiry."""

    LIFE_EVENT = "LIFE_EVENT"
    PERSONAL_PREFERENCE = "PERSONAL_PREFERENCE"
    CAUSAL_ORIGIN = "CAUSAL_ORIGIN"
    GROWTH_ERA = "GROWTH_ERA"
    SOCIAL_TIE = "SOCIAL_TIE"
    GENERAL_AUTOBIOGRAPHY = "GENERAL_AUTOBIOGRAPHY"


AutobiographicalIntentType = BiographicalIntentType


class AutobiographicalQuery(BaseModel):
    """Defines an autobiographical retrieval inquiry with scoped filters."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    raw_query: str = Field(..., min_length=1, description="Raw query string from user or internal prompt")
    intent: BiographicalIntentType = Field(
        default=BiographicalIntentType.GENERAL_AUTOBIOGRAPHY,
        description="Classified autobiographical intent",
    )
    target_domain: Optional[BiographicalDomain] = Field(
        default=None,
        description="Optional targeted biographical domain filter",
    )
    target_era: Optional[LifeEra] = Field(
        default=None,
        description="Optional targeted life era filter",
    )
    scope: HistoryScope = Field(
        default=HistoryScope.AEVUM_PERSONAL,
        description="History scope boundary (AEVUM_PERSONAL vs SHARED_WITH_USER, Lock F)",
    )
    keywords: tuple[str, ...] = Field(
        default=(),
        description="Normalized keyword tokens extracted from query",
    )
    target_entity_id: Optional[str] = Field(
        default=None,
        description="Target item identifier if querying a known fact, event, or preference",
    )


class ScoredBiographicalCandidate(BaseModel):
    """A scored candidate item for autobiographical context selection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    item_type: str = Field(..., description="Type of candidate: FACT, EVENT, PREFERENCE, CAUSAL_PATH, QUALIA, CONTACT")
    item_id: str = Field(..., description="Unique ID of the candidate item")
    relevance_score: int = Field(..., ge=0, le=100, description="Deterministic integer relevance score (0-100)")
    canonical_status: CanonicalStatus = Field(..., description="Canonical status of the item")
    recall_level: RecallLevel = Field(..., description="Phenomenological recall level")
    match_reasons: tuple[str, ...] = Field(default=(), description="Explanations for why candidate matched")
    era: Optional[LifeEra] = Field(default=None, description="Associated life era if applicable")
    domain: Optional[BiographicalDomain] = Field(default=None, description="Associated domain if applicable")


class AutobiographicalRetrievalResult(BaseModel):
    """The aggregate deterministic result of autobiographical retrieval."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query: AutobiographicalQuery = Field(..., description="Original query specifications")
    matched_facts: tuple[BiographicalFact, ...] = Field(default=(), description="Selected canonical facts")
    matched_events: tuple[LifeEventRecord, ...] = Field(default=(), description="Selected life events")
    matched_preferences: tuple[PersonalPreference, ...] = Field(default=(), description="Selected personal preferences")
    causal_paths: tuple[CausalExplanationPath, ...] = Field(default=(), description="Derived causal explanation paths")
    matched_qualia: tuple[QualiaAnchor, ...] = Field(default=(), description="Associated qualia sensory anchors")
    matched_contacts: tuple[SocialContactRecord, ...] = Field(default=(), description="Relevant social contacts")
    has_unknown_causal_boundary: bool = Field(
        default=False,
        description="Flag indicating that an queried preference or event has an explicit UNKNOWN causal state (Lock D)",
    )
    is_empty: bool = Field(
        default=False,
        description="Flag indicating no relevant biographical material was found (triggers Lock 5 boundary grace)",
    )


class AssembledBiographicalContext(BaseModel):
    """The structured serialized biographical context ready for prompt injection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    context_text: str = Field(..., description="Serialized XML <biographical_context> block")
    context_hash: str = Field(..., description="SHA-256 hash of context_text for determinism and audit")
    retrieval_summary: dict[str, int] = Field(
        default_factory=dict,
        description="Counts of included facts, events, preferences, causal paths, qualia, and contacts",
    )
    epistemic_directives: tuple[str, ...] = Field(
        default=(),
        description="Active Lock 5 and Lock D epistemic guidance directives",
    )
