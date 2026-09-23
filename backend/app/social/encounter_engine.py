"""Social encounter evaluation and execution engine (Phase 7C.4).

Enforces:
- Invariant 15.1: Role templates are blueprints, not pre-existing relationships.
- Invariant 15.4: Contextual social opportunity and hard gating.
- Invariant 15.8: Evidence-bounded encounter summaries.
- Standard 29: Idempotent social encounter recording.
- Standard 31: Atomic social transaction scope.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LifeEventRecord, SocialCandidateRecord, SocialEncounterRecord, CharacterSocialRecord
from app.life.models import LifeEventType
from app.social.models import (
    IdentityState,
    SocialOpportunityLevel,
    EncounterType,
    InteractionDepth,
    SocialDynamics,
)
from app.social.role_templates import (
    SocialOpportunityProfile,
    SocialRoleCategory,
    SocialRoleTemplate,
    get_eligible_role_templates,
)
from app.social.service import SocialWorldService

logger = logging.getLogger(__name__)


class SocialEncounterResult(BaseModel):
    """Result of an encounter evaluation cycle."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    opportunity_level: SocialOpportunityLevel
    encounter_generated: bool
    candidate_id: Optional[str] = None
    contact_id: Optional[str] = None
    role_template_id: Optional[str] = None
    encounter_record_id: Optional[str] = None
    life_event_id: Optional[str] = None
    observed_summary: Optional[str] = None
    is_new_candidate: bool = False
    is_promoted: bool = False


