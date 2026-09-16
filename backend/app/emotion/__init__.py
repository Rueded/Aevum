"""Emotion package for Aevum Core.

Phase 5.1: Emotion Model Foundation.
Provides domain representations, qualitative vocabulary, optimistic concurrency,
and persistent SQLite storage for Aevum's current dominant emotional state.
"""

from app.emotion.emotion_models import (
    BOOTSTRAP_EMOTION_TYPE,
    BOOTSTRAP_INTENSITY,
    DEFAULT_CHARACTER_ID,
    EmotionState,
    EmotionStateUpdate,
    EmotionType,
    create_initial_emotion_state,
)
from app.emotion.event_models import (
    MAX_EMOTION_EVENT_SUMMARY_LENGTH,
    EmotionEvent,
    EmotionEventCreate,
    EmotionEventSource,
    EmotionEventType,
)
from app.emotion.event_service import (
    DEFAULT_EMOTION_EVENTS_LIST_LIMIT,
    MAX_EMOTION_EVENTS_LIST_LIMIT,
    EmotionEventService,
)
from app.emotion.influence_models import (
    MAX_INFLUENCE_REASON_LENGTH,
    EmotionInfluence,
    EmotionInfluenceCreate,
    EmotionInfluenceDirection,
)
from app.emotion.influence_service import (
    DEFAULT_EMOTION_INFLUENCES_LIST_LIMIT,
    MAX_EMOTION_INFLUENCES_LIST_LIMIT,
    EmotionInfluenceService,
)
from app.emotion.service import (
    EmotionConflictError,
    EmotionService,
    get_emotion_state,
    update_emotion_state,
)
from app.emotion.transition_evaluator import (
    COMPETING_SWITCH_THRESHOLD,
    MAX_SWITCH_INTENSITY,
    MAX_TRANSITION_MAGNITUDE_PER_EVALUATION,
    MIN_SWITCH_INTENSITY,
    EmotionTransitionEvaluator,
    evaluate_emotion_transition,
)
from app.emotion.application_models import (
    EmotionStateApplicationResult,
)
from app.emotion.application_service import (
    EmotionStateApplicationService,
    StaleEmotionTransitionProposalError,
    apply_emotion_transition_proposal,
)
from app.emotion.engine import (
    EmotionEngine,
    process_emotion_influences,
)
from app.emotion.engine_models import (
    EmotionEngineResult,
)
from app.emotion.transition_models import (
    MAX_TRANSITION_REASON_LENGTH,
    EmotionTransitionProposal,
)

__all__ = [
    "BOOTSTRAP_EMOTION_TYPE",
    "BOOTSTRAP_INTENSITY",
    "COMPETING_SWITCH_THRESHOLD",
    "DEFAULT_CHARACTER_ID",
    "DEFAULT_EMOTION_EVENTS_LIST_LIMIT",
    "DEFAULT_EMOTION_INFLUENCES_LIST_LIMIT",
    "EmotionConflictError",
    "EmotionEngine",
    "EmotionEngineResult",
    "EmotionEvent",
    "EmotionEventCreate",
    "EmotionEventService",
    "EmotionEventSource",
    "EmotionEventType",
    "EmotionInfluence",
    "EmotionInfluenceCreate",
    "EmotionInfluenceDirection",
    "EmotionInfluenceService",
    "EmotionService",
    "EmotionState",
    "EmotionStateApplicationResult",
    "EmotionStateApplicationService",
    "EmotionStateUpdate",
    "EmotionTransitionEvaluator",
    "EmotionTransitionProposal",
    "EmotionType",
    "MAX_EMOTION_EVENTS_LIST_LIMIT",
    "MAX_EMOTION_EVENT_SUMMARY_LENGTH",
    "MAX_EMOTION_INFLUENCES_LIST_LIMIT",
    "MAX_INFLUENCE_REASON_LENGTH",
    "MAX_SWITCH_INTENSITY",
    "MAX_TRANSITION_MAGNITUDE_PER_EVALUATION",
    "MAX_TRANSITION_REASON_LENGTH",
    "MIN_SWITCH_INTENSITY",
    "StaleEmotionTransitionProposalError",
    "apply_emotion_transition_proposal",
    "create_initial_emotion_state",
    "evaluate_emotion_transition",
    "get_emotion_state",
    "process_emotion_influences",
    "update_emotion_state",
]
