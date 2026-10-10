"""Deterministic Visual Motion Mapping Engine (Phase 11.2).

Governed by ADR-022:
- Lock 2: Unidirectional Affective Visual Mapping (Backend CharacterMood -> VisualMotionCommand).
- Lock 7: Renderer State != Character State (Render Instruction != Character State).
- Mind/Body Boundary: MotionMapper is a pure deterministic presentation policy,
  NOT an emotion inference engine or psychological truth.
- Read-Only Consumer: Strictly zero mutation of CharacterMood, CharacterState, or EmotionState.
- Zero DB, Zero LLM, Zero set_fact authority.
"""

from __future__ import annotations

from typing import Dict

from app.character.state_models import CharacterMood
from app.visual.visual_models import (
    VisualMotionArchetype,
    VisualMotionCommand,
)

# Baseline idle motion mapping policy across all 7 canonical CharacterMoods.
# Note: This is an aesthetic presentation selection, NOT a psychological universal identity.
_MOOD_MOTION_POLICY: Dict[CharacterMood, VisualMotionArchetype] = {
    CharacterMood.NEUTRAL: VisualMotionArchetype.IDLE_NORMAL,
    CharacterMood.GOOD: VisualMotionArchetype.IDLE_ENERGETIC,
    CharacterMood.CALM: VisualMotionArchetype.IDLE_NORMAL,
    CharacterMood.LOW: VisualMotionArchetype.IDLE_DROWSY,
    CharacterMood.TIRED: VisualMotionArchetype.IDLE_DROWSY,
    CharacterMood.IRRITATED: VisualMotionArchetype.SHAKE_HEAD,
    CharacterMood.FOCUSED: VisualMotionArchetype.THINKING_TILT,
}


class MotionMapper:
    """Pure, deterministic presentation policy mapping mood and situation into motion render instructions.

    "Given the current canonical character mood and situational flags, this renderer chooses this motion."
    """

    @classmethod
    def map_motion(
        cls,
        mood: CharacterMood,
        is_speaking: bool = False,
        is_thinking: bool = False,
    ) -> VisualMotionCommand:
        """Deterministically map CharacterMood and situational flags into a VisualMotionCommand.

        Pure read-only consumer: does not mutate the passed mood or any backend state.
        """
        # Situational overlays take precedence over baseline idle posture
        if is_speaking:
            return VisualMotionCommand(
                archetype=VisualMotionArchetype.TALKING_CASUAL,
                priority=3,
                loop=True,
                fade_in_ms=250,
                fade_out_ms=250,
            )

        if is_thinking:
            return VisualMotionCommand(
                archetype=VisualMotionArchetype.THINKING_TILT,
                priority=2,
                loop=True,
                fade_in_ms=350,
                fade_out_ms=350,
            )

        # Baseline mood posture
        archetype = _MOOD_MOTION_POLICY.get(mood, VisualMotionArchetype.IDLE_NORMAL)

        # Non-looping reactive motions vs looping idle postures
        if archetype == VisualMotionArchetype.SHAKE_HEAD:
            return VisualMotionCommand(
                archetype=archetype,
                priority=2,
                loop=False,
                fade_in_ms=300,
                fade_out_ms=400,
            )

        # Idle posture timing modulation
        if mood == CharacterMood.TIRED:
            fade_ms = 800  # Slow, heavy posture shift
        elif mood == CharacterMood.GOOD:
            fade_ms = 400  # Crisp, energetic posture shift
        else:
            fade_ms = 500  # Standard default

        return VisualMotionCommand(
            archetype=archetype,
            priority=1,
            loop=True,
            fade_in_ms=fade_ms,
            fade_out_ms=fade_ms,
        )

    @classmethod
    def from_mood(cls, mood: CharacterMood) -> VisualMotionCommand:
        """Convenience method for mapping baseline mood with default situational context."""
        return cls.map_motion(mood=mood, is_speaking=False, is_thinking=False)
