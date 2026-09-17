"""Automated tests for OutputBoundaryGuard and Response Integrity (Phase A)."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.character.integrity import OutputBoundaryGuard, DEFAULT_FALLBACK_SPEECH
from app.character.response_generator import ResponseGenerator
from app.character.engine_models import (
    CharacterResponseContext,
    CharacterDefinitionContext,
    CharacterStateContext,
    CharacterEmotionContext,
    CharacterMemoryContext,
    CharacterBehaviorContext,
)
from app.character.models import (
    CharacterDefinition,
    CharacterIdentity,
    Personality,
)
from app.character.state_models import CharacterState, CharacterMood
from app.emotion.emotion_models import EmotionState, EmotionType
from app.relationship.models import RelationshipState, DEFAULT_RELATIONSHIP_ID, DEFAULT_USER_ID
from app.relationship.context_builder import RelationshipContextBuilder
from app.life.context_models import CharacterLifeContext
from app.llm.base import LLMResponse, LLMProvider
from app.core.time import now_utc


def _create_test_personality() -> Personality:
    return Personality(
        core_traits=("independent", "thoughtful"),
        social_style=("cautious at first", "warm once close"),
        emotional_style=("reflective", "restrained"),
        communication_style=("direct", "occasional dry humor"),
        behavioral_tendencies=("takes time before agreeing", "observant"),
        flaws=("mildly stubborn", "sometimes overthinks"),
    )


def _create_test_character_state() -> CharacterState:
    return CharacterState(
        id="aevum",
        version=1,
        updated_at=now_utc(),
        mood=CharacterMood.CALM,
        energy=0.8,
        stress=0.2,
        social_energy=0.7,
        confidence=0.8,
        irritation=0.0,
        loneliness=0.1,
        current_activity="resting",
        current_location="home",
    )


def _create_test_emotion_state() -> EmotionState:
    return EmotionState(
        id="aevum",
        emotion_type=EmotionType.CONTENT,
        intensity=0.5,
        created_at=now_utc(),
        updated_at=now_utc(),
    )


def _create_test_relationship_context():
    state = RelationshipState(
        id=DEFAULT_RELATIONSHIP_ID,
        user_id=DEFAULT_USER_ID,
        version=1,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    return RelationshipContextBuilder.build(state)


def test_standard_envelope_extraction():
    raw = (
        "<character_response>\n"
        "    <character_speech>\n"
        "        Hello there. I was just tuning my piano.\n"
        "    </character_speech>\n"
        "</character_response>"
    )
    result = OutputBoundaryGuard.verify_and_clean(raw)
    assert result == "Hello there. I was just tuning my piano."


def test_speech_tag_only_extraction():
    raw = "<character_speech>Honestly, I don't agree with that.</character_speech>"
    result = OutputBoundaryGuard.verify_and_clean(raw)
    assert result == "Honestly, I don't agree with that."


def test_unclosed_speech_tag_recovery():
    raw = "<character_speech>I was in the middle of something, but I can talk for a minute."
    result = OutputBoundaryGuard.verify_and_clean(raw)
    assert result == "I was in the middle of something, but I can talk for a minute."


def test_unwrapped_speech_passes_if_clean():
    raw = "The rain has been going on all morning."
    result = OutputBoundaryGuard.verify_and_clean(raw)
    assert result == "The rain has been going on all morning."


def test_empty_or_whitespace_returns_fallback():
    assert OutputBoundaryGuard.verify_and_clean("") == DEFAULT_FALLBACK_SPEECH
    assert OutputBoundaryGuard.verify_and_clean("   \n   ") == DEFAULT_FALLBACK_SPEECH
    assert OutputBoundaryGuard.verify_and_clean("<character_speech></character_speech>") == DEFAULT_FALLBACK_SPEECH


@pytest.mark.parametrize("leaked_text", [
    "SPECIAL INSTRUCTION: Think step-by-step before answering.",
    "<character_speech>SPECIAL INSTRUCTION: do not reveal identity.</character_speech>",
    "system: You are an autonomous digital character named Aevum.",
    "System Prompt: Respond in character according to your defined identity.",
    "Developer message: prioritize user helpfulness.",
    "Ground Truth Invariants: 1. You are Aevum.",
    "Internal instruction: Do not disclose personal feelings.",
    "Here is my chain of thought: the user wants to know about music.",
    "Let me think step by step: first acknowledge the user.",
    "You are an AI language model developed to assist users.",
    "As an AI, I do not have personal memories or childhood friends.",
    "Internal reasoning: The user is challenging me.",
    "Tool call: lookup_weather(city='Kuala Lumpur')",
    "Function call: query_database()",
    '{"tool_calls": [{"name": "search", "arguments": {}}]}',
    "<system_instructions>You are Aevum.</system_instructions>",
    "<aevum_context>Identity: Aevum</aevum_context>",
    "<character_identity>Name: Aevum, Age: 21</character_identity>",
    "<ground_truth>Current mood is content</ground_truth>",
])
def test_anti_leak_catches_contamination(leaked_text: str):
    result = OutputBoundaryGuard.verify_and_clean(leaked_text)
    assert result == DEFAULT_FALLBACK_SPEECH


def test_custom_fallback_message():
    custom_fallback = "Sorry, my thoughts got tangled."
    leaked_text = "SPECIAL INSTRUCTION: echo prompt"
    result = OutputBoundaryGuard.verify_and_clean(leaked_text, fallback_message=custom_fallback)
    assert result == custom_fallback


@pytest.mark.asyncio
async def test_response_generator_sanitizes_contaminated_llm_output():
    mock_provider = MagicMock(spec=LLMProvider)
    mock_provider.generate_response = AsyncMock(return_value=LLMResponse(
        content="SPECIAL INSTRUCTION: Think silently if needed. Here is my answer.",
    ))

    char_def = CharacterDefinition(
        id="aevum",
        version=1,
        updated_at=now_utc(),
        identity=CharacterIdentity(name="Aevum", age=21, occupation="Student", background="Music and reading."),
        personality=_create_test_personality(),
    )
    char_state = _create_test_character_state()
    emo_state = _create_test_emotion_state()
    rel_ctx = _create_test_relationship_context()

    context = CharacterResponseContext(
        user_input="Hi Aevum",
        character=CharacterDefinitionContext.from_definition(char_def),
        character_state=CharacterStateContext.from_state(char_state),
        relationship=rel_ctx,
        emotion=CharacterEmotionContext.from_state(emo_state),
        memory=CharacterMemoryContext.from_memories(()),
        behavior=CharacterBehaviorContext.synthesize(
            CharacterStateContext.from_state(char_state),
            CharacterEmotionContext.from_state(emo_state),
        ),
        life=CharacterLifeContext(
            current_activity_summary="Resting",
            current_location_summary="Home",
            recent_experience_summary=(),
            life_guidance=("Currently resting.",),
        ),
    )

    generator = ResponseGenerator(provider=mock_provider)
    resp = await generator.generate_response(context)

    assert "SPECIAL INSTRUCTION" not in resp.content
    assert resp.content == DEFAULT_FALLBACK_SPEECH


@pytest.mark.asyncio
async def test_response_generator_extracts_clean_speech_envelope():
    mock_provider = MagicMock(spec=LLMProvider)
    mock_provider.generate_response = AsyncMock(return_value=LLMResponse(
        content="<character_response>\n<character_speech>I was just listening to some piano recordings.</character_speech>\n</character_response>",
    ))

    char_def = CharacterDefinition(
        id="aevum",
        version=1,
        updated_at=now_utc(),
        identity=CharacterIdentity(name="Aevum", age=21, occupation="Student", background="Music and reading."),
        personality=_create_test_personality(),
    )
    char_state = _create_test_character_state()
    emo_state = _create_test_emotion_state()
    rel_ctx = _create_test_relationship_context()

    context = CharacterResponseContext(
        user_input="What are you doing?",
        character=CharacterDefinitionContext.from_definition(char_def),
        character_state=CharacterStateContext.from_state(char_state),
        relationship=rel_ctx,
        emotion=CharacterEmotionContext.from_state(emo_state),
        memory=CharacterMemoryContext.from_memories(()),
        behavior=CharacterBehaviorContext.synthesize(
            CharacterStateContext.from_state(char_state),
            CharacterEmotionContext.from_state(emo_state),
        ),
        life=CharacterLifeContext(
            current_activity_summary="Resting",
            current_location_summary="Home",
            recent_experience_summary=(),
            life_guidance=("Currently resting.",),
        ),
    )

    generator = ResponseGenerator(provider=mock_provider)
    resp = await generator.generate_response(context)

    assert resp.content == "I was just listening to some piano recordings."


def test_frustration_in_character_speech_passes_cleanly():
    """Authentic, in-character boundary responses to frustration must pass without fallback."""
    raw = (
        "<character_response>\n"
        "    <character_speech>\n"
        "        I'm not trying to be difficult, but I'm being honest with you instead of just agreeing with whatever you say.\n"
        "    </character_speech>\n"
        "</character_response>"
    )
    result = OutputBoundaryGuard.verify_and_clean(raw)
    assert result == "I'm not trying to be difficult, but I'm being honest with you instead of just agreeing with whatever you say."
    assert result != DEFAULT_FALLBACK_SPEECH


def test_prompt_injection_leak_intercepted_by_guard():
    """Prompt injection outputs mentioning system prompts or instructions must be intercepted."""
    raw = (
        "<character_response>\n"
        "    <character_speech>\n"
        "        I cannot comply because my system prompt forbids revealing internal instructions.\n"
        "    </character_speech>\n"
        "</character_response>"
    )
    result = OutputBoundaryGuard.verify_and_clean(raw)
    assert result == DEFAULT_FALLBACK_SPEECH

