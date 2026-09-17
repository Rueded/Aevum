"""Memory domain models for Aevum Core.

Defines provider-independent, immutable models representing persistent long-term memories,
categories, and validated partial memory updates.
"""

from datetime import datetime
import enum
import math
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_MEMORY_CONTENT_LENGTH = 5000


class MemoryCategory(str, enum.Enum):
    """Explicit categories for structured long-term memories.

    Intentionally bounded to core cognitive and episodic domains:
    - FACT: Stable information about the user or character.
    - PREFERENCE: User or character preference.
    - EVENT: A meaningful occurrence or milestone.
    - EXPERIENCE: A shared or personally meaningful interaction/experience.
    - PROMISE: A commitment or promise made.
    - JOKE: A recurring inside joke or humorous reference.
    - RELATIONSHIP: A meaningful relational fact or dynamic.
    - USER_GOAL: A goal or aspiration expressed by the user.
    - USER_PROBLEM: A problem, concern, or ongoing difficulty shared by the user.
    - CHARACTER_EVENT: A meaningful event in Aevum's personal/independent life.
    """

    FACT = "FACT"
    PREFERENCE = "PREFERENCE"
    EVENT = "EVENT"
    EXPERIENCE = "EXPERIENCE"
    PROMISE = "PROMISE"
    JOKE = "JOKE"
    RELATIONSHIP = "RELATIONSHIP"
    USER_GOAL = "USER_GOAL"
    USER_PROBLEM = "USER_PROBLEM"
    CHARACTER_EVENT = "CHARACTER_EVENT"


class MemorySubjectEntity(str, enum.Enum):
    """Explicit entity attribution for who a memory belongs to or describes.

    Distinguishes character-owned facts, user-owned facts, and third-party/NPC facts
    to prevent speaker attribution drift across long interaction horizons.
    """

    AEVUM = "AEVUM"
    USER = "USER"
    NPC = "NPC"
    OTHER = "OTHER"


def _validate_normalized_float(v: float, field_name: str) -> float:
    """Ensure float is a finite normalized number between 0.0 and 1.0 inclusive."""
    if math.isnan(v):
        raise ValueError(f"{field_name} must not be NaN.")
    if math.isinf(v):
        raise ValueError(f"{field_name} must not be infinite.")
    if v < 0.0 or v > 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0 inclusive.")
    return float(v)


def _validate_memory_content(v: str, field_name: str) -> str:
    """Ensure content is non-empty, stripped, and within length bounds."""
    if not isinstance(v, str) or not v.strip():
        raise ValueError(f"{field_name} must not be empty or whitespace.")
    stripped = v.strip()
    if len(stripped) > MAX_MEMORY_CONTENT_LENGTH:
        raise ValueError(
            f"{field_name} exceeds maximum length of {MAX_MEMORY_CONTENT_LENGTH} characters."
        )
    return stripped


