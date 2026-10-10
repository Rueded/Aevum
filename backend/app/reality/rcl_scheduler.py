"""Reality Construction Loop — Contracts & Scheduler (Phase 14.1).

Governed by ADR-025 (Revision 1):
- 14.1-A: RCLScheduler is the sole arbiter of WHEN a RCL cycle is eligible to start.
- 14.1-B: Eligibility is determined by cooldown boundary (>= 30 min wall-clock),
  per-character cycle lock (no parallel cycles), and post-conversation debounce
  (coalesces requests, never bypasses cooldown).
- 14.1-C: RCLScheduler has ZERO direct access to BiographyPromotionService,
  set_fact(), PromotionAuthorizationToken, database writes, LLM calls, or web calls.
- 14.1-D: MANUAL_DEBUG trigger bypasses cooldown in test/debug environment ONLY.
  Production environments must enforce cooldown unconditionally.
- 14.1-E: All DTOs are immutable (frozen=True). No runtime field mutation permitted.
- 14.1-F: Scheduler failures are isolated; they never propagate to conversation flow.

Constitutional Locks (ADR-025):
  Lock 7  — RCL Failure Isolation: RCL exception → cycle skipped, not crash.
  Lock 9  — One Construction Authority: RCLScheduler delegates to exactly one
            RealityConstructionOrchestrator per character per cycle.
  Lock 10 — Belief Maturity ≠ Truth: time is a maturity signal only.
  Lock 12 — No Same-Cycle Recursive Premise Promotion (enforced downstream in 14.3).

Phase 14.1 Scope:
  ✅ Pure DTO layer (RCLTriggerKind, RCLCycleContext, RCLCycleResult)
  ✅ RCLScheduler (clock injection, cooldown, debounce, per-character lock)
  ❌ Hypothesis generation, constraint evaluation, competition — Phase 14.2+
  ❌ CycleIsolationLedger — Phase 14.3
  ❌ BeliefRevisionRecord, BeliefMaturity — Phase 14.4+
  ❌ Any database writes beyond the existing Phase 7D tables
"""

from __future__ import annotations

import enum
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Set
import uuid

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Minimum wall-clock seconds between RCL cycles for the same character (D1).
RCL_COOLDOWN_SECONDS: float = 30.0 * 60.0  # 30 minutes

#: Post-conversation debounce window in seconds. Multiple conversation events
#: within this window are coalesced into a single pending trigger (D1).
RCL_DEBOUNCE_SECONDS: float = 5.0

#: Environment flag key checked to allow MANUAL_DEBUG cooldown bypass.
#: Production deployments must NOT set this flag. Test environments may set it.
_RCL_DEBUG_BYPASS_ATTR: str = "_rcl_debug_bypass_enabled"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RCLTriggerKind(str, enum.Enum):
    """Authoritative set of Reality Construction Loop trigger sources.

    Constitutional constraint (ADR-025 Lock 9):
    There is exactly one construction authority path per character. All
    trigger sources route through RCLScheduler — none may execute an
    independent inference path.

    Notes:
        POST_CONVERSATION: Preserves Phase 8A Step C2 per-turn trigger semantics.
            C2's AutonomousInferenceCoordinator is superseded as an independent
            implementation; its intent is expressed here (ADR-025 D5).
        MANUAL_DEBUG: Bypasses cooldown for test/debug environment ONLY.
            Must never be reachable in production code paths.
    """

    POST_CONVERSATION = "POST_CONVERSATION"
    SCHEDULED_TICK = "SCHEDULED_TICK"
    LIFE_EVENT = "LIFE_EVENT"
    MANUAL_DEBUG = "MANUAL_DEBUG"


# ---------------------------------------------------------------------------
# Immutable DTOs
# ---------------------------------------------------------------------------

