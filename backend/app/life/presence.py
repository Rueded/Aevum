"""User presence, absence tracking, and activity-aware attention for Aevum Core (Phase E)."""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class PresenceState(BaseModel):
    """Immutable semantic state of user presence, absence duration, and attention guidance."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    last_user_interaction_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp of previous user interaction.",
    )
    current_time: datetime = Field(
        ...,
        description="Current UTC timestamp.",
    )
    absence_duration_seconds: float = Field(
        default=0.0,
        description="Elapsed seconds since last interaction.",
    )
    absence_guidance: Optional[str] = Field(
        default=None,
        description="Behavioral guidance regarding elapsed time.",
    )
    attention_level: str = Field(
        default="NORMAL",
        description="Character situational attention level (NORMAL, FOCUSED, DORMANT).",
    )
    suggested_reply_delay_seconds: int = Field(
        default=0,
        description="Simulated realistic response timing delay in seconds.",
    )


class PresenceTracker:
    """Computes absence duration, anti-clinginess guidance, and activity attention."""

    @classmethod
    def track_presence(
        cls,
        last_interaction_at: Optional[datetime],
        current_time: Optional[datetime] = None,
        current_activity: str = "resting",
    ) -> PresenceState:
        """Evaluate presence dynamics and generate non-clingy guidance."""
        now = current_time or datetime.now(timezone.utc)

        if last_interaction_at is None:
            absence_seconds = 0.0
            guidance = None
        else:
            absence_seconds = max(0.0, (now - last_interaction_at).total_seconds())
            if absence_seconds >= 86400.0:  # > 24 hours
                hours = absence_seconds / 3600.0
                guidance = (
                    f"The user has returned after an absence of {hours:.0f} hours. "
                    "Acknowledge the gap naturally if it fits conversation, but NEVER exhibit clinginess, "
                    "guilt-tripping, resentment, or claims of abandonment."
                )
            elif absence_seconds >= 14400.0:  # > 4 hours
                hours = absence_seconds / 3600.0
                guidance = (
                    f"A few hours have passed ({hours:.1f} hours) since the last message. "
                    "Maintain normal conversational rhythm without dramatic commentary."
                )
            else:
                guidance = None

        # Activity attention mapping
        act_lower = current_activity.lower()
        if "sleep" in act_lower:
            attention = "DORMANT"
            delay = 30
        elif any(f in act_lower for f in ("piano", "practice", "study", "read", "writing", "composition")):
            attention = "FOCUSED"
            delay = 10
        else:
            attention = "NORMAL"
            delay = 0

        return PresenceState(
            last_user_interaction_at=last_interaction_at,
            current_time=now,
            absence_duration_seconds=absence_seconds,
            absence_guidance=guidance,
            attention_level=attention,
            suggested_reply_delay_seconds=delay,
        )