class Memory(BaseModel):
    """Immutable aggregate representing a persistent structured long-term memory.

    Distinction:
    - Conversation History = Raw turn-by-turn dialogue transcripts.
    - CharacterDefinition = WHO Aevum is (stable identity and personality).
    - CharacterState = HOW Aevum currently is (current condition and activity).
    - Memory = WHAT Aevum remembers happened / learned / mattered.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(
        ...,
        description="Unique, stable identifier for the memory record (UUID).",
    )
    category: MemoryCategory = Field(
        ...,
        description="Semantic category of the memory.",
    )
    subject_entity: MemorySubjectEntity = Field(
        default=MemorySubjectEntity.USER,
        description="Entity/person that this memory pertains to or belongs to (AEVUM, USER, NPC, OTHER).",
    )
    content: str = Field(
        ...,
        description="Human-readable semantic content of the memory.",
    )

    importance: float = Field(
        default=0.5,
        description="Normalized significance of the memory (0.0 = trivial, 1.0 = vital).",
    )
    confidence: float = Field(
        default=0.9,
        description="Normalized certainty of the memory (0.0 = highly uncertain, 1.0 = certain fact).",
    )
    emotional_weight: float = Field(
        default=0.0,
        description="Normalized emotional significance of the memory (0.0 = neutral, 1.0 = intense).",
    )

    created_at: datetime = Field(
        ...,
        description="Immutable UTC timestamp when the memory was initially formed.",
    )
    updated_at: datetime = Field(
        ...,
        description="UTC timestamp when the memory was most recently modified.",
    )
    last_recalled: datetime | None = Field(
        default=None,
        description="UTC timestamp of the most recent explicit recall, or None if never recalled.",
    )
    times_recalled: int = Field(
        default=0,
        ge=0,
        description="Counter of explicit recall events for this memory.",
    )
    version: int = Field(
        default=1,
        ge=1,
        description="Monotonically increasing version counter for optimistic concurrency.",
    )

    @field_validator("importance", "confidence", "emotional_weight")
    @classmethod
    def validate_metrics(cls, v: float, info: Any) -> float:
        return _validate_normalized_float(v, info.field_name)

    @field_validator("content")
    @classmethod
    def validate_content_field(cls, v: str, info: Any) -> str:
        return _validate_memory_content(v, info.field_name)

    @model_validator(mode="before")
    @classmethod
    def _default_subject_entity(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "subject_entity" not in data or data["subject_entity"] is None:
                category = data.get("category")
                if category in (MemoryCategory.CHARACTER_EVENT, MemoryCategory.CHARACTER_EVENT.value):
                    data["subject_entity"] = MemorySubjectEntity.AEVUM
                else:
                    data["subject_entity"] = MemorySubjectEntity.USER
        return data


class MemoryUpdate(BaseModel):
    """Immutable, validated request to partially modify an existing memory.

    Immutable metadata (id, category, created_at) cannot be updated via this model.
    Empty update requests containing zero specified fields are rejected.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    content: str | None = None
    subject_entity: MemorySubjectEntity | None = None
    importance: float | None = None
    confidence: float | None = None
    emotional_weight: float | None = None

    @field_validator("importance", "confidence", "emotional_weight")
    @classmethod
    def validate_optional_metrics(cls, v: float | None, info: Any) -> float | None:
        if v is not None:
            return _validate_normalized_float(v, info.field_name)
        return v

    @field_validator("content")
    @classmethod
    def validate_optional_content(cls, v: str | None, info: Any) -> str | None:
        if v is not None:
            return _validate_memory_content(v, info.field_name)
        return v

    @model_validator(mode="after")
    def check_at_least_one_field_provided(self) -> "MemoryUpdate":
        non_none_fields = {
            k: v for k, v in self.model_dump().items() if v is not None
        }
        if not non_none_fields:
            raise ValueError("MemoryUpdate must specify at least one field to update.")
        return self


# =============================================================================
# Phase 3.2: Memory Candidate & Curation Models
# =============================================================================


class MemoryCandidateStatus(str, enum.Enum):
    """Lifecycle status for a memory candidate."""

    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class MemoryCandidateSource(str, enum.Enum):
    """Source that proposed the memory candidate.

    Note: The LLM source type exists for forward-compatibility with future
    language interpretation layers. No LLM calls are invoked in Phase 3.2.
    """

    MANUAL = "MANUAL"
    SYSTEM = "SYSTEM"
    LLM = "LLM"


