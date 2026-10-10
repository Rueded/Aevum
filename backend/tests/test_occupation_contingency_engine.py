"""Tests for Occupation-Specific Life Profiles, Contingency Lock, and AI Life Compiler."""

import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.character.genesis_db_models import CharacterScheduleProfileRecord
from app.db.models import CharacterDefinitionRecord, CharacterStateRecord, LifeEventRecord, LifeStateRecord
from app.life.profile_compiler import ArchetypeProfileSynthesizer, LifeProfileCompiler
from app.life.schedule_engine import LifeScheduleEngine


@pytest.mark.asyncio
async def test_archetype_profile_synthesizer_domains():
    """Verify synthesizer produces rich domain-tailored slots and contingencies."""
    # 1. Doctor
    med_profile = ArchetypeProfileSynthesizer.synthesize(
        occupation="三甲医院急诊规培医生",
        lifestyle_rhythm="经常上夜班，白天拉遮光帘补觉",
        name="林医生",
    )
    assert any("医院" in loc for loc in med_profile["locations"])
    assert any("查房" in slot["activity"] for slot in med_profile["slots"])
    contingency_ids = [c["id"] for c in med_profile["contingencies"]]
    assert "emergency_trauma_intake" in contingency_ids
    assert "code_blue_resuscitation" in contingency_ids

    # 2. Software Developer
    dev_profile = ArchetypeProfileSynthesizer.synthesize(
        occupation="全栈后端架构师 / 独立开源开发者",
        lifestyle_rhythm="夜猫子作息，深夜写代码效率最高",
        name="阿澈",
    )
    assert any("工位" in loc or "机房" in loc for loc in dev_profile["locations"])
    assert any("编码" in slot["activity"] or "代码" in slot["activity"] for slot in dev_profile["slots"])
    dev_contingency_ids = [c["id"] for c in dev_profile["contingencies"]]
    assert "production_outage_hotfix" in dev_contingency_ids
    assert "git_merge_conflict_hell" in dev_contingency_ids

    # 3. Barista / Service
    barista_profile = ArchetypeProfileSynthesizer.synthesize(
        occupation="精品咖啡馆店长兼咖啡师",
        lifestyle_rhythm="早起备料开店，下午研发特调",
        name="苏苏",
    )
    assert any("吧台" in loc for loc in barista_profile["locations"])
    barista_contingency_ids = [c["id"] for c in barista_profile["contingencies"]]
    assert "machine_breakdown_rush" in barista_contingency_ids


@pytest.mark.asyncio
async def test_compile_and_store_profile(test_session: AsyncSession, monkeypatch):
    """Verify LifeProfileCompiler atomically persists schedule profile to SQLite."""
    async def mock_compile(cls, occupation, lifestyle_rhythm="", background="", name="Aevum"):
        return ArchetypeProfileSynthesizer.synthesize(occupation, lifestyle_rhythm, background, name)

    monkeypatch.setattr(LifeProfileCompiler, "compile_profile", classmethod(mock_compile))
    char_id = "test_doc_char"
    char_def = CharacterDefinitionRecord(
        id=char_id,
        name="陆医生",
        age=26,
        occupation="急诊重症监护医生",
        background="三甲医院急诊中心，负责抢救与重症监护",
    )
    test_session.add(char_def)
    await test_session.commit()

    # Compile and store
    rec = await LifeProfileCompiler.compile_and_store(
        db=test_session,
        character_id=char_id,
        occupation=char_def.occupation,
        lifestyle_rhythm="三班倒，抗压能力强",
        background=char_def.background,
        name=char_def.name,
    )
    await test_session.commit()

    assert rec.character_id == char_id
    assert "急诊" in rec.occupation

    # Query back from DB
    loaded = (await test_session.scalars(
        select(CharacterScheduleProfileRecord).where(CharacterScheduleProfileRecord.character_id == char_id)
    )).first()
    assert loaded is not None
    slots = json.loads(loaded.slots_json)
    contingencies = json.loads(loaded.contingencies_json)
    assert len(slots) >= 4
    assert len(contingencies) >= 3