class SocialEncounterEngine:
    """Orchestrates contextual social opportunities, encounter gating, and history generation."""

    @classmethod
    async def evaluate_activity_encounter(
        cls,
        session: AsyncSession,
        character_id: str,
        activity_title: str,
        activity_id_slug: str,
        location: str,
        sim_time: datetime,
        activity_uuid: Optional[str] = None,
        physiological_state: Optional[Any] = None,
        desire_state: Optional[Any] = None,
    ) -> SocialEncounterResult:
        """Evaluate and execute potential social encounter for an active or completed activity."""
        # 1. Evaluate Social Opportunity via Affordance Architecture (Lock-in Item 4)
        opp_level = SocialOpportunityProfile.evaluate(
            location=location,
            activity_id=activity_id_slug,
            physiological_state=physiological_state,
            desire_state=desire_state,
        )

        if opp_level == SocialOpportunityLevel.NONE:
            return SocialEncounterResult(
                opportunity_level=SocialOpportunityLevel.NONE,
                encounter_generated=False,
            )

        # 2. Identify eligible role templates
        templates = get_eligible_role_templates(location, activity_id_slug)
        if not templates:
            return SocialEncounterResult(
                opportunity_level=opp_level,
                encounter_generated=False,
            )

        # Choose primary eligible role template
        template = templates[0]
        social_svc = SocialWorldService(session)

        # 3. Check for existing canonical contact first (Reinforcement of established contact)
        canonical_contact = await social_svc.find_matching_canonical_contact(
            role_template_id=template.role_id,
            character_id=character_id,
        )

        if canonical_contact is not None:
            # Interaction with established contact
            enc_type, depth, valence = cls._determine_interaction_params(template, opp_level)
            curr_dyn = SocialDynamics(
                familiarity=canonical_contact.familiarity,
                comfort=canonical_contact.comfort,
                respect=canonical_contact.respect,
                trust=canonical_contact.trust,
            )
            new_dyn = curr_dyn.apply_encounter(enc_type, depth, valence=valence)
            await social_svc.update_canonical_contact_dynamics(
                contact_id=canonical_contact.id,
                new_dynamics=new_dyn,
                last_interacted_at=sim_time,
            )

            # Invariant 15.8: Evidence-bounded observed summary
            observed_summary = (
                f"Shared brief interaction with {canonical_contact.name} ({canonical_contact.relationship}) "
                f"at {location} during {activity_title}."
            )

            idem_key = f"encounter:{activity_uuid or activity_id_slug}:{canonical_contact.id}"
            enc_rec = await social_svc.record_encounter(
                character_id=character_id,
                contact_id=canonical_contact.id,
                activity_id=activity_uuid,
                location=location,
                encounter_type=enc_type,
                interaction_depth=depth,
                valence=valence,
                observed_summary=observed_summary,
                occurred_at=sim_time,
                idempotency_key=idem_key,
            )

            life_ev = await cls._create_life_event_if_missing(
                session=session,
                character_id=character_id,
                title=f"Saw {canonical_contact.name}",
                description=observed_summary,
                occurred_at=sim_time,
                idempotency_key=f"social_event:{activity_uuid or activity_id_slug}:{canonical_contact.id}",
                activity_id=activity_uuid,
            )

            return SocialEncounterResult(
                opportunity_level=opp_level,
                encounter_generated=True,
                contact_id=canonical_contact.id,
                role_template_id=template.role_id,
                encounter_record_id=enc_rec.id,
                life_event_id=life_ev.id if life_ev else None,
                observed_summary=observed_summary,
                is_new_candidate=False,
                is_promoted=False,
            )

        # 4. Check for existing candidate (Recurring evidence accumulation)
        candidate = await social_svc.find_matching_candidate(
            role_template_id=template.role_id,
            character_id=character_id,
        )

        if candidate is not None:
            enc_type, depth, valence = cls._determine_interaction_params(template, opp_level)
            curr_dyn = SocialDynamics(
                familiarity=candidate.provisional_familiarity,
                comfort=candidate.provisional_comfort,
                respect=candidate.provisional_respect,
                trust=candidate.provisional_trust,
            )
            new_dyn = curr_dyn.apply_encounter(enc_type, depth, valence=valence)

            # Encounter 2+ promotes identity_state to RECOGNIZED (Lock-in Item 2)
            new_id_state = IdentityState.RECOGNIZED
            await social_svc.update_candidate_encounter(
                candidate_id=candidate.id,
                observed_at=sim_time,
                new_dynamics=new_dyn,
                identity_state=new_id_state,
            )

            observed_summary = (
                f"Observed familiar recognized presence of a {template.title.lower()} at {location} "
                f"during {activity_title}."
            )

            idem_key = f"encounter:{activity_uuid or activity_id_slug}:{candidate.id}:{candidate.encounter_count}"
            enc_rec = await social_svc.record_encounter(
                character_id=character_id,
                candidate_id=candidate.id,
                activity_id=activity_uuid,
                location=location,
                encounter_type=enc_type,
                interaction_depth=depth,
                valence=valence,
                observed_summary=observed_summary,
                occurred_at=sim_time,
                idempotency_key=idem_key,
            )

            life_ev = await cls._create_life_event_if_missing(
                session=session,
                character_id=character_id,
                title=f"Noticed familiar {template.title.lower()}",
                description=observed_summary,
                occurred_at=sim_time,
                idempotency_key=f"social_event:{activity_uuid or activity_id_slug}:{candidate.id}:{candidate.encounter_count}",
                activity_id=activity_uuid,
            )

            return SocialEncounterResult(
                opportunity_level=opp_level,
                encounter_generated=True,
                candidate_id=candidate.id,
                role_template_id=template.role_id,
                encounter_record_id=enc_rec.id,
                life_event_id=life_ev.id if life_ev else None,
                observed_summary=observed_summary,
                is_new_candidate=False,
                is_promoted=False,
            )

        # 5. Check soft social capacity before creating a new candidate (Standard 30)
        has_capacity = await social_svc.evaluate_social_capacity_slot(character_id=character_id)
        if not has_capacity:
            return SocialEncounterResult(
                opportunity_level=opp_level,
                encounter_generated=False,
            )

        # 6. Instantiate new candidate slot (Anonymous encounter, Lock-in Item 2)
        new_cand = await social_svc.create_candidate(
            role_template_id=template.role_id,
            first_observed_at=sim_time,
            character_id=character_id,
            identity_state=IdentityState.ANONYMOUS,
            baseline_dynamics=template.baseline_dynamics,
        )

        enc_type, depth, valence = cls._determine_interaction_params(template, opp_level)
        observed_summary = (
            f"Noticed a {template.title.lower()} present at {location} during {activity_title}."
        )

        idem_key = f"encounter:{activity_uuid or activity_id_slug}:{new_cand.id}:1"
        enc_rec = await social_svc.record_encounter(
            character_id=character_id,
            candidate_id=new_cand.id,
            activity_id=activity_uuid,
            location=location,
            encounter_type=enc_type,
            interaction_depth=depth,
            valence=valence,
            observed_summary=observed_summary,
            occurred_at=sim_time,
            idempotency_key=idem_key,
        )

        life_ev = await cls._create_life_event_if_missing(
            session=session,
            character_id=character_id,
            title=f"Observed {template.title.lower()}",
            description=observed_summary,
            occurred_at=sim_time,
            idempotency_key=f"social_event:{activity_uuid or activity_id_slug}:{new_cand.id}:1",
            activity_id=activity_uuid,
        )

        return SocialEncounterResult(
            opportunity_level=opp_level,
            encounter_generated=True,
            candidate_id=new_cand.id,
            role_template_id=template.role_id,
            encounter_record_id=enc_rec.id,
            life_event_id=life_ev.id if life_ev else None,
            observed_summary=observed_summary,
            is_new_candidate=True,
            is_promoted=False,
        )

    @classmethod
    def _determine_interaction_params(
        cls,
        template: SocialRoleTemplate,
        opportunity: SocialOpportunityLevel,
    ) -> tuple[EncounterType, InteractionDepth, float]:
        """Derive encounter type, depth, and valence from role and opportunity."""
        if template.category == SocialRoleCategory.CAMPUS_SERVICE:
            return (EncounterType.TRANSACTIONAL, InteractionDepth.TRANSACTIONAL, 0.2)

        if template.category == SocialRoleCategory.ACADEMIC:
            if template.role_id == "academic_advisor":
                return (EncounterType.ACADEMIC_INQUIRY, InteractionDepth.FOCUSED_COLLABORATION, 0.3)
            # Course classmate
            if opportunity == SocialOpportunityLevel.HIGH:
                return (EncounterType.CASUAL_CHAT, InteractionDepth.CASUAL_EXCHANGE, 0.4)
            return (EncounterType.PASSING_PRESENCE, InteractionDepth.GLANCE_OR_PRESENCE, 0.1)

        if template.category == SocialRoleCategory.CREATIVE_PEER:
            return (EncounterType.CASUAL_CHAT, InteractionDepth.CASUAL_EXCHANGE, 0.5)

        return (EncounterType.PASSING_PRESENCE, InteractionDepth.GLANCE_OR_PRESENCE, 0.0)

    @classmethod
    async def _create_life_event_if_missing(
        cls,
        session: AsyncSession,
        character_id: str,
        title: str,
        description: str,
        occurred_at: datetime,
        idempotency_key: str,
        activity_id: Optional[str] = None,
    ) -> Optional[LifeEventRecord]:
        """Create an idempotent LifeEventRecord for this encounter."""
        from sqlalchemy import select
        stmt = select(LifeEventRecord).where(LifeEventRecord.idempotency_key == idempotency_key)
        existing = (await session.scalars(stmt)).first()
        if existing is not None:
            return existing

        ev = LifeEventRecord(
            character_id=character_id,
            event_type=LifeEventType.SOCIAL_EVENT.value,
            title=title,
            description=description,
            significance=0.4,
            occurred_at=occurred_at,
            idempotency_key=idempotency_key,
        )
        session.add(ev)
        await session.flush()
        return ev