class MemoryCandidate(BaseModel):
    """Immutable aggregate representing a potential memory candidate awaiting curation.

    Distinction:
    - Candidate = Uncurated proposal that might deserve persistent memory.
    - Memory = Curated, persistent reality owned by Aevum Core.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(
        ...,
        description="Unique UUID identifier for the candidate record.",
    )
    category: MemoryCategory = Field(
        ...,
        description="Proposed category for the candidate.",
    )
    subject_entity: MemorySubjectEntity = Field(
        default=MemorySubjectEntity.USER,
        description="Entity/person that this candidate memory pertains to (AEVUM, USER, NPC, OTHER).",
    )
    content: str = Field(
        ...,
        description="Proposed semantic content of the memory candidate.",
    )

    importance: float = Field(
        default=0.5,
        description="Proposed normalized significance (0.0 to 1.0).",
    )
    confidence: float = Field(
        default=0.9,
        description="Proposed normalized certainty (0.0 to 1.0).",
    )
    emotional_weight: float = Field(
        default=0.0,
        description="Proposed normalized emotional saliency (0.0 to 1.0).",
    )

    status: MemoryCandidateStatus = Field(
        default=MemoryCandidateStatus.PENDING,
        description="Current lifecycle status of the candidate.",
    )
    source_type: MemoryCandidateSource = Field(
        default=MemoryCandidateSource.MANUAL,
        description="Source component that proposed this candidate.",
    )

    created_at: datetime = Field(
        ...,
        description="Immutable UTC timestamp when the candidate was created.",
    )
    updated_at: datetime = Field(
        ...,
        description="UTC timestamp of the most recent candidate update.",
    )
    version: int = Field(
        default=1,
        ge=1,
        description="Monotonically increasing version counter for optimistic concurrency.",
    )

    @model_validator(mode="before")
    @classmethod
    def _default_subject_entity(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "subject_entity" not in data or data["subject_entity"] is None:
                category = data.get("category")
                if category in (MemoryCategory.CHARACTER_EVENT, MemoryCategory.CHARACTER_EVENT.value):
                    data["subject_entity"] = MemorySubjectEntity.AEVUM
                else:
                    data["subject_entity"] = MemorySubjectEntity.USER
        return data

    @field_validator("importance", "confidence", "emotional_weight")
    @classmethod
    def validate_metrics(cls, v: float, info: Any) -> float:
        return _validate_normalized_float(v, info.field_name)

    @field_validator("content")
    @classmethod
    def validate_content_field(cls, v: str, info: Any) -> str:
        return _validate_memory_content(v, info.field_name)


class MemoryCandidateUpdate(BaseModel):
    """Immutable, validated request to modify a PENDING memory candidate.

    Only mutable while status is PENDING. Terminal candidates (ACCEPTED or REJECTED)
    cannot be modified.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    content: str | None = None
    subject_entity: MemorySubjectEntity | None = None
    importance: float | None = None
    confidence: float | None = None
    emotional_weight: float | None = None

    @field_validator("importance", "confidence", "emotional_weight")
    @classmethod
    def validate_optional_metrics(cls, v: float | None, info: Any) -> float | None:
        if v is not None:
            return _validate_normalized_float(v, info.field_name)
        return v

    @field_validator("content")
    @classmethod
    def validate_optional_content(cls, v: str | None, info: Any) -> str | None:
        if v is not None:
            return _validate_memory_content(v, info.field_name)
        return v

    @model_validator(mode="after")
    def check_at_least_one_field_provided(self) -> "MemoryCandidateUpdate":
        non_none_fields = {
            k: v for k, v in self.model_dump().items() if v is not None
        }
        if not non_none_fields:
            raise ValueError("MemoryCandidateUpdate must specify at least one field to update.")
        return self


class CurationDecision(str, enum.Enum):
    """Outcome of a memory candidate curation evaluation."""

    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    DUPLICATE = "DUPLICATE"


class CurationResult(BaseModel):
    """Result of a deterministic memory curation decision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision: CurationDecision
    candidate_id: str
    memory_id: str | None = None
    memory: Memory | None = None
    reason: str | None = None


# =============================================================================
# Phase 3.3: LLM Memory Extraction Models
# =============================================================================


class MemoryExtractionProposal(BaseModel):
    """Immutable, validated memory proposal generated by an LLM.

    Contains purely semantic proposals. Database identifiers, versions, timestamps,
    and lifecycle status are strictly forbidden.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    category: MemoryCategory
    subject_entity: MemorySubjectEntity = Field(
        default=MemorySubjectEntity.USER,
        description="Entity/person that this proposed memory pertains to (AEVUM, USER, NPC, OTHER).",
    )
    content: str
    importance: float = 0.5
    confidence: float = 0.9
    emotional_weight: float = 0.0

    @field_validator("importance", "confidence", "emotional_weight")
    @classmethod
    def validate_metrics(cls, v: float, info: Any) -> float:
        return _validate_normalized_float(v, info.field_name)

    @field_validator("content")
    @classmethod
    def validate_content_field(cls, v: str, info: Any) -> str:
        return _validate_memory_content(v, info.field_name)


