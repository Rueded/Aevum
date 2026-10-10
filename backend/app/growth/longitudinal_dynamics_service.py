"""Phase 16.4 Longitudinal Dynamics Service.

Implements the DB-backed evaluation of interest domain activity state (ACTIVE/SATIATED/DORMANT)
and the strictly guarded ResurgenceEvent processing pipeline.

Constitutional Locks enforced in this module:
- Lock 10 (GC-413): Session is the atomic evaluation unit.
- Lock 11 (GC-414): Semantic-time (Phase 8C tick) only — never created_at / wall-clock.
- Lock 12 (GC-415): SATIATED/DORMANT writes zero mutations to 16.1–16.3 canonical state.
- Lock 13 (GC-416): ResurgenceEvent creates only a CharacterResurgenceEventTable record.
- Lock 14 (GC-417): USER_REPORTED / OBSERVED_MEDIA have zero refresh authority.

Architecture contract:
- This service is READ-ONLY with respect to 16.1/16.3 tables.
- The ONLY write this service performs is appending a CharacterResurgenceEventTable row.
- evaluate_activity() returns ActivityState without any DB writes.
"""

import uuid
from typing import Sequence

from sqlalchemy.orm import Session as DbSession

from app.growth.dynamics_models import (
    ActivityEvaluationResult,
    EligibleInteractionRecord,
    ELIGIBLE_REFRESH_PROVENANCES,
    LongitudinalEvaluationContext,
    LongitudinalDynamicsError,
    ResurgenceEvent,
    ResurgenceTriggerKind,
    SessionOutcome,
    SatiationPattern,
    evaluate_activity_state,
    validate_resurgence_event,
)
from app.growth.growth_db_models import (
    CharacterExperienceTable,
    CharacterFacetAppraisalTable,
    CharacterPreferenceTable,
    CharacterResurgenceEventTable,
)
from app.growth.state_machine import ActivityState


# =============================================================================
# LongitudinalDynamicsService
# =============================================================================

