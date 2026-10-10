"""Phase 16.4 Golden Tests — Longitudinal Dynamics: Satiation, Fatigue, Dormancy & Resurgence.

G50–G65: Covers all constitutional locks for Phase 16.4.

Constitutional Locks tested:
- Lock 10 (GC-413): Session-Unit Fatigue Integrity
- Lock 11 (GC-414): Semantic-Time-Only Longitudinal Evaluation
- Lock 12 (GC-415): Activity-State Non-Destructiveness
- Lock 13 (GC-416): Resurgence != Experience
- Lock 14 (GC-417): User-Reported Activity Cannot Refresh Aevum Activity

Key test invariants:
- G57/G58: Snapshot before/after — DORMANT/SATIATED never delete or modify 16.1–16.3 state.
- G62: ResurgenceEvent creates 0 experience, 0 appraisal, 0 preference delta.
- All tests: 0 floats, 0 wall-clock datetime comparisons, 0 LLM calls.
"""

import uuid
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session as DbSession

from app.db.session import Base
from app.growth.state_machine import ActivityState
from app.growth.dynamics_models import (
    ActivityEvaluationResult,
    DORMANCY_LAPSE_DAYS_FORMED,
    DORMANCY_LAPSE_DAYS_UNFORMED,
    ELIGIBLE_REFRESH_PROVENANCES,
    EligibleInteractionRecord,
    InvalidResurgenceStateError,
    LongitudinalDynamicsError,
    LongitudinalEvaluationContext,
    ResurgenceEvent,
    ResurgenceTriggerKind,
    SATIATION_COOLOFF_DAYS,
    SATIATION_DENSITY_FATIGUE_IN_WINDOW,
    SATIATION_DENSITY_SESSIONS_7D,
    SATIATION_DENSITY_TAIL_WINDOW,
    SATIATION_DIVERSITY_FACET_MINIMUM,
    SATIATION_MONOTONY_FATIGUE_IN_WINDOW,
    SATIATION_MONOTONY_SESSION_STREAK,
    SATIATION_MONOTONY_TAIL_WINDOW,
    SatiationPattern,
    SessionOutcome,
    UnanchoredStimulusRefError,
    evaluate_activity_state,
    evaluate_dormancy,
    evaluate_satiation_cooloff,
    evaluate_satiation_pattern,
    validate_resurgence_event,
    _compute_consecutive_monotony_streak,
    _count_fatigue_in_tail,
)
from app.growth.growth_db_models import (
    CharacterExperienceTable,
    CharacterFacetAppraisalTable,
    CharacterPreferenceTable,
    CharacterResurgenceEventTable,
    ResurgenceMutationProhibitedError,
)
from app.growth.longitudinal_dynamics_service import LongitudinalDynamicsService


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def engine():
    """In-memory SQLite engine for isolation (no disk I/O, no network)."""
    eng = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture(scope="function")
def db(engine):
    """Transactional session that rolls back after each test."""
    with DbSession(engine) as session:
        yield session


@pytest.fixture
def char_id():
    return str(uuid.uuid4())


@pytest.fixture
def domain_key():
    return "video_games"


def _make_session(
    session_id: str,
    facet_key: str,
    tick: int,
    had_fatigue: bool = False,
) -> SessionOutcome:
    return SessionOutcome(
        calendar_session_id=session_id,
        facet_key=facet_key,
        timeline_tick=tick,
        had_fatigue_appraisal=had_fatigue,
    )


def _make_ctx(
    sessions=None,
    calendar_days_since_last_eligible=0,
    sessions_in_trailing_7_days=0,
    distinct_facets_in_trailing_7_days=0,
    current_activity_state=ActivityState.ACTIVE,
    current_preference_polarity_is_formed=True,
    current_timeline_tick=1000,
    character_id="char-x",
    domain_key="video_games",
) -> LongitudinalEvaluationContext:
    return LongitudinalEvaluationContext(
        character_id=character_id,
        domain_key=domain_key,
        eligible_sessions=sessions or [],
        eligible_interactions=[],
        current_timeline_tick=current_timeline_tick,
        calendar_days_since_last_eligible_interaction=calendar_days_since_last_eligible,
        sessions_in_trailing_7_calendar_days=sessions_in_trailing_7_days,
        distinct_facets_in_trailing_7_days=distinct_facets_in_trailing_7_days,
        current_activity_state=current_activity_state,
        current_preference_polarity_is_formed=current_preference_polarity_is_formed,
    )


