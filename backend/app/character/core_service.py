"""Service managing persistent Character Core facts with strict authority and provenance.

Enforces:
- Database (`character_core_facts`) is the single runtime source of truth.
- FactKeyRegistry domain value contracts.
- Lock invariant: locked == True <==> authority == USER_LOCKED.
- Single current reality: One fact_key per character_id, atomic replacement of SYSTEM_BASELINE.
- Deletion matrix: USER_LOCKED raises FactLockedError (409), SYSTEM_BASELINE raises SystemBaselineImmutableError (403).
"""

import json
import logging
from typing import Any, Optional
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.core_models import CharacterCore
from app.db.models import CharacterCoreFactRecord, utc_now
from app.reality.biography_promotion_models import PromotionAuthorizationToken
from app.reality.models import CoreFactItem, FactAuthority, FactSource, FactStatus
from app.reality.registry import FactKeyRegistry

logger = logging.getLogger(__name__)


class FactLockedError(Exception):
    """Raised when attempting to modify or delete a fact locked by the user."""
    pass


class SystemBaselineImmutableError(Exception):
    """Raised when attempting to delete a foundational system baseline fact."""
    pass


class CandidateNotEditableError(Exception):
    """Raised when attempting to patch a candidate fact directly without confirm/reject."""
    pass


class AevumCanonicalNotDirectlyEditableError(Exception):
    """Raised when attempting to directly edit an Aevum canonical fact in Phase 7B.1."""
    pass


def _derive_category(fact_key: str) -> str:
    """Infer domain category from fact key prefix."""
    if "." in fact_key:
        return fact_key.split(".")[0]
    return fact_key


