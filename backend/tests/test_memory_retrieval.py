"""Unit and integration tests for Phase 3.5: Memory Retrieval Foundation.

Validates query validation, deterministic tokenization, lexical relevance scoring,
multi-signal ranking (relevance, importance, confidence, recency), deterministic tie-breaking,
Top-K limiting, category filtering, candidate exclusion, secret filtering,
and strict non-mutation of memory records.
"""

from datetime import datetime, timedelta, timezone
import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MemoryCandidateRecord, MemoryRecord, utc_now
from app.memory import (
    CONFIDENCE_WEIGHT,
    DEFAULT_STOP_WORDS,
    IMPORTANCE_WEIGHT,
    MAX_RETRIEVAL_LIMIT,
    MAX_RETRIEVAL_QUERY_LENGTH,
    MIN_RETRIEVAL_SCORE,
    RECENCY_HALF_LIFE_DAYS,
    RECENCY_WEIGHT,
    TEXT_RELEVANCE_WEIGHT,
    MemoryCategory,
    MemoryRetrievalQuery,
    MemoryRetrievalResult,
    MemoryRetrievalService,
    compute_recency_score,
    compute_text_relevance,
    create_memory,
    create_memory_candidate,
    get_memory,
    retrieve_memories,
    tokenize,
)


# =============================================================================
# 1. Query Validation Tests
# =============================================================================


def test_query_valid_instantiation() -> None:
    q = MemoryRetrievalQuery(text="software engineering", limit=5)
    assert q.text == "software engineering"
    assert q.categories == ()
    assert q.limit == 5


def test_query_rejects_empty_or_whitespace() -> None:
    with pytest.raises(ValidationError, match="must not be empty or whitespace"):
        MemoryRetrievalQuery(text="")

    with pytest.raises(ValidationError, match="must not be empty or whitespace"):
        MemoryRetrievalQuery(text="   \n\t  ")


def test_query_rejects_excessive_length() -> None:
    long_text = "a" * (MAX_RETRIEVAL_QUERY_LENGTH + 1)
    with pytest.raises(ValidationError, match="exceeds maximum length"):
        MemoryRetrievalQuery(text=long_text)


def test_query_rejects_invalid_limit() -> None:
    with pytest.raises(ValidationError):
        MemoryRetrievalQuery(text="valid text", limit=0)

    with pytest.raises(ValidationError):
        MemoryRetrievalQuery(text="valid text", limit=-1)

    with pytest.raises(ValidationError):
        MemoryRetrievalQuery(text="valid text", limit=MAX_RETRIEVAL_LIMIT + 1)


def test_query_is_immutable_and_forbids_extra_fields() -> None:
    q = MemoryRetrievalQuery(text="test query")
    with pytest.raises(ValidationError):
        q.text = "mutated"  # type: ignore[misc]

    with pytest.raises(ValidationError):
        MemoryRetrievalQuery(text="test", extra_field="unsupported")  # type: ignore[call-arg]


# =============================================================================
# 2. Tokenizer Unit Tests
# =============================================================================


def test_tokenize_normalization_and_punctuation() -> None:
    tokens = tokenize("Android, Kotlin! Rust.")
    assert "android" in tokens
    assert "kotlin" in tokens
    assert "rust" in tokens
    # Stop words or punctuation should not be separate tokens
    assert "!" not in tokens
    assert "." not in tokens


def test_tokenize_repeated_whitespace() -> None:
    tokens = tokenize("a    lot   of   spaces")
    assert tokens == ["lot", "spaces"]


def test_tokenize_unicode_support() -> None:
    tokens = tokenize("東京 Kyoto 東京")
    assert "東京" in tokens
    assert "kyoto" in tokens


def test_tokenize_all_stopwords_fallback() -> None:
    """When all tokens in query are stop words, falls back to unfiltered tokens."""
    tokens = tokenize("who is it")
    assert tokens == ["who", "is", "it"]


# =============================================================================
# 3. Text Relevance Scoring Unit Tests
# =============================================================================


def test_text_relevance_exact_overlap() -> None:
    score = compute_text_relevance("software engineering", "User studies Software Engineering.")
    assert score > 0.8  # Strong token overlap + exact phrase match


