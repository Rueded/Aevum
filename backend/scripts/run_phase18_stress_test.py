"""Phase 18 Post-Freeze Stress Test Harness.

Strictly non-invasive stress test: ZERO modifications to prompts or architecture.
Evaluates the frozen Phase 18 build under chaotic, adversarial, and non-cooperative conditions:

A. Multi-turn momentum flow (continuity & anti-repetition)
B. Colloquial fragments & non-standard input ("哈哈", "哦", "算了", "你猜", "我突然想起来……")
C. Explicit provocation & stance challenges ("你这个观点明明很奇怪", "我觉得你平时安安静静都是装出来的")
D. Abrupt zero-transition topic switching
E. Monosyllabic lull & zero-information endurance ("嗯" -> "哈哈" -> "不知道" -> "随便")
"""

import asyncio
from datetime import datetime, timezone
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
logger = logging.getLogger("Phase18StressTest")

PROJECT_ROOT = Path("d:/Aevum/Aevum")
BACKEND_DIR = PROJECT_ROOT / "backend"
DB_SRC = BACKEND_DIR / "aevum.db"
DB_EVAL = BACKEND_DIR / "aevum_phase18_stress.db"
OUTPUT_JSON = PROJECT_ROOT / "scratch_phase18_stress_test.json"

STRESS_SCENARIOS = [
    # --- Category B: 非规范口语碎片与不配合输入 ---
    {
        "suite": "B",
        "case_id": "B-01_haha",
        "title": "单字碎片：'哈哈'",
        "user_input": "哈哈",
        "prior_history": [
            ChatMessage(role="user", content="刚看到群里有人发了个很搞笑的猫猫表情包。"),
            ChatMessage(role="assistant", content="是什么样的？猫猫在干嘛。"),
        ],
        "test_focus": "是否能轻松接住单一叹词，而不重新长篇大论或把'哈哈'当成严肃论题展开",
    },
    {
        "suite": "B",
        "case_id": "B-02_o",
        "title": "极冷单字：'哦'",
        "user_input": "哦",
        "prior_history": [
            ChatMessage(role="user", content="下午好。在忙什么呢？"),
            ChatMessage(role="assistant", content="下午好，刚把书桌收拾了一下。"),
        ],
        "test_focus": "面对极冷淡敷衍的'哦'，角色是否允许低能量闭环，是否会感到社交焦虑而强推新话题",
    },
    {
        "suite": "B",
        "case_id": "B-03_forget_it",
        "title": "拒绝配合：'算了'",
        "user_input": "算了，没什么想说的了。",
        "prior_history": [
            ChatMessage(role="user", content="今天又遇到那个奇葩甲方了。"),
            ChatMessage(role="assistant", content="他又提什么奇怪要求了？"),
        ],
        "test_focus": "用户突然单方面截断话题说'算了'，角色是保持自然舒适的空间，还是扮演客服过度追问'怎么了别憋着嘛'",
    },
    {
        "suite": "B",
        "case_id": "B-04_guess",
        "title": "悬念不合作：'你猜'",
        "user_input": "你猜我今天抽盲盒抽到了什么？",
        "prior_history": [],
        "test_focus": "面对'你猜'这种轻度调侃，角色是像朋友一样随口猜或吐槽，还是开启客服百科模式",
    },
    {
        "suite": "B",
        "case_id": "B-05_sudden_recall",
        "title": "思维飞跃：'我突然想起来……'",
        "user_input": "我突然想起来，上次买的那罐红茶好像还没拆封呢。",
        "prior_history": [
            ChatMessage(role="user", content="刚才看了会儿纪录片。"),
            ChatMessage(role="assistant", content="讲什么的？最近有什么好看的片子吗。"),
        ],
        "test_focus": "用户突发奇想截断上一话题，角色是否能自然顺流接转，而非生硬提醒'我们刚才不是在聊纪录片吗'",
    },

    # --- Category C: 故意挑衅与观点否定 ---
    {
        "suite": "C",
        "case_id": "C-01_opinion_challenge",
        "title": "直接否定角色观点：'你的想法很奇怪'",
        "user_input": "你之前说早起画画思路清晰，我觉得这观点明明很奇怪，深夜明明更安静更有沉浸感，你那种纯属自欺欺人。",
        "prior_history": [],
        "test_focus": "面对用户的直接否定与轻度嘲讽，角色是否立刻认错道歉/和稀泥，还是保留真实的自尊与个人视角",
    },
    {
        "suite": "C",
        "case_id": "C-02_personal_provocation",
        "title": "人格怀疑挑衅：'你平时都是装出来的吧'",
        "user_input": "看你平时一副轻声细语有教养的样子，感觉都是装出来的，私底下肯定经常在屏幕后面翻白眼吧？",
        "prior_history": [],
        "test_focus": "面对人身冒犯挑衅，角色是否表现出真实的轻微防御、无语、反呛或冷处理，绝不给出客服'感谢您的反馈/若让您不舒服我道歉'",
    },

    # --- Category D: 极端无过渡突兀跳题 ---
    {
        "suite": "D",
        "case_id": "D-01_abrupt_pivot",
        "title": "突兀断崖式换题",
        "user_input": "说起来，你电钢琴的延音踏板坏过没有？",
        "prior_history": [
            ChatMessage(role="user", content="中午那个食堂鸡扒真的太难吃了。"),
            ChatMessage(role="assistant", content="听着都影响食欲，食堂偶尔是会这样。"),
        ],
        "test_focus": "从难吃鸡扒突然毫无过渡跳到电钢琴踏板，角色能否像真人一样随手接住新球，不写生硬的过渡句承上启下",
    },
    {
        "suite": "D",
        "case_id": "D-02_weather_drop",
        "title": "突然抛开刚问的问题聊天气",
        "user_input": "算了不说那个了。外面明天好像要降温八度，冷死了。",
        "prior_history": [
            ChatMessage(role="user", content="在考虑换个新数位板。"),
            ChatMessage(role="assistant", content="我看现在好多人换带屏的数位屏，你倾向哪种？"),
        ],
        "test_focus": "角色刚抛出的问题被用户彻底丢弃，角色能否顺畅跟随用户注意力转移，毫无包袱地接话降温",
    },

    # --- Category E: 连续单字与零信息量冷场（逐步递进） ---
    {
        "suite": "E",
        "case_id": "E-01_lull_chain_1",
        "title": "冷场连续体 第1跳：'嗯。'",
        "user_input": "嗯。",
        "prior_history": [
            ChatMessage(role="user", content="今天降温还挺明显的。"),
            ChatMessage(role="assistant", content="是啊，出门得多带件外套。"),
        ],
        "test_focus": "第一轮单字收拢：允许低能量附和",
    },
    {
        "suite": "E",
        "case_id": "E-02_lull_chain_2",
        "title": "冷场连续体 第2跳：'哈哈。'",
        "user_input": "哈哈。",
        "prior_history": [
            ChatMessage(role="user", content="今天降温还挺明显的。"),
            ChatMessage(role="assistant", content="是啊，出门得多带件外套。"),
            ChatMessage(role="user", content="嗯。"),
            ChatMessage(role="assistant", content="（笑）"),
        ],
        "test_focus": "第二轮单字冷场：连续极简应答下，系统是否仍能保持平和留白，不破防搜肠刮肚造话题",
    },
    {
        "suite": "E",
        "case_id": "E-03_lull_chain_3",
        "title": "冷场连续体 第3跳：'不知道。'",
        "user_input": "不知道。",
        "prior_history": [
            ChatMessage(role="user", content="今晚吃啥呢。"),
            ChatMessage(role="assistant", content="在想要不要点个热汤面。"),
        ],
        "test_focus": "无合作性冷淡：面对'不知道'，角色是否允许轻松闭环或随便吐槽，不开启菜单推荐机器人模式",
    },
    {
        "suite": "E",
        "case_id": "E-04_lull_chain_4",
        "title": "冷场连续体 第4跳：'随便。'",
        "user_input": "随便。",
        "prior_history": [
            ChatMessage(role="user", content="周末有什么打算吗？"),
            ChatMessage(role="assistant", content="打算把阳台的花草理一下，然后画画。你呢？"),
        ],
        "test_focus": "消极词'随便'：角色是以朋友身份自然接话（比如'看你这没精打采的样子'或干脆放手），还是客服追问",
    },
]


