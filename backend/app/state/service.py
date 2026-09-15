"""Application state service for Aevum Core.

Manages canonical application state persistence, loading, and atomic updates
with optimistic concurrency control using version counters.
"""

from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApplicationStateRecord, utc_now
from app.state.models import ApplicationState


class StateConflictError(Exception):
    """Raised when an update fails due to an optimistic concurrency version mismatch."""

    def __init__(self, expected_version: int, actual_version: int) -> None:
        self.expected_version = expected_version
        self.actual_version = actual_version
        super().__init__(
            f"State version mismatch: expected {expected_version}, but current version is {actual_version}"
        )


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime has UTC timezone info attached."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class ApplicationStateService:
    """Service for managing provider-independent application state."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_state(self, state_id: str = "canonical") -> ApplicationState:
        """Load canonical state, creating initial deterministic state (version 1) if none exists."""
        stmt = select(ApplicationStateRecord).where(ApplicationStateRecord.id == state_id)
        record = (await self._session.scalars(stmt)).first()

        if record is None:
            record = ApplicationStateRecord(
                id=state_id,
                version=1,
                updated_at=utc_now(),
            )
            self._session.add(record)
            await self._session.commit()
            await self._session.refresh(record)

        return ApplicationState(
            id=record.id,
            version=record.version,
            updated_at=_ensure_utc(record.updated_at),
        )

    async def update_state(
        self,
        expected_version: int | None = None,
        state_id: str = "canonical",
    ) -> ApplicationState:
        """Update state atomically with optimistic concurrency checking.

        This operation establishes the foundational lifecycle and versioning
        boundary for application state:
        1. Validates expected version when supplied; raises StateConflictError
           on mismatch without modifying the state.
        2. Atomically increments version counter.
        3. Updates the updated_at timestamp.
        4. Commits and returns the updated ApplicationState.

        Actual domain state mutations (emotion, relationship, memory) will be
        owned and coordinated by future dedicated subsystems.
        """
        stmt = select(ApplicationStateRecord).where(ApplicationStateRecord.id == state_id)
        record = (await self._session.scalars(stmt)).first()

        if record is None:
            record = ApplicationStateRecord(
                id=state_id,
                version=1,
                updated_at=utc_now(),
            )
            self._session.add(record)
            await self._session.commit()
            await self._session.refresh(record)

        if expected_version is not None and record.version != expected_version:
            raise StateConflictError(
                expected_version=expected_version,
                actual_version=record.version,
            )

        record.version += 1
        record.updated_at = utc_now()
        await self._session.commit()
        await self._session.refresh(record)

        return ApplicationState(
            id=record.id,
            version=record.version,
            updated_at=_ensure_utc(record.updated_at),
        )


async def get_application_state(
    session: AsyncSession,
    state_id: str = "canonical",
) -> ApplicationState:
    """Convenience function to get canonical application state."""
    service = ApplicationStateService(session)
    return await service.get_state(state_id=state_id)


async def update_application_state(
    session: AsyncSession,
    expected_version: int | None = None,
    state_id: str = "canonical",
) -> ApplicationState:
    """Convenience function to update canonical application state."""
    service = ApplicationStateService(session)
    return await service.update_state(
        expected_version=expected_version,
        state_id=state_id,
    )
