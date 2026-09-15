"""Tests for Phase 2.3: Character State Mutation Foundation.

Validates CharacterStateUpdate partial state replacement model, validation rules,
atomic partial application, SQL-level optimistic concurrency protection,
and architectural independence from LLMs, Conversation, Memory, Relationship,
Emotion Engine, and Life Simulation.
"""

import ast
from datetime import datetime, timezone
import inspect
import math
import pytest
import pydantic
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.character import (
    CharacterMood,
    CharacterState,
    CharacterStateConflictError,
    CharacterStateService,
    CharacterStateUpdate,
    apply_character_state_update,
    get_character_state,
)
from app.db.models import CharacterStateRecord
from app.db.session import Base


# ==============================================================================
# 1. Model Tests
# ==============================================================================

def test_valid_single_field_update():
    """Valid single-field update is instantiated successfully."""
    update = CharacterStateUpdate(energy=0.45)
    assert update.energy == 0.45
    assert update.stress is None
    assert update.mood is None


def test_valid_multi_field_update():
    """Valid multi-field update is instantiated successfully."""
    update = CharacterStateUpdate(
        mood=CharacterMood.FOCUSED,
        energy=0.85,
        stress=0.15,
        current_activity="studying computer science",
        current_location="library",
    )
    assert update.mood == CharacterMood.FOCUSED
    assert update.energy == 0.85
    assert update.stress == 0.15
    assert update.current_activity == "studying computer science"
    assert update.current_location == "library"
    assert update.social_energy is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("mood", CharacterMood.CALM),
        ("energy", 0.5),
        ("stress", 0.3),
        ("social_energy", 0.8),
        ("confidence", 0.9),
        ("irritation", 0.1),
        ("loneliness", 0.4),
        ("current_activity", "walking in the park"),
        ("current_location", "outside"),
    ],
)
def test_all_supported_fields_individually(field: str, value):
    """Every supported field can be updated individually."""
    update = CharacterStateUpdate(**{field: value})
    assert getattr(update, field) == value


def test_empty_update_rejected():
    """A mutation request containing zero specified fields is rejected."""
    with pytest.raises(pydantic.ValidationError) as exc_info:
        CharacterStateUpdate()

    assert "at least one field to update" in str(exc_info.value)


def test_invalid_mood_rejected():
    """Invalid mood values outside CharacterMood enum are rejected."""
    with pytest.raises(pydantic.ValidationError):
        CharacterStateUpdate(mood="euphoric")  # type: ignore


@pytest.mark.parametrize(
    "metric",
    ["energy", "stress", "social_energy", "confidence", "irritation", "loneliness"],
)
def test_out_of_range_metrics_rejected(metric: str):
    """Normalized metrics below 0.0 or above 1.0 are rejected."""
    with pytest.raises(pydantic.ValidationError):
        CharacterStateUpdate(**{metric: -0.05})

    with pytest.raises(pydantic.ValidationError):
        CharacterStateUpdate(**{metric: 1.05})


@pytest.mark.parametrize(
    "metric",
    ["energy", "stress", "social_energy", "confidence", "irritation", "loneliness"],
)
def test_nan_and_inf_metrics_rejected(metric: str):
    """NaN and infinite values are rejected on all numeric mutation fields."""
    with pytest.raises(pydantic.ValidationError):
        CharacterStateUpdate(**{metric: float("nan")})

    with pytest.raises(pydantic.ValidationError):
        CharacterStateUpdate(**{metric: float("inf")})

    with pytest.raises(pydantic.ValidationError):
        CharacterStateUpdate(**{metric: float("-inf")})


def test_empty_or_whitespace_strings_rejected():
    """Empty or whitespace-only activity and location strings are rejected."""
    with pytest.raises(pydantic.ValidationError):
        CharacterStateUpdate(current_activity="")

    with pytest.raises(pydantic.ValidationError):
        CharacterStateUpdate(current_activity="   \t")

    with pytest.raises(pydantic.ValidationError):
        CharacterStateUpdate(current_location="")

    with pytest.raises(pydantic.ValidationError):
        CharacterStateUpdate(current_location="   \n")


def test_extra_fields_rejected():
    """Arbitrary extra fields are rejected via extra='forbid'."""
    with pytest.raises(pydantic.ValidationError):
        CharacterStateUpdate(energy=0.5, happiness=0.9)  # type: ignore

    with pytest.raises(pydantic.ValidationError):
        CharacterStateUpdate(energy=0.5, reason="studied too long")  # type: ignore


