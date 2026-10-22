"""Telegram Channel Runner for Project Aevum (Phase 7 §10).

Governed by AEVUM_HUMANLIKE_REFACTOR_BRIEF §10:
1. Official Telegram Bot API via long-polling (no public IP / webhook required).
2. Shares identical backend character state with desktop app (Live2D/body remains on desktop, mind shared).
3. Whitelist enforcement: only authorized user ID(s) can interact with the companion.
4. Multimodal input: text, photos (Gemini vision described), stickers (described), voice (transcribed).
5. Human-like multi-bubble output with realistic typing action and intervals.
6. Sticker rendering: resolves sticker tags to local image files and sends as photos/animations.
7. Proactive push integration: delivers Phase 5 autonomous reach-outs directly to the user's phone.
"""

import asyncio
from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import re
from typing import Any, Optional

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.active_service import get_active_character_id
from app.character.engine import CharacterEngine
from app.character.latency_policy import ReplyLatencyPolicy
from app.character.post_turn_service import PostTurnService
from app.character.response_generator import ResponseGenerator
from app.core.config import settings
from app.db.models import Conversation, Message, MessageRole, StickerRecord
from app.db.session import async_session_factory
from app.llm import ChatMessage, get_llm_provider
from app.memory import get_embedding_provider
from app.stickers.service import StickerService

logger = logging.getLogger("telegram_channel")

# Local cache file to remember the owner's chat_id across backend restarts
TELEGRAM_STATE_FILE = Path("backend/data/telegram_chat.json")


class TelegramClient:
    """Async client interacting with official Telegram Bot API."""

    def __init__(self, token: str, base_url: str = "https://api.telegram.org") -> None:
        self.token = token
        self.api_url = f"{base_url}/bot{token}"
        self.file_url = f"{base_url}/file/bot{token}"
        self._http = httpx.AsyncClient(timeout=45.0)

    async def close(self) -> None:
        await self._http.aclose()

    async def get_me(self) -> dict[str, Any]:
        resp = await self._http.get(f"{self.api_url}/getMe")
        resp.raise_for_status()
        return resp.json()["result"]

    async def get_updates(self, offset: int = 0, timeout: int = 30) -> list[dict[str, Any]]:
        payload = {"offset": offset, "timeout": timeout, "allowed_updates": ["message"]}
        resp = await self._http.post(f"{self.api_url}/getUpdates", json=payload)
        resp.raise_for_status()
        return resp.json().get("result", [])

    async def send_chat_action(self, chat_id: int, action: str = "typing") -> None:
        try:
            await self._http.post(
                f"{self.api_url}/sendChatAction",
                json={"chat_id": chat_id, "action": action},
            )
        except Exception as exc:
            logger.debug("Failed to send chat action %s to %s: %s", action, chat_id, exc)

    async def send_message(self, chat_id: int, text: str) -> dict[str, Any]:
        resp = await self._http.post(
            f"{self.api_url}/sendMessage",
            json={"chat_id": chat_id, "text": text},
        )
        resp.raise_for_status()
        return resp.json()["result"]

    async def send_photo(self, chat_id: int, photo_bytes: bytes, caption: Optional[str] = None) -> dict[str, Any]:
        files = {"photo": ("photo.jpg", photo_bytes, "image/jpeg")}
        data: dict[str, Any] = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption
        resp = await self._http.post(f"{self.api_url}/sendPhoto", data=data, files=files)
        resp.raise_for_status()
        return resp.json()["result"]

    async def send_animation(self, chat_id: int, anim_bytes: bytes, caption: Optional[str] = None) -> dict[str, Any]:
        files = {"animation": ("sticker.gif", anim_bytes, "image/gif")}
        data: dict[str, Any] = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption
        resp = await self._http.post(f"{self.api_url}/sendAnimation", data=data, files=files)
        resp.raise_for_status()
        return resp.json()["result"]

    async def send_document(
        self, chat_id: int, doc_bytes: bytes, filename: str, caption: Optional[str] = None
    ) -> dict[str, Any]:
        files = {"document": (filename, doc_bytes, "application/octet-stream")}
        data: dict[str, Any] = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption
        resp = await self._http.post(f"{self.api_url}/sendDocument", data=data, files=files)
        resp.raise_for_status()
        return resp.json()["result"]

    async def get_file_info(self, file_id: str) -> dict[str, Any]:
        resp = await self._http.post(f"{self.api_url}/getFile", json={"file_id": file_id})
        resp.raise_for_status()
        return resp.json()["result"]

    async def download_file_bytes(self, file_path: str) -> bytes:
        resp = await self._http.get(f"{self.file_url}/{file_path}")
        resp.raise_for_status()
        return resp.content


