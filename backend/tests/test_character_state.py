"""Tests for Phase 2.2: Character State Foundation.

Validates CharacterMood, CharacterState domain model, validation constraints
(0.0-1.0 ranges, NaN/inf rejection, non-empty strings, immutability),
SQLite persistence in character_states table, optimistic concurrency control,
and architectural independence from LLM, Conversation, Memory, Relationship, and Emotion.
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
    create_initial_aevum_state,
    get_character_state,
    update_character_state,
)
from app.db.models import CharacterStateRecord
from app.db.session import Base


# ==============================================================================
# 1. Model Validation Tests
# ==============================================================================

def test_valid_character_state_accepted():
    """Valid CharacterState with all fields within constraints is accepted."""
    state = CharacterState(
        id="aevum",
        version=1,
        updated_at=datetime.now(timezone.utc),
        mood=CharacterMood.CALM,
        energy=0.8,
        stress=0.1,
        social_energy=0.5,
        confidence=0.8,
        irritation=0.0,
        loneliness=0.2,
        current_activity="reading a book",
        current_location="library",
    )
    assert state.id == "aevum"
    assert state.mood == CharacterMood.CALM
    assert state.energy == 0.8
    assert state.current_activity == "reading a book"
    assert state.current_location == "library"


def test_invalid_mood_rejected():
    """Undefined mood values outside CharacterMood are rejected."""
    with pytest.raises(pydantic.ValidationError):
        CharacterState(  # type: ignore
            id="aevum",
            version=1,
            updated_at=datetime.now(timezone.utc),
            mood="euphoric",  # type: ignore
            energy=0.5,
            stress=0.2,
            social_energy=0.5,
            confidence=0.5,
            irritation=0.0,
            loneliness=0.2,
            current_activity="resting",
            current_location="home",
        )


@pytest.mark.parametrize(
    "metric",
    ["energy", "stress", "social_energy", "confidence", "irritation", "loneliness"],
)
def test_out_of_range_metrics_rejected(metric: str):
    """Normalized metrics below 0.0 or above 1.0 are rejected."""
    base_kwargs = {
        "id": "aevum",
        "version": 1,
        "updated_at": datetime.now(timezone.utc),
        "mood": CharacterMood.NEUTRAL,
        "energy": 0.5,
        "stress": 0.2,
        "social_energy": 0.5,
        "confidence": 0.5,
        "irritation": 0.0,
        "loneliness": 0.2,
        "current_activity": "resting",
        "current_location": "home",
    }

    # Test below 0.0
    bad_low = {**base_kwargs, metric: -0.1}
    with pytest.raises(pydantic.ValidationError):
        CharacterState(**bad_low)

    # Test above 1.0
    bad_high = {**base_kwargs, metric: 1.1}
    with pytest.raises(pydantic.ValidationError):
        CharacterState(**bad_high)


@pytest.mark.parametrize(
    "metric",
    ["energy", "stress", "social_energy", "confidence", "irritation", "loneliness"],
)
def test_nan_and_inf_metrics_rejected(metric: str):
    """NaN and infinite values are rejected on all continuous metrics."""
    base_kwargs = {
        "id": "aevum",
        "version": 1,
        "updated_at": datetime.now(timezone.utc),
        "mood": CharacterMood.NEUTRAL,
        "energy": 0.5,
        "stress": 0.2,
        "social_energy": 0.5,
        "confidence": 0.5,
        "irritation": 0.0,
        "loneliness": 0.2,
        "current_activity": "resting",
        "current_location": "home",
    }

    # Test NaN
    with pytest.raises(pydantic.ValidationError):
        CharacterState(**{**base_kwargs, metric: float("nan")})

    # Test inf
    with pytest.raises(pydantic.ValidationError):
        CharacterState(**{**base_kwargs, metric: float("inf")})

    # Test -inf
    with pytest.raises(pydantic.ValidationError):
        CharacterState(**{**base_kwargs, metric: float("-inf")})


def test_empty_or_whitespace_activity_rejected():
    """Empty or whitespace-only current_activity is rejected."""
    base_kwargs = {
        "id": "aevum",
        "version": 1,
        "updated_at": datetime.now(timezone.utc),
        "mood": CharacterMood.NEUTRAL,
        "energy": 0.5,
        "stress": 0.2,
        "social_energy": 0.5,
        "confidence": 0.5,
        "irritation": 0.0,
        "loneliness": 0.2,
        "current_location": "home",
    }

    with pytest.raises(pydantic.ValidationError):
        CharacterState(**base_kwargs, current_activity="")

    with pytest.raises(pydantic.ValidationError):
        CharacterState(**base_kwargs, current_activity="   \t\n")


def test_empty_or_whitespace_location_rejected():
    """Empty or whitespace-only current_location is rejected."""
    base_kwargs = {
        "id": "aevum",
        "version": 1,
        "updated_at": datetime.now(timezone.utc),
        "mood": CharacterMood.NEUTRAL,
        "energy": 0.5,
        "stress": 0.2,
        "social_energy": 0.5,
        "confidence": 0.5,
        "irritation": 0.0,
        "loneliness": 0.2,
        "current_activity": "resting",
    }

    with pytest.raises(pydantic.ValidationError):
        CharacterState(**base_kwargs, current_location="")

    with pytest.raises(pydantic.ValidationError):
        CharacterState(**base_kwargs, current_location="   ")


def test_invalid_version_rejected():
    """Version counter must be >= 1."""
    state = create_initial_aevum_state()
    data = state.model_dump()
    data["version"] = 0

    with pytest.raises(pydantic.ValidationError):
        CharacterState.model_validate(data)


def test_character_state_rejects_extra_fields():
    """Speculative extra fields are forbidden by extra='forbid'."""
    state = create_initial_aevum_state()
    data = state.model_dump()
    data["happiness"] = 0.9

    with pytest.raises(pydantic.ValidationError):
        CharacterState.model_validate(data)


# ==============================================================================
# 2. Immutability Tests
# ==============================================================================

def test_character_state_is_immutable():
    """CharacterState instances cannot be mutated."""
    state = create_initial_aevum_state()

    with pytest.raises(pydantic.ValidationError):
        state.energy = 0.9  # type: ignore

    with pytest.raises(pydantic.ValidationError):
        state.mood = CharacterMood.FOCUSED  # type: ignore

    with pytest.raises(pydantic.ValidationError):
        state.current_activity = "running"  # type: ignore


# ==============================================================================
# 3. Serialization Tests
# ==============================================================================

def test_character_state_serialization_round_trip():
    """Serialization to JSON and deserialization back reproduces identical model."""
    original = create_initial_aevum_state()

    json_str = original.model_dump_json()
    restored = CharacterState.model_validate_json(json_str)

    assert restored == original
    assert restored.id == original.id
    assert restored.version == original.version
    assert restored.mood == original.mood
    assert restored.energy == original.energy
    assert restored.stress == original.stress
    assert restored.current_activity == original.current_activity
    assert restored.current_location == original.current_location


# ==============================================================================
# 4. Persistence & Service Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_initial_state_created_on_empty_db(test_session: AsyncSession):
    """Initial character state is deterministically seeded when table is empty."""
    service = CharacterStateService(test_session)
    state = await service.get_state("aevum")

    assert state.id == "aevum"
    assert state.version == 1
    assert state.mood == CharacterMood.NEUTRAL
    assert state.energy == 0.7
    assert state.stress == 0.2
    assert state.social_energy == 0.6
    assert state.confidence == 0.7
    assert state.irritation == 0.0
    assert state.loneliness == 0.3
    assert state.current_activity == "resting"
    assert state.current_location == "home"


@pytest.mark.asyncio
async def test_repeated_reads_return_same_persisted_state(test_session: AsyncSession):
    """Repeated reads return the identical persisted character state."""
    service = CharacterStateService(test_session)
    state1 = await service.get_state("aevum")
    state2 = await service.get_state("aevum")

    assert state1 == state2
    assert state1.version == state2.version
    assert state1.updated_at == state2.updated_at


@pytest.mark.asyncio
async def test_state_survives_session_boundary(test_engine):
    """Character state persists across separate database session boundaries."""
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session1:
        service1 = CharacterStateService(session1)
        created = await service1.get_state("aevum")
        assert created.version == 1

    async with session_factory() as session2:
        service2 = CharacterStateService(session2)
        loaded = await service2.get_state("aevum")
        assert loaded.id == created.id
        assert loaded.version == created.version
        assert loaded.mood == created.mood
        assert loaded.energy == created.energy
        assert loaded.current_activity == created.current_activity


@pytest.mark.asyncio
async def test_state_survives_service_recreation(test_session: AsyncSession):
    """Character state persists across service re-instantiations on the same session."""
    service_a = CharacterStateService(test_session)
    created = await service_a.get_state("aevum")

    service_b = CharacterStateService(test_session)
    loaded = await service_b.get_state("aevum")

    assert loaded == created


@pytest.mark.asyncio
async def test_state_survives_backend_restart_simulation(tmp_path):
    """Character state survives a complete backend process restart on disk."""
    db_file = tmp_path / "char_state_restart_test.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    # 1. Process 1: create tables, seed state, update state
    engine1 = create_async_engine(db_url, echo=False)
    async with engine1.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory1 = async_sessionmaker(bind=engine1, class_=AsyncSession, expire_on_commit=False)
    async with session_factory1() as session1:
        service1 = CharacterStateService(session1)
        state1 = await service1.get_state("aevum")
        assert state1.version == 1

        updated_def = CharacterState(
            id=state1.id,
            version=state1.version,
            updated_at=state1.updated_at,
            mood=CharacterMood.FOCUSED,
            energy=0.85,
            stress=0.3,
            social_energy=0.5,
            confidence=0.8,
            irritation=0.0,
            loneliness=0.1,
            current_activity="practicing piano",
            current_location="music room",
        )
        saved = await service1.update_state(updated_def, expected_version=1)
        assert saved.version == 2
        saved_updated_at = saved.updated_at

    await engine1.dispose()

    # 2. Process 2: new engine and session loading same SQLite file
    engine2 = create_async_engine(db_url, echo=False)
    session_factory2 = async_sessionmaker(bind=engine2, class_=AsyncSession, expire_on_commit=False)
    async with session_factory2() as session2:
        service2 = CharacterStateService(session2)
        loaded = await service2.get_state("aevum")
        assert loaded.id == "aevum"
        assert loaded.version == 2
        assert loaded.mood == CharacterMood.FOCUSED
        assert loaded.energy == 0.85
        assert loaded.current_activity == "practicing piano"
        assert loaded.current_location == "music room"
        assert loaded.updated_at == saved_updated_at

    await engine2.dispose()


@pytest.mark.asyncio
async def test_update_state_persists_and_increments_version(test_session: AsyncSession):
    """Updating character state increments version and updates timestamp."""
    service = CharacterStateService(test_session)
    initial = await service.get_state("aevum")

    new_state = CharacterState(
        id=initial.id,
        version=initial.version,
        updated_at=initial.updated_at,
        mood=CharacterMood.TIRED,
        energy=0.3,
        stress=0.4,
        social_energy=0.2,
        confidence=0.6,
        irritation=0.1,
        loneliness=0.2,
        current_activity="studying for exams",
        current_location="library",
    )

    updated = await service.update_state(new_state, expected_version=1)

    assert updated.version == 2
    assert updated.mood == CharacterMood.TIRED
    assert updated.energy == 0.3
    assert updated.current_activity == "studying for exams"
    assert updated.current_location == "library"
    assert updated.updated_at >= initial.updated_at

    # Re-reading confirms persistence
    reread = await service.get_state("aevum")
    assert reread.version == 2
    assert reread.current_activity == "studying for exams"


@pytest.mark.asyncio
async def test_stale_expected_version_rejected_by_database(test_session: AsyncSession):
    """Database-enforced optimistic concurrency rejects updates with mismatched version."""
    service = CharacterStateService(test_session)
    initial = await service.get_state("aevum")
    assert initial.version == 1

    new_state = CharacterState(
        id=initial.id,
        version=initial.version,
        updated_at=initial.updated_at,
        mood=CharacterMood.GOOD,
        energy=0.9,
        stress=0.1,
        social_energy=0.8,
        confidence=0.9,
        irritation=0.0,
        loneliness=0.1,
        current_activity="walking outside",
        current_location="outside",
    )

    with pytest.raises(CharacterStateConflictError) as exc_info:
        await service.update_state(new_state, expected_version=99)

    assert exc_info.value.expected_version == 99
    assert exc_info.value.actual_version == 1

    # Verify state remains untouched
    current = await service.get_state("aevum")
    assert current.version == 1
    assert current.mood == initial.mood
    assert current.current_activity == initial.current_activity


@pytest.mark.asyncio
async def test_convenience_functions(test_session: AsyncSession):
    """Verify get_character_state and update_character_state convenience helpers."""
    state1 = await get_character_state(test_session)
    assert state1.id == "aevum"
    assert state1.version == 1

    state2 = await update_character_state(test_session, state1, expected_version=1)
    assert state2.version == 2


# ==============================================================================
# 5. Architecture Isolation Tests
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


def test_character_state_models_do_not_import_gemini():
    """State models must not import Google GenAI or LLM SDKs."""
    import app.character.state_models as state_models

    imported = _get_imported_modules(state_models)
    for mod in imported:
        assert not any(x in mod.lower() for x in ["google", "genai", "gemini"]), (
            f"Unexpected LLM/Gemini import in state models: {mod}"
        )


def test_character_state_models_do_not_import_conversation():
    """State models must not depend on Conversation or Message models."""
    import app.character.state_models as state_models

    imported = _get_imported_modules(state_models)
    for mod in imported:
        assert not any(x in mod.lower() for x in ["conversation", "message"]), (
            f"Unexpected conversation import in state models: {mod}"
        )


def test_character_state_models_do_not_import_memory_relationship_emotion_life():
    """State models must not import speculative future systems."""
    import app.character.state_models as state_models

    imported = _get_imported_modules(state_models)
    for mod in imported:
        assert not any(x in mod.lower() for x in ["memory", "relationship", "emotion", "life", "event"]), (
            f"Unexpected subsystem import in state models: {mod}"
        )


def test_character_state_models_do_not_depend_on_character_definition():
    """State models must remain decoupled from CharacterDefinition models."""
    import app.character.state_models as state_models

    imported = _get_imported_modules(state_models)
    for mod in imported:
        assert "models" not in mod.lower() or "character.models" not in mod.lower(), (
            f"Unexpected coupling from state models to definition models: {mod}"
        )
