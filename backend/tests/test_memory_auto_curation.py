"""Unit tests for Phase 3.4: Automatic Memory Curation Foundation.

Validates deterministic candidate evaluation, conservative acceptance/rejection/deferral,
exact duplicate detection against persistent memories, secret filtering, terminal state handling,
bounded batch curation, and architectural isolation from LLM providers.
"""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import MemoryCandidateRecord, MemoryRecord
from app.memory import (
    DEFAULT_CURATION_BATCH_SIZE,
    MEMORY_CURATION_POLICY_VERSION,
    BatchCurationResult,
    CandidateEvaluation,
    CandidateNotFoundError,
    MemoryCategory,
    MemoryCandidate,
    MemoryCandidateSource,
    MemoryCandidateStatus,
    MemoryCurationDecision,
    MemoryCurationReason,
    MemoryCurationService,
    curate_memory_candidate,
    curate_pending_memory_candidates,
    evaluate_candidate,
)
from app.memory.service import MemoryService, create_memory


def _make_candidate(
    category: MemoryCategory = MemoryCategory.FACT,
    content: str = "User lives in Tokyo.",
    importance: float = 0.8,
    confidence: float = 0.95,
    emotional_weight: float = 0.0,
    status: MemoryCandidateStatus = MemoryCandidateStatus.PENDING,
    source_type: MemoryCandidateSource = MemoryCandidateSource.SYSTEM,
    cand_id: str = "cand-test-1",
    version: int = 1,
) -> MemoryCandidate:
    """Helper to construct a valid MemoryCandidate domain object for policy tests."""
    now = datetime.now(timezone.utc)
    return MemoryCandidate(
        id=cand_id,
        category=category,
        content=content,
        importance=importance,
        confidence=confidence,
        emotional_weight=emotional_weight,
        status=status,
        source_type=source_type,
        created_at=now,
        updated_at=now,
        version=version,
    )


# =============================================================================
# 1. Deterministic Curation Policy Unit Tests (No DB)
# =============================================================================


def test_policy_version() -> None:
    assert MEMORY_CURATION_POLICY_VERSION == "1.0.0"


def test_evaluate_candidate_accept_fact() -> None:
    cand = _make_candidate(
        category=MemoryCategory.FACT,
        content="User was born in Kyoto.",
        confidence=0.95,
        importance=0.8,
    )
    res = evaluate_candidate(cand)
    assert res.decision == MemoryCurationDecision.ACCEPT
    assert res.reason == MemoryCurationReason.ACCEPTED_STABLE_FACT


def test_evaluate_candidate_accept_preference() -> None:
    cand = _make_candidate(
        category=MemoryCategory.PREFERENCE,
        content="User loves black coffee with no sugar.",
        confidence=0.92,
        importance=0.65,
    )
    res = evaluate_candidate(cand)
    assert res.decision == MemoryCurationDecision.ACCEPT
    assert res.reason == MemoryCurationReason.ACCEPTED_STRONG_PREFERENCE


def test_evaluate_candidate_accept_user_goal() -> None:
    cand = _make_candidate(
        category=MemoryCategory.USER_GOAL,
        content="User plans to take the JLPT N1 exam in December.",
        confidence=0.91,
        importance=0.8,
    )
    res = evaluate_candidate(cand)
    assert res.decision == MemoryCurationDecision.ACCEPT
    assert res.reason == MemoryCurationReason.ACCEPTED_USER_GOAL


def test_evaluate_candidate_accept_user_problem() -> None:
    cand = _make_candidate(
        category=MemoryCategory.USER_PROBLEM,
        content="User suffers from persistent back strain when coding.",
        confidence=0.93,
        importance=0.75,
    )
    res = evaluate_candidate(cand)
    assert res.decision == MemoryCurationDecision.ACCEPT
    assert res.reason == MemoryCurationReason.ACCEPTED_USER_PROBLEM


def test_evaluate_candidate_accept_promise() -> None:
    cand = _make_candidate(
        category=MemoryCategory.PROMISE,
        content="User promised to send the revised architecture document by Friday.",
        confidence=0.90,
        importance=0.70,
    )
    res = evaluate_candidate(cand)
    assert res.decision == MemoryCurationDecision.ACCEPT
    assert res.reason == MemoryCurationReason.ACCEPTED_PROMISE


def test_evaluate_candidate_accept_event() -> None:
    cand = _make_candidate(
        category=MemoryCategory.EVENT,
        content="User graduated from university with honors.",
        confidence=0.95,
        importance=0.85,
    )
    res = evaluate_candidate(cand)
    assert res.decision == MemoryCurationDecision.ACCEPT
    assert res.reason == MemoryCurationReason.ACCEPTED_EVENT