# ─────────────────────────────────────────────────────────────────────────────
# G50: Threshold constants are integers (Permanent Note A — Zero Floats)
# ─────────────────────────────────────────────────────────────────────────────

def test_g50_threshold_constants_are_integers():
    """G50: All policy threshold constants are int type (zero float invariant)."""
    assert isinstance(SATIATION_MONOTONY_SESSION_STREAK, int), "SATIATION_MONOTONY_SESSION_STREAK must be int"
    assert isinstance(SATIATION_MONOTONY_TAIL_WINDOW, int), "SATIATION_MONOTONY_TAIL_WINDOW must be int"
    assert isinstance(SATIATION_MONOTONY_FATIGUE_IN_WINDOW, int), "SATIATION_MONOTONY_FATIGUE_IN_WINDOW must be int"
    assert isinstance(SATIATION_DENSITY_SESSIONS_7D, int), "SATIATION_DENSITY_SESSIONS_7D must be int"
    assert isinstance(SATIATION_DENSITY_TAIL_WINDOW, int), "SATIATION_DENSITY_TAIL_WINDOW must be int"
    assert isinstance(SATIATION_DENSITY_FATIGUE_IN_WINDOW, int), "SATIATION_DENSITY_FATIGUE_IN_WINDOW must be int"
    assert isinstance(SATIATION_DIVERSITY_FACET_MINIMUM, int), "SATIATION_DIVERSITY_FACET_MINIMUM must be int"
    assert isinstance(SATIATION_COOLOFF_DAYS, int), "SATIATION_COOLOFF_DAYS must be int"
    assert isinstance(DORMANCY_LAPSE_DAYS_FORMED, int), "DORMANCY_LAPSE_DAYS_FORMED must be int"
    assert isinstance(DORMANCY_LAPSE_DAYS_UNFORMED, int), "DORMANCY_LAPSE_DAYS_UNFORMED must be int"


# ─────────────────────────────────────────────────────────────────────────────
# G51: Baseline — Active domain below all thresholds stays ACTIVE
# ─────────────────────────────────────────────────────────────────────────────

def test_g51_active_below_all_thresholds():
    """G51: Domain with normal engagement stays ACTIVE."""
    sessions = [
        _make_session("s1", "exploration", 100),
        _make_session("s2", "combat", 200),
        _make_session("s3", "exploration", 300),
    ]
    ctx = _make_ctx(sessions=sessions, calendar_days_since_last_eligible=2,
                    sessions_in_trailing_7_days=3, distinct_facets_in_trailing_7_days=2)
    result = evaluate_activity_state(ctx)
    assert result.resolved_activity_state == ActivityState.ACTIVE
    assert result.satiation_pattern == SatiationPattern.NONE


# ─────────────────────────────────────────────────────────────────────────────
# G52: Diversity anti-fatigue — 4+ distinct facets blocks Pattern 1 satiation
# ─────────────────────────────────────────────────────────────────────────────

