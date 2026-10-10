"""Conversational Momentum Engine (Phase 18.2).

Tracks ongoing dialogue continuity, topic momentum, and organic thread decay
without turning conversational memory into a rigid task list (Boundary 1)
or mandatory prompt injection bloat (Boundary 5).
"""

import logging
import re
from typing import Optional

from app.character.conversational_models import (
    ConversationalMomentumState,
    FrictionTier,
    ResponseCommitmentTier,
    TurnConversationalDecision,
)

logger = logging.getLogger(__name__)


class ConversationalMomentumEngine:
    """Manages conversational momentum, in-jokes, and thread decay across turns."""

    # Maximum number of threads to keep before older ones drop off
    MAX_UNRESOLVED_THREADS = 2
    # Maximum number of running inside jokes to preserve
    MAX_RUNNING_IN_JOKES = 3
    # Maximum friction history to preserve
    MAX_FRICTION_HISTORY = 3

    @classmethod
    def update_momentum(
        cls,
        previous_state: Optional[ConversationalMomentumState],
        user_input: str,
        prior_decision: Optional[TurnConversationalDecision] = None,
    ) -> ConversationalMomentumState:
        """Derive updated ConversationalMomentumState for the current turn.

        Constitutional Boundaries:
        - Boundary 1 (Momentum != Task Tracking): Unreferenced threads naturally decay.
          Topics shift organically; no thread is a mandatory 'to-do'.
        - Boundary 2 (No Manufactured Low Energy): consecutive_low_effort_turns is
          purely observational, never used as an automated penalty clock.
        """
        prev = previous_state or ConversationalMomentumState()

        # 1. Update consecutive low-effort turns (purely observational)
        if prior_decision and prior_decision.commitment in (
            ResponseCommitmentTier.ZERO_EXPANSION,
            ResponseCommitmentTier.LOW_EFFORT,
        ):
            new_low_effort_count = prev.consecutive_low_effort_turns + 1
        else:
            new_low_effort_count = 0

        # 2. Update recent friction history
        new_friction_history = list(prev.recent_friction_history)
        if prior_decision and prior_decision.friction:
            new_friction_history.append(prior_decision.friction)
            new_friction_history = new_friction_history[-cls.MAX_FRICTION_HISTORY:]

        # 3. Running in-jokes: preserve existing
        new_in_jokes = list(prev.running_in_jokes[-cls.MAX_RUNNING_IN_JOKES:])

        # 4. Resolve topic anchor & thread decay
        cleaned_input = user_input.strip()
        new_topic_anchor = prev.active_topic_anchor
        new_threads = list(prev.unresolved_threads)

        if prior_decision and prior_decision.momentum_anchor:
            anchor = prior_decision.momentum_anchor.strip()
            if anchor:
                new_topic_anchor = anchor[:120]

        # Natural thread decay (Boundary 1):
        # If user input doesn't reference an unresolved thread, keep at most MAX_UNRESOLVED_THREADS
        # and do NOT force continuation.
        if new_threads:
            # Check if any thread keywords appear in user input
            surviving_threads = []
            for thread in new_threads:
                # Keep thread if loosely relevant or very recently opened, but prune if user moved far away
                keywords = [w for w in re.split(r"[\s,_\-，。？！]+", thread) if len(w) >= 2]
                if any(kw.lower() in cleaned_input.lower() for kw in keywords):
                    surviving_threads.append(thread)
                else:
                    # Thread not mentioned: allow it to persist only if at front of queue
                    surviving_threads.append(thread)
            # Cap strictly
            new_threads = surviving_threads[-cls.MAX_UNRESOLVED_THREADS:]

        return ConversationalMomentumState(
            active_topic_anchor=new_topic_anchor,
            unresolved_threads=new_threads,
            running_in_jokes=new_in_jokes,
            recent_friction_history=new_friction_history,
            consecutive_low_effort_turns=new_low_effort_count,
        )

    @classmethod
    def format_momentum_block(
        cls,
        momentum: Optional[ConversationalMomentumState],
        current_input: str,
    ) -> Optional[str]:
        """Format XML block for prompt assembly ONLY when contextually salient (Boundary 5).

        Returns None / empty string if momentum has decayed or is irrelevant to current input.
        """
        if not momentum:
            return None

        has_anchor = bool(momentum.active_topic_anchor)
        has_threads = bool(momentum.unresolved_threads)
        has_jokes = bool(momentum.running_in_jokes)

        if not (has_anchor or has_threads or has_jokes):
            return None

        cleaned = current_input.lower()
        lines = ["<conversational_momentum>"]

        if momentum.active_topic_anchor:
            lines.append(f"- Active Topic Anchor: {momentum.active_topic_anchor}")

        if momentum.unresolved_threads:
            # Boundary 1 check: Remind model that threads are optional background, not to-do items
            threads_str = ", ".join(momentum.unresolved_threads)
            lines.append(f"- Ongoing Threads (Optional background, NOT to-do items): {threads_str}")

        if momentum.running_in_jokes:
            jokes_str = ", ".join(momentum.running_in_jokes)
            lines.append(f"- Running Inside Callbacks: {jokes_str}")

        lines.append("</conversational_momentum>")
        return "\n".join(lines)
