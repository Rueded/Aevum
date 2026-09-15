"""Tests for Phase 2.1: Character Foundation.

Validates CharacterIdentity, Personality, Preference, Boundary,
CharacterDefinition aggregate, SQLite persistence, optimistic concurrency control,
and architectural independence from LLM, Conversation, Memory, Relationship, and Emotion.
"""

from datetime import datetime, timezone
import inspect
import pytest
import pydantic
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.character import (
    Boundary,
    CharacterDefinition,
    CharacterDefinitionConflictError,
    CharacterDefinitionService,
    CharacterIdentity,
    Personality,
    Preference,
    PreferenceSentiment,
    create_initial_aevum_definition,
    get_character_definition,
    update_character_definition,
)
from app.db.models import CharacterDefinitionRecord
from app.db.session import Base


# ==============================================================================
# 1. Identity Tests
# ==============================================================================

def test_valid_identity_accepted():
    """Valid character identity is instantiated successfully."""
    ident = CharacterIdentity(
        name="Aevum",
        age=21,
        occupation="University Student",
        background="Independent student interested in music and books.",
    )
    assert ident.name == "Aevum"
    assert ident.age == 21
    assert ident.occupation == "University Student"
    assert ident.background == "Independent student interested in music and books."


def test_empty_or_whitespace_name_rejected():
    """Empty or whitespace-only name is rejected."""
    with pytest.raises(pydantic.ValidationError):
        CharacterIdentity(name="", age=21, occupation="Student", background="Bg")

    with pytest.raises(pydantic.ValidationError):
        CharacterIdentity(name="   ", age=21, occupation="Student", background="Bg")


def test_empty_or_whitespace_occupation_rejected():
    """Empty or whitespace-only occupation is rejected."""
    with pytest.raises(pydantic.ValidationError):
        CharacterIdentity(name="Aevum", age=21, occupation="", background="Bg")

    with pytest.raises(pydantic.ValidationError):
        CharacterIdentity(name="Aevum", age=21, occupation="   \t", background="Bg")


def test_empty_or_whitespace_background_rejected():
    """Empty or whitespace-only background is rejected."""
    with pytest.raises(pydantic.ValidationError):
        CharacterIdentity(name="Aevum", age=21, occupation="Student", background="")

    with pytest.raises(pydantic.ValidationError):
        CharacterIdentity(name="Aevum", age=21, occupation="Student", background="   \n")


def test_invalid_age_rejected():
    """Age below 18 or above 100 is rejected."""
    with pytest.raises(pydantic.ValidationError):
        CharacterIdentity(name="Aevum", age=17, occupation="Student", background="Bg")

    with pytest.raises(pydantic.ValidationError):
        CharacterIdentity(name="Aevum", age=101, occupation="Student", background="Bg")

    # Boundary ages 18 and 100 should be accepted
    id_18 = CharacterIdentity(name="Aevum", age=18, occupation="Student", background="Bg")
    id_100 = CharacterIdentity(name="Aevum", age=100, occupation="Student", background="Bg")
    assert id_18.age == 18
    assert id_100.age == 100


def test_identity_rejects_extra_fields():
    """Extra or speculative fields are strictly forbidden."""
    with pytest.raises(pydantic.ValidationError):
        CharacterIdentity(  # type: ignore
            name="Aevum",
            age=21,
            occupation="Student",
            background="Bg",
            gender="female",  # type: ignore
        )

    with pytest.raises(pydantic.ValidationError):
        CharacterIdentity(  # type: ignore
            name="Aevum",
            age=21,
            occupation="Student",
            background="Bg",
            relationship_status="single",  # type: ignore
        )


def test_identity_is_immutable():
    """CharacterIdentity cannot be mutated after creation."""
    ident = CharacterIdentity(name="Aevum", age=21, occupation="Student", background="Bg")
    with pytest.raises(pydantic.ValidationError):
        ident.name = "Renamed"  # type: ignore


# ==============================================================================
# 2. Personality Tests
# ==============================================================================

def test_valid_personality_accepted():
    """Valid personality with all 6 required dimensions is accepted."""
    p = Personality(
        core_traits=("independent", "thoughtful"),
        social_style=("slow to warm up",),
        emotional_style=("processes internally",),
        communication_style=("natural", "teasing"),
        behavioral_tendencies=("values independence",),
        flaws=("mildly stubborn",),
    )
    assert p.core_traits == ("independent", "thoughtful")
    assert p.flaws == ("mildly stubborn",)