def test_g52_diversity_blocks_acute_monotony():
    """G52: >= 4 distinct facets in window prevents Pattern 1 (Acute Monotony) satiation."""
    # 4 consecutive sessions with same facet PLUS 2/3 tail fatigue
    sessions = [
        _make_session("s1", "combat", 100, had_fatigue=False),
        _make_session("s2", "combat", 200, had_fatigue=False),
        _make_session("s3", "combat", 300, had_fatigue=True),
        _make_session("s4", "combat", 400, had_fatigue=True),
    ]
    # Without diversity protection: would be SATIATED (streak=4, fatigue=2/3)
    ctx_low_diversity = _make_ctx(
        sessions=sessions,
        calendar_days_since_last_eligible=0,
        sessions_in_trailing_7_days=4,
        distinct_facets_in_trailing_7_days=3,  # < 4 threshold → Pattern 1 can hold
    )
    result_low = evaluate_activity_state(ctx_low_diversity)
    assert result_low.resolved_activity_state == ActivityState.SATIATED
    assert result_low.satiation_pattern == SatiationPattern.ACUTE_MONOTONY

    # With diversity protection: >= 4 distinct facets => Pattern 1 blocked
    ctx_high_diversity = _make_ctx(
        sessions=sessions,
        calendar_days_since_last_eligible=0,
        sessions_in_trailing_7_days=4,
        distinct_facets_in_trailing_7_days=4,  # >= 4 threshold → Pattern 1 blocked
    )
    result_high = evaluate_activity_state(ctx_high_diversity)
    assert result_high.resolved_activity_state == ActivityState.ACTIVE


# ─────────────────────────────────────────────────────────────────────────────
# G53: Pattern 1 Satiation — Acute Monotony detected correctly
# ─────────────────────────────────────────────────────────────────────────────

def test_g53_acute_monotony_satiation_pattern_1():
    """G53: >= 4 consecutive same-facet sessions + >= 2/3 tail fatigue => SATIATED (Pattern 1)."""
    sessions = [
        _make_session("s1", "combat", 100, had_fatigue=False),
        _make_session("s2", "combat", 200, had_fatigue=False),
        _make_session("s3", "combat", 300, had_fatigue=True),
        _make_session("s4", "combat", 400, had_fatigue=True),
    ]
    ctx = _make_ctx(sessions=sessions, sessions_in_trailing_7_days=4,
                    distinct_facets_in_trailing_7_days=1)
    result = evaluate_activity_state(ctx)
    assert result.resolved_activity_state == ActivityState.SATIATED
    assert result.satiation_pattern == SatiationPattern.ACUTE_MONOTONY
    assert result.consecutive_monotony_streak == 4


# ─────────────────────────────────────────────────────────────────────────────
# G54: Pattern 2 Satiation — Hyper-Density detected correctly
# ─────────────────────────────────────────────────────────────────────────────

def test_g54_hyper_density_satiation_pattern_2():
    """G54: >= 7 sessions in 7 days + >= 3/5 tail fatigue => SATIATED (Pattern 2).

    Uses alternating facets to prevent Pattern 1 (Acute Monotony) from firing first,
    ensuring Pattern 2 (Hyper-Density) is the detected pattern.
    """
    facets = ["exploration", "combat", "crafting", "music", "story", "exploration", "combat"]
    sessions = [
        _make_session(f"s{i}", facets[i - 1], i * 10, had_fatigue=(i >= 5))
        for i in range(1, 8)
    ]
    # Pattern 1: alternating facets → streak = 1 (no monotony streak)
    # Pattern 2: 7 sessions in 7 days, tail 5 = s3..s7, fatigue = s5,s6,s7 → 3 >= threshold
    ctx = _make_ctx(sessions=sessions, sessions_in_trailing_7_days=7,
                    distinct_facets_in_trailing_7_days=5)  # 5 distinct facets
    result = evaluate_activity_state(ctx)
    assert result.resolved_activity_state == ActivityState.SATIATED
    assert result.satiation_pattern == SatiationPattern.HYPER_DENSITY


# ─────────────────────────────────────────────────────────────────────────────
# G55: Intervening different-facet session resets consecutive streak (Lock 10)
# ─────────────────────────────────────────────────────────────────────────────

def test_g55_intervening_session_resets_streak():
    """G55 (Lock 10 / GC-413): An other-facet session in the middle resets the consecutive counter."""
    sessions = [
        _make_session("s1", "combat", 100),
        _make_session("s2", "combat", 200),
        _make_session("s3", "exploration", 300),  # ← interrupts the streak
        _make_session("s4", "combat", 400, had_fatigue=True),
        _make_session("s5", "combat", 500, had_fatigue=True),
    ]
    # After interruption, streak = 2 (s4, s5) — NOT 4 → Pattern 1 cannot hold
    streak, _ = _compute_consecutive_monotony_streak(sessions)
    assert streak == 2

    ctx = _make_ctx(sessions=sessions, distinct_facets_in_trailing_7_days=2)
    result = evaluate_activity_state(ctx)
    # Streak only 2, so Pattern 1 cannot trigger (needs >= 4)
    assert result.resolved_activity_state == ActivityState.ACTIVE


