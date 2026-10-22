"""
test_sticker_pipeline.py — Tests for Meme / Sticker pipeline and prompt grounding.

Validates:
1. ResponseContextAssembler emits Rule 29 (Meme Stickers & Playful Battle / 斗图生态)
   with supported sticker tags.
2. ConversationalResponseParser cleanly parses multi-bubble responses containing stickers.
3. Standalone sticker tags are preserved as first-class speech bubbles.
"""

from datetime import datetime, timezone
import pytest

from app.character.conversational_parser import ConversationalResponseParser
from app.character.engine_models import (
    CharacterBehaviorContext,
    CharacterDefinitionContext,
    CharacterEmotionContext,
    CharacterMemoryContext,
    CharacterResponseContext,
    CharacterStateContext,
)
from app.character.models import (
    CharacterDefinition,
    CharacterIdentity,
    Personality,
)
from app.character.prompt_assembler import ResponseContextAssembler
from app.character.state_models import CharacterMood, CharacterState
from app.emotion.emotion_models import EmotionState, EmotionType
from app.life.models import LifeState
from app.life.context_builder import LifeContextBuilder
from app.relationship.context_builder import RelationshipContextBuilder
from app.relationship.models import RelationshipState


def _create_sample_character_definition() -> CharacterDefinition:
    return CharacterDefinition(
        id="aevum",
        version=1,
        updated_at=datetime.now(timezone.utc),
        identity=CharacterIdentity(
            name="Aevum",
            age=21,
            occupation="University Student",
            background="Studies piano at USM.",
        ),
        personality=Personality(
            core_traits=["independent", "observant", "playful"],
            social_style=["Warm but reserved"],
            emotional_style=["Measured"],
            communication_style=["direct", "natural"],
            behavioral_tendencies=["Prefers quiet spaces"],
            flaws=["Hesitant to initiate"],
        ),
    )


def test_prompt_assembler_contains_sticker_rules_and_tags():
    """Prompt assembler emits WeChat-style sticker rules."""
    char_def = _create_sample_character_definition()
    char_ctx = CharacterDefinitionContext.from_definition(char_def)

    state = CharacterState(
        id="aevum",
        version=1,
        updated_at=datetime.now(timezone.utc),
        mood=CharacterMood.CALM,
        energy=0.8,
        stress=0.2,
        social_energy=0.8,
        confidence=0.8,
        irritation=0.0,
        loneliness=0.1,
        current_activity="resting",
        current_location="home",
    )
    state_ctx = CharacterStateContext.from_state(state)
    rel_ctx = RelationshipContextBuilder.build(RelationshipState(
        id="user", user_id="user", version=1,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
        familiarity=0.8, trust=0.8, comfort=0.8, affection=0.5, attachment=0.5, respect=0.8,
    ))
    emo_ctx = CharacterEmotionContext.from_state(EmotionState(
        id="emo-1", character_id="aevum", emotion_type=EmotionType.HAPPY, intensity=0.6,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    ))
    life_ctx = LifeContextBuilder.build(LifeState(
        character_id="aevum", current_activity="resting", current_location="home",
        updated_at=datetime.now(timezone.utc),
    ), (), ())

    ctx = CharacterResponseContext(
        user_input="斗图来不来？",
        character=char_ctx,
        character_state=state_ctx,
        relationship=rel_ctx,
        emotion=emo_ctx,
        memory=CharacterMemoryContext.empty(),
        behavior=CharacterBehaviorContext(behavioral_hints=()),
        life=life_ctx,
    )

    llm_context = ResponseContextAssembler.assemble(ctx)
    prompt_text = "\n".join(llm_context.system_instructions)

    assert "表情包是万能表达" in prompt_text
    assert "[表情包: 描述]" in prompt_text


def test_conversational_parser_extracts_sticker_burst_bubbles():
    """ConversationalResponseParser extracts separate bubbles when speech contains text + sticker."""
    raw_speech = "笑死，你自己还不是一样[旺柴]\n[sticker:cat_bonk]"
    bubbles = ConversationalResponseParser.extract_bubbles(raw_speech)
    assert len(bubbles) == 2
    assert "笑死" in bubbles[0]
    assert bubbles[1] == "[sticker:cat_bonk]"


def test_conversational_parser_standalone_sticker():
    """Standalone sticker is preserved cleanly as a single bubble."""
    raw_speech = "[sticker:cat_surprised]"
    bubbles = ConversationalResponseParser.extract_bubbles(raw_speech)
    assert len(bubbles) == 1
    assert bubbles[0] == "[sticker:cat_surprised]"


def test_full_turn_parsing_with_sticker_content():
    """Full <character_turn> XML containing a sticker parses successfully."""
    raw_output = """
<character_turn>
<internal_decision>
attention: playful banter
reaction: amused teasing
commitment: PARTIAL_FLOW
energy: HIGH
motivation: GENUINE_SHARING
friction: PLAYFUL_TEASE
curiosity: false
ignored: none
</internal_decision>
<character_speech>
要你管[白眼]
[sticker:cat_pout]
</character_speech>
</character_turn>
"""
    parsed = ConversationalResponseParser.parse(raw_output)
    assert parsed.decision is not None
    assert len(parsed.speech_bubbles) == 2
    assert "要你管[白眼]" in parsed.speech_bubbles[0]
    assert parsed.speech_bubbles[1] == "[sticker:cat_pout]"


def test_prompt_assembler_contains_gamer_vulnerability_and_slacking_rules():
    """Prompt assembler emits WeChat rules for casual peer banter (e.g. 抽卡歪了, 幸灾乐祸 '乐', 严禁油腻说教)."""
    char_def = _create_sample_character_definition()
    char_ctx = CharacterDefinitionContext.from_definition(char_def)
    state = CharacterState(
        id="aevum", version=1, updated_at=datetime.now(timezone.utc), mood=CharacterMood.CALM,
        energy=0.8, stress=0.2, social_energy=0.8, confidence=0.8, irritation=0.0, loneliness=0.1,
        current_activity="resting", current_location="home",
    )
    state_ctx = CharacterStateContext.from_state(state)
    rel_ctx = RelationshipContextBuilder.build(RelationshipState(
        id="user", user_id="user", version=1, created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc), familiarity=0.8, trust=0.8, comfort=0.8, affection=0.5,
        attachment=0.5, respect=0.8,
    ))
    emo_ctx = CharacterEmotionContext.from_state(EmotionState(
        id="emo-1", character_id="aevum", emotion_type=EmotionType.HAPPY, intensity=0.6,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    ))
    life_ctx = LifeContextBuilder.build(LifeState(
        character_id="aevum", current_activity="resting", current_location="home",
        updated_at=datetime.now(timezone.utc),
    ), (), ())

    ctx = CharacterResponseContext(
        user_input="今天又是连麦打游戏的一天",
        character=char_ctx,
        character_state=state_ctx,
        relationship=rel_ctx,
        emotion=emo_ctx,
        memory=CharacterMemoryContext.empty(),
        behavior=CharacterBehaviorContext(behavioral_hints=()),
        life=life_ctx,
    )

    llm_context = ResponseContextAssembler.assemble(ctx)
    prompt_text = "\n".join(llm_context.system_instructions)

    assert "熟人抽卡歪了等倒霉事可以直接幸灾乐祸" in prompt_text
    assert "严禁当心理咨询师或理性说教" in prompt_text
    assert "严禁说“抱抱不哭”" in prompt_text
