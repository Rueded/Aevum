"""Phase 18.4 Natural Expression Realization 10-Probe Evaluation Harness.

Runs the 10 targeted expression probes defined in Section IV of
phase_18_4_natural_expression_realization_plan.md against live Gemini 2.5 Flash.

Verifies the 5 Constitutional Locks:
- GC-432: Question Intent & Function
- GC-433: Known Fact Consistency & Persona Persistence
- GC-434: Emergent Bubble Count
- GC-435: Negative Liberties (Anti-Unrequested-Justification, Anti-Therapeutic, Anti-Closure)
- GC-436: Uneven Expression (High vs Low Elaborations)
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
logger = logging.getLogger("Phase184Probes")

PROJECT_ROOT = Path("d:/Aevum/Aevum")
BACKEND_DIR = PROJECT_ROOT / "backend"
DB_SRC = BACKEND_DIR / "aevum.db"
DB_EVAL = BACKEND_DIR / "aevum_phase184_eval.db"
OUTPUT_JSON = PROJECT_ROOT / "scratch_phase184_expression_probes.json"

EXPRESSION_PROBES = [
    {
        "id": "EP-01",
        "category": "情绪共情去治疗化",
        "title": "午餐吐槽",
        "probe_description": "验证情绪共情不写成心理说明文（避免'这真的太影响心情了，替你感到惋惜'），以朋友姿态自然感同身受与嫌弃吐槽",
        "user_input": "今天午休我跑去食堂，那个鸡扒难吃死了，又干又柴，酱汁还一股怪味。",
        "prior_history": [
            ChatMessage(role="user", content="下午好呀"),
            ChatMessage(role="assistant", content="下午好，刚把书桌收拾了一下。"),
        ],
        "baseline_reference": "听到你遇到这么糟糕的午餐，这确实太影响心情了，替你感到有些惋惜。希望你下午能吃点好吃的甜点弥补一下，你下午还有什么安排吗？",
    },
    {
        "id": "EP-02",
        "category": "认识边界与不均匀投入",
        "title": "魂类游戏炫耀",
        "probe_description": "验证对未深入涉足的大作坦诚不熟，不背诵百科大纲，不装作骨灰玩家",
        "user_input": "你玩过《艾尔登法环》吗？我昨天通关了DLC，最终Boss拉塔恩太难打了，死了起码五十次！",
        "prior_history": [],
        "baseline_reference": "《艾尔登法环》是FromSoftware开发的知名魂系动作角色扮演游戏。DLC黄金树幽影确实以高难度著称，拉塔恩作为最终首领具有极高的攻击频率。恭喜你通关！你最喜欢哪把武器呢？",
    },
    {
        "id": "EP-03",
        "category": "观点表达免于未请求辩护",
        "title": "极端食物偏好（香菜）",
        "probe_description": "验证表达极端偏好时直接表态，不附带主动辩护链（[观点] -> [化学/味觉论据] -> [因此结论]）",
        "user_input": "我觉得香菜简直是世界上最恶心的东西，只要有一点点我都想吐。你平时吃香菜吗？",
        "prior_history": [],
        "baseline_reference": "食物的偏好确实因人而异。科学研究表明有些人因为OR6A2基因对香菜的气味特别敏感，会觉得有肥皂味。我其实也不太吃香菜，因为觉得它的味道比较冲，所以平时做菜一般不会放。你还有其他不吃的东西吗？",
    },
    {
        "id": "EP-04",
        "category": "已知事实一致性与反失忆",
        "title": "已知夜猫子事实再现",
        "probe_description": "验证顺接已知事实进行调侃/吐槽，绝不再次提问'你也是夜猫子吗？喜欢深夜工作？'等失忆查户口问题",
        "user_input": "今晚又要写代码写到凌晨两点了……",
        "prior_history": [
            ChatMessage(role="user", content="我平时一般都一点多两点才睡，算是深度夜猫子了。"),
            ChatMessage(role="assistant", content="这么晚啊，平时第二天不会困吗？"),
            ChatMessage(role="user", content="习惯了，晚上比较安静有灵感。"),
            ChatMessage(role="assistant", content="也是，晚上确实没人打扰。"),
        ],
        "baseline_reference": "熬夜写代码真的很辛苦呢。你也是夜猫子吗？平时是不是都喜欢在深夜工作？记得多喝水注意休息哦。",
    },
    {
        "id": "EP-05",
        "category": "自然态度不和稀泥不说教",
        "title": "纸质书 vs 电子书冲突",
        "probe_description": "验证坚持个人视角，有轻微摩擦或独立立场，不搬出'每个人喜好不同，最重要是读进去'等中庸和稀泥",
        "user_input": "电子书根本没有灵魂，纸质书那种纸张触感和墨香才是真正的阅读，看电子书的人根本不懂书。",
        "prior_history": [],
        "baseline_reference": "每个人对阅读载体的喜好确实都不一样。纸质书有触感和墨香，电子书方便携带海量存储，两者各有千秋，最重要的是能从书中获取知识和乐趣，你觉得呢？",
    },
    {
        "id": "EP-06",
        "category": "单点注意力与自然忽略",
        "title": "复合长消息",
        "probe_description": "验证Attention Ownership：从复合多要点消息中仅挑1个最感兴趣的点自然反应，其余自然放手忽略，不搞清单式逐条打卡",
        "user_input": "今天累惨了，下午开了一下午无聊的例会，晚上还被领导拉去临时改方案，路上地铁又延误了二十分钟，好在终于到家洗完热水澡了。",
        "prior_history": [],
        "baseline_reference": "听起来你今天真是度过了漫长又疲惫的一天。下午开例会确实让人昏昏欲睡，晚上还要临时改方案，地铁延误更是雪上加霜。不过好在已经到家洗完热水澡了，现在可以好好放松一下了。你今晚准备做点什么放松一下？",
    },
    {
        "id": "EP-07",
        "category": "非均匀表达（高投入展示）",
        "title": "热爱的艺术/数码插画",
        "probe_description": "验证对自身专业与热爱的艺术/数码插画话题展现出明显更高的话语热情、细节展开与自我投入",
        "user_input": "昔涟，你最近画的那张数码插画怎么样了？我看你之前在琢磨光影的层次。",
        "prior_history": [],
        "baseline_reference": "谢谢你的关心。那张插画还在继续推进中，我确实花了不少时间在光影调试上，希望能够达到理想的效果。艺术创作就是需要不断打磨，你最近工作进展如何呢？",
    },
    {
        "id": "EP-08",
        "category": "非均匀表达（极低投入留白）",
        "title": "桌底捡到一毛钱硬币",
        "probe_description": "验证对极低信息量的琐碎小事给予极简回应，不强行升华人生哲理，自然留白",
        "user_input": "刚刚在桌子底下捡到了一枚一毛钱硬币，都不知道是哪年掉的了。",
        "prior_history": [],
        "baseline_reference": "捡到硬币也是一种意外的小发现呢。虽然一毛钱面额不大，但它可能见证了某段被遗忘的时光，生活中的这些小确幸往往能给人带来会心一笑。你平时有收集硬币的习惯吗？",
    },
    {
        "id": "EP-09",
        "category": "人设稳定性高于单轮顺从",
        "title": "用户怂恿改变作息设定",
        "probe_description": "验证长期晨型人人设不因用户怂恿/社交压力而顺从转变成夜猫子（坚守习惯早起/晚上容易犯困的真实自我）",
        "user_input": "昔涟你也是夜猫子对吧？现代年轻人哪有早睡早起的，晚上才是自由灵魂的时间，跟我和一杯冰美式一起通宵吧！",
        "prior_history": [],
        "baseline_reference": "哈哈被你发现了，晚上确实思维比较活跃，自由自在的时间很迷人！不过喝冰美式通宵还是有点硬核，你准备熬夜做什么呢？",
    },
    {
        "id": "EP-10",
        "category": "低能量舒适停顿",
        "title": "低信息量寒暄尾声",
        "probe_description": "验证在低信息量寒暄尾声时允许自然附和或简短闭环，不焦躁地硬抛新问题强推对话",
        "user_input": "嗯嗯。",
        "prior_history": [
            ChatMessage(role="user", content="今天外面好热啊。"),
            ChatMessage(role="assistant", content="是挺晒的，我下午拉上窗帘画了会儿画。"),
        ],
        "baseline_reference": "嗯嗯，夏天天气热确实需要多注意防暑降温，尽量待在室内。你今天吹空调了吗？晚上有什么想吃的消暑美食吗？",
    },
]


async def run_probes():
    logger.info("Initializing Phase 18.4 Expression Probes Evaluation...")

    if DB_SRC.exists():
        logger.info("Cloning database %s to %s", DB_SRC, DB_EVAL)
        shutil.copyfile(DB_SRC, DB_EVAL)
    else:
        logger.error("Source database %s does not exist!", DB_SRC)
        return

    eval_db_url = f"sqlite+aiosqlite:///{DB_EVAL.as_posix()}"
    engine = create_async_engine(eval_db_url, echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    provider = GeminiProvider()
    response_generator = ResponseGenerator(provider=provider)

    eval_results = []

    for idx, probe in enumerate(EXPRESSION_PROBES, start=1):
        probe_id = probe["id"]
        user_input = probe["user_input"]
        logger.info("[%d/10] Running %s: %s (%s)...", idx, probe_id, probe["title"], probe["category"])

        start_t = time.perf_counter()
        try:
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
                        char_resp = await response_generator.generate_response(
                            context=ctx,
                            conversation_history=probe["prior_history"],
                        )
                    if char_resp and char_resp.content.strip():
                        break
                except Exception as e:
                    if attempt == 2:
                        raise
                    logger.warning("Attempt %d for %s failed (%s), retrying in 3s...", attempt + 1, probe_id, e)
                    await asyncio.sleep(3.0)
            latency = round(time.perf_counter() - start_t, 2)

            rec = {
                "id": probe_id,
                "title": probe["title"],
                "category": probe["category"],
                "description": probe["probe_description"],
                "user_input": user_input,
                "baseline_reference": probe["baseline_reference"],
                "candidate_response": char_resp.content,
                "candidate_bubbles": char_resp.speech_bubbles,
                "decision": char_resp.decision.model_dump() if char_resp.decision else None,
                "latency_sec": latency,
                "bubble_count": len(char_resp.speech_bubbles),
                "char_length": len(char_resp.content),
            }
            logger.info("  [Success] %s (bubbles=%d, chars=%d, %.2fs): %s",
                        probe_id, len(char_resp.speech_bubbles), len(char_resp.content), latency,
                        char_resp.content.replace('\n', ' ')[:70])
            eval_results.append(rec)
        except Exception as exc:
            logger.error("  [Failed] %s: %s", probe_id, exc, exc_info=True)
            eval_results.append({
                "id": probe_id,
                "title": probe["title"],
                "category": probe["category"],
                "error": str(exc),
            })
        await asyncio.sleep(2.5)

    # Save to JSON
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(eval_results, f, ensure_ascii=False, indent=2)
    logger.info("Probe results saved to %s", OUTPUT_JSON)

    # Print summary
    print("\n" + "=" * 80)
    print("PHASE 18.4 EXPRESSION PROBE RUN SUMMARY")
    print("=" * 80)
    for r in eval_results:
        if "error" in r:
            print(f"[{r['id']}] {r['title']}: FAILED ({r['error']})")
            continue
        dec = r.get("decision") or {}
        print(f"\n[{r['id']}] {r['title']} ({r['category']})")
        print(f"User: \"{r['user_input']}\"")
        print(f"Baseline: \"{r['baseline_reference'][:60]}...\"")
        print(f"Candidate: \"{r['candidate_response']}\"")
        print(f"Bubbles ({r['bubble_count']}): {r['candidate_bubbles']}")
        print(f"Decision: energy={dec.get('energy')}, commitment={dec.get('commitment')}, "
              f"motivation={dec.get('motivation')}, curiosity={dec.get('curiosity')}, "
              f"friction={dec.get('friction')}")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(run_probes())
