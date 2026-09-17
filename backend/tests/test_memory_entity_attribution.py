"""Targeted regression tests for Memory Entity/Speaker Attribution.

Prevents long-range speaker attribution inversion (Turn 12 -> Turn 190 defect),
where character-owned facts (e.g., Aevum reading 'Normal People') get mistakenly
attributed to the user or vice-versa over extended conversational horizons.
"""

from datetime import datetime, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.session import Base
from app.memory.context_builder import build_memory_context
from app.memory.curation_service import MemoryCurationService
from app.memory.hybrid_retrieval_service import HybridMemoryRetrievalService
from app.memory.models import (
    HybridMemoryRetrievalQuery,
    Memory,
    MemoryCandidate,
    MemoryCandidateSource,
    MemoryCandidateStatus,
    MemoryCategory,
    MemoryRetrievalQuery,
    MemorySubjectEntity,
    MemoryUpdate,
)
from app.memory.retrieval_service import MemoryRetrievalService
from app.memory.service import MemoryService


@pytest.fixture
async def test_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session

    await engine.dispose()


# ---------------------------------------------------------------------------
# 1. Model and Service Attribution Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_memory_subject_entity_persistence_and_retrieval(test_session: AsyncSession):
    """Memories created with distinct subject_entity persist and deserialize correctly."""
    service = MemoryService(test_session)

    mem_aevum = await service.create_memory(
        category=MemoryCategory.CHARACTER_EVENT,
        content="Aevum finished playing Debussy's Clair de Lune.",
        subject_entity=MemorySubjectEntity.AEVUM,
    )
    assert mem_aevum.subject_entity == MemorySubjectEntity.AEVUM

    mem_user = await service.create_memory(
        category=MemoryCategory.PREFERENCE,
        content="User loves drinking oolong tea in the morning.",
        subject_entity=MemorySubjectEntity.USER,
    )
    assert mem_user.subject_entity == MemorySubjectEntity.USER

    mem_npc = await service.create_memory(
        category=MemoryCategory.FACT,
        content="Maya recommended visiting the local art gallery.",
        subject_entity=MemorySubjectEntity.NPC,
    )
    assert mem_npc.subject_entity == MemorySubjectEntity.NPC

    # Fetch from DB and verify persistence
    fetched_aevum = await service.get_memory(mem_aevum.id)
    assert fetched_aevum is not None
    assert fetched_aevum.subject_entity == MemorySubjectEntity.AEVUM

    fetched_user = await service.get_memory(mem_user.id)
    assert fetched_user is not None
    assert fetched_user.subject_entity == MemorySubjectEntity.USER

    fetched_npc = await service.get_memory(mem_npc.id)
    assert fetched_npc is not None
    assert fetched_npc.subject_entity == MemorySubjectEntity.NPC


@pytest.mark.asyncio
async def test_memory_subject_entity_defaulting():
    """Domain models default CHARACTER_EVENT to AEVUM and other categories to USER."""
    now = datetime.now(timezone.utc)

    # CHARACTER_EVENT defaults to AEVUM
    mem_char = Memory(
        id="mem-1",
        category=MemoryCategory.CHARACTER_EVENT,
        content="Practiced scales for 2 hours.",
        created_at=now,
        updated_at=now,
    )
    assert mem_char.subject_entity == MemorySubjectEntity.AEVUM

    # FACT defaults to USER
    mem_user = Memory(
        id="mem-2",
        category=MemoryCategory.FACT,
        content="User works as an aerospace software engineer.",
        created_at=now,
        updated_at=now,
    )
    assert mem_user.subject_entity == MemorySubjectEntity.USER


@pytest.mark.asyncio
async def test_memory_service_update_subject_entity(test_session: AsyncSession):
    """MemoryService allows updating the subject_entity of an existing memory."""
    service = MemoryService(test_session)
    mem = await service.create_memory(
        category=MemoryCategory.FACT,
        content="Likes reading contemporary Irish literature.",
        subject_entity=MemorySubjectEntity.USER,
    )
    assert mem.subject_entity == MemorySubjectEntity.USER

    # Update subject to AEVUM
    updated = await service.update_memory(
        memory_id=mem.id,
        memory_update=MemoryUpdate(subject_entity=MemorySubjectEntity.AEVUM),
    )
    assert updated.subject_entity == MemorySubjectEntity.AEVUM

    refetched = await service.get_memory(mem.id)
    assert refetched is not None
    assert refetched.subject_entity == MemorySubjectEntity.AEVUM


