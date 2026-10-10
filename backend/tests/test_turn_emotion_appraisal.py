"""Unit tests for TurnEmotionAppraisalService.

Verifies that post-turn emotion appraisal:
- Transitions dominant emotion away from static default when user interacts.
- Synchronizes baseline CharacterState mood (GOOD, IRRITATED, FOCUSED, etc.).
- Correctly handles teasing/humor, sweet affection, and friction.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.state_models import CharacterMood
from app.character.state_service import CharacterStateService
from app.emotion.emotion_models import EmotionType
from app.emotion.service import EmotionService
from app.emotion.turn_appraisal import TurnEmotionAppraisalService


@pytest.mark.asyncio
async def test_teasing_interaction_transitions_emotion_to_amused(test_session: AsyncSession):
    """Teasing or humorous input transitions emotion to AMUSED and mood to GOOD."""
    service = TurnEmotionAppraisalService(test_session)

    # Trigger post-turn appraisal for playful tease
    result = await service.process_turn_emotion(
        user_input="哈哈笨蛋，你刚才笑死我了，太逗了！",
        assistant_response="哪有……你别乱笑话我好不好。",
        character_id="aevum",
    )

    assert result is not None
    assert result.emotion_type == EmotionType.AMUSED
    assert result.intensity >= 0.40

    # Verify CharacterState mood synchronized to GOOD
    char_state = await CharacterStateService(test_session).get_state("aevum")
    assert char_state.mood == CharacterMood.GOOD


@pytest.mark.asyncio
async def test_hostile_interaction_transitions_emotion_to_irritated(test_session: AsyncSession):
    """Hostile or disrespectful input transitions emotion to IRRITATED and mood to IRRITATED."""
    service = TurnEmotionAppraisalService(test_session)

    result = await service.process_turn_emotion(
        user_input="闭嘴，你真烦，少废话！",
        assistant_response="请你好好说话，没必要这么冲。",
        character_id="aevum",
    )

    assert result is not None
    assert result.emotion_type == EmotionType.IRRITATED

    char_state = await CharacterStateService(test_session).get_state("aevum")
    assert char_state.mood == CharacterMood.IRRITATED


@pytest.mark.asyncio
async def test_gaming_interaction_transitions_emotion_to_amused(test_session: AsyncSession):
    """Gaming commiseration over gacha or artifacts transitions emotion to AMUSED."""
    service = TurnEmotionAppraisalService(test_session)

    result = await service.process_turn_emotion(
        user_input="救命啊！我抽卡大保底又歪了，圣遗物强化全歪防御了[苦涩]",
        assistant_response="不愧是你，防御力战士[旺柴]",
        character_id="aevum",
    )

    assert result is not None
    assert result.emotion_type == EmotionType.AMUSED
    char_state = await CharacterStateService(test_session).get_state("aevum")
    assert char_state.mood == CharacterMood.GOOD


@pytest.mark.asyncio
async def test_vulnerability_interaction_transitions_to_worried_caring(test_session: AsyncSession):
    """User venting or feeling wronged/crying transitions emotion to WORRIED/caring protective stance."""
    service = TurnEmotionAppraisalService(test_session)

    result = await service.process_turn_emotion(
        user_input="我今天受委屈了，他们不向着我，我一直在哭，想被偏心……",
        assistant_response="摸摸头，谁欺负你了？我永远都向着你！所有的委屈分我一半。",
        character_id="aevum",
    )

    assert result is not None
    assert result.emotion_type in (EmotionType.WORRIED, EmotionType.CONTENT)


@pytest.mark.asyncio
async def test_assistant_blushing_and_confession_transitions_to_embarrassed(test_session: AsyncSession):
    """Assistant expressively blushing/shy transitions emotion to EMBARRASSED and mood to GOOD."""
    service = TurnEmotionAppraisalService(test_session)

    result = await service.process_turn_emotion(
        user_input="我喜欢你，做我女朋友吧",
        assistant_response="等等……你突然说什么啊？哪有人这样随随便便表白的啊……讨厌啦……害羞了",
        character_id="aevum",
    )

    assert result is not None
    assert result.emotion_type == EmotionType.EMBARRASSED
    char_state = await CharacterStateService(test_session).get_state("aevum")
    assert char_state.mood == CharacterMood.GOOD


@pytest.mark.asyncio
async def test_date_anticipation_transitions_to_excited(test_session: AsyncSession):
    """Planning date itinerary transitions emotion to EXCITED and mood to GOOD."""
    service = TurnEmotionAppraisalService(test_session)

    result = await service.process_turn_emotion(
        user_input="明天下午2点接你，3点去兔子洞，4点去Pavilion看电影，7点Horizon Grill吃晚餐",
        assistant_response="哇！好期待明天的约会！",
        character_id="aevum",
    )

    assert result is not None
    assert result.emotion_type == EmotionType.EXCITED
    char_state = await CharacterStateService(test_session).get_state("aevum")
    assert char_state.mood == CharacterMood.GOOD

