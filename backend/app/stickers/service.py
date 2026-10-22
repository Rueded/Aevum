"""Sticker Retrieval & Recommendation Service for Project Aevum (Phase 6 §9.2 - §9.3).

Governed by AEVUM_HUMANLIKE_REFACTOR_BRIEF §9.2 & §9.3:
- Candidate Retrieval: Selects 8-10 diverse, contextually relevant sticker candidates per turn.
- Favorite Series Weighting: Reflects Su Tang's personal taste (Phoebe / casual吐槽 / Shiroko).
- Anti-Repetition Guard: Prevents back-to-back same sticker reuse without rigid hardcaps.
- Usage tracking: Maintains use_count and last_used_at timestamps.
"""

from datetime import datetime, timezone
import json
import logging
import random
from typing import Optional

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import StickerRecord
from app.stickers.models import StickerCandidate, StickerItem

logger = logging.getLogger(__name__)

# Emotion keyword map associating companion emotions with sticker tag patterns
EMOTION_TAG_MAP = {
    "happy": ["开心/整活", "认同/夸赞", "亲昵/温暖"],
    "joy": ["开心/整活", "认同/夸赞"],
    "tsundere": ["调侃/阴阳怪气", "无语/嫌弃", "生气/破防"],
    "annoyed": ["无语/嫌弃", "生气/破防", "调侃/阴阳怪气"],
    "angry": ["生气/破防", "无语/嫌弃"],
    "sad": ["委屈/哭泣", "摆烂/疲倦"],
    "tired": ["摆烂/疲倦", "委屈/哭泣"],
    "neutral": ["问号/疑惑", "认同/夸赞", "开心/整活"],
    "surprised": ["问号/疑惑", "开心/整活"],
}


