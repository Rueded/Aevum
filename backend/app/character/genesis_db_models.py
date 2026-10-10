"""SQLAlchemy ORM tables for Phase 17 Character Blueprint & Relationship Genesis.

Persists:
- CharacterBlueprintRecord: Tier A versioned setup blueprint.
- RelationshipGenesisRecord: Tier B genesis baseline origin configuration.
"""

from datetime import datetime
import uuid
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import utc_now
from app.db.session import Base


class CharacterBlueprintRecord(Base):
    """Tier A: Versioned setup configuration for character definition."""

    __tablename__ = "character_blueprints"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    character_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("character_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    identity_summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    lifestyle_rhythm: Mapped[str] = mapped_column(
        String(255),
        default="",
        nullable=False,
    )
    core_traits_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
    )
    communication_style_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
    )
    innate_boundaries_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
    )
    epistemic_seed_topics_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class RelationshipGenesisRecord(Base):
    """Tier B: Initial relationship genesis contract persisted as historical origin metadata."""

    __tablename__ = "relationship_genesis"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    character_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("character_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        default="user",
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    relationship_archetype: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    initial_trust: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    initial_familiarity: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    initial_comfort: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    initial_respect: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.50,
    )
    boundary_sensitivity: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.50,
    )
    genesis_meeting_context: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    initialized_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class CharacterScheduleProfileRecord(Base):
    """Tier A / Life: Persists AI-compiled occupation-tailored schedule, locations, contingencies, and incidents."""

    __tablename__ = "character_schedule_profiles"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    character_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("character_definitions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    occupation: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    lifestyle_rhythm: Mapped[str] = mapped_column(
        String(255),
        default="",
        nullable=False,
    )
    slots_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
    )
    locations_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
    )
    contingencies_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
    )
    micro_incidents_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="{}",
    )
    compiled_by: Mapped[str] = mapped_column(
        String(50),
        default="ai_compiler",
        nullable=False,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

