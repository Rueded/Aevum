"""Desktop Service (Phase 8.3).

Coordinates desktop configuration, consent-gated heartbeat telemetry,
and transient in-memory availability context.

Enforces:
- Lock-in 4: Zero persistence without idle consent.
- Lock-in 5: Subordinated desktop availability context only.
- Additional Lock-in A: In-memory transient lifecycle with explicit TTL.
- Additional Lock-in B: No psychological interpretation.
- Standard 33: Dual audit trail retrieval.
"""

from datetime import datetime, timedelta, timezone
import logging
from typing import ClassVar, Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DesktopUserSettingsRecord, ProactiveNotificationRecord
from app.desktop.models import (
    DesktopAvailabilityContext,
    DesktopHeartbeatRequest,
    DesktopHeartbeatResponse,
    DesktopUserSettingsUpdate,
    IdleCategory,
)

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DesktopService:
    """Service governing desktop settings, heartbeat telemetry, and transient context."""

    # In-memory transient store for ephemeral availability contexts.
    # HARD INVARIANT (Additional Lock-in A): Strictly memory-only. Never written to DB.
    _transient_contexts: ClassVar[dict[str, DesktopAvailabilityContext]] = {}

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @classmethod
    def clear_all_transient_contexts(cls) -> None:
        """Clear all in-memory transient availability contexts (simulates process restart)."""
        cls._transient_contexts.clear()

    @classmethod
    def clear_transient_context(cls, character_id: str = "aevum") -> None:
        """Clear transient context for a character (e.g. on consent revocation)."""
        cls._transient_contexts.pop(character_id, None)

    @classmethod
    def get_transient_context(
        cls, character_id: str = "aevum", current_time: Optional[datetime] = None
    ) -> Optional[DesktopAvailabilityContext]:
        """Retrieve current in-memory availability context if not expired."""
        ctx = cls._transient_contexts.get(character_id)
        if ctx is None:
            return None
        if ctx.is_expired(current_time):
            cls._transient_contexts.pop(character_id, None)
            return None
        return ctx

    async def get_settings(self, character_id: str = "aevum") -> DesktopUserSettingsRecord:
        """Retrieve desktop user settings for character, creating defaults if missing."""
        stmt = select(DesktopUserSettingsRecord).where(DesktopUserSettingsRecord.character_id == character_id)
        record = (await self._session.scalars(stmt)).first()
        if record is None:
            record = DesktopUserSettingsRecord(
                character_id=character_id,
                proactive_enabled=False,
                timezone="Asia/Shanghai",
                quiet_hours_enabled=True,
                quiet_hours_start="23:00",
                quiet_hours_end="08:00",
                max_daily_reach_outs=3,
                min_cooldown_minutes=120,
                idle_awareness_enabled=False,
                idle_threshold_seconds=300,
                dnd_until=None,
                created_at=_utc_now(),
                updated_at=_utc_now(),
            )
            self._session.add(record)
            await self._session.commit()
            await self._session.refresh(record)
        return record

    async def update_settings(
        self, updates: DesktopUserSettingsUpdate, character_id: str = "aevum"
    ) -> DesktopUserSettingsRecord:
        """Update desktop user settings, respecting consent revocation rules."""
        record = await self.get_settings(character_id)

        data = updates.model_dump(exclude_unset=True)
        for k, v in data.items():
            setattr(record, k, v)

        record.updated_at = _utc_now()

        # Hard Invariant (Lock-in 4 & Additional Lock-in A):
        # Revoking consent immediately clears any transient in-memory availability context.
        if updates.idle_awareness_enabled is False:
            self.clear_transient_context(character_id)

        await self._session.commit()
        await self._session.refresh(record)
        return record

    async def set_dnd(
        self,
        duration_minutes: Optional[int] = None,
        clear: bool = False,
        character_id: str = "aevum",
        current_time: Optional[datetime] = None,
    ) -> DesktopUserSettingsRecord:
        """Set or clear temporary Do-Not-Disturb."""
        record = await self.get_settings(character_id)
        now = current_time or _utc_now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        if clear or duration_minutes is None:
            record.dnd_until = None
        else:
            record.dnd_until = now + timedelta(minutes=duration_minutes)

        record.updated_at = now
        await self._session.commit()
        await self._session.refresh(record)
        return record

    async def process_heartbeat(
        self,
        request: DesktopHeartbeatRequest,
        character_id: str = "aevum",
        current_time: Optional[datetime] = None,
    ) -> DesktopHeartbeatResponse:
        """Process periodic desktop client heartbeat with strict consent gating.

        Invariants Enforced:
        - Lock-in 4: When idle_awareness_enabled == False, discard telemetry in-memory.
          ZERO rows written to SQLite.
        - Lock-in 5 & Additional Lock-in B: Telemetry is purely availability context.
          Zero psychological interpretation, zero mutation of emotions, trust, or memory.
        - Additional Lock-in A: In-memory transient context only, expiring after 120s TTL.
        """
        now = current_time or _utc_now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        settings = await self.get_settings(character_id)

        # 1. Evaluate DND active state
        dnd_active = False
        if settings.dnd_until is not None:
            dnd_until_aware = (
                settings.dnd_until
                if settings.dnd_until.tzinfo is not None
                else settings.dnd_until.replace(tzinfo=timezone.utc)
            )
            dnd_active = dnd_until_aware > now

        # 2. Count pending notifications
        count_stmt = select(func.count()).select_from(ProactiveNotificationRecord).where(
            ProactiveNotificationRecord.character_id == character_id,
            ProactiveNotificationRecord.status == "PENDING",
        )
        pending_count = await self._session.scalar(count_stmt) or 0

        # 3. Privacy Consent Gating (Lock-in 4)
        if not settings.idle_awareness_enabled:
            # Explicit consent absent: discard all idle metrics in-memory immediately.
            # ZERO telemetry records written to DB.
            self.clear_transient_context(character_id)
            return DesktopHeartbeatResponse(
                awareness_enabled=False,
                dnd_active=dnd_active,
                pending_notifications_count=pending_count,
                server_timestamp=now,
            )

        # 4. Consent Enabled: Derive In-Memory Availability Context (Lock-in 5 & Additional Lock-in A/B)
        idle_secs = request.idle_seconds if request.idle_seconds is not None else 0.0
        threshold = float(settings.idle_threshold_seconds)

        if request.is_idle is True or idle_secs >= threshold:
            is_available = False
            if idle_secs >= 1800.0:
                category = IdleCategory.EXTENDED_IDLE
            else:
                category = IdleCategory.BRIEFLY_AWAY
        else:
            is_available = True
            category = IdleCategory.ACTIVE

        # Form in-memory transient context (never persisted to SQLite)
        context = DesktopAvailabilityContext(
            character_id=character_id,
            is_user_available=is_available,
            idle_category=category,
            window_focused=bool(request.window_focused),
            observed_at=now,
            ttl_seconds=120.0,
        )
        self.__class__._transient_contexts[character_id] = context

        return DesktopHeartbeatResponse(
            awareness_enabled=True,
            dnd_active=dnd_active,
            pending_notifications_count=pending_count,
            server_timestamp=now,
        )

    async def get_audit_history(
        self, character_id: str = "aevum", limit: int = 50
    ) -> list[ProactiveNotificationRecord]:
        """Query dual audit trail of proactive candidates (DELIVERED and SUPPRESSED)."""
        stmt = (
            select(ProactiveNotificationRecord)
            .where(ProactiveNotificationRecord.character_id == character_id)
            .order_by(ProactiveNotificationRecord.created_at.desc())
            .limit(limit)
        )
        return list((await self._session.scalars(stmt)).all())
