"""Data models for Project Aevum Stickers & Memes System (Phase 6 §9)."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class StickerItem(BaseModel):
    """Client-facing and internal representation of a cataloged sticker."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    file_path: str
    thumb_path: Optional[str] = None
    file_hash: str
    dhash: Optional[str] = None
    series: str = "散装常用"
    description: str = ""
    text_ocr: str = ""
    emotion_tags: list[str] = Field(default_factory=list)
    usage_note: Optional[str] = None
    source: str = "user_imported"
    is_favorite: bool = False
    is_annotated: bool = False
    use_count: int = 0
    last_used_at: Optional[datetime] = None


class StickerCandidate(BaseModel):
    """Compact descriptor provided in LLM context for real-time candidate selection."""

    model_config = ConfigDict(frozen=True)

    id: str
    series: str
    summary: str = Field(description="Visual description and on-image text")
    emotion_tags: list[str] = Field(default_factory=list)


class StickerAnnotation(BaseModel):
    """Schema for multimodal LLM visual inspection of stickers (Brief §9.1 item 4)."""

    model_config = ConfigDict(extra="ignore")

    desc: str = Field(..., description="One sentence concise visual description of the character and expression.")
    text: str = Field(default="", description="Exact on-image OCR text or meme catchphrase, empty if no text.")
    emotion_tags: list[str] = Field(
        default_factory=list,
        description="2-4 emotion or attitude tags (e.g. ['无语', '阴阳怪气', '摆烂', '傲娇', '问号', '摸摸', '调侃']).",
    )
    usage_note: str = Field(default="", description="When it is most natural to use this sticker in conversational context.")
    series: Optional[str] = Field(default=None, description="Character series/author name if identifiable.")
