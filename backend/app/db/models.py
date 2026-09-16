from datetime import datetime, timezone
import enum
from typing import Optional
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

class LifeActivityRecord(Base):
    """Represents a discrete activity in the character's life."""
    __tablename__ = "life_activities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
