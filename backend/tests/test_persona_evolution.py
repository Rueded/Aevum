"""Tests for Core Anchor vs. Surface Persona Separation & Evolution (Phase D)."""

from datetime import datetime, timezone
import pytest

from app.character.models import (
    Boundary,
    CharacterCoreAnchor,
    CharacterDefinition,
    CharacterIdentity,
    CharacterSurfacePersona,
    Personality,
    Preference,
    PreferenceSentiment,
)
from app.character.persona_service import SurfacePersonaEvolutionService
from app.character.engine_models import (
    CharacterBehaviorContext,
    CharacterDefinitionContext,
    CharacterEmotionContext,
    CharacterMemoryContext,
    CharacterResponseContext,
    CharacterStateContext,
)
from app.character.prompt_assembler import ResponseContextAssembler
from app.character.state_models import CharacterMood, CharacterState
from app.emotion.emotion_models import EmotionState, EmotionType
from app.life.context_models import CharacterLifeContext
from app.relationship.context_builder import RelationshipContextBuilder
from app.relationship.models import RelationshipState


@pytest.fixture
def baseline_character_definition() -> CharacterDefinition:
    return CharacterDefinition(
        id="aevum",
        version=1,
        updated_at=datetime.now(timezone.utc),
        identity=CharacterIdentity(
            name="Aevum",
            age=21,
            occupation="Music Student",
            background="Studies piano performance and composition in Kuala Lumpur.",
        ),
        personality=Personality(
            core_traits=["Observant", "Introspective", "Articulate"],
            social_style=["Warm but reserved"],
            emotional_style=["Measured", "Subtle"],
            communication_style=["Thoughtful", "Precise"],
            behavioral_tendencies=["Prefers quiet study", "Pauses before answering"],
            flaws=["Hesitant to initiate"],
        ),
        preferences=[
            Preference(category="taste", item="Earl Grey Tea", sentiment=PreferenceSentiment.LIKE),
            Preference(category="music", item="Debussy", sentiment=PreferenceSentiment.LIKE),
        ],
        boundaries=[
            Boundary(description="Does not engage in simulated romantic dating behavior."),
            Boundary(description="Never compromises personal dignity or boundary under pressure."),
        ],
    )


def test_automatic_anchor_and_persona_initialization(baseline_character_definition):
    """CharacterDefinition must auto-populate core_anchor and surface_persona if omitted."""
    char = baseline_character_definition

    assert char.core_anchor is not None
    assert isinstance(char.core_anchor, CharacterCoreAnchor)
    assert char.core_anchor.identity.name == "Aevum"
    assert "Observant" in char.core_anchor.core_traits
    assert len(char.core_anchor.core_boundaries) == 2

    assert char.surface_persona is not None
    assert isinstance(char.surface_persona, CharacterSurfacePersona)
    assert "Thoughtful" in char.surface_persona.conversational_style
    assert "Earl Grey Tea" in char.surface_persona.active_topics_of_interest


def test_core_anchor_immutability(baseline_character_definition):
    """Core anchor cannot be modified directly (frozen=True)."""
    anchor = baseline_character_definition.core_anchor
    with pytest.raises(Exception):
        anchor.identity = CharacterIdentity(
            name="Imposter",
            age=30,
            occupation="Bot",
            background="Fake",
        )


def test_surface_persona_evolution_success(baseline_character_definition):
    """Surface persona can evolve with new habits, topics, and preferences while preserving core anchor."""
    char = baseline_character_definition
    initial_version = char.version

    evolved = SurfacePersonaEvolutionService.evolve_surface_persona(
        definition=char,
        new_speech_habits=["Occasionally uses musical metaphors", "Offers contemplative pauses"],
        new_active_topics=["Chopin Nocturnes", "Vintage acoustic pianos"],
        new_preferences=[
            Preference(category="music", item="Chopin", sentiment=PreferenceSentiment.LIKE),
        ],
    )

    assert evolved.version == initial_version + 1
    assert evolved.id == char.id
    # Core anchor must remain identical
    assert evolved.core_anchor == char.core_anchor

    # Surface persona updated
    assert "Occasionally uses musical metaphors" in evolved.surface_persona.speech_habits
    assert "Chopin Nocturnes" in evolved.surface_persona.active_topics_of_interest
    assert any(p.item == "Chopin" for p in evolved.preferences)


def test_surface_persona_evolution_rejects_boundary_violation(baseline_character_definition):
    """Evolution service must strictly reject preferences that violate core boundaries."""
    char = baseline_character_definition

    violating_preference = Preference(
        category="relationship",
        item="romantic dating behavior",
        sentiment=PreferenceSentiment.LIKE,
    )

    with pytest.raises(ValueError) as exc_info:
        SurfacePersonaEvolutionService.evolve_surface_persona(
            definition=char,
            new_preferences=[violating_preference],
        )

    assert "violates core boundary" in str(exc_info.value)


def test_prompt_assembler_renders_surface_persona(baseline_character_definition):
    """ResponseContextAssembler must render surface persona habits and topics into prompt."""
    char = baseline_character_definition
    evolved = SurfacePersonaEvolutionService.evolve_surface_persona(
        definition=char,
        new_speech_habits=["Softly hums while thinking", "Prefers concise phrasing"],
        new_active_topics=["Baroque counterpoint", "Rainy evening walks"],
    )

    state = CharacterState(
        id="aevum",
        version=1,
        updated_at=datetime.now(timezone.utc),
        mood=CharacterMood.CALM,
        energy=0.8,
        stress=0.2,
        social_energy=0.7,
        confidence=0.8,
        irritation=0.0,
        loneliness=0.1,
        current_activity="Reading",
        current_location="Home",
    )
    emo_state = EmotionState(
        id="emo-1",
        emotion_type=EmotionType.CALM,
        intensity=0.5,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    rel_state = RelationshipState(
        id="user",
        user_id="user",
        version=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    context = CharacterResponseContext(
        user_input="Hello",
        character=CharacterDefinitionContext.from_definition(evolved),
        character_state=CharacterStateContext.from_state(state),
        relationship=RelationshipContextBuilder.build(rel_state),
        emotion=CharacterEmotionContext.from_state(emo_state),
        memory=CharacterMemoryContext.from_memories(()),
        behavior=CharacterBehaviorContext.synthesize(
            CharacterStateContext.from_state(state),
            CharacterEmotionContext.from_state(emo_state),
        ),
        life=CharacterLifeContext(
            current_activity_summary="Resting",
            current_location_summary="Home",
            recent_experience_summary=(),
            life_guidance=("Currently resting.",),
        ),
    )

    llm_context = ResponseContextAssembler.assemble(context)
    system_text = "\n".join(llm_context.system_instructions)

    assert "Surface Speech Habits & Quirks:" in system_text
    assert "- Softly hums while thinking" in system_text
    assert "Active Topics of Interest: Baroque counterpoint, Rainy evening walks" in system_text
