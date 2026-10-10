"""shared_history_models.py — Phase 12.4 Longitudinal Shared History Contracts.

Governed by ADR-023:
1. Constitutional Axiom: "Shared History records what Aevum and the user experienced together;
   it does not rewrite what Aevum was before the relationship."
2. Lock 4 & Lock F: Strict Relational Isolation. HistoryScope.SHARED_WITH_USER is mandatory.
3. Lock 6: Segregated promotion authority. Shared history is independent of BiographyPromotionService.
4. Pure Immutable DTOs: Frozen Pydantic models with extra="forbid".
5. Rule 16 Compliance: Explicit linkage to multi-axis relationship dynamics.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import Self

from app.biography.biography_models import (
    CanonicalStatus,
    HistoryScope,
    LifeEra,
    RecallLevel,
)
from app.biography.retrieval_models import AssembledBiographicalContext


class SharedEpisodeType(str, Enum):
    """Categorizes the nature of a shared collaborative or conversational episode."""

    FIRST_ACQUAINTANCE = "FIRST_ACQUAINTANCE"
    COLLABORATIVE_TASK = "COLLABORATIVE_TASK"
    MEANINGFUL_CONVERSATION = "MEANINGFUL_CONVERSATION"
    SHARED_RITUAL = "SHARED_RITUAL"
    CONFLICT_RESOLUTION = "CONFLICT_RESOLUTION"
    MILESTONE_CELEBRATION = "MILESTONE_CELEBRATION"


class SharedHistoryEpisode(BaseModel):
    """Immutable record of an experience shared between Aevum and the User."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    episode_id: str = Field(..., description="Unique deterministic episode identifier")
    scope: HistoryScope = Field(
        default=HistoryScope.SHARED_WITH_USER,
        description="Must strictly be SHARED_WITH_USER (Lock 4)",
    )
    episode_type: SharedEpisodeType = Field(..., description="Classification of the shared episode")
    title: str = Field(..., min_length=1, description="Concise title of the shared episode")
    summary: str = Field(..., min_length=1, description="Narrative summary of the shared experience")
    session_anchor: str = Field(..., min_length=1, description="Identifier of the conversation session where it occurred")
    turn_range: Optional[tuple[int, int]] = Field(
        default=None,
        description="Optional turn index range (start_turn, end_turn)",
    )
    participants: tuple[str, ...] = Field(
        default=("aevum", "user"),
        description="Participants in the episode (must contain both aevum and user)",
    )
    key_learnings: tuple[str, ...] = Field(
        default=(),
        description="Shared insights or mutual learnings established during this episode",
    )
    canonical_status: CanonicalStatus = Field(
        default=CanonicalStatus.CANONICAL,
        description="Canonical truth status of the shared episode",
    )
    recall_level: RecallLevel = Field(
        default=RecallLevel.VIVID,
        description="Phenomenological recall level of the shared memory",
    )
    created_at_era: LifeEra = Field(
        default=LifeEra.ADULTHOOD,
        description="LifeEra when the shared episode occurred (Lock 3)",
    )

    @model_validator(mode="after")
    def validate_shared_scope_isolation(self) -> Self:
        """Lock 4: Shared History strictly mandates HistoryScope.SHARED_WITH_USER."""
        if self.scope != HistoryScope.SHARED_WITH_USER:
            raise ValueError(
                f"Lock 4 Violation: SharedHistoryEpisode must have HistoryScope.SHARED_WITH_USER, got '{self.scope}'"
            )
        if "user" not in self.participants:
            raise ValueError("SharedHistoryEpisode must include 'user' as a participant")
        if "aevum" not in self.participants:
            raise ValueError("SharedHistoryEpisode must include 'aevum' as a participant")
        return self


class SharedHistoryCandidate(BaseModel):
    """Candidate episode proposed from conversation turn analysis before promotion."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str = Field(..., description="Unique identifier for candidate episode")
    episode_type: SharedEpisodeType = Field(..., description="Classified episode type")
    title: str = Field(..., min_length=1, description="Proposed title")
    summary: str = Field(..., min_length=1, description="Proposed summary")
    session_anchor: str = Field(..., min_length=1, description="Originating session identifier")
    turn_range: Optional[tuple[int, int]] = Field(default=None, description="Turn index range")
    participants: tuple[str, ...] = Field(
        default=("aevum", "user"),
        description="Participants in the episode",
    )
    key_learnings: tuple[str, ...] = Field(default=(), description="Shared insights")
    evidence_text: str = Field(..., min_length=1, description="Raw conversation dialogue excerpt")
    is_validated: bool = Field(default=False, description="Whether multi-validator Bible check has passed")


class SharedHistoryQuery(BaseModel):
    """Scoped query specification for shared history retrieval."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    raw_query: str = Field(..., min_length=1, description="Inquiry string")
    episode_type: Optional[SharedEpisodeType] = Field(default=None, description="Optional episode type filter")
    keywords: tuple[str, ...] = Field(default=(), description="Normalized keyword tokens")
    session_anchor: Optional[str] = Field(default=None, description="Filter by originating session")
    scope: HistoryScope = Field(
        default=HistoryScope.SHARED_WITH_USER,
        description="Strictly SHARED_WITH_USER (Lock F: Scope-first)",
    )

    @model_validator(mode="after")
    def validate_query_scope(self) -> Self:
        if self.scope != HistoryScope.SHARED_WITH_USER:
            raise ValueError("SharedHistoryQuery strictly requires HistoryScope.SHARED_WITH_USER")
        return self


class AssembledLongitudinalContext(BaseModel):
    """Merged dual-track context containing personal biography and shared user journey."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    personal_context: AssembledBiographicalContext = Field(
        ...,
        description="Track 1: Personal autobiographical context (Phase 12.3)",
    )
    shared_episodes: tuple[SharedHistoryEpisode, ...] = Field(
        default=(),
        description="Track 2: Shared history episodes with the user",
    )
    relational_metrics: Optional[dict[str, float]] = Field(
        default=None,
        description="Rule 16 multi-axis relational dynamics snapshot (familiarity, trust, comfort, etc.)",
    )
    longitudinal_xml: str = Field(
        ...,
        description="Serialized XML <longitudinal_context> containing both tracks",
    )
    context_hash: str = Field(
        ...,
        description="SHA-256 hash of longitudinal_xml for bitwise replay determinism",
    )
