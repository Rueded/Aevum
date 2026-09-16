"""Unit and integration tests for Phase 3.6: Semantic Memory Retrieval Foundation.

Validates embedding domain models, serialization, cosine similarity, FakeEmbeddingProvider,
MemoryEmbeddingService, SemanticMemoryRetrievalService, stale embedding filtering,
model/dimension mismatch protection, candidate exclusion, secret filtering,
deterministic tie-breaking, and non-mutation guarantees.
"""

from datetime import datetime, timedelta, timezone
import math
import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, settings
from app.db.models import MemoryCandidateRecord, MemoryEmbeddingRecord, MemoryRecord, utc_now
from app.memory import (
    MAX_RETRIEVAL_LIMIT,
    MAX_RETRIEVAL_QUERY_LENGTH,
    MIN_SEMANTIC_SIMILARITY,
    EmbeddingError,
    EmbeddingGenerationError,
    EmbeddingProviderNotConfiguredError,
    EmbeddingResult,
    FakeEmbeddingProvider,
    GeminiEmbeddingProvider,
    MemoryCategory,
    MemoryEmbedding,
    MemoryEmbeddingService,
    MemoryNotFoundError,
    SemanticMemoryResult,
    SemanticMemoryRetrievalQuery,
    SemanticMemoryRetrievalResult,
    SemanticMemoryRetrievalService,
    compute_cosine_similarity,
    create_memory,
    create_memory_candidate,
    delete_memory_embedding,
    deserialize_vector,
    embed_memory,
    get_memory,
    get_memory_embedding,
    retrieve_semantic_memories,
    serialize_vector,
)


# =============================================================================
# 1. Embedding Domain Model Tests
# =============================================================================


def test_embedding_result_valid() -> None:
    res = EmbeddingResult(
        vector=(0.1, 0.2, 0.3),
        model="text-embedding-004",
        dimensions=3,
        provider="gemini",
    )
    assert res.vector == (0.1, 0.2, 0.3)
    assert res.dimensions == 3
    assert res.model == "text-embedding-004"


def test_embedding_result_rejects_empty_vector() -> None:
    with pytest.raises(ValidationError, match="must not be empty"):
        EmbeddingResult(
            vector=(),
            model="text-embedding-004",
            dimensions=0,
            provider="gemini",
        )


def test_embedding_result_rejects_nan_and_inf() -> None:
    with pytest.raises(ValidationError, match="must not be NaN"):
        EmbeddingResult(
            vector=(0.1, float("nan"), 0.3),
            model="text-embedding-004",
            dimensions=3,
            provider="gemini",
        )

    with pytest.raises(ValidationError, match="must not be infinite"):
        EmbeddingResult(
            vector=(0.1, float("inf"), 0.3),
            model="text-embedding-004",
            dimensions=3,
            provider="gemini",
        )


def test_embedding_result_dimensions_mismatch() -> None:
    with pytest.raises(ValidationError, match="does not match vector length"):
        EmbeddingResult(
            vector=(0.1, 0.2, 0.3),
            model="test-model",
            dimensions=5,
            provider="test",
        )


def test_embedding_result_immutable_and_extra_forbidden() -> None:
    res = EmbeddingResult(vector=(1.0,), model="m", dimensions=1, provider="p")
    with pytest.raises(ValidationError):
        res.vector = (2.0,)  # type: ignore[misc]

    with pytest.raises(ValidationError):
        EmbeddingResult(vector=(1.0,), model="m", dimensions=1, provider="p", extra_field=123)  # type: ignore[call-arg]


# =============================================================================
# 2. Serialization & Deserialization Tests
# =============================================================================


def test_vector_serialization_round_trip() -> None:
    vec = (0.123456, -0.654321, 0.0, 1.0)
    serialized = serialize_vector(vec)
    assert isinstance(serialized, str)

    deserialized = deserialize_vector(serialized, expected_dimensions=4)
    assert pytest.approx(deserialized[0], rel=1e-5) == 0.123456
    assert pytest.approx(deserialized[1], rel=1e-5) == -0.654321
    assert deserialized[2] == 0.0
    assert deserialized[3] == 1.0