@pytest.mark.parametrize(
    "ambiguous_cat",
    [
        MemoryCategory.EXPERIENCE,
        MemoryCategory.JOKE,
        MemoryCategory.RELATIONSHIP,
        MemoryCategory.CHARACTER_EVENT,
    ],
)
def test_evaluate_candidate_defer_ambiguous_categories(ambiguous_cat: MemoryCategory) -> None:
    """Ambiguous categories are deferred as PENDING even with high confidence and importance."""
    cand = _make_candidate(
        category=ambiguous_cat,
        content="Candidate in ambiguous domain.",
        confidence=0.98,
        importance=0.90,
    )
    res = evaluate_candidate(cand)
    assert res.decision == MemoryCurationDecision.DEFER
    assert res.reason == MemoryCurationReason.DEFERRED_AMBIGUOUS_CATEGORY


def test_evaluate_candidate_reject_low_confidence() -> None:
    cand = _make_candidate(
        category=MemoryCategory.FACT,
        content="User might have visited Paris.",
        confidence=0.65,
        importance=0.80,
    )
    res = evaluate_candidate(cand)
    assert res.decision == MemoryCurationDecision.REJECT
    assert res.reason == MemoryCurationReason.REJECTED_LOW_CONFIDENCE


def test_evaluate_candidate_reject_low_importance() -> None:
    cand = _make_candidate(
        category=MemoryCategory.FACT,
        content="User blinked their eyes twice.",
        confidence=0.95,
        importance=0.25,
    )
    res = evaluate_candidate(cand)
    assert res.decision == MemoryCurationDecision.REJECT
    assert res.reason == MemoryCurationReason.REJECTED_LOW_IMPORTANCE


def test_evaluate_candidate_reject_secrets() -> None:
    cand = _make_candidate(
        category=MemoryCategory.FACT,
        content="User's OpenAI key is sk-abcdef1234567890abcdef1234567890.",
        confidence=0.99,
        importance=0.99,
    )
    res = evaluate_candidate(cand)
    assert res.decision == MemoryCurationDecision.REJECT
    assert res.reason == MemoryCurationReason.REJECTED_SECRET


def test_evaluate_candidate_reject_terminal_accepted() -> None:
    cand = _make_candidate(status=MemoryCandidateStatus.ACCEPTED)
    res = evaluate_candidate(cand)
    assert res.decision == MemoryCurationDecision.REJECT
    assert res.reason == MemoryCurationReason.REJECTED_TERMINAL


def test_evaluate_candidate_reject_terminal_rejected() -> None:
    cand = _make_candidate(status=MemoryCandidateStatus.REJECTED)
    res = evaluate_candidate(cand)
    assert res.decision == MemoryCurationDecision.REJECT
    assert res.reason == MemoryCurationReason.REJECTED_TERMINAL


def test_evaluate_candidate_defer_insufficient_salience() -> None:
    """Meets baseline confidence (>=0.70) and importance (>=0.30) but below category accept bar."""
    cand = _make_candidate(
        category=MemoryCategory.FACT,
        content="User likes the color teal.",
        confidence=0.82,  # < 0.90
        importance=0.50,  # < 0.60
    )
    res = evaluate_candidate(cand)
    assert res.decision == MemoryCurationDecision.DEFER
    assert res.reason == MemoryCurationReason.DEFERRED_INSUFFICIENT_SALIENCE


# =============================================================================
# 2. Curation Service Integration Tests (Async DB)
# =============================================================================


@pytest.mark.asyncio
async def test_curate_candidate_accept_lifecycle(test_session: AsyncSession) -> None:
    service = MemoryCurationService(test_session)
    cand = await service.create_candidate(
        category=MemoryCategory.FACT,
        content="User lives in Kyoto.",
        importance=0.80,
        confidence=0.95,
    )
    assert cand.status == MemoryCandidateStatus.PENDING

    evaluation = await service.curate_candidate(cand.id)
    assert evaluation.decision == MemoryCurationDecision.ACCEPT
    assert evaluation.reason == MemoryCurationReason.ACCEPTED_STABLE_FACT

    # Verify candidate status transitioned to ACCEPTED
    updated_cand = await service.get_candidate(cand.id)
    assert updated_cand is not None
    assert updated_cand.status == MemoryCandidateStatus.ACCEPTED
    assert updated_cand.version == 2

    # Verify persistent Memory record created
    mem_query = select(MemoryRecord).where(MemoryRecord.content == "User lives in Kyoto.")
    mem_res = await test_session.scalars(mem_query)
    mem = mem_res.first()
    assert mem is not None
    assert mem.category == MemoryCategory.FACT.value
    assert mem.confidence == 0.95