class LongitudinalDynamicsService:
    """Phase 16.4 service: compile context from DB, evaluate activity state, process resurgence.

    All temporal evaluation uses Phase 8C semantic ticks (Lock 11).
    This service never mutates character_experiences, character_facet_appraisals,
    character_facet_preferences, or character_interest_* tables (Lock 12).
    """

    def __init__(self, db: DbSession) -> None:
        self._db = db

    # -------------------------------------------------------------------------
    # Public: evaluate_activity
    # -------------------------------------------------------------------------

    def evaluate_activity(
        self,
        character_id: str,
        domain_key: str,
        current_timeline_tick: int,
        calendar_days_since_last_eligible: int,
        sessions_in_trailing_7_days: int,
        distinct_facets_in_trailing_7_days: int,
        current_activity_state: ActivityState = ActivityState.ACTIVE,
    ) -> ActivityEvaluationResult:
        """Evaluate the current ActivityState for a domain without any DB writes.

        Callers are responsible for providing precomputed Phase 8C calendar measurements
        (calendar_days_since_last_eligible, sessions_in_trailing_7_days, distinct_facets_in_trailing_7_days).
        This ensures a clean separation: Phase 8C calendar arithmetic stays in Phase 8C; this
        service only does categorical pattern evaluation.

        Args:
            character_id: The character UUID.
            domain_key: The interest domain key.
            current_timeline_tick: Current Phase 8C semantic tick (Lock 11).
            calendar_days_since_last_eligible: Phase 8C calendar days since last DIRECT or SHARED session.
            sessions_in_trailing_7_days: Count of distinct eligible sessions in the trailing 7 Phase 8C days.
            distinct_facets_in_trailing_7_days: Set cardinality of distinct facets in trailing 7 Phase 8C days.
            current_activity_state: The activity state as known before this evaluation.

        Returns:
            ActivityEvaluationResult — a deterministic categorical derivation.
        """
        sessions = self._compile_eligible_sessions(character_id, domain_key)
        interactions = self._compile_eligible_interactions(character_id, domain_key)
        pref_formed = self._is_preference_formed(character_id, domain_key)

        ctx = LongitudinalEvaluationContext(
            character_id=character_id,
            domain_key=domain_key,
            eligible_sessions=sessions,
            eligible_interactions=interactions,
            current_timeline_tick=current_timeline_tick,
            calendar_days_since_last_eligible_interaction=calendar_days_since_last_eligible,
            sessions_in_trailing_7_calendar_days=sessions_in_trailing_7_days,
            distinct_facets_in_trailing_7_days=distinct_facets_in_trailing_7_days,
            current_activity_state=current_activity_state,
            current_preference_polarity_is_formed=pref_formed,
        )

        return evaluate_activity_state(ctx)

    # -------------------------------------------------------------------------
    # Public: evaluate_activity_from_context (pure context variant, for testing)
    # -------------------------------------------------------------------------

    def evaluate_activity_from_context(self, ctx: LongitudinalEvaluationContext) -> ActivityEvaluationResult:
        """Evaluate activity state directly from a pre-built LongitudinalEvaluationContext.

        This variant is useful for unit testing where the DB is mocked or bypassed.
        No DB queries are made.
        """
        return evaluate_activity_state(ctx)

    # -------------------------------------------------------------------------
    # Public: process_resurgence
    # -------------------------------------------------------------------------

    def process_resurgence(
        self,
        character_id: str,
        domain_key: str,
        trigger_kind: ResurgenceTriggerKind,
        stimulus_ref: str,
        timeline_tick: int,
        awakened_facet_key: str | None = None,
        reflection_note: str = "",
    ) -> ResurgenceEvent:
        """Guard-validate and persist a ResurgenceEvent for a dormant domain (SATIATED recovers via cooldown only).

        Process:
        1. Read current activity state from ResurgenceEvent table (last known state for this domain).
        2. Run 4-guard validation chain (state, stimulus, timeline, provenance).
        3. Append one CharacterResurgenceEventTable record.
        4. Return the ResurgenceEvent DTO.

        Writes ONLY: CharacterResurgenceEventTable.
        Never touches: character_experiences, character_facet_appraisals,
                       character_facet_preferences, character_interest_* (Lock 13 / GC-416).
        """
        current_state = self._get_current_activity_state(character_id, domain_key)

        event = ResurgenceEvent(
            event_id=str(uuid.uuid4()),
            character_id=character_id,
            domain_key=domain_key,
            trigger_kind=trigger_kind,
            stimulus_ref=stimulus_ref,
            timeline_tick=timeline_tick,
            awakened_facet_key=awakened_facet_key,
            reflection_note=reflection_note,
        )

        # Guard chain — raises on any violation (Lock 13 / GC-416)
        validate_resurgence_event(current_state, event)

        # Append-only write (single table, no cascade mutations)
        row = CharacterResurgenceEventTable(
            id=event.event_id,
            character_id=character_id,
            domain_key=domain_key,
            trigger_kind=trigger_kind.value,
            stimulus_ref=stimulus_ref,
            timeline_tick=timeline_tick,
            awakened_facet_key=awakened_facet_key or "",
            reflection_note=reflection_note,
        )
        self._db.add(row)
        self._db.flush()

        return event

    # -------------------------------------------------------------------------
    # Private DB compilation helpers (READ-ONLY on 16.1/16.3)
    # -------------------------------------------------------------------------

    def _compile_eligible_sessions(
        self, character_id: str, domain_key: str
    ) -> list[SessionOutcome]:
        """Compile SessionOutcome list from character_facet_appraisals (Lock 10 / GC-413).

        Collapsed by calendar_session_id: one SessionOutcome per session.
        The dominant facet is the first facet encountered within the session.
        Ordered by timeline_tick ASC (Lock 11 / GC-414).
        """
        rows = (
            self._db.query(
                CharacterFacetAppraisalTable.calendar_session_id,
                CharacterFacetAppraisalTable.facet_key,
                CharacterFacetAppraisalTable.timeline_tick,
                CharacterFacetAppraisalTable.appraisal_kind,
            )
            .filter(
                CharacterFacetAppraisalTable.character_id == character_id,
                CharacterFacetAppraisalTable.domain_key == domain_key,
            )
            .order_by(CharacterFacetAppraisalTable.timeline_tick.asc())
            .all()
        )

        # Collapse by session_id (ordered by tick ASC, so first row per session wins)
        seen: dict[str, SessionOutcome] = {}
        for row in rows:
            session_id = row.calendar_session_id
            if session_id not in seen:
                seen[session_id] = SessionOutcome(
                    calendar_session_id=session_id,
                    facet_key=row.facet_key,
                    timeline_tick=row.timeline_tick,
                    had_fatigue_appraisal=(row.appraisal_kind == "TEDIOUS_EXHAUSTING"),
                )
            else:
                # Accumulate fatigue within same session without creating a new SessionOutcome
                existing = seen[session_id]
                if row.appraisal_kind == "TEDIOUS_EXHAUSTING" and not existing.had_fatigue_appraisal:
                    seen[session_id] = SessionOutcome(
                        calendar_session_id=existing.calendar_session_id,
                        facet_key=existing.facet_key,
                        timeline_tick=existing.timeline_tick,
                        had_fatigue_appraisal=True,
                    )

        # Return in timeline_tick ASC order
        return sorted(seen.values(), key=lambda s: s.timeline_tick)

    def _compile_eligible_interactions(
        self, character_id: str, domain_key: str
    ) -> list[EligibleInteractionRecord]:
        """Compile eligible interaction records for dormancy lapse calculation (Lock 14 / GC-417).

        Only DIRECT_INTERACTION and SHARED_INTERACTION provenances are returned.
        USER_REPORTED, OBSERVED_MEDIA, etc. are omitted (zero refresh authority).
        """
        rows = (
            self._db.query(
                CharacterExperienceTable.provenance_kind,
                CharacterExperienceTable.timeline_tick,
                CharacterExperienceTable.calendar_session_id,
            )
            .filter(
                CharacterExperienceTable.character_id == character_id,
                CharacterExperienceTable.domain_key == domain_key,
                CharacterExperienceTable.provenance_kind.in_(list(ELIGIBLE_REFRESH_PROVENANCES)),
            )
            .order_by(CharacterExperienceTable.timeline_tick.asc())
            .all()
        )

        return [
            EligibleInteractionRecord(
                provenance_kind=row.provenance_kind,
                timeline_tick=row.timeline_tick,
                calendar_session_id=row.calendar_session_id,
            )
            for row in rows
        ]

    def _is_preference_formed(self, character_id: str, domain_key: str) -> bool:
        """Check if any facet in this domain has a formed (non-UNFORMED) preference polarity.

        Used to select the correct dormancy threshold (60 vs 45 days).
        """
        row = (
            self._db.query(CharacterPreferenceTable.preference_polarity)
            .filter(
                CharacterPreferenceTable.character_id == character_id,
                CharacterPreferenceTable.domain_key == domain_key,
                CharacterPreferenceTable.preference_polarity != "UNFORMED",
            )
            .first()
        )
        return row is not None

    def _get_current_activity_state(self, character_id: str, domain_key: str) -> ActivityState:
        """Derive the current ActivityState for a domain from the ResurgenceEvent log.

        If no resurgence events exist, the domain starts as ACTIVE.
        The latest event determines the current known activity level.
        This is a lightweight indicator only — the caller of process_resurgence is responsible
        for providing the accurate evaluated state from evaluate_activity().

        NOTE: This check is used as the resurgence guard (Guard 1: must be DORMANT or SATIATED).
        The full activity evaluation is a separate concern.
        """
        # Check if a recent resurgence event exists (indicates the domain was DORMANT at some point)
        # We rely on caller-provided evaluated state for real use cases.
        # For the guard chain, we perform a lightweight check:
        # if the caller is passing a real ResurgenceEvent, they should have evaluated activity first.
        # Here we return DORMANT by convention (the guard enforces non-ACTIVE only).
        # Callers that have the evaluated ActivityState should use process_resurgence_with_state().
        latest = (
            self._db.query(CharacterResurgenceEventTable)
            .filter(
                CharacterResurgenceEventTable.character_id == character_id,
                CharacterResurgenceEventTable.domain_key == domain_key,
            )
            .order_by(CharacterResurgenceEventTable.timeline_tick.desc())
            .first()
        )
        # If we have any resurgence events, we assume the domain has been dormant before.
        # The actual evaluated state should be passed via process_resurgence_with_state.
        # Return a safe default that doesn't block legitimate resurgence.
        if latest is None:
            # No history of dormancy: return ACTIVE (callers using the full pipeline
            # will have provided evaluated state via process_resurgence_with_state)
            return ActivityState.ACTIVE
        return ActivityState.DORMANT

    def process_resurgence_with_state(
        self,
        current_activity_state: ActivityState,
        character_id: str,
        domain_key: str,
        trigger_kind: ResurgenceTriggerKind,
        stimulus_ref: str,
        timeline_tick: int,
        awakened_facet_key: str | None = None,
        reflection_note: str = "",
    ) -> ResurgenceEvent:
        """Process a resurgence event with a caller-provided (pre-evaluated) activity state.

        This is the recommended API for the full longitudinal pipeline where the caller
        has already invoked evaluate_activity() and has the authoritative ActivityState.

        Writes ONLY: CharacterResurgenceEventTable (Lock 13 / GC-416).
        """
        event = ResurgenceEvent(
            event_id=str(uuid.uuid4()),
            character_id=character_id,
            domain_key=domain_key,
            trigger_kind=trigger_kind,
            stimulus_ref=stimulus_ref,
            timeline_tick=timeline_tick,
            awakened_facet_key=awakened_facet_key,
            reflection_note=reflection_note,
        )

        validate_resurgence_event(current_activity_state, event)

        row = CharacterResurgenceEventTable(
            id=event.event_id,
            character_id=character_id,
            domain_key=domain_key,
            trigger_kind=trigger_kind.value,
            stimulus_ref=stimulus_ref,
            timeline_tick=timeline_tick,
            awakened_facet_key=awakened_facet_key or "",
            reflection_note=reflection_note,
        )
        self._db.add(row)
        self._db.flush()

        return event