def test_deserialize_vector_validation_errors() -> None:
    with pytest.raises(ValueError, match="Malformed vector JSON"):
        deserialize_vector("invalid-json")

    with pytest.raises(ValueError, match="non-empty list"):
        deserialize_vector("[]")

    with pytest.raises(ValueError, match="not a numeric float"):
        deserialize_vector('["not", "numbers"]')

    with pytest.raises(ValueError, match="does not match expected"):
        deserialize_vector("[1.0, 2.0]", expected_dimensions=3)


# =============================================================================
# 3. Cosine Similarity Tests
# =============================================================================


def test_cosine_similarity_identical() -> None:
    v1 = (0.5, 0.5, 0.5, 0.5)
    sim = compute_cosine_similarity(v1, v1)
    assert pytest.approx(sim, abs=1e-5) == 1.0


def test_cosine_similarity_orthogonal() -> None:
    v1 = (1.0, 0.0)
    v2 = (0.0, 1.0)
    sim = compute_cosine_similarity(v1, v2)
    assert pytest.approx(sim, abs=1e-5) == 0.0


def test_cosine_similarity_opposite() -> None:
    v1 = (1.0, 0.0)
    v2 = (-1.0, 0.0)
    sim = compute_cosine_similarity(v1, v2)
    assert pytest.approx(sim, abs=1e-5) == -1.0


def test_cosine_similarity_zero_vector() -> None:
    v1 = (0.0, 0.0)
    v2 = (1.0, 2.0)
    sim = compute_cosine_similarity(v1, v2)
    assert sim == 0.0


def test_cosine_similarity_dimension_mismatch() -> None:
    with pytest.raises(ValueError, match="dimension mismatch"):
        compute_cosine_similarity((1.0, 2.0), (1.0, 2.0, 3.0))


def test_cosine_similarity_nan_rejection() -> None:
    with pytest.raises(ValueError, match="must not be NaN"):
        compute_cosine_similarity((1.0, float("nan")), (1.0, 2.0))


# =============================================================================
# 4. FakeEmbeddingProvider Tests
# =============================================================================


@pytest.mark.asyncio
async def test_fake_embedding_provider_deterministic() -> None:
    provider = FakeEmbeddingProvider(dimensions=8)
    res1 = await provider.embed_text("Software Engineering in Python")
    res2 = await provider.embed_text("Software Engineering in Python")

    assert res1.vector == res2.vector
    assert res1.dimensions == 8
    assert res1.model == "fake-embedding-v1"
    assert res1.provider == "fake"


@pytest.mark.asyncio
async def test_fake_embedding_provider_similar_vs_dissimilar() -> None:
    provider = FakeEmbeddingProvider(dimensions=16)
    res_base = await provider.embed_text("Python software development")
    res_similar = await provider.embed_text("Software development with Python language")
    res_dissimilar = await provider.embed_text("Baking sourdough bread in the kitchen")

    sim_similar = compute_cosine_similarity(res_base.vector, res_similar.vector)
    sim_dissimilar = compute_cosine_similarity(res_base.vector, res_dissimilar.vector)

    assert sim_similar > sim_dissimilar
    assert sim_similar > 0.4


@pytest.mark.asyncio
async def test_fake_embedding_provider_rejects_empty() -> None:
    provider = FakeEmbeddingProvider(dimensions=8)
    with pytest.raises(ValueError, match="must not be empty"):
        await provider.embed_text("   ")


# =============================================================================
# 5. Semantic Query Model Tests
# =============================================================================


def test_semantic_query_valid() -> None:
    q = SemanticMemoryRetrievalQuery(
        text="machine learning algorithms",
        categories=(MemoryCategory.FACT,),
        limit=3,
        min_similarity=0.60,
    )
    assert q.text == "machine learning algorithms"
    assert q.categories == (MemoryCategory.FACT,)
    assert q.limit == 3
    assert q.min_similarity == 0.60


def test_semantic_query_rejects_empty_and_excessive() -> None:
    with pytest.raises(ValidationError, match="must not be empty"):
        SemanticMemoryRetrievalQuery(text="")

    with pytest.raises(ValidationError, match="exceeds maximum length"):
        SemanticMemoryRetrievalQuery(text="a" * (MAX_RETRIEVAL_QUERY_LENGTH + 1))

    with pytest.raises(ValidationError):
        SemanticMemoryRetrievalQuery(text="test", limit=0)

    with pytest.raises(ValidationError):
        SemanticMemoryRetrievalQuery(text="test", limit=MAX_RETRIEVAL_LIMIT + 1)


