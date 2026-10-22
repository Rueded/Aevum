"""Code-level shape and structural controller for character responses (Phase 3).

Enforces hard structural invariants without polluting the system prompt:
1. Max bubbles limit: 1-2 bubbles if fatigued/low energy; at most 3-4 bubbles otherwise.
2. Single bubble length constraint: splits text bubbles > 60 chars by punctuation delimiters.
3. Separation of text & stickers: guarantees each bubble is strictly text, sticker, or photo.
4. Curiosity guard: trims reflex conversational bounces ("你呢？", "那你呢？") when curiosity is not high.
"""

from typing import List, Optional
import re
from app.character.conversational_models import StructuredTurnOutput, TurnMessageItem


class ShapeController:
    """Enforces shape and structural rules in code."""

    MAX_SINGLE_BUBBLE_CHARS = 60
    PUNCTUATION_SPLIT_REGEX = re.compile(r"([。！？!？~\n]+)")
    REFLEX_QUESTION_REGEX = re.compile(r"([，,\s]*(?:你呢|那你呢|你今天呢)[？?~～!！]*\s*)$")
    STICKER_IN_TEXT_REGEX = re.compile(r"\[(?:表情包[：:]?\s*([^\]]+))\]")

    @classmethod
    def process(
        cls,
        raw_output: StructuredTurnOutput,
        energy_level: float = 0.7,
        is_tired: bool = False,
        curiosity_active: bool = False,
    ) -> StructuredTurnOutput:
        """Apply code-level shape transformations to the structured messages."""
        items: List[TurnMessageItem] = []

        # 1. First pass: normalize and separate mixed text/stickers
        for msg in raw_output.messages:
            if msg.type == "sticker":
                sid = (msg.sticker_id or "").strip()
                if sid:
                    items.append(TurnMessageItem(type="sticker", sticker_id=sid))
            elif msg.type == "photo":
                pid = (msg.photo_id or "").strip()
                if pid:
                    items.append(TurnMessageItem(type="photo", photo_id=pid))
            elif msg.type == "text":
                text = (msg.text or "").strip()
                if not text:
                    continue

                # Separate any inline [表情包: xxx] into discrete sticker items
                extracted_parts = cls._separate_inline_stickers(text)
                for part in extracted_parts:
                    if part.type == "text":
                        # If text > 60 chars, split by punctuation
                        split_texts = cls._split_long_text(part.text or "")
                        for st in split_texts:
                            if st.strip():
                                items.append(TurnMessageItem(type="text", text=st.strip()))
                    else:
                        items.append(part)

        # 2. Curiosity Guard: check trailing reflex questions
        if not curiosity_active and items:
            last_item = items[-1]
            if last_item.type == "text" and last_item.text:
                cleaned = cls.REFLEX_QUESTION_REGEX.sub("", last_item.text).strip()
                if cleaned:
                    last_item.text = cleaned
                elif len(items) > 1:
                    # If the entire bubble was just "你呢？", remove it
                    items.pop()

        # 3. Energy & Bubble Count Limit (Updated per Brief §2 & §6.3)
        # Fatigued or very low energy: max 2 bubbles
        # Normal or excited: allows natural 1–6 bursts, capping hard at 8
        if is_tired or energy_level < 0.35:
            max_bubbles = 2
        elif energy_level > 0.8:
            max_bubbles = 8
        else:
            max_bubbles = 6

        if len(items) > max_bubbles:
            # Preserve sticker if one was dropped in truncation
            has_sticker_after = any(it.type == "sticker" for it in items[max_bubbles:])
            items = items[:max_bubbles]
            if has_sticker_after and items and items[-1].type == "text":
                # Find the first sticker from original messages to keep
                for it in raw_output.messages:
                    if it.type == "sticker" and it.sticker_id:
                        items[-1] = TurnMessageItem(type="sticker", sticker_id=it.sticker_id.strip())
                        break

        return StructuredTurnOutput(messages=items)

    @classmethod
    def _separate_inline_stickers(cls, text: str) -> List[TurnMessageItem]:
        """Separates inline [表情包: xxx] from plain text."""
        result: List[TurnMessageItem] = []
        last_idx = 0
        for m in cls.STICKER_IN_TEXT_REGEX.finditer(text):
            pre = text[last_idx:m.start()].strip()
            if pre:
                result.append(TurnMessageItem(type="text", text=pre))
            sticker_name = m.group(1).strip()
            if sticker_name:
                result.append(TurnMessageItem(type="sticker", sticker_id=sticker_name))
            last_idx = m.end()

        post = text[last_idx:].strip()
        if post:
            result.append(TurnMessageItem(type="text", text=post))

        if not result and text.strip():
            result.append(TurnMessageItem(type="text", text=text.strip()))

        return result

    @classmethod
    def _split_long_text(cls, text: str) -> List[str]:
        """Splits long text (>60 chars) into natural smaller clauses."""
        if len(text) <= cls.MAX_SINGLE_BUBBLE_CHARS:
            return [text]

        # First split by newlines if any
        if "\n" in text:
            chunks: List[str] = []
            for part in text.split("\n"):
                if part.strip():
                    chunks.extend(cls._split_long_text(part.strip()))
            return chunks

        # Split by sentence-ending punctuation
        tokens = cls.PUNCTUATION_SPLIT_REGEX.split(text)
        merged: List[str] = []
        curr = ""
        for i in range(0, len(tokens) - 1, 2):
            clause = tokens[i] + tokens[i + 1]
            if len(curr) + len(clause) <= cls.MAX_SINGLE_BUBBLE_CHARS:
                curr += clause
            else:
                if curr.strip():
                    merged.append(curr.strip())
                curr = clause
        if len(tokens) % 2 == 1:
            curr += tokens[-1]
        if curr.strip():
            merged.append(curr.strip())

        return merged if merged else [text]

    @classmethod
    def render_bubbles(cls, structured_output: StructuredTurnOutput) -> List[str]:
        """Convert structured TurnMessageItems into string bubbles for UI & database storage."""
        bubbles: List[str] = []
        for msg in structured_output.messages:
            if msg.type == "sticker" and msg.sticker_id:
                bubbles.append(f"[表情包: {msg.sticker_id.strip()}]")
            elif msg.type == "photo" and msg.photo_id:
                bubbles.append(f"[图片: {msg.photo_id.strip()}]")
            elif msg.type == "text" and msg.text:
                bubbles.append(msg.text.strip())
        return bubbles