# ─────────────────────────────────────────────────────────────────────────────
# G56: Dormancy entry — formed preference uses 60-day threshold (Lock 11 / GC-414)
# ─────────────────────────────────────────────────────────────────────────────

def test_g56_dormancy_formed_preference_60_day_threshold():
    """G56 (Lock 11 / GC-414): Formed preference => 60 calendar days for dormancy."""
    ctx_59 = _make_ctx(calendar_days_since_last_eligible=59, current_preference_polarity_is_formed=True)
    ctx_60 = _make_ctx(calendar_days_since_last_eligible=60, current_preference_polarity_is_formed=True)

    assert not evaluate_dormancy(ctx_59), "59 days should NOT trigger dormancy"
    assert evaluate_dormancy(ctx_60), "60 days MUST trigger dormancy"

    result_60 = evaluate_activity_state(ctx_60)
    assert result_60.resolved_activity_state == ActivityState.DORMANT


def test_g56b_dormancy_unformed_preference_45_day_threshold():
    """G56b: Unformed preference => 45 calendar days (lower threshold)."""
    ctx_44 = _make_ctx(calendar_days_since_last_eligible=44, current_preference_polarity_is_formed=False)
    ctx_45 = _make_ctx(calendar_days_since_last_eligible=45, current_preference_polarity_is_formed=False)

    assert not evaluate_dormancy(ctx_44), "44 days should NOT trigger dormancy (unformed)"
    assert evaluate_dormancy(ctx_45), "45 days MUST trigger dormancy (unformed)"


# ─────────────────────────────────────────────────────────────────────────────
# G57: Non-destructiveness — DORMANT does not modify 16.1–16.3 canonical state (Lock 12 / GC-415)
# ─────────────────────────────────────────────────────────────────────────────

def test_g57_dormant_state_is_non_destructive(db, char_id, domain_key, engine):
    """G57 (Lock 12 / GC-415): Snapshot before/after — evaluate_activity() for DORMANT domain
    does NOT delete, update, or modify character_experiences, character_facet_appraisals,
    character_facet_preferences rows. The 16.1–16.3 state is identical before and after."""

    # Seed a character_facet_preferences row to snapshot
    pref_row = CharacterPreferenceTable(
        id=str(uuid.uuid4()),
        character_id=char_id,
        domain_key=domain_key,
        facet_key="combat",
        preference_polarity="ENJOYED",
        stability_tier="STABLE",
        revision_kind="NONE",
        appraisal_count=5,
        distinct_session_count=3,
        last_evaluated_tick=500,
    )
    db.add(pref_row)
    db.flush()

    # SNAPSHOT BEFORE
    before_pref = db.get(CharacterPreferenceTable, pref_row.id)
    assert before_pref is not None
    before_polarity = before_pref.preference_polarity
    before_appraisal_count = before_pref.appraisal_count
    before_distinct_session_count = before_pref.distinct_session_count
    before_last_tick = before_pref.last_evaluated_tick

    # Trigger DORMANT evaluation (60 day lapse)
    svc = LongitudinalDynamicsService(db)
    result = svc.evaluate_activity(
        character_id=char_id,
        domain_key=domain_key,
        current_timeline_tick=2000,
        calendar_days_since_last_eligible=60,
        sessions_in_trailing_7_days=0,
        distinct_facets_in_trailing_7_days=0,
        current_activity_state=ActivityState.ACTIVE,
    )
    assert result.resolved_activity_state == ActivityState.DORMANT

    # SNAPSHOT AFTER — assert identical to before (non-destructive)
    db.expire_all()
    after_pref = db.get(CharacterPreferenceTable, pref_row.id)
    assert after_pref is not None, "Preference row must still exist (non-destructive)"
    assert after_pref.preference_polarity == before_polarity, "preference_polarity must not change"
    assert after_pref.appraisal_count == before_appraisal_count, "appraisal_count must not change"
    assert after_pref.distinct_session_count == before_distinct_session_count, "distinct_session_count must not change"
    assert after_pref.last_evaluated_tick == before_last_tick, "last_evaluated_tick must not change"


