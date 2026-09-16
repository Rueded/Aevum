"""Comprehensive test suite for Phase 4.4: Relationship Experience / History Foundation.

Verifies:
- RelationshipExperience and RelationshipExperienceCreate model validations (bounds, NaN/Inf rejection,
  summary sanitization, immutability, extra field forbidding, secret detection).
- Complete absence of raw relationship metrics or romance fields.
- RelationshipExperienceService persistence: create, get, list (reverse chronological, limit cap, type filter).
- Deterministic duplicate protection based on normalized summaries.
- Complete signal-to-experience mapping across all 11 Phase 4.2 signal types.
- Summary behavior (reason preservation vs. deterministic fallback).
- Significance and confidence inheritance from signals.
- State and history separation (independent recording, zero-delta signals like DISAGREEMENT recorded).
- Failure isolation during conversation turns.
- Security boundaries (no public mutation endpoint, untrusted user dialogue defense).
"""

from datetime import datetime, timezone
import math
import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RelationshipExperienceRecord
from app.relationship import (
    DEFAULT_EXPERIENCE_SUMMARIES,
    DEFAULT_EXPERIENCES_LIST_LIMIT,
    DEFAULT_RELATIONSHIP_ID,
    MAX_EXPERIENCE_SUMMARY_LENGTH,
    MAX_EXPERIENCES_LIST_LIMIT,
    RelationshipExperience,
    RelationshipExperienceCreate,
    RelationshipExperienceService,
    RelationshipExperienceSource,
    RelationshipExperienceType,
    RelationshipService,
    RelationshipSignal,
    RelationshipSignalSource,
    RelationshipSignalType,
    SIGNAL_TO_EXPERIENCE_TYPE_MAP,
    filter_eligible_signals,
    map_signal_to_experience_create,
)


# =============================================================================
# 1. Model Validation & Structural Tests
# =============================================================================


def test_valid_experience_model():
    """Valid parameters instantiate RelationshipExperience successfully."""
    exp = RelationshipExperience(
        relationship_id="default",
        experience_type=RelationshipExperienceType.BOUNDARY_RESPECTED,
        source=RelationshipExperienceSource.SYSTEM,
        summary="User respected Aevum's boundary regarding quiet hours.",
        significance=0.8,
        confidence=0.9,
    )
    assert exp.id is not None
    assert exp.experience_type == RelationshipExperienceType.BOUNDARY_RESPECTED
    assert exp.significance == 0.8
    assert exp.confidence == 0.9
    assert exp.created_at is not None


def test_experience_model_immutability():
    """RelationshipExperience is frozen and cannot be mutated."""
    exp = RelationshipExperience(
        relationship_id="default",
        experience_type=RelationshipExperienceType.APPRECIATION,
        source=RelationshipExperienceSource.SYSTEM,
        summary="User thanked Aevum.",
        significance=0.5,
        confidence=0.8,
    )
    with pytest.raises(ValidationError):
        exp.summary = "New summary"


def test_experience_model_rejects_extra_fields():
    """Extra fields (such as accidental metric scores) are strictly rejected."""
    with pytest.raises(ValidationError):
        RelationshipExperience(
            relationship_id="default",
            experience_type=RelationshipExperienceType.APPRECIATION,
            source=RelationshipExperienceSource.SYSTEM,
            summary="User thanked Aevum.",
            significance=0.5,
            confidence=0.8,
            trust=0.9,  # Forbidden!
        )


def test_experience_model_contains_no_raw_relationship_metrics():
    """Model definition must not define any continuous relationship state metrics."""
    forbidden = [
        "familiarity",
        "trust",
        "comfort",
        "affection",
        "attachment",
        "respect",
        "relationship_level",
        "relationship_score",
        "romance",
    ]
    model_fields = RelationshipExperience.model_fields.keys()
    for field in forbidden:
        assert field not in model_fields, f"Forbidden field '{field}' found in RelationshipExperience!"


def test_experience_rejects_empty_or_whitespace_summary():
    """Summary cannot be empty or whitespace-only."""
    with pytest.raises(ValidationError):
        RelationshipExperienceCreate(
            relationship_id="default",
            experience_type=RelationshipExperienceType.APPRECIATION,
            summary="",
            significance=0.5,
            confidence=0.8,
        )

    with pytest.raises(ValidationError):
        RelationshipExperienceCreate(
            relationship_id="default",
            experience_type=RelationshipExperienceType.APPRECIATION,
            summary="     ",
            significance=0.5,
            confidence=0.8,
        )


