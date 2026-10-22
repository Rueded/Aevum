"""Proactive Thought Generation Engine for Project Aevum (Phase 5 §8.2 & §8.3).

Governed by AEVUM_HUMANLIKE_REFACTOR_BRIEF §8.2 & §8.3:
- Replaces mechanical heuristic arithmetic formulas with LLM-based autonomous thought evaluation.
- Context materials provided:
  * Current local time and what she is doing right now (from LifeScheduleEngine)
  * Time elapsed since last conversation message
  * Her own slice-of-life daily micro-incident
  * Recent conversation snippet
  * Prospective memory / user goals
- Output: 1-3 casual WeChat-style bubbles, or NO_MESSAGE (should_reach_out=False).
- Post-processed through ShapeController to guarantee human-like shape invariants.
"""

from datetime import datetime, timezone
import hashlib
import logging
from typing import Optional
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.conversational_models import StructuredTurnOutput, TurnMessageItem
from app.character.shape_controller import ShapeController
from app.core.config import settings
from app.db.models import (
    CharacterDefinitionRecord,
    Conversation,
    MemoryRecord,
    Message,
    MessageRole,
)
from app.life.schedule_engine import MICRO_INCIDENTS, LifeScheduleEngine
from app.llm.base import ChatMessage, LLMProvider
from app.llm.context_builder import build_context

logger = logging.getLogger(__name__)


class ProactiveThoughtOutput(BaseModel):
    """Schema for autonomous thought appraisal and proactive reach-out decisions."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    should_reach_out: bool = Field(
        ...,
        description="Whether she genuinely feels like reaching out to the user right now (True) or stays silent (False).",
    )
    reach_out_type: Optional[str] = Field(
        default=None,
        description="Category: 'SHARE_INCIDENT', 'FOLLOW_UP', 'TIME_GREETING', 'MISSING_FRIEND', or None if False.",
    )
    thought_reason: str = Field(
        ...,
        description="Internal psychological reasoning for deciding to speak or stay quiet.",
    )
    bubbles: list[str] = Field(
        default_factory=list,
        description="1-3 natural, short chat bubbles if should_reach_out is True; empty if False.",
    )


PROACTIVE_THOUGHT_SYSTEM_INSTRUCTION = """你是{char_name}。
你现在有自己独立真实的生活，正在做自己的事情。
你正在进行一次内心独白评估：此刻你是否想主动给对方发微信？

【你此时此刻的生活】
现在时间：{time_str}（{time_period}）
你正在做的事：{current_activity}，在{current_location}
你今天遇到的一件日常小事：{micro_incident}

【你们的聊天现状】
距离上次发消息已经过去了：{elapsed_desc}
你们最近聊的话题：
{recent_dialogue}

【你知道的关于对方的近期事项（待跟进）】
{prospective_items}

【核心决策规则】
1. 真人不会没事一直找人闲聊。绝大多数时候（70%–90% 甚至更高），你忙着自己的事或沉浸在当前动作中，不会想要发消息（should_reach_out = false, bubbles = []）。
2. 只有在以下自然动机之一出现时，才输出 should_reach_out = true：
   - 分享一件刚发生的具体好玩/离谱的小事（如刚才猫掀翻了东西、喝到了巨好喝的饮料、碰到了奇葩事）；
   - 自然想起对方前几天说过的事并跟进（如询问考试顺不顺利、身体好点没）；
   - 很久没联系（过去了整整两三天以上），自然地冒泡问一句；
   - 对方连续多条没回你时，你绝不连续刷屏追问，应当保持沉默。
3. 如果决定说话：
   - 必须是 1–3 条极短的微信碎片气泡（每句 2–10 个字，如“刚下楼拿外卖 地板好烫”、“小橘刚才把笔筒掀翻了[表情包: 瘫倒]”、“好几天没动静 忙完没”）。
   - 句末不加句号，严禁长篇大论，严禁客服式说教。
