"""Multi-factor, role-differentiated Promotion Policy for Social Candidates (Phase 7C.4).

Enforces:
- Invariant 15.3: Multi-Stage Reality Promotion via evidence accumulation.
- Review Item 4: Differentiated promotion outcomes per role template.
- Review Item 2: Identity progression (ANONYMOUS -> RECOGNIZED -> IDENTIFIED).
"""

from datetime import datetime, timedelta, timezone
import hashlib
from typing import Optional, Sequence
from pydantic import BaseModel, ConfigDict, Field

from app.db.models import SocialCandidateRecord, SocialEncounterRecord
from app.social.models import IdentityState, InteractionDepth, SocialContactStatus
from app.social.role_templates import SocialRoleTemplate, get_role_template


# Emergent name syllables for deterministic naming upon IDENTIFIED state (Lock-in Item 2)
# Assigned ONLY upon promotion to IDENTIFIED, preventing pre-baked NPC databases
_ROLE_NAME_SEEDS: dict[str, list[str]] = {
    "course_classmate": ["Wei", "Li-An", "Arjun", "Hafiz", "Jia-Hui", "Marcus"],
    "academic_advisor": ["Dr. Hisham", "Dr. Lim", "Prof. Zainal", "Dr. Tan"],
    "campus_service_staff": ["Ken", "Sam", "Mei", "Rashid", "Chloe"],
    "creative_peer": ["Yuki", "Julian", "Alya", "Kai"],
    "community_acquaintance": ["Mr. Wong", "Uncle Tan", "Elena", "Dev"],
}


class PromotionEligibilityResult(BaseModel):
    """Evaluation result for promoting a candidate to canonical CharacterSocialRecord."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    is_eligible: bool
    reasons: tuple[str, ...] = Field(default_factory=tuple)
    suggested_display_name: str
    suggested_relationship_label: str
    suggested_traits: str
    promotion_outcome: str


class SocialPromotionPolicy:
    """Evaluates whether a candidate meets multi-factor criteria for canonical reality promotion."""

    @classmethod
    def evaluate(
        cls,
        candidate: SocialCandidateRecord,
        encounters: Sequence[SocialEncounterRecord],
    ) -> PromotionEligibilityResult:
        """Evaluate candidate readiness for canonical promotion.

        Multi-factor criteria:
        1. encounter_count >= template.min_encounters_for_promotion
        2. temporal_consistency: span between first and last observed >= 12 hours (distinct sessions)
        3. identity_consistency: candidate has progressed to RECOGNIZED
        4. interaction_depth: at least one encounter with depth >= CASUAL_EXCHANGE
        """
        tmpl = get_role_template(candidate.role_template_id)
        if tmpl is None:
            return PromotionEligibilityResult(
                is_eligible=False,
                reasons=("Role template not found in catalog.",),
                suggested_display_name="Unknown",
                suggested_relationship_label="Acquaintance",
                suggested_traits="",
                promotion_outcome="REJECTED",
            )

        reasons: list[str] = []
        is_eligible = True

        # 1. Encounter count check
        if candidate.encounter_count < tmpl.min_encounters_for_promotion:
            is_eligible = False
            reasons.append(
                f"Encounter count {candidate.encounter_count} < required {tmpl.min_encounters_for_promotion}."
            )

        # 2. Temporal consistency check (distinct sessions, not spammed in minutes)
        t_first = candidate.first_observed_at
        t_last = candidate.last_observed_at
        if t_first.tzinfo is None:
            t_first = t_first.replace(tzinfo=timezone.utc)
        if t_last.tzinfo is None:
            t_last = t_last.replace(tzinfo=timezone.utc)

        span = t_last - t_first
        # For academic advisors, 2 sessions separated by at least 4 hours suffice; for peers, 12 hours
        min_span = timedelta(hours=4) if candidate.role_template_id == "academic_advisor" else timedelta(hours=12)
        if candidate.encounter_count >= tmpl.min_encounters_for_promotion and span < min_span:
            is_eligible = False
            reasons.append(
                f"Temporal consistency gate not satisfied: span {span} < required {min_span}."
            )

        # 3. Identity consistency check (must have reached RECOGNIZED)
        if candidate.identity_state == IdentityState.ANONYMOUS.value and candidate.encounter_count > 1:
            is_eligible = False
            reasons.append("Identity state is still ANONYMOUS; requires recognized presence.")

        # 4. Interaction depth check
        has_substantive_interaction = any(
            enc.interaction_depth in (
                InteractionDepth.CASUAL_EXCHANGE.value,
                InteractionDepth.FOCUSED_COLLABORATION.value,
                InteractionDepth.DEEP_CONVERSATION.value,
                InteractionDepth.TRANSACTIONAL.value, # for service staff
            )
            for enc in encounters
        )
        if not has_substantive_interaction:
            is_eligible = False
            reasons.append("Lacks substantive interaction depth beyond passive glance.")

        # Generate emergent display name deterministically from candidate UUID (Lock-in Item 2)
        name_pool = _ROLE_NAME_SEEDS.get(tmpl.role_id, ["Alex", "Jordan", "Taylor"])
        idx = int(hashlib.sha256(candidate.id.encode()).hexdigest(), 16) % len(name_pool)
        display_name = name_pool[idx]

        # Role-differentiated outcomes (Review Item 4)
        rel_label = tmpl.default_relationship_label
        traits = f"Recognized {tmpl.title.lower()}; {tmpl.promotion_outcome.lower()}."

        if is_eligible:
            reasons.append("Candidate satisfied all multi-factor promotion criteria.")

        return PromotionEligibilityResult(
            is_eligible=is_eligible,
            reasons=tuple(reasons),
            suggested_display_name=display_name,
            suggested_relationship_label=rel_label,
            suggested_traits=traits,
            promotion_outcome=tmpl.promotion_outcome,
        )
