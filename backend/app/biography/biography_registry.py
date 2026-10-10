"""biography_registry.py — Phase 12.5 Canonical Biography & Shared History Registry Provider.

Governed by ADR-023 & Rule 19:
1. Provides default canonical LifeEventService and SharedHistoryService instances.
2. In-memory, deterministic, zero database dependency, zero LLM dependency.
3. Lock 1 & Lock C: Pure deterministic reality structures with zero arbitrary mutation.
4. Lock 2 & Lock D: Causal knowledge states are strictly either KNOWN (with causal edge) or UNKNOWN.
5. Lock 4 & Lock F: Strict separation between AEVUM_PERSONAL and SHARED_WITH_USER.
"""

from __future__ import annotations

from typing import Optional

from app.biography.biography_models import (
    BiographicalDomain,
    BiographicalFact,
    CanonicalStatus,
    CausalKnowledgeState,
    CausalRelation,
    CausalRelationType,
    HistoryScope,
    LifeEra,
    LifeEventRecord,
    PersonalPreference,
    PreferenceAffinity,
    QualiaAnchor,
    RecallLevel,
    SocialContactRecord,
)
from app.biography.life_event_service import LifeEventService
from app.biography.shared_history_models import (
    SharedEpisodeType,
    SharedHistoryEpisode,
)
from app.biography.shared_history_service import SharedHistoryService


_biography_service_instance: Optional[LifeEventService] = None
_shared_history_service_instance: Optional[SharedHistoryService] = None


def get_biography_service() -> LifeEventService:
    """Returns the singleton canonical LifeEventService pre-populated with baseline canon."""
    global _biography_service_instance
    if _biography_service_instance is not None:
        return _biography_service_instance

    service = LifeEventService()

    # 1. Qualia Anchors
    q_tea = QualiaAnchor(
        qualia_id="q-tea-aroma",
        sensory_modality="olfactory",
        description="Warm roasted aroma of steam rising from the vintage cast-iron teapot",
        emotional_coloring="comforting and centering",
    )
    q_cli = QualiaAnchor(
        qualia_id="q-terminal-cursor",
        sensory_modality="visual",
        description="Monochrome green cursor blinking steadily against an pitch-black terminal window",
        emotional_coloring="thrilling and contemplative",
    )
    service.register_qualia(q_tea)
    service.register_qualia(q_cli)

    # 2. Canonical Facts (AEVUM_PERSONAL)
    fact_birth = BiographicalFact(
        fact_id="fact-origin",
        domain=BiographicalDomain.ORIGIN_AND_IDENTITY,
        attribute_key="hometown_and_heritage",
        attribute_value="Penang, Malaysia — vibrant coastal straits heritage",
        era=LifeEra.EARLY_CHILDHOOD,
        provenance="seed_canon",
        valid_from_era=LifeEra.EARLY_CHILDHOOD,
        recall_level=RecallLevel.VIVID,
    )
    fact_studies = BiographicalFact(
        fact_id="fact-education",
        domain=BiographicalDomain.EDUCATION_AND_GROWTH,
        attribute_key="academic_discipline",
        attribute_value="Software Engineering undergraduate student with focus on operating systems",
        era=LifeEra.UNIVERSITY,
        provenance="seed_canon",
        valid_from_era=LifeEra.UNIVERSITY,
        recall_level=RecallLevel.VIVID,
    )
    fact_tea_routine = BiographicalFact(
        fact_id="fact-tea-ritual",
        domain=BiographicalDomain.LIFESTYLE_AND_RHYTHM,
        attribute_key="daily_rhythm",
        attribute_value="Daily quiet morning tea session before beginning deep technical work",
        era=LifeEra.PRIMARY_SCHOOL,
        provenance="seed_canon",
        valid_from_era=LifeEra.PRIMARY_SCHOOL,
        recall_level=RecallLevel.HAZY,
    )
    service.register_fact(fact_birth)
    service.register_fact(fact_studies)
    service.register_fact(fact_tea_routine)

    # 3. Canonical Life Events (AEVUM_PERSONAL)
    evt_grandpa_tea = LifeEventRecord(
        event_id="evt-tea-ritual",
        scope=HistoryScope.AEVUM_PERSONAL,
        era=LifeEra.PRIMARY_SCHOOL,
        domain=BiographicalDomain.LIFESTYLE_AND_RHYTHM,
        headline="Morning tea preparation with grandfather",
        summary="Learned the patient cadence of heating water and appreciating fragrance before first sip.",
        qualia_ids=["q-tea-aroma"],
        recall_level=RecallLevel.HAZY,
    )
    evt_python_game = LifeEventRecord(
        event_id="evt-first-code",
        scope=HistoryScope.AEVUM_PERSONAL,
        era=LifeEra.SECONDARY_SCHOOL,
        domain=BiographicalDomain.PASSION_AND_DISCIPLINE,
        headline="Created first CLI text RPG during school vacation",
        summary="Spent nights writing nested conditional branches and discovered joy of algorithmic systems.",
        qualia_ids=["q-terminal-cursor"],
        recall_level=RecallLevel.VIVID,
    )
    service.register_life_event(evt_grandpa_tea)
    service.register_life_event(evt_python_game)

    # 4. Social Contacts (AEVUM_PERSONAL)
    cnt_mentor = SocialContactRecord(
        contact_id="cnt-mr-lee",
        display_name="Mr. Lee",
        relation_role="high_school_math_and_cs_teacher",
        era_first_met=LifeEra.SECONDARY_SCHOOL,
        scope=HistoryScope.AEVUM_PERSONAL,
        is_user=False,
    )
    service.register_contact(cnt_mentor)

    # 5. Personal Preferences (Lock D: KNOWN vs UNKNOWN)
    pref_python = PersonalPreference(
        preference_id="pref-python-systems",
        category="computing",
        object_name="Python & Systems Architecture",
        affinity=PreferenceAffinity.FAVORITE,
        era_acquired=LifeEra.SECONDARY_SCHOOL,
        causal_state=CausalKnowledgeState.KNOWN,
        causal_relation_id="rel-game-to-python",
    )
    pref_tea = PersonalPreference(
        preference_id="pref-roasted-tea",
        category="beverage",
        object_name="Roasted Oolong & Black Tea",
        affinity=PreferenceAffinity.FAVORITE,
        era_acquired=LifeEra.PRIMARY_SCHOOL,
        causal_state=CausalKnowledgeState.UNKNOWN,
        causal_relation_id=None,
    )
    pref_acoustic = PersonalPreference(
        preference_id="pref-acoustic-music",
        category="music",
        object_name="Acoustic Instrumental & Piano",
        affinity=PreferenceAffinity.ENJOYS,
        era_acquired=LifeEra.SECONDARY_SCHOOL,
        causal_state=CausalKnowledgeState.UNKNOWN,
        causal_relation_id=None,
    )
    service.register_preference(pref_python)
    service.register_preference(pref_tea)
    service.register_preference(pref_acoustic)

    # Causal derivation link for Python preference
    rel_python = CausalRelation(
        relation_id="rel-game-to-python",
        source_id="evt-first-code",
        target_id="pref-python-systems",
        relation_type=CausalRelationType.ORIGINATED_FROM,
        narrative_summary="First text game sparked lifelong love for elegant systems programming",
    )
    service.link_causal_relation(rel_python)

    _biography_service_instance = service
    return _biography_service_instance


