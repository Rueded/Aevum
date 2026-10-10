"""Desktop Domain Models & Schemas (Phase 8.3).

Strictly enforces:
- Lock-in 4: Zero persistence without idle consent.
- Lock-in 5: Subordinated desktop context only.
- Additional Lock-in A: In-memory transient lifecycle with explicit TTL.
- Additional Lock-in B: No psychological interpretation.
"""

from datetime import datetime, timezone
import enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
import zoneinfo


class IdleCategory(str, enum.Enum):
    """Categorical availability states derived from idle duration."""

    ACTIVE = "ACTIVE"
    BRIEFLY_AWAY = "BRIEFLY_AWAY"
    EXTENDED_IDLE = "EXTENDED_IDLE"


class DesktopHeartbeatRequest(BaseModel):
    """Incoming periodic telemetry from desktop client shell."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    client_id: str = Field(..., description="Unique client instance identifier.")
    client_timestamp: datetime = Field(..., description="Client-side timestamp of heartbeat.")
    is_idle: Optional[bool] = Field(default=None, description="Client idle status.")
    idle_seconds: Optional[float] = Field(default=None, description="Seconds elapsed since last user input.")
    window_focused: Optional[bool] = Field(default=None, description="Whether main window currently holds focus.")
    app_active: Optional[bool] = Field(default=None, description="Whether desktop client is running and un-minimized.")


class DesktopHeartbeatResponse(BaseModel):
    """Response returned from desktop heartbeat."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    awareness_enabled: bool = Field(..., description="Whether idle awareness telemetry is accepted.")
    dnd_active: bool = Field(..., description="Whether Do-Not-Disturb is currently suppressing reach-outs.")
    pending_notifications_count: int = Field(default=0, description="Count of notifications awaiting delivery.")
    server_timestamp: datetime = Field(..., description="Server UTC time of response.")


class DesktopAvailabilityContext(BaseModel):
    """In-memory transient representation of desktop availability.

    Hard Invariants (Additional Lock-in A & B):
    - Strictly transient, NOT an ORM model.
    - NOT written to SQLite or any persistent store.
    - NOT written to CharacterState, RelationshipState, or Memory.
    - NOT converted into LifeEvent.
    - Expires after ttl_seconds.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    character_id: str = Field(default="aevum", description="Character identifier.")
    is_user_available: bool = Field(..., description="Availability boolean based on idle threshold.")
    idle_category: IdleCategory = Field(..., description="Coarse availability category.")
    window_focused: bool = Field(default=False, description="Whether the companion window was focused.")
    observed_at: datetime = Field(..., description="UTC timestamp of the observation.")
    ttl_seconds: float = Field(default=120.0, description="Context lifetime in seconds before automatic expiry.")

    def is_expired(self, current_time: Optional[datetime] = None) -> bool:
        """Check if this transient availability context has exceeded its TTL."""
        now = current_time or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        obs = self.observed_at if self.observed_at.tzinfo is not None else self.observed_at.replace(tzinfo=timezone.utc)
        elapsed = (now - obs).total_seconds()
        return elapsed > self.ttl_seconds or elapsed < -5.0


class DesktopUserSettingsUpdate(BaseModel):
    """Request payload for updating desktop user settings."""

    model_config = ConfigDict(extra="forbid")

    proactive_enabled: Optional[bool] = None
    timezone: Optional[str] = None
    quiet_hours_enabled: Optional[bool] = None
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    max_daily_reach_outs: Optional[int] = Field(default=None, ge=1, le=20)
    min_cooldown_minutes: Optional[int] = Field(default=None, ge=5, le=1440)
    idle_awareness_enabled: Optional[bool] = None
    idle_threshold_seconds: Optional[int] = Field(default=None, ge=30, le=3600)
    user_country: Optional[str] = Field(default=None, description="User cultural locale/country (e.g. 'MY', 'CN', 'SG', 'TW', 'GLOBAL').")

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            try:
                zoneinfo.ZoneInfo(v)
            except Exception as e:
                raise ValueError(f"Invalid IANA timezone '{v}': {e}") from e
        return v

    @field_validator("quiet_hours_start", "quiet_hours_end")
    @classmethod
    def validate_time_format(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            parts = v.split(":")
            if len(parts) != 2:
                raise ValueError(f"Time must be HH:MM format, got '{v}'")
            try:
                h, m = int(parts[0]), int(parts[1])
                if not (0 <= h <= 23 and 0 <= m <= 59):
                    raise ValueError("Hour must be 0-23 and minute 0-59")
            except ValueError as e:
                raise ValueError(f"Invalid time format '{v}': {e}") from e
        return v


class SetDNDRequest(BaseModel):
    """Request payload for setting or clearing temporary Do-Not-Disturb."""

    model_config = ConfigDict(extra="forbid")

    duration_minutes: Optional[int] = Field(default=None, ge=1, le=1440, description="DND duration in minutes.")
    clear: bool = Field(default=False, description="Whether to clear active DND immediately.")


class ClaimNotificationRequest(BaseModel):
    """Request payload for claiming a pending notification lease."""

    model_config = ConfigDict(extra="forbid")

    worker_id: str = Field(..., min_length=1, max_length=100, description="Unique worker/instance ID claiming the lease.")
    lease_timeout_seconds: Optional[float] = Field(default=None, ge=5.0, le=300.0, description="Custom lease timeout in seconds.")
    character_id: str = Field(default="aevum", max_length=36, description="Character identifier.")


class CompleteNotificationRequest(BaseModel):
    """Request payload for completing a delivering notification."""

    model_config = ConfigDict(extra="forbid")

    worker_id: str = Field(..., min_length=1, max_length=100, description="Worker ID that currently holds the lease.")
    character_id: str = Field(default="aevum", max_length=36, description="Character identifier.")


class ReleaseNotificationRequest(BaseModel):
    """Request payload for releasing a claim back to pending."""

    model_config = ConfigDict(extra="forbid")

    worker_id: str = Field(..., min_length=1, max_length=100, description="Worker ID that currently holds the lease.")
    character_id: str = Field(default="aevum", max_length=36, description="Character identifier.")


class InteractNotificationRequest(BaseModel):
    """Request payload for recording user interaction with a delivered notification."""

    model_config = ConfigDict(extra="forbid")

    action: str = Field(..., description="Action taken by user: CLICKED or DISMISSED.")
    character_id: str = Field(default="aevum", max_length=36, description="Character identifier.")


class NotificationItemResponse(BaseModel):
    """Canonical representation of a proactive notification record."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    character_id: str
    conversation_message_id: str
    trigger_type: str
    idempotency_key: str
    title: str
    body: str
    status: str
    claimed_by: Optional[str] = None
    claimed_at: Optional[datetime] = None
    suppression_reason: Optional[str] = None
    context_metadata: Optional[str] = None
    created_at: datetime
    delivered_at: Optional[datetime] = None
    interacted_at: Optional[datetime] = None

