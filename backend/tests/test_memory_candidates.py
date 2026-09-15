"""Unit tests for Phase 3.2: Memory Candidate & Curation Foundation.

Validates memory candidate domain models, lifecycle (PENDING -> ACCEPTED / REJECTED),
deterministic curation, atomic memory conversion, duplicate rejection, optimistic concurrency,
and architectural isolation from LLM providers.
"""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from unittest.mock import patch

from app.memory.curation_service import (
    CandidateConflictError,
    CandidateNotFoundError,
    CandidateTerminalStateError,
    MemoryCurationService,
    accept_memory_candidate,
    create_memory_candidate,
    get_memory_candidate,
    list_memory_candidates,
    reject_memory_candidate,
    update_memory_candidate,
)
from app.memory.models import (
    MAX_MEMORY_CONTENT_LENGTH,
    CurationDecision,
    MemoryCategory,
    MemoryCandidate,
    MemoryCandidateSource,
    MemoryCandidateStatus,
    MemoryCandidateUpdate,
)
from app.memory.service import MemoryService, create_memory, get_memory


def _make_valid_candidate(**overrides) -> MemoryCandidate:
    """Helper to construct a valid MemoryCandidate domain model."""
    now = datetime.now(timezone.utc)
    params = {
        "id": "cand-uuid-1",
        "category": MemoryCategory.EVENT,
        "content": "User passed driving test.",
        "importance": 0.7,
        "confidence": 0.9,
        "emotional_weight": 0.4,
        "status": MemoryCandidateStatus.PENDING,
        "source_type": MemoryCandidateSource.MANUAL,
        "created_at": now,
        "updated_at": now,
        "version": 1,
    }
    params.update(overrides)
    return MemoryCandidate(**params)


# =============================================================================
# 1. Candidate Domain Model Tests
# =============================================================================


def test_valid_candidate_instantiation() -> None:
    cand = _make_valid_candidate()
    assert cand.id == "cand-uuid-1"
    assert cand.category == MemoryCategory.EVENT
    assert cand.content == "User passed driving test."
    assert cand.importance == 0.7
    assert cand.confidence == 0.9
    assert cand.emotional_weight == 0.4
    assert cand.status == MemoryCandidateStatus.PENDING
    assert cand.source_type == MemoryCandidateSource.MANUAL
    assert cand.version == 1


def test_all_categories_supported() -> None:
    for cat in MemoryCategory:
        cand = _make_valid_candidate(category=cat)
        assert cand.category == cat


def test_all_source_types_supported() -> None:
    for source in MemoryCandidateSource:
        cand = _make_valid_candidate(source_type=source)
        assert cand.source_type == source


def test_all_statuses_supported() -> None:
    for status in MemoryCandidateStatus:
        cand = _make_valid_candidate(status=status)
        assert cand.status == status


def test_invalid_category_rejected() -> None:
    with pytest.raises(ValidationError):
        _make_valid_candidate(category="NON_EXISTENT")


def test_invalid_source_type_rejected() -> None:
    with pytest.raises(ValidationError):
        _make_valid_candidate(source_type="EXTERNAL_API")


def test_invalid_status_rejected() -> None:
    with pytest.raises(ValidationError):
        _make_valid_candidate(status="UNKNOWN")


def test_empty_or_whitespace_content_rejected() -> None:
    with pytest.raises(ValidationError, match="must not be empty or whitespace"):
        _make_valid_candidate(content="")

    with pytest.raises(ValidationError, match="must not be empty or whitespace"):
        _make_valid_candidate(content="   \n\t  ")


def test_content_length_limit_enforced() -> None:
    oversized = "x" * (MAX_MEMORY_CONTENT_LENGTH + 1)
    with pytest.raises(ValidationError, match="exceeds maximum length"):
        _make_valid_candidate(content=oversized)

    valid_edge = "x" * MAX_MEMORY_CONTENT_LENGTH
    cand = _make_valid_candidate(content=valid_edge)
    assert len(cand.content) == MAX_MEMORY_CONTENT_LENGTH


@pytest.mark.parametrize("metric", ["importance", "confidence", "emotional_weight"])
def test_out_of_range_metrics_rejected(metric: str) -> None:
    with pytest.raises(ValidationError):
        _make_valid_candidate(**{metric: -0.05})

    with pytest.raises(ValidationError):
        _make_valid_candidate(**{metric: 1.05})


@pytest.mark.parametrize("metric", ["importance", "confidence", "emotional_weight"])
def test_nan_and_inf_metrics_rejected(metric: str) -> None:
    with pytest.raises(ValidationError, match="must not be NaN"):
        _make_valid_candidate(**{metric: float("nan")})

    with pytest.raises(ValidationError, match="must not be infinite"):
        _make_valid_candidate(**{metric: float("inf")})

    with pytest.raises(ValidationError, match="must not be infinite"):
        _make_valid_candidate(**{metric: float("-inf")})


