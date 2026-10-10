"""Phase 16.4 Longitudinal Dynamics: Satiation, Fatigue, Dormancy & Resurgence.

Implements activity-level temporal state interpretation for interest domains.

Constitutional Locks (Phase 16.4):
- Lock 10 (GC-413): Session-Unit Fatigue Integrity — session is the atomic evaluation unit.
- Lock 11 (GC-414): Semantic-Time-Only Longitudinal Evaluation — Phase 8C ticks only, no created_at.
- Lock 12 (GC-415): Activity-State Non-Destructiveness — SATIATED/DORMANT never delete or downgrade.
- Lock 13 (GC-416): Resurgence != Experience — ResurgenceEvent awakens only; creates no appraisals.
- Lock 14 (GC-417): User-Reported Cannot Refresh Activity — only direct personal sessions are eligible.

Permanent Note A: Zero floats across all evaluation logic.
Phase 17 Lockout: Autonomous agency and background crawlers remain strictly reserved for Phase 17.
"""

from enum import Enum
from typing import Optional, Sequence
from pydantic import BaseModel, ConfigDict, Field

from app.growth.state_machine import ActivityState


# =============================================================================
# Phase 16.4 Error Hierarchy
# =============================================================================

class LongitudinalDynamicsError(Exception):
    """Base exception for Phase 16.4 longitudinal dynamics violations."""
    pass


class InvalidResurgenceStateError(LongitudinalDynamicsError):
    """Raised when a ResurgenceEvent is fired on an already ACTIVE domain."""
    pass


class UnanchoredStimulusRefError(LongitudinalDynamicsError):
    """Raised when a ResurgenceEvent stimulus_ref is empty, fake, or unauthorized."""
    pass


class Phase17ProhibitedError(LongitudinalDynamicsError):
    """Raised when autonomous Phase 17 agency is invoked within Phase 16.4 scope."""
    pass


# =============================================================================
# Categorical Enums (Zero Floats, Permanent Note A)
# =============================================================================

class ResurgenceTriggerKind(str, Enum):
    """Categorical taxonomy of verifiable stimuli that can awaken a dormant interest (Lock 13 / GC-416).

    Each trigger kind must be backed by a non-empty, non-fake stimulus_ref for anchoring.
    """

    ENVIRONMENTAL_STIMULUS = "ENVIRONMENTAL_STIMULUS"
    # System/desktop media cue: background music playback, file playback, media detected.
    # e.g. stimulus_ref="desktop://media/genshin_fontaine_ost.flac"

    CONVERSATIONAL_CUE = "CONVERSATIONAL_CUE"
    # User or dialogue references a past domain experience or key shared memory.
    # e.g. stimulus_ref="dialogue://turn/1042/mention_dragonspine"

    DIRECT_RE_ENGAGEMENT = "DIRECT_RE_ENGAGEMENT"
    # Explicit authorized tool execution session in the dormant domain.
    # e.g. stimulus_ref="exec://session/409"
    # NOTE: DIRECT_RE_ENGAGEMENT simultaneously creates an ExperientialRecord via 16.1 path.
    # The ResurgenceEvent records the activation; the ExperientialRecord records the experience.
    # They are orthogonal records (Lock 13).

    SCHEDULED_CALENDAR_MILESTONE = "SCHEDULED_CALENDAR_MILESTONE"
    # Phase 8C calendar anniversary or milestone associated with the domain.
    # e.g. stimulus_ref="calendar://anniversary/genshin_launch_tick/1000"


class SatiationPattern(str, Enum):
    """Classification of the satiation pattern detected, used for diagnostic/audit purposes only.

    These are post-hoc labels; they carry NO weight in preference or appraisal logic.
    """

    NONE = "NONE"                      # No satiation detected
    ACUTE_MONOTONY = "ACUTE_MONOTONY"  # Pattern 1: consecutive single-facet overload
    HYPER_DENSITY = "HYPER_DENSITY"    # Pattern 2: high-frequency domain-wide saturation


# =============================================================================
# Frozen Policy Thresholds (Permanent Note A: Integer math only)
# =============================================================================

