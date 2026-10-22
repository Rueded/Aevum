"""Domain models and enums for Proactive Reach-Out & Desktop Integration (Phase 8)."""

from datetime import datetime, timezone
import enum
import re
from typing import Any, Optional
import zoneinfo

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


class ProactiveIntentType(str, enum.Enum):
    """Permitted proactive intention categories."""

    SHARE_EXPERIENCE = "SHARE_EXPERIENCE"
    SOCIAL_CHECKIN = "SOCIAL_CHECKIN"
    TASK_REMINDER = "TASK_REMINDER"
    SPONTANEOUS_THOUGHT = "SPONTANEOUS_THOUGHT"


class ProactiveTriggerType(str, enum.Enum):
    """Categorization of what situational context gave rise to proactive opportunity."""

    ACTIVITY_COMPLETED = "ACTIVITY_COMPLETED"
    SPONTANEOUS_SHARE = "SPONTANEOUS_SHARE"
    SCHEDULED_REMINDER = "SCHEDULED_REMINDER"
    CONTEXT_CHECKIN = "CONTEXT_CHECKIN"


class NotificationStatus(str, enum.Enum):
    """Lifecycle states of a proactive notification."""

    PENDING = "PENDING"
    DELIVERING = "DELIVERING"
    DELIVERED = "DELIVERED"
    CLICKED = "CLICKED"
    DISMISSED = "DISMISSED"
    SUPPRESSED = "SUPPRESSED"


class SuppressionReason(str, enum.Enum):
    """Audit reason explaining why a proactive reach-out candidate was blocked."""

    DISABLED = "DISABLED"
    DND_ACTIVE = "DND_ACTIVE"
    QUIET_HOURS = "QUIET_HOURS"
    DAILY_CAP = "DAILY_CAP"
    COOLDOWN = "COOLDOWN"
    HIGH_FATIGUE = "HIGH_FATIGUE"
    SLEEPING = "SLEEPING"
    BUSY = "BUSY"
    LOW_INTENT = "LOW_INTENT"
    EXPIRED = "EXPIRED"


class ProactiveIntent(BaseModel):
    """Proactive communication intention formed within Aevum Core (Lock-in 1)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    character_id: str = "aevum"
    intent_type: ProactiveIntentType
    intent_strength: float = Field(..., ge=0.0, le=1.0)
    grounding_event_id: Optional[str] = None
    grounding_activity_title: Optional[str] = None
    topic_hook: Optional[str] = None
    reasoning_trace: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)


class DesktopUserSettings(BaseModel):
    """Validated user settings and privacy boundaries (Lock-in 4, 8, 9; Phase 5 §8.6)."""

    model_config = ConfigDict(extra="ignore")

    character_id: str = "aevum"
    proactive_enabled: bool = False
    timezone: str = "Asia/Shanghai"
    quiet_hours_enabled: bool = True
    quiet_hours_start: str = "23:00"
    quiet_hours_end: str = "08:00"
    max_daily_reach_outs: int = Field(default=3, ge=1, le=10)
    min_cooldown_minutes: int = Field(default=120, ge=15, le=720)
    idle_awareness_enabled: bool = False
    idle_threshold_seconds: int = Field(default=300, ge=30, le=3600)
    reply_latency_enabled: bool = False
    max_reply_latency_minutes: int = Field(default=15, ge=1, le=120)
    dnd_until: Optional[datetime] = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        try:
            zoneinfo.ZoneInfo(v)
        except Exception as err:
            raise ValueError(f"Invalid IANA timezone '{v}': {err}") from err
        return v

    @field_validator("quiet_hours_start", "quiet_hours_end")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        if not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", v):
            raise ValueError(f"Time format must be HH:MM (24-hour), got '{v}'")
        return v


class GateEvaluationResult(BaseModel):
    """Structured audit of deterministic gate evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    passed: bool
    suppression_reason: Optional[SuppressionReason] = None
    gate_breakdown: dict[str, bool] = Field(default_factory=dict)
    evaluation_time: datetime = Field(default_factory=utc_now)


class ProactiveContext(BaseModel):
    """Filtered canonical context for proactive reach-out message generation (Lock-in 6)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    character_id: str = "aevum"
    current_activity: Optional[str] = None
    recent_events: list[str] = Field(default_factory=list)
    active_goals: list[str] = Field(default_factory=list)
    approved_intent: ProactiveIntent
    relationship_comfort: float = 0.0
    relationship_trust: float = 0.0
