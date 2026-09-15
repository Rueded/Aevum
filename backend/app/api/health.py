from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db_session

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    """Structured health check response."""

    status: str
    app: str
    version: str
    database: str


@router.get("/health", response_model=HealthResponse)
async def health_check(
    db: AsyncSession = Depends(get_db_session),
) -> HealthResponse:
    """Verify backend liveness and database connectivity."""
    db_status = "connected"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"unhealthy: {exc!s}"

    overall_status = "ok" if db_status == "connected" else "degraded"

    return HealthResponse(
        status=overall_status,
        app=settings.app_name,
        version=settings.version,
        database=db_status,
    )