def test_empty_personality_dimension_rejected():
    """Empty personality dimension is rejected."""
    with pytest.raises(pydantic.ValidationError):
        Personality(
            core_traits=(),  # empty dimension must be rejected
            social_style=("slow to warm up",),
            emotional_style=("processes internally",),
            communication_style=("natural",),
            behavioral_tendencies=("values independence",),
            flaws=("mildly stubborn",),
        )


def test_whitespace_personality_traits_rejected():
    """Whitespace-only trait items are rejected."""
    with pytest.raises(pydantic.ValidationError):
        Personality(
            core_traits=("   ",),
            social_style=("slow to warm up",),
            emotional_style=("processes internally",),
            communication_style=("natural",),
            behavioral_tendencies=("values independence",),
            flaws=("mildly stubborn",),
        )


def test_personality_rejects_extra_fields():
    """Extra numerical sliders or speculative fields are rejected."""
    with pytest.raises(pydantic.ValidationError):
        Personality(  # type: ignore
            core_traits=("independent",),
            social_style=("slow to warm up",),
            emotional_style=("processes internally",),
            communication_style=("natural",),
            behavioral_tendencies=("values independence",),
            flaws=("mildly stubborn",),
            kindness=87,  # type: ignore
        )


def test_personality_is_immutable():
    """Personality model and its tuple dimensions cannot be mutated."""
    p = Personality(
        core_traits=("independent",),
        social_style=("slow to warm up",),
        emotional_style=("processes internally",),
        communication_style=("natural",),
        behavioral_tendencies=("values independence",),
        flaws=("mildly stubborn",),
    )
    with pytest.raises(pydantic.ValidationError):
        p.core_traits = ("other",)  # type: ignore


# ==============================================================================
# 3. Preference Tests
# ==============================================================================

def test_valid_preference_accepted():
    """Valid preference with typed sentiment is accepted."""
    pref = Preference(
        category="music",
        item="acoustic piano",
        sentiment=PreferenceSentiment.LIKE,
    )
    assert pref.category == "music"
    assert pref.item == "acoustic piano"
    assert pref.sentiment == PreferenceSentiment.LIKE


def test_preference_sentiment_validation():
    """Preference sentiment validates allowed values."""
    p_dislike = Preference(category="food", item="overcooked meat", sentiment=PreferenceSentiment.DISLIKE)
    assert p_dislike.sentiment == PreferenceSentiment.DISLIKE

    p_neutral = Preference(category="tech", item="tablets", sentiment="neutral")  # type: ignore
    assert p_neutral.sentiment == PreferenceSentiment.NEUTRAL

    with pytest.raises(pydantic.ValidationError):
        Preference(category="music", item="pop", sentiment="love")  # type: ignore


def test_empty_preference_item_or_category_rejected():
    """Empty category or item is rejected."""
    with pytest.raises(pydantic.ValidationError):
        Preference(category="", item="item", sentiment=PreferenceSentiment.LIKE)

    with pytest.raises(pydantic.ValidationError):
        Preference(category="cat", item="   ", sentiment=PreferenceSentiment.LIKE)


def test_preference_is_immutable():
    """Preference model cannot be mutated."""
    pref = Preference(category="music", item="piano", sentiment=PreferenceSentiment.LIKE)
    with pytest.raises(pydantic.ValidationError):
        pref.item = "guitar"  # type: ignore


# ==============================================================================
# 4. Boundary Tests
# ==============================================================================

def test_valid_boundary_accepted():
    """Valid behavioral boundary is accepted."""
    b = Boundary(description="Does not pretend to know something she does not know.")
    assert "Does not pretend" in b.description


def test_empty_or_whitespace_boundary_rejected():
    """Empty or whitespace boundary is rejected."""
    with pytest.raises(pydantic.ValidationError):
        Boundary(description="")

    with pytest.raises(pydantic.ValidationError):
        Boundary(description="   \t\n")


def test_boundary_is_immutable():
    """Boundary model cannot be mutated."""
    b = Boundary(description="Boundary description")
    with pytest.raises(pydantic.ValidationError):
        b.description = "Mutated"  # type: ignore


# ==============================================================================
# 5. CharacterDefinition Aggregate Tests
# ==============================================================================

