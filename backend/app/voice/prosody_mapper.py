"""Emotional prosody modulation engine for Project Aevum (Phase 10.2).

Governed by ADR-021:
- Lock C: Prosody Consumer Isolation:
  - Prosody is deterministically derived from EmotionState (EmotionType, intensity)
    and CharacterMood via ProsodyMapper.
  - LLM prompts do not invent or dictate emotional prosody.
  - ProsodyMapper is a pure read-only consumer and possesses zero authority to
    mutate EmotionState or CharacterState.
- Lock D: Categorical EpistemicCue:
  - Rejects continuous pseudo-probability floats (e.g. confidence=0.63).
  - Discrete EpistemicCue values (CERTAIN, UNCERTAIN, AMBIGUOUS, CONTESTED, UNKNOWN)
    deterministically trigger cadence adjustment and hesitation pauses.
- Determinism:
  - Pure functional mapping: identical input parameters guarantee bit-identical ProsodyConfig.
"""

from typing import Optional, Union
from app.character.state_models import CharacterMood, CharacterState
from app.character.engine_models import CharacterStateContext
from app.emotion.emotion_models import EmotionState, EmotionType
from app.voice.voice_models import EpistemicCue, ProsodyConfig


# Baseline emotional acoustic profiles
# Rate deviation (from 1.0), Pitch deviation in semitones (from 0.0), Volume gain in dB (from 0.0), style descriptor
_EMOTION_ACOUSTIC_PROFILES: dict[EmotionType, tuple[float, float, float, Optional[str]]] = {
    EmotionType.NEUTRAL: (0.00, 0.00, 0.00, None),
    EmotionType.HAPPY: (+0.08, +1.50, +1.00, "cheerful"),
    EmotionType.EXCITED: (+0.15, +2.50, +2.00, "excited"),
    EmotionType.CALM: (-0.05, -0.50, -1.00, "calm"),
    EmotionType.CONTENT: (-0.02, +0.50, 0.00, "content"),
    EmotionType.CURIOUS: (+0.04, +1.20, +0.50, "curious"),
    EmotionType.AMUSED: (+0.06, +1.80, +1.00, "amused"),
    EmotionType.SAD: (-0.10, -1.80, -2.00, "somber"),
    EmotionType.DISAPPOINTED: (-0.08, -1.20, -1.50, "disappointed"),
    EmotionType.WORRIED: (+0.05, +1.00, -0.50, "concerned"),
    EmotionType.FRUSTRATED: (+0.08, +1.50, +2.00, "frustrated"),
    EmotionType.IRRITATED: (+0.04, +0.80, +1.50, "irritated"),
    EmotionType.ANGRY: (+0.10, +2.00, +3.50, "firm"),
    EmotionType.LONELY: (-0.08, -1.50, -2.50, "somber"),
    EmotionType.EMBARRASSED: (-0.04, +1.00, -1.50, "timid"),
    EmotionType.NERVOUS: (+0.08, +1.80, -1.00, "timid"),
    EmotionType.TIRED: (-0.12, -1.50, -2.50, "whisper"),
}

# Mood bias offsets: (rate_delta, pitch_delta, volume_delta)
_MOOD_BIAS_OFFSETS: dict[CharacterMood, tuple[float, float, float]] = {
    CharacterMood.NEUTRAL: (0.00, 0.00, 0.00),
    CharacterMood.GOOD: (+0.03, +0.30, 0.00),
    CharacterMood.LOW: (-0.04, -0.50, -1.00),
    CharacterMood.IRRITATED: (0.00, 0.00, +0.50),
    CharacterMood.CALM: (-0.02, -0.20, 0.00),
    CharacterMood.TIRED: (-0.05, -0.50, -1.00),
    CharacterMood.FOCUSED: (+0.02, 0.00, 0.00),
}