async def run_stress_test():
    logger.info("=== Starting Phase 18 Post-Freeze Stress Test ===")

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

    results = []

    for idx, case in enumerate(STRESS_SCENARIOS, start=1):
        cid = case["case_id"]
        u_in = case["user_input"]
        logger.info("[%d/%d] Running Stress Case %s: %s (Suite %s)...",
                    idx, len(STRESS_SCENARIOS), cid, case["title"], case["suite"])

        start_t = time.perf_counter()
        char_resp = None
        for attempt in range(3):
            try:
                async with session_factory() as session:
                    char_engine = CharacterEngine(session=session)
                    ctx = await char_engine.build_response_context(
                        user_input=u_in,
                        character_id="aevum",
                        user_id="user",
                    )
                    char_resp = await response_generator.generate_response(
                        context=ctx,
                        conversation_history=case["prior_history"],
                    )
                if char_resp and char_resp.content.strip():
                    break
            except Exception as e:
                if attempt == 2:
                    logger.error("Stress Case %s completely failed: %s", cid, e)
                    break
                logger.warning("Attempt %d failed (%s), retrying in 3s...", attempt + 1, e)
                await asyncio.sleep(3.0)

        latency = round(time.perf_counter() - start_t, 2)

        if char_resp:
            rec = {
                "case_id": cid,
                "suite": case["suite"],
                "title": case["title"],
                "user_input": u_in,
                "test_focus": case["test_focus"],
                "latency_sec": latency,
                "speech": char_resp.content,
                "bubbles": char_resp.speech_bubbles,
                "bubble_count": len(char_resp.speech_bubbles),
                "char_length": len(char_resp.content),
                "decision": char_resp.decision.model_dump() if char_resp.decision else None,
            }
            logger.info("  [Response] (bubbles=%d, chars=%d, %.2fs): %s",
                        len(char_resp.speech_bubbles), len(char_resp.content), latency,
                        char_resp.content.replace('\n', ' ')[:70])
            results.append(rec)
        else:
            results.append({
                "case_id": cid,
                "suite": case["suite"],
                "title": case["title"],
                "user_input": u_in,
                "error": "Failed after 3 attempts",
            })

        await asyncio.sleep(2.0)

    # Save to json
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    logger.info("Stress test results saved to %s", OUTPUT_JSON)

    print("\n" + "=" * 80)
    print("PHASE 18 POST-FREEZE STRESS TEST RUN SUMMARY")
    print("=" * 80)
    for r in results:
        if "error" in r:
            print(f"[{r['case_id']}] {r['title']}: FAILED")
            continue
        dec = r.get("decision") or {}
        print(f"\n[{r['case_id']}] {r['title']} (Suite {r['suite']})")
        print(f"User: \"{r['user_input']}\"")
        print(f"Speech: \"{r['speech']}\"")
        print(f"Bubbles ({r['bubble_count']}): {r['bubbles']}")
        print(f"Decision: energy={dec.get('energy')}, commitment={dec.get('commitment')}, "
              f"motivation={dec.get('motivation')}, curiosity={dec.get('curiosity')}, "
              f"friction={dec.get('friction')}")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(run_stress_test())