def test_text_relevance_partial_overlap() -> None:
    score_strong = compute_text_relevance("Kotlin Android project", "User is working on a Kotlin Android project.")
    score_weak = compute_text_relevance("Kotlin Android project", "User enjoys project management.")
    assert score_strong > score_weak
    assert score_weak > 0.0


def test_text_relevance_zero_overlap() -> None:
    score = compute_text_relevance("What should I eat tonight?", "User studies Software Engineering.")
    assert score == 0.0


def test_text_relevance_phrase_bonus() -> None:
    """Consecutive phrase match scores higher than scattered token matches."""
    score_phrase = compute_text_relevance(
        "machine learning",
        "User is reading a book about machine learning.",
    )
    score_scattered = compute_text_relevance(
        "machine learning",
        "User washed the machine and is learning Italian.",
    )
    assert score_phrase > score_scattered


# =============================================================================
# 4. Recency Scoring Unit Tests
# =============================================================================


def test_recency_score_decay() -> None:
    now = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)
    t_today = now
    t_30_days_ago = now - timedelta(days=30)
    t_90_days_ago = now - timedelta(days=90)

    r_today = compute_recency_score(t_today, None, now)
    r_30d = compute_recency_score(t_30_days_ago, None, now)
    r_90d = compute_recency_score(t_90_days_ago, None, now)

    assert pytest.approx(r_today, rel=1e-3) == 1.0
    assert pytest.approx(r_30d, rel=1e-2) == 0.5
    assert pytest.approx(r_90d, rel=1e-2) == 0.25
    assert r_today > r_30d > r_90d > 0.0


# =============================================================================
# 5. Service Integration Tests (Async DB)
# =============================================================================


@pytest.mark.asyncio
async def test_retrieve_memories_basic(test_session: AsyncSession) -> None:
    service = MemoryRetrievalService(test_session)

    m1 = await create_memory(
        session=test_session,
        category=MemoryCategory.FACT,
        content="User studies Software Engineering at university.",
        importance=0.8,
        confidence=0.95,
    )
    m2 = await create_memory(
        session=test_session,
        category=MemoryCategory.PREFERENCE,
        content="User enjoys building Android applications in Kotlin.",
        importance=0.7,
        confidence=0.95,
    )

    query = MemoryRetrievalQuery(text="Android applications", limit=5)
    result = await service.retrieve(query)

    assert result.returned_count == 1
    assert result.memories[0].memory.id == m2.id
    assert result.memories[0].score > 0.4
    assert result.memories[0].signals.text_relevance > 0.5


@pytest.mark.asyncio
async def test_ranking_prefers_higher_importance_and_confidence(test_session: AsyncSession) -> None:
    """When text relevance is identical, higher importance and confidence rank higher."""
    service = MemoryRetrievalService(test_session)

    m_low = await create_memory(
        session=test_session,
        category=MemoryCategory.FACT,
        content="User has a meeting with David tomorrow.",
        importance=0.3,
        confidence=0.7,
    )
    m_high = await create_memory(
        session=test_session,
        category=MemoryCategory.FACT,
        content="User has a meeting with David on Friday.",
        importance=0.9,
        confidence=0.95,
    )

    query = MemoryRetrievalQuery(text="meeting with David", limit=5)
    result = await service.retrieve(query)

    assert result.returned_count == 2
    assert result.memories[0].memory.id == m_high.id
    assert result.memories[1].memory.id == m_low.id
    assert result.memories[0].score > result.memories[1].score


@pytest.mark.asyncio
async def test_minimum_score_threshold_filters_irrelevant_memories(test_session: AsyncSession) -> None:
    service = MemoryRetrievalService(test_session)

    await create_memory(
        session=test_session,
        category=MemoryCategory.FACT,
        content="User lives in Kyoto.",
        importance=0.9,
        confidence=0.95,
    )

    query = MemoryRetrievalQuery(text="quantum mechanics physics", limit=5)
    result = await service.retrieve(query)

    assert result.returned_count == 0
    assert result.memories == ()


@pytest.mark.asyncio
async def test_top_k_limit_respected(test_session: AsyncSession) -> None:
    service = MemoryRetrievalService(test_session)

    for i in range(5):
        await create_memory(
            session=test_session,
            category=MemoryCategory.FACT,
            content=f"User loves reading science fiction novel number {i}.",
            importance=0.7,
            confidence=0.9,
        )

    query = MemoryRetrievalQuery(text="science fiction", limit=2)
    result = await service.retrieve(query)

    assert result.returned_count == 2
    assert len(result.memories) == 2