@pytest.mark.asyncio
async def test_curate_candidate_reject_low_confidence(test_session: AsyncSession) -> None:
    service = MemoryCurationService(test_session)
    cand = await service.create_candidate(
        category=MemoryCategory.FACT,
        content="User might visit Sapporo.",
        importance=0.70,
        confidence=0.50,
    )

    evaluation = await service.curate_candidate(cand.id)
    assert evaluation.decision == MemoryCurationDecision.REJECT
    assert evaluation.reason == MemoryCurationReason.REJECTED_LOW_CONFIDENCE

    updated_cand = await service.get_candidate(cand.id)
    assert updated_cand is not None
    assert updated_cand.status == MemoryCandidateStatus.REJECTED

    # No memory record should exist
    mem_query = select(MemoryRecord).where(MemoryRecord.content == "User might visit Sapporo.")
    mem_res = await test_session.scalars(mem_query)
    assert mem_res.first() is None


@pytest.mark.asyncio
async def test_curate_candidate_reject_secret(test_session: AsyncSession) -> None:
    service = MemoryCurationService(test_session)
    cand = await service.create_candidate(
        category=MemoryCategory.FACT,
        content="User's API token is ghp_123456789012345678901234567890123456.",
        importance=0.90,
        confidence=0.95,
    )

    evaluation = await service.curate_candidate(cand.id)
    assert evaluation.decision == MemoryCurationDecision.REJECT
    assert evaluation.reason == MemoryCurationReason.REJECTED_SECRET

    updated_cand = await service.get_candidate(cand.id)
    assert updated_cand is not None
    assert updated_cand.status == MemoryCandidateStatus.REJECTED


@pytest.mark.asyncio
async def test_curate_candidate_reject_duplicate(test_session: AsyncSession) -> None:
    """If an identical persistent memory already exists, curate_candidate rejects with REJECTED_DUPLICATE."""
    # 1. Manually seed a persistent memory
    await create_memory(
        session=test_session,
        category=MemoryCategory.FACT,
        content="User speaks fluent Japanese.",
        importance=0.8,
        confidence=0.95,
    )

    # 2. Create candidate with identical content and high confidence
    service = MemoryCurationService(test_session)
    cand = await service.create_candidate(
        category=MemoryCategory.FACT,
        content="  User speaks fluent Japanese.  ",
        importance=0.85,
        confidence=0.95,
    )

    evaluation = await service.curate_candidate(cand.id)
    assert evaluation.decision == MemoryCurationDecision.REJECT
    assert evaluation.reason == MemoryCurationReason.REJECTED_DUPLICATE

    updated_cand = await service.get_candidate(cand.id)
    assert updated_cand is not None
    assert updated_cand.status == MemoryCandidateStatus.REJECTED


@pytest.mark.asyncio
async def test_curate_candidate_defer_remains_pending(test_session: AsyncSession) -> None:
    service = MemoryCurationService(test_session)
    cand = await service.create_candidate(
        category=MemoryCategory.EXPERIENCE,
        content="User felt relaxed while walking in the park.",
        importance=0.85,
        confidence=0.95,
    )

    evaluation = await service.curate_candidate(cand.id)
    assert evaluation.decision == MemoryCurationDecision.DEFER
    assert evaluation.reason == MemoryCurationReason.DEFERRED_AMBIGUOUS_CATEGORY

    # Candidate MUST remain PENDING
    updated_cand = await service.get_candidate(cand.id)
    assert updated_cand is not None
    assert updated_cand.status == MemoryCandidateStatus.PENDING
    assert updated_cand.version == 1


@pytest.mark.asyncio
async def test_curate_candidate_terminal_state_handling(test_session: AsyncSession) -> None:
    service = MemoryCurationService(test_session)
    cand = await service.create_candidate(
        category=MemoryCategory.FACT,
        content="User likes green tea.",
        importance=0.8,
        confidence=0.95,
    )
    # First curate: accepted
    eval1 = await service.curate_candidate(cand.id)
    assert eval1.decision == MemoryCurationDecision.ACCEPT

    # Second curate: already terminal
    eval2 = await service.curate_candidate(cand.id)
    assert eval2.decision == MemoryCurationDecision.REJECT
    assert eval2.reason == MemoryCurationReason.REJECTED_TERMINAL


@pytest.mark.asyncio
async def test_curate_candidate_not_found(test_session: AsyncSession) -> None:
    service = MemoryCurationService(test_session)
    with pytest.raises(CandidateNotFoundError):
        await service.curate_candidate("nonexistent-candidate-id")