# =============================================================================
# 6. MemoryEmbeddingService Tests (DB Integration)
# =============================================================================


@pytest.mark.asyncio
async def test_embed_memory_persists_embedding(test_session: AsyncSession) -> None:
    provider = FakeEmbeddingProvider(dimensions=8)
    service = MemoryEmbeddingService(test_session, provider)

    mem = await create_memory(
        session=test_session,
        category=MemoryCategory.FACT,
        content="User lives in Kyoto and enjoys green tea.",
        importance=0.8,
        confidence=0.95,
    )

    emb = await service.embed_memory(mem.id)
    assert emb.memory_id == mem.id
    assert emb.dimensions == 8
    assert emb.model == provider.model_name
    assert len(emb.vector) == 8
    assert emb.version == 1

    # Reload from DB
    loaded = await service.get_embedding(mem.id)
    assert loaded is not None
    assert loaded.id == emb.id
    assert loaded.vector == emb.vector


@pytest.mark.asyncio
async def test_embed_memory_updates_existing_embedding(test_session: AsyncSession) -> None:
    provider = FakeEmbeddingProvider(dimensions=8)
    service = MemoryEmbeddingService(test_session, provider)

    mem = await create_memory(
        session=test_session,
        category=MemoryCategory.FACT,
        content="Original fact.",
    )
    emb1 = await service.embed_memory(mem.id)
    assert emb1.version == 1

    emb2 = await service.embed_memory(mem.id)
    assert emb2.id == emb1.id
    assert emb2.version == 2


@pytest.mark.asyncio
async def test_embed_memory_not_found(test_session: AsyncSession) -> None:
    provider = FakeEmbeddingProvider(dimensions=8)
    service = MemoryEmbeddingService(test_session, provider)
    with pytest.raises(MemoryNotFoundError):
        await service.embed_memory("nonexistent-memory-id")


@pytest.mark.asyncio
async def test_delete_embedding(test_session: AsyncSession) -> None:
    provider = FakeEmbeddingProvider(dimensions=8)
    service = MemoryEmbeddingService(test_session, provider)

    mem = await create_memory(session=test_session, category=MemoryCategory.FACT, content="To be deleted.")
    await service.embed_memory(mem.id)

    deleted = await service.delete_embedding(mem.id)
    assert deleted is True

    loaded = await service.get_embedding(mem.id)
    assert loaded is None


# =============================================================================
# 7. SemanticMemoryRetrievalService Integration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_semantic_retrieval_ranking(test_session: AsyncSession) -> None:
    provider = FakeEmbeddingProvider(dimensions=16)
    emb_service = MemoryEmbeddingService(test_session, provider)
    retrieval_service = SemanticMemoryRetrievalService(test_session, provider)

    m1 = await create_memory(
        session=test_session,
        category=MemoryCategory.FACT,
        content="User loves building Android applications in Kotlin.",
        importance=0.8,
        confidence=0.95,
    )
    m2 = await create_memory(
        session=test_session,
        category=MemoryCategory.PREFERENCE,
        content="User prefers drinking espresso in the morning.",
        importance=0.6,
        confidence=0.90,
    )

    await emb_service.embed_memory(m1.id)
    await emb_service.embed_memory(m2.id)

    query = SemanticMemoryRetrievalQuery(
        text="Kotlin Android mobile development",
        limit=5,
        min_similarity=0.20,
    )
    result = await retrieval_service.retrieve(query)

    assert result.returned_count >= 1
    assert result.memories[0].memory.id == m1.id
    assert result.memories[0].similarity > 0.30


@pytest.mark.asyncio
async def test_semantic_retrieval_skips_unembedded_memories(test_session: AsyncSession) -> None:
    provider = FakeEmbeddingProvider(dimensions=8)
    retrieval_service = SemanticMemoryRetrievalService(test_session, provider)

    # Create memory but do NOT generate embedding
    await create_memory(
        session=test_session,
        category=MemoryCategory.FACT,
        content="Unembedded memory content.",
    )

    query = SemanticMemoryRetrievalQuery(text="Unembedded memory content", min_similarity=0.10)
    result = await retrieval_service.retrieve(query)

    assert result.returned_count == 0


