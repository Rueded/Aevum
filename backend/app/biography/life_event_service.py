"""life_event_service.py — Phase 12.2 Life Event & Causal Explanation Read Service.

Governed by ADR-023:
1. Lock A & B: Delegates causal explanations to CausalExplanationGraph ensuring acyclic DAG.
2. Lock C: Pure read and in-memory query service; zero canonical biography mutation authority.
3. Lock D: Preserves CausalKnowledgeState.UNKNOWN without confabulating causes.
4. Lock F: Respects HistoryScope segregation between personal history and shared journey.
"""

from __future__ import annotations

from typing import Optional

from app.biography.biography_models import (
    BiographicalDomain,
    BiographicalFact,
    CausalKnowledgeState,
    CausalRelation,
    HistoryScope,
    LifeEra,
    LifeEventRecord,
    PersonalPreference,
    QualiaAnchor,
    SocialContactRecord,
)
from app.biography.causal_graph import (
    CausalExplanationGraph,
    CausalExplanationPath,
    CausalExplanationStep,
)


class LifeEventService:
    """Read-side service orchestrating life events, facts, preferences, and causal derivations."""

    def __init__(self, causal_graph: Optional[CausalExplanationGraph] = None) -> None:
        self._graph = causal_graph or CausalExplanationGraph()
        self._events: dict[str, LifeEventRecord] = {}
        self._facts: dict[str, BiographicalFact] = {}
        self._preferences: dict[str, PersonalPreference] = {}
        self._qualia: dict[str, QualiaAnchor] = {}
        self._contacts: dict[str, SocialContactRecord] = {}

    @property
    def causal_graph(self) -> CausalExplanationGraph:
        """Direct access to the underlying causal explanation graph."""
        return self._graph

    # ========================================================================
    # Registration & Graph Synchronization
    # ========================================================================

    def register_life_event(self, event: LifeEventRecord) -> None:
        """Registers a LifeEventRecord and syncs it into the causal explanation graph."""
        self._events[event.event_id] = event
        self._graph.add_node_from_event(event)

    def register_fact(self, fact: BiographicalFact) -> None:
        """Registers a BiographicalFact and syncs it into the causal explanation graph."""
        self._facts[fact.fact_id] = fact
        self._graph.add_node_from_fact(fact)

    def register_preference(self, preference: PersonalPreference) -> None:
        """Registers a PersonalPreference and syncs it into the causal explanation graph."""
        self._preferences[preference.preference_id] = preference
        self._graph.add_node_from_preference(preference)

    def register_qualia(self, qualia: QualiaAnchor) -> None:
        """Registers a sensory QualiaAnchor."""
        self._qualia[qualia.qualia_id] = qualia

    def register_contact(self, contact: SocialContactRecord) -> None:
        """Registers a SocialContactRecord."""
        self._contacts[contact.contact_id] = contact

    def link_causal_relation(self, relation: CausalRelation) -> None:
        """Links a causal derivation relation in the causal explanation graph (Lock A, Lock B)."""
        self._graph.add_relation(relation)

    # ========================================================================
    # Query & Retrieval
    # ========================================================================

    def get_event_by_id(self, event_id: str) -> Optional[LifeEventRecord]:
        """Retrieves a life event by its ID."""
        return self._events.get(event_id)

    def get_fact_by_id(self, fact_id: str) -> Optional[BiographicalFact]:
        """Retrieves a biographical fact by its ID."""
        return self._facts.get(fact_id)

    def get_preference_by_id(self, preference_id: str) -> Optional[PersonalPreference]:
        """Retrieves a personal preference by its ID."""
        return self._preferences.get(preference_id)

    def get_qualia_by_id(self, qualia_id: str) -> Optional[QualiaAnchor]:
        """Retrieves a qualia anchor by its ID."""
        return self._qualia.get(qualia_id)

    def get_contact_by_id(self, contact_id: str) -> Optional[SocialContactRecord]:
        """Retrieves a social contact by its ID."""
        return self._contacts.get(contact_id)

    def get_all_facts(
        self,
        scope: Optional[HistoryScope] = None,
    ) -> list[BiographicalFact]:
        """Retrieves all registered facts, optionally filtered by HistoryScope."""
        if scope is None:
            return list(self._facts.values())
        return [f for f in self._facts.values() if f.scope == scope]

    def get_all_events(
        self,
        scope: Optional[HistoryScope] = None,
    ) -> list[LifeEventRecord]:
        """Retrieves all registered life events, optionally filtered by HistoryScope."""
        if scope is None:
            return list(self._events.values())
        return [e for e in self._events.values() if e.scope == scope]

    def get_all_preferences(self) -> list[PersonalPreference]:
        """Retrieves all registered personal preferences."""
        return list(self._preferences.values())

    def get_all_qualia(self) -> list[QualiaAnchor]:
        """Retrieves all registered qualia anchors."""
        return list(self._qualia.values())

    def get_all_contacts(
        self,
        scope: Optional[HistoryScope] = None,
    ) -> list[SocialContactRecord]:
        """Retrieves all registered social contacts, optionally filtered by HistoryScope."""
        if scope is None:
            return list(self._contacts.values())
        return [c for c in self._contacts.values() if c.scope == scope]

    def get_life_events_by_era(
        self,
        era: LifeEra,
        scope: HistoryScope = HistoryScope.AEVUM_PERSONAL,
    ) -> list[LifeEventRecord]:
        """Retrieves life events filtered by LifeEra and HistoryScope (Lock F)."""
        return [
            evt for evt in self._events.values()
            if evt.era == era and evt.scope == scope
        ]

    def get_life_events_by_domain(
        self,
        domain: BiographicalDomain,
        scope: HistoryScope = HistoryScope.AEVUM_PERSONAL,
    ) -> list[LifeEventRecord]:
        """Retrieves life events filtered by BiographicalDomain and HistoryScope."""
        return [
            evt for evt in self._events.values()
            if evt.domain == domain and evt.scope == scope
        ]

    def get_facts_by_domain(
        self,
        domain: BiographicalDomain,
        scope: HistoryScope = HistoryScope.AEVUM_PERSONAL,
    ) -> list[BiographicalFact]:
        """Retrieves biographical facts filtered by domain and scope."""
        return [
            fact for fact in self._facts.values()
            if fact.domain == domain and fact.scope == scope
        ]

    def get_preferences_by_category(self, category: str) -> list[PersonalPreference]:
        """Retrieves personal preferences by category."""
        return [
            pref for pref in self._preferences.values()
            if pref.category.lower() == category.lower()
        ]

    def get_qualia_for_event(self, event_id: str) -> list[QualiaAnchor]:
        """Retrieves all sensory QualiaAnchors associated with a given life event."""
        event = self._events.get(event_id)
        if not event:
            return []
        return [
            self._qualia[qid] for qid in event.qualia_ids
            if qid in self._qualia
        ]

    # ========================================================================
    # Causal Explanation Derivation
    # ========================================================================

    def explain_preference(self, preference_id: str) -> CausalExplanationPath:
        """Explains why a preference exists, strictly honoring Lock D."""
        pref = self._preferences.get(preference_id)
        if not pref:
            return CausalExplanationPath(
                target_id=preference_id,
                causal_state=CausalKnowledgeState.UNKNOWN,
                is_grounded=False,
                steps=[],
                root_cause_ids=[],
                terminal_reason="PREFERENCE_NOT_FOUND",
            )
        return self._graph.explain_preference(pref)

    def get_causal_chain(self, target_id: str) -> list[CausalExplanationStep]:
        """Returns the backward causal explanation chain leading up to target_id."""
        return self._graph.get_causal_chain(target_id)

    def get_event_causal_consequences(self, event_id: str) -> list[CausalExplanationStep]:
        """Returns the downstream causal consequences resulting from an event."""
        return self._graph.get_downstream_effects(event_id)
