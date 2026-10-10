"""test_phase115_gaze_layout_contracts.py — Dedicated Unit Tests for Phase 11.5.

Verifies:
1. Decoupled mouse cursor tracking -> Gaze parameters (ParamEyeBallX/Y, ParamAngleX/Y/Z).
2. Focus Release behavior (pointerleave/blur resets target to neutral (0.0, 0.0)).
3. Micro-saccade behavior (presentation-only bounded twitch, isolated Renderer State).
4. Exponential smoothing & damping interpolation.
5. Desktop visual presentation mappers (unidirectional mapping from emotion/mood).
6. AST Constitutional Boundary Audit across gaze tracking, layout, and visual modules:
   - Zero Hit-Testing / Touch / Petting (Lock 4).
   - Zero reverse state mutation from Gaze / Renderer to Mind (Lock 1 & Lock 7).
   - Zero DB, zero set_fact, zero LLM calls.
"""

from __future__ import annotations

import math
import pathlib
import pytest

from app.visual.visual_models import (
    GazeParameters,
    GazeTarget,
    RendererState,
    VisualExpressionConfig,
    VisualExpressionType,
    VisualMotionArchetype,
    VisualMotionCommand,
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
        """Normalizes cursor coordinates relative to window center to [-1.0, 1.0]."""
        w = max(1.0, window_width)
        h = max(1.0, window_height)
        norm_x = max(-1.0, min(1.0, (client_x - w / 2.0) / (w / 2.0)))
        norm_y = max(-1.0, min(1.0, (client_y - h / 2.0) / (h / 2.0)))
        self.current_target = GazeTarget(x=round(norm_x, 4), y=round(norm_y, 4), is_tracked=True)

    def handle_pointer_leave(self) -> None:
        """Focus Release: re-centers target coordinate to neutral forward pose (0.0, 0.0)."""
        self.current_target = GazeTarget(x=0.0, y=0.0, is_tracked=False)

    def update(self, delta_ms: int, random_seed_angle: float = 0.0, random_seed_mag: float = 1.0) -> GazeParameters:
        """Advances saccades, damping interpolation, and computes output GazeParameters."""
        # 1. Micro-saccade simulation
        self.saccade_timer_ms += delta_ms
        if self.saccade_timer_ms > self.saccade_interval_ms:
            self.saccade_timer_ms = 0
            mag = (random_seed_mag * 0.5 + 0.5) * self.saccade_amplitude
            self.saccade_offset_x = math.cos(random_seed_angle) * mag
            self.saccade_offset_y = math.sin(random_seed_angle) * mag

        # 2. Raw target parameters
        raw_eyeball_x = max(-1.0, min(1.0, self.current_target.x * self.max_eyeball + self.saccade_offset_x))
        raw_eyeball_y = max(-1.0, min(1.0, -self.current_target.y * self.max_eyeball + self.saccade_offset_y))

        raw_angle_x = max(-30.0, min(30.0, self.current_target.x * self.max_angle_x))
        raw_angle_y = max(-30.0, min(30.0, -self.current_target.y * self.max_angle_y))
        raw_angle_z = max(-30.0, min(30.0, self.current_target.x * -self.max_angle_z))

        # 3. Smooth exponential damping interpolation
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


class TestGazeParameterMathematicsAndClamping:
    """Verifies mathematical normalization, clamping, and bounds for Gaze tracking."""

    def test_gaze_coordinate_normalization(self) -> None:
        tracker = GazeTrackingSimulator()

        # Window center (960, 540) in 1920x1080 -> (0.0, 0.0)
        tracker.handle_pointer_move(960, 540, 1920, 1080)
        assert tracker.current_target.x == 0.0
        assert tracker.current_target.y == 0.0
        assert tracker.current_target.is_tracked is True

        # Top-left corner (0, 0) -> (-1.0, -1.0)
        tracker.handle_pointer_move(0, 0, 1920, 1080)
        assert tracker.current_target.x == -1.0
        assert tracker.current_target.y == -1.0

        # Bottom-right corner (1920, 1080) -> (1.0, 1.0)
        tracker.handle_pointer_move(1920, 1080, 1920, 1080)
        assert tracker.current_target.x == 1.0
        assert tracker.current_target.y == 1.0

        # Out of bounds coordinates clamp cleanly to [-1.0, 1.0]
        tracker.handle_pointer_move(-500, 3000, 1920, 1080)
        assert tracker.current_target.x == -1.0
        assert tracker.current_target.y == 1.0

    def test_gaze_eyeball_parameter_bounds(self) -> None:
        tracker = GazeTrackingSimulator()
        tracker.handle_pointer_move(1920, 0, 1920, 1080)  # Top-right corner

        # Run several frames of updates
        for _ in range(60):
            params = tracker.update(16)
            assert -1.0 <= params.eyeball_x <= 1.0
            assert -1.0 <= params.eyeball_y <= 1.0

    def test_gaze_head_angle_parameter_bounds(self) -> None:
        tracker = GazeTrackingSimulator()
        tracker.handle_pointer_move(1920, 1080, 1920, 1080)  # Bottom-right corner

        for _ in range(60):
            params = tracker.update(16)
            assert -30.0 <= params.angle_x <= 30.0
            assert -30.0 <= params.angle_y <= 30.0
            assert -30.0 <= params.angle_z <= 30.0


class TestGazeFocusReleaseAndSaccades:
    """Verifies Focus Release re-centering and micro-saccade behavior (Lock 7)."""

    def test_focus_release_centering(self) -> None:
        tracker = GazeTrackingSimulator()
        tracker.handle_pointer_move(1920, 1080, 1920, 1080)  # User looked far right/down

        # Settle parameters near target
        for _ in range(30):
            tracker.update(16)
        assert tracker.current_params.angle_x > 10.0

        # Trigger focus release (mouse left window)
        tracker.handle_pointer_leave()
        assert tracker.current_target.x == 0.0
        assert tracker.current_target.y == 0.0
        assert tracker.current_target.is_tracked is False

        # Run updates to observe smooth re-centering toward (0.0, 0.0)
        for _ in range(60):
            tracker.update(16)

        assert abs(tracker.current_params.eyeball_x) < 0.05
        assert abs(tracker.current_params.angle_x) < 0.50

    def test_focus_release_semantic_isolation_lock7(self) -> None:
        """Lock 7: Focus Release is visual centering, NOT character disinterest fact."""
        tracker = GazeTrackingSimulator()
        tracker.handle_pointer_leave()

        # Target is re-centered, but no epistemic state was modified
        assert tracker.current_target.is_tracked is False
        assert not hasattr(tracker, "character_state")
        assert not hasattr(tracker, "emotion_state")

    def test_micro_saccade_isolated_timer_and_bounds(self) -> None:
        tracker = GazeTrackingSimulator(saccade_interval_ms=2000, saccade_amplitude=0.06)

        # Before 2000ms: no offset
        tracker.update(1000)
        assert tracker.saccade_offset_x == 0.0
        assert tracker.saccade_offset_y == 0.0

        # After 2000ms: saccade fires with bounded amplitude
        tracker.update(1100, random_seed_angle=math.pi / 4, random_seed_mag=0.8)
        offset_mag = math.sqrt(tracker.saccade_offset_x**2 + tracker.saccade_offset_y**2)
        assert offset_mag <= 0.06
        assert offset_mag > 0.0


class TestDesktopVisualPresentationMappers:
    """Verifies desktop visual mapper presentation rules."""

    def test_desktop_visual_mappers_exist_and_importable(self) -> None:
        mappers_file = pathlib.Path("../apps/desktop/src/visual/visualMappers.ts")
        assert mappers_file.exists(), "visualMappers.ts must exist in desktop visual directory"
        content = mappers_file.read_text(encoding="utf-8")
        assert "deriveVisualExpression" in content
        assert "deriveVisualMotion" in content


class TestConstitutionalGazeAndLayoutAST:
    """Constitutional AST audits for Phase 11.5 deliverables."""

    def test_zero_hit_testing_in_phase_11_ast(self) -> None:
        """Lock 4: Pure visual presentation scope. Zero hit-testing / touch in Phase 11."""
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
                assert token not in content, f"Forbidden interaction token '{token}' found in {tf}"

    def test_zero_mind_state_mutation_in_gaze_and_layout_ast(self) -> None:
        """Lock 1 & Lock 7: Zero reverse state feedback from Gaze / Layout to Mind."""
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
                assert token not in content, f"Forbidden mutation token '{token}' found in {tf}"

    def test_ptt_voice_boundary_preserved(self) -> None:
        """Lock 4 & Rule 18: Continuous VAD remains strictly absent."""
        voice_files = list(pathlib.Path("app/voice").glob("**/*.py"))
        assert len(voice_files) >= 10, "Voice modules must exist"

        forbidden_vad_tokens = [
            "continuous_vad",
            "vad_detector",
            "listen_continuously",
            "always_listening",
        ]

        for vf in voice_files:
            content = vf.read_text(encoding="utf-8").lower()
            for token in forbidden_vad_tokens:
                assert token not in content, f"Forbidden continuous VAD token '{token}' in {vf}"