def test_mutation_model_is_immutable():
    """CharacterStateUpdate cannot be mutated after instantiation."""
    update = CharacterStateUpdate(energy=0.5)
    with pytest.raises(pydantic.ValidationError):
        update.energy = 0.7  # type: ignore


# ==============================================================================
# 2. Service & Persistence Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_apply_single_field_update(test_session: AsyncSession):
    """Applying a single field update updates only that field and preserves others."""
    service = CharacterStateService(test_session)
    initial = await service.get_state("aevum")
    assert initial.version == 1
    assert initial.energy == 0.7

    update = CharacterStateUpdate(energy=0.4)
    updated = await service.apply_update(update, expected_version=1)

    assert updated.version == 2
    assert updated.energy == 0.4
    # All other fields must remain preserved
    assert updated.stress == initial.stress
    assert updated.social_energy == initial.social_energy
    assert updated.confidence == initial.confidence
    assert updated.irritation == initial.irritation
    assert updated.loneliness == initial.loneliness
    assert updated.mood == initial.mood
    assert updated.current_activity == initial.current_activity
    assert updated.current_location == initial.current_location
    assert updated.updated_at >= initial.updated_at


@pytest.mark.asyncio
async def test_apply_multi_field_update(test_session: AsyncSession):
    """Applying multiple fields updates specified fields and preserves unspecified ones."""
    service = CharacterStateService(test_session)
    initial = await service.get_state("aevum")

    update = CharacterStateUpdate(
        mood=CharacterMood.TIRED,
        energy=0.25,
        current_activity="falling asleep",
    )
    updated = await service.apply_update(update, expected_version=1)

    assert updated.version == 2
    assert updated.mood == CharacterMood.TIRED
    assert updated.energy == 0.25
    assert updated.current_activity == "falling asleep"
    # Unspecified fields preserved
    assert updated.stress == initial.stress
    assert updated.social_energy == initial.social_energy
    assert updated.current_location == initial.current_location


@pytest.mark.asyncio
async def test_version_increments_exactly_once(test_session: AsyncSession):
    """Version increments by exactly 1 per mutation."""
    service = CharacterStateService(test_session)
    s1 = await service.get_state("aevum")
    assert s1.version == 1

    s2 = await service.apply_update(CharacterStateUpdate(energy=0.6))
    assert s2.version == 2

    s3 = await service.apply_update(CharacterStateUpdate(stress=0.4))
    assert s3.version == 3


@pytest.mark.asyncio
async def test_mutation_survives_session_boundary(test_engine):
    """Mutated character state persists across separate database sessions."""
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session1:
        service1 = CharacterStateService(session1)
        await service1.get_state("aevum")
        updated = await service1.apply_update(
            CharacterStateUpdate(energy=0.35, current_activity="resting after walk"),
            expected_version=1,
        )
        assert updated.version == 2

    async with session_factory() as session2:
        service2 = CharacterStateService(session2)
        loaded = await service2.get_state("aevum")
        assert loaded.version == 2
        assert loaded.energy == 0.35
        assert loaded.current_activity == "resting after walk"


@pytest.mark.asyncio
async def test_mutation_survives_backend_restart_simulation(tmp_path):
    """Mutated state persists across complete process restart on disk."""
    db_file = tmp_path / "mutation_restart_test.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    # 1. Process 1: seed and mutate
    engine1 = create_async_engine(db_url, echo=False)
    async with engine1.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory1 = async_sessionmaker(bind=engine1, class_=AsyncSession, expire_on_commit=False)
    async with session_factory1() as session1:
        service1 = CharacterStateService(session1)
        await service1.get_state("aevum")
        saved = await service1.apply_update(
            CharacterStateUpdate(
                mood=CharacterMood.GOOD,
                social_energy=0.9,
                current_activity="chatting with friend",
                current_location="cafe",
            ),
            expected_version=1,
        )
        assert saved.version == 2
        saved_updated_at = saved.updated_at

    await engine1.dispose()

    # 2. Process 2: new engine and session loading same SQLite file
    engine2 = create_async_engine(db_url, echo=False)
    session_factory2 = async_sessionmaker(bind=engine2, class_=AsyncSession, expire_on_commit=False)
    async with session_factory2() as session2:
        service2 = CharacterStateService(session2)
        loaded = await service2.get_state("aevum")
        assert loaded.version == 2
        assert loaded.mood == CharacterMood.GOOD
        assert loaded.social_energy == 0.9
        assert loaded.current_activity == "chatting with friend"
        assert loaded.current_location == "cafe"
        assert loaded.updated_at == saved_updated_at

    await engine2.dispose()


