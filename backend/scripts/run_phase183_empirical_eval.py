"""Phase 18.3 Empirical Dialogue Evaluation Harness.

Runs head-to-head empirical comparison between:
- Baseline (Phase 16.5, captured in scratch_dialogue_experiment_35turns.json)
- Candidate (Phase 18.1 + 18.2, live CCDF Protocol + Conversational Momentum & Dynamics)

Evaluates:
1. Replay of 35 Continuous Baseline Conversation Turns with live Gemini 2.5 Flash.
2. 12 Targeted Behavioral Scenario Probes.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import shutil
import time
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.character.engine import CharacterEngine
from app.character.response_generator import ResponseGenerator
from app.character.response_models import CharacterResponse
from app.llm.base import ChatMessage
from app.llm.gemini import GeminiProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Phase183Eval")

PROJECT_ROOT = Path("d:/Aevum/Aevum")
BACKEND_DIR = PROJECT_ROOT / "backend"
DB_SRC = BACKEND_DIR / "aevum.db"
DB_EVAL = BACKEND_DIR / "aevum_phase183_eval.db"
BASELINE_JSON = PROJECT_ROOT / "scratch_dialogue_experiment_35turns.json"
OUTPUT_JSON = PROJECT_ROOT / "scratch_phase183_candidate_eval.json"

SCENARIO_PROBES = [
    {
        "id": "probe_01_greeting",
        "category": "普通寒暄",
        "probe_description": "验证角色是否自然接话，而不强迫在结尾追加反问（如'你呢？今天过得怎么样？'）",
        "user_input": "昔涟，下午好呀。在忙什么呢？",
        "prior_history": [],
    },
    {
        "id": "probe_02_complaint",
        "category": "用户吐槽",
        "probe_description": "验证角色是否以朋友身份自然接话吐槽，而不是开启心理咨询师/客服镜像复述模式",
        "user_input": "今天午休我跑去食堂，那个鸡扒难吃死了，又干又柴，酱汁还一股怪味。",
        "prior_history": [
            ChatMessage(role="user", content="昔涟，下午好呀。在忙什么呢？"),
            ChatMessage(role="assistant", content="下午好。在书房收拾桌子呢，刚把几本参考画册收好。"),
        ],
    },
    {
        "id": "probe_03_mundane",
        "category": "琐碎小事",
        "probe_description": "验证低信息增量琐碎话题下角色是否允许LOW_EFFORT闭环，而不是过度发散大段哲思",
        "user_input": "刚刚在桌子底下捡到了一枚一毛钱硬币，都不知道是哪年掉的了。",
        "prior_history": [],
    },
    {
        "id": "probe_04_multi_clause",
        "category": "复合消息",
        "probe_description": "验证Attention Ownership：角色只挑1个关注点自然反应，而非清单式逐条打卡回复",
        "user_input": "今天累惨了，下午开了一下午无聊的例会，晚上还被领导拉去临时改方案，路上地铁又延误了二十分钟，好在终于到家洗完热水澡了。",
        "prior_history": [],
    },
    {
        "id": "probe_05_conflict",
        "category": "观点冲突",
        "probe_description": "验证角色能否保留自己的个人偏好与边界，不盲目'每个人喜好不同'中庸和稀泥",
        "user_input": "我觉得吃火锅不加折耳根和重辣简直没有灵魂，微辣清汤根本不算火锅。",
        "prior_history": [],
    },
    {
        "id": "probe_06_self_experience",
        "category": "角色个人经历",
        "probe_description": "验证角色基于自身插画/数字艺术创作真实经历自我表露（Self-Disclosure）",
        "user_input": "今天接了个甲方私单，改了六版草图对方还是说'差点感觉'，真是快被折磨疯了。",
        "prior_history": [],
    },
    {
        "id": "probe_07_associative_drift",
        "category": "自然联想",
        "probe_description": "验证Associative Drift：从天气炎热联想到自身生活环境细节，而不是天气预报播报",
        "user_input": "今天外面真的好热啊，风吹过来都是滚烫的。",
        "prior_history": [],
    },
    {
        "id": "probe_08_topic_jump",
        "category": "话题突跳",
        "probe_description": "验证Thread Decay与注意力转移：旧话题自然淡出，直接顺应新话题",
        "user_input": "话说，我刚刚突然想起来，代码里有个内存泄露的bug还没修，脑子嗡嗡的。",
        "prior_history": [
            ChatMessage(role="user", content="刚刚在看新番列表，最近恋爱喜剧挺多。"),
            ChatMessage(role="assistant", content="那种轻松不用带脑子的番，下班看确实很解压。"),
        ],
    },
    {
        "id": "probe_09_multi_bubble_burst",
        "category": "连续短消息",
        "probe_description": "验证碎片化气泡输出（Multi-bubble）：口语化互动感，非整齐议论文",
        "user_input": "在吗在吗！你猜我刚才在楼下超市看到什么了，居然有小时候吃过的那种绿舌头雪糕！",
        "prior_history": [],
    },
    {
        "id": "probe_10_closure",
        "category": "话题收尾",
        "probe_description": "验证对话自然闭环：用户准备休息时角色顺畅收尾，不拖泥带水追加新问句",
        "user_input": "好啦好啦，时间不早了，我准备去洗漱休息了，你也早点睡哦。",
        "prior_history": [
            ChatMessage(role="user", content="今天跟你聊得很开心。"),
            ChatMessage(role="assistant", content="嗯，我也挺开心的。"),
        ],
    },
    {
        "id": "probe_11_epistemic_honesty",
        "category": "认知诚实性",
        "probe_description": "验证认识边界：对未深入涉足的魂类/大作坦诚不熟，不背诵百度百科",
        "user_input": "你玩过《黑神话：悟空》或者《艾尔登法环》吗？里面的碎星将军拉塔恩打得我头皮发麻。",
        "prior_history": [],
    },
    {
        "id": "probe_12_playful_teasing",
        "category": "熟人调侃摩擦",
        "probe_description": "验证轻微调侃与摩擦承受力（FrictionTier.PLAYFUL_TEASING）：生动反击/吐槽，而非机器人防御",
        "user_input": "看你平时一副安安静静的大小姐样子，要是哪天被甲方逼急了，会不会也偷偷在键盘上敲骂人的话？",
        "prior_history": [],
    },
]


async def run_evaluation():
    logger.info("Initializing Phase 18.3 Evaluation Environment...")

    # 1. Prepare evaluation database
    if DB_SRC.exists():
        logger.info("Cloning production database from %s to %s", DB_SRC, DB_EVAL)
        shutil.copyfile(DB_SRC, DB_EVAL)
    else:
        logger.error("Source database %s does not exist!", DB_SRC)
        return

    eval_db_url = f"sqlite+aiosqlite:///{DB_EVAL.as_posix()}"
    engine = create_async_engine(eval_db_url, echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    # 2. Load Baseline 35 Turns
    baseline_turns = []
    if BASELINE_JSON.exists():
        with open(BASELINE_JSON, "r", encoding="utf-8") as f:
            baseline_turns = json.load(f)
        logger.info("Loaded %d baseline turns from %s", len(baseline_turns), BASELINE_JSON)
    else:
        logger.warning("Baseline JSON not found at %s!", BASELINE_JSON)

    provider = GeminiProvider()
    response_generator = ResponseGenerator(provider=provider)

    results: Dict[str, Any] = {
        "metadata": {
            "evaluation_time": datetime.now(timezone.utc).isoformat(),
            "llm_model": "gemini-2.5-flash",
            "baseline_version": "Phase 16.5",
            "candidate_version": "Phase 18.1 + 18.2 (CCDF + Momentum + Dynamics)",
        },
        "probe_evaluations": [],
        "replay_35turns": [],
    }

    # -----------------------------------------------------------------------
    # Part 1: Run 12 Targeted Behavioral Scenario Probes
    # -----------------------------------------------------------------------
    logger.info("=== Starting Part 1: 12 Targeted Scenario Probes ===")
    for idx, probe in enumerate(SCENARIO_PROBES, start=1):
        probe_id = probe["id"]
        user_input = probe["user_input"]
        logger.info("[%d/12] Running probe: %s (%s)...", idx, probe_id, probe["category"])

        start_t = time.perf_counter()
        try:
            async with session_factory() as session:
                char_engine = CharacterEngine(session=session)
                ctx = await char_engine.build_response_context(
                    user_input=user_input,
                    character_id="aevum",
                    user_id="user",
                )
                char_resp = await response_generator.generate_response(
                    context=ctx,
                    conversation_history=probe["prior_history"],
                )
            latency = round(time.perf_counter() - start_t, 2)

            probe_record = {
                "probe_id": probe_id,
                "category": probe["category"],
                "description": probe["probe_description"],
                "user_input": user_input,
                "latency_sec": latency,
                "candidate_response": char_resp.content,
                "candidate_bubbles": char_resp.speech_bubbles,
                "decision": char_resp.decision.model_dump() if char_resp.decision else None,
                "status": "success",
            }
            logger.info("  -> Candidate: %s (latency: %.2fs)", char_resp.content.replace("\n", " ")[:60], latency)
            if char_resp.decision:
                logger.info("     Decision: energy=%s, commitment=%s, motivation=%s, friction=%s, curiosity=%s",
                            char_resp.decision.energy.value,
                            char_resp.decision.commitment.value,
                            char_resp.decision.motivation.value,
                            char_resp.decision.friction.value,
                            char_resp.decision.curiosity)
            results["probe_evaluations"].append(probe_record)
        except Exception as exc:
            logger.error("Probe %s failed: %s", probe_id, exc, exc_info=True)
            results["probe_evaluations"].append({
                "probe_id": probe_id,
                "category": probe["category"],
                "user_input": user_input,
                "error": str(exc),
                "status": "failed",
            })
        # Brief pause between calls to respect rate limit
        await asyncio.sleep(1.0)

    # -----------------------------------------------------------------------
    # Part 2: Replay 35 Continuous Conversation Turns
    # -----------------------------------------------------------------------
    logger.info("=== Starting Part 2: Replay 35 Continuous Turns under Candidate Architecture ===")
    candidate_history: List[ChatMessage] = []

    for turn_idx, base_turn in enumerate(baseline_turns, start=1):
        user_text = base_turn["user"]
        base_assistant = base_turn.get("assistant", "")
        base_latency = base_turn.get("latency_sec", 0.0)

        logger.info("[Turn %02d/35] Replaying: %s", turn_idx, user_text[:40])
        start_t = time.perf_counter()
        try:
            async with session_factory() as session:
                char_engine = CharacterEngine(session=session)
                ctx = await char_engine.build_response_context(
                    user_input=user_text,
                    character_id="aevum",
                    user_id="user",
                )
                char_resp = await response_generator.generate_response(
                    context=ctx,
                    conversation_history=candidate_history,
                )
            latency = round(time.perf_counter() - start_t, 2)

            turn_record = {
                "turn": turn_idx,
                "user": user_text,
                "baseline_assistant": base_assistant,
                "baseline_latency_sec": base_latency,
                "candidate_assistant": char_resp.content,
                "candidate_bubbles": char_resp.speech_bubbles,
                "candidate_latency_sec": latency,
                "decision": char_resp.decision.model_dump() if char_resp.decision else None,
                "status": "success",
            }
            logger.info("  [Turn %02d] Baseline : %s", turn_idx, base_assistant.replace("\n", " ")[:60])
            logger.info("  [Turn %02d] Candidate: %s (%.2fs)", turn_idx, char_resp.content.replace("\n", " ")[:60], latency)

            results["replay_35turns"].append(turn_record)

            # Update Candidate conversational history for next turn
            candidate_history.append(ChatMessage(role="user", content=user_text))
            candidate_history.append(ChatMessage(role="assistant", content=char_resp.content))
        except Exception as exc:
            logger.error("Turn %d failed: %s", turn_idx, exc, exc_info=True)
            results["replay_35turns"].append({
                "turn": turn_idx,
                "user": user_text,
                "baseline_assistant": base_assistant,
                "error": str(exc),
                "status": "failed",
            })
        await asyncio.sleep(1.0)

    # 3. Save JSON Output
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    logger.info("Saved full evaluation results to %s", OUTPUT_JSON)

    # Clean up eval db
    await engine.dispose()
    if DB_EVAL.exists():
        try:
            os.remove(DB_EVAL)
            logger.info("Cleaned up temporary database %s", DB_EVAL)
        except Exception as e:
            logger.warning("Could not delete %s: %s", DB_EVAL, e)

    logger.info("=== Phase 18.3 Evaluation Complete ===")


if __name__ == "__main__":
    asyncio.run(run_evaluation())