@pytest.mark.asyncio
async def test_schedule_reconcile_custom_doctor(test_session: AsyncSession, monkeypatch):
    """Verify schedule reconciliation matches custom doctor slots instead of generic fallbacks."""
    async def mock_compile(cls, occupation, lifestyle_rhythm="", background="", name="Aevum"):
        return ArchetypeProfileSynthesizer.synthesize(occupation, lifestyle_rhythm, background, name)

    monkeypatch.setattr(LifeProfileCompiler, "compile_profile", classmethod(mock_compile))
    tz = "Asia/Shanghai"
    t_morning = datetime(2026, 10, 9, 8, 30, 0, tzinfo=ZoneInfo(tz))
    char_id = "doc_patient_rounds"

    char_def = CharacterDefinitionRecord(
        id=char_id,
        name="叶医生",
        age=27,
        occupation="急诊外科住院医师",
        background="负责急诊清创缝合与病房查房",
    )
    test_session.add(char_def)
    await test_session.commit()

    await LifeProfileCompiler.compile_and_store(
        db=test_session,
        character_id=char_id,
        occupation=char_def.occupation,
        lifestyle_rhythm="晨会交接，严谨细致",
        name=char_def.name,
    )
    await test_session.commit()

    # Reconcile schedule at 08:30 morning
    life_record = await LifeScheduleEngine.reconcile_schedule(
        session=test_session,
        character_id=char_id,
        dt_utc=t_morning,
        timezone_str=tz,
        force=True,
    )
    await test_session.commit()

    # Must reflect medical ward handoff / rounds / consultation, NOT piano practice
    assert any(kw in life_record.current_activity for kw in ("查房", "交接", "会诊", "急诊", "门诊", "手术", "病房", "医疗"))
    assert any(kw in life_record.current_location for kw in ("医院", "病房", "诊室", "科室", "办公室", "急诊", "抢救"))
    assert "钢琴" not in life_record.current_activity


@pytest.mark.asyncio
async def test_contingency_lock_and_expiration_lifecycle(test_session: AsyncSession):
    """Verify contingency locks during duration and expires cleanly into resolution event."""
    char_id = "prog_fire_char"
    now_utc = datetime(2026, 10, 9, 14, 0, 0, tzinfo=timezone.utc)
    expires_at = now_utc + timedelta(hours=2)

    # Setup character definition and life state with active contingency
    char_def = CharacterDefinitionRecord(
        id=char_id,
        name="小周",
        age=24,
        occupation="后端研发工程师",
        background="负责线上交易系统开发",
    )
    test_session.add(char_def)

    life_record = LifeStateRecord(
        id=char_id,
        character_id=char_id,
        current_activity="线上生产集群报警紧急排查修复 (Production Outage Emergency)",
        current_location="公司开放式工位双屏前",
        status="BUSY",
        active_contingency_id="production_outage_hotfix",
        active_contingency_title="线上生产环境告警突发救火修复",
        contingency_expires_at=expires_at,
        version=1,
    )
    test_session.add(life_record)
    await test_session.commit()

    # 1. During contingency window (+30 min): must remain locked
    t_mid = now_utc + timedelta(minutes=30)
    reconciled_mid = await LifeScheduleEngine.reconcile_schedule(
        session=test_session,
        character_id=char_id,
        dt_utc=t_mid,
    )
    assert reconciled_mid.active_contingency_id == "production_outage_hotfix"
    assert "线上" in reconciled_mid.current_activity
    assert reconciled_mid.status == "BUSY"

    # 2. After expiration window (+2h 15min): must expire, clear contingency, and emit resolution event
    t_after = now_utc + timedelta(hours=2, minutes=15)
    reconciled_after = await LifeScheduleEngine.reconcile_schedule(
        session=test_session,
        character_id=char_id,
        dt_utc=t_after,
    )
    await test_session.commit()

    assert reconciled_after.active_contingency_id is None
    assert reconciled_after.contingency_expires_at is None

    # Check that resolution LifeEventRecord was written
    events = (await test_session.scalars(
        select(LifeEventRecord).where(LifeEventRecord.character_id == char_id)
    )).all()
    assert any("突发状况已告一段落" in ev.title for ev in events)
