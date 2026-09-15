"""Unit tests for Phase 3.1: Memory Foundation.

Validates memory domain models, categories, SQLite persistence, deterministic retrieval,
atomic updates, recall tracking, optimistic concurrency, and architectural isolation.
"""

from datetime import datetime, timezone
import math
import sys
import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.memory.models import (
    MAX_MEMORY_CONTENT_LENGTH,
    Memory,
    MemoryCategory,
    MemoryUpdate,
)
from app.memory.service import (
    MemoryConflictError,
    MemoryNotFoundError,
    MemoryService,
    create_memory,
    delete_memory,
    get_memory,
    list_memories,
    recall_memory,
    update_memory,
)


def _make_valid_memory(**overrides) -> Memory:
    """Helper to construct a valid Memory domain model."""
    now = datetime.now(timezone.utc)
    params = {
        "id": "test-uuid-1",
        "category": MemoryCategory.FACT,
        "content": "User studies Software Engineering.",
        "importance": 0.8,
        "confidence": 0.95,
        "emotional_weight": 0.2,
        "created_at": now,
        "updated_at": now,
        "last_recalled": None,
        "times_recalled": 0,
        "version": 1,
    }
    params.update(overrides)
    return Memory(**params)


# =============================================================================
# 1. Model Validation Tests
# =============================================================================


def test_valid_memory_instantiation() -> None:
    mem = _make_valid_memory()
    assert mem.id == "test-uuid-1"
    assert mem.category == MemoryCategory.FACT
    assert mem.content == "User studies Software Engineering."
    assert mem.importance == 0.8
    assert mem.confidence == 0.95
    assert mem.emotional_weight == 0.2
    assert mem.times_recalled == 0
    assert mem.last_recalled is None
    assert mem.version == 1


def test_all_categories_supported() -> None:
    expected_categories = [
        "FACT",
        "PREFERENCE",
        "EVENT",
        "EXPERIENCE",
        "PROMISE",
        "JOKE",
        "RELATIONSHIP",
        "USER_GOAL",
        "USER_PROBLEM",
        "CHARACTER_EVENT",
    ]
    for cat_name in expected_categories:
        cat = MemoryCategory(cat_name)
        mem = _make_valid_memory(category=cat)
        assert mem.category == cat


def test_invalid_category_rejected() -> None:
    with pytest.raises(ValidationError):
        _make_valid_memory(category="INVALID_CATEGORY")


def test_empty_or_whitespace_content_rejected() -> None:
    with pytest.raises(ValidationError, match="content must not be empty or whitespace"):
        _make_valid_memory(content="")

    with pytest.raises(ValidationError, match="content must not be empty or whitespace"):
        _make_valid_memory(content="   \n\t  ")


def test_content_length_limit_enforced() -> None:
    oversized = "a" * (MAX_MEMORY_CONTENT_LENGTH + 1)
    with pytest.raises(ValidationError, match="exceeds maximum length"):
        _make_valid_memory(content=oversized)

    valid_edge = "a" * MAX_MEMORY_CONTENT_LENGTH
    mem = _make_valid_memory(content=valid_edge)
    assert len(mem.content) == MAX_MEMORY_CONTENT_LENGTH


@pytest.mark.parametrize("metric", ["importance", "confidence", "emotional_weight"])
def test_out_of_range_metrics_rejected(metric: str) -> None:
    with pytest.raises(ValidationError):
        _make_valid_memory(**{metric: -0.01})

    with pytest.raises(ValidationError):
        _make_valid_memory(**{metric: 1.01})


@pytest.mark.parametrize("metric", ["importance", "confidence", "emotional_weight"])
def test_nan_and_inf_metrics_rejected(metric: str) -> None:
    with pytest.raises(ValidationError, match="must not be NaN"):
        _make_valid_memory(**{metric: float("nan")})

    with pytest.raises(ValidationError, match="must not be infinite"):
        _make_valid_memory(**{metric: float("inf")})

    with pytest.raises(ValidationError, match="must not be infinite"):
        _make_valid_memory(**{metric: float("-inf")})


def test_negative_times_recalled_rejected() -> None:
    with pytest.raises(ValidationError):
        _make_valid_memory(times_recalled=-1)


def test_invalid_version_rejected() -> None:
    with pytest.raises(ValidationError):
        _make_valid_memory(version=0)


def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        _make_valid_memory(speculative_metadata="arbitrary_payload")


def test_memory_model_is_immutable() -> None:
    mem = _make_valid_memory()
    with pytest.raises(ValidationError):
        mem.content = "New content"  # type: ignore[misc]


# =============================================================================
# 2. MemoryUpdate Model Tests
# =============================================================================