class CharacterCoreService:
    """Application service for Character Core reality facts."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _ensure_initialized(self, character_id: str) -> None:
        """Ensure character baseline facts are initialized if database is empty."""
        if character_id == "aevum":
            await self.seed_default_core(character_id)

    async def get_core(self, character_id: str = "aevum") -> CharacterCore:
        """Load the authoritative CharacterCore for a character, seeding baseline if empty."""
        await self._ensure_initialized(character_id)
        stmt = (
            select(CharacterCoreFactRecord)
            .where(CharacterCoreFactRecord.character_id == character_id)
            .order_by(CharacterCoreFactRecord.category.asc(), CharacterCoreFactRecord.fact_key.asc())
        )
        records = (await self._session.scalars(stmt)).all()

        fact_items: dict[str, CoreFactItem] = {}
        for r in records:
            fact_items[r.fact_key] = self._record_to_domain(r)

        return CharacterCore(character_id=character_id, facts=fact_items)

    async def seed_default_core(self, character_id: str = "aevum") -> None:
        """Seed foundational system baseline anchors without unapproved biographical trivia."""
        stmt = select(CharacterCoreFactRecord.id).where(CharacterCoreFactRecord.character_id == character_id)
        existing_id = (await self._session.scalars(stmt)).first()
        if existing_id is not None:
            return

        logger.info("Seeding foundational baseline Character Core facts for '%s'", character_id)

        # Canonical approved baseline anchors
        baseline_facts = [
            ("identity.name", "identity", "Aevum"),
            ("identity.age", "identity", 21),
            ("identity.occupation", "identity", "University Student"),
            (
                "identity.background",
                "identity",
                "Undergraduate university student with a close, supportive family and an independent personal life.",
            ),
            ("family.background", "family", "Grew up in a supportive family environment."),
            ("education.level", "education", "Undergraduate"),
            ("location.residence", "location", "unspecified"),
            (
                "interests",
                "interests",
                [
                    "acoustic piano and guitar",
                    "story-rich indie games",
                    "thoughtful animated films and anime",
                    "contemporary fiction",
                ],
            ),
            (
                "dislikes",
                "dislikes",
                [
                    "crowded noisy social gatherings",
                    "rushed early morning obligations",
                ],
            ),
        ]

        now = utc_now()
        for key, cat, val in baseline_facts:
            norm_val = FactKeyRegistry.validate(key, val)
            rec = CharacterCoreFactRecord(
                character_id=character_id,
                fact_key=key,
                category=cat,
                value_json=json.dumps(norm_val),
                source=FactSource.SYSTEM_BASELINE.value,
                authority=FactAuthority.SYSTEM_BASELINE.value,
                status=FactStatus.CANONICAL.value,
                confidence=1.0,
                locked=False,
                explanation="Foundational baseline anchor",
                created_at=now,
                updated_at=now,
            )
            self._session.add(rec)

        await self._session.commit()

    async def set_fact(
        self,
        character_id: str,
        fact_key: str,
        value: Any,
        source: FactSource = FactSource.USER_CONFIGURED,
        authority: FactAuthority = FactAuthority.USER_CONFIGURED,
        status: FactStatus = FactStatus.CANONICAL,
        explanation: Optional[str] = None,
        confidence: float = 1.0,
        allow_canonical_reconciliation: bool = False,
        authorization_token: Optional[PromotionAuthorizationToken] = None,
        auto_commit: bool = True,
    ) -> CoreFactItem:
        """Create or update a fact with strict schema validation and authority checking."""
        await self._ensure_initialized(character_id)
        norm_val = FactKeyRegistry.validate(fact_key, value)
        category = _derive_category(fact_key)

        if allow_canonical_reconciliation:
            if authorization_token is None:
                raise AevumCanonicalNotDirectlyEditableError(
                    f"Canonical reconciliation on fact '{fact_key}' requires a valid PromotionAuthorizationToken."
                )
            if not authorization_token.verify(character_id, fact_key, norm_val):
                raise AevumCanonicalNotDirectlyEditableError(
                    f"PromotionAuthorizationToken invalid for character '{character_id}', fact '{fact_key}', or value payload."
                )

        stmt = select(CharacterCoreFactRecord).where(
            CharacterCoreFactRecord.character_id == character_id,
            CharacterCoreFactRecord.fact_key == fact_key,
        )
        existing = (await self._session.scalars(stmt)).first()
        now = utc_now()

        if existing is not None:
            # Check modification permissions
            if existing.locked:
                raise FactLockedError(
                    f"Cannot modify fact '{fact_key}' because it is locked by the user (USER_LOCKED)."
                )
            if existing.authority == FactAuthority.AEVUM_CANONICAL.value and existing.status == FactStatus.CANONICAL.value:
                if not allow_canonical_reconciliation or authorization_token is None:
                    raise AevumCanonicalNotDirectlyEditableError(
                        f"Direct edits on Aevum canonical fact '{fact_key}' require 7B.3 Reality Reconciliation."
                    )
                if not authorization_token.verify(character_id, fact_key, norm_val):
                    raise AevumCanonicalNotDirectlyEditableError(
                        f"PromotionAuthorizationToken invalid for character '{character_id}', fact '{fact_key}', or value payload."
                    )
            if existing.status == FactStatus.CANDIDATE.value and status != FactStatus.CANDIDATE:
                raise CandidateNotEditableError(
                    f"Candidate fact '{fact_key}' must be confirmed or rejected, not directly edited."
                )

            # Atomic update / replacement
            existing.value_json = json.dumps(norm_val)
            existing.source = source.value
            existing.authority = authority.value
            existing.status = status.value
            existing.confidence = confidence
            existing.locked = (authority == FactAuthority.USER_LOCKED)
            if explanation is not None:
                existing.explanation = explanation
            existing.updated_at = now
            record = existing
        else:
            # New fact creation
            is_locked = (authority == FactAuthority.USER_LOCKED)
            record = CharacterCoreFactRecord(
                character_id=character_id,
                fact_key=fact_key,
                category=category,
                value_json=json.dumps(norm_val),
                source=source.value,
                authority=authority.value,
                status=status.value,
                confidence=confidence,
                locked=is_locked,
                explanation=explanation,
                created_at=now,
                updated_at=now,
            )
            self._session.add(record)

        if auto_commit:
            await self._session.commit()
        else:
            await self._session.flush()
        return self._record_to_domain(record)

    async def lock_fact(self, character_id: str, fact_key: str) -> CoreFactItem:
        """Lock a fact against LLM modification (transitions authority to USER_LOCKED, locked=True)."""
        await self._ensure_initialized(character_id)
        stmt = select(CharacterCoreFactRecord).where(
            CharacterCoreFactRecord.character_id == character_id,
            CharacterCoreFactRecord.fact_key == fact_key,
        )
        record = (await self._session.scalars(stmt)).first()
        if record is None:
            raise ValueError(f"Fact '{fact_key}' not found for character '{character_id}'.")

        record.authority = FactAuthority.USER_LOCKED.value
        record.locked = True
        record.updated_at = utc_now()
        await self._session.commit()
        return self._record_to_domain(record)

    async def unlock_fact(self, character_id: str, fact_key: str) -> CoreFactItem:
        """Unlock a fact (transitions authority to USER_CONFIGURED, locked=False)."""
        await self._ensure_initialized(character_id)
        stmt = select(CharacterCoreFactRecord).where(
            CharacterCoreFactRecord.character_id == character_id,
            CharacterCoreFactRecord.fact_key == fact_key,
        )
        record = (await self._session.scalars(stmt)).first()
        if record is None:
            raise ValueError(f"Fact '{fact_key}' not found for character '{character_id}'.")

        record.authority = FactAuthority.USER_CONFIGURED.value
        record.locked = False
        record.updated_at = utc_now()
        await self._session.commit()
        return self._record_to_domain(record)

    async def confirm_candidate_fact(self, character_id: str, fact_key: str) -> CoreFactItem:
        """Confirm a candidate fact into canonical reality under user authorization.

        Transitions:
        - status: CANDIDATE -> CANONICAL
        - authority: -> USER_CONFIGURED
        - source: preserved as original provenance (e.g. AEVUM_INFERRED)
        - locked: False (user may lock subsequently if desired)
        """
        stmt = select(CharacterCoreFactRecord).where(
            CharacterCoreFactRecord.character_id == character_id,
            CharacterCoreFactRecord.fact_key == fact_key,
        )
        record = (await self._session.scalars(stmt)).first()
        if record is None:
            raise ValueError(f"Fact '{fact_key}' not found for character '{character_id}'.")

        if record.status != FactStatus.CANDIDATE.value:
            raise ValueError(f"Fact '{fact_key}' is in status '{record.status}', not CANDIDATE.")

        record.status = FactStatus.CANONICAL.value
        record.authority = FactAuthority.USER_CONFIGURED.value
        record.locked = False
        record.updated_at = utc_now()
        await self._session.commit()
        return self._record_to_domain(record)

    async def reject_candidate_fact(self, character_id: str, fact_key: str) -> bool:
        """Reject and cleanly discard a candidate fact without marking it as FALSIFIED."""
        stmt = select(CharacterCoreFactRecord).where(
            CharacterCoreFactRecord.character_id == character_id,
            CharacterCoreFactRecord.fact_key == fact_key,
        )
        record = (await self._session.scalars(stmt)).first()
        if record is None:
            return False

        if record.status != FactStatus.CANDIDATE.value:
            raise ValueError(f"Fact '{fact_key}' is in status '{record.status}', not CANDIDATE.")

        await self._session.delete(record)
        await self._session.commit()
        return True

    async def delete_fact(self, character_id: str, fact_key: str) -> bool:
        """Delete a fact adhering strictly to the authority matrix."""
        stmt = select(CharacterCoreFactRecord).where(
            CharacterCoreFactRecord.character_id == character_id,
            CharacterCoreFactRecord.fact_key == fact_key,
        )
        record = (await self._session.scalars(stmt)).first()
        if record is None:
            return False

        if record.locked:
            raise FactLockedError(
                f"Cannot delete fact '{fact_key}' because it is locked by user (USER_LOCKED). Unlock first."
            )
        if record.authority == FactAuthority.SYSTEM_BASELINE.value:
            raise SystemBaselineImmutableError(
                f"Cannot delete foundational system baseline fact '{fact_key}'."
            )

        await self._session.delete(record)
        await self._session.commit()
        return True

    async def bulk_update_user_fields(
        self, character_id: str, updates: dict[str, Any]
    ) -> CharacterCore:
        """Bulk update user-configurable core fields."""
        for key, val in updates.items():
            await self.set_fact(
                character_id=character_id,
                fact_key=key,
                value=val,
                source=FactSource.USER_CONFIGURED,
                authority=FactAuthority.USER_CONFIGURED,
                status=FactStatus.CANONICAL,
            )
        return await self.get_core(character_id)

    def _record_to_domain(self, r: CharacterCoreFactRecord) -> CoreFactItem:
        """Convert ORM record to immutable CoreFactItem domain model."""
        val = json.loads(r.value_json)
        return CoreFactItem(
            key=r.fact_key,
            category=r.category,
            value=val,
            source=FactSource(r.source),
            authority=FactAuthority(r.authority),
            status=FactStatus(r.status),
            epistemic_confidence=r.confidence,
            locked=r.locked,
            explanation=r.explanation,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
