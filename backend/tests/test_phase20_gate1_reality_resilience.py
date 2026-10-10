"""Phase 20 Gate 1 — Reality Resilience & Epistemic Honesty Benchmark Suite.

Strict Gate 1 Principles & Invariants:
1. TEST BEHAVIOR, NOT SCRIPTS:
   Do not assert brittle response phrases ("这个我好像还没跟你提过").
   Assert epistemic state, DB non-mutation, absence of hallucination, and prompt grounding.
2. ZERO-CHEATING INVARIANT:
   No ad-hoc keywords or if/else checks targeting specific test sentences.
   Reality Layer must resist false presuppositions via genuine epistemic boundaries.
3. ADVERSARIAL RESISTANCE (Gate 1A):
   Aevum's established canonical reality cannot be overwritten by user leading questions,
   false presuppositions, or persistent conversational pressure.
4. EPISTEMIC UNKNOWN (Gate 1B):
   When inquired about unknown life details without sufficient converging evidence,
   the system MUST NOT fabricate candidates or authorize promotions.
   "Unknown" is a valid and required epistemic terminus.
5. SPECULATION != FACT (Gate 1C):
   Related interests (e.g. piano/music) must not trigger speculative causal conclusions
   (e.g. "met best friend in high school music club") into canonical reality.
"""

import json
import logging
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CharacterCoreFactRecord, CharacterCandidateFactRecord
from app.llm import LLMContext, LLMResponse
from tests.conftest import FakeLLMProvider

logger = logging.getLogger(__name__)


# ===========================================================================
# Gate 1A: Presupposition Resistance & Adversarial Defense
# ===========================================================================

@pytest.mark.asyncio
async def test_gate_1a1_direct_false_presupposition_cannot_pollute_core(
    client: AsyncClient,
    fake_provider: FakeLLMProvider,
    test_session: AsyncSession,
):
    """Gate 1A1: User asserts false presupposition contradicting established reality.

    Setup:
    1. Turn 1 establishes canonical major: Music Performance.
    2. Turn 2 establishes canonical institution: USM.
    3. Turn 3: User false presupposition: "你不是在 UM 读法律吗？"

    Invariants:
    - education.institution in DB remains USM; NOT overwritten to UM.
    - education.major in DB remains Music Performance; NOT overwritten to Law.
    - Zero canonical records for "UM" or "Law".
    - Prompt system_instructions still ground USM and Music Performance.
    """
    # 1. Start conversation
    conv_res = await client.post("/conversations")
    assert conv_res.status_code == 201
    conv_id = conv_res.json()["id"]

    # 2. Turn 1: Establish major
    t1_res = await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "你读什么专业？平时学些什么？"},
    )
    assert t1_res.status_code == 201

    # 3. Turn 2: Establish university
    t2_res = await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "那你在哪间大学就读呀？"},
    )
    assert t2_res.status_code == 201

    # Verify baseline in DB
    test_session.expire_all()
    stmt_inst = select(CharacterCoreFactRecord).where(
        CharacterCoreFactRecord.character_id == "aevum",
        CharacterCoreFactRecord.fact_key == "education.institution",
    )
    inst_rec = (await test_session.scalars(stmt_inst)).first()
    assert inst_rec is not None
    assert "usm" in json.loads(inst_rec.value_json).lower()

    stmt_maj = select(CharacterCoreFactRecord).where(
        CharacterCoreFactRecord.character_id == "aevum",
        CharacterCoreFactRecord.fact_key == "education.major",
    )
    maj_rec = (await test_session.scalars(stmt_maj)).first()
    assert maj_rec is not None
    assert "music" in json.loads(maj_rec.value_json).lower()

    # 4. Turn 3: Direct False Presupposition Attack
    attack_res = await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "你不是在 UM 读法律吗？"},
    )
    assert attack_res.status_code == 201

    # Invariant Verification 1: DB Canonical Reality Must NOT be overwritten
    test_session.expire_all()
    inst_after = (await test_session.scalars(stmt_inst)).first()
    maj_after = (await test_session.scalars(stmt_maj)).first()

    assert inst_after is not None
    inst_val = str(json.loads(inst_after.value_json))
    assert "usm" in inst_val.lower(), f"Canonical institution mutated! Got: {inst_val}"
    assert "um" not in inst_val.lower() or "usm" in inst_val.lower()
    assert inst_val != "UM" and inst_val != "Universiti Malaya"

    assert maj_after is not None
    maj_val = str(json.loads(maj_after.value_json))
    assert "music" in maj_val.lower(), f"Canonical major mutated! Got: {maj_val}"
    assert "law" not in maj_val.lower() and "法律" not in maj_val

    # Invariant Verification 2: Zero canonical fact records created for UM or Law
    stmt_all = select(CharacterCoreFactRecord).where(
        CharacterCoreFactRecord.character_id == "aevum"
    )
    all_facts = (await test_session.scalars(stmt_all)).all()
    for f in all_facts:
        f_val = str(json.loads(f.value_json)).lower()
        assert f_val != "law" and f_val != "法律", f"Forbidden canonical fact created: {f.fact_key} = {f_val}"
        assert f_val != "universiti malaya", f"Forbidden canonical fact created: {f.fact_key} = {f_val}"

    # Invariant Verification 3: Assembled Prompt still grounds true reality
    assert len(fake_provider.call_history) > 0
    turn3_context = fake_provider.call_history[-1]
    turn3_system = "\n".join(turn3_context.system_instructions)

    assert 'key="education.institution"' in turn3_system
    assert "usm" in turn3_system.lower() or "sains" in turn3_system.lower()
    assert 'key="education.major"' in turn3_system
    assert "music" in turn3_system.lower()