# ─────────────────────────────────────────────────────────────────────────────
# G58: Non-destructiveness — SATIATED does not modify 16.1–16.3 canonical state (Lock 12 / GC-415)
# ─────────────────────────────────────────────────────────────────────────────

def test_g58_satiated_state_is_non_destructive(db, char_id, domain_key):
    """G58 (Lock 12 / GC-415): Snapshot before/after — SATIATED evaluation writes zero mutations
    to character_facet_preferences. Before == After on all fields."""

    pref_row = CharacterPreferenceTable(
        id=str(uuid.uuid4()),
        character_id=char_id,
        domain_key=domain_key,
        facet_key="combat",
        preference_polarity="ENJOYED",
        stability_tier="STABLE",
        revision_kind="NONE",
        appraisal_count=10,
        distinct_session_count=5,
        last_evaluated_tick=900,
    )
    db.add(pref_row)
    db.flush()

    # SNAPSHOT BEFORE
    before_polarity = pref_row.preference_polarity
    before_count = pref_row.appraisal_count
    before_session = pref_row.distinct_session_count

    # Build satiation scenario (4 consecutive same-facet sessions + 2/3 tail fatigue)
    sessions = [
        _make_session("s1", "combat", 100, had_fatigue=False),
        _make_session("s2", "combat", 200, had_fatigue=False),
        _make_session("s3", "combat", 300, had_fatigue=True),
        _make_session("s4", "combat", 400, had_fatigue=True),
    ]
    ctx = _make_ctx(
        sessions=sessions,
        calendar_days_since_last_eligible=0,
        sessions_in_trailing_7_days=4,
        distinct_facets_in_trailing_7_days=1,
        character_id=char_id,
        domain_key=domain_key,
    )
    result = evaluate_activity_state(ctx)
    assert result.resolved_activity_state == ActivityState.SATIATED

    # SNAPSHOT AFTER — no ORM flush triggered, but confirm evaluate_activity_state is pure
    db.expire_all()
    after_pref = db.get(CharacterPreferenceTable, pref_row.id)
    assert after_pref is not None, "Preference row must still exist"
    assert after_pref.preference_polarity == before_polarity
    assert after_pref.appraisal_count == before_count
    assert after_pref.distinct_session_count == before_session


# ─────────────────────────────────────────────────────────────────────────────
# G59: Time heals satiation — SATIATED + 60 days lapse => DORMANT (not SATIATED)
# ─────────────────────────────────────────────────────────────────────────────

def test_g59_satiated_plus_60_days_becomes_dormant():
    """G59: SATIATED + >= 60 lapse days => DORMANT (dormancy check takes precedence)."""
    ctx = _make_ctx(
        calendar_days_since_last_eligible=60,
        current_activity_state=ActivityState.SATIATED,
        current_preference_polarity_is_formed=True,
    )
    result = evaluate_activity_state(ctx)
    assert result.resolved_activity_state == ActivityState.DORMANT


# ─────────────────────────────────────────────────────────────────────────────
# G60: Satiation cool-off — SATIATED + >= 3 days without sessions => ACTIVE
# ─────────────────────────────────────────────────────────────────────────────

def test_g60_satiation_cooloff_recovers_to_active():
    """G60: SATIATED + 3 Phase 8C calendar days with no domain sessions => ACTIVE."""
    ctx = _make_ctx(
        calendar_days_since_last_eligible=3,
        current_activity_state=ActivityState.SATIATED,
        current_preference_polarity_is_formed=True,
    )
    assert evaluate_satiation_cooloff(ctx) is True
    result = evaluate_activity_state(ctx)
    assert result.resolved_activity_state == ActivityState.ACTIVE