@pytest.mark.asyncio
async def test_memory_service_list_with_subject_filter(test_session: AsyncSession):
    """MemoryService.list_memories filters by subject_entity."""
    service = MemoryService(test_session)

    await service.create_memory(
        category=MemoryCategory.FACT,
        content="Aevum fact 1",
        subject_entity=MemorySubjectEntity.AEVUM,
    )
    await service.create_memory(
        category=MemoryCategory.FACT,
        content="User fact 1",
        subject_entity=MemorySubjectEntity.USER,
    )
    await service.create_memory(
        category=MemoryCategory.FACT,
        content="Aevum fact 2",
        subject_entity=MemorySubjectEntity.AEVUM,
    )

    aevum_mems = await service.list_memories(subject_entity=MemorySubjectEntity.AEVUM)
    assert len(aevum_mems) == 2
    assert all(m.subject_entity == MemorySubjectEntity.AEVUM for m in aevum_mems)

    user_mems = await service.list_memories(subject_entity=MemorySubjectEntity.USER)
    assert len(user_mems) == 1
    assert user_mems[0].subject_entity == MemorySubjectEntity.USER


# ---------------------------------------------------------------------------
# 2. Retrieval Filtering and Attribution Isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lexical_retrieval_subject_entities_filter(test_session: AsyncSession):
    """MemoryRetrievalService supports filtering by subject_entities."""
    mem_service = MemoryService(test_session)
    retrieval_service = MemoryRetrievalService(test_session)

    # Aevum reading
    await mem_service.create_memory(
        category=MemoryCategory.CHARACTER_EVENT,
        content="Aevum is currently reading Normal People by Sally Rooney.",
        subject_entity=MemorySubjectEntity.AEVUM,
    )
    # User reading
    await mem_service.create_memory(
        category=MemoryCategory.PREFERENCE,
        content="User is currently reading The Three-Body Problem by Liu Cixin.",
        subject_entity=MemorySubjectEntity.USER,
    )

    # Query without subject filter: returns both
    query_all = MemoryRetrievalQuery(text="reading novel book")
    res_all = await retrieval_service.retrieve(query_all)
    assert len(res_all.memories) == 2

    # Query with AEVUM filter: returns ONLY Aevum's reading
    query_aevum = MemoryRetrievalQuery(
        text="reading novel book",
        subject_entities=(MemorySubjectEntity.AEVUM,),
    )
    res_aevum = await retrieval_service.retrieve(query_aevum)
    assert len(res_aevum.memories) == 1
    assert res_aevum.memories[0].memory.subject_entity == MemorySubjectEntity.AEVUM
    assert "Normal People" in res_aevum.memories[0].memory.content

    # Query with USER filter: returns ONLY User's reading
    query_user = MemoryRetrievalQuery(
        text="reading novel book",
        subject_entities=(MemorySubjectEntity.USER,),
    )
    res_user = await retrieval_service.retrieve(query_user)
    assert len(res_user.memories) == 1
    assert res_user.memories[0].memory.subject_entity == MemorySubjectEntity.USER
    assert "Three-Body Problem" in res_user.memories[0].memory.content


