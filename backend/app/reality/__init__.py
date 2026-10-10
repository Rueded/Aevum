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
from app.reality.temporal_models import (
    Canonicality,
    EpistemicGrounding,
    LifeEventItem,
    LifeStage,
    LifeStateItem,
    MAX_COMPATIBLE_TRAJECTORIES,
    MAX_PROJECTED_NODES,
    MAX_TEMPORAL_PROPAGATION_HOPS,
    TemporalGranularity,
    TemporalHorizon,
    TemporalInterval,
    validate_epistemic_canonicality_combination,
)
from app.reality.temporal_rules import (
    AgeWindowValue,
    CalendarWindowValue,
    DurationBoundValue,
    StagePrecedenceValue,
    TemporalConstraintType,
    TemporalRuleItem,
    TemporalRuleRegistry,
    TemporalRuleScope,
)
from app.reality.temporal_graph import (
    ConstraintEvaluationResult,
    ConstraintStatus,
    TemporalConstraintEvaluator,
    TemporalConstraintGraph,
    TemporalEdge,
    TemporalNode,
    TemporalRelationType,
)
from app.reality.trajectory_engine import (
    CANONICAL_HIGHER_ED_PATHWAYS,
    LifeTrajectory,
    TimelineTrajectoryEngine,
    TrajectoryPluralityResult,
    TrajectoryStatus,
)
from app.reality.timeline_orchestration_coordinator import (
    TemporalConflictSignal,
    TemporalEvaluationStatus,
    TimelineEvidenceAdapter,
    TimelineOrchestrationCoordinator,
    TimelineOrchestrationResult,
)

__all__ = [
    "AgeWindowValue",
    "BeliefClaim",
    "BudgetFilterResult",
    "BudgetRejectionReason",
    "CANONICAL_HIGHER_ED_PATHWAYS",
    "CalendarWindowValue",
    "CandidateCompetitionService",
    "CandidateFact",
    "CandidateHypothesis",
    "CandidateHypothesisSet",
    "CandidateLifecycleState",
    "CandidateRepository",
    "CandidateStatus",
    "Canonicality",
    "CausalityValidator",
    "ChoiceConfig",
    "ChoiceDecisionResult",
    "ChoiceFactorBreakdown",
    "ChoiceRationaleCode",
    "ChoiceSelectionService",
    "CompetitionResult",
    "CompetitionState",
    "ConsistencyValidator",
    "ConstraintEvaluationResult",
    "ConstraintStatus",
    "ContradictionResolution",
    "ContradictionResolver",
    "ContradictionType",
    "CoreFactItem",
    "DurationBoundValue",
    "EpistemicGrounding",
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
    "LifeEventItem",
    "LifeStage",
    "LifeStateItem",
    "LifeTrajectory",
    "MAX_COMPATIBLE_TRAJECTORIES",
    "MAX_PROJECTED_NODES",
    "MAX_TEMPORAL_PROPAGATION_HOPS",
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
    "StagePrecedenceValue",
    "TemporalConflictSignal",
    "TemporalConstraintEvaluator",
    "TemporalConstraintGraph",
    "TemporalConstraintType",
    "TemporalEdge",
    "TemporalEvaluationStatus",
    "TemporalGranularity",
    "TemporalHorizon",
    "TemporalInterval",
    "TemporalNode",
    "TemporalRelationType",
    "TemporalRuleItem",
    "TemporalRuleRegistry",
    "TemporalRuleScope",
    "TimelineEvidenceAdapter",
    "TimelineOrchestrationCoordinator",
    "TimelineOrchestrationResult",
    "TimelineTrajectoryEngine",
    "TimelineValidator",
    "TrajectoryPluralityResult",
    "TrajectoryStatus",
    "UnknownType",
    "ValidationResult",
    "VolatilityDecayPolicy",
    "WorldKnowledgeItem",
    "WorldKnowledgeRegistry",
    "WorldKnowledgeValidator",
    "classify_slot_volatility",
    "validate_epistemic_canonicality_combination",
]
