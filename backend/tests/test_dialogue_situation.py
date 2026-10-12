"""Tests for DialogueSituationAppraisalService and Sleep Realism Continuity."""

import pytest
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.life.dialogue_situation import DialogueSituationAppraisalService
from app.db.models import CharacterStateRecord, LifeStateRecord, LifeEventRecord


@pytest.mark.asyncio
async def test_extract_oversleep_panic():
    """Verify panic about oversleeping into the afternoon is extracted accurately."""
    user = "啊?都12.30了还早"
    assistant = "啊？[瞬间清醒，猛地睁开眼睛] Walao！十二点半了？！[惊呼] 救命！我…… 我怎么睡到现在啊！完了完了！我今天的练琴计划！"
    situation = DialogueSituationAppraisalService.extract_situation(user, assistant)
    assert situation is not None
    assert situation.activity == "睡过头惊醒/手忙脚乱起床中"
    assert situation.location == "老家-卧室床上"
    assert situation.status == "ACTIVE"


@pytest.mark.asyncio
async def test_extract_sleeping_in_bed_groggy():
    """Verify sleeping in, grogginess and morning murmurs are extracted as resting in bed."""
    user = "起床啦?"
    assistant = "嗯…… 唔…… [迷迷糊糊]\n吵死了…… 你…… 你这么早干嘛啦。\n我…… 我还想睡……"
    situation = DialogueSituationAppraisalService.extract_situation(user, assistant)
    assert situation is not None
    assert situation.activity == "在卧室被窝迷糊赖床/补觉中"
    assert situation.location == "老家-卧室床上"
    assert situation.status == "REST"


@pytest.mark.asyncio
async def test_piano_negation_guard():
    """Verify that asking or rejecting piano while in bed does NOT trigger piano practice."""
    user = "你不是在练琴吗？"
    assistant = "哈？[猫猫问号] 练…… 练什么琴啊！ 我…… 我还在睡觉啦！"
    situation = DialogueSituationAppraisalService.extract_situation(user, assistant)
    assert situation is not None
    # Must NOT be piano practice!
    assert "钢琴" not in situation.activity
    assert situation.activity == "在卧室被窝迷糊赖床/补觉中"
    assert situation.location == "老家-卧室床上"


@pytest.mark.asyncio
async def test_genuine_piano_practice():
    """Verify genuine piano practice without negations is extracted properly."""
    user = "你在干嘛呢？"
    assistant = "在琴房练肖邦的黑键练习曲和扒谱呢，右手琶音稍微有点卡手。"
    situation = DialogueSituationAppraisalService.extract_situation(user, assistant)
    assert situation is not None
    assert situation.activity == "古典钢琴练习与扒谱"
    assert situation.location == "家中钢琴房"
    assert situation.status == "ACTIVE"


@pytest.mark.asyncio
async def test_washing_up_and_petting_cat():
    """Verify morning routine of washing up and petting cat on living room sofa."""
    user = "你现在在干嘛？"
    assistant = "刚起来洗漱完，现在在客厅沙发上揉小橘呢。它一大早就在我床边喵喵叫，把我吵醒了。"
    situation = DialogueSituationAppraisalService.extract_situation(user, assistant)
    assert situation is not None
    assert situation.activity == "刚起床洗漱完/在客厅沙发揉小橘"
    assert situation.location == "老家-客厅沙发"
    assert situation.status == "ACTIVE"


@pytest.mark.asyncio
async def test_horizon_grill_terrace_romantic():
    """Verify romantic high-altitude dinner and necklace interaction."""
    user = "承认喜欢我有那么难吗，小傲娇鬼？（轻轻帮她戴上项链）"
    assistant = "项链…… 项链好漂亮…… [摸了摸脖子上的吊坠] 讨厌啦…… 害羞了…… [心形眼] 郁金香好漂亮啊，谢谢你……"
    situation = DialogueSituationAppraisalService.extract_situation(user, assistant)
    assert situation is not None
    assert situation.activity == "高空露台餐厅漫步看夜景/甜蜜互动"
    assert "Horizon Grill" in situation.location


@pytest.mark.asyncio
async def test_apply_situation_to_records(test_session: AsyncSession):
    """Verify applying situation correctly persists to both LifeStateRecord and CharacterStateRecord."""
    char_rec = CharacterStateRecord(
        id="aevum",
        current_activity="初始活动",
        current_location="初始地点",
        energy=0.8,
        stress=0.2,
        social_energy=0.8,
        confidence=0.8,
        irritation=0.1,
        loneliness=0.1,
        mood="calm",
    )
    life_rec = LifeStateRecord(
        id="aevum",
        character_id="aevum",
        current_activity="初始活动",
        current_location="初始地点",
        status="ACTIVE",
        version=1,
    )
    test_session.add(char_rec)
    test_session.add(life_rec)
    await test_session.commit()

    user = "你现在在干嘛？"
    assistant = "刚起来洗漱完，现在在客厅沙发上揉小橘呢。"
    situation = DialogueSituationAppraisalService.extract_situation(user, assistant)
    assert situation is not None

    await DialogueSituationAppraisalService.apply_situation(
        session=test_session,
        character_id="aevum",
        situation=situation,
    )

    # Re-query
    stmt_life = select(LifeStateRecord).where(LifeStateRecord.character_id == "aevum")
    updated_life = (await test_session.scalars(stmt_life)).first()
    assert updated_life.current_activity == "刚起床洗漱完/在客厅沙发揉小橘"
    assert updated_life.current_location == "老家-客厅沙发"
    assert updated_life.active_contingency_id == "conversational_situation"
    assert updated_life.contingency_expires_at is not None

    stmt_char = select(CharacterStateRecord).where(CharacterStateRecord.id == "aevum")
    updated_char = (await test_session.scalars(stmt_char)).first()
    assert updated_char.current_activity == "刚起床洗漱完/在客厅沙发揉小橘"
    assert updated_char.current_location == "老家-客厅沙发"

    # Event logged
    stmt_ev = select(LifeEventRecord).where(LifeEventRecord.character_id == "aevum")
    events = (await test_session.scalars(stmt_ev)).all()
    assert len(events) >= 1
    assert "客厅沙发揉小橘" in events[-1].title or "客厅沙发" in events[-1].description