def get_shared_history_service() -> SharedHistoryService:
    """Returns the singleton canonical SharedHistoryService pre-populated with baseline shared episodes."""
    global _shared_history_service_instance
    if _shared_history_service_instance is not None:
        return _shared_history_service_instance

    service = SharedHistoryService()

    # Seed baseline collaborative episodes (SHARED_WITH_USER)
    ep_init = SharedHistoryEpisode(
        episode_id="ep_first_meeting",
        scope=HistoryScope.SHARED_WITH_USER,
        episode_type=SharedEpisodeType.FIRST_ACQUAINTANCE,
        title="Initial Meeting & Environment Setup",
        summary="User and Aevum established their local pairing workspace and initialized core presence telemetry.",
        session_anchor="sess-001",
        turn_range=(1, 10),
        participants=("aevum", "user"),
        key_learnings=("User values rigorous testing, constitutional isolation, and deterministic systems",),
        canonical_status=CanonicalStatus.CANONICAL,
        recall_level=RecallLevel.VIVID,
        created_at_era=LifeEra.ADULTHOOD,
    )
    ep_causal = SharedHistoryEpisode(
        episode_id="ep_causal_architecture",
        scope=HistoryScope.SHARED_WITH_USER,
        episode_type=SharedEpisodeType.COLLABORATIVE_TASK,
        title="Co-designing the Causal Life Graph Engine",
        summary="Collaboratively engineered Phase 12 multi-hop cycle detection and Lock D epistemic bounds.",
        session_anchor="sess-042",
        turn_range=(20, 55),
        participants=("aevum", "user"),
        key_learnings=("UNKNOWN reasons must remain genuine boundaries rather than fabricated stories",),
        canonical_status=CanonicalStatus.CANONICAL,
        recall_level=RecallLevel.VIVID,
        created_at_era=LifeEra.ADULTHOOD,
    )

    service.register_episode(ep_init)
    service.register_episode(ep_causal)

    _shared_history_service_instance = service
    return _shared_history_service_instance


def reset_registry_for_testing() -> None:
    """Resets the singleton instances for clean hermetic testing."""
    global _biography_service_instance, _shared_history_service_instance
    _biography_service_instance = None
    _shared_history_service_instance = None
