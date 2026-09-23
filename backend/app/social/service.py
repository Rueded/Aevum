"""Service layer managing candidates, encounters, and social records (Phase 7C.4).

Enforces:
- Invariant 15.3: Multi-Stage Reality Promotion via separate candidate layer.
- Standard 30: Stratified Soft Social Capacity.
- Standard 31: Atomic Social Transaction Scope.
"""

from datetime import datetime, timezone
import logging
from typing import Optional, Sequence
import uuid

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    CharacterSocialRecord,
    SocialCandidateRecord,
    SocialEncounterRecord,
    NPCFactRecord,
    utc_now,
)
from app.social.models import (
    IdentityState,
    SocialContactStatus,
    SocialDynamics,
    SocialCandidate,
    NPCEntity,
    EncounterType,
    InteractionDepth,
)

logger = logging.getLogger(__name__)


class SocialWorldService:
    """Repository and transaction manager for candidate, encounter, and canonical social entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # =========================================================================
    # Candidate Management (Provisional Evidence Container)
    # =========================================================================

    async def create_candidate(
        self,
        role_template_id: str,
        first_observed_at: datetime,
        character_id: str = "aevum",
        identity_state: IdentityState = IdentityState.ANONYMOUS,
        baseline_dynamics: Optional[SocialDynamics] = None,
    ) -> SocialCandidateRecord:
        """Create a new provisional candidate entity (Invariant 15.3)."""
        dyn = baseline_dynamics or SocialDynamics()
        rec = SocialCandidateRecord(
            id=str(uuid.uuid4()),
            character_id=character_id,
            role_template_id=role_template_id,
            identity_state=identity_state.value,
            status=SocialContactStatus.PROVISIONAL.value,
            first_observed_at=first_observed_at,
            last_observed_at=first_observed_at,
            encounter_count=1,
            provisional_familiarity=dyn.familiarity,
            provisional_comfort=dyn.comfort,
            provisional_respect=dyn.respect,
            provisional_trust=dyn.trust,
        )
        self._session.add(rec)
        await self._session.flush()
        return rec

    async def get_candidate(self, candidate_id: str) -> Optional[SocialCandidateRecord]:
        """Fetch candidate record by ID."""
        stmt = select(SocialCandidateRecord).where(SocialCandidateRecord.id == candidate_id)
        return (await self._session.scalars(stmt)).first()

    async def list_candidates(
        self,
        character_id: str = "aevum",
        status: Optional[SocialContactStatus] = None,
    ) -> Sequence[SocialCandidateRecord]:
        """List candidate records for character, optionally filtered by status."""
        stmt = select(SocialCandidateRecord).where(SocialCandidateRecord.character_id == character_id)
        if status is not None:
            stmt = stmt.where(SocialCandidateRecord.status == status.value)
        stmt = stmt.order_by(SocialCandidateRecord.last_observed_at.desc())
        return (await self._session.scalars(stmt)).all()

    async def find_matching_candidate(
        self,
        role_template_id: str,
        character_id: str = "aevum",
    ) -> Optional[SocialCandidateRecord]:
        """Find an existing active provisional candidate matching a role template."""
        stmt = (
            select(SocialCandidateRecord)
            .where(
                SocialCandidateRecord.character_id == character_id,
                SocialCandidateRecord.role_template_id == role_template_id,
                SocialCandidateRecord.status.in_([
                    SocialContactStatus.PROVISIONAL.value,
                    SocialContactStatus.ELIGIBLE.value,
                ]),
            )
            .order_by(SocialCandidateRecord.last_observed_at.desc())
        )
        return (await self._session.scalars(stmt)).first()

    async def update_candidate_encounter(
        self,
        candidate_id: str,
        observed_at: datetime,
        new_dynamics: SocialDynamics,
        identity_state: Optional[IdentityState] = None,
    ) -> Optional[SocialCandidateRecord]:
        """Update candidate encounter count, timestamp, and provisional dynamics."""
        cand = await self.get_candidate(candidate_id)
        if cand is None:
            return None

        cand.encounter_count += 1
        cand.last_observed_at = observed_at
        cand.provisional_familiarity = new_dynamics.familiarity
        cand.provisional_comfort = new_dynamics.comfort
        cand.provisional_respect = new_dynamics.respect
        cand.provisional_trust = new_dynamics.trust

        if identity_state is not None:
            cand.identity_state = identity_state.value

        await self._session.flush()
        return cand

    # =========================================================================
    # Social Encounter Recording (Auditable History)
    # =========================================================================

    async def record_encounter(
        self,
        location: str,
        encounter_type: EncounterType,
        interaction_depth: InteractionDepth,
        observed_summary: str,
        occurred_at: datetime,
        idempotency_key: str,
        character_id: str = "aevum",
        candidate_id: Optional[str] = None,
        contact_id: Optional[str] = None,
        activity_id: Optional[str] = None,
        valence: float = 0.0,
    ) -> SocialEncounterRecord:
        """Persist an immutable, factual SocialEncounterRecord (Invariant 15.8 & Standard 29)."""
        # Idempotency check
        stmt = select(SocialEncounterRecord).where(SocialEncounterRecord.idempotency_key == idempotency_key)
        existing = (await self._session.scalars(stmt)).first()
        if existing is not None:
            return existing

        rec = SocialEncounterRecord(
            id=str(uuid.uuid4()),
            character_id=character_id,
            candidate_id=candidate_id,
            contact_id=contact_id,
            activity_id=activity_id,
            location=location,
            encounter_type=encounter_type.value,
            interaction_depth=interaction_depth.value,
            valence=valence,
            observed_summary=observed_summary,
            occurred_at=occurred_at,
            idempotency_key=idempotency_key,
        )
        self._session.add(rec)
        await self._session.flush()
        return rec

    async def list_recent_encounters(
        self,
        character_id: str = "aevum",
        limit: int = 10,
    ) -> Sequence[SocialEncounterRecord]:
        """Fetch recent encounters in reverse chronological order."""
        stmt = (
            select(SocialEncounterRecord)
            .where(SocialEncounterRecord.character_id == character_id)
            .order_by(SocialEncounterRecord.occurred_at.desc())
            .limit(limit)
        )
        return (await self._session.scalars(stmt)).all()

    # =========================================================================
    # Canonical Social Contact Management (CharacterSocialRecord)
    # =========================================================================

    async def promote_candidate(
        self,
        candidate_id: str,
        display_name: str,
        relationship_label: str,
        traits: str,
        promoted_at: datetime,
    ) -> CharacterSocialRecord:
        """Promote a candidate to canonical CharacterSocialRecord (Invariant 15.2 & 15.3)."""
        cand = await self.get_candidate(candidate_id)
        if cand is None:
            raise ValueError(f"Candidate {candidate_id} not found.")

        cand.status = SocialContactStatus.PROMOTED.value
        cand.identity_state = IdentityState.IDENTIFIED.value

        contact_id = str(uuid.uuid4())
        social_rec = CharacterSocialRecord(
            id=contact_id,
            character_id=cand.character_id,
            name=display_name,
            relationship=relationship_label,
            traits=traits,
            status=SocialContactStatus.ACTIVE.value,
            candidate_id=cand.id,
            role_template_id=cand.role_template_id,
            familiarity=cand.provisional_familiarity,
            comfort=cand.provisional_comfort,
            respect=cand.provisional_respect,
            trust=cand.provisional_trust,
            first_met_at=cand.first_observed_at,
            last_mentioned_at=promoted_at,
        )
        self._session.add(social_rec)
        await self._session.flush()
        return social_rec

    async def get_canonical_contact(self, contact_id: str) -> Optional[CharacterSocialRecord]:
        """Fetch canonical contact by ID."""
        stmt = select(CharacterSocialRecord).where(CharacterSocialRecord.id == contact_id)
        return (await self._session.scalars(stmt)).first()

    async def list_canonical_contacts(
        self,
        character_id: str = "aevum",
    ) -> Sequence[CharacterSocialRecord]:
        """List all canonical ACTIVE social contacts."""
        stmt = (
            select(CharacterSocialRecord)
            .where(
                CharacterSocialRecord.character_id == character_id,
                CharacterSocialRecord.status == SocialContactStatus.ACTIVE.value,
            )
            .order_by(CharacterSocialRecord.familiarity.desc())
        )
        return (await self._session.scalars(stmt)).all()

    async def find_matching_canonical_contact(
        self,
        role_template_id: str,
        character_id: str = "aevum",
    ) -> Optional[CharacterSocialRecord]:
        """Find an active canonical contact matching a role template."""
        stmt = (
            select(CharacterSocialRecord)
            .where(
                CharacterSocialRecord.character_id == character_id,
                CharacterSocialRecord.role_template_id == role_template_id,
                CharacterSocialRecord.status == SocialContactStatus.ACTIVE.value,
            )
            .order_by(CharacterSocialRecord.familiarity.desc())
        )
        return (await self._session.scalars(stmt)).first()

    async def update_canonical_contact_dynamics(
        self,
        contact_id: str,
        new_dynamics: SocialDynamics,
        last_interacted_at: datetime,
    ) -> Optional[CharacterSocialRecord]:
        """Update multidimensional dynamics for an existing canonical contact."""
        rec = await self.get_canonical_contact(contact_id)
        if rec is None:
            return None

        rec.familiarity = new_dynamics.familiarity
        rec.comfort = new_dynamics.comfort
        rec.respect = new_dynamics.respect
        rec.trust = new_dynamics.trust
        rec.last_mentioned_at = last_interacted_at
        await self._session.flush()
        return rec

    # =========================================================================
    # Soft Social Capacity Evaluation (Standard 30)
    # =========================================================================

    async def evaluate_social_capacity_slot(
        self,
        character_id: str = "aevum",
    ) -> bool:
        """Check whether character's current active contacts allow an additional candidate.

        Enforces Standard 30: Stratified soft capacity:
        - Regular active contacts: soft target 5–10
        - If total active canonical contacts >= 10, new candidates are restricted.
        """
        stmt = select(func.count()).select_from(CharacterSocialRecord).where(
            CharacterSocialRecord.character_id == character_id,
            CharacterSocialRecord.status == SocialContactStatus.ACTIVE.value,
        )
        active_count = (await self._session.scalar(stmt)) or 0
        return active_count < 10
