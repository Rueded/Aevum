from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy declarative models in Aevum Core."""
    pass


# Initialize async engine for SQLite (using aiosqlite driver)
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
)

# Async session factory
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db(engine_to_use: AsyncEngine | None = None) -> None:
    """Initialize database tables according to declarative metadata."""
    target_engine = engine_to_use or engine
    async with target_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency provider for FastAPI route handlers to obtain a database session."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()

