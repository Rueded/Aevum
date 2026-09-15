from datetime import datetime, timezone
import enum
import uuid

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class MessageRole(str, enum.Enum):
    """Permitted roles for persisted conversation messages."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


class Conversation(Base):
    """Represents a persistent conversation session."""

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
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

    # Relationship to messages, ordered chronologically
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at.asc()",
    )


class Message(Base):
    """Represents a single persisted message within a conversation."""

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationship back to conversation
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages",
    )


class ApplicationStateRecord(Base):
    """Represents canonical application state persisted in the database."""

    __tablename__ = "application_state"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default="canonical",
    )
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class CharacterDefinitionRecord(Base):
    """Represents canonical character identity and metadata persisted in SQLite."""

    __tablename__ = "character_definitions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default="aevum",
    )
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    # Character Identity fields
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    age: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    occupation: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    background: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Relational associations
    personality_traits: Mapped[list["CharacterPersonalityTraitRecord"]] = relationship(
        "CharacterPersonalityTraitRecord",
        back_populates="character",
        cascade="all, delete-orphan",
        order_by="CharacterPersonalityTraitRecord.order_index.asc()",
    )
    preferences: Mapped[list["CharacterPreferenceRecord"]] = relationship(
        "CharacterPreferenceRecord",
        back_populates="character",
        cascade="all, delete-orphan",
        order_by="CharacterPreferenceRecord.order_index.asc()",
    )
    boundaries: Mapped[list["CharacterBoundaryRecord"]] = relationship(
        "CharacterBoundaryRecord",
        back_populates="character",
        cascade="all, delete-orphan",
        order_by="CharacterBoundaryRecord.order_index.asc()",
    )


class CharacterPersonalityTraitRecord(Base):
    """Represents a specific personality trait or tendency in a given dimension."""

    __tablename__ = "character_personality_traits"

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
    dimension: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    trait: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    order_index: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    character: Mapped["CharacterDefinitionRecord"] = relationship(
        "CharacterDefinitionRecord",
        back_populates="personality_traits",
    )


class CharacterPreferenceRecord(Base):
    """Represents a character preference (like, dislike, neutral)."""

    __tablename__ = "character_preferences"

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
    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    item: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    sentiment: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    order_index: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    character: Mapped["CharacterDefinitionRecord"] = relationship(
        "CharacterDefinitionRecord",
        back_populates="preferences",
    )


class CharacterBoundaryRecord(Base):
    """Represents a character behavioral boundary."""

    __tablename__ = "character_boundaries"

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
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    order_index: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    character: Mapped["CharacterDefinitionRecord"] = relationship(
        "CharacterDefinitionRecord",
        back_populates="boundaries",
    )


class CharacterStateRecord(Base):
    """Represents current mutable character state persisted in SQLite."""

    __tablename__ = "character_states"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default="aevum",
    )
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    # Qualitative mood
    mood: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    # Continuous physiological/cognitive state indicators (normalized 0.0 - 1.0)
    energy: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    stress: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    social_energy: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    irritation: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    loneliness: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    # Situational context
    current_activity: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    current_location: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )


class MemoryRecord(Base):
    """Represents a structured long-term memory record persisted in SQLite."""

    __tablename__ = "memories"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    category: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    importance: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.5,
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.9,
    )
    emotional_weight: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
        index=True,
    )
    last_recalled: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
    times_recalled: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    embeddings: Mapped[list["MemoryEmbeddingRecord"]] = relationship(
        "MemoryEmbeddingRecord",
        back_populates="memory",
        cascade="all, delete-orphan",
    )


class MemoryCandidateRecord(Base):

    """Represents a memory candidate awaiting curation persisted in SQLite."""

    __tablename__ = "memory_candidates"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    category: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    importance: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.5,
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.9,
    )
    emotional_weight: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PENDING",
        index=True,
    )
    source_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="MANUAL",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )


class MemoryEmbeddingRecord(Base):
    """Represents a persistent vector embedding for a long-term memory record."""

    __tablename__ = "memory_embeddings"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    memory_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("memories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )
    dimensions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    vector_json: Mapped[str] = mapped_column(
        Text,
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
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    memory: Mapped["MemoryRecord"] = relationship(
        "MemoryRecord",
        back_populates="embeddings",
    )