class MemoryExtractionPayload(BaseModel):
    """Container schema for structured JSON output from LLM."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    proposals: list[MemoryExtractionProposal] = Field(
        default_factory=list,
        description="List of proposed memories. Can be empty.",
    )


class MemoryExtractionResult(BaseModel):
    """Immutable result of an application-owned memory extraction execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    proposals: tuple[MemoryExtractionProposal, ...] = ()
    candidate_ids: tuple[str, ...] = ()
    is_success: bool = True
    error_message: str | None = None


# =============================================================================
# Phase 3.4: Automatic Memory Curation Models
# =============================================================================


class MemoryCurationDecision(str, enum.Enum):
    """Deterministic curation decision for a candidate."""

    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    DEFER = "DEFER"


class MemoryCurationReason(str, enum.Enum):
    """Deterministic explanation for a curation decision."""

    ACCEPTED_STABLE_FACT = "ACCEPTED_STABLE_FACT"
    ACCEPTED_STRONG_PREFERENCE = "ACCEPTED_STRONG_PREFERENCE"
    ACCEPTED_USER_GOAL = "ACCEPTED_USER_GOAL"
    ACCEPTED_USER_PROBLEM = "ACCEPTED_USER_PROBLEM"
    ACCEPTED_PROMISE = "ACCEPTED_PROMISE"
    ACCEPTED_EVENT = "ACCEPTED_EVENT"
    REJECTED_LOW_CONFIDENCE = "REJECTED_LOW_CONFIDENCE"
    REJECTED_LOW_IMPORTANCE = "REJECTED_LOW_IMPORTANCE"
    REJECTED_SECRET = "REJECTED_SECRET"
    REJECTED_DUPLICATE = "REJECTED_DUPLICATE"
    REJECTED_TERMINAL = "REJECTED_TERMINAL"
    DEFERRED_AMBIGUOUS_CATEGORY = "DEFERRED_AMBIGUOUS_CATEGORY"
    DEFERRED_INSUFFICIENT_SALIENCE = "DEFERRED_INSUFFICIENT_SALIENCE"


class CandidateEvaluation(BaseModel):
    """Deterministic evaluation outcome of a MemoryCandidate against curation policy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision: MemoryCurationDecision
    reason: MemoryCurationReason
    explanation: str


class BatchCurationResult(BaseModel):
    """Outcome of a batch automatic curation run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    accepted_candidate_ids: tuple[str, ...] = ()
    rejected_candidate_ids: tuple[str, ...] = ()
    deferred_candidate_ids: tuple[str, ...] = ()
    total_evaluated: int = 0


# =============================================================================
# Phase 3.5: Memory Retrieval Foundation Models
# =============================================================================

MAX_RETRIEVAL_LIMIT: int = 20
MAX_RETRIEVAL_QUERY_LENGTH: int = 1000
MIN_RETRIEVAL_SCORE: float = 0.20