def test_empty_update_rejected() -> None:
    with pytest.raises(ValidationError, match="must specify at least one field to update"):
        MemoryUpdate()


def test_valid_partial_updates() -> None:
    up1 = MemoryUpdate(content="Updated fact.")
    assert up1.content == "Updated fact."
    assert up1.importance is None

    up2 = MemoryUpdate(importance=0.9, confidence=0.8)
    assert up2.importance == 0.9
    assert up2.confidence == 0.8
    assert up2.content is None


def test_memory_update_immutability_and_extra_fields() -> None:
    up = MemoryUpdate(content="Test")
    with pytest.raises(ValidationError):
        up.content = "Change"  # type: ignore[misc]

    with pytest.raises(ValidationError):
        MemoryUpdate(content="Test", category=MemoryCategory.EVENT)  # type: ignore[call-arg]


# =============================================================================
# 3. Service Persistence and CRUD Tests
# =============================================================================


@pytest.mark.asyncio
async def test_create_memory_success(test_session: AsyncSession) -> None:
    service = MemoryService(test_session)
    mem = await service.create_memory(
        category=MemoryCategory.USER_GOAL,
        content="User wants to learn German.",
        importance=0.7,
        confidence=0.9,
        emotional_weight=0.3,
    )

    assert mem.id is not None
    assert mem.category == MemoryCategory.USER_GOAL
    assert mem.content == "User wants to learn German."
    assert mem.importance == 0.7
    assert mem.confidence == 0.9
    assert mem.emotional_weight == 0.3
    assert mem.version == 1
    assert mem.times_recalled == 0
    assert mem.last_recalled is None
    assert mem.created_at is not None
    assert mem.updated_at is not None


@pytest.mark.asyncio
async def test_get_memory_found_and_not_found(test_session: AsyncSession) -> None:
    service = MemoryService(test_session)
    mem = await service.create_memory(
        category=MemoryCategory.FACT,
        content="User likes black tea.",
    )

    retrieved = await service.get_memory(mem.id)
    assert retrieved is not None
    assert retrieved.id == mem.id
    assert retrieved.content == "User likes black tea."

    missing = await service.get_memory("non-existent-id")
    assert missing is None


@pytest.mark.asyncio
async def test_list_memories_ordering_and_filtering(test_session: AsyncSession) -> None:
    service = MemoryService(test_session)
    m1 = await service.create_memory(category=MemoryCategory.FACT, content="Fact 1")
    m2 = await service.create_memory(category=MemoryCategory.EVENT, content="Event 1")
    m3 = await service.create_memory(category=MemoryCategory.FACT, content="Fact 2")

    all_mems = await service.list_memories()
    assert len(all_mems) == 3

    fact_mems = await service.list_memories(category=MemoryCategory.FACT)
    assert len(fact_mems) == 2
    assert all(m.category == MemoryCategory.FACT for m in fact_mems)

    # Deterministic limit & pagination
    paged = await service.list_memories(limit=2, offset=0)
    assert len(paged) == 2


@pytest.mark.asyncio
async def test_update_memory_fields_and_version(test_session: AsyncSession) -> None:
    service = MemoryService(test_session)
    mem = await service.create_memory(
        category=MemoryCategory.PROMISE,
        content="Promised to meet at 4 PM.",
        importance=0.5,
    )

    initial_created = mem.created_at
    initial_updated = mem.updated_at

    update_req = MemoryUpdate(content="Promised to meet at 5 PM.", importance=0.8)
    updated = await service.update_memory(mem.id, update_req, expected_version=1)

    assert updated.content == "Promised to meet at 5 PM."
    assert updated.importance == 0.8
    assert updated.confidence == mem.confidence  # preserved
    assert updated.emotional_weight == mem.emotional_weight  # preserved
    assert updated.version == 2
    assert updated.created_at == initial_created  # immutable
    assert updated.updated_at >= initial_updated


@pytest.mark.asyncio
async def test_update_missing_memory_raises_error(test_session: AsyncSession) -> None:
    service = MemoryService(test_session)
    with pytest.raises(MemoryNotFoundError):
        await service.update_memory("missing-id", MemoryUpdate(content="Test"))


@pytest.mark.asyncio
async def test_optimistic_concurrency_conflict(test_session: AsyncSession) -> None:
    service = MemoryService(test_session)
    mem = await service.create_memory(category=MemoryCategory.JOKE, content="Inside joke.")

    # Writer A updates successfully (version 1 -> 2)
    await service.update_memory(mem.id, MemoryUpdate(importance=0.6), expected_version=1)

    # Writer B attempts update expecting version 1
    with pytest.raises(MemoryConflictError) as exc_info:
        await service.update_memory(mem.id, MemoryUpdate(importance=0.9), expected_version=1)

    assert exc_info.value.expected_version == 1
    assert exc_info.value.actual_version == 2


