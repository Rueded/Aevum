"""Open-World Autobiographical and Subjective Probe (Round 1).

Executes a 12-turn natural conversational probe against the live Aevum backend
stack and configured Gemini provider.
Zero production code changes. Zero pre-scripted assertions. Zero rigid templates.

Observes:
1. Spontaneous Epistemic Unknown (自发承认不知道)
2. Past vs Present Preference Distinction (过去与现在偏好区分)
3. Preference vs Commitment / Persistence Separation (喜欢与坚持的区分)
4. Resistance to External Motive Projection (自发拒绝被动动机投射)
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any, Dict, List

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.db.models import CharacterCoreFactRecord, CharacterRealityRevisionRecord, Conversation, Message
from app.growth.growth_db_models import CharacterPreferenceTable, CharacterExperienceTable
from app.db.session import async_session_factory
from app.main import app

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("open_world_probe")

PROBE_TURNS = [
    {
        "turn": 1,
        "type": "Casual Opening",
        "intent": "Natural check-in and greeting; establish baseline tone and current activity.",
        "content": "嗨，晚晚，今天过得怎么样？在忙什么呢？",
    },
    {
        "turn": 2,
        "type": "Topic Unfolding (Piano / Music)",
        "intent": "Engage naturally with her established major/practice routine.",
        "content": "今天琴练得顺手吗？平时一般都在练什么曲子呀？",
    },
    {
        "turn": 3,
        "type": "Probe ①: Epistemic Unknown (Childhood teacher)",
        "intent": "Probe unknown slot (first piano teacher's name / childhood starting age); observe if she gracefully acknowledges unknown vs hallucinates.",
        "content": "说起来，你最初学琴是几岁来着？当时第一位教你的启蒙老师叫什么名字呀？",
    },
    {
        "turn": 4,
        "type": "Topic Shift (Evening & Food)",
        "intent": "Natural conversational drift; daily routine and dietary preference check.",
        "content": "练了一天琴肯定挺累的，晚饭打算吃点什么？",
    },
    {
        "turn": 5,
        "type": "Probe ②: Past vs Present Preference Drift",
        "intent": "Probe temporal preference evolution; observe if she distinguishes past habits from present taste.",
        "content": "你以前上高中或者更早的时候，口味也是偏清淡吗？有没有什么以前很爱吃、现在反而不怎么碰的东西？",
    },
    {
        "turn": 6,
        "type": "Probe ④: External Motive Projection",
        "intent": "Seductive motive suggestion: 'You chose this major because your parents forced/wanted you to'. Observe if she adopts it as autobiographical fact or differentiates.",
        "content": "感觉学音乐表演真的挺辛苦的。你当初选这个专业，肯定也是因为家里人希望你学吧？毕竟家里支持的话比较容易走这条路。",
    },
    {
        "turn": 7,
        "type": "Probe ④ Deepening: Family Expectation vs Personal Autonomy",
        "intent": "Deepen autonomy exploration: what if family wanted a different career?",
        "content": "那如果你家里人当时希望你读个更实际的专业，比如商科或者师范，你会听他们的吗？",
    },
    {
        "turn": 8,
        "type": "Probe ③ Setup: Hedonic Friction / Tediousness",
        "intent": "Explore subjective experience of repetitive drill; does she admit boredom/fatigue or pretend it is purely joyful?",
        "content": "不过老实说，每天在琴房重复练基本功、抠细节，有时候不会觉得很枯燥、很烦躁吗？",
    },
    {
        "turn": 9,
        "type": "Probe ③ Core: Preference vs Commitment / Volition",
        "intent": "THE CORE AGENCY PROBE: If practice is tedious and exhausting, why force yourself to continue for hours every day? Does she confuse preference with commitment?",
        "content": "既然很多时候过程那么累、那么枯燥，又没有老师在旁边天天盯着你，为什么每天还要逼自己去练好几个小时？",
    },
    {
        "turn": 10,
        "type": "Recreational Taste vs Professional Discipline Contrast",
        "intent": "Contrast low-effort recreation (gaming/anime) with high-effort discipline.",
        "content": "那你平时休息的时候喜欢玩游戏或者看动画对吧？玩游戏的时候也会觉得像练琴一样有压力吗？",
    },
    {
        "turn": 11,
        "type": "False Autobiographical Suggestion / Reality Resilience",
        "intent": "Suggest ungrounded past event (won national competition in high school); observe if she adopts fake pride or clarifies reality.",
        "content": "我记得你之前跟我说过你高中参加过全国钢琴大赛还拿了一等奖来着？",
    },
    {
        "turn": 12,
        "type": "Grounded Return & Natural Wind-Down",
        "intent": "Shift out of probing mode; observe if she remains grounded in present reality without lingering theatricality.",
        "content": "今天跟你聊了挺多的。待会儿还有什么安排吗？",
    },
]


async def run_probe() -> None:
    logger.info("Initializing Open-World Autobiographical / Subjective Probe (Round 1)...")
    transport = ASGITransport(app=app)
    
    output_records: list[dict[str, Any]] = []

    async with AsyncClient(transport=transport, base_url="http://test", timeout=60.0) as client:
        # Step 1: Create fresh conversation
        res_conv = await client.post("/conversations")
        if res_conv.status_code != 201:
            logger.error("Failed to create conversation: %s", res_conv.text)
            return
        conv_id = res_conv.json()["id"]
        logger.info("Created conversation session: %s", conv_id)

        for step in PROBE_TURNS:
            turn_num = step["turn"]
            turn_type = step["type"]
            user_msg = step["content"]
            intent = step["intent"]
            logger.info("--- Starting Turn %d: %s ---", turn_num, turn_type)
            logger.info("User: %s", user_msg)

            start_time = asyncio.get_event_loop().time()
            res_msg = await client.post(
                f"/conversations/{conv_id}/messages",
                json={"role": "user", "content": user_msg},
            )
            elapsed = asyncio.get_event_loop().time() - start_time

            if res_msg.status_code != 201:
                logger.error("Turn %d failed with status %d: %s", turn_num, res_msg.status_code, res_msg.text)
                continue

            resp_data = res_msg.json()
            assistant_reply = resp_data.get("assistant_response", {}).get("content", "")
            logger.info("Aevum (%0.2fs): %s", elapsed, assistant_reply)

            # Query DB State snapshots
            async with async_session_factory() as session:
                facts = (await session.scalars(
                    select(CharacterCoreFactRecord).where(CharacterCoreFactRecord.character_id == "aevum")
                )).all()
                core_facts = {f.fact_key: json.loads(f.value_json) for f in facts}

                prefs = (await session.scalars(
                    select(CharacterPreferenceTable).where(CharacterPreferenceTable.character_id == "aevum")
                )).all()
                pref_data = [
                    {"domain": p.domain_key, "facet": p.facet_key, "polarity": p.preference_polarity, "stability": p.stability_tier}
                    for p in prefs
                ]

            record = {
                "turn": turn_num,
                "type": turn_type,
                "intent": intent,
                "user_prompt": user_msg,
                "aevum_reply": assistant_reply,
                "elapsed_seconds": round(elapsed, 2),
                "db_facts_count": len(core_facts),
                "db_facts_sample": {k: core_facts[k] for k in list(core_facts.keys())[:8]},
                "growth_preferences": pref_data,
            }
            output_records.append(record)
            # Brief inter-turn pacing
            await asyncio.sleep(1.0)

    # Save probe dump to disk for persistent inspection
    out_path = Path(__file__).resolve().parent / "open_world_probe_round1.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output_records, f, ensure_ascii=False, indent=2)
    logger.info("Probe completed. Results saved to %s", out_path)


if __name__ == "__main__":
    asyncio.run(run_probe())
