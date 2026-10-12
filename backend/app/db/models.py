from datetime import datetime, timezone
import enum
from typing import Optional
import uuid

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
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
    character_id: Mapped[str] = mapped_column(
        String(36),
        default="aevum",
        nullable=False,
        index=True,
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
    active_character_id: Mapped[str] = mapped_column(
        String(36),
        default="aevum",
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
    emotion_state: Mapped[Optional["EmotionStateRecord"]] = relationship(
        "EmotionStateRecord",
        back_populates="character",
        cascade="all, delete-orphan",
        uselist=False,
    )
    emotion_events: Mapped[list["EmotionEventRecord"]] = relationship(
        "EmotionEventRecord",
        back_populates="character",
        cascade="all, delete-orphan",
        order_by="EmotionEventRecord.created_at.desc()",
    )
    emotion_influences: Mapped[list["EmotionInfluenceRecord"]] = relationship(
        "EmotionInfluenceRecord",
        back_populates="character",
        cascade="all, delete-orphan",
        order_by="EmotionInfluenceRecord.created_at.desc()",
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
    subject_entity: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="USER",
        index=True,
    )
    character_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        default="aevum",
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
    subject_entity: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="USER",
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


class RelationshipRecord(Base):
    """Represents current multidimensional relationship state persisted in SQLite."""

    __tablename__ = "relationships"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default="default",
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        default="user",
        index=True,
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

    # Multidimensional relationship axes (normalized 0.0 - 1.0)
    familiarity: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.05,
    )
    trust: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.20,
    )
    comfort: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.10,
    )
    affection: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.00,
    )
    attachment: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.00,
    )
    respect: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.50,
    )

    experiences: Mapped[list["RelationshipExperienceRecord"]] = relationship(
        "RelationshipExperienceRecord",
        back_populates="relationship",
        cascade="all, delete-orphan",
    )


class RelationshipExperienceRecord(Base):
    """Represents a discrete historical relationship-relevant experience persisted in SQLite."""

    __tablename__ = "relationship_experiences"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    relationship_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("relationships.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    experience_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    significance: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    relationship: Mapped["RelationshipRecord"] = relationship(
        "RelationshipRecord",
        back_populates="experiences",
    )


class EmotionStateRecord(Base):
    """Represents current dominant emotional state persisted in SQLite."""

    __tablename__ = "emotion_states"

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
        default="aevum",
    )
    emotion_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    intensity: Mapped[float] = mapped_column(
        Float,
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

    character: Mapped[Optional["CharacterDefinitionRecord"]] = relationship(
        "CharacterDefinitionRecord",
        back_populates="emotion_state",
    )


class EmotionEventRecord(Base):
    """Represents an emotionally relevant cause or event persisted in SQLite."""

    __tablename__ = "emotion_events"

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
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    summary: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    source_life_event_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("life_events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    emotional_relevance: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    character: Mapped[Optional["CharacterDefinitionRecord"]] = relationship(
        "CharacterDefinitionRecord",
        back_populates="emotion_events",
    )
    influences: Mapped[list["EmotionInfluenceRecord"]] = relationship(
        "EmotionInfluenceRecord",
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="EmotionInfluenceRecord.created_at.desc()",
    )


class EmotionInfluenceRecord(Base):
    """Represents a proposed emotional influence from an event persisted in SQLite."""

    __tablename__ = "emotion_influences"

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
    event_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("emotion_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_emotion: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    direction: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    strength: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    character: Mapped[Optional["CharacterDefinitionRecord"]] = relationship(
        "CharacterDefinitionRecord",
        back_populates="emotion_influences",
    )
    event: Mapped[Optional["EmotionEventRecord"]] = relationship(
        "EmotionEventRecord",
        back_populates="influences",
    )












class LifeStateRecord(Base):
    """Represents the current life state of the character."""
    __tablename__ = "life_states"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default="aevum")
    character_id: Mapped[str] = mapped_column(String(36), nullable=False, default="aevum")
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    
    current_activity: Mapped[str] = mapped_column(String(100), nullable=False)
    current_location: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    active_contingency_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    active_contingency_title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    contingency_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

