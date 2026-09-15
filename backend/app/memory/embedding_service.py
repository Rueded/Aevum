"""Memory embedding service for Aevum Core.

Manages the explicit creation, retrieval, and deletion of vector embeddings for persistent Memory records.
Decouples embedding generation from memory persistence to ensure network/provider failures
do not compromise memory storage or state.
"""

from datetime import datetime, timezone
import json
import logging
import uuid
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MemoryEmbeddingRecord, MemoryRecord, utc_now
from app.memory.embedding_provider import EmbeddingProvider
from app.memory.models import MemoryEmbedding
from app.memory.service import MemoryNotFoundError, _ensure_utc

logger = logging.getLogger(__name__)


def serialize_vector(vector: tuple[float, ...]) -> str:
    """Serialize a float tuple into a JSON string."""
    return json.dumps(list(vector))


def deserialize_vector(vector_json: str, expected_dimensions: int | None = None) -> tuple[float, ...]:
    """Safely deserialize a JSON string into a validated tuple of finite floats."""
    try:
        raw = json.loads(vector_json)
    except Exception as e:
        raise ValueError(f"Malformed vector JSON: {e}") from e

    if not isinstance(raw, list) or not raw:
        raise ValueError("Deserialized vector must be a non-empty list of numbers.")

    parsed: list[float] = []
    for idx, v in enumerate(raw):
        if not isinstance(v, (int, float)):
            raise ValueError(f"Vector element at index {idx} is not a numeric float.")
        val = float(v)
        parsed.append(val)

    if expected_dimensions is not None and len(parsed) != expected_dimensions:
        raise ValueError(
            f"Deserialized vector dimension {len(parsed)} does not match expected {expected_dimensions}."
        )

    return tuple(parsed)


class MemoryEmbeddingService:
    """Service managing memory vector embeddings."""

    def __init__(self, session: AsyncSession, provider: EmbeddingProvider) -> None:
        self._session = session
        self._provider = provider

    @property
    def provider(self) -> EmbeddingProvider:
        return self._provider

    async def embed_memory(self, memory_id: str) -> MemoryEmbedding:
        """Generate and persist an embedding for an existing persistent memory.

        Raises MemoryNotFoundError if the memory does not exist.
        If an embedding already exists for this memory and model, updates it in-place.
        """
        mem_stmt = select(MemoryRecord).where(MemoryRecord.id == memory_id)
        mem_rec = (await self._session.scalars(mem_stmt)).first()
        if mem_rec is None:
            raise MemoryNotFoundError(memory_id)

        # Call provider (may perform network call)
        emb_result = await self._provider.embed_text(mem_rec.content)
        vector_str = serialize_vector(emb_result.vector)
        now = utc_now()

        # Check for existing embedding record for this memory and model
        existing_stmt = select(MemoryEmbeddingRecord).where(
            MemoryEmbeddingRecord.memory_id == memory_id,
            MemoryEmbeddingRecord.model == emb_result.model,
        )
        existing_rec = (await self._session.scalars(existing_stmt)).first()

        if existing_rec is not None:
            existing_rec.vector_json = vector_str
            existing_rec.dimensions = emb_result.dimensions
            existing_rec.provider = self._provider.provider_name
            existing_rec.updated_at = now
            existing_rec.version += 1
            record = existing_rec
        else:
            record = MemoryEmbeddingRecord(
                id=str(uuid.uuid4()),
                memory_id=memory_id,
                provider=self._provider.provider_name,
                model=emb_result.model,
                dimensions=emb_result.dimensions,
                vector_json=vector_str,
                created_at=now,
                updated_at=now,
                version=1,
            )
            self._session.add(record)

        await self._session.commit()
        return self._record_to_domain(record)

    async def get_embedding(
        self,
        memory_id: str,
        model: str | None = None,
    ) -> MemoryEmbedding | None:
        """Retrieve an existing embedding for a memory, optionally filtered by model name."""
        stmt = select(MemoryEmbeddingRecord).where(MemoryEmbeddingRecord.memory_id == memory_id)
        if model is not None:
            stmt = stmt.where(MemoryEmbeddingRecord.model == model)
        else:
            stmt = stmt.where(MemoryEmbeddingRecord.model == self._provider.model_name)

        record = (await self._session.scalars(stmt)).first()
        if record is None:
            return None
        return self._record_to_domain(record)

    async def delete_embedding(
        self,
        memory_id: str,
        model: str | None = None,
    ) -> bool:
        """Delete an embedding for a memory. Returns True if deleted, False otherwise."""
        stmt = delete(MemoryEmbeddingRecord).where(MemoryEmbeddingRecord.memory_id == memory_id)
        if model is not None:
            stmt = stmt.where(MemoryEmbeddingRecord.model == model)
        else:
            stmt = stmt.where(MemoryEmbeddingRecord.model == self._provider.model_name)

        res = await self._session.execute(stmt)
        await self._session.commit()
        return bool(res.rowcount > 0)

    def _record_to_domain(self, record: MemoryEmbeddingRecord) -> MemoryEmbedding:
        """Convert a MemoryEmbeddingRecord into an immutable MemoryEmbedding domain model."""
        created = _ensure_utc(record.created_at)
        updated = _ensure_utc(record.updated_at)
        assert created is not None
        assert updated is not None

        vector = deserialize_vector(record.vector_json, expected_dimensions=record.dimensions)

        return MemoryEmbedding(
            id=record.id,
            memory_id=record.memory_id,
            provider=record.provider,
            model=record.model,
            dimensions=record.dimensions,
            vector=vector,
            created_at=created,
            updated_at=updated,
            version=record.version,
        )


async def embed_memory(
    session: AsyncSession,
    provider: EmbeddingProvider,
    memory_id: str,
) -> MemoryEmbedding:
    """Convenience function to generate and persist a memory embedding."""
    service = MemoryEmbeddingService(session, provider)
    return await service.embed_memory(memory_id)


async def get_memory_embedding(
    session: AsyncSession,
    provider: EmbeddingProvider,
    memory_id: str,
    model: str | None = None,
) -> MemoryEmbedding | None:
    """Convenience function to retrieve a memory embedding."""
    service = MemoryEmbeddingService(session, provider)
    return await service.get_embedding(memory_id, model=model)


async def delete_memory_embedding(
    session: AsyncSession,
    provider: EmbeddingProvider,
    memory_id: str,
    model: str | None = None,
) -> bool:
    """Convenience function to delete a memory embedding."""
    service = MemoryEmbeddingService(session, provider)
    return await service.delete_embedding(memory_id, model=model)