def test_invalid_version_rejected() -> None:
    with pytest.raises(ValidationError):
        _make_valid_candidate(version=0)


def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        _make_valid_candidate(arbitrary_json="payload")


def test_candidate_model_is_immutable() -> None:
    cand = _make_valid_candidate()
    with pytest.raises(ValidationError):
        cand.content = "Mutated"  # type: ignore[misc]


# =============================================================================
# 2. Candidate Update Model Tests
# =============================================================================


def test_empty_update_rejected() -> None:
    with pytest.raises(ValidationError, match="must specify at least one field to update"):
        MemoryCandidateUpdate()


def test_valid_candidate_update() -> None:
    up = MemoryCandidateUpdate(content="Updated proposal.", importance=0.8)
    assert up.content == "Updated proposal."
    assert up.importance == 0.8
    assert up.confidence is None


def test_candidate_update_immutable_and_extra_fields_forbidden() -> None:
    up = MemoryCandidateUpdate(content="Valid")
    with pytest.raises(ValidationError):
        up.content = "New"  # type: ignore[misc]

    with pytest.raises(ValidationError):
        MemoryCandidateUpdate(content="Valid", status=MemoryCandidateStatus.ACCEPTED)  # type: ignore[call-arg]


# =============================================================================
# 3. Curation Service Lifecycle Tests
# =============================================================================


@pytest.mark.asyncio
async def test_create_candidate_success(test_session: AsyncSession) -> None:
    service = MemoryCurationService(test_session)
    cand = await service.create_candidate(
        category=MemoryCategory.USER_GOAL,
        content="User wants to run a marathon.",
        importance=0.8,
        confidence=0.9,
        emotional_weight=0.5,
        source_type=MemoryCandidateSource.SYSTEM,
    )

    assert cand.id is not None
    assert cand.category == MemoryCategory.USER_GOAL
    assert cand.content == "User wants to run a marathon."
    assert cand.importance == 0.8
    assert cand.confidence == 0.9
    assert cand.emotional_weight == 0.5
    assert cand.status == MemoryCandidateStatus.PENDING
    assert cand.source_type == MemoryCandidateSource.SYSTEM
    assert cand.version == 1
    assert cand.created_at is not None
    assert cand.updated_at is not None


@pytest.mark.asyncio
async def test_get_and_list_candidates(test_session: AsyncSession) -> None:
    service = MemoryCurationService(test_session)
    c1 = await service.create_candidate(category=MemoryCategory.FACT, content="Fact candidate 1")
    c2 = await service.create_candidate(category=MemoryCategory.EVENT, content="Event candidate 1")

    retrieved = await service.get_candidate(c1.id)
    assert retrieved is not None
    assert retrieved.content == "Fact candidate 1"

    missing = await service.get_candidate("missing-candidate-id")
    assert missing is None

    all_cands = await service.list_candidates()
    assert len(all_cands) == 2

    fact_cands = await service.list_candidates(category=MemoryCategory.FACT)
    assert len(fact_cands) == 1
    assert fact_cands[0].id == c1.id


@pytest.mark.asyncio
async def test_update_pending_candidate(test_session: AsyncSession) -> None:
    service = MemoryCurationService(test_session)
    cand = await service.create_candidate(category=MemoryCategory.JOKE, content="First draft joke.")
    initial_created = cand.created_at

    updated = await service.update_candidate(
        cand.id,
        MemoryCandidateUpdate(content="Refined joke.", importance=0.4),
        expected_version=1,
    )

    assert updated.content == "Refined joke."
    assert updated.importance == 0.4
    assert updated.confidence == cand.confidence
    assert updated.version == 2
    assert updated.created_at == initial_created
    assert updated.status == MemoryCandidateStatus.PENDING


@pytest.mark.asyncio
async def test_terminal_candidate_cannot_be_updated(test_session: AsyncSession) -> None:
    service = MemoryCurationService(test_session)
    cand = await service.create_candidate(category=MemoryCategory.FACT, content="A candidate.")

    # Reject candidate -> terminal state
    await service.reject_candidate(cand.id, expected_version=1)

    with pytest.raises(CandidateTerminalStateError):
        await service.update_candidate(cand.id, MemoryCandidateUpdate(content="Modified after rejection."))