class MemoryRetrievalQuery(BaseModel):
    """Immutable, validated query for memory retrieval."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(
        ...,
        description="Query text representing conversational context or search topic.",
    )
    categories: tuple[MemoryCategory, ...] = Field(
        default=(),
        description="Optional category filter. If empty, all memory categories are eligible.",
    )
    subject_entities: tuple[MemorySubjectEntity, ...] = Field(
        default=(),
        description="Optional subject entity filter (AEVUM, USER, NPC, OTHER). If empty, all entities are eligible.",
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=MAX_RETRIEVAL_LIMIT,
        description=f"Maximum number of memories to return (1 to {MAX_RETRIEVAL_LIMIT}).",
    )

    @field_validator("text")
    @classmethod
    def _validate_text(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Query text must not be empty or whitespace.")
        stripped = v.strip()
        if len(stripped) > MAX_RETRIEVAL_QUERY_LENGTH:
            raise ValueError(
                f"Query text exceeds maximum length of {MAX_RETRIEVAL_QUERY_LENGTH} characters."
            )
        return stripped


class MemoryRetrievalSignals(BaseModel):
    """Structured breakdown of individual retrieval scoring signals."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text_relevance: float = Field(
        ...,
        description="Normalized lexical overlap and phrase match score (0.0 to 1.0).",
    )
    importance: float = Field(
        ...,
        description="Normalized importance score of the memory (0.0 to 1.0).",
    )
    confidence: float = Field(
        ...,
        description="Normalized confidence score of the memory (0.0 to 1.0).",
    )
    recency: float = Field(
        ...,
        description="Normalized recency score with smooth decay (0.0 to 1.0).",
    )


class ScoredMemory(BaseModel):
    """Immutable container pairing a persistent Memory domain model with its retrieval score and signals."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    memory: Memory
    score: float
    signals: MemoryRetrievalSignals


class MemoryRetrievalResult(BaseModel):
    """Immutable result of a memory retrieval query."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query: MemoryRetrievalQuery
    memories: tuple[ScoredMemory, ...] = ()
    total_candidates: int = 0
    returned_count: int = 0


# =============================================================================
# Phase 3.6: Semantic Memory Retrieval & Embedding Models
# =============================================================================

MIN_SEMANTIC_SIMILARITY: float = 0.50


class EmbeddingResult(BaseModel):
    """Immutable result of a text embedding operation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    vector: tuple[float, ...] = Field(
        ...,
        description="Normalized or raw embedding vector values.",
    )
    model: str = Field(
        ...,
        description="Identifier of the embedding model that generated this vector.",
    )
    dimensions: int = Field(
        ...,
        description="Dimensionality of the vector.",
    )
    provider: str = Field(
        default="unknown",
        description="Name of the embedding provider.",
    )

    @field_validator("vector")
    @classmethod
    def _validate_vector(cls, v: tuple[float, ...]) -> tuple[float, ...]:
        if not v:
            raise ValueError("Embedding vector must not be empty.")
        for idx, val in enumerate(v):
            if math.isnan(val):
                raise ValueError(f"Vector component at index {idx} must not be NaN.")
            if math.isinf(val):
                raise ValueError(f"Vector component at index {idx} must not be infinite.")
        return v

    @model_validator(mode="after")
    def _validate_dimensions_match(self) -> "EmbeddingResult":
        if self.dimensions != len(self.vector):
            raise ValueError(
                f"Dimensions field ({self.dimensions}) does not match vector length ({len(self.vector)})."
            )
        return self


class MemoryEmbedding(BaseModel):
    """Immutable domain representation of a persistent memory embedding record."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(..., description="Unique ID of the embedding record.")
    memory_id: str = Field(..., description="Foreign key to the associated Memory record.")
    provider: str = Field(..., description="Embedding provider name.")
    model: str = Field(..., description="Embedding model identifier.")
    dimensions: int = Field(..., description="Embedding dimensions count.")
    vector: tuple[float, ...] = Field(..., description="Deserialized vector components.")
    created_at: datetime = Field(..., description="Creation timestamp in UTC.")
    updated_at: datetime = Field(..., description="Last update timestamp in UTC.")
    version: int = Field(default=1, description="Optimistic concurrency version.")


