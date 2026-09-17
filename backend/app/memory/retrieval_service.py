"""Deterministic memory retrieval service for Aevum Core.

Retrieves a small, relevant subset of persistent Memory for the current conversational context
using deterministic lexical overlap, phrase detection, importance, confidence, and recency scoring.

Zero LLM calls, zero embeddings, zero vector databases, and zero network calls.
Retrieval does not mutate Memory records (does not update last_recalled or times_recalled).
"""

from datetime import datetime, timezone
import logging
import re
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MemoryRecord, utc_now
from app.memory.curation_policy import contains_obvious_credentials
from app.memory.models import (
    MAX_RETRIEVAL_LIMIT,
    MIN_RETRIEVAL_SCORE,
    Memory,
    MemoryCategory,
    MemoryRetrievalQuery,
    MemoryRetrievalResult,
    MemoryRetrievalSignals,
    MemorySubjectEntity,
    ScoredMemory,
)
from app.memory.service import _ensure_utc

logger = logging.getLogger(__name__)

# Scoring weights (sum to 1.0)
TEXT_RELEVANCE_WEIGHT: float = 0.55
IMPORTANCE_WEIGHT: float = 0.20
CONFIDENCE_WEIGHT: float = 0.15
RECENCY_WEIGHT: float = 0.10

# Recency decay half-life in days
RECENCY_HALF_LIFE_DAYS: float = 30.0

# Common English conversational stop words to filter noise while preserving content tokens
DEFAULT_STOP_WORDS: frozenset[str] = frozenset({
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "as", "at", "be", "because", "been", "before", "being", "below",
    "between", "both", "but", "by", "could", "did", "do", "does", "doing", "down",
    "during", "each", "few", "for", "from", "further", "had", "has", "have", "having",
    "he", "her", "here", "hers", "herself", "him", "himself", "his", "how", "i",
    "if", "in", "into", "is", "it", "its", "itself", "just", "me", "more", "most",
    "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or",
    "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same",
    "she", "should", "so", "some", "such", "than", "that", "the", "their", "theirs",
    "them", "themselves", "then", "there", "these", "they", "this", "those", "through",
    "to", "too", "under", "until", "up", "very", "was", "we", "were", "what", "when",
    "where", "which", "while", "who", "whom", "why", "with", "would", "you", "your",
    "yours", "yourself", "yourselves",
})


def tokenize(text: str, filter_stop_words: bool = True) -> list[str]:
    """Deterministically tokenize text into lowercase alphanumeric tokens.

    Supports Unicode word extraction via `(?u)\\b\\w+\\b`.
    If filter_stop_words is True and all tokens are stop words, falls back to unfiltered
    tokens to ensure short queries remain usable.
    """
    raw_tokens = re.findall(r"(?u)\b\w+\b", text.lower())
    if not filter_stop_words:
        return raw_tokens
    filtered = [t for t in raw_tokens if t not in DEFAULT_STOP_WORDS]
    return filtered if filtered else raw_tokens


def compute_text_relevance(query_text: str, memory_content: str) -> float:
    """Compute deterministic lexical relevance between query text and memory content.

    Returns a normalized float in [0.0, 1.0].
    - Evaluates token coverage: proportion of query tokens found in memory.
    - Evaluates phrase match bonus: exact phrase or multi-token n-gram overlap.
    - If no query tokens match, strictly returns 0.0.
    """
    q_tokens = tokenize(query_text, filter_stop_words=True)
    m_tokens = tokenize(memory_content, filter_stop_words=True)

    if not q_tokens or not m_tokens:
        return 0.0

    m_token_set = set(m_tokens)
    matched_tokens = sum(1 for t in q_tokens if t in m_token_set)
    if matched_tokens == 0:
        return 0.0

    # Token overlap: fraction of query tokens present in memory
    token_overlap = matched_tokens / len(q_tokens)

    # Phrase detection on normalized word sequences
    norm_query = " ".join(re.findall(r"(?u)\b\w+\b", query_text.lower()))
    norm_content = " ".join(re.findall(r"(?u)\b\w+\b", memory_content.lower()))

    phrase_bonus = 0.0
    if norm_query and norm_query in norm_content:
        phrase_bonus = 0.35
    elif len(q_tokens) >= 2:
        bigrams = [f"{q_tokens[i]} {q_tokens[i+1]}" for i in range(len(q_tokens) - 1)]
        matched_bigrams = sum(1 for bg in bigrams if bg in norm_content)
        phrase_bonus = (matched_bigrams / len(bigrams)) * 0.20

    raw_score = (token_overlap * 0.70) + phrase_bonus
    return min(1.0, max(0.0, raw_score))


def compute_recency_score(
    created_at: datetime | None,
    updated_at: datetime | None,
    now: datetime,
) -> float:
    """Compute deterministic recency score with smooth half-life decay.

    Uses the latest of (updated_at, created_at) as effective episodic memory timestamp.
    Decay formula: 1.0 / (1.0 + age_days / RECENCY_HALF_LIFE_DAYS).
    Guarantees a smooth score in (0.0, 1.0] that does not render older important memories invisible.
    """
    effective_dt = updated_at or created_at
    if effective_dt is None:
        return 0.5

    # Ensure UTC timezone alignment
    if effective_dt.tzinfo is None:
        effective_dt = effective_dt.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    diff_seconds = max(0.0, (now - effective_dt).total_seconds())
    age_days = diff_seconds / 86400.0
    return 1.0 / (1.0 + (age_days / RECENCY_HALF_LIFE_DAYS))


