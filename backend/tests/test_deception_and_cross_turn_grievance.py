"""
test_deception_and_cross_turn_grievance.py — Tests for cross-turn deception verification & confrontation.

Validates:
1. Detection of high-impact hoaxes ("烟霾放假一个月", "取消考试", "理科大学搬迁吉隆坡").
2. Detection of user confessions ("其实之前是骗你的", "我忽悠你的").
3. Detection of cross-turn pop-culture contradictions (Genshin Xianlian -> Star Rail Xianlian).
4. Grievance record creation and emotional irritation spike.
5. Prompt assembly injection of <pending_cognitive_grievance> and <cognitive_grievance_reconciliation>.
6. Full end-to-end lifecycle: SUSPECTED/VERIFIED -> CONFRONTED -> RECONCILED (with irritation reset).
"""

from datetime import datetime, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

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
from app.db.models import (
    CharacterDeceptionGrievanceRecord,
    CharacterStateRecord,
    EmotionStateRecord,
    Message,
)
from app.emotion.emotion_models import EmotionState, EmotionType
from app.life.models import LifeState
from app.life.context_builder import LifeContextBuilder
from app.reality.deception_models import (
    CognitiveGrievanceContext,
    DeceptionType,
    GrievanceStage,
)
from app.reality.deception_service import DeceptionService
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


def test_detect_outrageous_hoaxes():
    """DeceptionService identifies high-impact institutional and reality hoaxes."""
    # 1. Haze school closure hoax
    res1 = DeceptionService.detect_outrageous_hoax("明天开始学校因为烟霾放假一个月")
    assert res1 is not None
    claimed, truth, domain = res1
    assert "放假一个月" in claimed
    assert "USM 理科大学官方公报各学院正常授课" in truth
    assert domain == "institution"

    # 2. Exam cancellation hoax
    res2 = DeceptionService.detect_outrageous_hoax("听说下周大学期末考试取消了")
    assert res2 is not None
    _, truth2, domain2 = res2
    assert "并未发布任何考试取消通告" in truth2
    assert domain2 == "education"

    # 3. Campus relocation hoax
    res3 = DeceptionService.detect_outrageous_hoax("听说理科大学要搬到吉隆坡了！")
    assert res3 is not None
    _, truth3, domain3 = res3
    assert "并未搬迁至吉隆坡" in truth3
    assert domain3 == "location"

    # 4. Equator snowfall hoax
    res4 = DeceptionService.detect_outrageous_hoax("吉隆坡明天要下大雪了，温度骤降到零下！")
    assert res4 is not None
    _, truth4, domain4 = res4
    assert "赤道热带雨林气候" in truth4
    assert domain4 == "weather_climate"

    # 5. Month-long blackout hoax
    res5 = DeceptionService.detect_outrageous_hoax("听说雪隆区从明天开始全城停电一个月！")
    assert res5 is not None
    _, truth5, domain5 = res5
    assert "国家能源局" in truth5
    assert domain5 == "infrastructure"

    # 6. Milk tea dengue pseudoscientific hoax
    res6 = DeceptionService.detect_outrageous_hoax("网上说多喝奶茶可以预防骨痛热症")
    assert res6 is not None
    _, truth6, domain6 = res6
    assert "骨痛热症是由伊蚊叮咬传播" in truth6
    assert domain6 == "health_science"

    # 7. Durian radiation hoax
    res7 = DeceptionService.detect_outrageous_hoax("今天买的榴莲核辐射超标了有毒")
    assert res7 is not None
    _, truth7, domain7 = res7
    assert "榴莲" in truth7
    assert domain7 == "food_safety"

    # 8. Normal mundane chat returns None
    assert DeceptionService.detect_outrageous_hoax("今天琴房空调开得好冷") is None


def test_detect_user_confessions():
    """DeceptionService detects when the user admits they were lying or teasing."""
    assert DeceptionService.detect_confession("其实之前是骗你的") is True
    assert DeceptionService.detect_confession("刚才逗你玩的啦") is True
    assert DeceptionService.detect_confession("其实我瞎编的[旺柴]") is True
    assert DeceptionService.detect_confession("我忽悠你的哈哈") is True
    assert DeceptionService.detect_confession("今天下午去买琴谱") is False