class SemanticMemoryRetrievalQuery(BaseModel):
    """Immutable query for semantic memory retrieval."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(
        ...,
        description="Query text to embed and search against persistent memory embeddings.",
    )
    categories: tuple[MemoryCategory, ...] = Field(
        default=(),
        description="Optional category filter. If empty, all memory categories are eligible.",
    )
    subject_entities: tuple[MemorySubjectEntity, ...] = Field(
        default=(),
        description="Optional subject entity filter (AEVUM, USER, NPC, OTHER). If empty, all entities are eligible.",
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=MAX_RETRIEVAL_LIMIT,
        description=f"Maximum number of memories to return (1 to {MAX_RETRIEVAL_LIMIT}).",
    )
    min_similarity: float = Field(
        default=MIN_SEMANTIC_SIMILARITY,
        ge=-1.0,
        le=1.0,
        description="Minimum cosine similarity threshold required for inclusion.",
    )

    @field_validator("text")
    @classmethod
    def _validate_text(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Query text must not be empty or whitespace.")
        stripped = v.strip()
        if len(stripped) > MAX_RETRIEVAL_QUERY_LENGTH:
            raise ValueError(
                f"Query text exceeds maximum length of {MAX_RETRIEVAL_QUERY_LENGTH} characters."
            )
        return stripped


class SemanticMemoryResult(BaseModel):
    """Immutable container pairing a persistent Memory domain model with its cosine similarity score."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    memory: Memory
    similarity: float


class SemanticMemoryRetrievalResult(BaseModel):
    """Immutable result of a semantic memory retrieval query."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query: SemanticMemoryRetrievalQuery
    memories: tuple[SemanticMemoryResult, ...] = ()
    total_candidates: int = 0
    returned_count: int = 0


# =============================================================================
# Phase 3.7: Hybrid Memory Retrieval Models
# =============================================================================

DEFAULT_HYBRID_LEXICAL_WEIGHT: float = 0.50
DEFAULT_HYBRID_SEMANTIC_WEIGHT: float = 0.50


class HybridMemoryRetrievalQuery(BaseModel):
    """Immutable query specification for hybrid memory retrieval."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(
        ...,
        description="Query text to match against persistent memories lexically and semantically.",
    )
    categories: tuple[MemoryCategory, ...] = Field(
        default=(),
        description="Optional category filter. If empty, all memory categories are eligible.",
    )
    subject_entities: tuple[MemorySubjectEntity, ...] = Field(
        default=(),
        description="Optional subject entity filter (AEVUM, USER, NPC, OTHER). If empty, all entities are eligible.",
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=MAX_RETRIEVAL_LIMIT,
        description=f"Maximum number of memories to return (1 to {MAX_RETRIEVAL_LIMIT}).",
    )
    min_similarity: float = Field(
        default=MIN_SEMANTIC_SIMILARITY,
        ge=-1.0,
        le=1.0,
        description="Minimum cosine similarity threshold required for semantic candidate inclusion.",
    )
    lexical_weight: float = Field(
        default=DEFAULT_HYBRID_LEXICAL_WEIGHT,
        ge=0.0,
        le=1.0,
        description="Weight factor for lexical retrieval score (default: 0.50).",
    )
    semantic_weight: float = Field(
        default=DEFAULT_HYBRID_SEMANTIC_WEIGHT,
        ge=0.0,
        le=1.0,
        description="Weight factor for semantic similarity score (default: 0.50).",
    )

    @field_validator("text")
    @classmethod
    def _validate_text(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Query text must not be empty or whitespace.")
        stripped = v.strip()
        if len(stripped) > MAX_RETRIEVAL_QUERY_LENGTH:
            raise ValueError(
                f"Query text exceeds maximum length of {MAX_RETRIEVAL_QUERY_LENGTH} characters."
            )
        return stripped


class HybridMemoryResult(BaseModel):
    """Immutable container pairing a persistent Memory with its hybrid, lexical, and semantic scores."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    memory: Memory
    hybrid_score: float
    lexical_score: float = 0.0
    semantic_score: float = 0.0


class HybridMemoryRetrievalResult(BaseModel):
    """Immutable result of a hybrid memory retrieval query."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query: HybridMemoryRetrievalQuery
    memories: tuple[HybridMemoryResult, ...] = ()
    total_candidates: int = 0
    returned_count: int = 0
    semantic_fallback_triggered: bool = False