@pytest.mark.asyncio
async def test_deterministic_initialization_on_empty_db(test_session: AsyncSession):
    """Calling apply_update on empty database initializes deterministic baseline first."""
    service = CharacterStateService(test_session)
    # Apply update directly without calling get_state first
    updated = await service.apply_update(
        CharacterStateUpdate(irritation=0.2),
        expected_version=1,
    )
    assert updated.version == 2
    assert updated.irritation == 0.2
    assert updated.mood == CharacterMood.NEUTRAL
    assert updated.energy == 0.7


# ==============================================================================
# 3. Atomicity & Concurrency Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_stale_expected_version_rejected(test_session: AsyncSession):
    """Database-enforced optimistic concurrency rejects updates with mismatched version."""
    service = CharacterStateService(test_session)
    initial = await service.get_state("aevum")
    assert initial.version == 1

    # Writer attempts mutation with stale expected version 99
    with pytest.raises(CharacterStateConflictError) as exc_info:
        await service.apply_update(CharacterStateUpdate(energy=0.1), expected_version=99)

    assert exc_info.value.expected_version == 99
    assert exc_info.value.actual_version == 1

    # State must be untouched
    current = await service.get_state("aevum")
    assert current.version == 1
    assert current.energy == initial.energy


@pytest.mark.asyncio
async def test_concurrent_writer_conflict_protection(test_engine):
    """Writer B cannot overwrite Writer A when operating on the same initial version."""
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    # Initialize baseline state
    async with session_factory() as session_init:
        init_service = CharacterStateService(session_init)
        await init_service.get_state("aevum")  # version 1

    # Writer A and Writer B both read version 1
    async with session_factory() as session_a, session_factory() as session_b:
        service_a = CharacterStateService(session_a)
        service_b = CharacterStateService(session_b)

        state_a = await service_a.get_state("aevum")
        state_b = await service_b.get_state("aevum")
        assert state_a.version == 1
        assert state_b.version == 1

        # Writer A succeeds and advances to version 2
        updated_a = await service_a.apply_update(
            CharacterStateUpdate(energy=0.5),
            expected_version=1,
        )
        assert updated_a.version == 2

        # Writer B attempts to update expecting version 1 -> must raise conflict
        with pytest.raises(CharacterStateConflictError) as exc_info:
            await service_b.apply_update(
                CharacterStateUpdate(energy=0.9),
                expected_version=1,
            )

        assert exc_info.value.expected_version == 1
        assert exc_info.value.actual_version == 2

    # Verify Writer A's state persisted and Writer B did NOT overwrite
    async with session_factory() as session_check:
        service_check = CharacterStateService(session_check)
        final_state = await service_check.get_state("aevum")
        assert final_state.version == 2
        assert final_state.energy == 0.5  # Writer A value, NOT Writer B value 0.9


@pytest.mark.asyncio
async def test_convenience_function(test_session: AsyncSession):
    """Verify apply_character_state_update convenience helper."""
    s1 = await get_character_state(test_session)
    assert s1.version == 1

    s2 = await apply_character_state_update(
        test_session,
        CharacterStateUpdate(confidence=0.85),
        expected_version=1,
    )
    assert s2.version == 2
    assert s2.confidence == 0.85


# ==============================================================================
# 4. Architecture Isolation Tests
# ==============================================================================

def _get_imported_modules(module) -> set[str]:
    """Extract all module names imported by a module via AST."""
    source = inspect.getsource(module)
    tree = ast.parse(source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports


def test_mutation_models_do_not_import_gemini():
    """State mutation models must not import Google GenAI or LLM SDKs."""
    import app.character.state_models as state_models

    imported = _get_imported_modules(state_models)
    for mod in imported:
        assert not any(x in mod.lower() for x in ["google", "genai", "gemini"]), (
            f"Unexpected LLM/Gemini import in state models: {mod}"
        )


def test_mutation_models_do_not_import_conversation():
    """State mutation models must not depend on Conversation or Message models."""
    import app.character.state_models as state_models

    imported = _get_imported_modules(state_models)
    for mod in imported:
        assert not any(x in mod.lower() for x in ["conversation", "message"]), (
            f"Unexpected conversation import in state models: {mod}"
        )


def test_mutation_models_do_not_import_memory_relationship_emotion_life():
    """State mutation models must not import speculative future subsystems."""
    import app.character.state_models as state_models

    imported = _get_imported_modules(state_models)
    for mod in imported:
        assert not any(x in mod.lower() for x in ["memory", "relationship", "emotion", "life", "event"]), (
            f"Unexpected subsystem import in state models: {mod}"
        )
