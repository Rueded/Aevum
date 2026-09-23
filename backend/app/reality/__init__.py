"""Reality and epistemic domain package for Aevum Core."""

from app.reality.ledger_models import LedgerItem, RealityLedgerProjection
from app.reality.models import (
    CoreFactItem,
    FactAuthority,
    FactSource,
    FactStatus,
    LedgerTier,
)
from app.reality.registry import (
    FactKeyRegistry,
    InvalidFactValueError,
)

from app.reality.evidence_models import EvidenceExtractionMode, EvidenceRecord, EvidenceSource
from app.reality.belief_models import BeliefClaim, EpistemicStatus, FactSubject, UnknownType
from app.reality.candidate_models import (
    CandidateFact,
    CandidateHypothesis,
    CandidateHypothesisSet,
    CandidateLifecycleState,
    CandidateStatus,
    EvidenceFamily,
    InferenceEdgeType,
    InferenceScope,
    PlausibilityBreakdown,
    ProvenanceLineage,
    RealityImpact,
    RealityTaxonomy,
)
from app.reality.world_knowledge import KnowledgeKind, WorldKnowledgeItem, WorldKnowledgeRegistry
from app.reality.validators import (
    CausalityValidator,
    ConsistencyValidator,
    TimelineValidator,
    ValidationResult,
    WorldKnowledgeValidator,
)
from app.reality.contradiction_models import (
    ContradictionResolution,
    ContradictionType,
    RepairStrategy,
)
from app.reality.contradiction_resolver import ContradictionResolver
from app.reality.promotion_models import PromotionDecision, PromotionType
from app.reality.promotion_service import RealityPromotionService
from app.reality.candidate_repository import CandidateRepository
from app.reality.budget_controller import (
    BudgetFilterResult,
    BudgetRejectionReason,
    InferenceBudgetController,
    ProvenanceDAGValidator,
)
from app.reality.history_models import RealityRevisionRecord
from app.reality.history_service import RealityHistoryService
from app.reality.belief_engine import RealityBeliefEngine, RealityCycleResult
from app.reality.choice_models import (
    ChoiceConfig,
    ChoiceDecisionResult,
    ChoiceFactorBreakdown,
    ChoiceRationaleCode,
    CompetitionResult,
    CompetitionState,
)
from app.reality.competition_service import CandidateCompetitionService
from app.reality.choice_service import ChoiceSelectionService
from app.reality.volatility_policy import (
    FactVolatilityCategory,
    VolatilityDecayPolicy,
    classify_slot_volatility,
)

__all__ = [
    "BeliefClaim",
    "BudgetFilterResult",
    "BudgetRejectionReason",
    "CandidateCompetitionService",
    "CandidateFact",
    "CandidateHypothesis",
    "CandidateHypothesisSet",
    "CandidateLifecycleState",
    "CandidateRepository",
    "CandidateStatus",
    "CausalityValidator",
    "ChoiceConfig",
    "ChoiceDecisionResult",
    "ChoiceFactorBreakdown",
    "ChoiceRationaleCode",
    "ChoiceSelectionService",
    "CompetitionResult",
    "CompetitionState",
    "ConsistencyValidator",
    "ContradictionResolution",
    "ContradictionResolver",
    "ContradictionType",
    "CoreFactItem",
    "EpistemicStatus",
    "EvidenceExtractionMode",
    "EvidenceFamily",
    "EvidenceRecord",
    "EvidenceSource",
    "FactAuthority",
    "FactKeyRegistry",
    "FactSource",
    "FactStatus",
    "FactSubject",
    "FactVolatilityCategory",
    "InferenceBudgetController",
    "InferenceEdgeType",
    "InferenceScope",
    "InvalidFactValueError",
    "KnowledgeKind",
    "LedgerItem",
    "LedgerTier",
    "PlausibilityBreakdown",
    "PromotionDecision",
    "PromotionType",
    "ProvenanceDAGValidator",
    "ProvenanceLineage",
    "RealityBeliefEngine",
    "RealityCycleResult",
    "RealityHistoryService",
    "RealityImpact",
    "RealityLedgerProjection",
    "RealityPromotionService",
    "RealityRevisionRecord",
    "RealityTaxonomy",
    "RepairStrategy",
    "TimelineValidator",
    "UnknownType",
    "ValidationResult",
    "VolatilityDecayPolicy",
    "WorldKnowledgeItem",
    "WorldKnowledgeRegistry",
    "WorldKnowledgeValidator",
    "classify_slot_volatility",
]
