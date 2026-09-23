"""Proactive Intent Engine (Phase 8 Lock-in 1).

Translates internal psychological state, desires, relational dynamics,
and factual life events into explicit ProactiveIntent objects.

Invariant: A LifeEvent alone NEVER implies an unsolicited reach-out.
Grounding in factual events provides context, but communication intent
requires adequate social drive, relational comfort, and cognitive availability.
"""

from typing import Optional

from app.proactive.models import (
    ProactiveIntent,
    ProactiveIntentType,
)


class ProactiveIntentEngine:
    """Deterministic engine evaluating character intent to initiate contact."""

    MIN_INTENT_THRESHOLD: float = 0.40
    FATIGUE_CEILING: float = 0.85
    SOLITUDE_CEILING: float = 0.70
    RELATIONSHIP_FLOOR: float = 0.20

    def evaluate_intent(
        self,
        character_id: str,
        social_need: float,
        solitude_need: float,
        relationship_comfort: float,
        relationship_trust: float,
        fatigue: float,
        attention_availability: float,
        current_activity: Optional[str] = None,
        life_event_id: Optional[str] = None,
        life_event_type: Optional[str] = None,
        activity_title: Optional[str] = None,
        desire_focus: Optional[str] = None,
        topic_hook: Optional[str] = None,
    ) -> Optional[ProactiveIntent]:
        """
        Evaluate whether current internal state warrants forming a ProactiveIntent.

        Returns None if intent strength is below threshold or suppressed by internal constraints.
        """
        # 1. Physiological unavailability: sleeping or exhausted
        if current_activity in ("SLEEP", "night_sleep", "nap"):
            return None
        if fatigue >= self.FATIGUE_CEILING:
            return None

        # 2. Solitude preference suppression: character prefers quiet introspection
        if solitude_need >= self.SOLITUDE_CEILING:
            return None

        # 3. Relational guard: uninvited reach-outs require minimal comfort and trust
        if relationship_comfort < self.RELATIONSHIP_FLOOR or relationship_trust < self.RELATIONSHIP_FLOOR:
            return None

        # 4. Activity completion / experience sharing opportunity
        if life_event_type == "ACTIVITY_COMPLETED" or activity_title is not None:
            # Base sharing drive
            drive = (
                (social_need * 0.40)
                + (relationship_comfort * 0.30)
                + (relationship_trust * 0.30)
                - (solitude_need * 0.40)
            )

            # Bonus if desire focus aligns with communicative connection
            if desire_focus and any(
                keyword in desire_focus.lower()
                for keyword in ("share", "tell", "talk", "connect", "discuss", "user")
            ):
                drive += 0.15

            # Modulate by attention availability
            attention_factor = max(0.20, min(1.0, attention_availability))
            final_strength = max(0.0, min(1.0, drive * attention_factor))

            if final_strength < self.MIN_INTENT_THRESHOLD:
                # Event occurred, but drive insufficient -> internal experience only
                return None

            return ProactiveIntent(
                character_id=character_id,
                intent_type=ProactiveIntentType.SHARE_EXPERIENCE,
                intent_strength=round(final_strength, 4),
                grounding_event_id=life_event_id,
                grounding_activity_title=activity_title,
                topic_hook=topic_hook or f"Shared reflection on {activity_title}",
                reasoning_trace=(
                    f"Drive {final_strength:.2f} >= {self.MIN_INTENT_THRESHOLD} "
                    f"from activity '{activity_title}' with comfort {relationship_comfort:.2f}"
                ),
            )

        # 5. Scheduled reminder
        if life_event_type == "SCHEDULED_REMINDER":
            return ProactiveIntent(
                character_id=character_id,
                intent_type=ProactiveIntentType.TASK_REMINDER,
                intent_strength=0.90,
                grounding_event_id=life_event_id,
                topic_hook=topic_hook or "Scheduled reminder",
                reasoning_trace="Authoritative scheduled task reminder",
            )

        # 6. Spontaneous social check-in
        spontaneous_drive = (
            (social_need * 0.50)
            + (relationship_comfort * 0.30)
            + (relationship_trust * 0.20)
            - (solitude_need * 0.50)
        )
        final_spontaneous = max(0.0, min(1.0, spontaneous_drive * attention_availability))

        if final_spontaneous >= 0.55:
            return ProactiveIntent(
                character_id=character_id,
                intent_type=ProactiveIntentType.SOCIAL_CHECKIN,
                intent_strength=round(final_spontaneous, 4),
                grounding_event_id=life_event_id,
                topic_hook=topic_hook or "Casual check-in",
                reasoning_trace=f"Spontaneous social drive {final_spontaneous:.2f} >= 0.55",
            )

        return None