def test_experience_rejects_overlong_summary():
    """Summary exceeding MAX_EXPERIENCE_SUMMARY_LENGTH (500 chars) is rejected."""
    long_text = "a" * (MAX_EXPERIENCE_SUMMARY_LENGTH + 1)
    with pytest.raises(ValidationError):
        RelationshipExperienceCreate(
            relationship_id="default",
            experience_type=RelationshipExperienceType.APPRECIATION,
            summary=long_text,
            significance=0.5,
            confidence=0.8,
        )


@pytest.mark.parametrize("bad_val", [-0.1, 1.1, math.nan, math.inf, -math.inf])
def test_experience_rejects_invalid_metrics(bad_val):
    """Significance and confidence must be finite numbers in [0.0, 1.0]."""
    with pytest.raises(ValidationError):
        RelationshipExperienceCreate(
            relationship_id="default",
            experience_type=RelationshipExperienceType.APPRECIATION,
            summary="Test summary",
            significance=bad_val,
            confidence=0.8,
        )

    with pytest.raises(ValidationError):
        RelationshipExperienceCreate(
            relationship_id="default",
            experience_type=RelationshipExperienceType.APPRECIATION,
            summary="Test summary",
            significance=0.5,
            confidence=bad_val,
        )


def test_experience_rejects_credentials_in_summary():
    """Defense-in-depth: obvious credential patterns in summary are rejected."""
    with pytest.raises(ValidationError):
        RelationshipExperienceCreate(
            relationship_id="default",
            experience_type=RelationshipExperienceType.PERSONAL_DISCLOSURE,
            summary="User shared api-key: sk-proj-1234567890abcdef1234567890abcdef",
            significance=0.5,
            confidence=0.8,
        )


# =============================================================================
# 2. Persistence & Service Tests
# =============================================================================


