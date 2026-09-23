"""NPC Reality Layer managing append-only NPC facts with supersession (Phase 7C.4).

Enforces:
- Invariant 15.7: Grounded NPC Reality Integrity (Unestablished facts are UNKNOWN).
- Invariant 15.8: Evidence-Bounded Encounter History.
- Lock-in Item 1: Append-only / supersession for NPC facts (no destructive updates).
"""

from datetime import datetime, timezone
import logging
from typing import Optional, Sequence
import uuid

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import NPCFactRecord, utc_now
from app.social.models import NPCFact

logger = logging.getLogger(__name__)


class NPCRealityManager:
    """Authoritative manager for NPC facts and prompt context formatting."""

    @classmethod
    async def record_fact(
        cls,
        session: AsyncSession,
        npc_id: str,
        fact_key: str,
        fact_value: str,
        source_encounter_id: Optional[str] = None,
        supersedes_id: Optional[str] = None,
    ) -> NPCFactRecord:
        """Record an NPC fact with append-only supersession semantics (Lock-in Item 1)."""
        now = utc_now()

        # If superseding an existing fact, mark the prior fact as SUPERSEDED
        if supersedes_id is not None:
            stmt_prior = select(NPCFactRecord).where(NPCFactRecord.id == supersedes_id)
            prior = (await session.scalars(stmt_prior)).first()
            if prior is not None:
                prior.status = "SUPERSEDED"
                prior.effective_until = now

        new_id = str(uuid.uuid4())
        rec = NPCFactRecord(
            id=new_id,
            npc_id=npc_id,
            fact_key=fact_key,
            fact_value=fact_value,
            status="ACTIVE",
            supersedes_id=supersedes_id,
            source_encounter_id=source_encounter_id,
            effective_from=now,
            established_at=now,
        )
        session.add(rec)
        await session.flush()

        if supersedes_id is not None and prior is not None:
            prior.superseded_by = new_id

        return rec

    @classmethod
    async def get_active_facts(
        cls,
        session: AsyncSession,
        npc_id: str,
    ) -> Sequence[NPCFactRecord]:
        """Fetch all currently ACTIVE facts for an NPC."""
        stmt = (
            select(NPCFactRecord)
            .where(
                NPCFactRecord.npc_id == npc_id,
                NPCFactRecord.status == "ACTIVE",
            )
            .order_by(NPCFactRecord.established_at.asc())
        )
        return (await session.scalars(stmt)).all()

    @classmethod
    async def get_fact_value(
        cls,
        session: AsyncSession,
        npc_id: str,
        fact_key: str,
    ) -> Optional[str]:
        """Fetch fact value, or None if UNKNOWN (Invariant 15.7)."""
        stmt = (
            select(NPCFactRecord)
            .where(
                NPCFactRecord.npc_id == npc_id,
                NPCFactRecord.fact_key == fact_key,
                NPCFactRecord.status == "ACTIVE",
            )
        )
        rec = (await session.scalars(stmt)).first()
        return rec.fact_value if rec is not None else None

    @classmethod
    def format_npc_reality_context(
        cls,
        npc_name: str,
        role_label: str,
        facts: Sequence[NPCFactRecord],
    ) -> str:
        """Build structured XML prompt context enforcing Invariant 15.7 negative constraints."""
        lines = [f'<npc_reality name="{npc_name}" role="{role_label}">']
        if facts:
            lines.append("Established Factual Ground Truth:")
            for f in facts:
                lines.append(f"- {f.fact_key}: {f.fact_value}")
        else:
            lines.append("Established Factual Ground Truth: None (Identity and role presence only).")

        lines.append(
            "CRITICAL REALITY BOUNDARY (Invariant 15.7 - DO NOT VIOLATE):\n"
            "All other personal attributes (e.g. age, family background, hometown, academic major, "
            "childhood, romantic history, living arrangements) are UNKNOWN.\n"
            "You MUST NOT invent, assume, or fabricate any background biography for this person."
        )
        lines.append("</npc_reality>")
        return "\n".join(lines)
