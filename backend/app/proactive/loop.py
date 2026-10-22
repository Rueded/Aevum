"""Proactive Background Loop for Project Aevum (Phase 5 §8.1 - §8.4).

Governed by AEVUM_HUMANLIKE_REFACTOR_BRIEF §8:
- Runs in FastAPI lifespan background loop every ~5 minutes (default 300s).
- Evaluates 6 deterministic gates (master switch, DND, quiet hours, daily cap 1-3,
  doubled cooldown when 2+ unreplied, busy/sleep guard).
- If gates pass: executes LLM Thought Generation (ProactiveThoughtEngine)
  evaluating whether she feels like speaking autonomously based on her current day.
- Human-like shape constraints enforced via ShapeController (1-3 short bubbles).
- Saves canonical Message and bound ProactiveNotificationRecord (status=PENDING).
"""

import asyncio
from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    CharacterDefinitionRecord,
    Conversation,
    DesktopUserSettingsRecord,
    Message,
    MessageRole,
    ProactiveNotificationRecord,
)
from app.db.session import async_session_factory
from app.life.schedule_engine import LifeScheduleEngine
from app.llm import get_llm_provider
from app.llm.base import LLMProvider
from app.proactive.gate_engine import ProactiveGateEngine
from app.proactive.models import (
    DesktopUserSettings,
    NotificationStatus,
    ProactiveIntent,
    ProactiveIntentType,
)
from app.proactive.thought_engine import ProactiveThoughtEngine, ProactiveThoughtOutput

logger = logging.getLogger(__name__)