def test_canonical_initial_aevum_definition():
    """Verify canonical initial Aevum definition content and integrity."""
    def_aevum = create_initial_aevum_definition()
    assert def_aevum.id == "aevum"
    assert def_aevum.version == 1
    assert def_aevum.identity.name == "Aevum"
    assert def_aevum.identity.age == 21
    assert "University Student" in def_aevum.identity.occupation
    assert len(def_aevum.personality.core_traits) > 0
    assert len(def_aevum.preferences) >= 5
    assert len(def_aevum.boundaries) >= 5


def test_character_definition_is_immutable():
    """CharacterDefinition and its nested structures cannot be modified."""
    def_aevum = create_initial_aevum_definition()

    with pytest.raises(pydantic.ValidationError):
        def_aevum.version = 2  # type: ignore

    with pytest.raises(pydantic.ValidationError):
        def_aevum.identity = CharacterIdentity(  # type: ignore
            name="Other", age=22, occupation="Job", background="Bg"
        )


def test_character_definition_serialization_round_trip():
    """Serialization to JSON and deserialization back reproduces identical model."""
    original = create_initial_aevum_definition()

    json_str = original.model_dump_json()
    restored = CharacterDefinition.model_validate_json(json_str)

    assert restored == original
    assert restored.id == original.id
    assert restored.version == original.version
    assert restored.identity == original.identity
    assert restored.personality == original.personality
    assert restored.preferences == original.preferences
    assert restored.boundaries == original.boundaries


def test_character_definition_rejects_extra_fields():
    """Speculative extra fields are forbidden on CharacterDefinition."""
    original = create_initial_aevum_definition()
    data = original.model_dump()
    data["mood"] = "happy"

    with pytest.raises(pydantic.ValidationError):
        CharacterDefinition.model_validate(data)


def test_character_definition_contains_no_relationship_or_emotion_fields():
    """Verify absence of relationship, emotion, and memory fields."""
    fields = set(CharacterDefinition.model_fields.keys())
    expected = {"id", "version", "updated_at", "identity", "personality", "preferences", "boundaries"}
    assert fields == expected, f"Unexpected fields found: {fields - expected}"

    # Verify no affection, trust, mood, memory
    for forbidden in ["affection", "trust", "relationship", "mood", "emotion", "energy", "memory"]:
        assert forbidden not in fields


# ==============================================================================
# 6. Persistence & Service Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_initial_character_created_on_empty_db(test_session: AsyncSession):
    """Initial character definition is deterministically seeded when table is empty."""
    service = CharacterDefinitionService(test_session)
    char = await service.get_character("aevum")

    assert char.id == "aevum"
    assert char.version == 1
    assert char.identity.name == "Aevum"
    assert char.identity.age == 21
    assert len(char.preferences) > 0
    assert len(char.boundaries) > 0


@pytest.mark.asyncio
async def test_repeated_reads_return_same_persisted_character(test_session: AsyncSession):
    """Subsequent reads return the identical persisted character definition."""
    service = CharacterDefinitionService(test_session)
    char1 = await service.get_character("aevum")
    char2 = await service.get_character("aevum")

    assert char1 == char2
    assert char1.version == char2.version
    assert char1.updated_at == char2.updated_at


@pytest.mark.asyncio
async def test_character_survives_session_boundary(test_engine):
    """Character definition persists across database session boundaries."""
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session1:
        service1 = CharacterDefinitionService(session1)
        created = await service1.get_character("aevum")
        assert created.version == 1

    async with session_factory() as session2:
        service2 = CharacterDefinitionService(session2)
        loaded = await service2.get_character("aevum")
        assert loaded.id == created.id
        assert loaded.version == created.version
        assert loaded.identity == created.identity
        assert loaded.personality == created.personality
        assert loaded.preferences == created.preferences
        assert loaded.boundaries == created.boundaries


@pytest.mark.asyncio
async def test_character_survives_service_recreation(test_session: AsyncSession):
    """Character definition persists across service re-instantiations on the same session."""
    service_a = CharacterDefinitionService(test_session)
    created = await service_a.get_character("aevum")

    service_b = CharacterDefinitionService(test_session)
    loaded = await service_b.get_character("aevum")

    assert loaded == created