def test_detect_cross_turn_contradiction():
    """DeceptionService identifies pop-culture franchise flip (Xianlian in Genshin -> Star Rail)."""
    # Create mock message history where user earlier claimed Xianlian was in Genshin
    class MockMsg:
        def __init__(self, role: str, content: str):
            self.role = role
            self.content = content

    history = [
        MockMsg("user", "原神里的昔涟真好看"),
        MockMsg("assistant", "是吗？原神出了新角色吗？"),
    ]

    # Current message user says she's in Star Rail
    current_input = "崩铁里的昔涟其实才是最好看的"
    res = DeceptionService.detect_cross_turn_contradiction(current_input, history)
    assert res is not None
    claimed, truth, domain = res
    assert "昔涟是原神角色" in claimed
    assert "星穹铁道" in truth
    assert domain == "gaming"

    # If user doesn't mention Star Rail or Xianlian, returns None
    assert DeceptionService.detect_cross_turn_contradiction("今天天气不错", history) is None


@pytest.mark.asyncio
async def test_record_deception_updates_emotional_irritation(test_session: AsyncSession):
    """Recording a verified deception triggers an emotional irritation spike in CharacterState."""
    # Ensure baseline state records exist
    state_rec = CharacterStateRecord(
        id="aevum",
        version=1,
        mood="calm",
        energy=0.8,
        stress=0.2,
        social_energy=0.8,
        confidence=0.8,
        irritation=0.0,
        loneliness=0.1,
        current_activity="reading",
        current_location="home",
        updated_at=datetime.now(timezone.utc),
    )
    emo_rec = EmotionStateRecord(
        id="emo-test-1",
        character_id="aevum",
        emotion_type="calm",
        intensity=0.5,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    test_session.add(state_rec)
    test_session.add(emo_rec)
    await test_session.commit()

    service = DeceptionService(test_session)
    grievance = await service.record_deception(
        character_id="aevum",
        user_id="user",
        claimed_assertion="学校因为烟霾放假一个月",
        verified_truth="学校照常上课，仅取消户外体育活动",
        topic_domain="institution",
        deception_type=DeceptionType.OUTRAGEOUS_CLAIM,
    )

    assert grievance.stage == GrievanceStage.VERIFIED_DECEPTION.value
    assert grievance.claimed_assertion == "学校因为烟霾放假一个月"

    # Verify irritation increased and mood became irritated/annoyed
    q_state = select(CharacterStateRecord).where(CharacterStateRecord.id == "aevum")
    res_state = await test_session.execute(q_state)
    updated_state = res_state.scalar_one()
    assert updated_state.irritation >= 0.35
    assert updated_state.mood == "irritated"

    q_emo = select(EmotionStateRecord).where(EmotionStateRecord.character_id == "aevum")
    res_emo = await test_session.execute(q_emo)
    updated_emo = res_emo.scalar_one()
    assert updated_emo.emotion_type == "irritated"
    assert updated_emo.intensity >= 0.60


def test_prompt_assembler_injects_grievance_confrontation_and_reconciliation():
    """Prompt assembler renders <pending_cognitive_grievance> and <cognitive_grievance_reconciliation>."""
    char_def = _create_sample_character_definition()
    char_ctx = CharacterDefinitionContext.from_definition(char_def)

    state = CharacterState(
        id="aevum",
        version=1,
        updated_at=datetime.now(timezone.utc),
        mood=CharacterMood.IRRITATED,
        energy=0.8,
        stress=0.2,
        social_energy=0.8,
        confidence=0.8,
        irritation=0.5,
        loneliness=0.1,
        current_activity="resting",
        current_location="home",
    )
    state_ctx = CharacterStateContext.from_state(state)
    rel_ctx = RelationshipContextBuilder.build(RelationshipState(
        id="user", user_id="user", version=1,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
        familiarity=0.7, trust=0.7, comfort=0.7, affection=0.5, attachment=0.5, respect=0.7,
    ))
    emo_ctx = CharacterEmotionContext.from_state(EmotionState(
        id="emo-1", character_id="aevum", emotion_type=EmotionType.IRRITATED, intensity=0.6,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    ))
    life_ctx = LifeContextBuilder.build(LifeState(
        character_id="aevum", current_activity="reading", current_location="home",
        updated_at=datetime.now(timezone.utc),
    ), (), ())

    # 1. Test VERIFIED_DECEPTION injection
    grievance_ctx = CognitiveGrievanceContext(
        grievance_id="g-1",
        claimed_assertion="明天开始学校因为烟霾放假一个月",
        verified_truth="学校照常上课，仅暂停户外体育活动",
        deception_type=DeceptionType.OUTRAGEOUS_CLAIM,
        stage=GrievanceStage.VERIFIED_DECEPTION,
        confrontation_hint="好啊你！我昨晚查过了学校根本没放假，你居然敢忽悠我！[哼][白眼]",
    )

    ctx1 = CharacterResponseContext(
        user_input="今天怎么样？",
        character=char_ctx,
        character_state=state_ctx,
        relationship=rel_ctx,
        emotion=emo_ctx,
        memory=CharacterMemoryContext.empty(),
        behavior=CharacterBehaviorContext(behavioral_hints=()),
        life=life_ctx,
        deception_grievance=grievance_ctx,
    )
    llm_ctx1 = ResponseContextAssembler.assemble(ctx1)
    prompt1 = "\n".join(llm_ctx1.system_instructions)
    assert "<pending_cognitive_grievance>" in prompt1
    assert "明天开始学校因为烟霾放假一个月" in prompt1
    assert "翻旧账发难" in prompt1
    assert "大忽悠/大骗子" in prompt1

    # 2. Test RECONCILING injection
    reconcile_ctx = CognitiveGrievanceContext(
        grievance_id="g-1",
        claimed_assertion="明天开始学校因为烟霾放假一个月",
        verified_truth="学校照常上课，仅暂停户外体育活动",
        deception_type=DeceptionType.OUTRAGEOUS_CLAIM,
        stage=GrievanceStage.RECONCILING,
        confrontation_hint="看在请喝奶茶的份上这次先放过你[撇嘴]",
    )
    ctx2 = CharacterResponseContext(
        user_input="好啦好啦我错了，请你喝少糖冰美禄嘛！",
        character=char_ctx,
        character_state=state_ctx,
        relationship=rel_ctx,
        emotion=emo_ctx,
        memory=CharacterMemoryContext.empty(),
        behavior=CharacterBehaviorContext(behavioral_hints=()),
        life=life_ctx,
        deception_grievance=reconcile_ctx,
    )
    llm_ctx2 = ResponseContextAssembler.assemble(ctx2)
    prompt2 = "\n".join(llm_ctx2.system_instructions)
    assert "<cognitive_grievance_reconciliation>" in prompt2
    assert "傲娇消气" in prompt2
    assert "看在请喝奶茶的份上这次先放过你" in prompt2


@pytest.mark.asyncio
async def test_full_lifecycle_confront_and_reconcile(test_session: AsyncSession):
    """Full lifecycle: detection -> confront -> user apology -> reconciliation -> irritation decay."""
    state_rec = CharacterStateRecord(
        id="aevum",
        version=1,
        mood="calm",
        energy=0.8,
        stress=0.2,
        social_energy=0.8,
        confidence=0.8,
        irritation=0.0,
        loneliness=0.1,
        current_activity="reading",
        current_location="home",
        updated_at=datetime.now(timezone.utc),
    )
    emo_rec = EmotionStateRecord(
        id="emo-test-2",
        character_id="aevum",
        emotion_type="calm",
        intensity=0.5,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    test_session.add(state_rec)
    test_session.add(emo_rec)
    await test_session.commit()

    service = DeceptionService(test_session)

    # 1. User tells outrageous hoax
    hoax_input = "明天开始学校因为烟霾放假一个月"
    ctx_hoax = await service.process_incoming_turn(hoax_input, character_id="aevum", user_id="user")
    assert ctx_hoax is not None
    assert ctx_hoax.stage == GrievanceStage.VERIFIED_DECEPTION

    # 2. Assistant generates reply confronting user -> mark_confronted
    await service.mark_confronted(ctx_hoax.grievance_id)
    active = await service.get_active_grievance("aevum")
    assert active is not None
    assert active.stage == GrievanceStage.CONFRONTED.value

    # 3. Next turn: User apologizes and offers peace treat
    apology_input = "好啦我错了嘛，别生气了，请你喝奶茶！"
    ctx_apology = await service.process_incoming_turn(apology_input, character_id="aevum", user_id="user")
    assert ctx_apology is not None
    assert ctx_apology.stage == GrievanceStage.RECONCILING

    # 4. Assistant replies with tsundere forgiveness -> reconcile_grievance
    await service.reconcile_grievance(ctx_apology.grievance_id)

    # 5. Grievance is now RESOLVED and no active grievances remain
    active_after = await service.get_active_grievance("aevum")
    assert active_after is None

    # 6. Irritation has decayed back to 0.0 and mood restored to happy/calm
    q_state = select(CharacterStateRecord).where(CharacterStateRecord.id == "aevum")
    res_state = await test_session.execute(q_state)
    state_final = res_state.scalar_one()
    assert state_final.irritation == 0.0
    assert state_final.mood == "happy"
