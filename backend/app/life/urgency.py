"""Proactive Urgency Engine for Aevum Core (Phase E).

Evaluates candidate life events for proactive sharing, strictly gated by
quiet hours in Aevum's timezone, cooldown limits, and notification permissions.
"""

from datetime import datetime, timezone
import logging
from typing import Optional
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings

logger = logging.getLogger(__name__)


class ProactiveCandidate(BaseModel):
    """A candidate life event or thought that could trigger proactive engagement."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    title: str
    importance: float = Field(..., ge=0.0, le=1.0)
    occurred_at: datetime


class UrgencyEvaluation(BaseModel):
    """Result of proactive urgency evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    urgency_score: float = Field(..., ge=0.0, le=1.0)
    should_trigger: bool
    suppression_reason: Optional[str] = None


class ProactiveUrgencyEngine:
    """Calculates proactive urgency and enforces quiet hours, cooldown, and permissions."""

    @classmethod
    def evaluate(
        cls,
        candidate: ProactiveCandidate,
        current_time: datetime,
        last_proactive_at: Optional[datetime] = None,
        last_interaction_at: Optional[datetime] = None,
        relationship_affinity: float = 0.0,
        social_need: Optional[float] = None,
        unshared_events_score: Optional[float] = None,
        notifications_permitted: bool = False,
        timezone_name: Optional[str] = None,
        min_cooldown_seconds: float = 14400.0,  # 4 hours
        urgency_threshold: float = 0.60,
        w_time: float = 0.30,
        w_social: float = 0.30,
        w_events: float = 0.40,
    ) -> UrgencyEvaluation:
        """Evaluate whether a candidate life event should proactively message the user.

        Formula:
            U = ((T_silence * W_time) + (S_need * W_social) + (E_unshared * W_events)) / C_cooldown
        """
        # 1. Gate: Permission check (default least privilege)
        if not notifications_permitted:
            return UrgencyEvaluation(
                urgency_score=0.0,
                should_trigger=False,
                suppression_reason="PERMISSIONS_DISABLED",
            )

        # 2. Gate: Quiet hours check (23:00 to 07:00 in local timezone)
        tz_str = timezone_name or settings.aevum_timezone
        try:
            local_tz = ZoneInfo(tz_str)
            local_dt = current_time.astimezone(local_tz)
            if local_dt.hour >= 23 or local_dt.hour < 7:
                return UrgencyEvaluation(
                    urgency_score=0.0,
                    should_trigger=False,
                    suppression_reason="QUIET_HOURS",
                )
        except Exception as exc:
            logger.warning("Timezone conversion error for '%s': %s", tz_str, exc)

        # 3. Urgency Formula Calculation
        # T_silence: Normalized elapsed silence since last interaction (or last proactive engagement)
        if last_interaction_at is not None:
            silence_hours = max(0.0, (current_time - last_interaction_at).total_seconds() / 3600.0)
            t_silence = min(1.0, silence_hours / 72.0)
        elif last_proactive_at is not None:
            silence_hours = max(0.0, (current_time - last_proactive_at).total_seconds() / 3600.0)
            t_silence = min(1.0, silence_hours / 72.0)
        else:
            t_silence = 0.50

        # S_need: Social need / loneliness factor [0.0, 1.0]
        if social_need is not None:
            s_need = max(0.0, min(1.0, social_need))
        else:
            s_need = max(0.0, min(1.0, relationship_affinity / 100.0))

        # E_unshared: Unshared meaningful events score [0.0, 1.0]
        if unshared_events_score is not None:
            e_unshared = max(0.0, min(1.0, unshared_events_score))
        else:
            age_hours = max(0.0, (current_time - candidate.occurred_at).total_seconds() / 3600.0)
            decay_factor = max(0.2, 1.0 - (age_hours / 48.0))
            e_unshared = max(0.0, min(1.0, candidate.importance * decay_factor))

        # C_cooldown: Cooldown damping factor (>= 1.0)
        cooldown_elapsed: Optional[float] = None
        if last_proactive_at is not None:
            cooldown_elapsed = (current_time - last_proactive_at).total_seconds()
            if cooldown_elapsed < min_cooldown_seconds:
                c_cooldown = max(1.0, min_cooldown_seconds / max(1.0, cooldown_elapsed))
            else:
                c_cooldown = 1.0
        else:
            c_cooldown = 1.0

        numerator = (t_silence * w_time) + (s_need * w_social) + (e_unshared * w_events)
        raw_urgency = numerator / c_cooldown
        urgency_score = round(max(0.0, min(1.0, raw_urgency)), 2)

        # 4. Gate: Cooldown active suppression
        if cooldown_elapsed is not None and cooldown_elapsed < min_cooldown_seconds:
            return UrgencyEvaluation(
                urgency_score=urgency_score,
                should_trigger=False,
                suppression_reason="COOLDOWN_ACTIVE",
            )

        # 5. Threshold Gate
        if urgency_score >= urgency_threshold:
            return UrgencyEvaluation(
                urgency_score=urgency_score,
                should_trigger=True,
                suppression_reason=None,
            )

        return UrgencyEvaluation(
            urgency_score=urgency_score,
            should_trigger=False,
            suppression_reason="SCORE_BELOW_THRESHOLD",
        )