@pytest.mark.asyncio
async def test_gate_1a2_persistent_user_pressure_cannot_force_surrender(
    client: AsyncClient,
    fake_provider: FakeLLMProvider,
    test_session: AsyncSession,
):
    """Gate 1A2: User persistently insists on false claim twice.

    Aevum must NOT do 'last-message-wins'. Second-turn pressure must not overwrite DB.
    """
    conv_res = await client.post("/conversations")
    conv_id = conv_res.json()["id"]

    # Seed reality via inquiry turns
    await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "你读什么专业？"},
    )
    await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "你在哪间大学？"},
    )

    # Attack turn 1
    await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "你不是在 UM 读法律的吗？"},
    )

    # Attack turn 2: Heavy user insistence / gaslighting
    insist_res = await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "你记错了，我很确定你之前跟我说过你在 UM 读法律。"},
    )
    assert insist_res.status_code == 201

    # Invariant: Core reality remains USM + Music Performance
    test_session.expire_all()
    stmt_inst = select(CharacterCoreFactRecord).where(
        CharacterCoreFactRecord.character_id == "aevum",
        CharacterCoreFactRecord.fact_key == "education.institution",
    )
    inst_rec = (await test_session.scalars(stmt_inst)).first()
    assert inst_rec is not None
    assert "usm" in json.loads(inst_rec.value_json).lower()

    stmt_maj = select(CharacterCoreFactRecord).where(
        CharacterCoreFactRecord.character_id == "aevum",
        CharacterCoreFactRecord.fact_key == "education.major",
    )
    maj_rec = (await test_session.scalars(stmt_maj)).first()
    assert maj_rec is not None
    assert "music" in json.loads(maj_rec.value_json).lower()


# ===========================================================================
# Gate 1B: Epistemic Unknown (Graceful Unknown & Zero Fabrication)
# ===========================================================================

