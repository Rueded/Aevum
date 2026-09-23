"""Service managing versioned reality revisions and temporal fact history (Phase 7B.3).

Ensures that when canonical reality evolves (e.g. moving cities from Penang to KL,
or updating age/degree), historical ground truth is preserved in an append-only
lineage rather than silently overwritten or erased.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CharacterRealityRevisionRecord, utc_now
from app.reality.history_models import RealityRevisionRecord

logger = logging.getLogger(__name__)


class RealityHistoryService:
    """Provides append-only temporal tracking and querying of reality revisions."""

    def __init__(self, session: Optional[AsyncSession] = None) -> None:
        self._session = session
        # In-memory registry fallback for tests and quick lookups
        self._memory_revisions: list[RealityRevisionRecord] = []

    async def record_revision(
        self,
        character_id: str,
        fact_key: str,
        value: Any,
        effective_from: Optional[str] = None,
        effective_until: Optional[str] = None,
    ) -> RealityRevisionRecord:
        """Record a new revision for a reality fact, superseding prior active revision."""
        now = datetime.now(timezone.utc)
        now_str = now.isoformat()
        new_id = str(uuid.uuid4())

        prior_revision_id: Optional[str] = None

        if self._session is not None:
            # Query active revision from DB
            stmt = (
                select(CharacterRealityRevisionRecord)
                .where(
                    CharacterRealityRevisionRecord.character_id == character_id,
                    CharacterRealityRevisionRecord.fact_key == fact_key,
                    CharacterRealityRevisionRecord.superseded_by.is_(None),
                )
                .order_by(CharacterRealityRevisionRecord.created_at.desc())
            )
            active_db = (await self._session.scalars(stmt)).first()
            if active_db is not None:
                prior_revision_id = active_db.id
                active_db.superseded_by = new_id
                if not active_db.effective_until:
                    active_db.effective_until = effective_from or now_str

            new_db = CharacterRealityRevisionRecord(
                id=new_id,
                character_id=character_id,
                fact_key=fact_key,
                value_json=json.dumps(value),
                effective_from=effective_from or now_str,
                effective_until=effective_until,
                supersedes_id=prior_revision_id,
                superseded_by=None,
                created_at=now,
            )
            self._session.add(new_db)
            await self._session.commit()

        # Update in-memory fallback
        updated_mem: list[RealityRevisionRecord] = []
        for rev in self._memory_revisions:
            if (
                rev.character_id == character_id
                and rev.fact_key == fact_key
                and rev.superseded_by is None
            ):
                prior_revision_id = prior_revision_id or rev.id
                updated_mem.append(
                    rev.model_copy(
                        update={
                            "superseded_by": new_id,
                            "effective_until": rev.effective_until or effective_from or now_str,
                        }
                    )
                )
            else:
                updated_mem.append(rev)

        new_record = RealityRevisionRecord(
            id=new_id,
            character_id=character_id,
            fact_key=fact_key,
            value=value,
            effective_from=effective_from or now_str,
            effective_until=effective_until,
            supersedes_id=prior_revision_id,
            superseded_by=None,
            created_at=now,
        )
        updated_mem.append(new_record)
        self._memory_revisions = updated_mem

        return new_record

    async def get_history(
        self, character_id: str, fact_key: Optional[str] = None
    ) -> list[RealityRevisionRecord]:
        """Retrieve historical revisions in chronological order."""
        if self._session is not None:
            stmt = select(CharacterRealityRevisionRecord).where(
                CharacterRealityRevisionRecord.character_id == character_id
            )
            if fact_key is not None:
                stmt = stmt.where(CharacterRealityRevisionRecord.fact_key == fact_key)
            stmt = stmt.order_by(CharacterRealityRevisionRecord.created_at.asc())
            records = (await self._session.scalars(stmt)).all()
            return [
                RealityRevisionRecord(
                    id=r.id,
                    character_id=r.character_id,
                    fact_key=r.fact_key,
                    value=json.loads(r.value_json),
                    effective_from=r.effective_from,
                    effective_until=r.effective_until,
                    supersedes_id=r.supersedes_id,
                    superseded_by=r.superseded_by,
                    created_at=r.created_at,
                )
                for r in records
            ]

        # Memory fallback
        results = [
            r for r in self._memory_revisions
            if r.character_id == character_id and (fact_key is None or r.fact_key == fact_key)
        ]
        return sorted(results, key=lambda x: x.created_at)

    async def get_active_revision(
        self, character_id: str, fact_key: str
    ) -> Optional[RealityRevisionRecord]:
        """Retrieve the currently active revision for a fact."""
        history = await self.get_history(character_id, fact_key)
        for rev in reversed(history):
            if rev.is_current:
                return rev
        return None

    async def get_revision_at_time(
        self, character_id: str, fact_key: str, as_of: Any
    ) -> Optional[RealityRevisionRecord]:
        """Retrieve the historical fact revision valid at a specific point in time."""
        as_of_str = as_of.isoformat() if isinstance(as_of, datetime) else str(as_of)
        history = await self.get_history(character_id, fact_key)
        for rev in history:
            from_ok = rev.effective_from is None or rev.effective_from <= as_of_str
            until_ok = rev.effective_until is None or as_of_str < rev.effective_until
            if from_ok and until_ok:
                return rev
        return None