@pytest.mark.asyncio
async def test_recall_memory_tracking(test_session: AsyncSession) -> None:
    service = MemoryService(test_session)
    mem = await service.create_memory(
        category=MemoryCategory.EXPERIENCE,
        content="Visited a quiet cafe together.",
    )
    assert mem.times_recalled == 0
    assert mem.last_recalled is None

    # First recall
    recalled_1 = await service.recall_memory(mem.id, expected_version=1)
    assert recalled_1.times_recalled == 1
    assert recalled_1.last_recalled is not None
    assert recalled_1.version == 2
    assert recalled_1.content == mem.content

    # Second recall
    recalled_2 = await service.recall_memory(mem.id, expected_version=2)
    assert recalled_2.times_recalled == 2
    assert recalled_2.version == 3


@pytest.mark.asyncio
async def test_delete_memory(test_session: AsyncSession) -> None:
    service = MemoryService(test_session)
    m1 = await service.create_memory(category=MemoryCategory.FACT, content="To be deleted")
    m2 = await service.create_memory(category=MemoryCategory.FACT, content="To remain")

    assert await service.delete_memory(m1.id) is True
    assert await service.get_memory(m1.id) is None

    # Other memory untouched
    assert await service.get_memory(m2.id) is not None

    # Deleting non-existent returns False
    assert await service.delete_memory("non-existent-id") is False


@pytest.mark.asyncio
async def test_persistence_survives_session_boundary(test_engine) -> None:
    factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    # Session 1: Create
    async with factory() as s1:
        service1 = MemoryService(s1)
        m = await service1.create_memory(
            category=MemoryCategory.CHARACTER_EVENT,
            content="Aevum organized her bookshelf.",
        )
        mem_id = m.id

    # Session 2: Read and update
    async with factory() as s2:
        service2 = MemoryService(s2)
        loaded = await service2.get_memory(mem_id)
        assert loaded is not None
        assert loaded.content == "Aevum organized her bookshelf."

        await service2.update_memory(mem_id, MemoryUpdate(importance=0.6))

    # Session 3: Read updated
    async with factory() as s3:
        service3 = MemoryService(s3)
        updated = await service3.get_memory(mem_id)
        assert updated is not None
        assert updated.importance == 0.6
        assert updated.version == 2


@pytest.mark.asyncio
async def test_convenience_functions(test_session: AsyncSession) -> None:
    mem = await create_memory(test_session, category=MemoryCategory.USER_PROBLEM, content="Difficulty sleeping.")
    assert mem.id is not None

    got = await get_memory(test_session, mem.id)
    assert got is not None

    listed = await list_memories(test_session, category=MemoryCategory.USER_PROBLEM)
    assert len(listed) == 1

    updated = await update_memory(test_session, mem.id, MemoryUpdate(importance=0.9))
    assert updated.importance == 0.9

    recalled = await recall_memory(test_session, mem.id)
    assert recalled.times_recalled == 1

    deleted = await delete_memory(test_session, mem.id)
    assert deleted is True


# =============================================================================
# 4. Architectural Isolation Verification Tests
# =============================================================================


def test_memory_models_do_not_import_gemini() -> None:
    import app.memory.models as m_models
    import app.memory.service as m_service

    for mod in (m_models, m_service):
        for name, obj in vars(mod).items():
            if isinstance(obj, type) and hasattr(obj, "__module__"):
                assert "genai" not in obj.__module__, f"Leaked Gemini dependency in {name}"
                assert "gemini" not in obj.__module__, f"Leaked Gemini dependency in {name}"


def test_memory_models_do_not_import_conversation() -> None:
    import app.memory.models as m_models
    import app.memory.service as m_service

    for mod in (m_models, m_service):
        for name, obj in vars(mod).items():
            if isinstance(obj, type) and hasattr(obj, "__module__"):
                assert "conversation" not in obj.__module__.lower(), f"Leaked Conversation dependency in {name}"


def test_memory_models_do_not_import_character_state_or_emotion_or_life() -> None:
    import app.memory.models as m_models
    import app.memory.service as m_service

    for mod in (m_models, m_service):
        for name, obj in vars(mod).items():
            if isinstance(obj, type) and hasattr(obj, "__module__"):
                mod_name = obj.__module__.lower()
                assert "character_state" not in mod_name
                assert "emotion" not in mod_name
                assert "relationship" not in mod_name
                assert "life" not in mod_name
                assert "autonomy" not in mod_name
