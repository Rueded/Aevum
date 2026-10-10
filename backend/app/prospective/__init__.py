"""Phase 19 — Prospective Memory, Unresolved Threads & Experiential Continuity.

Phase 19.1: Prospective Contracts, Epistemic DTOs & Schema Isolation.
Zero execution logic, zero database mutations, zero LLM calls.
"""

from app.prospective.contracts import (
    ClosureReasonKind,
    EpistemicStanceKind,
    GravityTier,
    ProspectiveThread,
    ResonanceTier,
    SalienceCoordinates,
    ThreadDomainKind,
    ThreadEnduranceTier,
    ThreadLifecycleState,
    ThreadProvenanceKind,
    UncertaintyTier,
)
from app.prospective.events import (
    SettlementContextPayload,
    ThreadClosurePayload,
    ThreadEncounterPayload,
    ThreadEventKind,
    ThreadTransitionRecord,
)
from app.prospective.state_machine import (
    InvalidThreadTransitionError,
    LEGAL_TRANSITIONS,
    ThreadStateMachine,
)

from app.prospective.resonance_models import (
    AttentionDecision,
    ExpressionDisposition,
    RealityEventContext,
    ResonanceDegree,
    ResonanceEvaluation,
)
from app.prospective.resonance_engine import ContextualResonanceEngine

from app.prospective.transformation_models import (
    EpistemicStage,
    IllegalEpistemicSkipError,
    TransformationAuditRecord,
    TransformationEvidenceKind,
)
from app.prospective.transformation_engine import (
    EpistemicTransformationEngine,
    LEGAL_LADDER_STEPS,
)

__all__ = [
    "AttentionDecision",
    "ClosureReasonKind",
    "ContextualResonanceEngine",
    "EpistemicStage",
    "EpistemicStanceKind",
    "EpistemicTransformationEngine",
    "ExpressionDisposition",
    "GravityTier",
    "IllegalEpistemicSkipError",
    "InvalidThreadTransitionError",
    "LEGAL_LADDER_STEPS",
    "LEGAL_TRANSITIONS",
    "ProspectiveThread",
    "RealityEventContext",
    "ResonanceDegree",
    "ResonanceEvaluation",
    "ResonanceTier",
    "SalienceCoordinates",
    "SettlementContextPayload",
    "ThreadClosurePayload",
    "ThreadDomainKind",
    "ThreadEncounterPayload",
    "ThreadEnduranceTier",
    "ThreadEventKind",
    "ThreadLifecycleState",
    "ThreadProvenanceKind",
    "ThreadStateMachine",
    "ThreadTransitionRecord",
    "TransformationAuditRecord",
    "TransformationEvidenceKind",
    "UncertaintyTier",
]



