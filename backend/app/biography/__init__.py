"""app.biography — Phase 12 Canonical Biography, Causal Life Graphs & Longitudinal Memory.

Establishes:
1. Pure immutable DTOs and enums for personal history and shared journey.
2. Two orthogonal axes: CanonicalStatus (truth) vs RecallLevel (phenomenology).
3. First-class HistoryScope domain identity (AEVUM_PERSONAL vs SHARED_WITH_USER).
4. Epistemic causal integrity with domain-level CausalKnowledgeState (KNOWN / UNKNOWN).
5. Canonical Causal Explanation Graph (DAG) with full multi-hop cycle detection.
6. Read-side LifeEventService for grounded personal history queries.
7. Segregated mutation authorities: BiographyPromotionService vs SharedHistoryService.
"""

from app.biography.biography_models import (
    BiographicalAnchor,
    BiographicalDomain,
    BiographicalFact,
    CanonicalStatus,
    CausalKnowledgeState,
    CausalRelation,
    CausalRelationType,
    HistoryScope,
    LifeEra,
    LifeEventRecord,
    PersonalPreference,
    PreferenceAffinity,
    QualiaAnchor,
    RecallLevel,
    SocialContactRecord,
)
from app.biography.causal_graph import (
    CausalCycleDetectedError,
    CausalExplanationGraph,
    CausalExplanationPath,
    CausalExplanationStep,
    CausalNode,
    CausalNodeNotFoundError,
    CausalNodeType,
)
from app.biography.autobiographical_retriever import AutobiographicalRetriever
from app.biography.biographical_context_assembler import BiographicalContextAssembler
from app.biography.life_event_service import LifeEventService
from app.biography.retrieval_models import (
    AssembledBiographicalContext,
    AutobiographicalIntentType,
    AutobiographicalQuery,
    AutobiographicalRetrievalResult,
    ScoredBiographicalCandidate,
)
from app.biography.shared_history_models import (
    AssembledLongitudinalContext,
    SharedEpisodeType,
    SharedHistoryCandidate,
    SharedHistoryEpisode,
    SharedHistoryQuery,
)
from app.biography.shared_history_service import (
    LongitudinalContextAssembler,
    SharedHistoryService,
)

__all__ = [
    "AssembledBiographicalContext",
    "AssembledLongitudinalContext",
    "AutobiographicalIntentType",
    "AutobiographicalQuery",
    "AutobiographicalRetrievalResult",
    "AutobiographicalRetriever",
    "BiographicalAnchor",
    "BiographicalContextAssembler",
    "BiographicalDomain",
    "BiographicalFact",
    "CanonicalStatus",
    "CausalCycleDetectedError",
    "CausalExplanationGraph",
    "CausalExplanationPath",
    "CausalExplanationStep",
    "CausalKnowledgeState",
    "CausalNode",
    "CausalNodeNotFoundError",
    "CausalNodeType",
    "CausalRelation",
    "CausalRelationType",
    "HistoryScope",
    "LifeEra",
    "LifeEventRecord",
    "LifeEventService",
    "LongitudinalContextAssembler",
    "PersonalPreference",
    "PreferenceAffinity",
    "QualiaAnchor",
    "RecallLevel",
    "ScoredBiographicalCandidate",
    "SharedEpisodeType",
    "SharedHistoryCandidate",
    "SharedHistoryEpisode",
    "SharedHistoryQuery",
    "SharedHistoryService",
    "SocialContactRecord",
]
