"""Hybrid memory retrieval service for Aevum Core.

Combines deterministic lexical retrieval (Phase 3.5) with semantic vector retrieval (Phase 3.6)
into a unified, deduplicated, and ranked memory result set.

Guarantees:
- Zero mutations to Memory records (does not update last_recalled, times_recalled, or version).
- Failure isolation: if semantic embedding fails or embedding provider is unavailable,
  transparently falls back to lexical-only retrieval without throwing errors.
- Deterministic multi-tier tie-breaking:
  1. hybrid_score descending
  2. lexical_score descending
  3. semantic_score descending
  4. importance descending
  5. confidence descending
  6. created_at descending
  7. memory id ascending (alphabetical tie-breaker)
- Strict deduplication by persistent Memory ID.
"""

from collections.abc import Sequence
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.embedding_provider import EmbeddingError, EmbeddingProvider
from app.memory.models import (
    MAX_RETRIEVAL_LIMIT,
    HybridMemoryResult,
    HybridMemoryRetrievalQuery,
    HybridMemoryRetrievalResult,
    Memory,
    MemoryRetrievalQuery,
    SemanticMemoryRetrievalQuery,
)
from app.memory.retrieval_service import MemoryRetrievalService
from app.memory.semantic_retrieval_service import SemanticMemoryRetrievalService

logger = logging.getLogger(__name__)


def _hybrid_sort_key(res: HybridMemoryResult) -> tuple[float, float, float, float, float, float, str]:
    """Deterministic tie-breaking sort key:

    1. hybrid_score descending
    2. lexical_score descending
    3. semantic_score descending
    4. importance descending
    5. confidence descending
    6. created_at descending
    7. memory ID ascending (alphabetical tie-breaker)
    """
    created_ts = res.memory.created_at.timestamp() if res.memory.created_at else 0.0
    return (
        -res.hybrid_score,
        -res.lexical_score,
        -res.semantic_score,
        -res.memory.importance,
        -res.memory.confidence,
        -created_ts,
        res.memory.id,
    )


class HybridMemoryRetrievalService:
    """Service orchestrating hybrid lexical and semantic memory retrieval."""

    def __init__(
        self,
        session: AsyncSession,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self._session = session
        self._embedding_provider = embedding_provider
        self._lexical_service = MemoryRetrievalService(session=session)
        self._semantic_service = (
            SemanticMemoryRetrievalService(session=session, provider=embedding_provider)
            if embedding_provider is not None
            else None
        )

    @property
    def embedding_provider(self) -> EmbeddingProvider | None:
        return self._embedding_provider

    async def retrieve(
        self,
        query: HybridMemoryRetrievalQuery,
    ) -> HybridMemoryRetrievalResult:
        """Perform hybrid retrieval combining lexical and semantic candidates.

        Steps:
        1. Fetch candidate pool: lexical and semantic retrieved with 2x limit (capped at MAX_RETRIEVAL_LIMIT).
        2. If semantic retrieval is unavailable or fails, fall back gracefully to lexical candidates.
        3. Deduplicate candidates by Memory ID.
        4. Calculate hybrid_score = (lexical_score * lexical_weight) + (semantic_score * semantic_weight).
        5. Apply deterministic multi-tier tie-breaking.
        6. Truncate to query.limit and return immutable result.
        """
        candidate_limit = min(MAX_RETRIEVAL_LIMIT, query.limit * 2)
        semantic_fallback_triggered = False

        # 1. Lexical retrieval
        lexical_query = MemoryRetrievalQuery(
            text=query.text,
            categories=query.categories,
            limit=candidate_limit,
        )
        lexical_res = await self._lexical_service.retrieve(lexical_query)

        # 2. Semantic retrieval (with graceful fallback)
        semantic_candidates: dict[str, tuple[Memory, float]] = {}
        if self._semantic_service is not None:
            try:
                semantic_query = SemanticMemoryRetrievalQuery(
                    text=query.text,
                    categories=query.categories,
                    limit=candidate_limit,
                    min_similarity=query.min_similarity,
                )
                semantic_res = await self._semantic_service.retrieve(semantic_query)
                for item in semantic_res.memories:
                    semantic_candidates[item.memory.id] = (item.memory, item.similarity)
            except (EmbeddingError, Exception) as exc:
                logger.warning("Semantic memory retrieval failed; falling back to lexical-only: %s", exc)
                semantic_fallback_triggered = True
        else:
            semantic_fallback_triggered = True

        # 3. Deduplicate and collect candidate memories
        # Map: memory_id -> (Memory, lexical_score, semantic_score)
        all_candidates: dict[str, tuple[Memory, float, float]] = {}

        for scored_mem in lexical_res.memories:
            mem_id = scored_mem.memory.id
            all_candidates[mem_id] = (scored_mem.memory, scored_mem.score, 0.0)

        for mem_id, (mem, sem_score) in semantic_candidates.items():
            if mem_id in all_candidates:
                mem, lex_score, _ = all_candidates[mem_id]
                all_candidates[mem_id] = (mem, lex_score, sem_score)
            else:
                all_candidates[mem_id] = (mem, 0.0, sem_score)

        # 4. Compute hybrid scores
        scored_results: list[HybridMemoryResult] = []
        for mem_id, (mem, lex_score, sem_score) in all_candidates.items():
            hybrid_score = (lex_score * query.lexical_weight) + (sem_score * query.semantic_weight)
            scored_results.append(
                HybridMemoryResult(
                    memory=mem,
                    hybrid_score=round(hybrid_score, 6),
                    lexical_score=round(lex_score, 6),
                    semantic_score=round(sem_score, 6),
                )
            )

        # 5. Deterministic sorting
        scored_results.sort(key=_hybrid_sort_key)

        # 6. Slice to requested limit
        top_results = scored_results[: query.limit]

        return HybridMemoryRetrievalResult(
            query=query,
            memories=tuple(top_results),
            total_candidates=len(all_candidates),
            returned_count=len(top_results),
            semantic_fallback_triggered=semantic_fallback_triggered,
        )


async def retrieve_hybrid_memories(
    session: AsyncSession,
    text: str,
    limit: int = 5,
    embedding_provider: EmbeddingProvider | None = None,
) -> HybridMemoryRetrievalResult:
    """Convenience helper for hybrid memory retrieval."""
    service = HybridMemoryRetrievalService(session=session, embedding_provider=embedding_provider)
    query = HybridMemoryRetrievalQuery(text=text, limit=limit)
    return await service.retrieve(query)
