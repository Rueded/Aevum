"""Circadian rhythm modifier engine (Phase 7C.2).

Enforces:
- Invariant 20: Provides modifiers/priors only; does not own or write physiological state.
- Guardrail 2: Modulates alertness and focus affinity without duplicating wakeful sleep pressure.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app.core.config import settings

class CircadianEngine:
    """
    Deterministic diurnal rhythm provider.
    Evaluates local time in Aevum's canonical timezone (Asia/Kuala_Lumpur)
    to output a smooth alertness/sleepiness modifier in [-1.0, 1.0].
    """

    @classmethod
    def get_local_hour(cls, dt_utc: datetime) -> float:
        """Return fractional local hour in Aevum's timezone (0.0 to 24.0)."""
        tz = ZoneInfo(settings.aevum_timezone)
        if dt_utc.tzinfo is None:
            dt_aware = dt_utc.replace(tzinfo=timezone.utc)
        else:
            dt_aware = dt_utc.astimezone(timezone.utc)
        local_dt = dt_aware.astimezone(tz)
        return local_dt.hour + (local_dt.minute / 60.0) + (local_dt.second / 3600.0)

    @classmethod
    def get_circadian_modifier(cls, dt_utc: datetime) -> float:
        """
        Evaluate time to produce a diurnal alertness modifier in [-1.0, 1.0].
        - Positive (+0.2 to +0.8): high alertness, focus affinity, social availability.
        - Neutral (0.0 to +0.2): calm, steady alertness.
        - Negative (-0.7 to -0.2): nocturnal drowsiness, wind-down drive.
        """
        h = cls.get_local_hour(dt_utc)

        # 01:00 - 07:00: Deep night valley
        if 1.0 <= h < 7.0:
            return -0.7

        # 07:00 - 08:30: Morning awakening transition (-0.7 -> +0.3)
        if 7.0 <= h < 8.5:
            progress = (h - 7.0) / 1.5
            return -0.7 + progress * 1.0

        # 08:30 - 12:30: Morning productive window (+0.3 -> +0.6)
        if 8.5 <= h < 12.5:
            return 0.5

        # 12:30 - 14:30: Post-lunch slight alertness dip (+0.2)
        if 12.5 <= h < 14.5:
            return 0.2

        # 14:30 - 22:30: Afternoon and evening peak focus window (+0.6 -> +0.7)
        if 14.5 <= h < 22.5:
            return 0.65

        # 22:30 - 24:00: Late evening wind-down (+0.4 -> -0.2)
        if 22.5 <= h < 24.0:
            progress = (h - 22.5) / 1.5
            return 0.4 - progress * 0.6

        # 00:00 - 01:00: Midnight transition (-0.2 -> -0.7)
        progress = h / 1.0
        return -0.2 - progress * 0.5