# Pattern 1 — Acute Monotony Satiation
SATIATION_MONOTONY_SESSION_STREAK: int = 4      # >= 4 consecutive sessions on exact same facet
SATIATION_MONOTONY_TAIL_WINDOW: int = 3          # Evaluate trailing 3 eligible sessions
SATIATION_MONOTONY_FATIGUE_IN_WINDOW: int = 2    # >= 2 out of trailing 3 must have TEDIOUS_EXHAUSTING

# Pattern 2 — Hyper-Density Satiation
SATIATION_DENSITY_SESSIONS_7D: int = 7           # >= 7 distinct sessions in trailing 7 calendar days
SATIATION_DENSITY_TAIL_WINDOW: int = 5           # Evaluate trailing 5 eligible sessions
SATIATION_DENSITY_FATIGUE_IN_WINDOW: int = 3     # >= 3 out of trailing 5 must have TEDIOUS_EXHAUSTING

# Diversity anti-fatigue invariant (G52)
SATIATION_DIVERSITY_FACET_MINIMUM: int = 4       # >= 4 distinct facets in 7-day window blocks Pattern 1

# Satiation cool-off recovery
SATIATION_COOLOFF_DAYS: int = 3                  # >= 3 Phase 8C calendar days with 0 sessions

# Dormancy entry threshold
DORMANCY_LAPSE_DAYS_FORMED: int = 60             # 60 days lapse when preference is formed
DORMANCY_LAPSE_DAYS_UNFORMED: int = 45           # 45 days lapse when preference is UNFORMED

# Eligible provenance for activity refresh (Lock 14 / GC-417)
ELIGIBLE_REFRESH_PROVENANCES: frozenset = frozenset({
    "DIRECT_INTERACTION",
    "SHARED_INTERACTION",
})
# USER_REPORTED, OBSERVED_MEDIA, VICARIOUS_DESCRIPTION, SIMULATED, UNKNOWN — zero refresh authority.


# =============================================================================
# Data Transfer Objects
# =============================================================================

class SessionOutcome(BaseModel):
    """A discrete session outcome for satiation pattern evaluation (Lock 10 / GC-413).

    The session (calendar_session_id) is the atomic evaluation unit.
    Multiple appraisals within one session are collapsed into one SessionOutcome.
    Ordered strictly by timeline_tick ASC (Lock 11 / GC-414).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    calendar_session_id: str
    facet_key: str                      # Dominant facet of this session (for streak counting)
    timeline_tick: int                  # Phase 8C canonical tick (Lock 11)
    had_fatigue_appraisal: bool         # True if ANY appraisal in session was TEDIOUS_EXHAUSTING


class EligibleInteractionRecord(BaseModel):
    """Minimal record of an eligible personal interaction for dormancy calculation (Lock 14 / GC-417).

    Only provenance kinds in ELIGIBLE_REFRESH_PROVENANCES count toward activity lapse measurement.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    provenance_kind: str                # Must be in ELIGIBLE_REFRESH_PROVENANCES to matter
    timeline_tick: int                  # Phase 8C canonical tick (Lock 11)
    calendar_session_id: str


class LongitudinalEvaluationContext(BaseModel):
    """Deterministic factual context for Phase 16.4 activity state evaluation.

    Compiled READ-ONLY from Phase 16.1 and 16.3 DB streams (Lock 12 / GC-415).
    Permanent Note A: All fields are integers (zero floats).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    character_id: str
    domain_key: str

    # Eligible sessions ordered by timeline_tick ASC (Locks 10 & 11)
    eligible_sessions: Sequence[SessionOutcome] = Field(default_factory=list)

    # Eligible interaction records for dormancy lapse calculation (Lock 14)
    eligible_interactions: Sequence[EligibleInteractionRecord] = Field(default_factory=list)

    # Current semantic calendar position (Phase 8C tick, never wall-clock) (Lock 11)
    current_timeline_tick: int = 0

    # Phase 8C calendar days between tick values: provided by caller from Phase 8C service
    # Mapping: (from_tick, to_tick) -> calendar_days (precomputed; no float, no datetime arithmetic)
    calendar_days_since_last_eligible_interaction: int = 0  # Integer calendar days (Lock 11)

    # Distinct Phase 8C calendar days elapsed in trailing 7-day window
    sessions_in_trailing_7_calendar_days: int = 0           # Count of distinct sessions in 7-day window

    # Distinct facet keys used in the trailing 7-day window (for diversity invariant G52)
    distinct_facets_in_trailing_7_days: int = 0             # Set cardinality (integer, no ratio)

    # Current activity state (before this evaluation)
    current_activity_state: ActivityState = ActivityState.ACTIVE

    # Current preference polarity (for dormancy threshold selection)
    current_preference_polarity_is_formed: bool = False


class ResurgenceEvent(BaseModel):
    """Immutable transition event record for interest domain reactivation (Lock 13 / GC-416).

    A ResurgenceEvent awakens a DORMANT or SATIATED domain to ACTIVE.
    It does NOT create experience records, appraisals, or preferences.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str
    character_id: str
    domain_key: str
    trigger_kind: ResurgenceTriggerKind
    stimulus_ref: str                       # Must be non-empty and non-fake (validated by guard)
    timeline_tick: int                      # Phase 8C canonical tick (Lock 11)
    awakened_facet_key: Optional[str] = None  # Optional specific sub-facet cue
    reflection_note: str = ""              # Audit annotation only — zero semantic logic weight


