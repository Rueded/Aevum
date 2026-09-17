"""Lightweight, idempotent SQLite schema migration helpers for Aevum Core.

Ensures newly introduced columns in domain models exist in pre-existing SQLite database
files without requiring a heavy external migration framework or destroying existing data.
"""

import logging
from typing import Any
from sqlalchemy import Connection

logger = logging.getLogger(__name__)

# Mapping of table_name -> list of (column_name, column_sql_definition)
SCHEMA_MIGRATIONS: dict[str, list[tuple[str, str]]] = {
    "memories": [
        ("subject_entity", "VARCHAR NOT NULL DEFAULT 'USER'"),
    ],
    "memory_candidates": [
        ("subject_entity", "VARCHAR NOT NULL DEFAULT 'USER'"),
    ],
    "emotion_events": [
        ("source_life_event_id", "VARCHAR NULL"),
    ],
    "life_events": [
        ("idempotency_key", "VARCHAR(120) NULL"),
    ],
}


def migrate_sqlite_schema(conn: Connection) -> None:
    """Inspect SQLite schema and add any missing columns idempotently."""
    for table_name, columns in SCHEMA_MIGRATIONS.items():
        # Check if table exists in sqlite_master
        table_exists = conn.exec_driver_sql(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=:name",
            {"name": table_name},
        ).scalar()
        if not table_exists:
            continue

        # Fetch existing column names via PRAGMA table_info
        table_info = conn.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()
        existing_cols = {row[1] for row in table_info}

        for col_name, col_def in columns:
            if col_name not in existing_cols:
                logger.info(
                    "Migrating SQLite schema: Adding column '%s' to table '%s'",
                    col_name,
                    table_name,
                )
                conn.exec_driver_sql(
                    f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}"
                )

    # Ensure unique index on life_events.idempotency_key if life_events table exists
    table_exists = conn.exec_driver_sql(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='life_events'"
    ).scalar()
    if table_exists:
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_life_events_idempotency_key ON life_events (idempotency_key)"
        )