class TelegramChannel:
    """Aevum Telegram Channel Service providing mobile companion interaction."""

    _instance: Optional["TelegramChannel"] = None

    def __init__(
        self,
        token: Optional[str] = None,
        allowed_user_ids: Optional[str] = None,
        state_file: Optional[Path] = None,
    ) -> None:
        self.token = token or settings.telegram_bot_token
        self.allowed_raw = allowed_user_ids if allowed_user_ids is not None else settings.telegram_allowed_user_ids
        self.allowed_user_ids: set[int] = self._parse_allowed_ids(self.allowed_raw)
        self.state_file: Path = state_file or TELEGRAM_STATE_FILE

        self.client: Optional[TelegramClient] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.active_chat_id: Optional[int] = self._load_saved_chat_id()
        self.bot_info: dict[str, Any] = {}

        TelegramChannel._instance = self

    @classmethod
    def get_instance(cls) -> Optional["TelegramChannel"]:
        return cls._instance

    @staticmethod
    def _parse_allowed_ids(raw: str) -> set[int]:
        ids = set()
        for part in raw.replace(";", ",").split(","):
            cleaned = part.strip()
            if cleaned.isdigit() or (cleaned.startswith("-") and cleaned[1:].isdigit()):
                ids.add(int(cleaned))
        return ids

    def _load_saved_chat_id(self) -> Optional[int]:
        try:
            if self.state_file.exists():
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                return data.get("active_chat_id")
        except Exception as exc:
            logger.debug("Failed to load saved telegram chat id: %s", exc)
        return None

    def _save_active_chat_id(self, chat_id: int) -> None:
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(
                json.dumps({"active_chat_id": chat_id, "updated_at": datetime.now(timezone.utc).isoformat()}),
                encoding="utf-8",
            )
            self.active_chat_id = chat_id
        except Exception as exc:
            logger.warning("Failed to save telegram chat id: %s", exc)
        try:
            TELEGRAM_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            TELEGRAM_STATE_FILE.write_text(
                json.dumps({"active_chat_id": chat_id, "updated_at": datetime.now(timezone.utc).isoformat()}),
                encoding="utf-8",
            )
            self.active_chat_id = chat_id
        except Exception as exc:
            logger.warning("Failed to save telegram chat id: %s", exc)

    async def start(self) -> None:
        """Start Telegram Bot long polling runner."""
        if not self.token:
            logger.info("Telegram channel disabled: TELEGRAM_BOT_TOKEN not configured.")
            return

        self.client = TelegramClient(self.token)
        try:
            self.bot_info = await self.client.get_me()
            bot_username = self.bot_info.get("username", "unknown_bot")
            logger.info("Telegram Bot connected successfully: @%s (ID: %s)", bot_username, self.bot_info.get("id"))
            if not self.allowed_user_ids:
                logger.warning(
                    "TELEGRAM_ALLOWED_USER_IDS is empty! For security, no messages will be processed until "
                    "you send a message to @%s to see your user ID and add it to .env.",
                    bot_username,
                )
            else:
                logger.info("Telegram whitelist active: %d authorized user(s)", len(self.allowed_user_ids))
        except Exception as exc:
            logger.error("Failed to connect to Telegram Bot API with configured token: %s", exc)
            await self.client.close()
            self.client = None
            return

        self._running = True
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        """Stop Telegram Bot runner cleanly."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        if self.client is not None:
            await self.client.close()
            self.client = None
        logger.info("Telegram channel stopped cleanly.")

    async def _poll_loop(self) -> None:
        offset = 0
        backoff = 1.0
        while self._running:
            if not self.client:
                break
            try:
                updates = await self.client.get_updates(offset=offset, timeout=25)
                backoff = 1.0  # reset backoff upon successful request
                for update in updates:
                    update_id = update["update_id"]
                    offset = max(offset, update_id + 1)
                    if "message" in update:
                        asyncio.create_task(self._handle_update(update["message"]))
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Telegram polling error: %s (retrying in %.1fs)", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 30.0)

    async def _handle_update(self, msg: dict[str, Any]) -> None:
        from_user = msg.get("from", {})
        user_id = from_user.get("id")
        chat_id = msg.get("chat", {}).get("id")

        if not user_id or not chat_id:
            return

        # Security whitelist check
        if not self.allowed_user_ids or user_id not in self.allowed_user_ids:
            logger.warning(
                "Rejected Telegram message from unauthorized user ID: %s (Username: @%s, Name: %s). "
                "To authorize this user, add '%s' to TELEGRAM_ALLOWED_USER_IDS in .env",
                user_id,
                from_user.get("username", "none"),
                from_user.get("first_name", ""),
                user_id,
            )
            return

        # Save authorized chat_id for autonomous reach-outs
        if self.active_chat_id != chat_id:
            self._save_active_chat_id(chat_id)

        # Handle special commands like /start or /id
        text_content = msg.get("text", "")
        if text_content.strip() == "/start" or text_content.strip() == "/id":
            await self.client.send_message(
                chat_id,
                f"苏棠已连接！你的 Telegram User ID 是 `{user_id}`。已绑定桌面与手机共享状态。",
            )
            return

        # Multimodal perception: extract perceptual text representation
        user_input_text = await self._extract_user_content(msg)
        if not user_input_text:
            return

        logger.info(
            "Telegram input from User %s (@%s): %s",
            user_id,
            from_user.get("username"),
            user_input_text,
        )

        # Execute conversation turn with unified backend state
        await self._process_conversation_turn(chat_id, user_input_text)

    async def _extract_user_content(self, msg: dict[str, Any]) -> Optional[str]:
        """Extract text or multimodal description from Telegram message."""
        # 1. Plain text
        if "text" in msg:
            return msg["text"].strip()

        caption = msg.get("caption", "").strip()

        # 2. Photo
        if "photo" in msg and msg["photo"]:
            photo_sizes = msg["photo"]
            best_photo = photo_sizes[-1]
            file_id = best_photo["file_id"]
            desc = await self._describe_image(file_id)
            if caption:
                return f"[用户发来照片: {desc}] (附言: {caption})"
            return f"[用户发来照片: {desc}]"

        # 3. Sticker
        if "sticker" in msg:
            stk = msg["sticker"]
            emoji = stk.get("emoji", "")
            file_id = stk.get("file_id")
            # If static webp sticker, attempt vision description
            desc = ""
            if not stk.get("is_animated") and not stk.get("is_video") and file_id:
                desc = await self._describe_image(file_id, is_sticker=True)
            if desc:
                return f"[表情包: {desc}] {emoji}".strip()
            return f"[表情包: {emoji or '贴纸'}]"

        # 4. Voice message
        if "voice" in msg:
            file_id = msg["voice"]["file_id"]
            transcription = await self._transcribe_audio(file_id)
            if transcription:
                return transcription
            return "[用户发来一段语音]"

        return None

    async def _describe_image(self, file_id: str, is_sticker: bool = False) -> str:
        """Download image from Telegram and use Gemini multimodal vision to extract concise description."""
        if not settings.gemini_api_key or not self.client:
            return "表情图片" if is_sticker else "一张图片"

        try:
            file_info = await self.client.get_file_info(file_id)
            file_path = file_info.get("file_path")
            if not file_path:
                return "图片"
            img_bytes = await self.client.download_file_bytes(file_path)

            from google import genai
            from google.genai import types

            client = genai.Client(api_key=settings.gemini_api_key)
            prompt = (
                "简短用一句话描述这个表情包的神态、动作、角色或图上文字（20字以内）。"
                if is_sticker
                else "简短用一句话描述这张图片的内容、主体或亮点细节（30字以内）。"
            )

            mime = "image/webp" if file_path.endswith(".webp") else "image/jpeg"
            part_img = types.Part.from_bytes(data=img_bytes, mime_type=mime)
            part_txt = types.Part.from_text(text=prompt)

            resp = await asyncio.to_thread(
                client.models.generate_content,
                model=settings.gemini_model or "gemini-3.8-flash",
                contents=[part_img, part_txt],
            )
            desc = resp.text.strip().replace("\n", " ")
            return desc[:40] if desc else ("表情" if is_sticker else "图片")
        except Exception as exc:
            logger.warning("Gemini vision perception error for telegram image: %s", exc)
            return "表情" if is_sticker else "图片"

    async def _transcribe_audio(self, file_id: str) -> Optional[str]:
        """Download voice note and transcribe via Gemini multimodal audio."""
        if not settings.gemini_api_key or not self.client:
            return None

        try:
            file_info = await self.client.get_file_info(file_id)
            file_path = file_info.get("file_path")
            if not file_path:
                return None
            audio_bytes = await self.client.download_file_bytes(file_path)

            from google import genai
            from google.genai import types

            client = genai.Client(api_key=settings.gemini_api_key)
            part_audio = types.Part.from_bytes(data=audio_bytes, mime_type="audio/ogg")
            part_txt = types.Part.from_text(text="请准确转写这段语音内容为简体中文文本。只输出文字内容，不要有多余说明。")

            resp = await asyncio.to_thread(
                client.models.generate_content,
                model=settings.gemini_model or "gemini-3.8-flash",
                contents=[part_audio, part_txt],
            )
            text = resp.text.strip()
            return text if text else None
        except Exception as exc:
            logger.warning("Gemini audio transcription error for telegram voice: %s", exc)
            return None

    async def _process_conversation_turn(self, chat_id: int, user_text: str) -> None:
        """Run standard conversation turn through Aevum Core and stream bubbles to Telegram."""
        async with async_session_factory() as session:
            target_char_id = await get_active_character_id(session)

            # Discover or create the shared conversation session
            stmt = (
                select(Conversation)
                .where(Conversation.character_id == target_char_id)
                .order_by(Conversation.updated_at.desc())
                .limit(1)
            )
            conv = (await session.scalars(stmt)).first()
            if not conv:
                conv = Conversation(character_id=target_char_id)
                session.add(conv)
                await session.commit()
                await session.refresh(conv)

            conversation_id = conv.id

            # 1. Persist user message
            user_msg = Message(
                conversation_id=conversation_id,
                role=MessageRole.USER.value,
                content=user_text,
            )
            session.add(user_msg)
            conv.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(user_msg)

            # 2. Load recent conversation history (30 messages)
            hist_stmt = (
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.asc())
            )
            stored = list((await session.scalars(hist_stmt)).all())

            # 3. Elapsed time calculation
            elapsed_time_desc = None
            if len(stored) >= 2:
                prev_turn = stored[-2]
                prev_time = prev_turn.created_at if prev_turn.created_at.tzinfo else prev_turn.created_at.replace(tzinfo=timezone.utc)
                curr_time = user_msg.created_at if user_msg.created_at.tzinfo else user_msg.created_at.replace(tzinfo=timezone.utc)
                diff_sec = max(0, int((curr_time - prev_time).total_seconds()))
                if diff_sec < 45:
                    elapsed_time_desc = f"即时打字连续交流中（上一条消息仅过去 {diff_sec} 秒）"
                elif diff_sec < 180:
                    elapsed_time_desc = f"间隔约 {diff_sec // 60} 分钟，几乎是在同一连续对话节奏内"
                elif diff_sec < 3600:
                    elapsed_time_desc = f"距离上一条消息过去了约 {diff_sec // 60} 分钟。"
                elif diff_sec < 86400:
                    hrs = round(diff_sec / 3600, 1)
                    elapsed_time_desc = f"【重大时间流逝警报】：距离你们上一条消息过去了约 {hrs} 小时！请按当下作息自然问候并好奇询问对方。"
                else:
                    days = round(diff_sec / 86400, 1)
                    elapsed_time_desc = f"【多日未见真实警报】：距离你们上一次说话已经过去了 {days} 天！对方好几天没有找你了，要流露真实关切与好奇。"

            # 4. Schedule reconciliation & response context assembly
            try:
                from app.life.schedule_engine import LifeScheduleEngine
                await LifeScheduleEngine.reconcile_schedule(session, target_char_id)
            except Exception as sched_err:
                logger.debug("Schedule reconcile in telegram skipped: %s", sched_err)

            embedding_provider = get_embedding_provider()
            char_engine = CharacterEngine(session=session, embedding_provider=embedding_provider)
            response_context = await char_engine.build_response_context(
                user_input=user_text,
                character_id=target_char_id,
                user_id="user",
                elapsed_time_description=elapsed_time_desc,
                conversation_summary=getattr(conv, "summary", None),
            )

            # 5. Sleep realism check
            try:
                from app.desktop.service import DesktopService
                desktop_service = DesktopService(session)
                desktop_settings = await desktop_service.get_settings(target_char_id)
                sleep_realism = getattr(desktop_settings, "sleep_realism_enabled", True)
                current_act = (response_context.character_state.current_activity or "").lower()
                is_sleeping = any(k in current_act for k in ("sleep", "night_sleep", "deep_sleep", "睡觉", "睡眠", "小憩", "熟睡"))

                if sleep_realism and is_sleeping:
                    now_utc = datetime.now(timezone.utc)
                    recent_user_turns = [
                        m for m in stored
                        if m.role == MessageRole.USER.value
                        and (now_utc - (m.created_at if m.created_at.tzinfo else m.created_at.replace(tzinfo=timezone.utc))).total_seconds() <= 90
                    ]
                    char_name = getattr(response_context.character_definition, "name", "苏棠")
                    if len(recent_user_turns) < 3:
                        sleep_msg = Message(
                            conversation_id=conversation_id,
                            role=MessageRole.ASSISTANT.value,
                            content=f"（{char_name}正在深度睡眠中……呼吸平稳安静，没有被消息吵醒。若有急事可尝试连续发消息）",
                        )
                        session.add(sleep_msg)
                        conv.updated_at = now_utc
                        await session.commit()
                        await self.client.send_message(chat_id, sleep_msg.content)
                        return
            except Exception as sleep_err:
                logger.debug("Telegram sleep check skipped: %s", sleep_err)

            # 6. Generate Response via LLM
            recent_stored = stored[-30:] if len(stored) > 30 else stored
            chat_messages = [ChatMessage(role=m.role, content=m.content) for m in recent_stored]

            llm_provider = get_llm_provider()
            response_generator = ResponseGenerator(provider=llm_provider)
            llm_response = await response_generator.generate_response(
                context=response_context,
                conversation_history=chat_messages,
            )

            assistant_msg = Message(
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT.value,
                content=llm_response.content.strip(),
            )
            session.add(assistant_msg)
            conv.updated_at = datetime.now(timezone.utc)
            await session.commit()

            bubbles = llm_response.speech_bubbles or [assistant_msg.content]

            # 7. Asynchronous post-turn pipeline
            interaction_context = chat_messages + [ChatMessage(role=assistant_msg.role, content=assistant_msg.content)]
            asyncio.create_task(
                PostTurnService.run_post_turn_pipeline(
                    conversation_id=conversation_id,
                    target_char_id=target_char_id,
                    rel_id="user",
                    user_text=user_text,
                    assistant_text=assistant_msg.content,
                    interaction_context=interaction_context,
                    llm_provider=llm_provider,
                )
            )

            # 8. Send bubbles to Telegram with typing indicator and human intervals
            await self._send_bubbles_to_telegram(chat_id, bubbles, session)

    async def _send_bubbles_to_telegram(
        self, chat_id: int, bubbles: list[str], session: AsyncSession
    ) -> None:
        """Send bubbles sequentially with typing action and natural intervals, rendering stickers."""
        stk_svc = StickerService(session)

        for idx, bubble in enumerate(bubbles):
            bubble_clean = bubble.strip()
            if not bubble_clean:
                continue

            # Check if this bubble is or contains a sticker tag
            sticker_match = re.search(r"\[(?:表情包[：:]?\s*([^\]]+)|sticker:([a-zA-Z0-9_\-]+))\]", bubble_clean)
            if sticker_match:
                stk_query = (sticker_match.group(1) or sticker_match.group(2) or "").strip()
                stk_item = await stk_svc.get_sticker_by_name_or_hash(stk_query)

                # If sticker file exists on disk
                if stk_item and os.path.exists(stk_item.file_path):
                    await stk_svc.record_usage(stk_item.id)

                    # Remaining text without sticker
                    remaining_text = re.sub(
                        r"\[(?:表情包[：:]?\s*[^\]]+|sticker:[a-zA-Z0-9_\-]+)\]", "", bubble_clean
                    ).strip()

                    # Send typing/upload indicator
                    await self.client.send_chat_action(chat_id, "choose_sticker")
                    await asyncio.sleep(0.6)

                    # Send sticker
                    file_ext = os.path.splitext(stk_item.file_path)[1].lower()
                    with open(stk_item.file_path, "rb") as f:
                        file_bytes = f.read()

                    if file_ext == ".gif":
                        await self.client.send_animation(chat_id, file_bytes, caption=remaining_text or None)
                    elif file_ext in (".webp", ".png", ".jpg", ".jpeg"):
                        await self.client.send_photo(chat_id, file_bytes, caption=remaining_text or None)
                    else:
                        await self.client.send_document(
                            chat_id, file_bytes, filename=os.path.basename(stk_item.file_path), caption=remaining_text or None
                        )

                    if idx < len(bubbles) - 1:
                        await asyncio.sleep(0.8)
                    continue

            # Standard text bubble
            await self.client.send_chat_action(chat_id, "typing")
            # Calculate human-like typing pause based on text length (0.4s to 2.5s)
            typing_delay = min(2.5, max(0.4, len(bubble_clean) * 0.07))
            await asyncio.sleep(typing_delay)

            await self.client.send_message(chat_id, bubble_clean)

            # Inter-bubble pause
            if idx < len(bubbles) - 1:
                await asyncio.sleep(0.7)

    async def push_proactive_message(self, bubbles: list[str]) -> bool:
        """Push autonomous proactive reach-out bubbles directly to Telegram owner."""
        if not self.client or not self.active_chat_id:
            logger.debug("Cannot push proactive message: client or active_chat_id not available")
            return False

        try:
            async with async_session_factory() as session:
                await self._send_bubbles_to_telegram(self.active_chat_id, bubbles, session)
            logger.info("Successfully pushed proactive reach-out to Telegram (chat_id: %s)", self.active_chat_id)
            return True
        except Exception as exc:
            logger.error("Failed to push proactive reach-out to Telegram: %s", exc)
            return False


async def start_telegram_channel() -> Optional[TelegramChannel]:
    """Factory helper to start Telegram channel if enabled and configured."""
    if not settings.telegram_bot_token and not settings.telegram_enabled:
        return None

    channel = TelegramChannel()
    await channel.start()
    return channel