@pytest.mark.asyncio
async def test_hybrid_retrieval_forwards_subject_entities_filter(test_session: AsyncSession):
    """HybridMemoryRetrievalService forwards subject_entities filter correctly."""
    mem_service = MemoryService(test_session)
    hybrid_service = HybridMemoryRetrievalService(session=test_session, embedding_provider=None)

    await mem_service.create_memory(
        category=MemoryCategory.CHARACTER_EVENT,
        content="Aevum spent the afternoon playing Rachmaninoff on piano.",
        subject_entity=MemorySubjectEntity.AEVUM,
    )
    await mem_service.create_memory(
        category=MemoryCategory.PREFERENCE,
        content="User loves listening to Rachmaninoff piano concertos.",
        subject_entity=MemorySubjectEntity.USER,
    )

    query = HybridMemoryRetrievalQuery(
        text="Rachmaninoff piano",
        subject_entities=(MemorySubjectEntity.AEVUM,),
    )
    res = await hybrid_service.retrieve(query)
    assert len(res.memories) == 1
    assert res.memories[0].memory.subject_entity == MemorySubjectEntity.AEVUM
    assert "spent the afternoon playing" in res.memories[0].memory.content


# ---------------------------------------------------------------------------
# 3. Curation Pipeline Attribution Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_curation_candidate_acceptance_preserves_subject_entity(test_session: AsyncSession):
    """Accepting a memory candidate transfers subject_entity to persistent MemoryRecord."""
    curation_service = MemoryCurationService(test_session)
    mem_service = MemoryService(test_session)

    candidate = await curation_service.create_candidate(
        category=MemoryCategory.CHARACTER_EVENT,
        content="Aevum is rereading Normal People.",
        subject_entity=MemorySubjectEntity.AEVUM,
        source_type=MemoryCandidateSource.LLM,
    )
    assert candidate.subject_entity == MemorySubjectEntity.AEVUM

    res = await curation_service.accept_candidate(candidate.id)
    assert res.decision.value == "ACCEPTED"
    assert res.memory is not None
    assert res.memory.subject_entity == MemorySubjectEntity.AEVUM

    # Verify persisted memory in DB
    persisted = await mem_service.get_memory(res.memory_id)
    assert persisted is not None
    assert persisted.subject_entity == MemorySubjectEntity.AEVUM


# ---------------------------------------------------------------------------
# 4. Context Builder & Long-Horizon Attribution Inversion Reproduction
# ---------------------------------------------------------------------------


def test_context_builder_formats_subject_entity():
    """Context builder renders Subject/Entity and clear attribution instructions."""
    now = datetime.now(timezone.utc)
    mems = [
        Memory(
            id="mem-aevum-reading",
            category=MemoryCategory.CHARACTER_EVENT,
            subject_entity=MemorySubjectEntity.AEVUM,
            content="Aevum is reading Normal People by Sally Rooney.",
            confidence=0.95,
            created_at=now,
            updated_at=now,
        ),
        Memory(
            id="mem-user-tea",
            category=MemoryCategory.PREFERENCE,
            subject_entity=MemorySubjectEntity.USER,
            content="User prefers green tea over black tea.",
            confidence=0.90,
            created_at=now,
            updated_at=now,
        ),
    ]

    context = build_memory_context(mems)
    assert context is not None
    assert "Subject Attribution: AEVUM facts belong to Aevum, USER facts to user." in context
    assert "Never invert ownership" in context
    assert "Subject/Entity: AEVUM" in context
    assert "Subject/Entity: USER" in context
    assert "Aevum is reading Normal People by Sally Rooney." in context


def test_reproduction_turn_12_turn_190_speaker_attribution():
    """Reproduction 2: Turn 12 Aevum reading Normal People vs Turn 190 attribution.

    Verifies that Aevum reading 'Normal People' is strictly tagged as AEVUM,
    and user facts are tagged as USER, preventing the LLM from asking the user
    if they are reading Normal People.
    """
    now = datetime.now(timezone.utc)
    aevum_reading = Memory(
        id="turn-12-reading",
        category=MemoryCategory.CHARACTER_EVENT,
        subject_entity=MemorySubjectEntity.AEVUM,
        content="Aevum mentioned reading Normal People by Sally Rooney.",
        confidence=0.95,
        created_at=now,
        updated_at=now,
    )

    context = build_memory_context([aevum_reading])
    assert context is not None
    # Subject/Entity must clearly be AEVUM
    assert "Subject/Entity: AEVUM" in context
    assert "Subject/Entity: USER" not in context
    # Header must explicitly command no inversion
    assert "Never invert ownership" in context