class RCLCycleContext(BaseModel):
    """Immutable snapshot describing the context at the start of an RCL cycle.

    This DTO is constructed by RCLScheduler immediately before handing control
    to RealityConstructionOrchestrator (Phase 14.3). It is read-only throughout
    the cycle; no field may be mutated after construction.

    Constitutional constraints:
        - No fields that reference BiographyPromotionService, set_fact(), or
          PromotionAuthorizationToken.
        - active_canonical_facts_count is a snapshot count for observability only;
          it is NOT an input to inference or promotion decisions.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    cycle_id: str = Field(
        description="Unique identifier for this RCL cycle execution.",
    )
    character_id: str = Field(
        description="The character this cycle belongs to.",
    )
    trigger_kind: RCLTriggerKind = Field(
        description="What triggered this cycle.",
    )
    triggered_at_monotonic: float = Field(
        description=(
            "Monotonic clock value at cycle start. Used exclusively for "
            "cooldown and duration measurements. NOT wall-clock time. "
            "Never used as truth signal (ADR-025 Lock 10)."
        ),
    )
    active_canonical_facts_count: int = Field(
        default=0,
        ge=0,
        description=(
            "Snapshot count of canonical facts at cycle start. "
            "Observability only. Not an inference input."
        ),
    )
    is_debug_cycle: bool = Field(
        default=False,
        description=(
            "True only for MANUAL_DEBUG trigger in test/debug environments. "
            "Production cycles always have is_debug_cycle=False."
        ),
    )


class RCLCycleResult(BaseModel):
    """Immutable record of an RCL cycle's outcome.

    Persisted after each cycle attempt (including skipped cycles) for
    observability and cooldown tracking. The scheduler uses
    ``completed_at_monotonic`` to enforce the next eligible window.

    Constitutional constraints:
        - No field carries canonical facts or belief content.
        - ``loop_skipped_reason`` is a diagnostic string, not an error.
          Skipped cycles are normal steady-state behavior.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    cycle_id: str = Field(description="Matches RCLCycleContext.cycle_id.")
    character_id: str = Field(description="The character this cycle belongs to.")
    trigger_kind: RCLTriggerKind
    started_at_monotonic: float = Field(
        description="Monotonic clock value when the cycle started.",
    )
    completed_at_monotonic: float = Field(
        description="Monotonic clock value when the cycle completed (or was skipped).",
    )
    elapsed_ms: float = Field(
        ge=0.0,
        description="Wall-equivalent duration in milliseconds.",
    )
    candidates_generated: int = Field(
        default=0,
        ge=0,
        description="Number of hypothesis candidates generated this cycle.",
    )
    candidates_promoted: int = Field(
        default=0,
        ge=0,
        description="Number of candidates promoted to canonical this cycle (max 1 per D2).",
    )
    candidates_suppressed: int = Field(
        default=0,
        ge=0,
        description="Candidates that passed competition but were suppressed (governance gate).",
    )
    loop_skipped_reason: Optional[str] = Field(
        default=None,
        description=(
            "If set, the cycle was skipped without executing inference. "
            "Normal reasons: COOLDOWN_ACTIVE, CYCLE_ALREADY_RUNNING, "
            "DEBOUNCE_PENDING, RCL_EXCEPTION. None means cycle ran normally."
        ),
    )
    exception_detail: Optional[str] = Field(
        default=None,
        description=(
            "Diagnostic string if the cycle was skipped due to an unhandled "
            "exception. Never re-raised. Conversation flow is unaffected (Lock 7)."
        ),
    )


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

