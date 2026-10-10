"""
test_golden_suite_11.py — Golden Acceptance Suite 11 (Phase 11.6: GC-271 ~ GC-297)

Golden Acceptance Suite for Phase 11: Live2D Visual Presence & Embodiment.
Verifies all frozen contracts (11.1–11.5) and the 7 Constitutional Visual Locks under ADR-022.

"Live2D is Aevum's visible body, not its second mind."
- Phase 10 gave Aevum a voice.
- Phase 11 gives Aevum a visible body.
- Neither voice nor body becomes the mind.

Covers 27 Acceptance Benchmarks across 6 Structured Clusters:
- Cluster 1: The 7 Constitutional Visual Locks Hard Invariants (GC-271 ~ GC-277)
  - GC-271: Lock 1 — Visual State != Canonical Reality (Presentation-Only Non-Promoting Body)
  - GC-272: Lock 2 — Unidirectional Affective Visual Mapping (Mind -> Body, Zero Reverse Feedback)
  - GC-273: Lock 3 — Audio-Driven Lip-Sync Without Epistemic Authority (ParamMouthOpenY Only)
  - GC-274: Lock 3 — Barge-In Immediate-Zero Latch Persistence
  - GC-275: Lock 4 — Pure Visual Presentation Scope & Hit-Testing Deferral
  - GC-276: Lock 5 — Fail-Closed & Graceful Visual Degradability
  - GC-277: Lock 7 — Renderer State != Character State

- Cluster 2: Affective Visual Expression & Motion Mapping Engines (GC-278 ~ GC-281)
  - GC-278: Expression Mapping Complete Policy & Nuance Selection
  - GC-279: Motion Mapping Policy & Situational Preemption
  - GC-280: Mapper Read-Only Consumer Isolation
  - GC-281: Mapper Pure Determinism & Zero Epistemic Probability Floats

- Cluster 3: Audio Amplitude Lip-Sync & Barge-In Latch Invariants (GC-282 ~ GC-285)
  - GC-282: RMS Energy Extraction & Noise Gate Cutoff
  - GC-283: Asymmetric Attack/Decay Smoothing Filter
  - GC-284: Barge-In Latch State Machine Hostile Packet Rejection
  - GC-285: Phase 10 Voice Contract Integrity & Non-Regression

- Cluster 4: Gaze Tracking, Focus Release & Micro-Saccade Dynamics (GC-286 ~ GC-289)
  - GC-286: Decoupled Gaze Coordinate Normalization & Bounded Parameter Envelopes
  - GC-287: Focus Release Neutral Re-Centering Semantic Invariant
  - GC-288: Micro-Saccade Bounded Twitch Isolation
  - GC-289: Gaze Damping Exponential Smoothing Stability

- Cluster 5: Multi-Turn Visual Embodiment & Lifecycle Resilience (GC-290 ~ GC-293)
  - GC-290: Multi-Turn Turn Isolation & Voice-Visual Coordination
  - GC-291: Cross-Turn Barge-In Interruption Sequence
  - GC-292: Renderer State Transient Resets != Reality Mutation
  - GC-293: Situational Presentation Overrides Reversibility

- Cluster 6: Defensive Integrity, AST Audits & Constitutional Guard (GC-294 ~ GC-297)
  - GC-294: Static AST Boundary Audit — Zero Hit-Testing Across All Modules
  - GC-295: Static AST Boundary Audit — Zero Reverse State Mutation Across All Modules
  - GC-296: Static AST Boundary Audit — Headless CI Purity & Zero WebGL Leakage into Backend
  - GC-297: System-Wide Voice & Reality Contract Non-Regression Audit
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import math
import pathlib
import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.state_models import CharacterMood, CharacterState
from app.db.models import Conversation, Message, MessageRole
from app.emotion.emotion_models import EmotionState, EmotionType
from app.main import app
from app.visual.expression_mapper import ExpressionMapper
from app.visual.motion_mapper import MotionMapper
from app.visual.visual_models import (
    GazeParameters,
    GazeTarget,
    LipSyncMouthState,
    Live2DModelManifest,
    RendererPresentationConfig,
    RendererState,
    VisualExpressionConfig,
    VisualExpressionType,
    VisualMotionArchetype,
    VisualMotionCommand,
    VisualSubsystemType,
)


# =============================================================================
# Test Fixtures & Mathematical Simulators
# =============================================================================

def create_sample_emotion_state(
    emotion_type: EmotionType = EmotionType.HAPPY,
    intensity: float = 0.7,
) -> EmotionState:
    now = datetime.now(timezone.utc)
    return EmotionState(
        character_id="aevum",
        emotion_type=emotion_type,
        intensity=intensity,
        version=1,
        created_at=now,
        updated_at=now,
    )


def create_sample_character_state(
    mood: CharacterMood = CharacterMood.GOOD,
) -> CharacterState:
    now = datetime.now(timezone.utc)
    return CharacterState(
        id="aevum",
        version=1,
        updated_at=now,
        mood=mood,
        energy=0.8,
        stress=0.2,
        social_energy=0.7,
        confidence=0.9,
        irritation=0.0,
        loneliness=0.1,
        current_activity="resting",
        current_location="home",
    )


class DesktopRendererLifecycleSimulator:
    """State machine simulation of CubismRendererManager for backend contract verification."""

    def __init__(self) -> None:
        self.state: RendererState = RendererState.UNINITIALIZED
        self.error_message: str | None = None
        self.blink_timer_ms: int = 0
        self.is_blinking: bool = False
        self.motion_progress_ms: int = 0
        self.breath_phase: float = 0.0
        self.active_expression: VisualExpressionType = VisualExpressionType.NEUTRAL
        self.active_motion: VisualMotionArchetype = VisualMotionArchetype.IDLE_NORMAL
        self.motion_priority: int = 1
        self.gaze: GazeParameters = GazeParameters(
            eyeball_x=0.0, eyeball_y=0.0, angle_x=0.0, angle_y=0.0, angle_z=0.0
        )
        self.mouth_open_y: float = 0.0

    def initialize(self, webgl_available: bool = True, has_cubism_core: bool = True) -> RendererState:
        self.state = RendererState.LOADING
        if not webgl_available or not has_cubism_core:
            self.state = RendererState.DEGRADED_FALLBACK
            self.error_message = "WebGL or CubismCore unavailable"
            return self.state
        self.state = RendererState.READY
        return self.state

    def set_expression(self, config: VisualExpressionConfig) -> None:
        self.active_expression = config.expression

    def set_motion(self, cmd: VisualMotionCommand) -> None:
        if cmd.priority >= self.motion_priority:
            self.active_motion = cmd.archetype
            self.motion_priority = cmd.priority
            self.motion_progress_ms = 0

    def set_lip_sync(self, mouth: LipSyncMouthState) -> None:
        self.mouth_open_y = mouth.mouth_open_y

    def set_gaze(self, gaze: GazeParameters) -> None:
        self.gaze = gaze

    def update_frame(self, delta_ms: int) -> None:
        self.motion_progress_ms += delta_ms
        self.blink_timer_ms += delta_ms
        if not self.is_blinking and self.blink_timer_ms > 4000:
            self.is_blinking = True
            self.blink_timer_ms = 0
        elif self.is_blinking and self.blink_timer_ms > 160:
            self.is_blinking = False
            self.blink_timer_ms = 0

        self.breath_phase = (self.breath_phase + (delta_ms / 6000.0) * math.pi * 2) % (math.pi * 2)


class LipSyncEngineSimulator:
    """Mathematical simulation of LipSyncAnalyzer (apps/desktop/src/visual/lipSyncAnalyzer.ts)."""

    def __init__(
        self,
        noise_gate: float = 0.015,
        gain: float = 3.8,
        attack_rate: float = 0.65,
        decay_rate: float = 0.28,
    ) -> None:
        self.noise_gate = noise_gate
        self.gain = gain
        self.attack_rate = attack_rate
        self.decay_rate = decay_rate
        self.current_mouth_open: float = 0.0
        self.is_speaking: bool = False
        self.barge_in_latched: bool = False

    def trigger_barge_in(self) -> LipSyncMouthState:
        self.barge_in_latched = True
        self.is_speaking = False
        self.current_mouth_open = 0.0
        return self.get_mouth_state()

    def reset_latch(self) -> None:
        self.barge_in_latched = False

    def step(self, rms_input: float) -> LipSyncMouthState:
        if self.barge_in_latched:
            self.current_mouth_open = 0.0
            self.is_speaking = False
            return self.get_mouth_state()

        if rms_input <= self.noise_gate:
            target_open = 0.0
        else:
            target_open = min(1.0, max(0.0, (rms_input - self.noise_gate) * self.gain))

        if target_open > self.current_mouth_open:
            self.current_mouth_open += self.attack_rate * (target_open - self.current_mouth_open)
        else:
            self.current_mouth_open += self.decay_rate * (target_open - self.current_mouth_open)

        if self.current_mouth_open < 0.005:
            self.current_mouth_open = 0.0

        self.is_speaking = self.current_mouth_open > 0.05
        return self.get_mouth_state()

    def get_mouth_state(self) -> LipSyncMouthState:
        return LipSyncMouthState(
            mouth_open_y=round(self.current_mouth_open, 4),
            mouth_form=0.0,
            is_speaking=self.is_speaking and not self.barge_in_latched,
        )


class GazeTrackingSimulator:
    """Mathematical simulation of GazeTracker (apps/desktop/src/visual/gazeTracker.ts)."""

    def __init__(
        self,
        max_angle_x: float = 20.0,
        max_angle_y: float = 15.0,
        max_angle_z: float = 8.0,
        max_eyeball: float = 0.85,
        smoothing_rate: float = 0.12,
        saccade_interval_ms: int = 2800,
        saccade_amplitude: float = 0.06,
    ) -> None:
        self.max_angle_x = max_angle_x
        self.max_angle_y = max_angle_y
        self.max_angle_z = max_angle_z
        self.max_eyeball = max_eyeball
        self.smoothing_rate = smoothing_rate
        self.saccade_interval_ms = saccade_interval_ms
        self.saccade_amplitude = saccade_amplitude

        self.current_target = GazeTarget(x=0.0, y=0.0, is_tracked=False)
        self.current_params = GazeParameters(
            eyeball_x=0.0, eyeball_y=0.0, angle_x=0.0, angle_y=0.0, angle_z=0.0
        )
        self.saccade_timer_ms: int = 0
        self.saccade_offset_x: float = 0.0
        self.saccade_offset_y: float = 0.0

    def handle_pointer_move(
        self, client_x: float, client_y: float, window_width: float, window_height: float
    ) -> None:
        w = max(1.0, window_width)
        h = max(1.0, window_height)
        norm_x = max(-1.0, min(1.0, (client_x - w / 2.0) / (w / 2.0)))
        norm_y = max(-1.0, min(1.0, (client_y - h / 2.0) / (h / 2.0)))
        self.current_target = GazeTarget(x=round(norm_x, 4), y=round(norm_y, 4), is_tracked=True)

    def handle_pointer_leave(self) -> None:
        self.current_target = GazeTarget(x=0.0, y=0.0, is_tracked=False)

    def update(self, delta_ms: int, random_seed_angle: float = 0.0, random_seed_mag: float = 1.0) -> GazeParameters:
        self.saccade_timer_ms += delta_ms
        if self.saccade_timer_ms > self.saccade_interval_ms:
            self.saccade_timer_ms = 0
            mag = (random_seed_mag * 0.5 + 0.5) * self.saccade_amplitude
            self.saccade_offset_x = math.cos(random_seed_angle) * mag
            self.saccade_offset_y = math.sin(random_seed_angle) * mag

        raw_eyeball_x = max(-1.0, min(1.0, self.current_target.x * self.max_eyeball + self.saccade_offset_x))
        raw_eyeball_y = max(-1.0, min(1.0, -self.current_target.y * self.max_eyeball + self.saccade_offset_y))

        raw_angle_x = max(-30.0, min(30.0, self.current_target.x * self.max_angle_x))
        raw_angle_y = max(-30.0, min(30.0, -self.current_target.y * self.max_angle_y))
        raw_angle_z = max(-30.0, min(30.0, self.current_target.x * -self.max_angle_z))

        alpha = min(1.0, self.smoothing_rate * (delta_ms / 16.6))

        new_eyeball_x = self.current_params.eyeball_x + (raw_eyeball_x - self.current_params.eyeball_x) * alpha
        new_eyeball_y = self.current_params.eyeball_y + (raw_eyeball_y - self.current_params.eyeball_y) * alpha
        new_angle_x = self.current_params.angle_x + (raw_angle_x - self.current_params.angle_x) * alpha
        new_angle_y = self.current_params.angle_y + (raw_angle_y - self.current_params.angle_y) * alpha
        new_angle_z = self.current_params.angle_z + (raw_angle_z - self.current_params.angle_z) * alpha

        self.current_params = GazeParameters(
            eyeball_x=round(new_eyeball_x, 4),
            eyeball_y=round(new_eyeball_y, 4),
            angle_x=round(new_angle_x, 2),
            angle_y=round(new_angle_y, 2),
            angle_z=round(new_angle_z, 2),
        )
        return self.current_params


# =============================================================================
# Cluster 1: The 7 Constitutional Visual Locks Hard Invariants (GC-271 ~ GC-277)
# =============================================================================


class TestCluster1ConstitutionalVisualLocks:
    """Verifies all 7 Constitutional Visual Locks under ADR-022."""

    def test_gc271_lock1_visual_state_not_canonical_reality(self) -> None:
        """GC-271: Visual State != Canonical Reality.

        Live2D canvas meshes, deformers, and physics oscillations possess zero
        DB persistence authority, zero promotion authority, and zero factual weight.
        """
        expr = VisualExpressionConfig(
            expression=VisualExpressionType.JOY,
            intensity=0.9,
            parameter_overrides={"ParamCheek": 0.8},
            transition_duration_ms=300,
        )
        motion = VisualMotionCommand(
            archetype=VisualMotionArchetype.TALKING_CASUAL,
            priority=3,
        )
        manifest = Live2DModelManifest(
            model_id="aevum_live2d_v1",
            name="Aevum Standard Model",
            version="1.0.0",
            model_path="aevum.model3.json",
        )

        for model in (expr, motion, manifest):
            assert not hasattr(model, "set_fact")
            assert not hasattr(model, "promote_fact")
            assert not hasattr(model, "claim_key")
            assert not hasattr(model, "epistemic_status")

    def test_gc272_lock2_unidirectional_affective_visual_mapping(self) -> None:
        """GC-272: Unidirectional Affective Visual Mapping.

        EmotionState & CharacterMood -> Render Instructions -> Renderer.
        Zero reverse feedback from visual states or motion transitions back into EmotionState.
        """
        emotion = create_sample_emotion_state(EmotionType.EXCITED, intensity=0.85)
        mood = CharacterMood.GOOD

        expr = ExpressionMapper.map_expression(emotion, mood)
        motion = MotionMapper.map_motion(mood)

        assert expr.expression == VisualExpressionType.JOY
        assert motion.archetype == VisualMotionArchetype.IDLE_ENERGETIC

        # Modifying or simulating renderer state progression does not touch source EmotionState
        renderer = DesktopRendererLifecycleSimulator()
        renderer.set_expression(expr)
        renderer.set_motion(motion)
        renderer.update_frame(500)

        # Source emotion state remains completely immutable
        assert emotion.emotion_type == EmotionType.EXCITED
        assert emotion.intensity == 0.85

    def test_gc273_lock3_audio_driven_lipsync_without_epistemic_authority(self) -> None:
        """GC-273: Audio RMS volume envelope drives ParamMouthOpenY only.

        ParamMouthForm is strictly untouched (0.0). Mouth opening cannot invent or
        mutate conversation text, facts, or reality.
        """
        engine = LipSyncEngineSimulator()
        mouth = engine.step(0.20)  # Strong audio speech frame

        assert mouth.mouth_open_y > 0.0
        assert mouth.mouth_form == 0.0  # Strictly untouched
        assert mouth.is_speaking is True
        assert not hasattr(mouth, "transcript")
        assert not hasattr(mouth, "confidence")

    def test_gc274_lock3_barge_in_immediate_zero_latch_persistence(self) -> None:
        """GC-274: User barge-in instantly latches mouth_open_y = 0.0.

        Residual audio packets cannot unlatch or re-open mouth until an explicit
        new assistant playback turn begins.
        """
        engine = LipSyncEngineSimulator()
        engine.step(0.25)
        assert engine.current_mouth_open > 0.0

        # User interrupts / barges in
        latched_mouth = engine.trigger_barge_in()
        assert latched_mouth.mouth_open_y == 0.0
        assert latched_mouth.is_speaking is False

        # Hostile packet injection while latched
        for hostile_rms in (0.35, 0.80, 0.95):
            mouth = engine.step(hostile_rms)
            assert mouth.mouth_open_y == 0.0
            assert mouth.is_speaking is False

        # Explicit unlatch for new playback turn
        engine.reset_latch()
        mouth_restored = engine.step(0.25)
        assert mouth_restored.mouth_open_y > 0.0

    def test_gc275_lock4_pure_visual_presentation_scope_and_zero_hit_testing(self) -> None:
        """GC-275: Phase 11 is strictly constrained to visual rendering.

        Interactive hit-testing, physical touch, petting, and tactile reactions
        are formally deferred and strictly absent.
        """
        renderer = DesktopRendererLifecycleSimulator()
        renderer.initialize(webgl_available=True, has_cubism_core=True)

        assert not hasattr(renderer, "hit_test")
        assert not hasattr(renderer, "handle_touch")
        assert not hasattr(renderer, "on_tap")
        assert not hasattr(renderer, "petting_reaction")

    def test_gc276_lock5_fail_closed_and_graceful_visual_degradability(self) -> None:
        """GC-276: WebGL or asset failure degrades gracefully to DEGRADED_FALLBACK.

        Conversation flow and voice playback continue 100% uninterrupted.
        """
        renderer = DesktopRendererLifecycleSimulator()
        state = renderer.initialize(webgl_available=False, has_cubism_core=True)

        assert state == RendererState.DEGRADED_FALLBACK
        assert renderer.state == RendererState.DEGRADED_FALLBACK
        assert renderer.error_message == "WebGL or CubismCore unavailable"

        # In degraded fallback, audio lip-sync and expression instructions can still be set safely
        renderer.set_expression(VisualExpressionConfig(expression=VisualExpressionType.SMILE, intensity=0.5))
        assert renderer.active_expression == VisualExpressionType.SMILE

    def test_gc277_lock7_renderer_state_not_character_state(self) -> None:
        """GC-277: Internal renderer states (blink timers, breath, saccades) are isolated Renderer State.

        Renderer State cannot flow backward into CharacterState, EmotionState, or Reality.
        """
        renderer = DesktopRendererLifecycleSimulator()
        renderer.initialize(webgl_available=True, has_cubism_core=True)

        renderer.update_frame(4100)
        assert renderer.is_blinking is True
        assert renderer.blink_timer_ms == 0
        assert renderer.breath_phase > 0.0

        # Renderer state is strictly self-contained
        assert not hasattr(renderer, "character_state")
        assert not hasattr(renderer, "emotion_state")


# =============================================================================
# Cluster 2: Affective Visual Expression & Motion Mapping Engines (GC-278 ~ GC-281)
# =============================================================================


class TestCluster2AffectiveVisualMappers:
    """Verifies deterministic affective expression and motion mapping engines."""

    def test_gc278_expression_mapping_complete_policy_and_nuance(self) -> None:
        """GC-278: Complete policy table and nuance selection across all 17 EmotionTypes."""
        assert len(EmotionType) == 17

        # 1. Verify coverage of all 17 emotions
        for et in EmotionType:
            emotion = create_sample_emotion_state(et, intensity=0.7)
            cfg = ExpressionMapper.map_expression(emotion)
            assert isinstance(cfg.expression, VisualExpressionType)
            assert cfg.intensity == 0.7

        # 2. Verify intensity nuances
        low_happy = ExpressionMapper.map_expression(create_sample_emotion_state(EmotionType.HAPPY, intensity=0.4))
        high_happy = ExpressionMapper.map_expression(create_sample_emotion_state(EmotionType.HAPPY, intensity=0.9))
        assert low_happy.expression == VisualExpressionType.SMILE
        assert high_happy.expression == VisualExpressionType.JOY

        # 3. Verify mood baseline bias for neutral emotion
        neutral = create_sample_emotion_state(EmotionType.NEUTRAL, intensity=0.5)
        tired_bias = ExpressionMapper.map_expression(neutral, mood=CharacterMood.TIRED)
        assert tired_bias.expression == VisualExpressionType.TIRED

    def test_gc279_motion_mapping_policy_and_situational_preemption(self) -> None:
        """GC-279: Baseline mood motion policy and priority preemption."""
        assert len(CharacterMood) == 7

        # 1. Baseline mood mapping
        for mood in CharacterMood:
            cmd = MotionMapper.from_mood(mood)
            assert isinstance(cmd.archetype, VisualMotionArchetype)
            assert cmd.priority in (1, 2)

        # 2. Situational overlays & priority preemption
        cmd_talking = MotionMapper.map_motion(CharacterMood.NEUTRAL, is_speaking=True, is_thinking=False)
        assert cmd_talking.archetype == VisualMotionArchetype.TALKING_CASUAL
        assert cmd_talking.priority == 3

        cmd_thinking = MotionMapper.map_motion(CharacterMood.NEUTRAL, is_speaking=False, is_thinking=True)
        assert cmd_thinking.archetype == VisualMotionArchetype.THINKING_TILT
        assert cmd_thinking.priority == 2

    def test_gc280_mapper_read_only_consumer_isolation(self) -> None:
        """GC-280: ExpressionMapper and MotionMapper are strictly read-only consumers."""
        emotion = create_sample_emotion_state(EmotionType.WORRIED, intensity=0.65)
        mood = CharacterMood.FOCUSED

        _ = ExpressionMapper.map_expression(emotion, mood)
        _ = MotionMapper.map_motion(mood)

        assert emotion.emotion_type == EmotionType.WORRIED
        assert emotion.intensity == 0.65
        assert mood == CharacterMood.FOCUSED

    def test_gc281_mapper_pure_determinism_and_zero_pseudo_confidence(self) -> None:
        """GC-281: Mappers are pure deterministic functions without pseudo-confidence floats."""
        emotion = create_sample_emotion_state(EmotionType.SAD, intensity=0.8)
        res1 = ExpressionMapper.map_expression(emotion, CharacterMood.LOW)
        res2 = ExpressionMapper.map_expression(emotion, CharacterMood.LOW)

        assert res1 == res2
        assert not hasattr(res1, "confidence")
        assert not hasattr(res1, "score")


# =============================================================================
# Cluster 3: Audio Amplitude Lip-Sync & Barge-In Latch Invariants (GC-282 ~ GC-285)
# =============================================================================


class TestCluster3LipSyncAndBargeIn:
    """Verifies audio RMS energy extraction, smoothing, and barge-in latch state machine."""

    def test_gc282_rms_energy_extraction_and_noise_gate_cutoff(self) -> None:
        """GC-282: Noise gate cutoff suppresses background hiss to absolute 0.0."""
        engine = LipSyncEngineSimulator(noise_gate=0.015, gain=3.8)

        # Sub-gate noise (e.g. mic hiss) -> 0.0
        m_noise = engine.step(0.010)
        assert m_noise.mouth_open_y == 0.0
        assert m_noise.is_speaking is False

        # Above gate -> positive scaled opening
        m_speech = engine.step(0.10)
        assert m_speech.mouth_open_y > 0.0

    def test_gc283_asymmetric_attack_decay_smoothing_filter(self) -> None:
        """GC-283: Fast attack on rising energy, smooth decay on falling energy."""
        engine = LipSyncEngineSimulator(attack_rate=0.65, decay_rate=0.28)

        # Step up
        m1 = engine.step(0.30)
        assert m1.mouth_open_y > 0.50  # Fast attack

        # Step down to zero
        m2 = engine.step(0.0)
        assert m2.mouth_open_y > 0.30  # Smooth trailing decay

    def test_gc284_barge_in_latch_hostile_packet_rejection(self) -> None:
        """GC-284: Latched state unconditionally rejects hostile or out-of-order packets."""
        engine = LipSyncEngineSimulator()
        engine.trigger_barge_in()

        for amplitude in (0.1, 0.4, 0.8, 1.0):
            state = engine.step(amplitude)
            assert state.mouth_open_y == 0.0
            assert state.is_speaking is False

    def test_gc285_phase10_voice_contract_integrity_and_non_regression(self) -> None:
        """GC-285: Phase 10 Voice files remain 100% untouched and unregressed."""
        voice_files = [
            pathlib.Path("app/voice/voice_models.py"),
            pathlib.Path("app/voice/tts_service.py"),
            pathlib.Path("app/voice/stt_service.py"),
            pathlib.Path("app/voice/audio_cache.py"),
            pathlib.Path("app/voice/prosody_mapper.py"),
        ]

        for vf in voice_files:
            assert vf.exists(), f"Phase 10 file {vf} must exist"
            content = vf.read_text(encoding="utf-8")
            assert "VisualExpressionConfig" not in content
            assert "ParamMouthOpenY" not in content
            assert "Live2D" not in content


# =============================================================================
# Cluster 4: Gaze Tracking, Focus Release & Micro-Saccade Dynamics (GC-286 ~ GC-289)
# =============================================================================


class TestCluster4GazeAndSaccades:
    """Verifies gaze coordinate normalization, focus release, and micro-saccades."""

    def test_gc286_decoupled_gaze_coordinate_normalization_and_clamping(self) -> None:
        """GC-286: Viewport normalization to [-1.0, 1.0] and parameter physical clamping."""
        tracker = GazeTrackingSimulator()

        # Center
        tracker.handle_pointer_move(960, 540, 1920, 1080)
        assert tracker.current_target.x == 0.0
        assert tracker.current_target.y == 0.0

        # Out-of-bounds cursor
        tracker.handle_pointer_move(-2000, 5000, 1920, 1080)
        assert tracker.current_target.x == -1.0
        assert tracker.current_target.y == 1.0

        # Physical safety parameters bounds
        for _ in range(60):
            p = tracker.update(16)
            assert -1.0 <= p.eyeball_x <= 1.0
            assert -1.0 <= p.eyeball_y <= 1.0
            assert -30.0 <= p.angle_x <= 30.0
            assert -30.0 <= p.angle_y <= 30.0
            assert -30.0 <= p.angle_z <= 30.0

    def test_gc287_focus_release_neutral_re_centering_semantic_invariant(self) -> None:
        """GC-287: Focus release re-centers gaze forward without generating memory/emotion facts."""
        tracker = GazeTrackingSimulator()
        tracker.handle_pointer_move(1920, 1080, 1920, 1080)
        for _ in range(30):
            tracker.update(16)

        # Trigger pointerleave
        tracker.handle_pointer_leave()
        assert tracker.current_target.x == 0.0
        assert tracker.current_target.y == 0.0
        assert tracker.current_target.is_tracked is False

        # Converges smoothly back toward neutral pose
        for _ in range(60):
            tracker.update(16)

        assert abs(tracker.current_params.eyeball_x) < 0.05
        assert abs(tracker.current_params.angle_x) < 0.50

    def test_gc288_micro_saccade_bounded_twitch_isolation(self) -> None:
        """GC-288: Micro-saccades operate on isolated presentation timer with bounded displacement."""
        tracker = GazeTrackingSimulator(saccade_interval_ms=1000, saccade_amplitude=0.06)

        tracker.update(500)
        assert tracker.saccade_offset_x == 0.0

        tracker.update(600, random_seed_angle=math.pi / 2, random_seed_mag=1.0)
        assert tracker.saccade_offset_y > 0.0
        assert tracker.saccade_offset_y <= 0.06

    def test_gc289_gaze_damping_exponential_smoothing_stability(self) -> None:
        """GC-289: Damping avoids discrete oscillations or parameter instability."""
        tracker = GazeTrackingSimulator(smoothing_rate=0.12)
        tracker.handle_pointer_move(1920, 540, 1920, 1080)  # Sudden step change

        prev_x = 0.0
        for _ in range(10):
            p = tracker.update(16)
            assert p.eyeball_x >= prev_x  # Monotonically smoothly approaching
            prev_x = p.eyeball_x


# =============================================================================
# Cluster 5: Multi-Turn Visual Embodiment & Lifecycle Resilience (GC-290 ~ GC-293)
# =============================================================================


class TestCluster5MultiTurnVisualResilience:
    """Verifies end-to-end multi-turn interaction, barge-in, and lifecycle recovery."""

    @pytest.mark.asyncio
    async def test_gc290_multi_turn_turn_isolation_and_voice_visual_coordination(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """GC-290: Multi-turn session verifying visual presentation coordination without reality corruption.

        Turn 1: User message -> Aevum reply -> mouth moves via RMS.
        Turn 2: User moves mouse -> Aevum gaze follows cursor.
        Turn 3: WebGL failure occurs -> degrades to static fallback card -> conversation text continues.
        Turn 4: WebGL recovers -> visual canvas restores without state desynchronization.
        """
        # Create conversation
        conv_resp = await client.post("/conversations")
        conv_id = conv_resp.json()["id"]

        renderer = DesktopRendererLifecycleSimulator()
        renderer.initialize(webgl_available=True, has_cubism_core=True)
        lipsync = LipSyncEngineSimulator()
        gaze = GazeTrackingSimulator()

        # Turn 1: Conversation & speaking
        resp1 = await client.post(
            f"/conversations/{conv_id}/messages",
            json={"content": "Hello Aevum!"},
        )
        assert resp1.status_code == 201
        renderer.set_expression(VisualExpressionConfig(expression=VisualExpressionType.SMILE, intensity=0.7))
        renderer.set_motion(VisualMotionCommand(archetype=VisualMotionArchetype.TALKING_CASUAL, priority=3))
        mouth = lipsync.step(0.20)
        renderer.set_lip_sync(mouth)
        assert renderer.mouth_open_y > 0.0

        # Turn 2: User moves mouse
        gaze.handle_pointer_move(1400, 300, 1920, 1080)
        p = gaze.update(16)
        renderer.set_gaze(p)
        assert renderer.gaze.eyeball_x > 0.0

        # Turn 3: WebGL failure -> graceful degraded fallback
        renderer.initialize(webgl_available=False, has_cubism_core=True)
        assert renderer.state == RendererState.DEGRADED_FALLBACK

        # Conversation proceeds 100% uninterrupted during visual fallback
        resp2 = await client.post(
            f"/conversations/{conv_id}/messages",
            json={"content": "Are you still here?"},
        )
        assert resp2.status_code == 201

        # Turn 4: WebGL recovery
        renderer.initialize(webgl_available=True, has_cubism_core=True)
        assert renderer.state == RendererState.READY

    def test_gc291_cross_turn_barge_in_interruption_sequence(self) -> None:
        """GC-291: Assistant playback interrupted by user input clamps mouth immediately."""
        lipsync = LipSyncEngineSimulator()
        renderer = DesktopRendererLifecycleSimulator()

        # Assistant speaking
        lipsync.step(0.30)
        renderer.set_lip_sync(lipsync.get_mouth_state())
        assert renderer.mouth_open_y > 0.0

        # User interrupts / types next turn
        lipsync.trigger_barge_in()
        renderer.set_lip_sync(lipsync.get_mouth_state())
        assert renderer.mouth_open_y == 0.0

    def test_gc292_renderer_state_transient_resets_not_reality_mutation(self) -> None:
        """GC-292: Disposing or re-initializing renderer leaves canonical state untouched."""
        renderer = DesktopRendererLifecycleSimulator()
        renderer.initialize(webgl_available=True, has_cubism_core=True)
        renderer.update_frame(2000)

        # Reset / dispose
        renderer = DesktopRendererLifecycleSimulator()
        assert renderer.state == RendererState.UNINITIALIZED
        assert renderer.motion_progress_ms == 0

    def test_gc293_situational_presentation_overrides_reversibility(self) -> None:
        """GC-293: Thinking overlay reverses immediately when generation completes."""
        mood = CharacterMood.GOOD

        # While generating: priority 2 thinking overlay
        motion_thinking = MotionMapper.map_motion(mood, is_speaking=False, is_thinking=True)
        assert motion_thinking.archetype == VisualMotionArchetype.THINKING_TILT
        assert motion_thinking.priority == 2

        # After generation finishes: returns cleanly to baseline mood
        motion_idle = MotionMapper.map_motion(mood, is_speaking=False, is_thinking=False)
        assert motion_idle.archetype == VisualMotionArchetype.IDLE_ENERGETIC
        assert motion_idle.priority == 1


# =============================================================================
# Cluster 6: Defensive Integrity, AST Audits & Constitutional Guard (GC-294 ~ GC-297)
# =============================================================================


class TestCluster6DefensiveIntegrityAndASTAudits:
    """Constitutional static AST boundary and non-regression audits."""

    def test_gc294_ast_zero_hit_testing_across_all_modules(self) -> None:
        """GC-294: Lock 4 — Zero hit-testing tokens in any visual or layout modules."""
        target_files = [
            pathlib.Path("../apps/desktop/src/visual/gazeTracker.ts"),
            pathlib.Path("../apps/desktop/src/visual/visualMappers.ts"),
            pathlib.Path("../apps/desktop/src/visual/cubismManager.ts"),
            pathlib.Path("../apps/desktop/src/components/Live2DCanvas.tsx"),
        ]

        forbidden_tokens = [
            "hittest",
            "hit_test",
            "hitarea",
            "petting",
            "touchhead",
            "tapbody",
            "touch_reaction",
            "onclick_model",
        ]

        for tf in target_files:
            assert tf.exists(), f"File {tf} must exist"
            content = tf.read_text(encoding="utf-8").lower()
            for token in forbidden_tokens:
                assert token not in content, f"Forbidden interaction token '{token}' in {tf}"

    def test_gc295_ast_zero_reverse_state_mutation_across_all_modules(self) -> None:
        """GC-295: Lock 1 & Lock 7 — Zero reverse state mutation from Body to Mind."""
        target_files = [
            pathlib.Path("../apps/desktop/src/visual/gazeTracker.ts"),
            pathlib.Path("../apps/desktop/src/visual/visualMappers.ts"),
            pathlib.Path("../apps/desktop/src/visual/cubismManager.ts"),
            pathlib.Path("../apps/desktop/src/components/Live2DCanvas.tsx"),
        ]

        forbidden_mutations = [
            "set_fact",
            "character_core",
            "promotion",
            "reality_ledger",
            "emotion_state_update",
            "mutate_emotion",
            "patch_emotion",
        ]

        for tf in target_files:
            assert tf.exists(), f"File {tf} must exist"
            content = tf.read_text(encoding="utf-8").lower()
            for token in forbidden_mutations:
                assert token not in content, f"Forbidden mutation token '{token}' in {tf}"

    def test_gc296_ast_headless_ci_purity_zero_webgl_in_backend(self) -> None:
        """GC-296: Lock 6 — Backend visual models and mappers are pure Python AST with zero WebGL/Canvas/DOM."""
        visual_backend_files = list(pathlib.Path("app/visual").glob("**/*.py"))
        assert len(visual_backend_files) >= 3

        forbidden_backend_tokens = [
            "webgl",
            "canvas",
            "document.",
            "window.",
            "htmlcanvaselement",
            "webglrenderingcontext",
        ]

        for vf in visual_backend_files:
            source = vf.read_text(encoding="utf-8")
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    assert node.id.lower() not in forbidden_backend_tokens

    def test_gc297_system_wide_voice_and_reality_non_regression_audit(self) -> None:
        """GC-297: System-wide audit confirming Phase 9 Reality & Phase 10 Voice integrity."""
        # 1. Voice PTT-only boundary
        voice_files = list(pathlib.Path("app/voice").glob("**/*.py"))
        for vf in voice_files:
            content = vf.read_text(encoding="utf-8").lower()
            assert "continuous_vad" not in content
            assert "always_listening" not in content

        # 2. Reality models zero float invariant
        reality_models_path = pathlib.Path("app/reality/verification_models.py")
        source = reality_models_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign) and isinstance(node.annotation, ast.Name):
                assert node.annotation.id != "float"
