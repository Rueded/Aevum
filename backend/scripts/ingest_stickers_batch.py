"""Batch ingestion script for Priority 1 & 2 stickers."""

import asyncio
from app.db.session import async_session_factory
from app.stickers.pipeline import StickerPipeline

async def main():
    pipeline = StickerPipeline(
        images_root="docs/stickers/images",
        thumbs_root="backend/data/stickers/thumbs",
    )
    async with async_session_factory() as session:
        print("Starting sticker ingestion for Priority 1 & 2...")
        res = await pipeline.ingest_stickers(
            session=session,
            target_series=["菲比/散装常用", "砂狼白子", "doro"],
        )
        print("Ingestion result:", res)

if __name__ == "__main__":
    asyncio.run(main())
