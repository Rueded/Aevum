import os
import shutil
import sqlite3
import logging
from fastapi import APIRouter, Depends, HTTPException, Header, UploadFile, File
from fastapi.responses import FileResponse
from app.db.session import engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["Sync"])

DB_PATH = "aevum.db"


def verify_sync_auth(x_sync_key: str = Header(...)) -> bool:
    expected_key = os.environ.get("GEMINI_API_KEY")
    if not expected_key or x_sync_key.strip() != expected_key.strip():
        raise HTTPException(status_code=401, detail="Unauthorized: invalid sync authorization key")
    return True


@router.post("/upload-database")
async def upload_database(
    file: UploadFile = File(...),
    _: bool = Depends(verify_sync_auth),
):
    """Securely upload and restore database from local PC to cloud."""
    temp_path = "aevum_temp.db"
    try:
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Verify it is a valid SQLite database with message records
        con = sqlite3.connect(temp_path)
        cur = con.cursor()
        cur.execute("SELECT count(*) FROM messages")
        count = cur.fetchone()[0]
        con.close()
    except Exception as exc:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=400, detail=f"Invalid database file: {exc}")

    # Dispose existing SQLAlchemy engine connections before swapping file
    await engine.dispose()

    # Clean up stale journal/wal locks
    for ext in ["aevum.db-wal", "aevum.db-shm", "aevum.db-journal"]:
        if os.path.exists(ext):
            try:
                os.remove(ext)
            except Exception as e:
                logger.warning("Could not remove stale %s: %s", ext, e)

    shutil.move(temp_path, DB_PATH)
    logger.info("Database successfully synchronized with %d messages.", count)
    return {"status": "ok", "message": f"Successfully synced database with {count} messages"}


@router.get("/download-database")
async def download_database(_: bool = Depends(verify_sync_auth)):
    """Securely download the latest cloud database back to local PC."""
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Database file not found")

    # Flush WAL into main database file
    try:
        con = sqlite3.connect(DB_PATH)
        con.execute("PRAGMA wal_checkpoint(FULL);")
        con.close()
    except Exception as exc:
        logger.warning("WAL checkpoint before download failed: %s", exc)

    return FileResponse(DB_PATH, filename="aevum.db", media_type="application/x-sqlite3")
