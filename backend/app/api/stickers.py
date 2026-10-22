"""Stickers & Memes HTTP API Endpoints for Project Aevum (Phase 6 §9)."""

import os
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import StickerRecord
from app.db.session import get_db_session
from app.stickers.models import StickerCandidate, StickerItem
from app.stickers.pipeline import StickerPipeline
from app.stickers.service import StickerService

router = APIRouter(prefix="/stickers", tags=["stickers"])


@router.get("", response_model=dict[str, Any], summary="List cataloged stickers")
async def list_stickers(
    series: Optional[str] = Query(None, description="Filter by sticker series"),
    favorite_only: bool = Query(False, description="Filter to favorite series only"),
    search: Optional[str] = Query(None, description="Search keyword in text or description"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """List stickers with pagination and optional series/keyword filtering."""
    query = select(StickerRecord)
    if series:
        query = query.where(StickerRecord.series == series)
    if favorite_only:
        query = query.where(StickerRecord.is_favorite.is_(True))
    if search:
        query = query.where(
            (StickerRecord.description.ilike(f"%{search}%"))
            | (StickerRecord.text_ocr.ilike(f"%{search}%"))
        )

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.scalar(count_query)) or 0

    # Paginate
    query = query.order_by(desc(StickerRecord.is_favorite), desc(StickerRecord.use_count), StickerRecord.created_at.asc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    records = list((await db.scalars(query)).all())

    service = StickerService(db)
    items = [service._record_to_item(r) for r in records]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


@router.get("/series", response_model=list[dict[str, Any]], summary="List sticker series summary")
async def list_sticker_series(db: AsyncSession = Depends(get_db_session)) -> list[dict[str, Any]]:
    """List all available sticker series with item counts and favorite status."""
    stmt = (
        select(StickerRecord.series, StickerRecord.is_favorite, func.count(StickerRecord.id))
        .group_by(StickerRecord.series, StickerRecord.is_favorite)
        .order_by(desc(StickerRecord.is_favorite), desc(func.count(StickerRecord.id)))
    )
    rows = list((await db.execute(stmt)).all())
    return [
        {
            "series": r[0],
            "is_favorite": r[1],
            "count": r[2],
        }
        for r in rows
    ]


@router.get("/candidates", response_model=list[StickerCandidate], summary="Get contextual sticker candidates")
async def get_sticker_candidates(
    emotion: str = Query("neutral", description="Current companion emotion"),
    snippet: Optional[str] = Query("", description="Recent user message snippet"),
    limit: int = Query(8, ge=1, le=20),
    db: AsyncSession = Depends(get_db_session),
) -> list[StickerCandidate]:
    """Retrieve 8-10 contextual sticker candidates for prompt context or UI preview."""
    service = StickerService(db)
    return await service.get_contextual_candidates(
        current_emotion=emotion,
        dialogue_snippet=snippet or "",
        limit=limit,
    )


@router.get("/{sticker_id}", response_model=StickerItem, summary="Get sticker details")
async def get_sticker(sticker_id: str, db: AsyncSession = Depends(get_db_session)) -> StickerItem:
    """Retrieve a single cataloged sticker by UUID."""
    service = StickerService(db)
    item = await service.get_sticker_by_id(sticker_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sticker not found")
    return item


@router.get("/{sticker_id}/file", summary="Stream raw sticker file")
async def get_sticker_file(sticker_id: str, db: AsyncSession = Depends(get_db_session)) -> FileResponse:
    """Stream the actual sticker image/gif binary from disk."""
    service = StickerService(db)
    item = await service.get_sticker_by_id(sticker_id)
    if not item or not os.path.exists(item.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sticker file not found")
    return FileResponse(item.file_path)


@router.get("/{sticker_id}/thumb", summary="Stream sticker thumbnail")
async def get_sticker_thumb(sticker_id: str, db: AsyncSession = Depends(get_db_session)) -> FileResponse:
    """Stream the thumbnail webp binary from disk (frame 0 for GIF)."""
    service = StickerService(db)
    item = await service.get_sticker_by_id(sticker_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sticker not found")

    target_path = item.thumb_path if item.thumb_path and os.path.exists(item.thumb_path) else item.file_path
    if not os.path.exists(target_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thumbnail not found")
    return FileResponse(target_path)