class ActivityEvaluationResult(BaseModel):
    """Output of evaluate_activity_state() — a deterministic categorical derivation.

    Permanent Note A: no float fields.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    resolved_activity_state: ActivityState
    satiation_pattern: SatiationPattern = SatiationPattern.NONE
    consecutive_monotony_streak: int = 0   # Number of consecutive same-facet sessions (for audit)
    calendar_days_since_last_eligible: int = 0  # For audit and test assertion


# =============================================================================
# Pure Satiation Pattern Evaluators (Zero Floats, Deterministic, Testable)
# =============================================================================

def _compute_consecutive_monotony_streak(sessions: Sequence[SessionOutcome]) -> tuple[int, str | None]:
    """Compute the length of the most recent consecutive same-facet session streak.

    Sessions must be ordered by timeline_tick ASC (Lock 11).
    Any intervening session with a different facet_key resets the streak counter (Lock 10).

    Returns:
        (streak_length, streak_facet_key): streak_facet_key is None if no sessions.
    """
    if not sessions:
        return 0, None

    # Walk sessions from most recent backwards
    reversed_sessions = list(reversed(sessions))
    streak_facet = reversed_sessions[0].facet_key
    streak = 1

    for session in reversed_sessions[1:]:
        if session.facet_key == streak_facet:
            streak += 1
        else:
            break  # Intervening different facet resets count

    return streak, streak_facet


def _count_fatigue_in_tail(sessions: Sequence[SessionOutcome], window_size: int) -> int:
    """Count sessions with had_fatigue_appraisal in the most recent N sessions.

    Sessions must be ordered by timeline_tick ASC (Lock 11).
    Tail window is the last `window_size` sessions (discrete fixed window, not ambiguous "recent").
    Permanent Note A: integer count, no float.
    """
    tail = list(sessions)[-window_size:]
    return sum(1 for s in tail if s.had_fatigue_appraisal)


def evaluate_satiation_pattern(ctx: LongitudinalEvaluationContext) -> tuple[bool, SatiationPattern, int]:
    """Evaluate whether the current evidence stream matches any satiation pattern.

    Returns:
        (is_satiated, satiation_pattern, consecutive_streak)

    Pattern 1 — Acute Monotony Satiation (Lock 10 / Watchpoint 3):
        - >= SATIATION_MONOTONY_SESSION_STREAK consecutive sessions on the same facet
        - AND >= SATIATION_MONOTONY_FATIGUE_IN_WINDOW out of trailing SATIATION_MONOTONY_TAIL_WINDOW

    Pattern 2 — Hyper-Density Satiation:
        - >= SATIATION_DENSITY_SESSIONS_7D sessions in trailing 7 Phase 8C calendar days
        - AND >= SATIATION_DENSITY_FATIGUE_IN_WINDOW out of trailing SATIATION_DENSITY_TAIL_WINDOW

    Diversity Anti-Fatigue Invariant (G52):
        - If distinct_facets_in_trailing_7_days >= SATIATION_DIVERSITY_FACET_MINIMUM,
          Pattern 1 (Acute Monotony) cannot hold by definition (streak broken by diversity).
    """
    sessions = ctx.eligible_sessions

    # Pattern 1: Acute Monotony
    streak, _ = _compute_consecutive_monotony_streak(sessions)

    if streak >= SATIATION_MONOTONY_SESSION_STREAK:
        # Diversity invariant: cardinality check prevents false monotony when diverse (G52)
        if ctx.distinct_facets_in_trailing_7_days < SATIATION_DIVERSITY_FACET_MINIMUM:
            fatigue_in_tail = _count_fatigue_in_tail(sessions, SATIATION_MONOTONY_TAIL_WINDOW)
            if fatigue_in_tail >= SATIATION_MONOTONY_FATIGUE_IN_WINDOW:
                return True, SatiationPattern.ACUTE_MONOTONY, streak

    # Pattern 2: Hyper-Density
    if ctx.sessions_in_trailing_7_calendar_days >= SATIATION_DENSITY_SESSIONS_7D:
        fatigue_in_tail = _count_fatigue_in_tail(sessions, SATIATION_DENSITY_TAIL_WINDOW)
        if fatigue_in_tail >= SATIATION_DENSITY_FATIGUE_IN_WINDOW:
            return True, SatiationPattern.HYPER_DENSITY, streak

    return False, SatiationPattern.NONE, streak


def evaluate_dormancy(ctx: LongitudinalEvaluationContext) -> bool:
    """Evaluate whether the domain qualifies for dormancy entry.

    Dormancy Entry Rule (GC-410):
        - 60 Phase 8C calendar days since last eligible interaction (if preference formed)
        - 45 Phase 8C calendar days since last eligible interaction (if preference UNFORMED)

    Eligible interaction = DIRECT_INTERACTION or SHARED_INTERACTION (Lock 14 / GC-417).
    USER_REPORTED and OBSERVED_MEDIA do NOT qualify (zero refresh authority).
    """
    lapse_threshold = (
        DORMANCY_LAPSE_DAYS_UNFORMED
        if not ctx.current_preference_polarity_is_formed
        else DORMANCY_LAPSE_DAYS_FORMED
    )
    return ctx.calendar_days_since_last_eligible_interaction >= lapse_threshold


def evaluate_satiation_cooloff(ctx: LongitudinalEvaluationContext) -> bool:
    """Evaluate whether a currently SATIATED domain has naturally recovered.

    Satiation Cool-off Rule:
        - SATIATED + >= SATIATION_COOLOFF_DAYS Phase 8C calendar days without any eligible sessions
          -> transitions back to ACTIVE.
    """
    if ctx.current_activity_state != ActivityState.SATIATED:
        return False
    return ctx.calendar_days_since_last_eligible_interaction >= SATIATION_COOLOFF_DAYS


# =============================================================================
# Main Activity State Evaluator
# =============================================================================

def evaluate_activity_state(ctx: LongitudinalEvaluationContext) -> ActivityEvaluationResult:
    """Evaluate the current ActivityState for an interest domain.

    Evaluation precedence (applied in strict order):
    1. Dormancy superpositional check: Does either SATIATED or ACTIVE state qualify for dormancy?
       - Satiation + 60 days lapse => DORMANT (time heals old fatigue; G59).
       - ACTIVE + 60 days lapse => DORMANT.
    2. Satiation recovery check: SATIATED + cool-off => ACTIVE.
    3. Satiation detection: Does the current session stream match any satiation pattern?
       - Pattern 1: Acute Monotony => SATIATED.
       - Pattern 2: Hyper-Density => SATIATED.
    4. Default: ACTIVE.

    Constitutional Guarantees:
    - Zero float arithmetic. All comparisons are integer >= (Lock 11, Permanent Note A).
    - No preference, appraisal, or experience record is modified (Lock 12 / GC-415).
    - No Phase 17 autonomous agency invoked.
    """
    lapse = ctx.calendar_days_since_last_eligible_interaction
    streak = 0

    # Step 1: Dormancy superpositional check (takes priority over satiation)
    # This also handles the time-heals-satiation case (G59): SATIATED + 60 days => DORMANT
    if evaluate_dormancy(ctx):
        return ActivityEvaluationResult(
            resolved_activity_state=ActivityState.DORMANT,
            satiation_pattern=SatiationPattern.NONE,
            consecutive_monotony_streak=0,
            calendar_days_since_last_eligible=lapse,
        )

    # Step 2: Satiation recovery (cool-off period)
    if evaluate_satiation_cooloff(ctx):
        return ActivityEvaluationResult(
            resolved_activity_state=ActivityState.ACTIVE,
            satiation_pattern=SatiationPattern.NONE,
            consecutive_monotony_streak=0,
            calendar_days_since_last_eligible=lapse,
        )

    # Step 3: If still SATIATED (cool-off not yet elapsed), remain SATIATED
    if ctx.current_activity_state == ActivityState.SATIATED:
        streak, _ = _compute_consecutive_monotony_streak(ctx.eligible_sessions)
        return ActivityEvaluationResult(
            resolved_activity_state=ActivityState.SATIATED,
            satiation_pattern=SatiationPattern.NONE,
            consecutive_monotony_streak=streak,
            calendar_days_since_last_eligible=lapse,
        )

    # Step 4: Detect new satiation patterns
    is_satiated, pattern, streak = evaluate_satiation_pattern(ctx)
    if is_satiated:
        return ActivityEvaluationResult(
            resolved_activity_state=ActivityState.SATIATED,
            satiation_pattern=pattern,
            consecutive_monotony_streak=streak,
            calendar_days_since_last_eligible=lapse,
        )

    # Step 5: Default — ACTIVE
    return ActivityEvaluationResult(
        resolved_activity_state=ActivityState.ACTIVE,
        satiation_pattern=SatiationPattern.NONE,
        consecutive_monotony_streak=streak,
        calendar_days_since_last_eligible=lapse,
    )


# =============================================================================
# Resurgence Guard Chain
# =============================================================================

_BLOCKED_STIMULUS_PREFIXES = frozenset({"fake://", "unauthorized://", "simulated://"})


def validate_resurgence_event(
    current_activity: ActivityState,
    event: ResurgenceEvent,
) -> None:
    """Validate a ResurgenceEvent before processing.

    Semantic Contract (Revision 2, Gate 0 — Freeze Lock):
        Resurgence is a Dormancy recovery mechanism ONLY.
        SATIATED domains recover via natural cooldown (3 Phase 8C days without sessions).
        External stimuli must NOT forcibly bypass the satiation fatigue cooldown.
        Therefore: ResurgenceEvent is valid ONLY when the domain is DORMANT.

    Guard Chain (fail-closed):
    1. State Guard: domain must be DORMANT — not ACTIVE, not SATIATED.
       - ACTIVE: no resurgence needed.
       - SATIATED: must recover naturally; external stimulus cannot override fatigue.
    2. Stimulus Anchor Guard: stimulus_ref must be non-empty and not use a blocked prefix.
    3. Timeline Guard: timeline_tick must be > 0.

    Raises:
        InvalidResurgenceStateError: domain is ACTIVE or SATIATED (not eligible for resurgence).
        UnanchoredStimulusRefError: stimulus_ref is empty, fake, or unauthorized.
        LongitudinalDynamicsError: timeline_tick invalid.
    """
    # Guard 1: State guard — only DORMANT is eligible for ResurgenceEvent
    if current_activity != ActivityState.DORMANT:
        raise InvalidResurgenceStateError(
            f"Cannot trigger ResurgenceEvent on domain '{event.domain_key}': "
            f"domain is '{current_activity.value}', not DORMANT. "
            f"Resurgence is exclusively a Dormancy recovery mechanism. "
            f"SATIATED domains recover via natural cooldown only (external stimuli cannot bypass fatigue)."
        )

    # Guard 2: Stimulus anchor guard (Lock 13 / GC-416)
    if not event.stimulus_ref or not event.stimulus_ref.strip():
        raise UnanchoredStimulusRefError(
            f"ResurgenceEvent for domain '{event.domain_key}' has empty stimulus_ref. "
            f"Resurgence requires a verifiable, anchored stimulus reference."
        )

    if any(event.stimulus_ref.startswith(blocked) for blocked in _BLOCKED_STIMULUS_PREFIXES):
        raise UnanchoredStimulusRefError(
            f"ResurgenceEvent stimulus_ref '{event.stimulus_ref}' uses a prohibited prefix. "
            f"Fake or unauthorized stimulus refs are not valid resurgence anchors."
        )

    # Guard 3: Timeline anchor guard (Lock 11 / GC-414)
    if event.timeline_tick <= 0:
        raise LongitudinalDynamicsError(
            f"ResurgenceEvent timeline_tick must be a positive Phase 8C tick. "
            f"Got: {event.timeline_tick}"
        )
