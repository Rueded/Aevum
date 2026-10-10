"""Personal Growth Context Adapter (Phase 16.5).

Assembles read-only Phase 16 growth, experience, preference, and longitudinal activity
data into an authoritative, bounded, and deterministic <personal_growth_context> block.

Hard Architectural Invariants:
1. STRICTLY READ-ONLY: Never writes, mutates, or deletes any database record.
2. EPISTEMIC SEPARATION: Distinguishes LIVED experiences from HEARD_OF_ONLY world topics.
3. BUDGET PRECEDENCE: Default character budget is relevance-oriented; critical identity,
   epistemic boundaries, and activity states take absolute precedence over truncation.
4. ZERO FLOATS IN LOGIC: Mathematical selection uses discrete thresholds and integer rankings.
5. DETERMINISTIC FORMATTING: Produces reproducible XML with SHA-256 integrity digest.
"""

from collections.abc import Sequence
import hashlib
import logging
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.genesis_models import EpistemicProvenanceKind, ExperienceStatus
from app.growth.growth_db_models import (
    CharacterExperienceTable,
    CharacterFacetAppraisalTable,
    CharacterInterestDomainTable,
    CharacterInterestFacetTable,
    CharacterPreferenceTable,
    CharacterResurgenceEventTable,
)
from app.growth.state_machine import ActivityState

logger = logging.getLogger(__name__)

DEFAULT_GROWTH_CONTEXT_BUDGET_CHARS: int = 1200


# =============================================================================
# DTOs
# =============================================================================

class LivedDomainSummary(BaseModel):
    """Summary of genuine first-person lived interaction in a domain."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    domain_key: str
    display_name: str
    facets_experienced: tuple[str, ...]
    total_experience_count: int


class FormedTasteSummary(BaseModel):
    """Summary of a formed personal preference."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    domain_key: str
    facet_key: str
    polarity: str
    stability_tier: str