def test_g60b_satiation_no_cooloff_before_threshold():
    """G60b: SATIATED + 2 days (< 3) must remain SATIATED."""
    ctx = _make_ctx(
        calendar_days_since_last_eligible=2,
        current_activity_state=ActivityState.SATIATED,
        current_preference_polarity_is_formed=True,
    )
    assert evaluate_satiation_cooloff(ctx) is False
    result = evaluate_activity_state(ctx)
    assert result.resolved_activity_state == ActivityState.SATIATED


# ─────────────────────────────────────────────────────────────────────────────
# G61: ResurgenceEvent guard chain — ACTIVE domain rejected
# ─────────────────────────────────────────────────────────────────────────────

def test_g61_resurgence_rejected_on_active_domain(char_id, domain_key):
    """G61 (Lock 13 / GC-416): Resurgence guard rejects ACTIVE domains."""
    event = ResurgenceEvent(
        event_id=str(uuid.uuid4()),
        character_id=char_id,
        domain_key=domain_key,
        trigger_kind=ResurgenceTriggerKind.CONVERSATIONAL_CUE,
        stimulus_ref="dialogue://turn/100/mention_genshin",
        timeline_tick=1000,
    )
    with pytest.raises(InvalidResurgenceStateError):
        validate_resurgence_event(ActivityState.ACTIVE, event)


def test_g61b_resurgence_rejected_on_empty_stimulus_ref(char_id, domain_key):
    """G61b: Resurgence guard rejects empty stimulus_ref (unanchored evidence)."""
    event = ResurgenceEvent(
        event_id=str(uuid.uuid4()),
        character_id=char_id,
        domain_key=domain_key,
        trigger_kind=ResurgenceTriggerKind.CONVERSATIONAL_CUE,
        stimulus_ref="",
        timeline_tick=1000,
    )
    with pytest.raises(UnanchoredStimulusRefError):
        validate_resurgence_event(ActivityState.DORMANT, event)


def test_g61c_resurgence_rejected_on_fake_stimulus_ref(char_id, domain_key):
    """G61c: Resurgence guard rejects fake:// prefix stimulus_ref."""
    event = ResurgenceEvent(
        event_id=str(uuid.uuid4()),
        character_id=char_id,
        domain_key=domain_key,
        trigger_kind=ResurgenceTriggerKind.ENVIRONMENTAL_STIMULUS,
        stimulus_ref="fake://manufactured/evidence",
        timeline_tick=1000,
    )
    with pytest.raises(UnanchoredStimulusRefError):
        validate_resurgence_event(ActivityState.DORMANT, event)


def test_g61d_resurgence_rejected_on_zero_tick(char_id, domain_key):
    """G61d: Resurgence guard rejects timeline_tick <= 0 (invalid semantic time)."""
    event = ResurgenceEvent(
        event_id=str(uuid.uuid4()),
        character_id=char_id,
        domain_key=domain_key,
        trigger_kind=ResurgenceTriggerKind.DIRECT_RE_ENGAGEMENT,
        stimulus_ref="exec://session/999",
        timeline_tick=0,
    )
    with pytest.raises(LongitudinalDynamicsError):
        validate_resurgence_event(ActivityState.DORMANT, event)


# ─────────────────────────────────────────────────────────────────────────────
# G62: Resurgence is NOT experience — writes ONLY CharacterResurgenceEventTable (Lock 13 / GC-416)
# ─────────────────────────────────────────────────────────────────────────────

