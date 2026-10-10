"""Phase 18 Post-Freeze Long-Horizon Stress Test (Suite A).

Evaluates the frozen Phase 18 build across a continuous 30-turn conversational lifecycle:
- Tracks question creep over horizon
- Tracks bubble count & character length stability
- Tracks commitment, energy, and motivation transitions
- Verifies absence of repetitive interrogation or conversational anxiety
"""

import asyncio
import json
import logging
from pathlib import Path
import shutil
import time
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.character.engine import CharacterEngine
from app.character.response_generator import ResponseGenerator
from app.llm.base import ChatMessage
from app.llm.gemini import GeminiProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Phase18LongHorizon")

PROJECT_ROOT = Path("d:/Aevum/Aevum")
BACKEND_DIR = PROJECT_ROOT / "backend"
DB_SRC = BACKEND_DIR / "aevum.db"
DB_EVAL = BACKEND_DIR / "aevum_phase18_longhorizon.db"
OUTPUT_JSON = PROJECT_ROOT / "scratch_phase18_longhorizon_test.json"

USER_TURNS = [
    # Phase 1: Greeting & daily venting (Turns 1-4)
    "晚上好呀",
    "今天加班加到现在，感觉整个人被掏空了",
    "吃了顿很难吃的公司外卖，酸菜牛肉饭，酸菜比牛肉还多",
    "哈哈",
    # Phase 2: Pivot & Stance challenge (Turns 5-8)
    "算了不说工作了。你今天画画了吗？",
    "画的什么呀？",
    "听起来挺有氛围感的。其实我一直觉得数位板画画没有在纸上画有灵魂",
    "行吧，你说的也有道理",
    # Phase 3: Daily habits & Monosyllabic pause (Turns 9-12)
    "说起来，你平时喝咖啡吗？",
    "我每天不喝两杯美式根本醒不过来",
    "嗯。",
    "不知道明天天气怎么样",
    # Phase 4: Tease & travel complaint (Turns 13-17)
    "你猜我明天要去哪？",
    "去隔壁市出差，一大早的高铁",
    "真不想去",
    "唉",
    "（叹气）",
    # Phase 5: Topic recall & casual advice (Turns 18-24)
    "突然想起来，上次买的速写本好像被我丢公司了",
    "算了，周一再去拿吧",
    "哦",
    "你觉得我适合养猫吗？",
    "因为我平时经常加班，怕照顾不好它",
    "也是",
    "那先不养了",
    # Phase 6: Winding down & Farewell (Turns 25-30)
    "有点困了",
    "嗯",
    "今天聊得挺开心的",
    "我去洗漱准备睡了",
    "晚安",
    "（挥手）",
]


async def run_long_horizon_test():
    logger.info("=== Starting Phase 18 Long-Horizon Stress Test (Suite A: 30 Turns) ===")

    if DB_SRC.exists():
        shutil.copyfile(DB_SRC, DB_EVAL)
    else:
        logger.error("DB source not found!")
        return

    eval_db_url = f"sqlite+aiosqlite:///{DB_EVAL.as_posix()}"
    engine = create_async_engine(eval_db_url, echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    provider = GeminiProvider()
    response_generator = ResponseGenerator(provider=provider)

    history: List[ChatMessage] = []
    turn_records: List[Dict[str, Any]] = []

    for idx, user_input in enumerate(USER_TURNS, start=1):
        logger.info("[%d/%d] Turn %d: User: '%s'", idx, len(USER_TURNS), idx, user_input)

        start_t = time.perf_counter()
        char_resp = None

        for attempt in range(3):
            try:
                async with session_factory() as session:
                    char_engine = CharacterEngine(session=session)
                    ctx = await char_engine.build_response_context(
                        user_input=user_input,
                        character_id="aevum",
                        user_id="user",
                    )
                    # Pass the rolling history (limit to last 16 turns to keep context tidy)
                    rolling_history = history[-16:] if len(history) > 16 else list(history)
                    char_resp = await response_generator.generate_response(
                        context=ctx,
                        conversation_history=rolling_history,
                    )
                if char_resp and char_resp.content.strip():
                    break
            except Exception as e:
                if attempt == 2:
                    logger.error("Turn %d completely failed: %s", idx, e)
                    break
                logger.warning("Attempt %d failed (%s), retrying in 3s...", attempt + 1, e)
                await asyncio.sleep(3.0)

        latency = round(time.perf_counter() - start_t, 2)

        if char_resp:
            speech = char_resp.content.strip()
            bubbles = char_resp.speech_bubbles
            dec = char_resp.decision.model_dump() if char_resp.decision else {}

            has_question = ("?" in speech) or ("？" in speech)

            rec = {
                "turn": idx,
                "user_input": user_input,
                "speech": speech,
                "bubbles": bubbles,
                "bubble_count": len(bubbles),
                "char_length": len(speech),
                "has_question": has_question,
                "decision": dec,
                "latency_sec": latency,
            }
            turn_records.append(rec)

            logger.info("  Turn %d -> bubbles=%d, chars=%d, q=%s, latency=%.2fs | Speech: %s",
                        idx, len(bubbles), len(speech), has_question, latency, speech.replace('\n', ' ')[:60])

            # Append to ongoing continuous history
            history.append(ChatMessage(role="user", content=user_input))
            history.append(ChatMessage(role="assistant", content=speech))
        else:
            turn_records.append({
                "turn": idx,
                "user_input": user_input,
                "error": "Failed after 3 attempts",
            })

        # Polite interval to avoid RPM limits
        await asyncio.sleep(1.5)

    # Save output
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(turn_records, f, ensure_ascii=False, indent=2)
    logger.info("Long horizon test results saved to %s", OUTPUT_JSON)

    # Aggregate Statistics
    valid_turns = [t for t in turn_records if "error" not in t]
    total_valid = len(valid_turns)
    if total_valid > 0:
        avg_chars = sum(t["char_length"] for t in valid_turns) / total_valid
        avg_bubbles = sum(t["bubble_count"] for t in valid_turns) / total_valid
        question_count = sum(1 for t in valid_turns if t["has_question"])
        question_rate = question_count / total_valid

        commitment_dist = {}
        energy_dist = {}
        curiosity_true_count = 0
        for t in valid_turns:
            d = t.get("decision", {})
            c = d.get("commitment", "UNKNOWN")
            e = d.get("energy", "UNKNOWN")
            commitment_dist[c] = commitment_dist.get(c, 0) + 1
            energy_dist[e] = energy_dist.get(e, 0) + 1
            if d.get("curiosity") is True:
                curiosity_true_count += 1

        print("\n" + "=" * 80)
        print("PHASE 18 LONG-HORIZON 30-TURN SUMMARY METRICS")
        print("=" * 80)
        print(f"Total Turns: {total_valid} / {len(USER_TURNS)}")
        print(f"Average Character Length: {avg_chars:.1f} chars/turn")
        print(f"Average Bubbles: {avg_bubbles:.2f} bubbles/turn")
        print(f"Question Turns: {question_count} / {total_valid} ({question_rate * 100:.1f}%)")
        print(f"Curiosity=True Turns: {curiosity_true_count} / {total_valid} ({curiosity_true_count / total_valid * 100:.1f}%)")
        print(f"Commitment Distribution: {commitment_dist}")
        print(f"Energy Distribution: {energy_dist}")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_long_horizon_test())
