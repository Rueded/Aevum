"""Surface Persona Evolution Service for Aevum Core (Phase D).

Controls the safe, grounded evolution of surface persona habits, speech quirks,
and developing preferences while guaranteeing the immutable Core Anchor remains unviolated.
"""

from datetime import datetime, timezone
import logging
from typing import Optional, Sequence

from app.character.models import (
    Boundary,
    CharacterCoreAnchor,
    CharacterDefinition,
    CharacterSurfacePersona,
    Personality,
    Preference,
)

logger = logging.getLogger(__name__)


class SurfacePersonaEvolutionService:
    """Orchestrates structured surface persona updates without violating Core Anchors."""

    @classmethod
    def evolve_surface_persona(
        cls,
        definition: CharacterDefinition,
        new_conversational_style: Optional[Sequence[str]] = None,
        new_speech_habits: Optional[Sequence[str]] = None,
        new_active_topics: Optional[Sequence[str]] = None,
        new_preferences: Optional[Sequence[Preference]] = None,
        mood_expression_bias: Optional[str] = None,
    ) -> CharacterDefinition:
        """Create an evolved CharacterDefinition with updated surface persona.

        Args:
            definition: Current authoritative CharacterDefinition.
            new_conversational_style: Optional updated surface conversational styles.
            new_speech_habits: Optional updated speech habits.
            new_active_topics: Optional updated current topics of interest.
            new_preferences: Optional new or updated preferences.
            mood_expression_bias: Optional bias in emotional surface display.

        Returns:
            A new, version-bumped CharacterDefinition preserving the exact Core Anchor.

        Raises:
            ValueError: If proposed updates attempt to contradict core boundaries.
        """
        anchor = definition.core_anchor
        current_persona = definition.surface_persona

        # Validation: Check if any new preference conflicts with core boundaries
        if new_preferences:
            for pref in new_preferences:
                for b in anchor.core_boundaries:
                    if pref.item.lower() in b.description.lower() and pref.sentiment.value == "like":
                        # Check if boundary expressly forbids this
                        if "does not" in b.description.lower() or "never" in b.description.lower():
                            raise ValueError(
                                f"Cannot add preference '{pref.item}' which violates core boundary: '{b.description}'"
                            )

        # Merge preferences
        merged_prefs: list[Preference] = list(definition.preferences)
        if new_preferences:
            existing_items = {p.item.lower() for p in merged_prefs}
            for np in new_preferences:
                if np.item.lower() not in existing_items:
                    merged_prefs.append(np)
                    existing_items.add(np.item.lower())

        # Construct new surface persona
        updated_style = (
            tuple(new_conversational_style)
            if new_conversational_style is not None
            else current_persona.conversational_style
        )
        updated_habits = (
            tuple(new_speech_habits)
            if new_speech_habits is not None
            else current_persona.speech_habits
        )
        updated_topics = (
            tuple(new_active_topics)
            if new_active_topics is not None
            else current_persona.active_topics_of_interest
        )
        updated_bias = (
            mood_expression_bias
            if mood_expression_bias is not None
            else current_persona.mood_expression_bias
        )

        new_surface_persona = CharacterSurfacePersona(
            conversational_style=updated_style,
            speech_habits=updated_habits,
            active_topics_of_interest=updated_topics,
            evolving_preferences=tuple(merged_prefs),
            mood_expression_bias=updated_bias,
        )

        updated_personality = Personality(
            core_traits=anchor.core_traits,
            social_style=definition.personality.social_style,
            emotional_style=definition.personality.emotional_style,
            communication_style=updated_style,
            behavioral_tendencies=updated_habits,
            flaws=definition.personality.flaws,
        )

        evolved = CharacterDefinition(
            id=definition.id,
            version=definition.version + 1,
            updated_at=datetime.now(timezone.utc),
            identity=anchor.identity,
            personality=updated_personality,
            preferences=tuple(merged_prefs),
            boundaries=anchor.core_boundaries,
        )
        object.__setattr__(evolved, "_custom_surface_persona", new_surface_persona)
        return evolved
