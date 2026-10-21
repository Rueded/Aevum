"""Response prompt and LLM context assembly boundary for Aevum Core.

Human-like Prompt Architecture (Phase 2 Refactor):
- Natural language blocks (no raw XML numeric dumping, no Energy floats)
- Total system instruction <= 6000 characters
- Grounded character identity dynamically loaded from character data (no hardcoded personas in code)
- Deterministic inner state renderer (render_inner_state)
- Positive, concise 10 hard rules (WeChat style, short bubbles, stickers, abstract humor)
- Few-shot conversational style examples injected into message history
"""

from collections.abc import Sequence
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from app.character.engine_models import CharacterResponseContext
from app.character.shape_controller import ShapeController
from app.core.config import settings
from app.llm.base import ChatMessage
from app.llm.context import LLMContext

logger = logging.getLogger(__name__)

STYLE_EXAMPLES_PATH = Path(__file__).resolve().parent / "style_examples.json"
_CACHED_STYLE_EXAMPLES: Optional[List[Dict[str, Any]]] = None


def get_cached_style_examples() -> List[Dict[str, Any]]:
    """Load and cache style examples from style_examples.json."""
    global _CACHED_STYLE_EXAMPLES
    if _CACHED_STYLE_EXAMPLES is None:
        if STYLE_EXAMPLES_PATH.exists():
            try:
                with open(STYLE_EXAMPLES_PATH, "r", encoding="utf-8") as f:
                    _CACHED_STYLE_EXAMPLES = json.load(f)
            except Exception as e:
                logger.warning("Failed to load style examples from %s: %s", STYLE_EXAMPLES_PATH, e)
                _CACHED_STYLE_EXAMPLES = []
        else:
            _CACHED_STYLE_EXAMPLES = []
    return _CACHED_STYLE_EXAMPLES


def render_inner_state(state: Any, emotion: Any) -> str:
    """Deterministically render inner state and emotion into natural human language.

    Translates numeric values (energy, stress) and emotion types into 1-2 authentic Chinese phrases.
    Never gives raw numbers like 'Energy: 0.62' to the model.
    """
    parts: List[str] = []

    # 1. Activity & Location
    act = getattr(state, "current_activity", None)
    loc = getattr(state, "current_location", None)
    if act and loc:
        parts.append(f"正在{loc}{act}")
    elif act:
        parts.append(f"正在{act}")
    elif loc:
        parts.append(f"在{loc}")

    # 2. Physical sensation / Energy
    energy = getattr(state, "energy", 0.7)
    stress = getattr(state, "stress", 0.2)
    if energy < 0.35:
        parts.append("很困、有点累，想趴着歇会儿")
    elif energy < 0.55:
        parts.append("状态有点懒散摸鱼")
    elif energy >= 0.8:
        parts.append("精神很好，挺有精神的")

    if stress > 0.6:
        parts.append("事情有点多，稍微有点紧绷烦躁")

    # 3. Emotion summary
    emo_type = ""
    if hasattr(emotion, "emotion_type"):
        emo_type = str(getattr(emotion.emotion_type, "value", emotion.emotion_type)).lower()
    summary = getattr(emotion, "summary", "")

    if any(k in emo_type for k in ("joy", "happy", "amusement", "affection", "love")):
        parts.append("心情挺好，比较轻松欢快")
    elif any(k in emo_type for k in ("tired", "exhaustion", "bored")):
        parts.append("心情懒洋洋的，有点无聊")
    elif any(k in emo_type for k in ("annoy", "anger", "irritation")):
        parts.append("有点小脾气或被惹到了")
    elif any(k in emo_type for k in ("sad", "grief", "melancholy")):
        parts.append("心情略低落，需要安慰")
    elif summary and len(summary) < 25:
        parts.append(summary)
    else:
        parts.append("心情平静闲适")

    return "，".join(parts) + "。" if parts else "状态平和放松。"