@pytest.mark.asyncio
async def test_character_survives_backend_restart_simulation(tmp_path):
    """Character definition survives a complete backend process restart on disk."""
    db_file = tmp_path / "char_restart_test.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    # 1. First process run: create tables, seed character
    engine1 = create_async_engine(db_url, echo=False)
    async with engine1.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory1 = async_sessionmaker(bind=engine1, class_=AsyncSession, expire_on_commit=False)
    async with session_factory1() as session1:
        service1 = CharacterDefinitionService(session1)
        char1 = await service1.get_character("aevum")
        assert char1.version == 1

    await engine1.dispose()

    # 2. Second process run: new engine and session loading same SQLite file
    engine2 = create_async_engine(db_url, echo=False)
    session_factory2 = async_sessionmaker(bind=engine2, class_=AsyncSession, expire_on_commit=False)
    async with session_factory2() as session2:
        service2 = CharacterDefinitionService(session2)
        loaded = await service2.get_character("aevum")
        assert loaded.id == "aevum"
        assert loaded.version == 1
        assert loaded.identity.name == "Aevum"
        assert loaded.identity.age == 21
        assert loaded.personality == char1.personality
        assert loaded.preferences == char1.preferences
        assert loaded.boundaries == char1.boundaries

    await engine2.dispose()


@pytest.mark.asyncio
async def test_update_character_persists_and_increments_version(test_session: AsyncSession):
    """Updating character definition increments version and updates timestamp."""
    service = CharacterDefinitionService(test_session)
    initial = await service.get_character("aevum")

    # Construct updated definition with modified background
    updated_identity = CharacterIdentity(
        name="Aevum",
        age=21,
        occupation="Senior University Student",
        background="Updated student background reflecting academic progression.",
    )
    new_def = CharacterDefinition(
        id=initial.id,
        version=initial.version,
        updated_at=initial.updated_at,
        identity=updated_identity,
        personality=initial.personality,
        preferences=initial.preferences,
        boundaries=initial.boundaries,
    )

    updated = await service.update_character(new_def, expected_version=1)

    assert updated.version == 2
    assert updated.identity.occupation == "Senior University Student"
    assert updated.updated_at >= initial.updated_at

    # Re-reading verifies persistence
    reread = await service.get_character("aevum")
    assert reread.version == 2
    assert reread.identity.occupation == "Senior University Student"


@pytest.mark.asyncio
async def test_stale_expected_version_rejected_by_database(test_session: AsyncSession):
    """Database-enforced optimistic concurrency rejects updates with mismatched version."""
    service = CharacterDefinitionService(test_session)
    initial = await service.get_character("aevum")
    assert initial.version == 1

    new_def = CharacterDefinition(
        id=initial.id,
        version=initial.version,
        updated_at=initial.updated_at,
        identity=initial.identity,
        personality=initial.personality,
        preferences=initial.preferences,
        boundaries=initial.boundaries,
    )

    # Attempt update expecting version 99 when current version is 1
    with pytest.raises(CharacterDefinitionConflictError) as exc_info:
        await service.update_character(new_def, expected_version=99)

    assert exc_info.value.expected_version == 99
    assert exc_info.value.actual_version == 1

    # Verify character definition remains untouched
    current = await service.get_character("aevum")
    assert current.version == 1
    assert current.identity.occupation == initial.identity.occupation


@pytest.mark.asyncio
async def test_convenience_functions(test_session: AsyncSession):
    """Verify get_character_definition and update_character_definition convenience helpers."""
    char1 = await get_character_definition(test_session)
    assert char1.id == "aevum"
    assert char1.version == 1

    char2 = await update_character_definition(test_session, char1, expected_version=1)
    assert char2.version == 2


# ==============================================================================
# 7. Architecture Isolation Tests
# ==============================================================================

import ast


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


def test_character_models_do_not_import_gemini_sdk():
    """Character models must not import Google GenAI or LLM SDKs."""
    import app.character.models as char_models

    imported = _get_imported_modules(char_models)
    for mod in imported:
        assert not any(x in mod.lower() for x in ["google", "genai", "gemini"]), (
            f"Unexpected LLM/Gemini import in character models: {mod}"
        )


def test_character_models_do_not_import_conversation_models():
    """Character models must not depend on Conversation or Message models."""
    import app.character.models as char_models

    imported = _get_imported_modules(char_models)
    for mod in imported:
        assert not any(x in mod.lower() for x in ["conversation", "message"]), (
            f"Unexpected conversation import in character models: {mod}"
        )


def test_character_models_do_not_import_memory_relationship_emotion():
    """Character models must not import speculative future systems."""
    import app.character.models as char_models

    imported = _get_imported_modules(char_models)
    for mod in imported:
        assert not any(x in mod.lower() for x in ["memory", "relationship", "emotion"]), (
            f"Unexpected subsystem import in character models: {mod}"
        )