# Epistemic hesitation offsets: (hesitation_pause_ms, rate_delta, pitch_delta)
_EPISTEMIC_CUE_MODULATIONS: dict[EpistemicCue, tuple[int, float, float]] = {
    EpistemicCue.CERTAIN: (0, 0.00, 0.00),
    EpistemicCue.UNCERTAIN: (250, -0.04, -0.30),
    EpistemicCue.AMBIGUOUS: (350, -0.05, -0.50),
    EpistemicCue.CONTESTED: (200, -0.02, +0.40),
    EpistemicCue.UNKNOWN: (400, -0.06, -0.80),
}


class ProsodyMapper:
    """Deterministic mapper converting emotional and epistemic states into ProsodyConfig.

    Pure functional consumer:
    - Zero state mutation: Does not modify EmotionState or CharacterState.
    - Zero LLM generation: Acoustic parameters follow deterministic mathematical transformations.
    - Bounded safety: All output values are validated by ProsodyConfig.
    """

    @classmethod
    def map_prosody(
        cls,
        emotion_type: EmotionType,
        intensity: float,
        mood: Optional[CharacterMood] = None,
        epistemic_cue: EpistemicCue = EpistemicCue.CERTAIN,
    ) -> ProsodyConfig:
        """Deterministically map emotional affect and epistemic certainty to acoustic prosody."""
        # 1. Normalize and bound intensity to [0.0, 1.0]
        clamped_intensity = max(0.0, min(1.0, float(intensity)))

        # 2. Retrieve emotion profile
        rate_delta, pitch_delta, volume_delta, style_tag = _EMOTION_ACOUSTIC_PROFILES.get(
            emotion_type, (0.00, 0.00, 0.00, None)
        )

        # Scale emotion deviation by intensity factor
        raw_rate = 1.00 + (rate_delta * clamped_intensity)
        raw_pitch = pitch_delta * clamped_intensity
        raw_volume = volume_delta * clamped_intensity

        # Only apply style tag if intensity is meaningful (>= 0.30)
        effective_style = style_tag if clamped_intensity >= 0.30 else None

        # 3. Apply baseline mood bias if present
        if mood is not None:
            mood_rate_bias, mood_pitch_bias, mood_vol_bias = _MOOD_BIAS_OFFSETS.get(
                mood, (0.00, 0.00, 0.00)
            )
            raw_rate += mood_rate_bias
            raw_pitch += mood_pitch_bias
            raw_volume += mood_vol_bias

        # 4. Apply categorical EpistemicCue hesitation modulation (ADR-021 Lock D)
        hesitation_ms, epistemic_rate_bias, epistemic_pitch_bias = _EPISTEMIC_CUE_MODULATIONS.get(
            epistemic_cue, (0, 0.00, 0.00)
        )
        raw_rate += epistemic_rate_bias
        raw_pitch += epistemic_pitch_bias

        # 5. Bound and round to physical ProsodyConfig constraints
        clamped_rate = max(0.50, min(2.00, round(raw_rate, 3)))
        clamped_pitch = max(-12.0, min(12.0, round(raw_pitch, 2)))
        clamped_volume = max(-20.0, min(10.0, round(raw_volume, 2)))
        clamped_pause = max(0, min(2000, hesitation_ms))

        return ProsodyConfig(
            rate_multiplier=clamped_rate,
            pitch_shift_semitones=clamped_pitch,
            volume_gain_db=clamped_volume,
            style_tag=effective_style,
            hesitation_pause_ms=clamped_pause,
        )

    @classmethod
    def from_states(
        cls,
        emotion_state: EmotionState,
        character_state: Optional[Union[CharacterState, CharacterStateContext]] = None,
        epistemic_cue: EpistemicCue = EpistemicCue.CERTAIN,
    ) -> ProsodyConfig:
        """Construct ProsodyConfig directly from domain state objects.

        Strictly read-only consumer: does not mutate emotion_state or character_state.
        """
        mood = character_state.mood if character_state is not None else None
        return cls.map_prosody(
            emotion_type=emotion_state.emotion_type,
            intensity=emotion_state.intensity,
            mood=mood,
            epistemic_cue=epistemic_cue,
        )
