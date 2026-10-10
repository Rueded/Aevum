from collections.abc import AsyncGenerator
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings
from app.db.migrations import migrate_sqlite_schema


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy declarative models in Aevum Core."""
    pass


# SQLite-specific connection arguments for concurrency resilience
connect_args: dict = {}
if "sqlite" in settings.database_url:
    connect_args = {
        "timeout": 60.0,
        "check_same_thread": False,
    }

# Initialize async engine for SQLite (using aiosqlite driver)
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    connect_args=connect_args,
)

# Automatically configure WAL mode, busy timeout, and normal synchronous mode for SQLite
if "sqlite" in settings.database_url:
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=60000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

# Async session factory
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


def _safe_create_all(connection) -> None:
    # Ensure all models are registered on Base.metadata
    import app.db.models  # noqa: F401
    import app.growth.growth_db_models  # noqa: F401
    import app.character.genesis_db_models  # noqa: F401

    try:
        Base.metadata.create_all(connection, checkfirst=True)
    except Exception as e:
        if "already exists" in str(e).lower():
            pass
        else:
            raise


async def init_db(engine_to_use: AsyncEngine | None = None) -> None:
    """Initialize database tables according to declarative metadata and migrate missing columns."""
    target_engine = engine_to_use or engine
    async with target_engine.begin() as conn:
        if "sqlite" in str(target_engine.url):
            await conn.execute(text("PRAGMA journal_mode=WAL;"))
            await conn.execute(text("PRAGMA busy_timeout=60000;"))
        await conn.run_sync(_safe_create_all)
        await conn.run_sync(migrate_sqlite_schema)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency provider for FastAPI route handlers to obtain a database session."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()

