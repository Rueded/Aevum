"""Life simulation domain module."""
from app.life.models import (
    LifeState,
    LifeActivity,
    LifePlan,
    LifeEvent,
    LifeGoal,
    LifeActivityType,
    LifeActivityStatus,
    LifePlanStatus,
    LifeEventType,
    LifeGoalStatus,
)
from app.life.services import LifeService, OptimisticConcurrencyError
from app.life.simulator import LifeSimulator, LifeSimulationResult, reconcile_current_life
from app.life.context_models import CharacterLifeContext
from app.life.context_builder import LifeContextBuilder
from app.life.emotion_integrator import LifeEmotionIntegrator
from app.life.orchestrator import LifeSimulationOrchestrator, LifeSimulationTickResult
from app.life.activity_templates import (
    ActivityGroundingPolicy,
    ActivityTemplate,
    CANONICAL_ACTIVITY_TEMPLATES,
    get_template_by_id,
)
from app.life.activity_utility import (
    ActivitySelectionDecision,
    ActivityUtilityBreakdown,
    ActivityUtilityEvaluator,
    HardEligibilityGate,
)
from app.life.activity_selector import AutonomousActivitySelector

__all__ = [
    "LifeState",
    "LifeActivity",
    "LifePlan",
    "LifeEvent",
    "LifeGoal",
    "LifeActivityType",
    "LifeActivityStatus",
    "LifePlanStatus",
    "LifeEventType",
    "LifeGoalStatus",
    "LifeService",
    "OptimisticConcurrencyError",
    "LifeSimulator",
    "LifeSimulationResult",
    "reconcile_current_life",
    "CharacterLifeContext",
    "LifeContextBuilder",
    "LifeEmotionIntegrator",
    "LifeSimulationOrchestrator",
    "LifeSimulationTickResult",
    "ActivityGroundingPolicy",
    "ActivityTemplate",
    "CANONICAL_ACTIVITY_TEMPLATES",
    "get_template_by_id",
    "ActivitySelectionDecision",
    "ActivityUtilityBreakdown",
    "ActivityUtilityEvaluator",
    "HardEligibilityGate",
    "AutonomousActivitySelector",
]
