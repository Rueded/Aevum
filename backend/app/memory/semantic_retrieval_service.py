"""Semantic memory retrieval service for Aevum Core.

Retrieves persistent memories using cosine similarity against pre-computed vector embeddings.
Isolates semantic retrieval from lexical retrieval (Phase 3.5), Character Engine, and LLM chat.

Guarantees:
- Zero mutations to Memory records during retrieval.
- Only one embedding request per query (for query.text); stored memories are not re-embedded during retrieval.
- Excludes candidates, credentials/secrets, stale embeddings, and incompatible models/dimensions.
"""

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MemoryEmbeddingRecord, MemoryRecord
from app.memory.curation_policy import contains_obvious_credentials
from app.memory.embedding_provider import EmbeddingProvider, compute_cosine_similarity
from app.memory.embedding_service import deserialize_vector
from app.memory.models import (
    Memory,
    MemoryCategory,
    SemanticMemoryResult,
    SemanticMemoryRetrievalQuery,
    SemanticMemoryRetrievalResult,
)
from app.memory.retrieval_service import _record_to_domain

logger = logging.getLogger(__name__)


def _semantic_sort_key(res: SemanticMemoryResult) -> tuple[float, float, float, float, str]:
    """Deterministic tie-breaking sort key:

    1. similarity descending
    2. importance descending
    3. confidence descending
    4. created_at descending
    5. memory ID ascending (alphabetical tie-breaker)
    """
    created_ts = res.memory.created_at.timestamp() if res.memory.created_at else 0.0
    return (
        -res.similarity,
        -res.memory.importance,
        -res.memory.confidence,
        -created_ts,
        res.memory.id,
    )


class SemanticMemoryRetrievalService:
    """Service managing semantic memory retrieval using vector cosine similarity."""

    def __init__(self, session: AsyncSession, provider: EmbeddingProvider) -> None:
        self._session = session
        self._provider = provider

    @property
    def provider(self) -> EmbeddingProvider:
        return self._provider

    async def retrieve(
        self,
        query: SemanticMemoryRetrievalQuery,
    ) -> SemanticMemoryRetrievalResult:
        """Retrieve memories by cosine similarity with the query vector.

        Guarantees:
        - Read-only against memories (does not update last_recalled, times_recalled, or version).
        - Skips memories without embeddings or with stale embeddings.
        - Excludes memories with credentials/secrets.
        - Enforces query.min_similarity.
        - Sorts deterministically.
        """
        # 1. Generate query vector (single network/embedding call)
        query_emb = await self._provider.embed_text(query.text)

        # 2. Query persistent memories joined with compatible embeddings
        stmt = (
            select(MemoryRecord, MemoryEmbeddingRecord)
            .join(MemoryEmbeddingRecord, MemoryRecord.id == MemoryEmbeddingRecord.memory_id)
            .where(
                MemoryEmbeddingRecord.model == query_emb.model,
                MemoryEmbeddingRecord.dimensions == query_emb.dimensions,
            )
        )
        if query.categories:
            cat_values = [c.value if hasattr(c, "value") else str(c) for c in query.categories]
            stmt = stmt.where(MemoryRecord.category.in_(cat_values))
        if query.subject_entities:
            subj_values = [s.value if hasattr(s, "value") else str(s) for s in query.subject_entities]
            stmt = stmt.where(MemoryRecord.subject_entity.in_(subj_values))

        rows = (await self._session.execute(stmt)).all()
        total_candidates = len(rows)

        scored_results: list[SemanticMemoryResult] = []

        for mem_rec, emb_rec in rows:
            # Stale embedding check: if memory was updated after embedding, exclude it
            if mem_rec.updated_at > emb_rec.updated_at:
                logger.debug(
                    "Skipping memory %s due to stale embedding (mem_updated=%s > emb_updated=%s)",
                    mem_rec.id,
                    mem_rec.updated_at,
                    emb_rec.updated_at,
                )
                continue

            # Defense-in-depth: secret filtering
            if contains_obvious_credentials(mem_rec.content):
                continue

            # Deserialize stored vector safely
            try:
                stored_vec = deserialize_vector(
                    emb_rec.vector_json,
                    expected_dimensions=query_emb.dimensions,
                )
            except Exception as e:
                logger.warning("Failed to deserialize embedding for memory %s: %e", mem_rec.id, e)
                continue

            sim = compute_cosine_similarity(query_emb.vector, stored_vec)
            sim_rounded = round(sim, 4)

            # Minimum similarity threshold
            if sim_rounded < query.min_similarity:
                continue

            memory = _record_to_domain(mem_rec)
            scored_results.append(
                SemanticMemoryResult(
                    memory=memory,
                    similarity=sim_rounded,
                )
            )

        # Sort deterministically
        scored_results.sort(key=_semantic_sort_key)

        # Slice to Top-K
        top_k = tuple(scored_results[: query.limit])

        logger.debug(
            "Semantic memory retrieval completed. QueryLen=%d Candidates=%d Returned=%d",
            len(query.text),
            total_candidates,
            len(top_k),
        )

        return SemanticMemoryRetrievalResult(
            query=query,
            memories=top_k,
            total_candidates=total_candidates,
            returned_count=len(top_k),
        )


async def retrieve_semantic_memories(
    session: AsyncSession,
    provider: EmbeddingProvider,
    query: SemanticMemoryRetrievalQuery,
) -> SemanticMemoryRetrievalResult:
    """Convenience function to perform semantic memory retrieval."""
    service = SemanticMemoryRetrievalService(session, provider)
    return await service.retrieve(query)