class ProactiveLoop:
    """Periodic autonomous background loop inspecting and generating reach-out opportunities."""

    def __init__(
        self,
        interval_seconds: float = 300.0,
        llm_provider: Optional[LLMProvider] = None,
        gate_engine: Optional[ProactiveGateEngine] = None,
    ) -> None:
        self.interval_seconds = interval_seconds
        self._provider = llm_provider
        self.gate_engine = gate_engine or ProactiveGateEngine()
        self._running = False

    def _get_provider(self) -> LLMProvider:
        if self._provider is not None:
            return self._provider
        return get_llm_provider()

    async def run_tick(
        self,
        current_time: Optional[datetime] = None,
        session_override: Optional[AsyncSession] = None,
    ) -> list[dict[str, Any]]:
        """
        Execute one complete proactive inspection tick across all registered characters.

        Can be called directly by unit tests with optional session_override or mock time.
        """
        now_utc = current_time or datetime.now(timezone.utc)
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)

        results: list[dict[str, Any]] = []

        if session_override is not None:
            return await self._tick_with_session(session_override, now_utc)

        async with async_session_factory() as session:
            try:
                results = await self._tick_with_session(session, now_utc)
            except Exception as exc:
                logger.exception("Error during proactive tick: %s", exc)
        return results

    async def _tick_with_session(
        self,
        session: AsyncSession,
        now_utc: datetime,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []

        # 1. Discover all companion characters
        char_stmt = select(CharacterDefinitionRecord.id, CharacterDefinitionRecord.name)
        chars = list((await session.execute(char_stmt)).all())
        if not chars:
            chars = [("aevum", "苏棠")]

        for char_id, char_name in chars:
            res_entry = {
                "character_id": char_id,
                "character_name": char_name,
                "reached_out": False,
                "reason": None,
                "bubbles": [],
            }

            try:
                # 2. Fetch or construct DesktopUserSettings
                settings_stmt = select(DesktopUserSettingsRecord).where(
                    DesktopUserSettingsRecord.character_id == char_id
                )
                user_settings_rec = (await session.scalars(settings_stmt)).first()

                if user_settings_rec is None:
                    user_settings = DesktopUserSettings(character_id=char_id, proactive_enabled=False)
                else:
                    user_settings = DesktopUserSettings(
                        character_id=char_id,
                        proactive_enabled=user_settings_rec.proactive_enabled,
                        timezone=user_settings_rec.timezone,
                        quiet_hours_enabled=user_settings_rec.quiet_hours_enabled,
                        quiet_hours_start=user_settings_rec.quiet_hours_start,
                        quiet_hours_end=user_settings_rec.quiet_hours_end,
                        max_daily_reach_outs=user_settings_rec.max_daily_reach_outs,
                        min_cooldown_minutes=user_settings_rec.min_cooldown_minutes,
                        idle_awareness_enabled=user_settings_rec.idle_awareness_enabled,
                        idle_threshold_seconds=user_settings_rec.idle_threshold_seconds,
                        reply_latency_enabled=getattr(user_settings_rec, "reply_latency_enabled", False),
                        max_reply_latency_minutes=getattr(user_settings_rec, "max_reply_latency_minutes", 15),
                        dnd_until=user_settings_rec.dnd_until,
                    )

                # Gate 1: Check master switch early
                if not user_settings.proactive_enabled:
                    res_entry["reason"] = "proactive_disabled"
                    results.append(res_entry)
                    continue

                # 3. Fetch past 24h notifications for quota and cooldown inspection
                cutoff_24h = now_utc - timedelta(hours=24)
                notifs_stmt = (
                    select(ProactiveNotificationRecord)
                    .where(
                        ProactiveNotificationRecord.character_id == char_id,
                        ProactiveNotificationRecord.created_at >= cutoff_24h,
                    )
                    .order_by(ProactiveNotificationRecord.created_at.desc())
                )
                recent_notifs = list((await session.scalars(notifs_stmt)).all())

                # 4. Reconcile life activity
                life_state = await LifeScheduleEngine.reconcile_schedule(
                    session=session,
                    character_id=char_id,
                    dt_utc=now_utc,
                    timezone_str=user_settings.timezone,
                )
                current_activity = life_state.current_activity or "在房间休息"

                # 5. Inspect conversation history for consecutive unreplied assistant messages
                conv_stmt = (
                    select(Conversation)
                    .where(Conversation.character_id == char_id)
                    .order_by(Conversation.updated_at.desc())
                    .limit(1)
                )
                conv = (await session.scalars(conv_stmt)).first()

                unreplied_count = 0
                if conv:
                    msg_stmt = (
                        select(Message)
                        .where(Message.conversation_id == conv.id)
                        .order_by(Message.created_at.desc())
                        .limit(8)
                    )
                    recent_msgs = list((await session.scalars(msg_stmt)).all())
                    for m in recent_msgs:
                        if m.role == MessageRole.ASSISTANT.value:
                            unreplied_count += 1
                        else:
                            break

                # 6. Evaluate all 6 deterministic gates
                candidate_intent = ProactiveIntent(
                    intent_type=ProactiveIntentType.SHARE_EXPERIENCE,
                    character_id=char_id,
                    intent_strength=1.0,
                    grounding_activity_title=current_activity,
                )
                gate_result = self.gate_engine.evaluate_gates(
                    settings=user_settings,
                    intent=candidate_intent,
                    current_time=now_utc,
                    recent_notifications=recent_notifs,
                    fatigue=0.0,
                    current_activity=current_activity,
                    unreplied_count=unreplied_count,
                )

                if not gate_result.passed:
                    res_entry["reason"] = f"gate_suppressed:{gate_result.suppression_reason.value if gate_result.suppression_reason else 'unknown'}"
                    results.append(res_entry)
                    continue

                # 7. LLM Thought Generation (Brief §8.2 & §8.3)
                provider = self._get_provider()
                thought: ProactiveThoughtOutput = await ProactiveThoughtEngine.evaluate_reach_out(
                    session=session,
                    character_id=char_id,
                    llm_provider=provider,
                    current_time=now_utc,
                )

                if not thought.should_reach_out or not thought.bubbles:
                    res_entry["reason"] = f"thought_silence:{thought.thought_reason}"
                    results.append(res_entry)
                    continue

                # 8. Persist proactive messages & notification
                if conv is None:
                    conv = Conversation(
                        id=str(uuid.uuid4()),
                        character_id=char_id,
                        created_at=now_utc,
                        updated_at=now_utc,
                    )
                    session.add(conv)
                    await session.flush()

                first_msg_id: Optional[str] = None
                for idx, bubble in enumerate(thought.bubbles):
                    msg_time = now_utc + timedelta(seconds=idx)
                    msg = Message(
                        id=str(uuid.uuid4()),
                        conversation_id=conv.id,
                        role=MessageRole.ASSISTANT.value,
                        content=bubble,
                        created_at=msg_time,
                    )
                    session.add(msg)
                    if first_msg_id is None:
                        first_msg_id = msg.id

                    # Sync message to Firestore
                    try:
                        from app.core.firestore_sync import sync_message_to_firestore
                        sync_message_to_firestore(msg.id, conv.id, msg.role, msg.content, msg.created_at)
                    except Exception:
                        pass

                # Create bound ProactiveNotificationRecord (status=PENDING)
                idempotency_key = f"proactive:{char_id}:{now_utc.strftime('%Y%m%d%H%M')}"
                notif = ProactiveNotificationRecord(
                    id=str(uuid.uuid4()),
                    character_id=char_id,
                    conversation_message_id=first_msg_id or str(uuid.uuid4()),
                    trigger_type=thought.reach_out_type or "AUTONOMOUS",
                    idempotency_key=idempotency_key,
                    title=f"{char_name} 发来新消息",
                    body=thought.bubbles[0],
                    status=NotificationStatus.PENDING.value,
                    created_at=now_utc,
                )
                session.add(notif)
                conv.updated_at = now_utc + timedelta(seconds=len(thought.bubbles))

                await session.commit()

                # Push autonomous message to Telegram channel if active
                try:
                    from app.channels.telegram import TelegramChannel
                    tg = TelegramChannel.get_instance()
                    if tg is not None and tg.active_chat_id:
                        asyncio.create_task(tg.push_proactive_message(list(thought.bubbles)))
                except Exception as tg_err:
                    logger.debug("Telegram proactive push skipped: %s", tg_err)

                res_entry["reached_out"] = True
                res_entry["reason"] = thought.thought_reason
                res_entry["bubbles"] = list(thought.bubbles)
                results.append(res_entry)
                logger.info(
                    "Proactive reach-out generated for %s (%d bubbles): %s",
                    char_name,
                    len(thought.bubbles),
                    thought.bubbles,
                )
            except Exception as exc:
                logger.warning("Error evaluating proactive reach-out for %s: %s", char_id, exc)
                res_entry["reason"] = f"error:{exc}"
                results.append(res_entry)

        return results

    async def start(self) -> None:
        """Start long-running background task."""
        self._running = True
        logger.info("ProactiveLoop started (interval: %.1fs)", self.interval_seconds)
        while self._running:
            try:
                await self.run_tick()
            except asyncio.CancelledError:
                logger.info("ProactiveLoop cancelled.")
                break
            except Exception as exc:
                logger.exception("Unexpected error in proactive loop: %s", exc)

            try:
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                logger.info("ProactiveLoop cancelled during sleep.")
                break

    def stop(self) -> None:
        """Signal loop to stop."""
        self._running = False


async def start_proactive_loop(interval_seconds: float = 300.0) -> None:
    """Helper entry point for main lifespan."""
    loop = ProactiveLoop(interval_seconds=interval_seconds)
    await loop.start()
