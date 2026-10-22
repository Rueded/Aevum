"""Unit tests for Sticker & Meme Catalog System (Phase 6 §9)."""

from datetime import datetime, timezone
import json
import os
from PIL import Image
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.character.conversational_models import StructuredTurnOutput, TurnMessageItem
from app.character.shape_controller import ShapeController
from app.db.models import Base, StickerRecord
from app.stickers.models import StickerCandidate, StickerItem
from app.stickers.pipeline import StickerPipeline, calculate_dhash, clean_filename_prior
from app.stickers.service import StickerService


@pytest.fixture
async def sticker_session():
    """Create in-memory SQLite database with stickers table."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        # Seed test stickers
        s1 = StickerRecord(
            id="stk-phoebe-question",
            file_path="docs/stickers/images/？菲比.png",
            file_hash="hash001",
            series="菲比/散装常用",
            description="疑惑问号菲比",
            text_ocr="？",
            emotion_tags=json.dumps(["问号/疑惑", "无语/嫌弃"]),
            is_favorite=True,
            use_count=5,
        )
        s2 = StickerRecord(
            id="stk-phoebe-sleep",
            file_path="docs/stickers/images/1别睡了.webp",
            file_hash="hash002",
            series="菲比/散装常用",
            description="别睡了快起来",
            text_ocr="别睡了",
            emotion_tags=json.dumps(["摆烂/疲倦", "调侃/阴阳怪气"]),
            is_favorite=True,
            use_count=2,
        )
        s3 = StickerRecord(
            id="stk-shiroko-pout",
            file_path="docs/stickers/images/砂狼白子 表情包/2.webp",
            file_hash="hash003",
            series="砂狼白子",
            description="白子鼓脸生闷气",
            text_ocr="",
            emotion_tags=json.dumps(["调侃/阴阳怪气", "生气/破防"]),
            is_favorite=True,
            use_count=0,
        )
        s4 = StickerRecord(
            id="stk-doro-funny",
            file_path="docs/stickers/images/doro表情包/1.png",
            file_hash="hash004",
            series="doro",
            description="doro怪笑",
            text_ocr="哈哈",
            emotion_tags=json.dumps(["开心/整活"]),
            is_favorite=False,
            use_count=0,
        )
        session.add_all([s1, s2, s3, s4])
        await session.commit()
        yield session

    await engine.dispose()


def test_clean_filename_prior():
    """Verify filename prior cleaning and tag inference."""
    desc, tags = clean_filename_prior("1别睡了.webp")
    assert desc == "别睡了"
    assert "摆烂/疲倦" in tags

    desc2, tags2 = clean_filename_prior("？菲比.png")
    assert "问号/疑惑" in tags2

    desc3, tags3 = clean_filename_prior("120-砂狼白子表情包.gif")
    assert "砂狼白子" not in desc3 or desc3 == "120-砂狼白子表情包"


def test_calculate_dhash():
    """Verify dHash calculation produces 16-char hex string."""
    img = Image.new("RGB", (64, 64), color="blue")
    h = calculate_dhash(img)
    assert len(h) == 16
    assert isinstance(h, str)


@pytest.mark.asyncio
async def test_get_sticker_by_id(sticker_session: AsyncSession):
    """Verify retrieving a sticker by UUID."""
    service = StickerService(sticker_session)
    stk = await service.get_sticker_by_id("stk-phoebe-question")
    assert stk is not None
    assert stk.id == "stk-phoebe-question"
    assert stk.series == "菲比/散装常用"
    assert stk.is_favorite is True


@pytest.mark.asyncio
async def test_get_contextual_candidates_ranking(sticker_session: AsyncSession):
    """Verify contextual candidates ranking favors mood tags and favorite series."""
    service = StickerService(sticker_session)

    # When emotion is tsundere / annoyed: should retrieve shiroko pout and phoebe question
    candidates = await service.get_contextual_candidates(
        current_emotion="tsundere",
        limit=3,
    )
    assert len(candidates) >= 2
    c_ids = [c.id for c in candidates]
    # Shiroko pout has "调侃/阴阳怪气" + "生气/破防" matching tsundere
    assert "stk-shiroko-pout" in c_ids or "stk-phoebe-question" in c_ids


@pytest.mark.asyncio
async def test_anti_repetition_guard(sticker_session: AsyncSession):
    """Verify recently used sticker IDs are excluded from next turn candidates."""
    service = StickerService(sticker_session)
    candidates = await service.get_contextual_candidates(
        current_emotion="neutral",
        limit=4,
        exclude_sticker_ids=["stk-phoebe-question"],
    )
    c_ids = [c.id for c in candidates]
    assert "stk-phoebe-question" not in c_ids


@pytest.mark.asyncio
async def test_record_usage(sticker_session: AsyncSession):
    """Verify record_usage increments use_count and records timestamp."""
    service = StickerService(sticker_session)
    await service.record_usage("stk-doro-funny")

    updated = await service.get_sticker_by_id("stk-doro-funny")
    assert updated.use_count == 1
    assert updated.last_used_at is not None


def test_format_candidates_prompt():
    """Verify LLM prompt formatting for sticker candidates."""
    candidates = [
        StickerCandidate(
            id="test-1",
            series="菲比/散装常用",
            summary="疑惑问号菲比",
            emotion_tags=["问号/疑惑"],
        )
    ]
    prompt = StickerService.format_candidates_prompt(candidates)
    assert "【可用表情包候选库】" in prompt
    assert "test-1" in prompt
    assert "疑惑问号菲比" in prompt


def test_shape_controller_separates_stickers():
    """Verify ShapeController cleanly separates inline [表情包: xxx] and [sticker: xxx] into discrete bubbles."""
    raw = StructuredTurnOutput(
        messages=[
            TurnMessageItem(type="text", text="你怎么才来啊[表情包: 别睡了]快上号"),
            TurnMessageItem(type="text", text="看这个[sticker:test_img]"),
        ]
    )
    shaped = ShapeController.process(raw)
    bubbles = ShapeController.render_bubbles(shaped)

    assert any(b == "[表情包: 别睡了]" for b in bubbles)
    assert any(b == "[表情包: test_img]" for b in bubbles)
    assert not any("[表情包:" in b and len(b) > 20 for b in bubbles)


@pytest.mark.asyncio
async def test_api_list_stickers(client: AsyncClient):
    """Verify HTTP GET /stickers lists seeded stickers."""
    res = await client.get("/stickers")
    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert "items" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_api_sticker_candidates(client: AsyncClient):
    """Verify HTTP GET /stickers/candidates returns candidate list."""
    res = await client.get("/stickers/candidates?emotion=tsundere&limit=5")
    assert res.status_code == 200
    candidates = res.json()
    assert isinstance(candidates, list)
    if candidates:
        assert "id" in candidates[0]
        assert "series" in candidates[0]
        assert "summary" in candidates[0]
