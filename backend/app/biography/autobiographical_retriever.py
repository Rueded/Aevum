"""autobiographical_retriever.py — Phase 12.3 Deterministic Autobiographical Retrieval Engine.

Governed by ADR-023:
1. Lock 1 & Lock C: Pure-read deterministic retrieval with zero mutation authority (0 set_fact, 0 token).
2. Lock 2 & Lock D: Preserves CausalKnowledgeState.UNKNOWN as a first-class domain state without fabrication.
3. Lock 4 & Lock F: Strict HistoryScope segregation (AEVUM_PERSONAL default vs SHARED_WITH_USER).
4. Lock 5: Flags empty/undefined territory and unknown causal origins for humble boundary expression.
5. Bitwise determinism: Integer-based relevance scoring, deterministic sorting and presentation budget caps.
"""

from __future__ import annotations

import logging
from typing import Optional, Sequence

from app.biography.biography_models import (
    BiographicalDomain,
    BiographicalFact,
    CanonicalStatus,
    CausalKnowledgeState,
    HistoryScope,
    LifeEra,
    LifeEventRecord,
    PersonalPreference,
    QualiaAnchor,
    RecallLevel,
    SocialContactRecord,
)
from app.biography.causal_graph import CausalExplanationPath
from app.biography.life_event_service import LifeEventService
from app.biography.retrieval_models import (
    AutobiographicalQuery,
    AutobiographicalRetrievalResult,
    BiographicalIntentType,
    ScoredBiographicalCandidate,
)

logger = logging.getLogger(__name__)