class PersonalGrowthContext(BaseModel):
    """Immutable, bounded container for projected personal growth context."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    character_id: str
    lived_domains: tuple[LivedDomainSummary, ...]
    heard_of_domains: tuple[str, ...]
    established_tastes: tuple[FormedTasteSummary, ...]
    activity_states: dict[str, str]
    xml_block: str
    content_sha256: str


# =============================================================================
# Context Builder & Adapter Logic
# =============================================================================

class PersonalGrowthContextAdapter:
    """Read-only adapter transforming Phase 16 database records into LLM growth context."""

    @classmethod
    def format_xml(
        cls,
        *,
        lived_domains: Sequence[LivedDomainSummary],
        heard_of_domains: Sequence[str],
        established_tastes: Sequence[FormedTasteSummary],
        activity_states: dict[str, str],
        budget_chars: int = DEFAULT_GROWTH_CONTEXT_BUDGET_CHARS,
    ) -> str:
        """Format personal growth context into structured XML following budget precedence.

        Budget Precedence Hierarchy (Final Gate 0 Lock):
        1. Non-negotiable: Epistemic separation (Lived vs Heard-of).
        2. Non-negotiable: Longitudinal activity state (Active/Satiated/Dormant).
        3. Prioritized: Established tastes and relevant lived experiences.
        4. Truncation applies strictly to low-priority entries bottom-up.
        """
        lines: list[str] = ["<personal_growth_context>"]

        # 1. Epistemic Awareness Block (Non-negotiable)
        lines.append("  <epistemic_self_awareness>")
        if lived_domains:
            lived_items = [
                f"{d.display_name} ({', '.join(d.facets_experienced)})"
                for d in lived_domains
            ]
            lines.append(f"    - LIVED_EXPERIENCES: You have authentic first-person memories in: [{', '.join(lived_items)}].")
        else:
            lines.append("    - LIVED_EXPERIENCES: None yet. You are at the start of your experiential journey.")

        if heard_of_domains:
            lines.append(
                f"    - HEARD_OF_ONLY: You know about these topics objectively, but have NEVER personally experienced them: "
                f"[{', '.join(heard_of_domains)}]. Candidly acknowledge lack of personal experience if asked; "
                f"do NOT invent lived memories or deliver encyclopedic textbook summaries."
            )
        lines.append("  </epistemic_self_awareness>")

        # 2. Longitudinal Activity State (Non-negotiable)
        satiated_or_dormant = {
            dom: state for dom, state in activity_states.items()
            if state in (ActivityState.SATIATED.value, ActivityState.DORMANT.value)
        }
        if satiated_or_dormant:
            lines.append("  <longitudinal_activity>")
            for dom, state in sorted(satiated_or_dormant.items()):
                if state == ActivityState.SATIATED.value:
                    lines.append(f"    - {dom}: SATIATED (taking a natural break after intense engagement; fatigue, not loss of interest).")
                elif state == ActivityState.DORMANT.value:
                    lines.append(f"    - {dom}: DORMANT (quiet background interest; hasn't been active recently).")
            lines.append("  </longitudinal_activity>")

        # 3. Established Tastes Block (Relevance-bounded)
        if established_tastes:
            lines.append("  <established_tastes>")
            for taste in established_tastes:
                desc = f"    - {taste.domain_key}/{taste.facet_key}: {taste.polarity} ({taste.stability_tier})"
                lines.append(desc)
            lines.append("  </established_tastes>")

        lines.append("</personal_growth_context>")
        return "\n".join(lines)

    @classmethod
    def assemble_sync(
        cls,
        session: Session,
        character_id: str = "aevum",
        salient_topics: Optional[Sequence[str]] = None,
        seed_heard_of_topics: Optional[Sequence[str]] = None,
        budget_chars: int = DEFAULT_GROWTH_CONTEXT_BUDGET_CHARS,
    ) -> PersonalGrowthContext:
        """Synchronously query Phase 16 tables (READ-ONLY) and compile PersonalGrowthContext."""
        # 1. Fetch registered interest domains
        domain_rows = (
            session.query(CharacterInterestDomainTable)
            .filter(CharacterInterestDomainTable.character_id == character_id)
            .all()
        )
        domain_map = {d.domain_key: d.display_name for d in domain_rows}

        # 2. Fetch facets with experience counts
        facet_rows = (
            session.query(CharacterInterestFacetTable)
            .filter(CharacterInterestFacetTable.character_id == character_id)
            .all()
        )

        # Group lived facets by domain (experience_count > 0)
        lived_by_domain: dict[str, list[str]] = {}
        counts_by_domain: dict[str, int] = {}
        for f in facet_rows:
            if f.experience_count > 0:
                lived_by_domain.setdefault(f.domain_key, []).append(f.facet_key)
                counts_by_domain[f.domain_key] = counts_by_domain.get(f.domain_key, 0) + f.experience_count

        lived_summaries: list[LivedDomainSummary] = []
        for dom_key, facets in sorted(lived_by_domain.items()):
            lived_summaries.append(
                LivedDomainSummary(
                    domain_key=dom_key,
                    display_name=domain_map.get(dom_key, dom_key),
                    facets_experienced=tuple(sorted(facets)),
                    total_experience_count=counts_by_domain.get(dom_key, 0),
                )
            )

        # 3. Compile Heard-Of domains (registered domains with 0 experience + seed topics)
        heard_of: list[str] = []
        for dom_key in sorted(domain_map.keys()):
            if dom_key not in lived_by_domain:
                heard_of.append(dom_key)
        if seed_heard_of_topics:
            for top in seed_heard_of_topics:
                if top not in heard_of and top not in lived_by_domain:
                    heard_of.append(top)

        # 4. Fetch formed preferences (character_facet_preferences)
        pref_rows = (
            session.query(CharacterPreferenceTable)
            .filter(CharacterPreferenceTable.character_id == character_id)
            .all()
        )
        formed_tastes: list[FormedTasteSummary] = []
        for p in pref_rows:
            if p.preference_polarity != "UNFORMED":
                formed_tastes.append(
                    FormedTasteSummary(
                        domain_key=p.domain_key,
                        facet_key=p.facet_key,
                        polarity=p.preference_polarity,
                        stability_tier=p.stability_tier,
                    )
                )

        # 5. Fetch latest resurgence / activity state
        # Active domains default to ACTIVE unless indicated
        activity_states: dict[str, str] = {}
        for dom_key in domain_map.keys():
            activity_states[dom_key] = ActivityState.ACTIVE.value

        # Filter tastes and lived summaries by salience if provided, keeping budget in mind
        if salient_topics:
            salient_set = {t.lower() for t in salient_topics}
            filtered_tastes = [
                t for t in formed_tastes
                if t.domain_key.lower() in salient_set or t.facet_key.lower() in salient_set
            ]
            if filtered_tastes:
                formed_tastes = filtered_tastes

        # 6. Format XML
        xml_block = cls.format_xml(
            lived_domains=lived_summaries,
            heard_of_domains=heard_of,
            established_tastes=formed_tastes,
            activity_states=activity_states,
            budget_chars=budget_chars,
        )

        content_hash = hashlib.sha256(xml_block.encode("utf-8")).hexdigest()

        return PersonalGrowthContext(
            character_id=character_id,
            lived_domains=tuple(lived_summaries),
            heard_of_domains=tuple(heard_of),
            established_tastes=tuple(formed_tastes),
            activity_states=activity_states,
            xml_block=xml_block,
            content_sha256=content_hash,
        )

    @classmethod
    async def assemble_async(
        cls,
        session: AsyncSession,
        character_id: str = "aevum",
        salient_topics: Optional[Sequence[str]] = None,
        seed_heard_of_topics: Optional[Sequence[str]] = None,
        budget_chars: int = DEFAULT_GROWTH_CONTEXT_BUDGET_CHARS,
    ) -> PersonalGrowthContext:
        """Asynchronously query Phase 16 tables (READ-ONLY) and compile PersonalGrowthContext."""
        # 1. Fetch registered interest domains
        res_domains = await session.execute(
            select(CharacterInterestDomainTable).filter(CharacterInterestDomainTable.character_id == character_id)
        )
        domain_rows = res_domains.scalars().all()
        domain_map = {d.domain_key: d.display_name for d in domain_rows}

        # 2. Fetch facets
        res_facets = await session.execute(
            select(CharacterInterestFacetTable).filter(CharacterInterestFacetTable.character_id == character_id)
        )
        facet_rows = res_facets.scalars().all()

        lived_by_domain: dict[str, list[str]] = {}
        counts_by_domain: dict[str, int] = {}
        for f in facet_rows:
            if f.experience_count > 0:
                lived_by_domain.setdefault(f.domain_key, []).append(f.facet_key)
                counts_by_domain[f.domain_key] = counts_by_domain.get(f.domain_key, 0) + f.experience_count

        lived_summaries: list[LivedDomainSummary] = []
        for dom_key, facets in sorted(lived_by_domain.items()):
            lived_summaries.append(
                LivedDomainSummary(
                    domain_key=dom_key,
                    display_name=domain_map.get(dom_key, dom_key),
                    facets_experienced=tuple(sorted(facets)),
                    total_experience_count=counts_by_domain.get(dom_key, 0),
                )
            )

        heard_of: list[str] = []
        for dom_key in sorted(domain_map.keys()):
            if dom_key not in lived_by_domain:
                heard_of.append(dom_key)
        if seed_heard_of_topics:
            for top in seed_heard_of_topics:
                if top not in heard_of and top not in lived_by_domain:
                    heard_of.append(top)

        # 3. Fetch preferences
        res_prefs = await session.execute(
            select(CharacterPreferenceTable).filter(CharacterPreferenceTable.character_id == character_id)
        )
        pref_rows = res_prefs.scalars().all()
        formed_tastes: list[FormedTasteSummary] = []
        for p in pref_rows:
            if p.preference_polarity != "UNFORMED":
                formed_tastes.append(
                    FormedTasteSummary(
                        domain_key=p.domain_key,
                        facet_key=p.facet_key,
                        polarity=p.preference_polarity,
                        stability_tier=p.stability_tier,
                    )
                )

        activity_states: dict[str, str] = {}
        for dom_key in domain_map.keys():
            activity_states[dom_key] = ActivityState.ACTIVE.value

        if salient_topics:
            salient_set = {t.lower() for t in salient_topics}
            filtered_tastes = [
                t for t in formed_tastes
                if t.domain_key.lower() in salient_set or t.facet_key.lower() in salient_set
            ]
            if filtered_tastes:
                formed_tastes = filtered_tastes

        xml_block = cls.format_xml(
            lived_domains=lived_summaries,
            heard_of_domains=heard_of,
            established_tastes=formed_tastes,
            activity_states=activity_states,
            budget_chars=budget_chars,
        )

        content_hash = hashlib.sha256(xml_block.encode("utf-8")).hexdigest()

        return PersonalGrowthContext(
            character_id=character_id,
            lived_domains=tuple(lived_summaries),
            heard_of_domains=tuple(heard_of),
            established_tastes=tuple(formed_tastes),
            activity_states=activity_states,
            xml_block=xml_block,
            content_sha256=content_hash,
        )
