import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.character import router as character_router
from app.api.genesis import router as genesis_router
from app.api.conversations import router as conversations_router
from app.api.desktop import router as desktop_router
from app.api.health import router as health_router
from app.api.profile import router as profile_router
from app.api.voice import router as voice_router
from app.api.call_stream import router as call_stream_router
from app.api.sync import router as sync_router
from app.api.stickers import router as stickers_router
from app.core.config import settings
from app.db.session import async_session_factory, engine, init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle management."""
    # Startup: Initialize database tables according to declarative metadata
    await init_db()

    # Hydrate from Firestore if SQLite database is newly created / empty (e.g. on Render container restart)
    async with async_session_factory() as session:
        try:
            from app.core.firestore_sync import hydrate_sqlite_if_empty
            await hydrate_sqlite_if_empty(session)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Firestore hydration check skipped: %s", e)

    # Seed baseline defaults across services if needed
    async with async_session_factory() as session:
        try:
            from app.character.core_service import CharacterCoreService
            from app.character.service import CharacterDefinitionService
            from app.character.state_service import CharacterStateService
            from app.emotion.service import EmotionService
            from app.life.services import LifeService
            from app.relationship.service import RelationshipService
            from app.world.service import PersonalWorldService

            await CharacterCoreService(session).get_core("aevum")
            await CharacterDefinitionService(session).get_character("aevum")
            await CharacterStateService(session).get_state("aevum")
            await RelationshipService(session).get_relationship_state("user")
            await EmotionService(session).get_emotion_state("aevum")
            await LifeService(session).initialize_aevum_life("aevum")
            await PersonalWorldService(session).seed_default_world("aevum")
        except Exception:
            pass

    # Start Proactive autonomous background loop (Phase 5 §8.1)
    proactive_task = None
    if settings.environment != "test":
        import asyncio
        from app.proactive.loop import start_proactive_loop
        proactive_task = asyncio.create_task(start_proactive_loop(interval_seconds=300.0))

    # Start Telegram channel runner if enabled (Phase 7 §10)
    telegram_channel = None
    if settings.environment != "test" and (settings.telegram_enabled or settings.telegram_bot_token):
        try:
            from app.channels.telegram import start_telegram_channel
            telegram_channel = await start_telegram_channel()
        except Exception as tg_init_err:
            import logging
            logging.getLogger(__name__).warning("Telegram channel startup skipped: %s", tg_init_err)

    yield

    # Shutdown: Cleanly cancel background tasks and dispose of database engine
    if telegram_channel is not None:
        try:
            await telegram_channel.stop()
        except Exception:
            pass

    if proactive_task is not None:
        proactive_task.cancel()
        try:
            await proactive_task
        except (asyncio.CancelledError, Exception):
            pass

    await engine.dispose()

    # Write shutdown marker if requested by supervisor or integration test
    marker_file = os.environ.get("AEVUM_SHUTDOWN_MARKER")
    if marker_file:
        try:
            with open(marker_file, "w", encoding="utf-8") as f:
                f.write("disposed_cleanly")
        except Exception:
            pass


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        lifespan=lifespan,
    )

    # Configure CORS for local desktop client communication
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:1420",
            "http://127.0.0.1:1420",
            "http://localhost:1422",
            "http://127.0.0.1:1422",
            "tauri://localhost",
            "http://tauri.localhost",
            "*",
        ],
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(health_router)
    app.include_router(conversations_router)
    app.include_router(character_router)
    app.include_router(genesis_router)
    app.include_router(profile_router)
    app.include_router(desktop_router)
    app.include_router(voice_router)
    app.include_router(call_stream_router)
    app.include_router(sync_router)
    app.include_router(stickers_router)

    return app


app = create_app()
