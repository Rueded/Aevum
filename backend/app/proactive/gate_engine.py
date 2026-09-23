"""Proactive Gate Engine (Phase 8 Lock-in 8, 9, 10).

Deterministic 6-gate filter enforcing privacy boundaries, quiet hours,
cooldowns, daily caps, and physiological state.

Invariants:
- Lock-in 8: Explicit IANA timezone evaluation for quiet hours and daily boundaries.
- Lock-in 9: Only DELIVERED (and subsequent CLICKED/DISMISSED) notifications consume daily quota.
- Lock-in 10: DND is terminal suppression; suppressed intents are discarded, never queued.
"""

from datetime import datetime, time, timezone
from typing import Any, Iterable, Optional
import zoneinfo

from app.proactive.models import (
    DesktopUserSettings,
    GateEvaluationResult,
    ProactiveIntent,
    SuppressionReason,
)


def is_in_quiet_hours(local_dt: datetime, start_str: str, end_str: str) -> bool:
    """Determine whether local datetime falls within quiet hours, handling midnight wrap."""
    start_parts = [int(p) for p in start_str.split(":")]
    end_parts = [int(p) for p in end_str.split(":")]
    start_time = time(start_parts[0], start_parts[1])
    end_time = time(end_parts[0], end_parts[1])
    current_time = local_dt.time()

    if start_time == end_time:
        return False

    if start_time > end_time:
        # Midnight wrap-around: e.g. 23:00 to 08:00
        return current_time >= start_time or current_time < end_time
    else:
        # Same-day window: e.g. 13:00 to 15:00
        return start_time <= current_time < end_time


def get_local_day_start(dt_local: datetime) -> datetime:
    """Return midnight start of the local day in the local timezone."""
    return dt_local.replace(hour=0, minute=0, second=0, microsecond=0)


class ProactiveGateEngine:
    """Deterministic gate filter for proactive reach-out opportunities."""

    FATIGUE_CEILING: float = 0.85
    MIN_INTENT_THRESHOLD: float = 0.40

    def evaluate_gates(
        self,
        settings: DesktopUserSettings,
        intent: ProactiveIntent,
        current_time: datetime,
        recent_notifications: Iterable[Any],
        fatigue: float = 0.0,
        current_activity: Optional[str] = None,
    ) -> GateEvaluationResult:
        """
        Evaluate all 6 deterministic gates.

        Returns GateEvaluationResult with passed=True only if all gates clear.
        """
        # Ensure current_time is timezone-aware
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        # Convert to configured user timezone (Lock-in 8)
        user_tz = zoneinfo.ZoneInfo(settings.timezone)
        local_time = current_time.astimezone(user_tz)

        gate_breakdown: dict[str, bool] = {
            "master_switch": False,
            "dnd": False,
            "quiet_hours": False,
            "daily_cap": False,
            "cooldown": False,
            "physiological": False,
        }

        # Gate 1: Master Switch (Invariant 25)
        if not settings.proactive_enabled:
            return GateEvaluationResult(
                passed=False,
                suppression_reason=SuppressionReason.DISABLED,
                gate_breakdown=gate_breakdown,
                evaluation_time=current_time,
            )
        gate_breakdown["master_switch"] = True

        # Gate 2: Temporary DND (Lock-in 10 - Terminal suppression)
        if settings.dnd_until is not None:
            dnd_until_aware = (
                settings.dnd_until
                if settings.dnd_until.tzinfo is not None
                else settings.dnd_until.replace(tzinfo=timezone.utc)
            )
            if current_time < dnd_until_aware:
                return GateEvaluationResult(
                    passed=False,
                    suppression_reason=SuppressionReason.DND_ACTIVE,
                    gate_breakdown=gate_breakdown,
                    evaluation_time=current_time,
                )
        gate_breakdown["dnd"] = True

        # Gate 3: Timezone-Aware Quiet Hours (Lock-in 8)
        if settings.quiet_hours_enabled:
            if is_in_quiet_hours(local_time, settings.quiet_hours_start, settings.quiet_hours_end):
                return GateEvaluationResult(
                    passed=False,
                    suppression_reason=SuppressionReason.QUIET_HOURS,
                    gate_breakdown=gate_breakdown,
                    evaluation_time=current_time,
                )
        gate_breakdown["quiet_hours"] = True

        # Gate 4: Daily Cap (Lock-in 9 - Only DELIVERED / CLICKED / DISMISSED consume quota)
        local_day_start = get_local_day_start(local_time)
        delivered_statuses = {"DELIVERED", "CLICKED", "DISMISSED"}

        delivered_today_count = 0
        most_recent_delivered_at: Optional[datetime] = None

        for n in recent_notifications:
            status = getattr(n, "status", None) or (n.get("status") if isinstance(n, dict) else None)
            if status in delivered_statuses:
                deliv_at = getattr(n, "delivered_at", None) or (
                    n.get("delivered_at") if isinstance(n, dict) else None
                )
                if deliv_at is not None:
                    if deliv_at.tzinfo is None:
                        deliv_at = deliv_at.replace(tzinfo=timezone.utc)

                    # Track most recent delivery for cooldown check
                    if most_recent_delivered_at is None or deliv_at > most_recent_delivered_at:
                        most_recent_delivered_at = deliv_at

                    # Check if within current user local day
                    deliv_local = deliv_at.astimezone(user_tz)
                    if deliv_local >= local_day_start:
                        delivered_today_count += 1

        if delivered_today_count >= settings.max_daily_reach_outs:
            return GateEvaluationResult(
                passed=False,
                suppression_reason=SuppressionReason.DAILY_CAP,
                gate_breakdown=gate_breakdown,
                evaluation_time=current_time,
            )
        gate_breakdown["daily_cap"] = True

        # Gate 5: Cooldown Interval
        if most_recent_delivered_at is not None:
            elapsed_minutes = (current_time - most_recent_delivered_at).total_seconds() / 60.0
            if elapsed_minutes < settings.min_cooldown_minutes:
                return GateEvaluationResult(
                    passed=False,
                    suppression_reason=SuppressionReason.COOLDOWN,
                    gate_breakdown=gate_breakdown,
                    evaluation_time=current_time,
                )
        gate_breakdown["cooldown"] = True

        # Gate 6: Physiological State & Sleep
        if current_activity in ("SLEEP", "night_sleep", "nap"):
            return GateEvaluationResult(
                passed=False,
                suppression_reason=SuppressionReason.SLEEPING,
                gate_breakdown=gate_breakdown,
                evaluation_time=current_time,
            )

        if fatigue >= self.FATIGUE_CEILING:
            return GateEvaluationResult(
                passed=False,
                suppression_reason=SuppressionReason.HIGH_FATIGUE,
                gate_breakdown=gate_breakdown,
                evaluation_time=current_time,
            )

        if intent.intent_strength < self.MIN_INTENT_THRESHOLD:
            return GateEvaluationResult(
                passed=False,
                suppression_reason=SuppressionReason.LOW_INTENT,
                gate_breakdown=gate_breakdown,
                evaluation_time=current_time,
            )
        gate_breakdown["physiological"] = True

        return GateEvaluationResult(
            passed=True,
            suppression_reason=None,
            gate_breakdown=gate_breakdown,
            evaluation_time=current_time,
        )