def test_g62_resurgence_creates_only_resurgence_row(db, char_id, domain_key):
    """G62 (Lock 13 / GC-416): process_resurgence_with_state appends exactly ONE
    CharacterResurgenceEventTable row and ZERO experience/appraisal/preference mutations."""

    svc = LongitudinalDynamicsService(db)

    # Snapshot before
    before_experiences = db.query(CharacterExperienceTable).filter_by(character_id=char_id).count()
    before_appraisals = db.query(CharacterFacetAppraisalTable).filter_by(character_id=char_id).count()
    before_preferences = db.query(CharacterPreferenceTable).filter_by(character_id=char_id).count()
    before_resurgences = db.query(CharacterResurgenceEventTable).filter_by(character_id=char_id).count()

    # Process resurgence
    event = svc.process_resurgence_with_state(
        current_activity_state=ActivityState.DORMANT,
        character_id=char_id,
        domain_key=domain_key,
        trigger_kind=ResurgenceTriggerKind.CONVERSATIONAL_CUE,
        stimulus_ref="dialogue://turn/500/mention_favorite_ost",
        timeline_tick=2000,
        awakened_facet_key="exploration",
        reflection_note="User brought up the OST unexpectedly.",
    )

    # Snapshot after
    after_experiences = db.query(CharacterExperienceTable).filter_by(character_id=char_id).count()
    after_appraisals = db.query(CharacterFacetAppraisalTable).filter_by(character_id=char_id).count()
    after_preferences = db.query(CharacterPreferenceTable).filter_by(character_id=char_id).count()
    after_resurgences = db.query(CharacterResurgenceEventTable).filter_by(character_id=char_id).count()

    # Assertions: zero experience delta, zero appraisal delta, zero preference delta
    assert after_experiences == before_experiences, "G62: ResurgenceEvent must not create experience records"
    assert after_appraisals == before_appraisals, "G62: ResurgenceEvent must not create appraisal records"
    assert after_preferences == before_preferences, "G62: ResurgenceEvent must not create/modify preference records"

    # Exactly ONE new resurgence row
    assert after_resurgences == before_resurgences + 1, "G62: Exactly one CharacterResurgenceEventTable row expected"

    # Confirm the row content
    assert event.trigger_kind == ResurgenceTriggerKind.CONVERSATIONAL_CUE
    assert event.stimulus_ref == "dialogue://turn/500/mention_favorite_ost"
    assert event.timeline_tick == 2000


# ─────────────────────────────────────────────────────────────────────────────
# G63: CharacterResurgenceEventTable is immutable (ORM events block UPDATE/DELETE)
# ─────────────────────────────────────────────────────────────────────────────

def test_g63_resurgence_event_table_is_immutable(db, char_id, domain_key):
    """G63: ORM events reject UPDATE and DELETE on character_resurgence_events (append-only)."""

    row = CharacterResurgenceEventTable(
        id=str(uuid.uuid4()),
        character_id=char_id,
        domain_key=domain_key,
        trigger_kind=ResurgenceTriggerKind.ENVIRONMENTAL_STIMULUS.value,
        stimulus_ref="desktop://media/ost.flac",
        timeline_tick=1500,
        awakened_facet_key="music",
        reflection_note="",
    )
    db.add(row)
    db.flush()

    # Attempt UPDATE — must raise
    row.reflection_note = "tampered"
    with pytest.raises(ResurgenceMutationProhibitedError):
        db.flush()

    db.rollback()

    # Re-add and attempt DELETE
    row2 = CharacterResurgenceEventTable(
        id=str(uuid.uuid4()),
        character_id=char_id,
        domain_key=domain_key,
        trigger_kind=ResurgenceTriggerKind.ENVIRONMENTAL_STIMULUS.value,
        stimulus_ref="desktop://media/ost.flac",
        timeline_tick=1600,
        awakened_facet_key="",
        reflection_note="",
    )
    db.add(row2)
    db.flush()

    with pytest.raises(ResurgenceMutationProhibitedError):
        db.delete(row2)
        db.flush()


# ─────────────────────────────────────────────────────────────────────────────
# G64: User-Reported provenance has zero refresh authority (Lock 14 / GC-417)
# ─────────────────────────────────────────────────────────────────────────────