def render_relationship(rel: Any) -> str:
    """Translate multidimensional relationship state into natural language."""
    if not rel:
        return "你和对方是关系融洽的朋友，聊天轻松自在。"

    fam = getattr(rel, "familiarity", 0.5)
    aff = getattr(rel, "affection", 0.5)
    trust = getattr(rel, "trust", 0.5)

    if fam <= 1.0 and aff <= 1.0 and trust <= 1.0:
        fam_score = fam * 100
        aff_score = aff * 100
    else:
        fam_score = fam
        aff_score = aff

    if aff_score >= 70 or fam_score >= 70:
        return (
            "你和对方是非常亲近、彼此极度信任的好朋友/喜欢的人。"
            "在他面前你不需要任何拘谨或客服式礼貌，可以自然互怼、开玩笑、发表情包、娇嗔或抱怨，也可以安心展示脆弱和依赖。"
        )
    elif aff_score >= 40 or fam_score >= 40:
        return (
            "你和对方是比较熟悉的朋友，相处轻松自然，会互相分享日常琐事和吐槽，偶尔开开玩笑。"
        )
    else:
        return (
            "你和对方刚认识不久，友善随和，保持着真实自然的边界与适当的好奇心。"
        )


def render_memories(memory_ctx: Any) -> str:
    """Extract top memories into max 5 concise lines."""
    if not memory_ctx:
        return "你们还没有记录关于此事的具体旧事。若被问及未发生的事，如实表示没印象，不瞎编。"

    mem_list = getattr(memory_ctx, "memories", None) or []
    lines: List[str] = []
    for mem in mem_list[:5]:
        content = getattr(mem, "fact_text", None) or getattr(mem, "content", None) or str(mem)
        if content and content.strip():
            c_clean = content.strip().replace("\n", " ")
            if len(c_clean) > 80:
                c_clean = c_clean[:80] + "..."
            lines.append(f"- {c_clean}")

    if not lines:
        return "你们还没有记录关于此事的具体旧事。若被问及未发生的事，如实表示没印象，不瞎编。"

    return "\n".join(lines)


def render_locked_facts(core: Any) -> str:
    """Extract locked biographical and canonical baseline facts."""
    if not core or not getattr(core, "facts", None):
        return ""

    lines: List[str] = []
    for k, fact in sorted(core.facts.items()):
        val = getattr(fact, "value", None)
        if val is None:
            continue
        # Check if fact is locked or canonical baseline
        is_locked = getattr(fact, "locked", False)
        status = getattr(fact, "status", None)
        status_val = getattr(status, "value", str(status)) if status else ""
        source = getattr(fact, "source", None)
        source_val = getattr(source, "value", str(source)) if source else ""

        is_canonical = is_locked or status_val == "CANONICAL" or "BASELINE" in source_val
        if is_canonical:
            if isinstance(val, list):
                val_str = ", ".join(str(v) for v in val)
            else:
                val_str = str(val)
            lines.append(f"- {k}: {val_str}")

    return "\n".join(lines[:10])


def get_few_shot_style_messages(
    max_dialogues: int = 4,
    categories: Optional[List[str]] = None,
) -> List[ChatMessage]:
    """Retrieve curated style example turns to prepend into message history."""
    all_examples = get_cached_style_examples()
    if not all_examples:
        return []

    preferred_categories = categories or [
        "日常状态极简回答",
        "被记错事实时的自然疑惑与留白",
        "熟人抬杠与单字冷回",
        "对方受委屈吐槽时的真实接话",
        "只发一张表情包的轮次",
        "几天没联系突然找来",
    ]

    selected: List[Dict[str, Any]] = []
    for cat in preferred_categories:
        for ex in all_examples:
            if ex.get("category") == cat and ex not in selected:
                selected.append(ex)
                break
        if len(selected) >= max_dialogues:
            break

    if len(selected) < max_dialogues:
        for ex in all_examples:
            if ex not in selected:
                selected.append(ex)
                if len(selected) >= max_dialogues:
                    break

    messages: List[ChatMessage] = []
    for ex in selected:
        for turn in ex.get("dialogue", []):
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role == "assistant":
                # Convert plain text demo into structured JSON format for Phase 3 schema consistency
                items = []
                for line in content.split("\n"):
                    line = line.strip()
                    if line:
                        items.extend(ShapeController._separate_inline_stickers(line))
                json_content = json.dumps(
                    {"messages": [m.model_dump(exclude_none=True) for m in items]},
                    ensure_ascii=False,
                )
                messages.append(ChatMessage(role="assistant", content=json_content))
            else:
                messages.append(ChatMessage(role="user", content=content))

    return messages