# =============================================================================
# 3. Batch Curation Tests
# =============================================================================


@pytest.mark.asyncio
async def test_curate_pending_candidates_batch(test_session: AsyncSession) -> None:
    service = MemoryCurationService(test_session)

    # Seed 5 candidates:
    # 1: Acceptable Fact
    c1 = await service.create_candidate(
        category=MemoryCategory.FACT,
        content="User has a cat named Luna.",
        importance=0.80,
        confidence=0.95,
    )
    # 2: Low confidence Fact (Reject)
    c2 = await service.create_candidate(
        category=MemoryCategory.FACT,
        content="User might like dogs.",
        importance=0.70,
        confidence=0.40,
    )
    # 3: Acceptable User Goal
    c3 = await service.create_candidate(
        category=MemoryCategory.USER_GOAL,
        content="User wants to learn Rust.",
        importance=0.80,
        confidence=0.92,
    )
    # 4: Ambiguous category Experience (Defer)
    c4 = await service.create_candidate(
        category=MemoryCategory.EXPERIENCE,
        content="User enjoyed the sunset.",
        importance=0.90,
        confidence=0.95,
    )
    # 5: Secret (Reject)
    c5 = await service.create_candidate(
        category=MemoryCategory.FACT,
        content="password = supersecret1234",
        importance=0.90,
        confidence=0.95,
    )

    batch_result = await service.curate_pending_candidates(batch_size=10)

    assert batch_result.total_evaluated == 5
    assert batch_result.accepted_candidate_ids == (c1.id, c3.id)
    assert batch_result.rejected_candidate_ids == (c2.id, c5.id)
    assert batch_result.deferred_candidate_ids == (c4.id,)


    # Verify status in database
    c1_db = await service.get_candidate(c1.id)
    c2_db = await service.get_candidate(c2.id)
    c3_db = await service.get_candidate(c3.id)
    c4_db = await service.get_candidate(c4.id)
    c5_db = await service.get_candidate(c5.id)

    assert c1_db and c1_db.status == MemoryCandidateStatus.ACCEPTED
    assert c2_db and c2_db.status == MemoryCandidateStatus.REJECTED
    assert c3_db and c3_db.status == MemoryCandidateStatus.ACCEPTED
    assert c4_db and c4_db.status == MemoryCandidateStatus.PENDING
    assert c5_db and c5_db.status == MemoryCandidateStatus.REJECTED


@pytest.mark.asyncio
async def test_curate_pending_candidates_bounded_batch_size(test_session: AsyncSession) -> None:
    service = MemoryCurationService(test_session)

    # Seed 5 candidates
    for i in range(5):
        await service.create_candidate(
            category=MemoryCategory.FACT,
            content=f"Fact number {i}",
            importance=0.8,
            confidence=0.95,
        )

    # Batch size bounded to 2
    batch_result = await service.curate_pending_candidates(batch_size=2)
    assert batch_result.total_evaluated == 2
    assert len(batch_result.accepted_candidate_ids) == 2

    # 3 remaining candidates should still be PENDING
    pending = await service.list_candidates(status=MemoryCandidateStatus.PENDING)
    assert len(pending) == 3


@pytest.mark.asyncio
async def test_convenience_functions(test_session: AsyncSession) -> None:
    service = MemoryCurationService(test_session)
    cand = await service.create_candidate(
        category=MemoryCategory.FACT,
        content="User has a garden.",
        importance=0.8,
        confidence=0.95,
    )

    # Test curate_memory_candidate convenience
    eval_res = await curate_memory_candidate(test_session, cand.id)
    assert eval_res.decision == MemoryCurationDecision.ACCEPT

    # Test curate_pending_memory_candidates convenience
    batch_res = await curate_pending_memory_candidates(test_session, batch_size=5)
    assert batch_res.total_evaluated == 0  # No more pending


# =============================================================================
# 4. Architecture & Configuration Tests
# =============================================================================


def test_feature_flag_config_default() -> None:
    from app.core.config import Settings
    s = Settings()
    assert hasattr(s, "memory_auto_curation_enabled")
    assert s.memory_auto_curation_enabled is False



def test_no_llm_imports_in_curation_policy() -> None:
    """Verify curation_policy has zero LLM provider or external network dependencies."""
    import sys
    import app.memory.curation_policy as policy_mod

    # Inspect module source / symbols
    policy_file = policy_mod.__file__
    with open(policy_file, "r", encoding="utf-8") as f:
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
    ]
    for term in forbidden_terms:
        assert term not in content, f"Forbidden external/LLM dependency found in curation policy: {term}"
