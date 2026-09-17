"""Permission and local capability security service for Aevum Core (Phase E).

Implements default least-privilege access control and enforces strict boundary
against unauthorized system, file, and sensor access.
"""

from datetime import datetime, timezone
import enum
import logging
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PermissionRecord, utc_now

logger = logging.getLogger(__name__)


class Capability(str, enum.Enum):
    """Controlled device or OS capabilities."""

    NOTIFICATIONS = "notifications"
    SCREEN_CONTEXT = "screen_context"
    FILE_SYSTEM = "file_system"
    MICROPHONE = "microphone"
    CAMERA = "camera"


class PermissionService:
    """Evaluates and manages capability permissions under strict least-privilege."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def is_permitted(self, capability: Capability) -> bool:
        """Check whether capability is explicitly permitted by the user.

        Rule 18 Invariant: FILE_SYSTEM access is strictly disallowed by default.
        """
        if capability == Capability.FILE_SYSTEM:
            # Absolute hard block on arbitrary private file system access
            return False

        res = await self._session.execute(
            select(PermissionRecord).where(PermissionRecord.capability == capability.value)
        )
        record = res.scalars().first()
        if record is None:
            # Default least privilege: False
            return False

        return bool(record.is_granted)

    async def set_permission(self, capability: Capability, is_granted: bool) -> None:
        """Set explicit permission status for a capability."""
        if capability == Capability.FILE_SYSTEM and is_granted:
            raise ValueError("FILE_SYSTEM capability cannot be granted: direct file system access is strictly restricted.")

        res = await self._session.execute(
            select(PermissionRecord).where(PermissionRecord.capability == capability.value)
        )
        record = res.scalars().first()

        now = datetime.now(timezone.utc)
        if record is None:
            record = PermissionRecord(
                capability=capability.value,
                is_granted=is_granted,
                granted_at=now if is_granted else None,
                updated_at=now,
            )
            self._session.add(record)
        else:
            record.is_granted = is_granted
            if is_granted and record.granted_at is None:
                record.granted_at = now
            record.updated_at = now

        await self._session.commit()
