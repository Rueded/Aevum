"""Tests for Multi-Bubble Burst Chat Rhythm & WeChat Emoji Pipeline.

Verifies:
- ConversationalResponseParser extracts multi-bubble bursts correctly.
- MessageRead schema dynamically populates speech_bubbles.
- Conversation API endpoints return speech_bubbles in responses.
"""

from datetime import datetime, timezone
import pytest
from httpx import AsyncClient

from app.api.schemas import MessageRead
from app.character.conversational_parser import ConversationalResponseParser
from tests.conftest import FakeLLMProvider


def test_conversational_parser_extracts_msg_tags():
    """Verify explicit <msg> tags are extracted into discrete bubbles."""
    raw = "<msg>刚到琴房！今天风好大[Facepalm]</msg><msg>刚才手都快吹僵了，先暖暖手再弹琴~</msg>"
    bubbles = ConversationalResponseParser.extract_bubbles(raw)
    assert len(bubbles) == 2
    assert bubbles[0] == "刚到琴房！今天风好大[Facepalm]"
    assert bubbles[1] == "刚才手都快吹僵了，先暖暖手再弹琴~"


def test_conversational_parser_extracts_multiline_bursts():
    """Verify newline-separated natural bursts are split into bubbles."""
    raw = "好的呀！\n我正好也在看肖邦的乐谱[愉快]\n你练到哪一段了？"
    bubbles = ConversationalResponseParser.extract_bubbles(raw)
    assert len(bubbles) == 3
    assert bubbles[0] == "好的呀！"
    assert bubbles[1] == "我正好也在看肖邦的乐谱[愉快]"
    assert bubbles[2] == "你练到哪一段了？"


def test_conversational_parser_extracts_punctuation_bursts():
    """Verify punctuation clauses with bracket emojis are cleanly split."""
    raw = "刚才吓死我了！猫咪居然跳上阳台栏杆了[旺柴] 还好被我一把抓住了~"
    bubbles = ConversationalResponseParser.extract_bubbles(raw)
    assert len(bubbles) >= 2
    assert any("[旺柴]" in b for b in bubbles)


def test_message_read_model_validator_populates_bubbles():
    """Verify MessageRead auto-populates speech_bubbles for assistant messages."""
    msg = MessageRead(
        id="test-msg-1",
        conversation_id="conv-1",
        role="assistant",
        content="刚练完琴！\n手好酸呀[苦涩]",
        created_at=datetime.now(timezone.utc),
    )
    assert msg.speech_bubbles is not None
    assert len(msg.speech_bubbles) == 2
    assert msg.speech_bubbles[0] == "刚练完琴！"
    assert msg.speech_bubbles[1] == "手好酸呀[苦涩]"


def test_message_read_preserves_explicit_speech_bubbles():
    """Verify MessageRead keeps explicitly provided speech_bubbles."""
    explicit_bubbles = ["第一句话", "第二句话[偷笑]"]
    msg = MessageRead(
        id="test-msg-2",
        conversation_id="conv-1",
        role="assistant",
        content="第一句话\n第二句话[偷笑]",
        created_at=datetime.now(timezone.utc),
        speech_bubbles=explicit_bubbles,
    )
    assert msg.speech_bubbles == explicit_bubbles


@pytest.mark.asyncio
async def test_conversation_api_returns_speech_bubbles(
    client: AsyncClient,
    fake_provider: FakeLLMProvider,
):
    """Verify create_message and get_conversation API responses include speech_bubbles."""
    # Set fake LLM output with multi-bubble CCDF structure
    fake_provider.response_text = (
        "<character_turn>\n"
        "<internal_decision>\n"
        "attention: user greeting\n"
        "reaction: happy\n"
        "commitment: PARTIAL_FLOW\n"
        "energy: NORMAL\n"
        "motivation: GENUINE_SHARING\n"
        "friction: POLITE_DISTANT\n"
        "curiosity: false\n"
        "</internal_decision>\n"
        "<character_speech>\n"
        "<msg>今天天气真好！[太阳]</msg>\n"
        "<msg>我刚泡了一杯热茶在看书呢~</msg>\n"
        "</character_speech>\n"
        "</character_turn>"
    )

    # 1. Create conversation
    create_conv_res = await client.post("/conversations")
    assert create_conv_res.status_code == 201
    conv_id = create_conv_res.json()["id"]

    # 2. Send user message
    msg_res = await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "今天在做什么呢？"},
    )
    assert msg_res.status_code == 201
    data = msg_res.json()
    assert data["assistant_status"] == "generated"
    assert data["assistant_response"] is not None

    bubbles = data["assistant_response"].get("speech_bubbles")
    assert bubbles is not None
    assert len(bubbles) == 2
    assert "今天天气真好！[太阳]" in bubbles[0]
    assert "我刚泡了一杯热茶在看书呢~" in bubbles[1]

    # 3. Retrieve conversation via GET /conversations/{id}
    get_conv_res = await client.get(f"/conversations/{conv_id}")
    assert get_conv_res.status_code == 200
    conv_data = get_conv_res.json()
    assistant_msgs = [m for m in conv_data["messages"] if m["role"] == "assistant"]
    assert len(assistant_msgs) == 1
    assert assistant_msgs[0]["speech_bubbles"] is not None
    assert len(assistant_msgs[0]["speech_bubbles"]) == 2
