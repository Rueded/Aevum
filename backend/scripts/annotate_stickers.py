"""Multimodal Sticker Annotation Pilot Runner for Project Aevum (Phase 6 §9.1 item 3 & 4).

Usage:
    python backend/scripts/annotate_stickers.py --batch-size 20
    python backend/scripts/annotate_stickers.py --batch-size 100 --series 菲比/散装常用
    python backend/scripts/annotate_stickers.py --dry-run
"""

import argparse
import asyncio
from datetime import datetime, timezone
import json
import logging
import os
import sys
import time

from google import genai
from google.genai import types
from PIL import Image
from sqlalchemy import select

from app.core.config import settings
from app.db.models import StickerRecord
from app.db.session import async_session_factory
from app.stickers.models import StickerAnnotation

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("sticker_annotator")


SYSTEM_INSTRUCTION = """你是一个专业的微信表情包与二次元/互联网梗图理解引擎。
你的任务是观察提供的表情包图片，提取其核心视觉神态、图上文字，并生成精准的情绪态度标签与自然对话使用建议。

输出要求：
1. `desc`：一句话简短精准描述图片人物、动物神态或动作（20字以内，如“菲比两手一摊满脸无语”、“小狗双手抱头崩溃发癫”）。
2. `text`：图上清晰可见的文字或梗词（严格如实提取；若图上无任何文字则留空字符串 ""）。
3. `emotion_tags`：2-4个精准中文情绪标签（如：["无语", "阴阳怪气", "摆烂", "问号", "暗爽", "破防", "贴贴"]）。
4. `usage_note`：在日常真实微信聊天中适合什么情境甩出（如：“对方讲离谱八卦时”、“熟人问在干嘛不想解释时”）。
"""


def load_image_bytes_for_vision(file_path: str, thumb_path: str | None = None) -> tuple[bytes, str]:
    """Load image bytes suitable for vision model. If GIF, prefers webp/png thumbnail frame 0."""
    target_path = file_path
    if file_path.lower().endswith(".gif") and thumb_path and os.path.exists(thumb_path):
        target_path = thumb_path

    ext = os.path.splitext(target_path)[1].lower()
    mime = "image/webp" if ext == ".webp" else "image/png" if ext == ".png" else "image/jpeg"

    with open(target_path, "rb") as f:
        return f.read(), mime


async def run_annotation(batch_size: int = 20, series_filter: str | None = None, dry_run: bool = False):
    if not settings.gemini_api_key and not dry_run:
        logger.error("AEVUM_GEMINI_API_KEY is not configured in environment or .env!")
        return

    client = None if dry_run else genai.Client(api_key=settings.gemini_api_key)
    model_name = settings.gemini_model or "gemini-2.5-flash"

    async with async_session_factory() as session:
        query = select(StickerRecord).where(StickerRecord.is_annotated.is_(False))
        if series_filter:
            query = query.where(StickerRecord.series == series_filter)
        query = query.order_by(StickerRecord.is_favorite.desc(), StickerRecord.created_at.asc()).limit(batch_size)

        stickers = list((await session.scalars(query)).all())
        if not stickers:
            logger.info("No unannotated stickers found matching criteria.")
            return

        logger.info("Found %d unannotated stickers to process (dry_run=%s)...", len(stickers), dry_run)

        total_tokens = 0
        total_duration = 0.0
        success_count = 0

        for idx, stk in enumerate(stickers, 1):
            if not os.path.exists(stk.file_path):
                logger.warning("[%d/%d] File not found: %s", idx, len(stickers), stk.file_path)
                continue

            clean_desc_prior = stk.description or stk.text_ocr or "日常表情包"
            logger.info("[%d/%d] Processing: %s (Series: %s, Prior: %s)", idx, len(stickers), stk.file_path, stk.series, clean_desc_prior)

            if dry_run:
                continue

            try:
                img_bytes, mime_type = load_image_bytes_for_vision(stk.file_path, stk.thumb_path)
                part_img = types.Part.from_bytes(data=img_bytes, mime_type=mime_type)

                user_prompt = f"请标注这张表情包。先验信息：属于系列【{stk.series}】，文件名先验提示为：『{clean_desc_prior}』。"
                part_txt = types.Part.from_text(text=user_prompt)

                t0 = time.time()
                resp = await asyncio.to_thread(
                    client.models.generate_content,
                    model=model_name,
                    contents=[part_img, part_txt],
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        response_mime_type="application/json",
                        response_schema=StickerAnnotation,
                        temperature=0.2,
                    ),
                )
                duration = time.time() - t0
                total_duration += duration

                raw_json = resp.text.strip()
                annotation = StickerAnnotation.model_validate_json(raw_json)

                # Usage tokens tracking if available
                usage = getattr(resp, "usage_metadata", None)
                tokens = getattr(usage, "total_token_count", 0) if usage else 0
                total_tokens += tokens

                # Update database record
                stk.description = annotation.desc
                if annotation.text:
                    stk.text_ocr = annotation.text
                if annotation.emotion_tags:
                    stk.emotion_tags = json.dumps(annotation.emotion_tags, ensure_ascii=False)
                if annotation.usage_note:
                    stk.usage_note = annotation.usage_note
                stk.is_annotated = True

                await session.commit()
                success_count += 1

                logger.info(
                    "[%d/%d] Success (%.2fs, ~%d tokens) -> Text: '%s' | Desc: '%s' | Tags: %s",
                    idx,
                    len(stickers),
                    duration,
                    tokens,
                    annotation.text,
                    annotation.desc,
                    annotation.emotion_tags,
                )

                # Small sleep to respect rate limits
                await asyncio.sleep(0.5)

            except Exception as exc:
                logger.error("[%d/%d] Failed to annotate %s: %s", idx, len(stickers), stk.file_path, exc)

        logger.info("=== BATCH RUN SUMMARY ===")
        logger.info("Processed: %d, Succeeded: %d", len(stickers), success_count)
        if success_count > 0:
            avg_time = total_duration / success_count
            avg_tokens = total_tokens / success_count if total_tokens else 0
            logger.info("Average latency per sticker: %.2fs", avg_time)
            logger.info("Average tokens per sticker: %.1f tokens", avg_tokens)
            logger.info("Estimated tokens for 1,000 stickers: ~%d tokens", int(avg_tokens * 1000))


def main():
    parser = argparse.ArgumentParser(description="Pilot sticker annotator with Gemini multimodal.")
    parser.add_argument("--batch-size", type=int, default=20, help="Number of stickers to annotate in this batch.")
    parser.add_argument("--series", type=str, default=None, help="Filter to specific series.")
    parser.add_argument("--dry-run", action="store_true", help="Print items without making external API calls.")
    args = parser.parse_args()

    asyncio.run(run_annotation(batch_size=args.batch_size, series_filter=args.series, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
