"""Sticker Ingestion & Thumbnail Pipeline for Project Aevum (Phase 6 §9.1).

Governed by AEVUM_HUMANLIKE_REFACTOR_BRIEF §9.1:
- Local scanning & deduplication of PNG, JPG, GIF, WEBP.
- SHA-256 exact content deduplication.
- dHash perceptual difference hashing.
- Frame 0 extraction for GIF animated stickers saved to disk thumbnails.
- Automatic filename & directory prior labeling for high baseline accuracy.
- Persistent database indexing (paths & metadata in SQLite; blobs on disk).
"""

from datetime import datetime, timezone
import hashlib
import json
import logging
import os
import re
from typing import Any, Optional
import uuid

from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import StickerRecord

logger = logging.getLogger(__name__)

# Directory mappings for series naming and priority favorite flagging
SERIES_MAP = {
    ".": ("菲比/散装常用", True),
    "砂狼白子 表情包": ("砂狼白子", True),
    "doro表情包": ("doro", False),
    "永雏塔菲表情包 344张": ("永雏塔菲", False),
    "初音未来表情包 242张": ("初音未来", False),
    "DeepSeek鲸鱼娘表情包【动图200+静图1700张】": ("DeepSeek鲸鱼娘", False),
}

# Heuristic emotion tag mapping based on Chinese filename tokens
TAG_RULES = [
    (r"(问号|\?|？|疑惑|什么|啊？|难道说)", "问号/疑惑"),
    (r"(生气|气死|愤怒|怒|吵|骂|掀|服了)", "生气/破防"),
    (r"(笑|哈|嘿|乐|偷笑|咧嘴|开心|欢呼)", "开心/整活"),
    (r"(哭|泪|呜|难过|伤心|委屈|TT|呜呜)", "委屈/哭泣"),
    (r"(躺|瘫|摆烂|累|困|睡|休|无力)", "摆烂/疲倦"),
    (r"(抱|蹭|爱|喜欢|贴贴|摸摸|心|捧)", "亲昵/温暖"),
    (r"(无语|汗|白眼|别致|虾头|变态|奇怪|服)", "无语/嫌弃"),
    (r"(赞|强|厉害|高手|神|顶|ok|棒)", "认同/夸赞"),
    (r"(怼|阴阳|呵|走吧|去死|反击|开大)", "调侃/阴阳怪气"),
]


def calculate_dhash(image: Image.Image, hash_size: int = 8) -> str:
    """Calculate 64-bit difference hash (dHash) as a 16-char hex string."""
    try:
        resized = image.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
        # Use getdata or get_flattened_data
        try:
            pixels = list(resized.get_flattened_data())
        except AttributeError:
            pixels = list(resized.getdata())

        difference = []
        for row in range(hash_size):
            row_pixels = pixels[row * (hash_size + 1) : (row + 1) * (hash_size + 1)]
            for col in range(hash_size):
                difference.append(row_pixels[col] > row_pixels[col + 1])

        decimal_val = 0
        hex_parts = []
        for idx, bit in enumerate(difference):
            if bit:
                decimal_val += 1 << (idx % 4)
            if idx % 4 == 3:
                hex_parts.append(f"{decimal_val:x}")
                decimal_val = 0
        return "".join(hex_parts)
    except Exception as exc:
        logger.debug("dHash calculation failed: %s", exc)
        return ""


def clean_filename_prior(fname: str) -> tuple[str, list[str]]:
    """Extract clean title text and inferred emotion tags from filename."""
    base = os.path.splitext(fname)[0]
    # Remove leading numeric prefixes like "1", "120-", "Screenshot "
    cleaned = re.sub(r"^\d+[-_ ]*", "", base).strip()
    cleaned = re.sub(r"[-_ ]*(?:砂狼白子|菲比|表情包).*$", "", cleaned).strip()
    if not cleaned:
        cleaned = base

    tags: list[str] = []
    for pattern, tag in TAG_RULES:
        if re.search(pattern, base, re.IGNORECASE):
            if tag not in tags:
                tags.append(tag)

    return cleaned, tags