@pytest.mark.asyncio
async def test_category_filtering(test_session: AsyncSession) -> None:
    service = MemoryRetrievalService(test_session)

    m_fact = await create_memory(
        session=test_session,
        category=MemoryCategory.FACT,
        content="User works on Rust compiler tools.",
        importance=0.8,
        confidence=0.95,
    )
    m_pref = await create_memory(
        session=test_session,
        category=MemoryCategory.PREFERENCE,
        content="User prefers using Rust over C++.",
        importance=0.8,
        confidence=0.95,
    )

    # Filter to PREFERENCE only
    query = MemoryRetrievalQuery(
        text="Rust programming",
        categories=(MemoryCategory.PREFERENCE,),
        limit=5,
    )
    result = await service.retrieve(query)

    assert result.returned_count == 1
    assert result.memories[0].memory.id == m_pref.id


@pytest.mark.asyncio
async def test_candidate_exclusion(test_session: AsyncSession) -> None:
    """PENDING and REJECTED MemoryCandidates must NEVER be retrieved."""
    service = MemoryRetrievalService(test_session)

    # 1. Create a persistent Memory
    persisted = await create_memory(
        session=test_session,
        category=MemoryCategory.FACT,
        content="User is fluent in English and French.",
        importance=0.8,
        confidence=0.95,
    )

    # 2. Create PENDING and REJECTED candidates with similar content
    c_pending = await create_memory_candidate(
        session=test_session,
        category=MemoryCategory.FACT,
        content="User might speak French.",
        importance=0.9,
        confidence=0.95,
    )

    query = MemoryRetrievalQuery(text="French language", limit=10)
    result = await service.retrieve(query)

    assert result.returned_count == 1
    assert result.memories[0].memory.id == persisted.id
    # Ensure no candidate ID appears in results
    assert result.memories[0].memory.id != c_pending.id


@pytest.mark.asyncio
async def test_retrieval_does_not_mutate_memory(test_session: AsyncSession) -> None:
    """Retrieval must NOT modify last_recalled, times_recalled, updated_at, or version."""
    service = MemoryRetrievalService(test_session)

    initial_memory = await create_memory(
        session=test_session,
        category=MemoryCategory.FACT,
        content="User has two sisters named Alice and Emma.",
        importance=0.8,
        confidence=0.95,
    )
    assert initial_memory.times_recalled == 0
    assert initial_memory.last_recalled is None
    initial_version = initial_memory.version
    initial_updated_at = initial_memory.updated_at

    query = MemoryRetrievalQuery(text="Alice and Emma sisters", limit=5)
    result = await service.retrieve(query)
    assert result.returned_count == 1

    # Reload memory directly from DB
    reloaded = await get_memory(test_session, initial_memory.id)
    assert reloaded is not None
    assert reloaded.times_recalled == 0
    assert reloaded.last_recalled is None
    assert reloaded.version == initial_version
    assert reloaded.updated_at == initial_updated_at


@pytest.mark.asyncio
async def test_secret_filtering(test_session: AsyncSession) -> None:
    """Memories containing obvious credentials or tokens are excluded (defense-in-depth)."""
    service = MemoryRetrievalService(test_session)

    # Seed a memory that contains a secret
    rec = MemoryRecord(
        id="mem-secret-1",
        category=MemoryCategory.FACT.value,
        content="User's access token is ghp_1234567890abcdefghijklmnopqrstuvwxyz",
        importance=0.9,
        confidence=0.95,
        emotional_weight=0.0,
        created_at=utc_now(),
        updated_at=utc_now(),
        times_recalled=0,
        version=1,
    )
    test_session.add(rec)
    await test_session.commit()

    query = MemoryRetrievalQuery(text="access token", limit=5)
    result = await service.retrieve(query)
    assert result.returned_count == 0


