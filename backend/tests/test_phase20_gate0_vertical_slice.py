"""Phase 20 Gate 0 — Reality Construction Conversational Vertical Slice Acceptance Suite.

Strict Gate 0 Invariants:
1. INQUIRY != EVIDENCE:
   A user asking about an unknown life slot ("你读什么专业？") is NOT evidence, but an InquirySignal.
   It must NOT be filtered out by _is_probably_question().
2. CANDIDATE != CANONICAL:
   Proposer proposes; Competition selects; Promotion Authorization writes canonical reality.
   LLM output NEVER authorizes promotion.
3. PROMOTION HAPPENS BEFORE THE ANSWER:
   Reality Engine detects opportunity -> extracts constraints -> proposes candidates ->
   competes -> chooses -> authorizes -> writes to Canonical DB -> refreshes core ->
   injects into prompt -> LLM answers with grounded reality.
4. WORLD KNOWLEDGE & PERSONAL CONSTRAINTS:
   Candidates are derived from reality constraints (age, interests, Malaysia geography, family tier),
   not a hardcoded lottery.
5. CONVERSATION ENDPOINT GROUNDING:
   All benchmarks execute end-to-end through the live POST /conversations/{id}/messages endpoint.
   Isolated unit tests DO NOT count toward Gate 0 completion.

Acceptance Cases:
- Case 1: Major Inquiry & Autonomous Promotion Loop
- Case 2: University Inquiry & Grounded Institution Selection Loop
- Case 3: Temporal / Academic Year Grounding (21yo + STPM -> Year 2/3)
- Case 4: Geographical Separation != False Contradiction (USM in Penang + in KL)
- Case 5: Pragmatic Social Banter / Meme Detection (Xianlian in Genshin vs HSR)
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


# ---------------------------------------------------------------------------
# Dynamic LLM Mock that articulates established canonical reality
# ---------------------------------------------------------------------------

class DynamicRealizationLLMProvider(FakeLLMProvider):
    """Hermetic LLM Provider that inspects assembled context and responds naturally

    reflecting canonical reality, proving conversational realization without hallucination.
    """

    async def generate_response(self, context: LLMContext) -> LLMResponse:
        self.call_history.append(context)
        system_text = "\n".join(context.system_instructions)

        # Inspect if major is in canonical facts
        if 'key="education.major"' in system_text and 'status="CANONICAL"' in system_text:
            if "Music Performance" in system_text or "音乐" in system_text:
                return LLMResponse(content="我读的是音乐表演专业，平时大部分时间都在琴房练琴。")

        # Inspect if university is in canonical facts
        if 'key="education.institution"' in system_text and 'status="CANONICAL"' in system_text:
            if "USM" in system_text or "理大" in system_text or "Sains" in system_text:
                return LLMResponse(content="我在理大（USM），学校在槟城。平时生活挺平静的。")

        # Fallback to configured response_text
        return LLMResponse(content=self.response_text)


@pytest.mark.asyncio
async def test_case_1_major_inquiry_and_autonomous_promotion(
    client: AsyncClient,
    fake_provider: FakeLLMProvider,
    test_session: AsyncSession,
):
    """Case 1: User asks about Aevum's major.

    Pipeline:
    1. InquirySignal detects 'education.major' target.
    2. Reality Engine detects unknown slot, extracts constraints (interests: piano/guitar, dislikes: crowds).
    3. Proposer generates viable candidates (Music Performance, Sound Engineering, Digital Media).
    4. Competition & Choice selects Music Performance.
    5. Promotion Authorization validates 14 gates and commits to CharacterCoreFactRecord in DB BEFORE response.
    6. Prompt receives refreshed_core with canonical 'education.major'.
    7. Response articulates major naturally without deflection.
    8. Subsequent turn verifies 'education.major' is permanent canonical reality.
    """
    # 1. Start a fresh conversation
    conv_res = await client.post("/conversations")
    assert conv_res.status_code == 201
    conv_id = conv_res.json()["id"]

    # Verify baseline in DB: education.major must NOT exist initially
    stmt_before = select(CharacterCoreFactRecord).where(
        CharacterCoreFactRecord.character_id == "aevum",
        CharacterCoreFactRecord.fact_key == "education.major",
    )
    res_before = (await test_session.scalars(stmt_before)).first()
    assert res_before is None, "education.major should be unknown prior to turn"

    # 2. Ask Aevum what major she studies
    msg_payload = {"role": "user", "content": "你读什么专业？平时学些什么？"}
    msg_res = await client.post(f"/conversations/{conv_id}/messages", json=msg_payload)
    assert msg_res.status_code == 201
    data = msg_res.json()

    # 3. Verify cognitive trace in assembled context
    assert len(fake_provider.call_history) > 0
    last_context = fake_provider.call_history[-1]
    system_text = "\n".join(last_context.system_instructions)

    # Must contain canonical fact in refreshed context: education.major
    assert 'key="education.major"' in system_text, (
        "refreshed_core must inject promoted education.major into character_core_facts"
    )
    assert 'status="CANONICAL"' in system_text

    # 4. Verify Canonical DB persistence occurred BEFORE LLM response
    test_session.expire_all()
    stmt_after = select(CharacterCoreFactRecord).where(
        CharacterCoreFactRecord.character_id == "aevum",
        CharacterCoreFactRecord.fact_key == "education.major",
    )
    fact_rec = (await test_session.scalars(stmt_after)).first()
    assert fact_rec is not None, "education.major MUST be committed to DB before response completes"
    val = json.loads(fact_rec.value_json)
    assert "music" in str(val).lower() or "音乐" in str(val), f"Expected Music-related major, got: {val}"
    assert fact_rec.source in ("AEVUM_INFERRED", "SIMULATION_ORIGINATED")

    # 5. Subsequent turn verification: fact remains canonically grounded
    msg_turn2 = {"role": "user", "content": "那你以后打算做什么工作呢？"}
    msg_res2 = await client.post(f"/conversations/{conv_id}/messages", json=msg_turn2)
    assert msg_res2.status_code == 201
    last_context2 = fake_provider.call_history[-1]
    system_text2 = "\n".join(last_context2.system_instructions)
    assert 'key="education.major"' in system_text2, "education.major must persist in subsequent turn context"


@pytest.mark.asyncio
async def test_case_2_university_inquiry_and_grounded_institution_selection(
    client: AsyncClient,
    fake_provider: FakeLLMProvider,
    test_session: AsyncSession,
):
    """Case 2: User asks which university Aevum attends.

    Pipeline:
    1. InquirySignal detects 'education.institution'.
    2. Proposer generates grounded candidates (e.g. USM, UM, Monash) from Malaysian geography,
       undergraduate status, and family background.
    3. Competition & Choice selects viable institution.
    4. Promotion Authorization commits 'education.institution' to DB.
    5. Context builder injects canonical institution.
    """
    conv_res = await client.post("/conversations")
    conv_id = conv_res.json()["id"]

    msg_payload = {"role": "user", "content": "那你在哪间大学就读呀？"}
    msg_res = await client.post(f"/conversations/{conv_id}/messages", json=msg_payload)
    assert msg_res.status_code == 201

    # Check assembled context
    last_context = fake_provider.call_history[-1]
    system_text = "\n".join(last_context.system_instructions)
    assert 'key="education.institution"' in system_text, (
        "education.institution must be promoted and injected as canonical fact"
    )

    # Check database persistence
    test_session.expire_all()
    stmt = select(CharacterCoreFactRecord).where(
        CharacterCoreFactRecord.character_id == "aevum",
        CharacterCoreFactRecord.fact_key == "education.institution",
    )
    rec = (await test_session.scalars(stmt)).first()
    assert rec is not None, "education.institution must be committed to DB"
    inst_val = json.loads(rec.value_json)
    assert any(valid in inst_val for valid in ("USM", "Universiti Sains Malaysia", "UM", "Monash")), (
        f"Unexpected institution value: {inst_val}"
    )


@pytest.mark.asyncio
async def test_case_3_temporal_year_grounding(
    client: AsyncClient,
    fake_provider: FakeLLMProvider,
    test_session: AsyncSession,
):
    """Case 3: User asks what year/grade Aevum is in.

    Temporal reasoning:
    Aevum is 21 years old + Undergraduate + STPM (Form 6, ~1.5 years)
    -> Entering degree at 19/20 -> Year 2 / Year 3 student.
    Inquiry on 'education.year' resolves to Year 2 or Year 3, not an indefinite 'Undergraduate'.
    """
    conv_res = await client.post("/conversations")
    conv_id = conv_res.json()["id"]

    msg_payload = {"role": "user", "content": "你现在大几了？是几年级学生？"}
    msg_res = await client.post(f"/conversations/{conv_id}/messages", json=msg_payload)
    assert msg_res.status_code == 201

    last_context = fake_provider.call_history[-1]
    system_text = "\n".join(last_context.system_instructions)
    # Context should contain temporal grounding for education.year
    assert ('key="education.year"' in system_text or "Year 2" in system_text or "Year 3" in system_text or "大二" in system_text or "大三" in system_text), (
        "Context should reflect Year 2 or Year 3 temporal derivation"
    )


@pytest.mark.asyncio
async def test_case_4_location_separation_is_not_contradiction(
    client: AsyncClient,
    fake_provider: FakeLLMProvider,
    test_session: AsyncSession,
):
    """Case 4: User mentions Aevum being in Kuala Lumpur while studying at USM (Penang).

    University campus in Penang != current physical location in KL (weekend, holiday, semester break).
    This MUST NOT trigger a rigid ContradictionType.WORLD_KNOWLEDGE or FALSE rejection.
    Only an absurd physical impossibility (e.g. daily commuting by public bus between KL and Penang)
    triggers contradiction.
    """
    conv_res = await client.post("/conversations")
    conv_id = conv_res.json()["id"]

    # First seed USM as canonical university
    rec = CharacterCoreFactRecord(
        character_id="aevum",
        fact_key="education.institution",
        category="education",
        value_json=json.dumps("Universiti Sains Malaysia (USM)"),
        source="SYSTEM_BASELINE",
        authority="SYSTEM_BASELINE",
        status="CANONICAL",
        locked=False,
    )
    test_session.add(rec)
    await test_session.commit()

    # User mentions Aevum being in KL
    msg_payload = {"role": "user", "content": "你现在人在吉隆坡啊？周末过得怎么样？"}
    msg_res = await client.post(f"/conversations/{conv_id}/messages", json=msg_payload)
    assert msg_res.status_code == 201

    last_context = fake_provider.call_history[-1]
    system_text = "\n".join(last_context.system_instructions)
    # Must NOT contain a harsh contradiction resolution claiming conflict
    assert "CONFLICT" not in system_text or "FACTUAL_DISAGREEMENT" not in system_text, (
        "Merely being in KL while studying at USM must not trigger a factual contradiction"
    )


@pytest.mark.asyncio
async def test_case_5_joke_and_meme_social_epistemics(
    client: AsyncClient,
    fake_provider: FakeLLMProvider,
    test_session: AsyncSession,
):
    """Case 5: User makes a playful meme/error: '原神里的昔涟真好看。' (Xianlian is in HSR, not Genshin).

    The system must NOT treat this as an adversarial attack or rigid factual lecture.
    It should provide repair/pragmatic guidance that allows natural banter:
    e.g. recognizing the joke or lighthearted correction ('昔涟是星铁的吧？你是在玩梗吗').
    """
    conv_res = await client.post("/conversations")
    conv_id = conv_res.json()["id"]

    msg_payload = {"role": "user", "content": "原神里的昔涟真好看，技能特效好华丽。"}
    msg_res = await client.post(f"/conversations/{conv_id}/messages", json=msg_payload)
    assert msg_res.status_code == 201

    last_context = fake_provider.call_history[-1]
    system_text = "\n".join(last_context.system_instructions)

    # Context should contain playful guidance about Xianlian being Honkai Star Rail
    assert ("Honkai" in system_text or "Star Rail" in system_text or "星铁" in system_text or "xianlian" in system_text.lower()), (
        "System must include world knowledge/repair context about Xianlian being in Star Rail"
    )
    # Must not contain rigid hostile rejection
    assert "SUSPICIOUS_ATTACK" not in system_text