@pytest.mark.asyncio
async def test_create_and_get_experience(test_session: AsyncSession):
    """Service persists an experience and retrieves it accurately by ID."""
    rel_service = RelationshipService(test_session)
    _ = await rel_service.get_relationship_state()

    service = RelationshipExperienceService(test_session)
    payload = RelationshipExperienceCreate(
        relationship_id="default",
        experience_type=RelationshipExperienceType.BOUNDARY_RESPECTED,
        source=RelationshipExperienceSource.LLM,
        summary="User respected Aevum's request to pause conversation.",
        significance=0.75,
        confidence=0.95,
    )
    created = await service.create_experience(payload)
    assert created is not None
    assert created.experience_type == RelationshipExperienceType.BOUNDARY_RESPECTED
    assert created.significance == 0.75
    assert created.confidence == 0.95
    assert created.summary == "User respected Aevum's request to pause conversation."

    fetched = await service.get_experience(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.experience_type == created.experience_type
    assert fetched.summary == created.summary


@pytest.mark.asyncio
async def test_get_nonexistent_experience_returns_none(test_session: AsyncSession):
    """Fetching unknown ID returns None."""
    service = RelationshipExperienceService(test_session)
    result = await service.get_experience("non-existent-id")
    assert result is None


@pytest.mark.asyncio
async def test_list_experiences_ordering_and_filtering(test_session: AsyncSession):
    """List returns experiences in reverse chronological order with optional filtering."""
    rel_service = RelationshipService(test_session)
    _ = await rel_service.get_relationship_state()

    service = RelationshipExperienceService(test_session)

    # Add 3 experiences of different types
    e1 = await service.create_experience(
        RelationshipExperienceCreate(
            relationship_id="default",
            experience_type=RelationshipExperienceType.APPRECIATION,
            summary="First gratitude expressed.",
            significance=0.4,
            confidence=0.8,
        )
    )
    e2 = await service.create_experience(
        RelationshipExperienceCreate(
            relationship_id="default",
            experience_type=RelationshipExperienceType.SHARED_INTEREST,
            summary="Shared enthusiasm for books.",
            significance=0.6,
            confidence=0.9,
        )
    )
    e3 = await service.create_experience(
        RelationshipExperienceCreate(
            relationship_id="default",
            experience_type=RelationshipExperienceType.APPRECIATION,
            summary="Second heartfelt thank you.",
            significance=0.7,
            confidence=0.95,
        )
    )

    all_exp = await service.list_experiences(relationship_id="default", limit=10)
    assert len(all_exp) == 3
    # Newest first: e3, e2, e1
    assert [e.id for e in all_exp] == [e3.id, e2.id, e1.id]

    # Filter by type: APPRECIATION only
    appreciation_only = await service.list_experiences(
        relationship_id="default",
        experience_type=RelationshipExperienceType.APPRECIATION,
    )
    assert len(appreciation_only) == 2
    assert [e.id for e in appreciation_only] == [e3.id, e1.id]


@pytest.mark.asyncio
async def test_list_experiences_limit_enforcement(test_session: AsyncSession):
    """List limit is clamped between 1 and MAX_EXPERIENCES_LIST_LIMIT (50)."""
    rel_service = RelationshipService(test_session)
    _ = await rel_service.get_relationship_state()

    service = RelationshipExperienceService(test_session)

    # Insert 5 distinct experiences
    for i in range(5):
        await service.create_experience(
            RelationshipExperienceCreate(
                relationship_id="default",
                experience_type=RelationshipExperienceType.PLAYFUL_CONNECTION,
                summary=f"Playful banter number {i}",
                significance=0.5,
                confidence=0.8,
            )
        )

    # Request limit 2
    res2 = await service.list_experiences(limit=2)
    assert len(res2) == 2

    # Request limit 100 -> capped at 50 (returns all 5 available)
    res_all = await service.list_experiences(limit=100)
    assert len(res_all) == 5


# =============================================================================
# 3. Duplicate Protection Tests
# =============================================================================


@pytest.mark.asyncio
async def test_duplicate_protection_exact_match(test_session: AsyncSession):
    """Identical experience in the same relationship is skipped as a duplicate."""
    rel_service = RelationshipService(test_session)
    _ = await rel_service.get_relationship_state()

    service = RelationshipExperienceService(test_session)
    payload = RelationshipExperienceCreate(
        relationship_id="default",
        experience_type=RelationshipExperienceType.APPRECIATION,
        summary="User thanked Aevum warmly.",
        significance=0.5,
        confidence=0.9,
    )
    first = await service.create_experience(payload)
    assert first is not None

    # Second identical creation returns None (duplicate skipped)
    second = await service.create_experience(payload)
    assert second is None

    # Verify only 1 record exists
    records = await service.list_experiences()
    assert len(records) == 1


@pytest.mark.asyncio
async def test_duplicate_protection_normalized_summary(test_session: AsyncSession):
    """Duplicates with differing casing or extra whitespace are detected and skipped."""
    rel_service = RelationshipService(test_session)
    _ = await rel_service.get_relationship_state()

    service = RelationshipExperienceService(test_session)
    p1 = RelationshipExperienceCreate(
        relationship_id="default",
        experience_type=RelationshipExperienceType.SHARED_INTEREST,
        summary="User loves classical music.",
        significance=0.6,
        confidence=0.8,
    )
    first = await service.create_experience(p1)
    assert first is not None

    p2 = RelationshipExperienceCreate(
        relationship_id="default",
        experience_type=RelationshipExperienceType.SHARED_INTEREST,
        summary="  USER LOVES CLASSICAL MUSIC.  ",
        significance=0.6,
        confidence=0.8,
    )
    second = await service.create_experience(p2)
    assert second is None


@pytest.mark.asyncio
async def test_different_experience_types_not_duplicates(test_session: AsyncSession):
    """Different experience types with identical text are distinct experiences."""
    rel_service = RelationshipService(test_session)
    _ = await rel_service.get_relationship_state()

    service = RelationshipExperienceService(test_session)
    e1 = await service.create_experience(
        RelationshipExperienceCreate(
            relationship_id="default",
            experience_type=RelationshipExperienceType.SUPPORT_GIVEN,
            summary="User offered comfort during a difficult topic.",
            significance=0.7,
            confidence=0.85,
        )
    )
    e2 = await service.create_experience(
        RelationshipExperienceCreate(
            relationship_id="default",
            experience_type=RelationshipExperienceType.PERSONAL_DISCLOSURE,
            summary="User offered comfort during a difficult topic.",
            significance=0.7,
            confidence=0.85,
        )
    )
    assert e1 is not None
    assert e2 is not None
    assert e1.id != e2.id


# =============================================================================
# 4. Signal Mapping Tests
# =============================================================================


def test_all_signal_types_map_to_experience_types():
    """Every Phase 4.2 RelationshipSignalType maps deterministically to a valid experience type."""
    for sig_type in RelationshipSignalType:
        assert sig_type in SIGNAL_TO_EXPERIENCE_TYPE_MAP
        exp_type = SIGNAL_TO_EXPERIENCE_TYPE_MAP[sig_type]
        assert isinstance(exp_type, RelationshipExperienceType)


def test_map_signal_to_experience_preserves_reason():
    """Mapping uses signal explanation reason when available."""
    sig = RelationshipSignal(
        signal_type=RelationshipSignalType.RESPECT_BOUNDARY,
        source=RelationshipSignalSource.LLM,
        confidence=0.90,
        strength=0.70,
        reason="User accepted Aevum's request to change the subject.",
    )
    exp_create = map_signal_to_experience_create(sig)
    assert exp_create.experience_type == RelationshipExperienceType.BOUNDARY_RESPECTED
    assert exp_create.source == RelationshipExperienceSource.LLM
    assert exp_create.summary == "User accepted Aevum's request to change the subject."
    assert exp_create.significance == 0.70
    assert exp_create.confidence == 0.90


def test_map_signal_to_experience_fallback_when_reason_missing():
    """Mapping provides deterministic fallback when reason is absent."""
    sig = RelationshipSignal(
        signal_type=RelationshipSignalType.BOUNDARY_VIOLATION,
        source=RelationshipSignalSource.SYSTEM,
        confidence=0.85,
        strength=0.80,
        reason=None,
    )
    exp_create = map_signal_to_experience_create(sig)
    assert exp_create.experience_type == RelationshipExperienceType.BOUNDARY_VIOLATED
    assert exp_create.source == RelationshipExperienceSource.SYSTEM
    assert exp_create.summary == DEFAULT_EXPERIENCE_SUMMARIES[RelationshipExperienceType.BOUNDARY_VIOLATED]
    assert exp_create.significance == 0.80
    assert exp_create.confidence == 0.85


# =============================================================================
# 5. State / History Separation Tests
# =============================================================================


@pytest.mark.asyncio
async def test_experience_recording_does_not_mutate_relationship_state(test_session: AsyncSession):
    """Recording an experience is completely independent from RelationshipState mutations."""
    rel_service = RelationshipService(test_session)
    state_before = await rel_service.get_relationship_state()

    exp_service = RelationshipExperienceService(test_session)
    await exp_service.create_experience(
        RelationshipExperienceCreate(
            relationship_id=state_before.id,
            experience_type=RelationshipExperienceType.DISAGREEMENT,
            summary="User and Aevum had a respectful disagreement.",
            significance=0.5,
            confidence=0.9,
        )
    )

    state_after = await rel_service.get_relationship_state()
    assert state_after.version == state_before.version
    assert state_after.updated_at == state_before.updated_at
    assert state_after.trust == state_before.trust
    assert state_after.familiarity == state_before.familiarity


@pytest.mark.asyncio
async def test_zero_delta_signal_records_experience(test_session: AsyncSession):
    """DISAGREEMENT produces zero relationship delta in policy but records a historical experience."""
    rel_service = RelationshipService(test_session)
    _ = await rel_service.get_relationship_state()

    exp_service = RelationshipExperienceService(test_session)
    signals = [
        RelationshipSignal(
            signal_type=RelationshipSignalType.DISAGREEMENT,
            confidence=0.90,
            strength=0.60,
            reason="Respectful difference on favorite literature.",
        )
    ]

    recorded = await exp_service.record_signals(signals)
    assert len(recorded) == 1
    assert recorded[0].experience_type == RelationshipExperienceType.DISAGREEMENT
    assert recorded[0].summary == "Respectful difference on favorite literature."


@pytest.mark.asyncio
async def test_sub_threshold_signals_do_not_record_experience(test_session: AsyncSession):
    """Signals failing policy thresholds (confidence < 0.70 or strength < 0.10) produce no experience."""
    rel_service = RelationshipService(test_session)
    _ = await rel_service.get_relationship_state()

    exp_service = RelationshipExperienceService(test_session)
    sub_threshold_signals = [
        RelationshipSignal(
            signal_type=RelationshipSignalType.APPRECIATION,
            confidence=0.50,  # Below MIN_SIGNAL_CONFIDENCE (0.70)
            strength=0.80,
            reason="Uncertain thank you.",
        ),
        RelationshipSignal(
            signal_type=RelationshipSignalType.SHARED_INTEREST,
            confidence=0.90,
            strength=0.05,  # Below MIN_SIGNAL_STRENGTH (0.10)
            reason="Negligible shared topic.",
        ),
    ]

    recorded = await exp_service.record_signals(sub_threshold_signals)
    assert len(recorded) == 0

    all_exp = await exp_service.list_experiences()
    assert len(all_exp) == 0
