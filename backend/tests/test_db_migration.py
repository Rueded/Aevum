import pytest
import sqlite3
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.session import init_db
from app.db.migrations import migrate_sqlite_schema


@pytest.mark.asyncio
async def test_sqlite_migration_on_old_schema(tmp_path):
    """Verify that an old SQLite database missing new columns is migrated safely and idempotently."""
    db_file = tmp_path / "old_schema.db"
    
    # 1. Create SQLite database with old table schemas
    raw_conn = sqlite3.connect(str(db_file))
    raw_conn.execute("""
        CREATE TABLE memories (
            id VARCHAR PRIMARY KEY,
            category VARCHAR NOT NULL,
            content TEXT NOT NULL,
            importance FLOAT NOT NULL,
            confidence FLOAT NOT NULL,
            emotional_weight FLOAT NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            last_recalled DATETIME,
            times_recalled INTEGER NOT NULL,
            version INTEGER NOT NULL
        )
    """)
    raw_conn.execute("""
        CREATE TABLE memory_candidates (
            id VARCHAR PRIMARY KEY,
            category VARCHAR NOT NULL,
            content TEXT NOT NULL,
            importance FLOAT NOT NULL,
            confidence FLOAT NOT NULL,
            emotional_weight FLOAT NOT NULL,
            status VARCHAR NOT NULL,
            source_type VARCHAR NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            version INTEGER NOT NULL
        )
    """)
    raw_conn.execute("""
        CREATE TABLE emotion_events (
            id VARCHAR PRIMARY KEY,
            character_id VARCHAR NOT NULL,
            event_type VARCHAR NOT NULL,
            valence FLOAT NOT NULL,
            arousal FLOAT NOT NULL,
            description VARCHAR NOT NULL,
            occurred_at DATETIME NOT NULL
        )
    """)

    # Insert existing data
    raw_conn.execute("""
        INSERT INTO memories (id, category, content, importance, confidence, emotional_weight, created_at, updated_at, times_recalled, version)
        VALUES ('mem-1', 'FACT', 'Existing memory content', 0.8, 0.9, 0.0, '2026-09-01 10:00:00', '2026-09-01 10:00:00', 1, 1)
    """)
    raw_conn.execute("""
        INSERT INTO memory_candidates (id, category, content, importance, confidence, emotional_weight, status, source_type, created_at, updated_at, version)
        VALUES ('cand-1', 'PREFERENCE', 'Existing candidate', 0.5, 0.7, 0.1, 'PENDING', 'MANUAL', '2026-09-01 10:00:00', '2026-09-01 10:00:00', 1)
    """)
    raw_conn.execute("""
        INSERT INTO emotion_events (id, character_id, event_type, valence, arousal, description, occurred_at)
        VALUES ('ev-1', 'aevum', 'INTERACTION', 0.2, 0.1, 'Conversation event', '2026-09-01 10:00:00')
    """)
    raw_conn.commit()
    raw_conn.close()

    # 2. Run init_db with the engine pointing to this old database
    async_engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    await init_db(async_engine)

    # 3. Verify columns now exist and data is preserved
    verify_conn = sqlite3.connect(str(db_file))
    
    mem_cols = [row[1] for row in verify_conn.execute("PRAGMA table_info(memories)").fetchall()]
    assert "subject_entity" in mem_cols
    
    cand_cols = [row[1] for row in verify_conn.execute("PRAGMA table_info(memory_candidates)").fetchall()]
    assert "subject_entity" in cand_cols

    event_cols = [row[1] for row in verify_conn.execute("PRAGMA table_info(emotion_events)").fetchall()]
    assert "source_life_event_id" in event_cols

    # Check preserved records
    row_mem = verify_conn.execute("SELECT id, content, subject_entity FROM memories WHERE id='mem-1'").fetchone()
    assert row_mem is not None
    assert row_mem[0] == "mem-1"
    assert row_mem[1] == "Existing memory content"
    assert row_mem[2] == "USER"  # Default value assigned

    row_cand = verify_conn.execute("SELECT id, content, subject_entity FROM memory_candidates WHERE id='cand-1'").fetchone()
    assert row_cand is not None
    assert row_cand[2] == "USER"

    row_ev = verify_conn.execute("SELECT id, source_life_event_id FROM emotion_events WHERE id='ev-1'").fetchone()
    assert row_ev is not None
    assert row_ev[1] is None  # Nullable column

    verify_conn.close()

    # 4. Run init_db a second time to ensure idempotency
    await init_db(async_engine)
    await async_engine.dispose()
