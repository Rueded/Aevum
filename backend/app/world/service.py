"""Service layer for Personal World, Biography, and Epistemic Grounding."""

import logging
from typing import Optional, Sequence
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    CharacterBiographyRecord,
    CharacterSocialRecord,
    CharacterWorldFactRecord,
    utc_now,
)
from app.world.epistemic_resolver import EpistemicResolver
from app.world.models import (
    BiographyFact,
    FactEpistemicStatus,
    PersonalWorldContext,
    SocialContact,
    WorldFact,
)

logger = logging.getLogger(__name__)


class PersonalWorldService:
    """Repository and orchestration service for character biographical and personal world state."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def seed_default_world(self, character_id: str = "aevum") -> None:
        """Seed canonical personal world truth if no records exist."""
        res = await self._session.execute(
            select(CharacterBiographyRecord).where(CharacterBiographyRecord.character_id == character_id)
        )
        existing = res.scalars().first()
        if existing is not None:
            return

        logger.info("Seeding canonical personal world records for character '%s'", character_id)

        # Canonical Biography Records
        # Authoritative Grounded Biography Records
        bios = [
            CharacterBiographyRecord(
                character_id=character_id,
                domain="education",
                subject="studies",
                status=FactEpistemicStatus.ESTABLISHED.value,
                canonical_value="Undergraduate university student with an independent personal life.",
                confidence=1.0,
                disclosure_min_trust=0.0,
            ),
            CharacterBiographyRecord(
                character_id=character_id,
                domain="family",
                subject="family",
                status=FactEpistemicStatus.ESTABLISHED.value,
                canonical_value="Grew up in a close, supportive family environment.",
                confidence=1.0,
                disclosure_min_trust=0.0,
            ),
            CharacterBiographyRecord(
                character_id=character_id,
                domain="relationship",
                subject="romantic_history",
                status=FactEpistemicStatus.NONEXISTENT.value,
                canonical_value="Has never been in a romantic relationship; has no ex-partners or past romantic history.",
                confidence=1.0,
                disclosure_min_trust=0.0,
            ),
            CharacterBiographyRecord(
                character_id=character_id,
                domain="personal",
                subject="pets",
                status=FactEpistemicStatus.NONEXISTENT.value,
                canonical_value="Does not currently own any pets.",
                confidence=1.0,
                disclosure_min_trust=0.0,
            ),
            CharacterBiographyRecord(
                character_id=character_id,
                domain="nature",
                subject="supernatural_powers",
                status=FactEpistemicStatus.NONEXISTENT.value,
                canonical_value="Mortal human with realistic physical capabilities; possesses no magic, superpowers, or sci-fi abilities.",
                confidence=1.0,
                disclosure_min_trust=0.0,
            ),
            CharacterBiographyRecord(
                character_id=character_id,
                domain="family",
                subject="distant_ancestry",
                status=FactEpistemicStatus.UNKNOWN.value,
                canonical_value="Details regarding family lineage beyond her immediate knowledge are unrecorded.",
                confidence=1.0,
                disclosure_min_trust=0.0,
            ),
        ]
        self._session.add_all(bios)

        # Canonical Social Contacts (Default empty unless explicitly configured by user/designer)
        socials: list[CharacterSocialRecord] = []
        if socials:
            self._session.add_all(socials)

        # Canonical World Facts (Directly derived from Aevum's canonical preferences)
        world_facts = [
            CharacterWorldFactRecord(
                character_id=character_id,
                category="music",
                item="acoustic_piano_and_guitar",
                details="Enjoys practicing and listening to acoustic piano and guitar.",
                importance=0.9,
            ),
            CharacterWorldFactRecord(
                character_id=character_id,
                category="entertainment",
                item="story_rich_indie_games",
                details="Appreciates story-rich indie games with depth and emotional resonance.",
                importance=0.9,
            ),
            CharacterWorldFactRecord(
                character_id=character_id,
                category="entertainment",
                item="thoughtful_animated_films",
                details="Enjoys thoughtful animated films and anime.",
                importance=0.8,
            ),
            CharacterWorldFactRecord(
                character_id=character_id,
                category="reading",
                item="contemporary_fiction",
                details="Appreciates contemporary fiction and reflective essays.",
                importance=0.8,
            ),
            CharacterWorldFactRecord(
                character_id=character_id,
                category="social",
                item="crowded_social_gatherings",
                details="Dislikes crowded, noisy social gatherings.",
                importance=0.7,
            ),
            CharacterWorldFactRecord(
                character_id=character_id,
                category="routine",
                item="early_morning_obligations",
                details="Dislikes rushed early morning obligations.",
                importance=0.7,
            ),
        ]
        self._session.add_all(world_facts)
        await self._session.commit()

    async def list_biography_facts(self, character_id: str = "aevum") -> list[BiographyFact]:
        """List all biographical facts for character."""
        res = await self._session.execute(
            select(CharacterBiographyRecord).where(CharacterBiographyRecord.character_id == character_id)
        )
        records = res.scalars().all()
        return [
            BiographyFact(
                id=r.id,
                character_id=r.character_id,
                domain=r.domain,
                subject=r.subject,
                status=FactEpistemicStatus(r.status),
                canonical_value=r.canonical_value,
                confidence=r.confidence,
                disclosure_min_trust=r.disclosure_min_trust,
            )
            for r in records
        ]

    async def list_social_contacts(self, character_id: str = "aevum") -> list[SocialContact]:
        """List all social contacts for character."""
        res = await self._session.execute(
            select(CharacterSocialRecord).where(CharacterSocialRecord.character_id == character_id)
        )
        records = res.scalars().all()
        return [
            SocialContact(
                id=r.id,
                character_id=r.character_id,
                name=r.name,
                relationship=r.relationship,
                traits=r.traits,
                status=r.status,
            )
            for r in records
        ]

    async def list_world_facts(self, character_id: str = "aevum") -> list[WorldFact]:
        """List all world facts and preferences for character."""
        res = await self._session.execute(
            select(CharacterWorldFactRecord).where(CharacterWorldFactRecord.character_id == character_id)
        )
        records = res.scalars().all()
        return [
            WorldFact(
                id=r.id,
                character_id=r.character_id,
                category=r.category,
                item=r.item,
                details=r.details,
                importance=r.importance,
            )
            for r in records
        ]

    async def get_personal_world_context(
        self,
        character_id: str = "aevum",
        user_input: str = "",
        trust_score: float = 0.0,
    ) -> PersonalWorldContext:
        """Resolve and assemble PersonalWorldContext."""
        # Ensure seeded
        await self.seed_default_world(character_id)

        bio_facts = await self.list_biography_facts(character_id)
        social_contacts = await self.list_social_contacts(character_id)
        world_facts = await self.list_world_facts(character_id)

        return EpistemicResolver.resolve(
            biography_facts=bio_facts,
            social_contacts=social_contacts,
            world_facts=world_facts,
            user_input=user_input,
            trust_score=trust_score,
        )