class AutobiographicalRetriever:
    """Pure-read deterministic retrieval engine for autobiographical facts, events, and causal paths."""

    # Presentation / Context budget caps
    MAX_FACTS: int = 6
    MAX_EVENTS: int = 4
    MAX_PREFERENCES: int = 4
    MAX_CAUSAL_PATHS: int = 2
    MAX_QUALIA: int = 3
    MAX_CONTACTS: int = 2

    def __init__(self, life_event_service: LifeEventService) -> None:
        self._service = life_event_service

    def retrieve(self, query: AutobiographicalQuery) -> AutobiographicalRetrievalResult:
        """Executes scoped, deterministic retrieval across canonical biography structures.

        Strict Invariant:
        Zero mutation authority, zero DB writes, zero LLM calls.
        """
        # 1. Retrieve candidates per domain type, filtered strictly by HistoryScope (Lock F)
        all_facts = self._service.get_all_facts(scope=query.scope)
        all_events = self._service.get_all_events(scope=query.scope)
        all_preferences = self._service.get_all_preferences()
        all_qualia = self._service.get_all_qualia()
        all_contacts = self._service.get_all_contacts(scope=query.scope)

        # 2. Score and rank facts
        scored_facts: list[tuple[int, BiographicalFact]] = []
        for fact in all_facts:
            score = self._score_fact(fact, query)
            if score > 0:
                scored_facts.append((score, fact))
        # Deterministic sort: -score, then fact_id ascending
        scored_facts.sort(key=lambda pair: (-pair[0], pair[1].fact_id))
        selected_facts = tuple(fact for _, fact in scored_facts[: self.MAX_FACTS])

        # 3. Score and rank events
        scored_events: list[tuple[int, LifeEventRecord]] = []
        for event in all_events:
            score = self._score_event(event, query)
            if score > 0:
                scored_events.append((score, event))
        scored_events.sort(key=lambda pair: (-pair[0], pair[1].event_id))
        selected_events = tuple(event for _, event in scored_events[: self.MAX_EVENTS])

        # 4. Score and rank preferences
        scored_prefs: list[tuple[int, PersonalPreference]] = []
        for pref in all_preferences:
            score = self._score_preference(pref, query)
            if score > 0:
                scored_prefs.append((score, pref))
        scored_prefs.sort(key=lambda pair: (-pair[0], pair[1].preference_id))
        selected_prefs = tuple(pref for _, pref in scored_prefs[: self.MAX_PREFERENCES])

        # 5. Score and rank contacts
        scored_contacts: list[tuple[int, SocialContactRecord]] = []
        for contact in all_contacts:
            score = self._score_contact(contact, query)
            if score > 0:
                scored_contacts.append((score, contact))
        scored_contacts.sort(key=lambda pair: (-pair[0], pair[1].contact_id))
        selected_contacts = tuple(contact for _, contact in scored_contacts[: self.MAX_CONTACTS])

        # 6. Causal explanation retrieval & Lock D boundary check
        causal_paths: list[CausalExplanationPath] = []
        has_unknown_causal_boundary = False

        # If query targets an entity specifically or has intent CAUSAL_ORIGIN / PERSONAL_PREFERENCE
        target_pref_ids: list[str] = []
        if query.target_entity_id:
            # Check if target_entity_id is a preference
            if self._service.get_preference_by_id(query.target_entity_id):
                target_pref_ids.append(query.target_entity_id)
        elif query.intent in (BiographicalIntentType.CAUSAL_ORIGIN, BiographicalIntentType.PERSONAL_PREFERENCE):
            for pref in selected_prefs:
                target_pref_ids.append(pref.preference_id)

        for pref_id in target_pref_ids[: self.MAX_CAUSAL_PATHS]:
            path = self._service.explain_preference(pref_id)
            causal_paths.append(path)
            if path.causal_state == CausalKnowledgeState.UNKNOWN:
                has_unknown_causal_boundary = True

        # 7. Qualia retrieval: Expand sensory anchors for selected events
        selected_qualia_dict: dict[str, QualiaAnchor] = {}
        for event in selected_events:
            for q in self._service.get_qualia_for_event(event.event_id):
                selected_qualia_dict[q.qualia_id] = q
                if len(selected_qualia_dict) >= self.MAX_QUALIA:
                    break
            if len(selected_qualia_dict) >= self.MAX_QUALIA:
                break

        # If qualia still below cap and query matches qualia description directly
        if len(selected_qualia_dict) < self.MAX_QUALIA and query.keywords:
            for q in all_qualia:
                if q.qualia_id not in selected_qualia_dict:
                    desc_lower = q.description.lower()
                    if any(kw.lower() in desc_lower for kw in query.keywords):
                        selected_qualia_dict[q.qualia_id] = q
                        if len(selected_qualia_dict) >= self.MAX_QUALIA:
                            break

        selected_qualia = tuple(
            sorted(selected_qualia_dict.values(), key=lambda q: q.qualia_id)
        )

        # 8. Check if result is empty (Lock 5 boundary condition)
        is_empty = (
            len(selected_facts) == 0
            and len(selected_events) == 0
            and len(selected_prefs) == 0
            and len(causal_paths) == 0
            and len(selected_qualia) == 0
            and len(selected_contacts) == 0
        )

        return AutobiographicalRetrievalResult(
            query=query,
            matched_facts=selected_facts,
            matched_events=selected_events,
            matched_preferences=selected_prefs,
            causal_paths=tuple(causal_paths),
            matched_qualia=selected_qualia,
            matched_contacts=selected_contacts,
            has_unknown_causal_boundary=has_unknown_causal_boundary,
            is_empty=is_empty,
        )

    # ========================================================================
    # Internal Scoring Routines (Deterministic Integer Scoring: 0 - 100)
    # ========================================================================

    def _score_fact(self, fact: BiographicalFact, query: AutobiographicalQuery) -> int:
        if query.target_entity_id and fact.fact_id == query.target_entity_id:
            return 100

        matched = False
        score = 0

        # Era match
        if query.target_era is not None:
            if fact.era == query.target_era:
                score += 30
                matched = True
            elif not query.keywords:
                return 0

        # Domain match
        if query.target_domain is not None:
            if fact.domain == query.target_domain:
                score += 30
                matched = True
            elif not query.keywords and query.target_era is None:
                return 0

        # Keyword match
        if query.keywords:
            kw_hits = 0
            haystack = f"{fact.attribute_key} {fact.attribute_value} {fact.provenance}".lower()
            for kw in query.keywords:
                if kw.lower() in haystack:
                    kw_hits += 1
            if kw_hits > 0:
                score += min(30, kw_hits * 15)
                matched = True

        if not matched:
            return 0

        # Intent boost
        if query.intent == BiographicalIntentType.GROWTH_ERA:
            score += 15

        # Epistemic quality weighting
        if fact.canonical_status == CanonicalStatus.CANONICAL:
            score += 10
        elif fact.canonical_status == CanonicalStatus.PROVISIONAL:
            score += 5

        if fact.recall_level == RecallLevel.VIVID:
            score += 10
        elif fact.recall_level == RecallLevel.HAZY:
            score += 5
        elif fact.recall_level == RecallLevel.FRAGMENTARY:
            score += 2

        return min(100, max(0, score))

    def _score_event(self, event: LifeEventRecord, query: AutobiographicalQuery) -> int:
        if query.target_entity_id and event.event_id == query.target_entity_id:
            return 100

        matched = False
        score = 0

        # Era match
        if query.target_era is not None:
            if event.era == query.target_era:
                score += 30
                matched = True
            elif not query.keywords:
                return 0

        # Domain match
        if query.target_domain is not None:
            if event.domain == query.target_domain:
                score += 30
                matched = True
            elif not query.keywords and query.target_era is None:
                return 0

        # Keyword match
        if query.keywords:
            kw_hits = 0
            haystack = f"{event.headline} {event.summary} {event.location_anchor or ''}".lower()
            for kw in query.keywords:
                if kw.lower() in haystack:
                    kw_hits += 1
            if kw_hits > 0:
                score += min(30, kw_hits * 15)
                matched = True

        if not matched:
            return 0

        # Intent boost
        if query.intent in (BiographicalIntentType.LIFE_EVENT, BiographicalIntentType.GROWTH_ERA):
            score += 20

        # Epistemic quality weighting
        if event.canonical_status == CanonicalStatus.CANONICAL:
            score += 10
        elif event.canonical_status == CanonicalStatus.PROVISIONAL:
            score += 5

        if event.recall_level == RecallLevel.VIVID:
            score += 10
        elif event.recall_level == RecallLevel.HAZY:
            score += 5
        elif event.recall_level == RecallLevel.FRAGMENTARY:
            score += 2

        return min(100, max(0, score))

    def _score_preference(self, pref: PersonalPreference, query: AutobiographicalQuery) -> int:
        if query.target_entity_id and pref.preference_id == query.target_entity_id:
            return 100

        matched = False
        score = 0

        # Era acquired match
        if query.target_era is not None:
            if pref.era_acquired == query.target_era:
                score += 20
                matched = True
            elif not query.keywords and pref.object_name.lower() not in query.raw_query.lower():
                return 0

        # Keyword match
        if query.keywords:
            kw_hits = 0
            haystack = f"{pref.category} {pref.object_name}".lower()
            for kw in query.keywords:
                if kw.lower() in haystack:
                    kw_hits += 1
            if kw_hits > 0:
                score += min(40, kw_hits * 20)
                matched = True

        # Raw query direct match on object_name
        if pref.object_name.lower() in query.raw_query.lower():
            score += 35
            matched = True

        if not matched:
            return 0

        # Intent boost
        if query.intent in (BiographicalIntentType.PERSONAL_PREFERENCE, BiographicalIntentType.CAUSAL_ORIGIN):
            score += 25

        return min(100, max(0, score))

    def _score_contact(self, contact: SocialContactRecord, query: AutobiographicalQuery) -> int:
        if query.target_entity_id and contact.contact_id == query.target_entity_id:
            return 100

        matched = False
        score = 0

        if query.target_era is not None:
            if contact.era_first_met == query.target_era:
                score += 25
                matched = True
            elif not query.keywords:
                return 0

        if query.keywords:
            kw_hits = 0
            haystack = f"{contact.display_name} {contact.relation_role}".lower()
            for kw in query.keywords:
                if kw.lower() in haystack:
                    kw_hits += 1
            if kw_hits > 0:
                score += min(30, kw_hits * 15)
                matched = True

        if not matched:
            return 0

        if query.intent == BiographicalIntentType.SOCIAL_TIE:
            score += 30

        return min(100, max(0, score))

        if query.keywords:
            kw_hits = 0
            haystack = f"{contact.display_name} {contact.relation_role}".lower()
            for kw in query.keywords:
                if kw.lower() in haystack:
                    kw_hits += 1
            score += min(30, kw_hits * 15)

        return min(100, max(0, score))
