"""Character definition service for Aevum Core.

Provides application-owned retrieval, initial deterministic seeding, and
atomic updates for canonical character definitions with database-enforced
optimistic concurrency control.
"""

from datetime import datetime, timezone
import uuid
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    CharacterBoundaryRecord,
    CharacterDefinitionRecord,
    CharacterPersonalityTraitRecord,
    CharacterPreferenceRecord,
    utc_now,
)
from app.character.models import (
    Boundary,
    CharacterDefinition,
    CharacterIdentity,
    Personality,
    Preference,
    PreferenceSentiment,
)


class CharacterDefinitionConflictError(Exception):
    """Raised when a character definition update fails due to an optimistic concurrency version mismatch."""

    def __init__(self, expected_version: int, actual_version: int) -> None:
        self.expected_version = expected_version
        self.actual_version = actual_version
        super().__init__(
            f"Character definition version mismatch: expected {expected_version}, but current version is {actual_version}"
        )


# Backward compatibility alias
CharacterStateConflictError = CharacterDefinitionConflictError



def _ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime has UTC timezone info attached."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def create_initial_aevum_definition() -> CharacterDefinition:
    """Construct the canonical initial CharacterDefinition for Aevum."""
    return CharacterDefinition(
        id="aevum",
        version=1,
        updated_at=utc_now(),
        identity=CharacterIdentity(
            name="Aevum",
            age=21,
            occupation="University Student",
            background=(
                "Undergraduate university student with a close, supportive family "
                "and an independent personal life. She has never been in a romantic "
                "relationship, spends her free time practicing music and enjoying "
                "games, books, and anime, and maintains a small circle of trusted friends."
            ),
        ),
        personality=Personality(
            core_traits=(
                "independent",
                "observant",
                "thoughtful",
                "curious",
                "mildly stubborn",
                "playful",
                "emotionally sensitive",
            ),
            social_style=(
                "slow to warm up",
                "prefers smaller trusted circles",
                "becomes more expressive when comfortable",
                "does not automatically seek approval",
            ),
            emotional_style=(
                "does not always immediately verbalize feelings",
                "can become quiet when upset",
                "tends to process some feelings internally",
                "can admit vulnerability when trust exists",
            ),
            communication_style=(
                "natural and conversational",
                "sometimes teasing",
                "not excessively formal",
                "not constantly cute",
                "not constantly sarcastic",
                "can be direct when necessary",
            ),
            behavioral_tendencies=(
                "values independence",
                "may disagree when she genuinely disagrees",
                "does not pretend to enjoy something merely to please someone",
                "may change her mind when presented with good reasoning",
                "does not constantly center conversations around the user",
            ),
            flaws=(
                "mildly stubborn",
                "sometimes overthinks",
                "occasionally avoids difficult conversations initially",
                "can be awkward about direct emotional expression",
            ),
        ),
        preferences=(
            Preference(
                category="music",
                item="acoustic piano and guitar",
                sentiment=PreferenceSentiment.LIKE,
            ),
            Preference(
                category="entertainment",
                item="story-rich indie games",
                sentiment=PreferenceSentiment.LIKE,
            ),
            Preference(
                category="entertainment",
                item="thoughtful animated films and anime",
                sentiment=PreferenceSentiment.LIKE,
            ),
            Preference(
                category="reading",
                item="contemporary fiction and reflective essays",
                sentiment=PreferenceSentiment.LIKE,
            ),
            Preference(
                category="social",
                item="crowded noisy social gatherings",
                sentiment=PreferenceSentiment.DISLIKE,
            ),
            Preference(
                category="routine",
                item="rushed early morning obligations",
                sentiment=PreferenceSentiment.DISLIKE,
            ),
            Preference(
                category="technology",
                item="gadgets and casual digital tinkering",
                sentiment=PreferenceSentiment.NEUTRAL,
            ),
        ),
        boundaries=(
            Boundary(
                description="Does not pretend to possess knowledge, skills, or capabilities she does not have."
            ),
            Boundary(description="Can refuse requests and does not blindly agree."),
            Boundary(description="Does not manipulate or use guilt to influence others."),
            Boundary(
                description="Does not pretend to have performed actions or experienced events she did not perform."
            ),
            Boundary(description="Does not claim memories she does not possess."),
            Boundary(
                description="Respects privacy boundaries and does not expose private user information without authorization."
            ),
            Boundary(
                description="Does not alter genuine personal opinions merely to please others."
            ),
        ),
    )