@pytest.mark.asyncio
async def test_semantic_retrieval_excludes_stale_embeddings(test_session: AsyncSession) -> None:
    """When a Memory is updated after its embedding was created, it is excluded as stale."""
    provider = FakeEmbeddingProvider(dimensions=8)
    emb_service = MemoryEmbeddingService(test_session, provider)
    retrieval_service = SemanticMemoryRetrievalService(test_session, provider)

    now = utc_now()
    # Create memory
    mem_rec = MemoryRecord(
        id="mem-stale-test",
        category=MemoryCategory.FACT.value,
        content="Stale memory test fact.",
        importance=0.8,
        confidence=0.9,
        emotional_weight=0.0,
        created_at=now,
        updated_at=now + timedelta(seconds=10),  # Memory updated LATER than embedding
        times_recalled=0,
        version=2,
    )
    # Create embedding with EARLIER updated_at
    emb_rec = MemoryEmbeddingRecord(
        id="emb-stale-test",
        memory_id="mem-stale-test",
        provider=provider.provider_name,
        model=provider.model_name,
        dimensions=8,
        vector_json=serialize_vector((1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)),
        created_at=now,
        updated_at=now,  # Earlier than memory updated_at
        version=1,
    )
    test_session.add(mem_rec)
    test_session.add(emb_rec)
    await test_session.commit()

    query = SemanticMemoryRetrievalQuery(text="Stale memory test fact", min_similarity=0.0)
    result = await retrieval_service.retrieve(query)

    # Should be excluded because mem_rec.updated_at > emb_rec.updated_at
    assert result.returned_count == 0


@pytest.mark.asyncio
async def test_semantic_retrieval_model_and_dimension_mismatch(test_session: AsyncSession) -> None:
    """Embeddings generated with a different model or dimension are never compared."""
    provider_v1 = FakeEmbeddingProvider(dimensions=8, model_name="fake-v1")
    provider_v2 = FakeEmbeddingProvider(dimensions=16, model_name="fake-v2")

    emb_service = MemoryEmbeddingService(test_session, provider_v1)
    retrieval_service_v2 = SemanticMemoryRetrievalService(test_session, provider_v2)

    mem = await create_memory(
        session=test_session,
        category=MemoryCategory.FACT,
        content="Model mismatch test fact.",
    )
    await emb_service.embed_memory(mem.id)  # Stored with fake-v1 and 8 dimensions

    query = SemanticMemoryRetrievalQuery(text="Model mismatch test fact", min_similarity=0.0)
    # Query with fake-v2 (16 dimensions)
    result = await retrieval_service_v2.retrieve(query)

    assert result.returned_count == 0


@pytest.mark.asyncio
async def test_semantic_retrieval_candidate_exclusion(test_session: AsyncSession) -> None:
    """Candidates (PENDING, REJECTED) must never appear in semantic retrieval."""
    provider = FakeEmbeddingProvider(dimensions=8)
    retrieval_service = SemanticMemoryRetrievalService(test_session, provider)

    cand = await create_memory_candidate(
        session=test_session,
        category=MemoryCategory.FACT,
        content="Candidate content about space exploration.",
    )

    query = SemanticMemoryRetrievalQuery(text="space exploration", min_similarity=0.0)
    result = await retrieval_service.retrieve(query)

    assert result.returned_count == 0
    assert all(r.memory.id != cand.id for r in result.memories)


@pytest.mark.asyncio
async def test_semantic_retrieval_secret_filtering(test_session: AsyncSession) -> None:
    """Memories containing credentials are excluded even if similar."""
    provider = FakeEmbeddingProvider(dimensions=8)
    emb_service = MemoryEmbeddingService(test_session, provider)
    retrieval_service = SemanticMemoryRetrievalService(test_session, provider)

    mem = await create_memory(
        session=test_session,
        category=MemoryCategory.FACT,
        content="User's OpenAI key is sk-1234567890abcdef1234567890abcdef",
    )
    await emb_service.embed_memory(mem.id)

    query = SemanticMemoryRetrievalQuery(text="OpenAI key", min_similarity=0.0)
    result = await retrieval_service.retrieve(query)

    assert result.returned_count == 0