class StickerPipeline:
    """Manages batch scanning, thumbnail generation, and database registration."""

    def __init__(
        self,
        images_root: str = "docs/stickers/images",
        thumbs_root: str = "backend/data/stickers/thumbs",
    ) -> None:
        self.images_root = images_root
        self.thumbs_root = thumbs_root

    def _ensure_thumbs_dir(self) -> None:
        os.makedirs(self.thumbs_root, exist_ok=True)

    def extract_thumbnail(self, file_path: str, file_hash: str) -> Optional[str]:
        """Extract frame 0 for GIF, or generate thumbnail for large static image."""
        self._ensure_thumbs_dir()
        thumb_filename = f"{file_hash[:16]}.webp"
        thumb_abs_path = os.path.join(self.thumbs_root, thumb_filename)

        if os.path.exists(thumb_abs_path):
            return os.path.relpath(thumb_abs_path, start=os.getcwd()).replace("\\", "/")

        try:
            with Image.open(file_path) as img:
                is_gif = getattr(img, "is_animated", False) or file_path.lower().endswith(".gif")
                if is_gif:
                    img.seek(0)
                    frame = img.convert("RGBA")
                    frame.thumbnail((256, 256), Image.Resampling.LANCZOS)
                    frame.save(thumb_abs_path, "WEBP", quality=85)
                else:
                    if img.width > 256 or img.height > 256:
                        thumb = img.convert("RGBA")
                        thumb.thumbnail((256, 256), Image.Resampling.LANCZOS)
                        thumb.save(thumb_abs_path, "WEBP", quality=85)
                    else:
                        return None  # Original is already small enough
            return os.path.relpath(thumb_abs_path, start=os.getcwd()).replace("\\", "/")
        except Exception as exc:
            logger.warning("Failed to extract thumbnail for %s: %s", file_path, exc)
            return None

    async def ingest_stickers(
        self,
        session: AsyncSession,
        target_series: Optional[list[str]] = None,
        max_items: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Scan disk directory and ingest new/unique stickers into SQLite database.

        Idempotent: skips files already present with matching SHA-256 hash.
        """
        if not os.path.exists(self.images_root):
            logger.warning("Stickers images directory not found at '%s'", self.images_root)
            return {"status": "error", "message": f"Directory not found: {self.images_root}"}

        # Query existing hashes to skip already ingested files
        existing_hashes = set((await session.scalars(select(StickerRecord.file_hash))).all())

        discovered_count = 0
        added_count = 0
        skipped_dup_count = 0
        seen_run_hashes = set()

        for dirpath, _, filenames in os.walk(self.images_root):
            rel_dir = os.path.relpath(dirpath, self.images_root)
            series_name, is_fav = SERIES_MAP.get(rel_dir, (os.path.basename(dirpath) or "散装常用", False))

            if target_series and series_name not in target_series:
                continue

            for fname in sorted(filenames):
                ext = os.path.splitext(fname)[1].lower()
                if ext not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
                    continue

                full_path = os.path.join(dirpath, fname)
                rel_file_path = os.path.relpath(full_path, start=os.getcwd()).replace("\\", "/")

                # Compute content SHA-256
                try:
                    with open(full_path, "rb") as f:
                        file_bytes = f.read()
                    f_hash = hashlib.sha256(file_bytes).hexdigest()
                except Exception as exc:
                    logger.warning("Failed to read file %s: %s", full_path, exc)
                    continue

                discovered_count += 1

                # Exact duplicate check
                if f_hash in existing_hashes or f_hash in seen_run_hashes:
                    skipped_dup_count += 1
                    continue
                seen_run_hashes.add(f_hash)

                # Thumbnail & dHash
                thumb_path = self.extract_thumbnail(full_path, f_hash)
                dhash_val = None
                try:
                    with Image.open(full_path) as img:
                        dhash_val = calculate_dhash(img)
                except Exception:
                    pass

                # Derive initial prior text & tags from filename
                clean_title, tags = clean_filename_prior(fname)

                record = StickerRecord(
                    id=str(uuid.uuid4()),
                    file_path=rel_file_path,
                    thumb_path=thumb_path,
                    file_hash=f_hash,
                    dhash=dhash_val,
                    series=series_name,
                    description=clean_title,
                    text_ocr=clean_title if len(clean_title) <= 20 else "",
                    emotion_tags=json.dumps(tags, ensure_ascii=False),
                    usage_note="",
                    source="user_imported",
                    is_favorite=is_fav,
                    is_annotated=False,
                    use_count=0,
                    created_at=datetime.now(timezone.utc),
                )
                session.add(record)
                added_count += 1

                if max_items and added_count >= max_items:
                    break

            if max_items and added_count >= max_items:
                break

        await session.commit()
        logger.info(
            "Sticker ingestion complete: scanned=%d, added=%d, skipped_duplicates=%d",
            discovered_count,
            added_count,
            skipped_dup_count,
        )

        return {
            "status": "success",
            "scanned": discovered_count,
            "added": added_count,
            "skipped_duplicates": skipped_dup_count,
        }