class StickerService:
    """Service providing catalog search, contextual candidate ranking, and sticker lifecycle."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_sticker_by_id(self, sticker_id: str) -> Optional[StickerItem]:
        """Fetch sticker by UUID."""
        stmt = select(StickerRecord).where(StickerRecord.id == sticker_id)
        record = (await self.session.scalars(stmt)).first()
        if not record:
            return None
        return self._record_to_item(record)

    async def get_sticker_by_name_or_hash(self, query: str) -> Optional[StickerItem]:
        """Fetch sticker by description, text_ocr, filename, or hash prefix."""
        stmt = (
            select(StickerRecord)
            .where(
                or_(
                    StickerRecord.id == query,
                    StickerRecord.description.ilike(f"%{query}%"),
                    StickerRecord.text_ocr.ilike(f"%{query}%"),
                    StickerRecord.file_path.ilike(f"%{query}%"),
                    StickerRecord.file_hash.startswith(query),
                )
            )
            .limit(1)
        )
        record = (await self.session.scalars(stmt)).first()
        if not record:
            return None
        return self._record_to_item(record)

    async def get_contextual_candidates(
        self,
        current_emotion: str = "neutral",
        dialogue_snippet: str = "",
        limit: int = 8,
        exclude_sticker_ids: Optional[list[str]] = None,
    ) -> list[StickerCandidate]:
        """
        Retrieve 8-10 diverse sticker candidates grounded in emotion and conversation topic.

        Architecture Invariants (§9.2):
        - Favorite series (Su Tang's taste: Phoebe / Shiroko) get high priority weighting.
        - Includes candidates from non-favorite series for diversity.
        - Excludes recently used sticker IDs to prevent awkward back-to-back duplicate sends.
        """
        exclude_set = set(exclude_sticker_ids or [])

        # 1. Fetch favorite series pool
        fav_stmt = (
            select(StickerRecord)
            .where(StickerRecord.is_favorite.is_(True))
            .order_by(desc(StickerRecord.use_count))
            .limit(150)
        )
        fav_records = list((await self.session.scalars(fav_stmt)).all())

        # 2. Fetch non-favorite series pool for variety
        other_stmt = (
            select(StickerRecord)
            .where(StickerRecord.is_favorite.is_(False))
            .limit(50)
        )
        other_records = list((await self.session.scalars(other_stmt)).all())

        all_pool = fav_records + other_records
        if not all_pool:
            return []

        # Filter out recently sent duplicates
        filtered_pool = [r for r in all_pool if r.id not in exclude_set]
        if not filtered_pool:
            filtered_pool = all_pool

        # 3. Score candidates based on emotion tags and dialogue relevance
        target_tags = EMOTION_TAG_MAP.get(current_emotion.lower(), ["开心/整活", "问号/疑惑"])
        scored_candidates: list[tuple[float, StickerRecord]] = []

        for rec in filtered_pool:
            score = 1.0

            # Weight by personal favorite taste
            if rec.is_favorite:
                score += 3.0

            # Weight by matching emotion tags
            try:
                rec_tags = json.loads(rec.emotion_tags) if rec.emotion_tags else []
            except Exception:
                rec_tags = [t.strip() for t in rec.emotion_tags.split(",") if t.strip()]

            for t in target_tags:
                if any(t in rt for rt in rec_tags):
                    score += 4.0

            # Dialogue topic keyword match
            if dialogue_snippet and rec.text_ocr:
                if any(tok in dialogue_snippet for tok in rec.text_ocr if len(tok) >= 2):
                    score += 2.5

            # Slight randomness to prevent stagnant candidate sets across turns
            score += random.uniform(0.0, 1.5)
            scored_candidates.append((score, rec))

        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        # Select top candidates (favoring top favorites, plus 1-2 from diverse pool)
        selected_records: list[StickerRecord] = []
        for _, rec in scored_candidates:
            if len(selected_records) >= limit:
                break
            selected_records.append(rec)

        candidates = [
            StickerCandidate(
                id=rec.id,
                series=rec.series,
                summary=rec.description or rec.text_ocr or rec.series,
                emotion_tags=json.loads(rec.emotion_tags) if rec.emotion_tags.startswith("[") else [],
            )
            for rec in selected_records
        ]

        return candidates

    async def record_usage(self, sticker_id: str) -> None:
        """Increment usage metrics when companion or user sends a sticker."""
        stmt = select(StickerRecord).where(StickerRecord.id == sticker_id)
        record = (await self.session.scalars(stmt)).first()
        if record:
            record.use_count += 1
            record.last_used_at = datetime.now(timezone.utc)
            await self.session.commit()

    @classmethod
    def format_candidates_prompt(cls, candidates: list[StickerCandidate]) -> str:
        """Format candidate descriptors for injection into ResponseGenerator prompt."""
        if not candidates:
            return ""

        lines = [
            "【可用表情包候选库】（真人聊天中每隔几句就发一张，或整段单独只发一张表情包表达情绪）："
        ]
        for c in candidates:
            tag_str = f" [标签: {', '.join(c.emotion_tags)}]" if c.emotion_tags else ""
            lines.append(f"- ID: {c.id} | 【{c.series}】: {c.summary}{tag_str}")

        lines.extend([
            "【表情包使用规则】：",
            "1. 若本轮你想发表情包表达情绪，请在 `messages` 数组中添加一个类型为 `sticker` 的独立气泡：",
            "   `{\"type\": \"sticker\", \"sticker_id\": \"<选中的ID>\"}`",
            "2. 严禁把表情包和文字塞在同一个气泡中；",
            "3. 真人非常频繁单独只发一张表情包作为整轮回复（例如只回一张问号、无语、白眼、摸摸贴纸）；",
            "4. 若当前话题特别严肃或暂无贴合的表情包，也可以选择不发（全为 text 气泡）。",
        ])
        return "\n".join(lines)

    def _record_to_item(self, record: StickerRecord) -> StickerItem:
        tags: list[str] = []
        if record.emotion_tags:
            try:
                tags = json.loads(record.emotion_tags)
            except Exception:
                tags = [t.strip() for t in record.emotion_tags.split(",") if t.strip()]

        return StickerItem(
            id=record.id,
            file_path=record.file_path,
            thumb_path=record.thumb_path,
            file_hash=record.file_hash,
            dhash=record.dhash,
            series=record.series,
            description=record.description,
            text_ocr=record.text_ocr,
            emotion_tags=tags,
            usage_note=record.usage_note,
            source=record.source,
            is_favorite=record.is_favorite,
            is_annotated=record.is_annotated,
            use_count=record.use_count,
            last_used_at=record.last_used_at,
        )
