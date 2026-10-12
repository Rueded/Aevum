"""Memory service for Aevum Core.

Provides application-owned persistence, retrieval, atomic conditional updates,
and recall tracking for structured long-term memories in SQLite.
"""

from datetime import datetime, timezone
import uuid
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MemoryRecord, utc_now
from app.memory.models import (
    Memory,
    MemoryCategory,
    MemorySubjectEntity,
    MemoryUpdate,
)


class MemoryNotFoundError(Exception):
    """Raised when a requested memory record does not exist."""

    def __init__(self, memory_id: str) -> None:
        self.memory_id = memory_id
        super().__init__(f"Memory with ID '{memory_id}' was not found.")


class MemoryConflictError(Exception):
    """Raised when a memory update or recall fails due to an optimistic concurrency version mismatch."""

    def __init__(self, memory_id: str, expected_version: int, actual_version: int) -> None:
        self.memory_id = memory_id
        self.expected_version = expected_version
        self.actual_version = actual_version
        super().__init__(
            f"Memory '{memory_id}' version mismatch: expected {expected_version}, but current version is {actual_version}."
        )


def _ensure_utc(dt: datetime | None) -> datetime | None:
    """Ensure datetime has UTC timezone info attached."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class MemoryService:
    """Service managing deterministic long-term memory operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_memory(
        self,
        category: MemoryCategory,
        content: str,
        importance: float = 0.5,
        confidence: float = 0.9,
        emotional_weight: float = 0.0,
        memory_id: str | None = None,
        subject_entity: MemorySubjectEntity | None = None,
        character_id: str = "aevum",
    ) -> Memory:
        """Create and persist a new long-term memory record."""
        stable_id = memory_id or str(uuid.uuid4())
        now = utc_now()

        # Validate domain constraints via domain model instantiation
        domain_mem_kwargs: dict[str, object] = {
            "id": stable_id,
            "category": category,
            "content": content,
            "importance": importance,
            "confidence": confidence,
            "emotional_weight": emotional_weight,
            "created_at": now,
            "updated_at": now,
            "last_recalled": None,
            "times_recalled": 0,
            "version": 1,
        }
        if subject_entity is not None:
            domain_mem_kwargs["subject_entity"] = subject_entity

        domain_mem = Memory(**domain_mem_kwargs)

        record = MemoryRecord(
            id=domain_mem.id,
            category=domain_mem.category.value,
            subject_entity=domain_mem.subject_entity.value,
            character_id=character_id,
            content=domain_mem.content,
            importance=domain_mem.importance,
            confidence=domain_mem.confidence,
            emotional_weight=domain_mem.emotional_weight,
            created_at=domain_mem.created_at,
            updated_at=domain_mem.updated_at,
            last_recalled=None,
            times_recalled=0,
            version=1,
        )
        self._session.add(record)
        await self._session.commit()

        return domain_mem

    async def get_memory(self, memory_id: str) -> Memory | None:
        """Retrieve a specific memory by its unique ID, returning None if not found."""
        query = select(MemoryRecord).where(MemoryRecord.id == memory_id)
        result = await self._session.scalars(query)
        record = result.first()
        if record is None:
            return None
        return self._record_to_domain(record)

    async def list_memories(
        self,
        category: MemoryCategory | None = None,
        subject_entity: MemorySubjectEntity | None = None,
        limit: int = 100,
        offset: int = 0,
        character_id: str | None = None,
    ) -> list[Memory]:
        """Deterministically list memories with optional category, subject, and character filters."""
        query = select(MemoryRecord)
        if character_id is not None:
            query = query.where(MemoryRecord.character_id == character_id)
        if category is not None:
            cat_val = category.value if hasattr(category, "value") else str(category)
            query = query.where(MemoryRecord.category == cat_val)
        if subject_entity is not None:
            subj_val = subject_entity.value if hasattr(subject_entity, "value") else str(subject_entity)
            query = query.where(MemoryRecord.subject_entity == subj_val)

        query = query.order_by(
            MemoryRecord.created_at.desc(),
            MemoryRecord.id.asc(),
        ).offset(offset).limit(limit)

        result = await self._session.scalars(query)
        return [self._record_to_domain(rec) for rec in result.all()]

    async def update_memory(
        self,
        memory_id: str,
        memory_update: MemoryUpdate,
        expected_version: int | None = None,
    ) -> Memory:
        """Apply a validated partial update to an existing memory with optimistic concurrency."""
        # 1. Verify existence and retrieve current record
        existing = await self.get_memory(memory_id)
        if existing is None:
            raise MemoryNotFoundError(memory_id)

        now = utc_now()
        values_to_update: dict[str, object] = {
            "version": MemoryRecord.version + 1,
            "updated_at": now,
        }
        if memory_update.subject_entity is not None:
            values_to_update["subject_entity"] = memory_update.subject_entity.value
        if memory_update.content is not None:
            values_to_update["content"] = memory_update.content
        if memory_update.importance is not None:
            values_to_update["importance"] = memory_update.importance
        if memory_update.confidence is not None:
            values_to_update["confidence"] = memory_update.confidence
        if memory_update.emotional_weight is not None:
            values_to_update["emotional_weight"] = memory_update.emotional_weight

        # 2. Database-enforced atomic conditional update
        if expected_version is not None:
            stmt = (
                update(MemoryRecord)
                .where(
                    MemoryRecord.id == memory_id,
                    MemoryRecord.version == expected_version,
                )
                .values(**values_to_update)
            )
            result = await self._session.execute(stmt)
            if result.rowcount == 0:
                current_v = (
                    await self._session.scalars(
                        select(MemoryRecord.version).where(MemoryRecord.id == memory_id)
                    )
                ).first()
                if current_v is None:
                    raise MemoryNotFoundError(memory_id)
                raise MemoryConflictError(
                    memory_id=memory_id,
                    expected_version=expected_version,
                    actual_version=current_v,
                )
        else:
            stmt = (
                update(MemoryRecord)
                .where(MemoryRecord.id == memory_id)
                .values(**values_to_update)
            )
            result = await self._session.execute(stmt)
            if result.rowcount == 0:
                raise MemoryNotFoundError(memory_id)

        await self._session.commit()
        updated = await self.get_memory(memory_id)
        if updated is None:
            raise MemoryNotFoundError(memory_id)
        return updated

    async def recall_memory(
        self,
        memory_id: str,
        expected_version: int | None = None,
    ) -> Memory:
        """Record an explicit application-level recall event for a memory."""
        existing = await self.get_memory(memory_id)
        if existing is None:
            raise MemoryNotFoundError(memory_id)

        now = utc_now()
        values_to_update: dict[str, object] = {
            "version": MemoryRecord.version + 1,
            "updated_at": now,
            "last_recalled": now,
            "times_recalled": MemoryRecord.times_recalled + 1,
        }

        if expected_version is not None:
            stmt = (
                update(MemoryRecord)
                .where(
                    MemoryRecord.id == memory_id,
                    MemoryRecord.version == expected_version,
                )
                .values(**values_to_update)
            )
            result = await self._session.execute(stmt)
            if result.rowcount == 0:
                current_v = (
                    await self._session.scalars(
                        select(MemoryRecord.version).where(MemoryRecord.id == memory_id)
                    )
                ).first()
                if current_v is None:
                    raise MemoryNotFoundError(memory_id)
                raise MemoryConflictError(
                    memory_id=memory_id,
                    expected_version=expected_version,
                    actual_version=current_v,
                )
        else:
            stmt = (
                update(MemoryRecord)
                .where(MemoryRecord.id == memory_id)
                .values(**values_to_update)
            )
            result = await self._session.execute(stmt)
            if result.rowcount == 0:
                raise MemoryNotFoundError(memory_id)

        await self._session.commit()
        recalled = await self.get_memory(memory_id)
        if recalled is None:
            raise MemoryNotFoundError(memory_id)
        return recalled

    async def delete_memory(self, memory_id: str) -> bool:
        """Explicitly delete a memory record by ID. Returns True if deleted, False if not found."""
        stmt = delete(MemoryRecord).where(MemoryRecord.id == memory_id)
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount > 0

    def _record_to_domain(self, record: MemoryRecord) -> Memory:
        """Convert an SQLAlchemy MemoryRecord into an immutable Memory domain model."""
        created = _ensure_utc(record.created_at)
        updated = _ensure_utc(record.updated_at)
        recalled = _ensure_utc(record.last_recalled)
        assert created is not None
        assert updated is not None

        rec_cat = getattr(record, "category", None)
        try:
            cat = MemoryCategory(rec_cat) if rec_cat else MemoryCategory.FACT
        except (ValueError, KeyError):
            cat = MemoryCategory.FACT

        rec_subj = getattr(record, "subject_entity", None)
        try:
            subj_entity = MemorySubjectEntity(rec_subj) if rec_subj else MemorySubjectEntity.USER
        except (ValueError, KeyError):
            subj_entity = MemorySubjectEntity.USER

        return Memory(
            id=record.id,
            category=cat,
            subject_entity=subj_entity,
            content=record.content,
            importance=record.importance,
            confidence=record.confidence,
            emotional_weight=record.emotional_weight,
            created_at=created,
            updated_at=updated,
            last_recalled=recalled,
            times_recalled=record.times_recalled,
            version=record.version,
        )