@pytest.mark.asyncio
async def test_accept_candidate_creates_memory_and_marks_accepted(test_session: AsyncSession) -> None:
    curation_service = MemoryCurationService(test_session)
    memory_service = MemoryService(test_session)

    cand = await curation_service.create_candidate(
        category=MemoryCategory.EXPERIENCE,
        content="Shared a coffee on Sunday morning.",
        importance=0.75,
        confidence=0.95,
        emotional_weight=0.3,
    )

    result = await curation_service.accept_candidate(cand.id, expected_version=1)

    assert result.decision == CurationDecision.ACCEPTED
    assert result.candidate_id == cand.id
    assert result.memory_id is not None
    assert result.memory_id != cand.id  # Memory gets unique UUID
    assert result.memory is not None
    assert result.memory.category == MemoryCategory.EXPERIENCE
    assert result.memory.content == "Shared a coffee on Sunday morning."
    assert result.memory.importance == 0.75
    assert result.memory.confidence == 0.95
    assert result.memory.emotional_weight == 0.3
    assert result.memory.version == 1

    # Verify candidate is now terminal ACCEPTED
    updated_cand = await curation_service.get_candidate(cand.id)
    assert updated_cand is not None
    assert updated_cand.status == MemoryCandidateStatus.ACCEPTED
    assert updated_cand.version == 2

    # Verify memory is persisted and retrievable in memory service
    persisted_mem = await memory_service.get_memory(result.memory_id)
    assert persisted_mem is not None
    assert persisted_mem.content == "Shared a coffee on Sunday morning."


@pytest.mark.asyncio
async def test_reject_candidate_creates_no_memory(test_session: AsyncSession) -> None:
    curation_service = MemoryCurationService(test_session)
    memory_service = MemoryService(test_session)

    cand = await curation_service.create_candidate(
        category=MemoryCategory.FACT,
        content="Candidate to be rejected.",
    )

    result = await curation_service.reject_candidate(cand.id, reason="Irrelevant detail.", expected_version=1)
    assert result.decision == CurationDecision.REJECTED
    assert result.candidate_id == cand.id
    assert result.memory_id is None
    assert result.reason == "Irrelevant detail."

    # Candidate is now REJECTED
    updated_cand = await curation_service.get_candidate(cand.id)
    assert updated_cand is not None
    assert updated_cand.status == MemoryCandidateStatus.REJECTED

    # No memories were created
    mems = await memory_service.list_memories()
    assert len(mems) == 0


@pytest.mark.asyncio
async def test_terminal_candidate_cannot_be_accepted_or_re_rejected(test_session: AsyncSession) -> None:
    service = MemoryCurationService(test_session)
    cand = await service.create_candidate(category=MemoryCategory.FACT, content="Fact candidate.")

    await service.reject_candidate(cand.id)

    # Attempting to accept a REJECTED candidate must fail
    with pytest.raises(CandidateTerminalStateError):
        await service.accept_candidate(cand.id)

    # Attempting to re-reject a REJECTED candidate must fail
    with pytest.raises(CandidateTerminalStateError):
        await service.reject_candidate(cand.id)


@pytest.mark.asyncio
async def test_duplicate_detection_rejects_candidate(test_session: AsyncSession) -> None:
    memory_service = MemoryService(test_session)
    curation_service = MemoryCurationService(test_session)

    # Pre-existing memory
    await memory_service.create_memory(
        category=MemoryCategory.PREFERENCE,
        content="User likes black coffee.",
    )

    # Candidate with exact duplicate content and category (differing only by whitespace)
    dup_cand = await curation_service.create_candidate(
        category=MemoryCategory.PREFERENCE,
        content="   User likes black coffee.  ",
    )

    result = await curation_service.accept_candidate(dup_cand.id)
    assert result.decision == CurationDecision.DUPLICATE
    assert result.memory_id is None
    assert "Exact duplicate" in (result.reason or "")

    # Candidate is marked REJECTED
    cand_after = await curation_service.get_candidate(dup_cand.id)
    assert cand_after is not None
    assert cand_after.status == MemoryCandidateStatus.REJECTED

    # No additional memory created
    all_mems = await memory_service.list_memories()
    assert len(all_mems) == 1


@pytest.mark.asyncio
async def test_different_category_or_distinct_content_is_not_duplicate(test_session: AsyncSession) -> None:
    memory_service = MemoryService(test_session)
    curation_service = MemoryCurationService(test_session)

    await memory_service.create_memory(
        category=MemoryCategory.PREFERENCE,
        content="User likes coffee.",
    )

    # Different category with same content -> Accepted
    cand_diff_cat = await curation_service.create_candidate(
        category=MemoryCategory.FACT,
        content="User likes coffee.",
    )
    res1 = await curation_service.accept_candidate(cand_diff_cat.id)
    assert res1.decision == CurationDecision.ACCEPTED

    # Different phrased content -> Not assumed duplicate in Phase 3.2 -> Accepted
    cand_diff_phrasing = await curation_service.create_candidate(
        category=MemoryCategory.PREFERENCE,
        content="User really enjoys drinking coffee.",
    )
    res2 = await curation_service.accept_candidate(cand_diff_phrasing.id)
    assert res2.decision == CurationDecision.ACCEPTED

    all_mems = await memory_service.list_memories()
    assert len(all_mems) == 3