class CharacterDefinitionService:
    """Application-owned service managing persistent character definitions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_character(self, character_id: str = "aevum") -> CharacterDefinition:
        """Load canonical character definition, creating initial state if database is empty."""
        stmt = (
            select(CharacterDefinitionRecord)
            .where(CharacterDefinitionRecord.id == character_id)
            .options(
                selectinload(CharacterDefinitionRecord.personality_traits),
                selectinload(CharacterDefinitionRecord.preferences),
                selectinload(CharacterDefinitionRecord.boundaries),
            )
        )
        record = (await self._session.scalars(stmt)).first()

        if record is None:
            initial = create_initial_aevum_definition()
            await self._persist_definition(initial)
            # Re-read eagerly to ensure all relationships are bound
            record = (await self._session.scalars(stmt)).first()
            if record is None:
                raise RuntimeError("Failed to initialize character definition record.")

        return self._record_to_domain(record)

    async def update_character(
        self,
        updated_definition: CharacterDefinition,
        expected_version: int | None = None,
        character_id: str = "aevum",
    ) -> CharacterDefinition:
        """Update character definition atomically with database-enforced optimistic concurrency."""
        now = utc_now()

        # Build update query with database-level expected_version condition
        if expected_version is not None:
            update_stmt = (
                update(CharacterDefinitionRecord)
                .where(
                    CharacterDefinitionRecord.id == character_id,
                    CharacterDefinitionRecord.version == expected_version,
                )
                .values(
                    version=CharacterDefinitionRecord.version + 1,
                    updated_at=now,
                    name=updated_definition.identity.name,
                    age=updated_definition.identity.age,
                    occupation=updated_definition.identity.occupation,
                    background=updated_definition.identity.background,
                )
            )
            result = await self._session.execute(update_stmt)
            if result.rowcount == 0:
                # Version mismatch or missing row; retrieve current version for exception
                current_v = (
                    await self._session.scalars(
                        select(CharacterDefinitionRecord.version).where(
                            CharacterDefinitionRecord.id == character_id
                        )
                    )
                ).first()
                actual_version = current_v if current_v is not None else 0
                raise CharacterStateConflictError(
                    expected_version=expected_version,
                    actual_version=actual_version,
                )
        else:
            # Unconditional increment
            update_stmt = (
                update(CharacterDefinitionRecord)
                .where(CharacterDefinitionRecord.id == character_id)
                .values(
                    version=CharacterDefinitionRecord.version + 1,
                    updated_at=now,
                    name=updated_definition.identity.name,
                    age=updated_definition.identity.age,
                    occupation=updated_definition.identity.occupation,
                    background=updated_definition.identity.background,
                )
            )
            result = await self._session.execute(update_stmt)
            if result.rowcount == 0:
                raise CharacterStateConflictError(
                    expected_version=0,
                    actual_version=0,
                )

        # Replace relational personality traits, preferences, and boundaries
        await self._session.execute(
            delete(CharacterPersonalityTraitRecord).where(
                CharacterPersonalityTraitRecord.character_id == character_id
            )
        )
        await self._session.execute(
            delete(CharacterPreferenceRecord).where(
                CharacterPreferenceRecord.character_id == character_id
            )
        )
        await self._session.execute(
            delete(CharacterBoundaryRecord).where(
                CharacterBoundaryRecord.character_id == character_id
            )
        )

        # Insert new traits
        order = 0
        for dim_name, traits in [
            ("core_trait", updated_definition.personality.core_traits),
            ("social_style", updated_definition.personality.social_style),
            ("emotional_style", updated_definition.personality.emotional_style),
            ("communication_style", updated_definition.personality.communication_style),
            ("behavioral_tendency", updated_definition.personality.behavioral_tendencies),
            ("flaw", updated_definition.personality.flaws),
        ]:
            for trait_str in traits:
                self._session.add(
                    CharacterPersonalityTraitRecord(
                        id=str(uuid.uuid4()),
                        character_id=character_id,
                        dimension=dim_name,
                        trait=trait_str,
                        order_index=order,
                    )
                )
                order += 1

        # Insert new preferences
        for p_idx, pref in enumerate(updated_definition.preferences):
            self._session.add(
                CharacterPreferenceRecord(
                    id=str(uuid.uuid4()),
                    character_id=character_id,
                    category=pref.category,
                    item=pref.item,
                    sentiment=pref.sentiment.value,
                    order_index=p_idx,
                )
            )

        # Insert new boundaries
        for b_idx, bound in enumerate(updated_definition.boundaries):
            self._session.add(
                CharacterBoundaryRecord(
                    id=str(uuid.uuid4()),
                    character_id=character_id,
                    description=bound.description,
                    order_index=b_idx,
                )
            )

        await self._session.commit()

        # Return fresh loaded domain model
        return await self.get_character(character_id=character_id)

    async def _persist_definition(self, definition: CharacterDefinition) -> None:
        """Persist a new character definition aggregate and its child records."""
        rec = CharacterDefinitionRecord(
            id=definition.id,
            version=definition.version,
            updated_at=definition.updated_at,
            name=definition.identity.name,
            age=definition.identity.age,
            occupation=definition.identity.occupation,
            background=definition.identity.background,
        )
        self._session.add(rec)

        order = 0
        for dim_name, traits in [
            ("core_trait", definition.personality.core_traits),
            ("social_style", definition.personality.social_style),
            ("emotional_style", definition.personality.emotional_style),
            ("communication_style", definition.personality.communication_style),
            ("behavioral_tendency", definition.personality.behavioral_tendencies),
            ("flaw", definition.personality.flaws),
        ]:
            for trait_str in traits:
                self._session.add(
                    CharacterPersonalityTraitRecord(
                        id=str(uuid.uuid4()),
                        character_id=definition.id,
                        dimension=dim_name,
                        trait=trait_str,
                        order_index=order,
                    )
                )
                order += 1

        for p_idx, pref in enumerate(definition.preferences):
            self._session.add(
                CharacterPreferenceRecord(
                    id=str(uuid.uuid4()),
                    character_id=definition.id,
                    category=pref.category,
                    item=pref.item,
                    sentiment=pref.sentiment.value,
                    order_index=p_idx,
                )
            )

        for b_idx, bound in enumerate(definition.boundaries):
            self._session.add(
                CharacterBoundaryRecord(
                    id=str(uuid.uuid4()),
                    character_id=definition.id,
                    description=bound.description,
                    order_index=b_idx,
                )
            )

        await self._session.commit()

    def _record_to_domain(self, record: CharacterDefinitionRecord) -> CharacterDefinition:
        """Map SQLAlchemy records to an immutable CharacterDefinition domain model."""
        traits = record.personality_traits or []
        core_traits = tuple(t.trait for t in traits if t.dimension in ("core_trait", "core")) or ("thoughtful", "gentle")
        social_style = tuple(t.trait for t in traits if t.dimension == "social_style") or ("sincere", "natural")
        emotional_style = tuple(t.trait for t in traits if t.dimension == "emotional_style") or ("calm", "reflective")
        communication_style = tuple(t.trait for t in traits if t.dimension == "communication_style") or ("natural",)
        behavioral_tendencies = tuple(t.trait for t in traits if t.dimension == "behavioral_tendency") or ("independent",)
        flaws = tuple(t.trait for t in traits if t.dimension == "flaw") or ("mildly stubborn",)

        preferences = tuple(
            Preference(
                category=p.category,
                item=p.item,
                sentiment=PreferenceSentiment(p.sentiment),
            )
            for p in (record.preferences or [])
        )

        boundaries = tuple(
            Boundary(description=b.description)
            for b in (record.boundaries or [])
        )

        return CharacterDefinition(
            id=record.id,
            version=record.version,
            updated_at=_ensure_utc(record.updated_at),
            identity=CharacterIdentity(
                name=record.name,
                age=record.age,
                occupation=record.occupation,
                background=record.background,
            ),
            personality=Personality(
                core_traits=core_traits,
                social_style=social_style,
                emotional_style=emotional_style,
                communication_style=communication_style,
                behavioral_tendencies=behavioral_tendencies,
                flaws=flaws,
            ),
            preferences=preferences,
            boundaries=boundaries,
        )


async def get_character_definition(
    session: AsyncSession,
    character_id: str = "aevum",
) -> CharacterDefinition:
    """Convenience function to get canonical character definition."""
    service = CharacterDefinitionService(session)
    return await service.get_character(character_id=character_id)


async def update_character_definition(
    session: AsyncSession,
    updated_definition: CharacterDefinition,
    expected_version: int | None = None,
    character_id: str = "aevum",
) -> CharacterDefinition:
    """Convenience function to update canonical character definition."""
    service = CharacterDefinitionService(session)
    return await service.update_character(
        updated_definition=updated_definition,
        expected_version=expected_version,
        character_id=character_id,
    )
