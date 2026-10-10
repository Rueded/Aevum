"""Deterministic Affective Visual Expression Mapping Engine (Phase 11.2).

Governed by ADR-022:
- Lock 2: Unidirectional Affective Visual Mapping (Backend EmotionState/Mood -> VisualExpressionConfig).
- Lock 7: Renderer State != Character State (Render Instruction != Character State).
- Mind/Body Boundary: ExpressionMapper is a pure deterministic presentation policy,
  NOT an emotion inference engine or psychological truth.
- Read-Only Consumer: Strictly zero mutation of EmotionState or CharacterState.
- Zero DB, Zero LLM, Zero set_fact authority.
"""

from __future__ import annotations

from typing import Dict, Optional

from app.character.state_models import CharacterMood
from app.emotion.emotion_models import EmotionState, EmotionType
from app.visual.visual_models import (
    VisualExpressionConfig,
    VisualExpressionType,
)

# Mapping table representing renderer presentation policy across all 17 canonical EmotionTypes.
# Note: This is an aesthetic presentation selection, NOT a psychological universal identity.
_EMOTION_PRESENTATION_POLICY: Dict[EmotionType, VisualExpressionType] = {
    EmotionType.NEUTRAL: VisualExpressionType.NEUTRAL,
    EmotionType.HAPPY: VisualExpressionType.JOY,
    EmotionType.CALM: VisualExpressionType.NEUTRAL,
    EmotionType.EXCITED: VisualExpressionType.JOY,
    EmotionType.CURIOUS: VisualExpressionType.THINKING,
    EmotionType.AMUSED: VisualExpressionType.SMILE,
    EmotionType.CONTENT: VisualExpressionType.SMILE,
    EmotionType.SAD: VisualExpressionType.SAD,
    EmotionType.DISAPPOINTED: VisualExpressionType.SAD,
    EmotionType.WORRIED: VisualExpressionType.WORRIED,
    EmotionType.FRUSTRATED: VisualExpressionType.POUT,
    EmotionType.IRRITATED: VisualExpressionType.POUT,
    EmotionType.ANGRY: VisualExpressionType.POUT,
    EmotionType.LONELY: VisualExpressionType.SAD,
    EmotionType.EMBARRASSED: VisualExpressionType.BLUSH,
    EmotionType.NERVOUS: VisualExpressionType.WORRIED,
    EmotionType.TIRED: VisualExpressionType.TIRED,
}


class ExpressionMapper:
    """Pure, deterministic presentation policy mapping emotions into render instructions.

    "Given the current canonical emotional state, this renderer chooses this presentation."
    """

    @classmethod
    def map_expression(
        cls,
        emotion: EmotionState,
        mood: Optional[CharacterMood] = None,
    ) -> VisualExpressionConfig:
        """Deterministically map an EmotionState and optional CharacterMood into a VisualExpressionConfig.

        Pure read-only consumer: does not mutate the passed emotion state or mood.
        """
        return cls.from_types(
            emotion_type=emotion.emotion_type,
            intensity=emotion.intensity,
            mood=mood,
        )

    @classmethod
    def from_types(
        cls,
        emotion_type: EmotionType,
        intensity: float = 1.0,
        mood: Optional[CharacterMood] = None,
    ) -> VisualExpressionConfig:
        """Map raw emotion parameters and mood bias into VisualExpressionConfig."""
        # Clamp intensity safely to [0.0, 1.0]
        clamped_intensity = max(0.0, min(1.0, float(intensity)))

        # 1. Base presentation expression from policy table
        base_expression = _EMOTION_PRESENTATION_POLICY.get(
            emotion_type, VisualExpressionType.NEUTRAL
        )

        # 2. Intensity-dependent nuances
        # e.g., low-intensity HAPPY presents as gentle SMILE rather than full JOY
        if emotion_type == EmotionType.HAPPY and clamped_intensity <= 0.50:
            target_expression = VisualExpressionType.SMILE
        else:
            target_expression = base_expression

        # 3. Mood presentation baseline bias (applied only when dominant emotion is NEUTRAL or CALM)
        if emotion_type in (EmotionType.NEUTRAL, EmotionType.CALM) and mood is not None:
            if mood == CharacterMood.TIRED:
                target_expression = VisualExpressionType.TIRED
            elif mood == CharacterMood.GOOD:
                target_expression = VisualExpressionType.SMILE
            elif mood == CharacterMood.LOW:
                target_expression = VisualExpressionType.SAD
            elif mood == CharacterMood.IRRITATED:
                target_expression = VisualExpressionType.POUT
            elif mood == CharacterMood.FOCUSED:
                target_expression = VisualExpressionType.THINKING

        # 4. Deterministic parameter overrides based on emotion and intensity
        parameter_overrides: Dict[str, float] = {}

        if emotion_type == EmotionType.EMBARRASSED:
            parameter_overrides["ParamCheek"] = round(0.5 + 0.5 * clamped_intensity, 3)
        elif emotion_type == EmotionType.EXCITED:
            parameter_overrides["ParamCheek"] = round(0.4 * clamped_intensity, 3)
            parameter_overrides["ParamEyeLSmile"] = round(0.8 * clamped_intensity, 3)
            parameter_overrides["ParamEyeRSmile"] = round(0.8 * clamped_intensity, 3)
        elif emotion_type == EmotionType.ANGRY:
            parameter_overrides["ParamBrowLAngle"] = round(-0.6 * clamped_intensity, 3)
            parameter_overrides["ParamBrowRAngle"] = round(-0.6 * clamped_intensity, 3)

        # 5. Transition duration modulation based on target expression
        if target_expression == VisualExpressionType.SURPRISE:
            transition_ms = 150  # Quick reaction
        elif target_expression in (VisualExpressionType.TIRED, VisualExpressionType.SAD):
            transition_ms = 500  # Sluggish or relaxed transition
        else:
            transition_ms = 300  # Standard default

        return VisualExpressionConfig(
            expression=target_expression,
            intensity=clamped_intensity,
            parameter_overrides=parameter_overrides,
            transition_duration_ms=transition_ms,
        )