@pytest.mark.asyncio
async def test_concurrency_conflict_on_acceptance_and_rejection(test_session: AsyncSession) -> None:
    service = MemoryCurationService(test_session)
    cand = await service.create_candidate(category=MemoryCategory.PROMISE, content="Promise candidate.")

    # Process A accepts candidate with expected_version=1 (advancing version to 2)
    res = await service.accept_candidate(cand.id, expected_version=1)
    assert res.decision == CurationDecision.ACCEPTED

    # Process B tries to reject expecting version 1 -> fails with conflict or terminal state
    with pytest.raises((CandidateConflictError, CandidateTerminalStateError)):
        await service.reject_candidate(cand.id, expected_version=1)


@pytest.mark.asyncio
async def test_atomic_transaction_rollback_on_failure(test_session: AsyncSession) -> None:
    curation_service = MemoryCurationService(test_session)
    memory_service = MemoryService(test_session)

    cand = await curation_service.create_candidate(
        category=MemoryCategory.EVENT,
        content="Atomic rollback test candidate.",
    )

    # Simulate unexpected failure during candidate update execution
    with patch.object(test_session, "execute", side_effect=RuntimeError("Simulated DB error during commit")):
        with pytest.raises(RuntimeError, match="Simulated DB error"):
            await curation_service.accept_candidate(cand.id)

    # After rollback, candidate remains PENDING with version 1
    cand_after = await curation_service.get_candidate(cand.id)
    assert cand_after is not None
    assert cand_after.status == MemoryCandidateStatus.PENDING
    assert cand_after.version == 1

    # No memory was persisted
    mems = await memory_service.list_memories()
    assert len(mems) == 0


@pytest.mark.asyncio
async def test_persistence_survives_session_boundary(test_engine) -> None:
    factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    # Session 1: Create candidate
    async with factory() as s1:
        service1 = MemoryCurationService(s1)
        c = await service1.create_candidate(
            category=MemoryCategory.CHARACTER_EVENT,
            content="Aevum composed a new melody.",
        )
        cand_id = c.id

    # Session 2: Accept candidate into memory
    async with factory() as s2:
        service2 = MemoryCurationService(s2)
        res = await service2.accept_candidate(cand_id)
        assert res.decision == CurationDecision.ACCEPTED
        mem_id = res.memory_id

    # Session 3: Read both candidate and memory in new session
    async with factory() as s3:
        cand_service = MemoryCurationService(s3)
        mem_service = MemoryService(s3)

        cand = await cand_service.get_candidate(cand_id)
        assert cand is not None
        assert cand.status == MemoryCandidateStatus.ACCEPTED

        mem = await mem_service.get_memory(mem_id)
        assert mem is not None
        assert mem.content == "Aevum composed a new melody."


@pytest.mark.asyncio
async def test_convenience_functions(test_session: AsyncSession) -> None:
    cand = await create_memory_candidate(
        test_session,
        category=MemoryCategory.USER_PROBLEM,
        content="User lost their keys.",
    )
    assert cand.id is not None

    got = await get_memory_candidate(test_session, cand.id)
    assert got is not None

    listed = await list_memory_candidates(test_session, status=MemoryCandidateStatus.PENDING)
    assert len(listed) == 1

    updated = await update_memory_candidate(
        test_session,
        cand.id,
        MemoryCandidateUpdate(importance=0.9),
    )
    assert updated.importance == 0.9

    res = await accept_memory_candidate(test_session, cand.id)
    assert res.decision == CurationDecision.ACCEPTED


# =============================================================================
# 4. Architectural Isolation Verification Tests
# =============================================================================


def test_memory_candidates_do_not_import_gemini() -> None:
    import app.memory.curation_service as cur_service
    import app.memory.models as mem_models

    for mod in (cur_service, mem_models):
        for name, obj in vars(mod).items():
            if isinstance(obj, type) and hasattr(obj, "__module__"):
                assert "genai" not in obj.__module__, f"Leaked Gemini dependency in {name}"
                assert "gemini" not in obj.__module__, f"Leaked Gemini dependency in {name}"


def test_memory_candidates_do_not_import_conversation_or_character_engines() -> None:
    import app.memory.curation_service as cur_service
    import app.memory.models as mem_models

    for mod in (cur_service, mem_models):
        for name, obj in vars(mod).items():
            if isinstance(obj, type) and hasattr(obj, "__module__"):
                mod_name = obj.__module__.lower()
                assert "conversation" not in mod_name
                assert "character_state" not in mod_name
                assert "character_engine" not in mod_name
                assert "emotion" not in mod_name
                assert "relationship" not in mod_name
                assert "life" not in mod_name
                assert "event" not in mod_name
                assert "autonomy" not in mod_name