@pytest.mark.asyncio
async def test_deterministic_tie_breaking(test_session: AsyncSession) -> None:
    """Tied memories must sort deterministically by id ascending."""
    service = MemoryRetrievalService(test_session)
    now = utc_now()

    # Create two memories with identical content, importance, confidence, created_at
    m_b = MemoryRecord(
        id="mem-uuid-b",
        category=MemoryCategory.FACT.value,
        content="User practices meditation every morning.",
        importance=0.8,
        confidence=0.9,
        emotional_weight=0.0,
        created_at=now,
        updated_at=now,
        times_recalled=0,
        version=1,
    )
    m_a = MemoryRecord(
        id="mem-uuid-a",
        category=MemoryCategory.FACT.value,
        content="User practices meditation every morning.",
        importance=0.8,
        confidence=0.9,
        emotional_weight=0.0,
        created_at=now,
        updated_at=now,
        times_recalled=0,
        version=1,
    )
    test_session.add(m_b)
    test_session.add(m_a)
    await test_session.commit()

    query = MemoryRetrievalQuery(text="meditation every morning", limit=5)
    result = await service.retrieve(query)

    assert result.returned_count == 2
    # Tie-breaker rule 5: memory ID ascending
    assert result.memories[0].memory.id == "mem-uuid-a"
    assert result.memories[1].memory.id == "mem-uuid-b"


@pytest.mark.asyncio
async def test_section_31_ranking_fixtures(test_session: AsyncSession) -> None:
    """Validate Section 31 ranking test fixtures."""
    service = MemoryRetrievalService(test_session)

    # Memory A
    mA = await create_memory(
        session=test_session,
        category=MemoryCategory.FACT,
        content="User is studying Software Engineering.",
        importance=0.8,
        confidence=0.95,
    )
    # Memory B
    mB = await create_memory(
        session=test_session,
        category=MemoryCategory.PREFERENCE,
        content="User enjoys building Android applications.",
        importance=0.7,
        confidence=0.95,
    )
    # Memory C
    mC = await create_memory(
        session=test_session,
        category=MemoryCategory.PREFERENCE,
        content="User dislikes crowded noisy gatherings.",
        importance=0.6,
        confidence=0.9,
    )
    # Memory D
    mD = await create_memory(
        session=test_session,
        category=MemoryCategory.USER_GOAL,
        content="User wants to learn penetration testing.",
        importance=0.9,
        confidence=0.95,
    )

    # Query 1: "Android development" -> B
    res_b = await service.retrieve(MemoryRetrievalQuery(text="Android development", limit=2))
    assert res_b.returned_count >= 1
    assert res_b.memories[0].memory.id == mB.id

    # Query 2: "Software Engineering course" -> A
    res_a = await service.retrieve(MemoryRetrievalQuery(text="Software Engineering course", limit=2))
    assert res_a.returned_count >= 1
    assert res_a.memories[0].memory.id == mA.id

    # Query 3: "crowded places" -> C
    res_c = await service.retrieve(MemoryRetrievalQuery(text="crowded places", limit=2))
    assert res_c.returned_count >= 1
    assert res_c.memories[0].memory.id == mC.id

    # Query 4: "penetration testing" -> D
    res_d = await service.retrieve(MemoryRetrievalQuery(text="penetration testing", limit=2))
    assert res_d.returned_count >= 1
    assert res_d.memories[0].memory.id == mD.id

    # Query 5: "banana recipes" -> empty
    res_empty = await service.retrieve(MemoryRetrievalQuery(text="banana recipes", limit=2))
    assert res_empty.returned_count == 0


@pytest.mark.asyncio
async def test_convenience_function(test_session: AsyncSession) -> None:
    await create_memory(
        session=test_session,
        category=MemoryCategory.FACT,
        content="User lives in Berlin.",
        importance=0.8,
        confidence=0.9,
    )

    query = MemoryRetrievalQuery(text="Berlin city", limit=5)
    res = await retrieve_memories(test_session, query)
    assert res.returned_count == 1
    assert res.memories[0].memory.content == "User lives in Berlin."


def test_no_llm_or_network_imports_in_retrieval_service() -> None:
    """Verify retrieval_service has zero LLM provider or external network dependencies."""
    import app.memory.retrieval_service as retrieval_mod

    with open(retrieval_mod.__file__, "r", encoding="utf-8") as f:
        content = f.read()

    forbidden_terms = [
        "app.llm",
        "httpx",
        "requests",
        "openai",
        "anthropic",
        "gemini",
        "google.genai",
        "aiohttp",
        "urllib",
        "faiss",
        "chroma",
    ]
    for term in forbidden_terms:
        assert term not in content, f"Forbidden external/LLM dependency in retrieval service: {term}"