"""


class ProactiveThoughtEngine:
    """Evaluates whether the character autonomously feels like speaking to the user."""

    @classmethod
    async def evaluate_reach_out(
        cls,
        session: AsyncSession,
        character_id: str,
        llm_provider: LLMProvider,
        current_time: Optional[datetime] = None,
        force_evaluation: bool = False,
    ) -> ProactiveThoughtOutput:
        """Evaluate autonomous thought and return structured decision."""
        now_utc = current_time or datetime.now(timezone.utc)
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)

        # 1. Character Identity
        char_rec = await session.scalar(
            select(CharacterDefinitionRecord).where(CharacterDefinitionRecord.id == character_id)
        )
        char_name = char_rec.name if char_rec else "苏棠"

        # 2. Time & Current Activity
        tz_name = settings.aevum_timezone or "Asia/Kuala_Lumpur"
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = timezone.utc
        local_dt = now_utc.astimezone(tz)
        weekday_cn = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][local_dt.weekday()]
        hour = local_dt.hour
        time_period = (
            "深夜" if hour >= 23 or hour < 5
            else "清晨" if hour < 9
            else "上午" if hour < 12
            else "中午" if hour < 14
            else "下午" if hour < 18
            else "晚上"
        )
        time_str = f"{local_dt.strftime('%Y-%m-%d %H:%M')} {weekday_cn}"

        life_state = await LifeScheduleEngine.reconcile_schedule(
            session=session,
            character_id=character_id,
            dt_utc=now_utc,
            timezone_str=tz_name,
        )
        current_act = life_state.current_activity or "在房间休息"
        current_loc = life_state.current_location or "家中"

        # 3. Deterministic Micro-incident for today's time window
        period_key = (
            "night" if hour >= 22 or hour < 6
            else "morning" if hour < 12
            else "afternoon" if hour < 18
            else "evening"
        )
        incidents = MICRO_INCIDENTS.get(period_key, MICRO_INCIDENTS["afternoon"])
        seed_str = f"{character_id}:{local_dt.strftime('%Y-%m-%d')}:{period_key}"
        idx = int(hashlib.md5(seed_str.encode()).hexdigest(), 16) % len(incidents)
        micro_incident = incidents[idx]

        # 4. Conversation History & Elapsed Time
        conv_stmt = select(Conversation).where(Conversation.character_id == character_id).order_by(Conversation.updated_at.desc()).limit(1)
        conversation = (await session.scalars(conv_stmt)).first()

        recent_msgs: list[Message] = []
        elapsed_desc = "刚聊完不久"
        unreplied_count = 0

        if conversation:
            msg_stmt = select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at.desc()).limit(8)
            recent_msgs = list((await session.scalars(msg_stmt)).all())
            recent_msgs.reverse()

            if recent_msgs:
                last_m = recent_msgs[-1]
                l_time = last_m.created_at if last_m.created_at.tzinfo else last_m.created_at.replace(tzinfo=timezone.utc)
                diff_sec = max(0, int((now_utc - l_time).total_seconds()))
                if diff_sec < 180:
                    elapsed_desc = f"{diff_sec} 秒前（刚刚才聊过）"
                elif diff_sec < 3600:
                    elapsed_desc = f"{diff_sec // 60} 分钟前"
                elif diff_sec < 86400:
                    elapsed_desc = f"{round(diff_sec / 3600, 1)} 小时前"
                else:
                    elapsed_desc = f"{round(diff_sec / 86400, 1)} 天前（已经好几天没说话了）"

                # Count consecutive assistant turns at the end
                for m in reversed(recent_msgs):
                    if m.role == MessageRole.ASSISTANT.value:
                        unreplied_count += 1
                    else:
                        break

        # If user has not replied to last 2+ proactive messages: stay silent
        if unreplied_count >= 2 and not force_evaluation:
            logger.debug("ProactiveThoughtEngine: unreplied_count=%d >= 2, withholding proactive reach-out.", unreplied_count)
            return ProactiveThoughtOutput(
                should_reach_out=False,
                thought_reason="对方尚未回复前两条主动消息，不打扰，等待对方回复。",
                bubbles=[],
            )

        recent_dialogue = (
            "\n".join(f"{'用户' if m.role == 'user' else char_name}: {m.content}" for m in recent_msgs[-5:])
            if recent_msgs
            else "（最近尚无对话记录）"
        )

        # 5. Prospective Memories / Goals
        mem_stmt = (
            select(MemoryRecord)
            .where(
                MemoryRecord.character_id == character_id,
                MemoryRecord.category.in_(["USER_GOAL", "USER_PROBLEM", "PROMISE", "EVENT"]),
            )
            .order_by(MemoryRecord.created_at.desc())
            .limit(3)
        )
        mems = list((await session.scalars(mem_stmt)).all())
        prospective_items = (
            "\n".join(f"- {m.content}" for m in mems)
            if mems
            else "（近期暂无待跟进的特殊事项）"
        )

        # 6. Build LLM Context
        system_prompt = PROACTIVE_THOUGHT_SYSTEM_INSTRUCTION.format(
            char_name=char_name,
            time_str=time_str,
            time_period=time_period,
            current_activity=current_act,
            current_location=current_loc,
            micro_incident=micro_incident,
            elapsed_desc=elapsed_desc,
            recent_dialogue=recent_dialogue,
            prospective_items=prospective_items,
        )

        llm_context = build_context(
            messages=[ChatMessage(role="user", content="请评估你此刻是否想主动说话，并以规范结构返回决定。")],
            system_instructions=[system_prompt],
        )

        # 7. Execute Structured LLM Generation
        try:
            if hasattr(llm_provider, "generate_structured_response"):
                resp = await llm_provider.generate_structured_response(
                    context=llm_context,
                    response_schema=ProactiveThoughtOutput,
                )
                raw_json = (resp.content or "").strip()
            elif hasattr(llm_provider, "generate_structured"):
                raw_json = await llm_provider.generate_structured(
                    context=llm_context,
                    response_schema=ProactiveThoughtOutput,
                )
            else:
                resp = await llm_provider.generate_response(llm_context)
                raw_json = (resp.content or "").strip()

            if not raw_json:
                return ProactiveThoughtOutput(should_reach_out=False, thought_reason="LLM returned empty output", bubbles=[])

            thought = ProactiveThoughtOutput.model_validate_json(raw_json)

            # Apply ShapeController to bubbles if should_reach_out is True
            if thought.should_reach_out and thought.bubbles:
                raw_turn = StructuredTurnOutput(
                    messages=[TurnMessageItem(type="text", text=b) for b in thought.bubbles if b.strip()]
                )
                shaped = ShapeController.process(raw_turn, energy_level=0.7, curiosity_active=True)
                clean_bubbles = ShapeController.render_bubbles(shaped)[:3]
                return ProactiveThoughtOutput(
                    should_reach_out=bool(clean_bubbles),
                    reach_out_type=thought.reach_out_type,
                    thought_reason=thought.thought_reason,
                    bubbles=clean_bubbles,
                )

            return thought
        except Exception as exc:
            logger.warning("Proactive thought generation failed (%s). Defaulting to silence.", exc)
            return ProactiveThoughtOutput(
                should_reach_out=False,
                thought_reason=f"Generation failed: {exc}",
                bubbles=[],
            )