@pytest.mark.asyncio
async def test_semantic_retrieval_does_not_mutate_memory(test_session: AsyncSession) -> None:
    provider = FakeEmbeddingProvider(dimensions=8)
    emb_service = MemoryEmbeddingService(test_session, provider)
    retrieval_service = SemanticMemoryRetrievalService(test_session, provider)

    mem = await create_memory(
        session=test_session,
        category=MemoryCategory.FACT,
        content="Immutable memory observation.",
    )
    await emb_service.embed_memory(mem.id)

    # Capture state before retrieval
    initial_mem = await get_memory(test_session, mem.id)
    assert initial_mem is not None
    initial_version = initial_mem.version
    initial_updated_at = initial_mem.updated_at
    initial_times_recalled = initial_mem.times_recalled

    # Perform retrieval
    query = SemanticMemoryRetrievalQuery(text="Immutable memory observation", min_similarity=0.10)
    result = await retrieval_service.retrieve(query)
    assert result.returned_count == 1

    # Reload memory from DB and verify unchanged
    reloaded = await get_memory(test_session, mem.id)
    assert reloaded is not None
    assert reloaded.version == initial_version
    assert reloaded.updated_at == initial_updated_at
    assert reloaded.times_recalled == initial_times_recalled
    assert reloaded.last_recalled is None


@pytest.mark.asyncio
async def test_semantic_retrieval_category_filtering(test_session: AsyncSession) -> None:
    provider = FakeEmbeddingProvider(dimensions=8)
    emb_service = MemoryEmbeddingService(test_session, provider)
    retrieval_service = SemanticMemoryRetrievalService(test_session, provider)

    m_fact = await create_memory(
        session=test_session,
        category=MemoryCategory.FACT,
        content="User loves programming in Go.",
    )
    m_pref = await create_memory(
        session=test_session,
        category=MemoryCategory.PREFERENCE,
        content="User prefers programming in Go.",
    )
    await emb_service.embed_memory(m_fact.id)
    await emb_service.embed_memory(m_pref.id)

    # Filter to PREFERENCE only
    query = SemanticMemoryRetrievalQuery(
        text="programming in Go",
        categories=(MemoryCategory.PREFERENCE,),
        min_similarity=0.10,
    )
    result = await retrieval_service.retrieve(query)

    assert result.returned_count == 1
    assert result.memories[0].memory.id == m_pref.id


@pytest.mark.asyncio
async def test_convenience_functions(test_session: AsyncSession) -> None:
    provider = FakeEmbeddingProvider(dimensions=8)
    mem = await create_memory(
        session=test_session,
        category=MemoryCategory.FACT,
        content="Convenience function test memory.",
    )

    emb = await embed_memory(test_session, provider, mem.id)
    assert emb.memory_id == mem.id

    fetched = await get_memory_embedding(test_session, provider, mem.id)
    assert fetched is not None
    assert fetched.id == emb.id

    query = SemanticMemoryRetrievalQuery(text="Convenience function test", min_similarity=0.10)
    ret_res = await retrieve_semantic_memories(test_session, provider, query)
    assert ret_res.returned_count == 1

    deleted = await delete_memory_embedding(test_session, provider, mem.id)
    assert deleted is True


# =============================================================================
# 8. Architecture & Configuration Tests
# =============================================================================


def test_embedding_configuration_defaults() -> None:
    s = Settings()
    assert hasattr(s, "embedding_provider")
    assert hasattr(s, "embedding_model")
    assert s.embedding_provider == "gemini"
    assert s.embedding_model == "text-embedding-004"
    # Verify independent from chat model
    assert s.embedding_model != s.gemini_model


def test_gemini_embedding_provider_unconfigured_raises(monkeypatch) -> None:
    monkeypatch.setattr("app.memory.embedding_provider.settings.gemini_api_key", None)
    provider = GeminiEmbeddingProvider(api_key=None, client=None)
    with pytest.raises(EmbeddingProviderNotConfiguredError):
        import asyncio
        asyncio.run(provider.embed_text("test"))