# Top-level convenience functions


async def create_memory(
    session: AsyncSession,
    category: MemoryCategory,
    content: str,
    importance: float = 0.5,
    confidence: float = 0.9,
    emotional_weight: float = 0.0,
    memory_id: str | None = None,
    subject_entity: MemorySubjectEntity | None = None,
) -> Memory:
    """Convenience function to create and persist a new long-term memory."""
    service = MemoryService(session)
    return await service.create_memory(
        category=category,
        content=content,
        importance=importance,
        confidence=confidence,
        emotional_weight=emotional_weight,
        memory_id=memory_id,
        subject_entity=subject_entity,
    )


async def get_memory(
    session: AsyncSession,
    memory_id: str,
) -> Memory | None:
    """Convenience function to retrieve a memory by ID."""
    service = MemoryService(session)
    return await service.get_memory(memory_id=memory_id)


async def list_memories(
    session: AsyncSession,
    category: MemoryCategory | None = None,
    subject_entity: MemorySubjectEntity | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Memory]:
    """Convenience function to list memories."""
    service = MemoryService(session)
    return await service.list_memories(
        category=category,
        subject_entity=subject_entity,
        limit=limit,
        offset=offset,
    )


async def update_memory(
    session: AsyncSession,
    memory_id: str,
    memory_update: MemoryUpdate,
    expected_version: int | None = None,
) -> Memory:
    """Convenience function to partially update a memory."""
    service = MemoryService(session)
    return await service.update_memory(
        memory_id=memory_id,
        memory_update=memory_update,
        expected_version=expected_version,
    )


async def recall_memory(
    session: AsyncSession,
    memory_id: str,
    expected_version: int | None = None,
) -> Memory:
    """Convenience function to record an explicit recall event."""
    service = MemoryService(session)
    return await service.recall_memory(
        memory_id=memory_id,
        expected_version=expected_version,
    )


async def delete_memory(
    session: AsyncSession,
    memory_id: str,
) -> bool:
    """Convenience function to delete a memory by ID."""
    service = MemoryService(session)
    return await service.delete_memory(memory_id=memory_id)
