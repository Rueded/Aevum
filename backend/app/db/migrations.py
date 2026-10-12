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
    "application_state": [
        ("active_character_id", "VARCHAR(36) NOT NULL DEFAULT 'aevum'"),
    ],
    "conversations": [
        ("character_id", "VARCHAR(36) NOT NULL DEFAULT 'aevum'"),
    ],
    "memories": [
        ("subject_entity", "VARCHAR NOT NULL DEFAULT 'USER'"),
        ("character_id", "VARCHAR(36) NOT NULL DEFAULT 'aevum'"),
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
    "character_candidate_facts": [
        ("selection_metadata_json", "TEXT NULL"),
    ],
    "character_social_records": [
        ("candidate_id", "VARCHAR(36) NULL"),
        ("role_template_id", "VARCHAR(50) NULL"),
        ("familiarity", "FLOAT NOT NULL DEFAULT 0.05"),
        ("comfort", "FLOAT NOT NULL DEFAULT 0.1"),
        ("respect", "FLOAT NOT NULL DEFAULT 0.5"),
        ("trust", "FLOAT NOT NULL DEFAULT 0.1"),
        ("first_met_at", "DATETIME NULL"),
    ],
    "life_activities": [
        ("goal_id", "VARCHAR(36) NULL"),
    ],
    "life_goals": [
        ("progress_per_completion", "FLOAT NOT NULL DEFAULT 0.1"),
    ],
    "life_plans": [
        ("goal_id", "VARCHAR(36) NULL"),
    ],
    # Phase 16.3: New tables created by Base.metadata.create_all() on startup.
    # These entries are present for future ADD COLUMN migration readiness only.
    "character_facet_appraisals": [],
    "character_facet_preferences": [],
    # Phase 16.4: New table created by Base.metadata.create_all() on startup.
    "character_resurgence_events": [],
    # Phase 17.1: Character blueprints & relationship genesis tables
    "character_blueprints": [],
    "relationship_genesis": [],
    "character_schedule_profiles": [],
    "life_states": [
        ("active_contingency_id", "VARCHAR(100) NULL"),
        ("active_contingency_title", "VARCHAR(200) NULL"),
        ("contingency_expires_at", "DATETIME NULL"),
    ],
    "desktop_user_settings": [
        ("user_country", "VARCHAR(32) NOT NULL DEFAULT 'MY'"),
    ],
    # Cross-turn deception & cognitive grievances table
    "character_deception_grievances": [],
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

