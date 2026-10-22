"""Proactive Communication & Reach-Out Engine (Phase 8)."""

from app.proactive.models import (
    DesktopUserSettings,
    GateEvaluationResult,
    NotificationStatus,
    ProactiveContext,
    ProactiveIntent,
    ProactiveIntentType,
    ProactiveTriggerType,
    SuppressionReason,
)
from app.proactive.intent_engine import ProactiveIntentEngine
from app.proactive.gate_engine import ProactiveGateEngine
from app.proactive.message_generator import ProactiveMessageGenerator
from app.proactive.notification_service import ProactiveNotificationService
from app.proactive.thought_engine import ProactiveThoughtEngine, ProactiveThoughtOutput
from app.proactive.loop import ProactiveLoop, start_proactive_loop

__all__ = [
    "DesktopUserSettings",
    "GateEvaluationResult",
    "NotificationStatus",
    "ProactiveContext",
    "ProactiveIntent",
    "ProactiveIntentType",
    "ProactiveTriggerType",
    "SuppressionReason",
    "ProactiveIntentEngine",
    "ProactiveGateEngine",
    "ProactiveMessageGenerator",
    "ProactiveNotificationService",
    "ProactiveThoughtEngine",
    "ProactiveThoughtOutput",
    "ProactiveLoop",
    "start_proactive_loop",
]