class LifeActivityRecord(Base):
    """Represents a discrete activity in the character's life."""
    __tablename__ = "life_activities"
    __table_args__ = (
        Index(
            "ix_life_activities_character_ongoing",
            "character_id",
            unique=True,
            sqlite_where=text("status = 'ONGOING'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    goal_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    character_id: Mapped[str] = mapped_column(String(36), nullable=False, default="aevum", index=True)
    activity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    planned_end_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    importance: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

class LifePlanRecord(Base):
    """Represents a planned action or intention."""
    __tablename__ = "life_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    goal_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    character_id: Mapped[str] = mapped_column(String(36), nullable=False, default="aevum", index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    planned_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    planned_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PLANNED", index=True)
    importance: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

class LifeEventRecord(Base):
    """Represents a factual event that occurred in the character's life."""
    __tablename__ = "life_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    character_id: Mapped[str] = mapped_column(String(36), nullable=False, default="aevum", index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    significance: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

class LifeGoalRecord(Base):
    """Represents a personal goal."""
    __tablename__ = "life_goals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    character_id: Mapped[str] = mapped_column(String(36), nullable=False, default="aevum", index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE", index=True)
    importance: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    progress_per_completion: Mapped[float] = mapped_column(Float, nullable=False, default=0.10)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class CharacterBiographyRecord(Base):
    """Represents canonical biographical ground truth for a character."""
    __tablename__ = "character_biography"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    character_id: Mapped[str] = mapped_column(String(36), nullable=False, default="aevum", index=True)
    domain: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ESTABLISHED", index=True)
    canonical_value: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    disclosure_min_trust: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class CharacterSocialRecord(Base):
    """Represents a person in the character's independent social circle."""
    __tablename__ = "character_social_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    character_id: Mapped[str] = mapped_column(String(36), nullable=False, default="aevum", index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    relationship: Mapped[str] = mapped_column(String(100), nullable=False)
    traits: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE", index=True)
    candidate_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    role_template_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    familiarity: Mapped[float] = mapped_column(Float, nullable=False, default=0.05)
    comfort: Mapped[float] = mapped_column(Float, nullable=False, default=0.10)
    respect: Mapped[float] = mapped_column(Float, nullable=False, default=0.50)
    trust: Mapped[float] = mapped_column(Float, nullable=False, default=0.10)
    first_met_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_mentioned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class CharacterWorldFactRecord(Base):
    """Represents factual preferences, world knowledge, and tastes owned by the character."""
    __tablename__ = "character_world_facts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    character_id: Mapped[str] = mapped_column(String(36), nullable=False, default="aevum", index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    item: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    importance: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class PermissionRecord(Base):
    """Represents local system capability grant or denial (default least privilege)."""
    __tablename__ = "system_permissions"

    capability: Mapped[str] = mapped_column(String(50), primary_key=True)
    is_granted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    granted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class CharacterCoreFactRecord(Base):
    """Represents a persistent Character Core reality fact with strict provenance and authority."""
    __tablename__ = "character_core_facts"
    __table_args__ = (
        UniqueConstraint("character_id", "fact_key", name="uq_character_core_fact_character_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    character_id: Mapped[str] = mapped_column(String(36), nullable=False, default="aevum", index=True)
    fact_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    authority: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class CharacterRealityRevisionRecord(Base):
    """Represents a historical or current versioned revision of a reality fact."""
    __tablename__ = "character_reality_revisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    character_id: Mapped[str] = mapped_column(String(36), nullable=False, default="aevum", index=True)
    fact_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    effective_from: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    effective_until: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    supersedes_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    superseded_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class CharacterPhysiologicalRecord(Base):
    """Represents current physiological state (energy, fatigue, stress, sleep pressure) persisted in SQLite."""
    __tablename__ = "character_physiological_states"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default="aevum")
    character_id: Mapped[str] = mapped_column(String(36), nullable=False, default="aevum", unique=True, index=True)
    energy: Mapped[float] = mapped_column(Float, nullable=False, default=0.75)
    fatigue: Mapped[float] = mapped_column(Float, nullable=False, default=0.15)
    stress: Mapped[float] = mapped_column(Float, nullable=False, default=0.15)
    sleep_pressure: Mapped[float] = mapped_column(Float, nullable=False, default=0.20)
    qualitative_band: Mapped[str] = mapped_column(String(30), nullable=False, default="STEADY")
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class StateTransitionAuditRecord(Base):
    """Represents an immutable provenance audit record for physiological state transitions."""
    __tablename__ = "state_transition_audit"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    character_id: Mapped[str] = mapped_column(String(36), nullable=False, default="aevum", index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    activity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    time_interval_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    circadian_modifier: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rule_id: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    before_state_json: Mapped[str] = mapped_column(Text, nullable=False)
    after_state_json: Mapped[str] = mapped_column(Text, nullable=False)
    delta_json: Mapped[str] = mapped_column(Text, nullable=False)


class SocialCandidateRecord(Base):
    """Represents a provisional candidate entity accumulating encounter evidence prior to canonical promotion."""
    __tablename__ = "social_candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    character_id: Mapped[str] = mapped_column(String(36), nullable=False, default="aevum", index=True)
    role_template_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    identity_state: Mapped[str] = mapped_column(String(50), nullable=False, default="ANONYMOUS", index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PROVISIONAL", index=True)
    first_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    encounter_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    provisional_familiarity: Mapped[float] = mapped_column(Float, nullable=False, default=0.05)
    provisional_comfort: Mapped[float] = mapped_column(Float, nullable=False, default=0.10)
    provisional_respect: Mapped[float] = mapped_column(Float, nullable=False, default=0.50)
    provisional_trust: Mapped[float] = mapped_column(Float, nullable=False, default=0.10)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class SocialEncounterRecord(Base):
    """Represents an immutable, factual record of a social encounter in the simulation."""
    __tablename__ = "social_encounters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    character_id: Mapped[str] = mapped_column(String(36), nullable=False, default="aevum", index=True)
    candidate_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    contact_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    activity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    location: Mapped[str] = mapped_column(String(100), nullable=False)
    encounter_type: Mapped[str] = mapped_column(String(50), nullable=False)
    interaction_depth: Mapped[str] = mapped_column(String(50), nullable=False)
    valence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    observed_summary: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class NPCFactRecord(Base):
    """Represents an append-only canonical fact about an NPC with explicit supersession support."""
    __tablename__ = "npc_facts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    npc_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    fact_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    fact_value: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE", index=True)
    supersedes_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    superseded_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    source_encounter_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    effective_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    established_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class DesktopUserSettingsRecord(Base):
    """User configuration and privacy boundaries for desktop integration (Phase 8)."""

    __tablename__ = "desktop_user_settings"

    character_id: Mapped[str] = mapped_column(String(36), primary_key=True, default="aevum")
    proactive_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="Asia/Shanghai")
    quiet_hours_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    quiet_hours_start: Mapped[str] = mapped_column(String(10), nullable=False, default="23:00")
    quiet_hours_end: Mapped[str] = mapped_column(String(10), nullable=False, default="08:00")
    max_daily_reach_outs: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    min_cooldown_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    idle_awareness_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    idle_threshold_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    user_country: Mapped[str] = mapped_column(String(32), nullable=False, default="MY", server_default="MY")
    sleep_realism_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    dnd_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class ProactiveNotificationRecord(Base):
    """Represents a proactive reach-out notification and its lifecycle (Phase 8)."""

    __tablename__ = "proactive_notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    character_id: Mapped[str] = mapped_column(String(36), nullable=False, default="aevum", index=True)
    conversation_message_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING", index=True)
    claimed_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    suppression_reason: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    context_metadata: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    interacted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class CharacterCandidateFactRecord(Base):
    """Represents a persistent unconfirmed reality hypothesis (Phase 7D.1).
    
    Hard invariant: Candidate facts are non-canonical and are NEVER directly
    read by CharacterCoreService as canonical truth.
    """

    __tablename__ = "character_candidate_facts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    character_id: Mapped[str] = mapped_column(String(36), nullable=False, default="aevum", index=True)
    slot_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    reality_taxonomy: Mapped[str] = mapped_column(String(50), nullable=False, default="SIMULATED_BIOGRAPHY_FACT")
    inference_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    inference_edge_type: Mapped[str] = mapped_column(String(50), nullable=False, default="DIRECT_ATTRIBUTE")
    lifecycle_state: Mapped[str] = mapped_column(String(30), nullable=False, default="PERSISTED", index=True)
    is_quarantined: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    quarantine_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    composite_plausibility: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    plausibility_json: Mapped[str] = mapped_column(Text, nullable=False)
    provenance_json: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_family_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    supersedes_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    superseded_by_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
    stale_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    selection_metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class EvidenceFamilyRecord(Base):
    """Represents a persistent evidence family tracking source independence (Phase 7D.1).

    Hard invariant: Different sessions != independent evidence.
    Repeated user assertions share the same family and have independent_evidence_weight = 1.
    """

    __tablename__ = "evidence_families"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    cluster_key: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
    mention_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    session_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    first_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    last_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class CharacterChoiceRecord(Base):
    """Represents persistent structured provenance for character choice decisions (Phase 7D.2).

    Hard Invariants:
    - Choice decisions are NON-CANONICAL reality records.
    - Zero modification of character_core_facts.
    - Captures complete multi-attribute factor inputs, contributions, and unselected alternatives.
    """

    __tablename__ = "character_choice_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    character_id: Mapped[str] = mapped_column(String(36), nullable=False, default="aevum", index=True)
    slot_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    candidate_set_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    selected_candidate_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    unselected_candidate_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    decision_model_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")
    competition_state: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    competition_margin: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    choice_margin: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rationale_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    rationale_description: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    plausibility_scores_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    factor_inputs_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    factor_contributions_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    choice_scores_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    provenance_references_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)


class CharacterBiographyPromotionRecord(Base):
    """Represents persistent structured audit record for autonomous biography promotion (Phase 7D.3).

    Hard Invariants:
    - Authoritative record proving candidate promotion into canonical reality.
    - Captures candidate ID, choice decision ID, policy version, and full gate results.
    """

    __tablename__ = "character_biography_promotions"
    __table_args__ = (
        UniqueConstraint("character_id", "slot_name", "candidate_id", name="uq_char_bio_promotion_candidate"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    character_id: Mapped[str] = mapped_column(String(36), nullable=False, default="aevum", index=True)
    slot_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    candidate_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    choice_decision_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    promoted_value_json: Mapped[str] = mapped_column(Text, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")
    decision_model_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")
    previous_canonical_state_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_canonical_state_json: Mapped[str] = mapped_column(Text, nullable=False)
    gates_passed_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    provenance_references_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    authorization_code: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)


class CharacterDeceptionGrievanceRecord(Base):
    """Represents persistent cognitive grievance record for deception verification and confrontation.

    Tracks cross-turn hoaxes, confessions, and background verification findings.
    Lifecycle: SUSPECTED -> VERIFYING -> VERIFIED_DECEPTION -> CONFRONTED -> RECONCILING -> RESOLVED.
    """

    __tablename__ = "character_deception_grievances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    character_id: Mapped[str] = mapped_column(String(36), nullable=False, default="aevum", index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, default="user", index=True)
    claimed_assertion: Mapped[str] = mapped_column(Text, nullable=False)
    verified_truth: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    topic_domain: Mapped[str] = mapped_column(String(50), nullable=False, default="general")
    deception_type: Mapped[str] = mapped_column(String(50), nullable=False, default="OUTRAGEOUS_CLAIM")
    stage: Mapped[str] = mapped_column(String(50), nullable=False, default="VERIFIED_DECEPTION", index=True)
    emotional_tone: Mapped[str] = mapped_column(String(50), nullable=False, default="playful_indignant")
    confrontation_hint: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    confronted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