def _record_to_domain(record: MemoryRecord) -> Memory:
    """Convert a MemoryRecord into an immutable Memory domain model."""
    created = _ensure_utc(record.created_at)
    updated = _ensure_utc(record.updated_at)
    last_rec = _ensure_utc(record.last_recalled)
    assert created is not None
    assert updated is not None

    rec_subj = getattr(record, "subject_entity", None)
    try:
        subj_entity = MemorySubjectEntity(rec_subj) if rec_subj else MemorySubjectEntity.USER
    except (ValueError, KeyError):
        subj_entity = MemorySubjectEntity.USER

    return Memory(
        id=record.id,
        category=MemoryCategory(record.category),
        subject_entity=subj_entity,
        content=record.content,
        importance=record.importance,
        confidence=record.confidence,
        emotional_weight=record.emotional_weight,
        created_at=created,
        updated_at=updated,
        last_recalled=last_rec,
        times_recalled=record.times_recalled,
        version=record.version,
    )


def _retrieval_sort_key(sm: ScoredMemory) -> tuple[float, float, float, float, str]:
    """Deterministic tie-breaking sort key:

    1. final score descending
    2. importance descending
    3. confidence descending
    4. created_at descending
    5. memory ID ascending (alphabetical tie-breaker)
    """
    created_ts = sm.memory.created_at.timestamp() if sm.memory.created_at else 0.0
    return (
        -sm.score,
        -sm.memory.importance,
        -sm.memory.confidence,
        -created_ts,
        sm.memory.id,
    )


class MemoryRetrievalService:
    """Application-owned, deterministic memory retrieval service."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def retrieve(
        self,
        query: MemoryRetrievalQuery,
    ) -> MemoryRetrievalResult:
        """Retrieve a small, relevant subset of persistent memories.

        Guarantees:
        - Only queries `memories` table (never candidates).
        - Does NOT mutate Memory (does not modify last_recalled, times_recalled, or version).
        - Excludes memories containing credentials or secrets.
        - Excludes memories with zero lexical relevance.
        - Excludes memories scoring below MIN_RETRIEVAL_SCORE.
        - Limits returned results to query.limit (bounded by MAX_RETRIEVAL_LIMIT).
        - Deterministic sorting and tie-breaking.
        """
        now = utc_now()

        stmt = select(MemoryRecord)
        if query.categories:
            cat_values = [c.value if hasattr(c, "value") else str(c) for c in query.categories]
            stmt = stmt.where(MemoryRecord.category.in_(cat_values))
        if query.subject_entities:
            subj_values = [s.value if hasattr(s, "value") else str(s) for s in query.subject_entities]
            stmt = stmt.where(MemoryRecord.subject_entity.in_(subj_values))

        result = await self._session.scalars(stmt)
        records = result.all()
        total_candidates = len(records)

        scored_memories: list[ScoredMemory] = []

        for rec in records:
            # Defense-in-depth: exclude memories containing credentials
            if contains_obvious_credentials(rec.content):
                continue

            memory = _record_to_domain(rec)
            text_rel = compute_text_relevance(query.text, memory.content)

            # Zero relevance rule: memories with no lexical overlap are not returned
            if text_rel <= 0.0:
                continue

            recency = compute_recency_score(memory.created_at, memory.updated_at, now)
            signals = MemoryRetrievalSignals(
                text_relevance=round(text_rel, 4),
                importance=round(memory.importance, 4),
                confidence=round(memory.confidence, 4),
                recency=round(recency, 4),
            )

            # Final scoring formula
            final_score = (
                signals.text_relevance * TEXT_RELEVANCE_WEIGHT
                + signals.importance * IMPORTANCE_WEIGHT
                + signals.confidence * CONFIDENCE_WEIGHT
                + signals.recency * RECENCY_WEIGHT
            )
            final_score = round(final_score, 4)

            # Minimum score threshold
            if final_score < MIN_RETRIEVAL_SCORE:
                continue

            scored_memories.append(
                ScoredMemory(
                    memory=memory,
                    score=final_score,
                    signals=signals,
                )
            )

        # Sort deterministically
        scored_memories.sort(key=_retrieval_sort_key)

        # Slice to Top-K
        top_k = tuple(scored_memories[: query.limit])

        logger.debug(
            "Memory retrieval query evaluated. QueryLen=%d TotalCandidates=%d Returned=%d",
            len(query.text),
            total_candidates,
            len(top_k),
        )

        return MemoryRetrievalResult(
            query=query,
            memories=top_k,
            total_candidates=total_candidates,
            returned_count=len(top_k),
        )


async def retrieve_memories(
    session: AsyncSession,
    query: MemoryRetrievalQuery,
) -> MemoryRetrievalResult:
    """Convenience function to perform deterministic memory retrieval."""
    service = MemoryRetrievalService(session)
    return await service.retrieve(query)