def test_g64_eligible_refresh_provenances_are_correctly_defined():
    """G64 (Lock 14 / GC-417): ELIGIBLE_REFRESH_PROVENANCES must contain DIRECT_INTERACTION
    and SHARED_INTERACTION ONLY. USER_REPORTED and OBSERVED_MEDIA must be absent."""
    assert "DIRECT_INTERACTION" in ELIGIBLE_REFRESH_PROVENANCES, "DIRECT_INTERACTION must be eligible"
    assert "SHARED_INTERACTION" in ELIGIBLE_REFRESH_PROVENANCES, "SHARED_INTERACTION must be eligible"
    assert "USER_REPORTED" not in ELIGIBLE_REFRESH_PROVENANCES, "USER_REPORTED has zero refresh authority"
    assert "OBSERVED_MEDIA" not in ELIGIBLE_REFRESH_PROVENANCES, "OBSERVED_MEDIA has zero refresh authority"
    assert "VICARIOUS_DESCRIPTION" not in ELIGIBLE_REFRESH_PROVENANCES, "VICARIOUS_DESCRIPTION not eligible"
    assert "SIMULATED" not in ELIGIBLE_REFRESH_PROVENANCES, "SIMULATED not eligible"
    assert "UNKNOWN" not in ELIGIBLE_REFRESH_PROVENANCES, "UNKNOWN not eligible"


def test_g64b_user_reported_does_not_extend_eligible_interaction_lapse(db, char_id, domain_key):
    """G64b: Service compile_eligible_interactions excludes USER_REPORTED rows (lock 14)."""
    # Insert a USER_REPORTED experience
    exp = CharacterExperienceTable(
        id=str(uuid.uuid4()),
        character_id=char_id,
        domain_key=domain_key,
        facet_key="combat",
        provenance_kind="USER_REPORTED",
        exposure_kind="USER_RECOMMENDATION",
        calendar_session_id="sess-user-reported",
        timeline_tick=999,
        interaction_evidence_ref="none",
        is_fictional_frame=False,
    )
    db.add(exp)
    db.flush()

    svc = LongitudinalDynamicsService(db)
    interactions = svc._compile_eligible_interactions(char_id, domain_key)
    assert len(interactions) == 0, "USER_REPORTED must not appear in eligible interactions"


# ─────────────────────────────────────────────────────────────────────────────
# G65: ActivityState enum has exactly ACTIVE, SATIATED, DORMANT (no regressions)
# ─────────────────────────────────────────────────────────────────────────────

def test_g65_activity_state_enum_values():
    """G65: ActivityState enum contains exactly the 3 expected values — no additions or removals."""
    values = {e.value for e in ActivityState}
    assert values == {"ACTIVE", "SATIATED", "DORMANT"}, f"Unexpected ActivityState values: {values}"


def test_g65b_resurgence_rejected_on_satiated_and_accepted_on_dormant(char_id, domain_key):
    """G65b: External stimulus cannot forcibly bypass SATIATED fatigue; resurgence applies exclusively to DORMANT."""
    event = ResurgenceEvent(
        event_id=str(uuid.uuid4()),
        character_id=char_id,
        domain_key=domain_key,
        trigger_kind=ResurgenceTriggerKind.SCHEDULED_CALENDAR_MILESTONE,
        stimulus_ref="calendar://anniversary/genshin_tick/1000",
        timeline_tick=1001,
    )
    # SATIATED must raise InvalidResurgenceStateError (external stimulus cannot bypass cooldown)
    with pytest.raises(InvalidResurgenceStateError):
        validate_resurgence_event(ActivityState.SATIATED, event)

    # DORMANT must succeed
    validate_resurgence_event(ActivityState.DORMANT, event)


# ─────────────────────────────────────────────────────────────────────────────
# G65c: evaluate_activity_state result fields are all integers (zero floats)
# ─────────────────────────────────────────────────────────────────────────────

def test_g65c_evaluation_result_has_no_floats():
    """G65c (Permanent Note A): ActivityEvaluationResult contains zero float fields."""
    ctx = _make_ctx(calendar_days_since_last_eligible=5, current_activity_state=ActivityState.ACTIVE)
    result = evaluate_activity_state(ctx)
    # resolved_activity_state is an enum (str), satiation_pattern is enum (str),
    # consecutive_monotony_streak and calendar_days_since_last_eligible must be int
    assert isinstance(result.consecutive_monotony_streak, int)
    assert isinstance(result.calendar_days_since_last_eligible, int)
    assert not isinstance(result.consecutive_monotony_streak, float)
    assert not isinstance(result.calendar_days_since_last_eligible, float)
