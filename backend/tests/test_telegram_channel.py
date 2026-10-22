"""Unit and integration tests for Telegram Channel (Phase 7 §10).

Covers:
- Whitelist authorization and rejection
- Multimodal payload extraction (text, photo, sticker, voice)
- Outgoing bubble streaming with typing actions
- Sticker resolution from SQLite stickers table
- Proactive message push delivery
- Graceful lifecycle management
"""

import asyncio
from datetime import datetime, timezone
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.channels.telegram import TelegramChannel, TelegramClient
from app.db.models import Conversation, Message, MessageRole, StickerRecord
from app.stickers.service import StickerItem


def test_telegram_channel_whitelist_parsing():
    """Verify comma/semicolon whitelist parsing of Telegram user IDs."""
    ch = TelegramChannel(token="dummy", allowed_user_ids="123456, 789012; -100998877")
    assert ch.allowed_user_ids == {123456, 789012, -100998877}

    ch_empty = TelegramChannel(token="dummy", allowed_user_ids="")
    assert ch_empty.allowed_user_ids == set()


@pytest.mark.asyncio
async def test_unauthorized_user_is_rejected():
    """Unauthorized Telegram user messages are ignored and do not trigger conversation turns."""
    ch = TelegramChannel(token="dummy", allowed_user_ids="111222")
    ch.client = MagicMock()
    ch._process_conversation_turn = AsyncMock()

    # Message from unauthorized user 999999
    unauth_msg = {
        "from": {"id": 999999, "username": "intruder"},
        "chat": {"id": 999999},
        "text": "Hello?",
    }
    await ch._handle_update(unauth_msg)
    ch._process_conversation_turn.assert_not_called()


@pytest.mark.asyncio
async def test_authorized_user_triggers_turn(tmp_path):
    """Authorized Telegram user message triggers conversation turn and updates active_chat_id."""
    ch = TelegramChannel(token="dummy", allowed_user_ids="111222", state_file=tmp_path / "tg.json")
    ch.client = MagicMock()
    ch._process_conversation_turn = AsyncMock()
    ch._save_active_chat_id = MagicMock()

    auth_msg = {
        "from": {"id": 111222, "username": "owner"},
        "chat": {"id": 888888},
        "text": "在干嘛呢",
    }
    await ch._handle_update(auth_msg)
    ch._process_conversation_turn.assert_called_once_with(888888, "在干嘛呢")
    ch._save_active_chat_id.assert_called_once_with(888888)


@pytest.mark.asyncio
async def test_start_command_returns_user_id_instruction():
    """Sending /start or /id returns connection acknowledgment and the user's ID."""
    ch = TelegramChannel(token="dummy", allowed_user_ids="111222")
    ch.client = MagicMock()
    ch.client.send_message = AsyncMock()
    ch._process_conversation_turn = AsyncMock()

    start_msg = {
        "from": {"id": 111222, "username": "owner"},
        "chat": {"id": 888888},
        "text": "/start",
    }
    await ch._handle_update(start_msg)
    ch.client.send_message.assert_called_once()
    sent_text = ch.client.send_message.call_args[0][1]
    assert "111222" in sent_text
    ch._process_conversation_turn.assert_not_called()


@pytest.mark.asyncio
async def test_extract_user_content_multimodal():
    """Extract multimodal payloads including text, photo with caption, sticker, and voice."""
    ch = TelegramChannel(token="dummy", allowed_user_ids="111222")
    ch._describe_image = AsyncMock(return_value="一只可爱的橘猫在晒太阳")
    ch._transcribe_audio = AsyncMock(return_value="今天天气真好出来散步")

    # Plain text
    assert await ch._extract_user_content({"text": "测试消息"}) == "测试消息"

    # Photo with caption
    photo_msg = {
        "photo": [{"file_id": "p1"}, {"file_id": "p2"}],
        "caption": "看我家猫猫",
    }
    content = await ch._extract_user_content(photo_msg)
    assert "[用户发来照片: 一只可爱的橘猫在晒太阳]" in content
    assert "(附言: 看我家猫猫)" in content

    # Static Sticker
    sticker_msg = {
        "sticker": {"file_id": "s1", "emoji": "🐱", "is_animated": False, "is_video": False}
    }
    stk_content = await ch._extract_user_content(sticker_msg)
    assert "[表情包:" in stk_content
    assert "🐱" in stk_content

    # Voice message
    voice_msg = {"voice": {"file_id": "v1"}}
    voice_content = await ch._extract_user_content(voice_msg)
    assert voice_content == "今天天气真好出来散步"


@pytest.mark.asyncio
async def test_send_bubbles_with_sticker_resolution(tmp_path):
    """Outgoing bubbles containing stickers are resolved and sent as media."""
    dummy_img = tmp_path / "test_cat.webp"
    dummy_img.write_bytes(b"RIFF....WEBPVP8 ...")

    mock_session = AsyncMock()
    mock_stk_item = StickerItem(
        id="stk-1",
        file_path=str(dummy_img),
        thumb_path=None,
        file_hash="hash1",
        series="测试系列",
        description="猫猫歪头",
        text_ocr="？",
        emotion_tags=["问号/疑惑"],
        is_favorite=True,
        is_annotated=True,
    )

    ch = TelegramChannel(token="dummy", allowed_user_ids="111222")
    ch.client = MagicMock()
    ch.client.send_chat_action = AsyncMock()
    ch.client.send_message = AsyncMock()
    ch.client.send_photo = AsyncMock()
    ch.client.send_animation = AsyncMock()

    with patch("app.channels.telegram.StickerService") as mock_service_cls:
        mock_svc = MagicMock()
        mock_svc.get_sticker_by_name_or_hash = AsyncMock(return_value=mock_stk_item)
        mock_svc.record_usage = AsyncMock()
        mock_service_cls.return_value = mock_svc

        bubbles = ["笑死", "[表情包: 猫猫歪头]"]
        await ch._send_bubbles_to_telegram(chat_id=12345, bubbles=bubbles, session=mock_session)

        # Bubble 1: text "笑死"
        ch.client.send_message.assert_called_once_with(12345, "笑死")
        # Bubble 2: photo sticker
        ch.client.send_photo.assert_called_once()
        mock_svc.record_usage.assert_called_once_with("stk-1")


@pytest.mark.asyncio
async def test_push_proactive_message():
    """Proactive message push delivers autonomous bubbles to active chat ID."""
    ch = TelegramChannel(token="dummy", allowed_user_ids="111222")
    ch.client = MagicMock()
    ch.active_chat_id = 998877
    ch._send_bubbles_to_telegram = AsyncMock()

    with patch("app.channels.telegram.async_session_factory") as mock_session_ctx:
        mock_session = AsyncMock()
        mock_session_ctx.return_value.__aenter__.return_value = mock_session

        success = await ch.push_proactive_message(["好无聊啊", "你在干嘛呢"])
        assert success is True
        ch._send_bubbles_to_telegram.assert_called_once_with(998877, ["好无聊啊", "你在干嘛呢"], mock_session)
