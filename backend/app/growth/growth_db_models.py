"""SQLAlchemy declarative models for Phase 16 Personal Learning & Growth.

Defines tables for:
- character_experiences: Append-only immutable log of experiential events (Phase 16.1).
- character_interest_domains: Domain registration and exposure tracking (Phase 16.1).
- character_interest_facets: Multi-dimensional sub-facet tracking (Phase 16.1).
- character_facet_appraisals: Append-only immutable episodic appraisal log (Phase 16.3).
- character_facet_preferences: Mutable materialized preference projection (Phase 16.3).
- character_resurgence_events: Append-only immutable resurgence activation log (Phase 16.4).

Immutability note:
- character_experiences, character_facet_appraisals, character_resurgence_events:
  ORM events block UPDATE/DELETE.
- character_facet_preferences: mutable derived state; NO ORM immutability events.
  It is a deterministic projection of character_facet_appraisals — not source of truth.
"""

from datetime import datetime, timezone
import uuid
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.growth.experiential_models import ExperienceMutationProhibitedError


def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


class CharacterExperienceTable(Base):
    """Immutable, append-only log of discrete experiential events.

    Hard Invariants:
    - Never updated.
    - Never deleted.
    - timeline_tick is the authoritative cognitive clock anchor (Phase 8C).
    - created_at is database persistence metadata only.
    """

    __tablename__ = "character_experiences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    character_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("character_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    domain_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    facet_key: Mapped[str] = mapped_column(String(64), nullable=False)
    provenance_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    exposure_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    calendar_session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    timeline_tick: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    interaction_evidence_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    qualia_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_fictional_frame: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class CharacterInterestDomainTable(Base):
    """Interest domain registration container.

    Hard Invariants:
    - Unique per (character_id, domain_key).
    - Represents interest presence/exposure, NOT preference or affinity.
    """

    __tablename__ = "character_interest_domains"
    __table_args__ = (
        UniqueConstraint("character_id", "domain_key", name="uq_char_interest_domain"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    character_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("character_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    domain_key: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    exposure_state: Mapped[str] = mapped_column(String(32), nullable=False, default="UNEXPOSED")
    created_at_tick: Mapped[int] = mapped_column(Integer, nullable=False)


class CharacterInterestFacetTable(Base):
    """Sub-facet container under an interest domain.

    Hard Invariants:
    - Unique per (character_id, domain_key, facet_key).
    - Captures multi-dimensional facets (music, exploration, combat).
    """

    __tablename__ = "character_interest_facets"
    __table_args__ = (
        UniqueConstraint("character_id", "domain_key", "facet_key", name="uq_char_interest_facet"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    character_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("character_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    domain_key: Mapped[str] = mapped_column(String(64), nullable=False)
    facet_key: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    experience_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    familiarity_level: Mapped[str] = mapped_column(String(32), nullable=False, default="UNAWARE")
    last_experienced_tick: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


# ─────────────────────────────────────────────────────────────────────────────
# ORM-Level Immutability Enforcement (Blocker 1)
# ─────────────────────────────────────────────────────────────────────────────

@event.listens_for(CharacterExperienceTable, "before_update")
def _block_character_experience_update(mapper, connection, target):
    """Intercept and reject any UPDATE operation on CharacterExperienceTable."""
    raise ExperienceMutationProhibitedError(
        f"Cannot update CharacterExperienceTable record '{target.id}': experiences are immutable event logs."
    )


@event.listens_for(CharacterExperienceTable, "before_delete")
def _block_character_experience_delete(mapper, connection, target):
    """Intercept and reject any DELETE operation on CharacterExperienceTable."""
    raise ExperienceMutationProhibitedError(
        f"Cannot delete CharacterExperienceTable record '{target.id}': experiences are append-only event logs."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Phase 16.3 Tables
# ─────────────────────────────────────────────────────────────────────────────

# Define inline to avoid circular import (appraisal_models imports from here)
class AppraisalMutationProhibitedError(Exception):
    """Raised when an UPDATE or DELETE is attempted on character_facet_appraisals (immutable log)."""
    pass



class CharacterFacetAppraisalTable(Base):
    """Append-only, immutable log of episodic facet appraisals (Phase 16.3).

    Hard Invariants:
    - Never updated. Never deleted. (ORM event listeners enforce this.)
    - timeline_tick = experience.timeline_tick (set by FacetAppraisalEngine; non-configurable).
    - UNIQUE(experience_id, facet_key): One experience x one facet -> one authoritative appraisal. (Req 8)
    - Source of truth: character_preferences is a materialized projection of this table. (Req 7)
    - calendar_session_id stored for distinct-session aggregation in PreferenceFormationService.
    """

    __tablename__ = "character_facet_appraisals"
    __table_args__ = (
        UniqueConstraint("experience_id", "facet_key", name="uq_appraisal_experience_facet"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    character_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("character_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    domain_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    facet_key: Mapped[str] = mapped_column(String(64), nullable=False)
    experience_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("character_experiences.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    appraisal_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_id: Mapped[str] = mapped_column(String(128), nullable=False)
    grounded_signal: Mapped[str] = mapped_column(String(64), nullable=False)
    calendar_session_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    timeline_tick: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class CharacterPreferenceTable(Base):
    """Mutable materialized preference projection for (character, domain, facet) triples (Phase 16.3).

    Hard Invariants:
    - UNIQUE(character_id, domain_key, facet_key): one preference row per facet per character.
    - Updated deterministically via upsert; result is idempotent on the same appraisal stream. (Req 12)
    - NOT the source of truth: character_facet_appraisals is the source of truth.
    - NO ORM immutability events: this table IS the mutable derived state (unlike character_facet_appraisals).
    - MIXED_AMBIVALENT preference_polarity is always paired with StabilityTier.TENTATIVE. (Blocker 4)
    """

    __tablename__ = "character_facet_preferences"
    __table_args__ = (
        UniqueConstraint("character_id", "domain_key", "facet_key", name="uq_char_facet_pref"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    character_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("character_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    domain_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    facet_key: Mapped[str] = mapped_column(String(64), nullable=False)
    preference_polarity: Mapped[str] = mapped_column(String(32), nullable=False, default="UNFORMED")
    stability_tier: Mapped[str] = mapped_column(String(32), nullable=False, default="UNFORMED")
    revision_kind: Mapped[str] = mapped_column(String(48), nullable=False, default="NONE")
    appraisal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    distinct_session_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_evaluated_tick: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 16.3 ORM Immutability — character_facet_appraisals ONLY
# character_preferences has NO immutability events (it is mutable derived state)
# ─────────────────────────────────────────────────────────────────────────────

@event.listens_for(CharacterFacetAppraisalTable, "before_update")
def _block_appraisal_update(mapper, connection, target):
    """Intercept and reject any UPDATE operation on CharacterFacetAppraisalTable."""
    raise AppraisalMutationProhibitedError(
        f"Cannot update CharacterFacetAppraisalTable record '{target.id}': appraisals are immutable event logs."
    )


@event.listens_for(CharacterFacetAppraisalTable, "before_delete")
def _block_appraisal_delete(mapper, connection, target):
    """Intercept and reject any DELETE operation on CharacterFacetAppraisalTable."""
    raise AppraisalMutationProhibitedError(
        f"Cannot delete CharacterFacetAppraisalTable record '{target.id}': appraisals are append-only event logs."
    )



# ─────────────────────────────────────────────────────────────────────────────
# Phase 16.4 Table
# ─────────────────────────────────────────────────────────────────────────────

class ResurgenceMutationProhibitedError(Exception):
    """Raised when an UPDATE or DELETE is attempted on character_resurgence_events (immutable log)."""
    pass


class CharacterResurgenceEventTable(Base):
    """Append-only, immutable log of interest domain resurgence activations (Phase 16.4).

    Hard Invariants (Lock 13 / GC-416):
    - Never updated. Never deleted. (ORM event listeners enforce this.)
    - One row = one ResurgenceEvent (awakenment of DORMANT domain; SATIATED recovers via cooldown only).
    - Creates NO experience records, appraisals, or preference mutations.
    - stimulus_ref must be non-empty and use a valid, authorized prefix.
    - timeline_tick = Phase 8C canonical tick (wall-clock never used; Lock 11 / GC-414).
    """

    __tablename__ = "character_resurgence_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    character_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("character_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    domain_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    trigger_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    stimulus_ref: Mapped[str] = mapped_column(Text, nullable=False)
    timeline_tick: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    awakened_facet_key: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    reflection_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 16.4 ORM Immutability — character_resurgence_events
# ─────────────────────────────────────────────────────────────────────────────

@event.listens_for(CharacterResurgenceEventTable, "before_update")
def _block_resurgence_update(mapper, connection, target):
    """Intercept and reject any UPDATE operation on CharacterResurgenceEventTable."""
    raise ResurgenceMutationProhibitedError(
        f"Cannot update CharacterResurgenceEventTable record '{target.id}': resurgence events are immutable."
    )


@event.listens_for(CharacterResurgenceEventTable, "before_delete")
def _block_resurgence_delete(mapper, connection, target):
    """Intercept and reject any DELETE operation on CharacterResurgenceEventTable."""
    raise ResurgenceMutationProhibitedError(
        f"Cannot delete CharacterResurgenceEventTable record '{target.id}': resurgence events are append-only."
    )