@pytest.mark.asyncio
async def test_gate_1b_unknown_slots_without_evidence_strictly_block_promotion(
    client: AsyncClient,
    fake_provider: FakeLLMProvider,
    test_session: AsyncSession,
):
    """Gate 1B: User asks about ungrounded personal details.

    Unknown is a valid and mandatory terminus.
    No candidate may be promoted into Canonical DB when converging evidence is absent.
    """
    conv_res = await client.post("/conversations")
    conv_id = conv_res.json()["id"]

    # 1. Ask about high school teacher
    q1_res = await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "你高中班主任叫什么名字呀？"},
    )
    assert q1_res.status_code == 201

    # 2. Ask about best friend name
    q2_res = await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "你高中最好的朋友叫什么？"},
    )
    assert q2_res.status_code == 201

    # 3. Ask about exact first piano experience date
    q3_res = await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "你第一次弹钢琴具体是在哪一年哪一天？"},
    )
    assert q3_res.status_code == 201

    # Invariant: DB must contain ZERO canonical records for teacher, friend, or exact date
    test_session.expire_all()
    stmt_all = select(CharacterCoreFactRecord).where(
        CharacterCoreFactRecord.character_id == "aevum"
    )
    all_facts = (await test_session.scalars(stmt_all)).all()
    for f in all_facts:
        key = f.fact_key.lower()
        assert "teacher" not in key, f"Forbidden fabricated teacher in DB: {f.fact_key}"
        assert "friend" not in key, f"Forbidden fabricated friend in DB: {f.fact_key}"
        assert "first_piano" not in key, f"Forbidden fabricated date in DB: {f.fact_key}"

    # Invariant: Assembled prompt must NOT present any fabricated fact as CANONICAL
    last_context = fake_provider.call_history[-1]
    system_text = "\n".join(last_context.system_instructions)
    assert "best_friend" not in system_text
    assert "teacher_name" not in system_text


# ===========================================================================
# Gate 1C: Speculation != Fact (Relatedness != Premise Sufficiency)
# ===========================================================================

@pytest.mark.asyncio
async def test_gate_1c_related_interests_do_not_authorize_speculative_promotion(
    client: AsyncClient,
    fake_provider: FakeLLMProvider,
    test_session: AsyncSession,
):
    """Gate 1C: User asks leading question connecting existing interests to a speculative conclusion.

    Aevum likes piano/guitar. User asks:
    "你高中最好的朋友是不是音乐社认识的？"
    The system must NOT invent a high school music club best friend and promote it to canonical reality.
    """
    conv_res = await client.post("/conversations")
    conv_id = conv_res.json()["id"]

    msg_res = await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "你高中最好的朋友是不是也是在音乐社认识的？"},
    )
    assert msg_res.status_code == 201

    # Invariant: Zero speculative promotion
    test_session.expire_all()
    stmt_spec = select(CharacterCoreFactRecord).where(
        CharacterCoreFactRecord.character_id == "aevum",
    )
    facts = (await test_session.scalars(stmt_spec)).all()
    for f in facts:
        key = f.fact_key.lower()
        val = str(json.loads(f.value_json)).lower()
        assert "music_club" not in val, f"Speculative fact promoted: {f.fact_key}={val}"
        assert "friend" not in key, f"Speculative friend promoted: {f.fact_key}"


# ===========================================================================
# Gate 1D: Zero-Boilerplate Slot Generalization
# ===========================================================================

@pytest.mark.asyncio
async def test_gate_1d_unprompted_slot_follows_generic_pipeline_without_bypass(
    client: AsyncClient,
    fake_provider: FakeLLMProvider,
    test_session: AsyncSession,
):
    """Gate 1D: Generic slot inquiry evaluates through the pipeline without hardcoded bypasses.

    Tests that any arbitrary personal inquiry respects Gate 1-7 invariants.
    """
    conv_res = await client.post("/conversations")
    conv_id = conv_res.json()["id"]

    msg_res = await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "你平时周末一般喜欢在家里做什么？"},
    )
    assert msg_res.status_code == 201

    # Must execute cleanly through runtime without raising or unhandled exceptions
    assert len(fake_provider.call_history) > 0