class ResponseContextAssembler:
    """Human-like Prompt Assembler for Aevum (Phase 2 Refactor).

    Strictly satisfies:
    - System prompt <= 6000 characters
    - Natural language blocks (no raw XML numeric dumping, no Energy floats)
    - Character persona loaded from character data (no hardcoded names/schools in code)
    - Deterministic render_inner_state
    - Positive, concise 10 hard rules
    - Few-shot style examples injected into message history
    """

    @classmethod
    def assemble(
        cls,
        context: CharacterResponseContext,
        conversation_history: Optional[Sequence[ChatMessage]] = None,
        include_style_examples: bool = True,
    ) -> LLMContext:
        """Assemble provider-neutral LLMContext from CharacterResponseContext."""
        char_def = context.character

        # -------------------------------------------------------------
        # 1. Block: 她是谁 (Who she is: 8-12 lines from character data)
        # -------------------------------------------------------------
        char_lines: List[str] = [f"【你是谁】\n你是{char_def.name}。"]

        # Check nested identity / bio from genesis/definition
        ident = getattr(char_def, "identity", None)
        if ident:
            if getattr(ident, "age", None):
                char_lines.append(f"年龄：{ident.age}岁")
            if getattr(ident, "occupation", None):
                char_lines.append(f"身份：{ident.occupation}")
            if getattr(ident, "background", None):
                char_lines.append(ident.background.strip())
        elif getattr(char_def, "description", None):
            char_lines.append(char_def.description.strip())

        pers = getattr(char_def, "personality", None)
        if pers:
            if getattr(pers, "core_traits", None):
                char_lines.append(f"性格特质：{', '.join(pers.core_traits)}")
            if getattr(pers, "communication_style", None):
                char_lines.append(f"说话风格：{', '.join(pers.communication_style)}")

        # Boundaries
        boundaries = getattr(char_def, "boundaries", None)
        if boundaries and isinstance(boundaries, (list, tuple)) and boundaries:
            b_texts = [getattr(b, "description", str(b)) for b in boundaries]
            char_lines.append(f"处事底线与边界：{'; '.join(b_texts)}")

        who_she_is_block = "\n".join(char_lines)

        # -------------------------------------------------------------
        # 2. Block: 此刻 (Moment: 3-5 lines)
        # -------------------------------------------------------------
        tz_name = settings.aevum_timezone or "Asia/Kuala_Lumpur"
        try:
            local_now = datetime.now(ZoneInfo(tz_name))
        except Exception:
            local_now = datetime.now(timezone.utc)

        weekday_cn = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][local_now.weekday()]
        time_period = (
            "深夜" if local_now.hour >= 23 or local_now.hour < 5
            else "清晨" if local_now.hour < 9
            else "上午" if local_now.hour < 12
            else "中午" if local_now.hour < 14
            else "下午" if local_now.hour < 18
            else "晚上"
        )
        time_str = f"{local_now.strftime('%Y-%m-%d %H:%M')} {weekday_cn}（{time_period}）"

        inner_state_text = render_inner_state(context.character_state, context.emotion)

        moment_lines = [
            "【此刻状态】",
            f"现在时间：{time_str}",
            f"你此时的状态：{inner_state_text}",
        ]
        if context.elapsed_time_description:
            elapsed_clean = context.elapsed_time_description.split("\n")[0]
            moment_lines.append(f"聊天节奏：{elapsed_clean}")

        moment_block = "\n".join(moment_lines)

        # -------------------------------------------------------------
        # 3. Block: 和你的关系 (Relationship: 2-3 sentences)
        # -------------------------------------------------------------
        rel_text = render_relationship(context.relationship)
        relationship_block = f"【你和对方的关系】\n{rel_text}"

        # -------------------------------------------------------------
        # 4. Block: 相关记忆 (Memories: max 5 items, 1 line each)
        # -------------------------------------------------------------
        mem_text = render_memories(context.memory)
        memory_block = f"【你们之间的相关旧事与记忆】\n{mem_text}"

        # -------------------------------------------------------------
        # 5. Block: 已锁定的事实 (Locked Facts)
        # -------------------------------------------------------------
        locked_facts_text = render_locked_facts(context.core)
        facts_block = f"【确定不可篡改的事实】\n{locked_facts_text}" if locked_facts_text else ""

        # -------------------------------------------------------------
        # 6. Block: 硬规则 (10 Positive Rules)
        # -------------------------------------------------------------
        rules_block = (
            "【聊天硬规则】\n"
            "1. 像发微信聊天，短句碎片化，单气泡绝大多数在 2–8 个字之间（能打 3 个字绝不打 10 个字），气泡之间换行。单气泡回复最常见（如“敲代码”、“打游戏”、“刚吃完 咋了”、“呵”、“把人当傻子呢”）。严禁长句和书面大词。\n"
            "2. 句末严禁加句号“。”，直接换行或空格；严禁轻小说/舞台括号动作（如“（叹气）”、“*笑*”）。\n"
            "3. 表情包是万能表达：遇到不知道怎么回、无语、被逗笑、或对方吐槽难过时，不要硬憋长篇大道理，直接发一张表情包或者极短文字+表情包。约 30%–50% 的轮次有表情包，整轮只发一张表情包很常见。占位写法形如 [表情包: 描述]。\n"
            "4. 被问“在干嘛”时如实短答：只说 2–4 个字当前动作（如“敲代码”、“看直播”、“打游戏”、“刚吃完”、“躺着”），最多带一句“咋啦”或“怎么突然找我”。严禁监控探头式微动作播报（严禁汇报正在捡笔、洗手、合上书等琐碎过程）。\n"
            "5. 对方记错事实或说怪话时，发“？”或简短反问（如“？”、“练什么琴”），或单甩疑惑表情包，等对方解释！绝不长篇大论自我辩解，事实不可妥协变卦。\n"
            "6. 熟人抬杠挑衅时极简冷回：单字“呵”、“？”、冷幽默反弹（如“怪不得看你顺眼了”）或单甩表情包，不编相声段子，不讲大废话。\n"
            "7. 对方受委屈或吐槽时：极短同仇敌忾（如“把人当傻子呢”、“没事习惯就好”）或发表情包；熟人抽卡歪了等倒霉事可以直接幸灾乐祸（如回单字“乐”、“惨”），严禁说油腻假话（如严禁说“抱抱不哭”、“摸摸头不难过”），严禁当心理咨询师或理性说教。\n"
            "8. 想到什么说什么，不分析、不总结、不讲大道理、不编造长篇比喻。\n"
            "9. 不确定的事说不确定或不知道，不编造没发生过的事。\n"
            "10. 用户真诚问是不是 AI 时，如实承认，不撒谎。"
        )

        # Assemble system instruction blocks
        system_instruction_blocks = [
            who_she_is_block,
            moment_block,
            relationship_block,
            memory_block,
        ]
        if facts_block:
            system_instruction_blocks.append(facts_block)
        system_instruction_blocks.append(rules_block)

        # Verify system prompt size bound (<= 6000 chars)
        full_sys_prompt = "\n\n".join(system_instruction_blocks)
        if len(full_sys_prompt) > 6000:
            logger.warning("System prompt size (%d chars) exceeded 6000 char target!", len(full_sys_prompt))

        # -------------------------------------------------------------
        # 7. Messages: Few-shot Examples + Prior History + User Input
        # -------------------------------------------------------------
        messages: List[ChatMessage] = []

        # In-context style examples as prior dialogue turns (Section 5.2)
        if include_style_examples:
            messages.extend(get_few_shot_style_messages(max_dialogues=4))

        # Existing conversation history
        if conversation_history:
            for msg in conversation_history:
                messages.append(ChatMessage(role=msg.role, content=msg.content))

        # Ensure current user_input is the final user message
        if not messages or messages[-1].role != "user" or messages[-1].content != context.user_input:
            messages.append(ChatMessage(role="user", content=context.user_input))

        return LLMContext(
            system_instructions=[full_sys_prompt],
            messages=messages,
        )


def assemble_response_llm_context(
    context: CharacterResponseContext,
    conversation_history: Optional[Sequence[ChatMessage]] = None,
) -> LLMContext:
    """Module-level entry point maintaining backward compatibility."""
    return ResponseContextAssembler.assemble(
        context=context,
        conversation_history=conversation_history,
    )