class RCLScheduler:
    """Governs WHEN a Reality Construction Loop cycle is eligible to start.

    The scheduler is the sole authority over cycle timing. It enforces:
      - 30-minute wall-clock cooldown between cycles per character (D1).
      - Per-character cycle lock: no two cycles may run concurrently for
        the same character (Lock 9).
      - Post-conversation debounce: multiple rapid triggers coalesce into
        one pending request without bypassing the cooldown (D1).
      - MANUAL_DEBUG bypass of cooldown for test environments only (D1).

    Authority boundaries (ADR-025 14.1-C):
      This class MUST NOT import or reference:
        - BiographyPromotionService
        - set_fact()
        - PromotionAuthorizationToken
        - Any SQLAlchemy model or database session
        - Any LLM provider or HTTP client
        - Any Phase 14.2+ component

    Args:
        clock_fn: Callable returning monotonic time in seconds. Defaults to
            ``time.monotonic``. Inject a deterministic mock in tests.
        cooldown_seconds: Minimum seconds between cycles per character.
            Defaults to RCL_COOLDOWN_SECONDS (1800s / 30 min).
        debounce_seconds: Window within which rapid POST_CONVERSATION triggers
            are coalesced. Defaults to RCL_DEBOUNCE_SECONDS (5s).
        debug_bypass_enabled: If True, MANUAL_DEBUG trigger bypasses cooldown.
            Must be False in production. Tests may set True.
    """

    def __init__(
        self,
        clock_fn: Callable[[], float] = time.monotonic,
        cooldown_seconds: float = RCL_COOLDOWN_SECONDS,
        debounce_seconds: float = RCL_DEBOUNCE_SECONDS,
        debug_bypass_enabled: bool = False,
    ) -> None:
        self._clock = clock_fn
        self._cooldown_seconds = cooldown_seconds
        self._debounce_seconds = debounce_seconds
        self._debug_bypass_enabled = debug_bypass_enabled

        # Per-character: monotonic time of last completed (or skipped) cycle.
        self._last_cycle_completed_at: Dict[str, float] = {}

        # Per-character: set of character_ids currently executing a cycle.
        self._active_cycles: Set[str] = set()

        # Per-character: monotonic time of last POST_CONVERSATION trigger
        # (for debounce tracking).
        self._last_conversation_trigger_at: Dict[str, float] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def request_cycle(
        self,
        character_id: str,
        trigger_kind: RCLTriggerKind,
        active_canonical_facts_count: int = 0,
    ) -> tuple[bool, RCLCycleContext | None, str]:
        """Evaluate whether a new RCL cycle is eligible to start.

        This method is purely a decision function. It does NOT execute
        inference, hypothesis generation, or any canonical mutation.

        Args:
            character_id: The character to run a cycle for.
            trigger_kind: Source of the trigger request.
            active_canonical_facts_count: Snapshot count for observability.

        Returns:
            A 3-tuple of:
              - eligible (bool): True if a cycle should be started.
              - context (RCLCycleContext | None): The cycle context if eligible,
                None if not eligible.
              - skip_reason (str): Diagnostic reason if not eligible, empty string
                if eligible.
        """
        now = self._clock()

        # MANUAL_DEBUG: may bypass cooldown in test environment only.
        if trigger_kind == RCLTriggerKind.MANUAL_DEBUG:
            if not self._debug_bypass_enabled:
                return False, None, "MANUAL_DEBUG_NOT_ALLOWED_IN_PRODUCTION"
            return self._build_context(
                character_id=character_id,
                trigger_kind=trigger_kind,
                now=now,
                active_canonical_facts_count=active_canonical_facts_count,
                is_debug_cycle=True,
            )

        # Gate 1: Per-character cycle lock.
        if character_id in self._active_cycles:
            return False, None, "CYCLE_ALREADY_RUNNING"

        # Gate 2: Post-conversation debounce coalescing.
        if trigger_kind == RCLTriggerKind.POST_CONVERSATION:
            last_conv = self._last_conversation_trigger_at.get(character_id)
            if last_conv is not None and (now - last_conv) < self._debounce_seconds:
                # Request recorded but not yet eligible; will be picked up
                # when cooldown allows.
                self._last_conversation_trigger_at[character_id] = now
                return False, None, "DEBOUNCE_PENDING"
            self._last_conversation_trigger_at[character_id] = now

        # Gate 3: Cooldown boundary.
        # Exact boundary: elapsed >= cooldown_seconds → eligible.
        # elapsed < cooldown_seconds → blocked.
        last_completed = self._last_cycle_completed_at.get(character_id)
        if last_completed is not None:
            elapsed = now - last_completed
            if elapsed < self._cooldown_seconds:
                return False, None, "COOLDOWN_ACTIVE"

        return self._build_context(
            character_id=character_id,
            trigger_kind=trigger_kind,
            now=now,
            active_canonical_facts_count=active_canonical_facts_count,
            is_debug_cycle=False,
        )

    def mark_cycle_started(self, character_id: str) -> None:
        """Record that a cycle has started for character_id.

        Must be called before the cycle body executes to enforce the
        per-character lock.
        """
        self._active_cycles.add(character_id)

    def mark_cycle_completed(
        self,
        character_id: str,
        result: RCLCycleResult,
    ) -> None:
        """Record that a cycle has completed (or was skipped with a result).

        Updates the cooldown clock and releases the per-character lock.
        Must be called unconditionally in a finally block to prevent
        deadlocking the character's cycle lock on exception.
        """
        self._active_cycles.discard(character_id)
        self._last_cycle_completed_at[character_id] = result.completed_at_monotonic

    def is_character_locked(self, character_id: str) -> bool:
        """Return True if a cycle is currently active for character_id."""
        return character_id in self._active_cycles

    def seconds_until_next_eligible(self, character_id: str) -> float:
        """Return seconds until the character's next eligible cycle window.

        Returns 0.0 if the character is already eligible (no prior cycle, or
        cooldown has elapsed). Returns a positive float if still cooling down.
        """
        last_completed = self._last_cycle_completed_at.get(character_id)
        if last_completed is None:
            return 0.0
        elapsed = self._clock() - last_completed
        remaining = self._cooldown_seconds - elapsed
        return max(0.0, remaining)

    def make_skipped_result(
        self,
        character_id: str,
        trigger_kind: RCLTriggerKind,
        skip_reason: str,
        started_at_monotonic: Optional[float] = None,
        exception_detail: Optional[str] = None,
    ) -> RCLCycleResult:
        """Construct an RCLCycleResult for a skipped cycle.

        Used both for pre-eligibility skips (no context yet) and for
        mid-cycle exception skips (Lock 7: fail-degraded).
        """
        now = self._clock()
        started = started_at_monotonic if started_at_monotonic is not None else now
        return RCLCycleResult(
            cycle_id=str(uuid.uuid4()),
            character_id=character_id,
            trigger_kind=trigger_kind,
            started_at_monotonic=started,
            completed_at_monotonic=now,
            elapsed_ms=max(0.0, (now - started) * 1000.0),
            loop_skipped_reason=skip_reason,
            exception_detail=exception_detail,
        )

    def make_completed_result(
        self,
        context: RCLCycleContext,
        started_at_monotonic: float,
        candidates_generated: int = 0,
        candidates_promoted: int = 0,
        candidates_suppressed: int = 0,
    ) -> RCLCycleResult:
        """Construct an RCLCycleResult for a successfully executed cycle."""
        now = self._clock()
        return RCLCycleResult(
            cycle_id=context.cycle_id,
            character_id=context.character_id,
            trigger_kind=context.trigger_kind,
            started_at_monotonic=started_at_monotonic,
            completed_at_monotonic=now,
            elapsed_ms=max(0.0, (now - started_at_monotonic) * 1000.0),
            candidates_generated=candidates_generated,
            candidates_promoted=candidates_promoted,
            candidates_suppressed=candidates_suppressed,
            loop_skipped_reason=None,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_context(
        self,
        character_id: str,
        trigger_kind: RCLTriggerKind,
        now: float,
        active_canonical_facts_count: int,
        is_debug_cycle: bool,
    ) -> tuple[bool, RCLCycleContext, str]:
        context = RCLCycleContext(
            cycle_id=str(uuid.uuid4()),
            character_id=character_id,
            trigger_kind=trigger_kind,
            triggered_at_monotonic=now,
            active_canonical_facts_count=active_canonical_facts_count,
            is_debug_cycle=is_debug_cycle,
        )
        return True, context, ""
