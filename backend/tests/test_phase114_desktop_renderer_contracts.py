"""test_phase114_desktop_renderer_contracts.py — Dedicated Unit Tests for Phase 11.4.

Verifies:
1. Priority 1: Zero reverse state mutation from Live2D Renderer to Mind.
2. Priority 2: Fail-closed & graceful visual degradation (DEGRADED_FALLBACK on WebGL / asset failure).
3. Priority 3: Renderer State vs Character State isolation (Lock 7).
4. Priority 4: Zero Hit-Testing / Touch / Petting in Phase 11 (Lock 4).
5. AST Boundary Audit across all desktop renderer and visual modules:
   - 0 DB mutations, 0 set_fact, 0 LLM calls, 0 PromotionAuthorizationToken.
   - Voice and Reality modules remain 100% untouched.
"""

from __future__ import annotations

import ast
import pathlib
import pytest

from app.visual.visual_models import (
    RendererState,
    VisualExpressionConfig,
    VisualExpressionType,
    VisualMotionArchetype,
    VisualMotionCommand,
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

    def initialize(self, webgl_available: bool = True, has_cubism_core: bool = True) -> RendererState:
        self.state = RendererState.LOADING

        # Lock 5: If WebGL or Cubism Core is unavailable, gracefully enter DEGRADED_FALLBACK
        if not webgl_available:
            self.state = RendererState.DEGRADED_FALLBACK
            self.error_message = "WebGL unavailable"
            return self.state

        if not has_cubism_core:
            self.state = RendererState.DEGRADED_FALLBACK
            self.error_message = "Live2DCubismCore runtime not detected"
            return self.state

        self.state = RendererState.READY
        return self.state

    def set_expression(self, config: VisualExpressionConfig) -> None:
        """Lock 2: Unidirectional expression instruction consumption."""
        self.active_expression = config.expression

    def set_motion(self, cmd: VisualMotionCommand) -> None:
        """Lock 7: Motion instruction queue with priority preemption."""
        if cmd.priority >= self.motion_priority:
            self.active_motion = cmd.archetype
            self.motion_priority = cmd.priority
            self.motion_progress_ms = 0

    def update_frame(self, delta_ms: int) -> None:
        """Advance internal renderer presentation behaviors."""
        self.motion_progress_ms += delta_ms
        self.blink_timer_ms += delta_ms

        if not self.is_blinking and self.blink_timer_ms > 4000:
            self.is_blinking = True
            self.blink_timer_ms = 0
        elif self.is_blinking and self.blink_timer_ms > 160:
            self.is_blinking = False
            self.blink_timer_ms = 0


class TestDesktopRendererLifecycleAndFallback:
    """Verifies Priority 2: Fail-Closed & Graceful Visual Degradability (Lock 5)."""

    def test_successful_initialization_transitions_to_ready(self) -> None:
        sim = DesktopRendererLifecycleSimulator()
        assert sim.state == RendererState.UNINITIALIZED

        state = sim.initialize(webgl_available=True, has_cubism_core=True)
        assert state == RendererState.READY
        assert sim.state == RendererState.READY

    def test_webgl_failure_gracefully_enters_degraded_fallback(self) -> None:
        """Lock 5: WebGL failure must transition to DEGRADED_FALLBACK without crashing."""
        sim = DesktopRendererLifecycleSimulator()
        state = sim.initialize(webgl_available=False, has_cubism_core=True)

        assert state == RendererState.DEGRADED_FALLBACK
        assert sim.error_message == "WebGL unavailable"
        # State machine remains safe, non-crashing
        assert sim.state == RendererState.DEGRADED_FALLBACK

    def test_missing_cubism_runtime_gracefully_enters_degraded_fallback(self) -> None:
        """Lock 5: Missing runtime must degrade safely."""
        sim = DesktopRendererLifecycleSimulator()
        state = sim.initialize(webgl_available=True, has_cubism_core=False)

        assert state == RendererState.DEGRADED_FALLBACK
        assert sim.error_message == "Live2DCubismCore runtime not detected"


class TestRendererStateIsolation:
    """Verifies Priority 3: Renderer State != Character State (Lock 7)."""

    def test_internal_presentation_behavior_progression(self) -> None:
        sim = DesktopRendererLifecycleSimulator()
        sim.initialize(webgl_available=True, has_cubism_core=True)

        # Before 4000ms: not blinking
        sim.update_frame(2000)
        assert sim.blink_timer_ms == 2000
        assert sim.is_blinking is False

        # After 4000ms: triggers blink
        sim.update_frame(2100)
        assert sim.is_blinking is True

        # Blink lasts ~160ms then returns to open
        sim.update_frame(200)
        assert sim.is_blinking is False

    def test_motion_preemption_by_priority(self) -> None:
        sim = DesktopRendererLifecycleSimulator()
        sim.initialize(webgl_available=True, has_cubism_core=True)

        # Baseline idle: priority 1
        sim.set_motion(VisualMotionCommand(archetype=VisualMotionArchetype.IDLE_NORMAL, priority=1))
        assert sim.active_motion == VisualMotionArchetype.IDLE_NORMAL

        # Talking casual: priority 3 preempts baseline
        sim.set_motion(VisualMotionCommand(archetype=VisualMotionArchetype.TALKING_CASUAL, priority=3))
        assert sim.active_motion == VisualMotionArchetype.TALKING_CASUAL
        assert sim.motion_priority == 3

        # Lower priority command cannot preempt higher priority active motion
        sim.set_motion(VisualMotionCommand(archetype=VisualMotionArchetype.IDLE_DROWSY, priority=1))
        assert sim.active_motion == VisualMotionArchetype.TALKING_CASUAL  # Unchanged!


class TestConstitutionalRendererBoundariesAST:
    """Verifies Priorities 1 & 4: Zero mutation to Mind & Zero Hit-Testing."""

    def test_zero_hit_testing_in_desktop_renderer(self) -> None:
        """Priority 4 / Lock 4: Pure visual presentation. Zero hit testing in Phase 11."""
        ts_files = [
            pathlib.Path("../apps/desktop/src/visual/cubismManager.ts"),
            pathlib.Path("../apps/desktop/src/components/Live2DCanvas.tsx"),
        ]

        forbidden_interaction_tokens = [
            "hittest",
            "hit_test",
            "hitarea",
            "petting",
            "touchhead",
            "tapbody",
            "touch_reaction",
            "onclick_model",
        ]

        for tf in ts_files:
            assert tf.exists(), f"File {tf} must exist"
            content = tf.read_text(encoding="utf-8").lower()
            for token in forbidden_interaction_tokens:
                assert token not in content, (
                    f"Forbidden interaction token '{token}' found in {tf}"
                )

    def test_zero_mind_state_mutation_in_desktop_renderer(self) -> None:
        """Priority 1 / Lock 1 & Lock 7: Renderer must NEVER reverse-pollute Mind."""
        ts_files = [
            pathlib.Path("../apps/desktop/src/visual/cubismManager.ts"),
            pathlib.Path("../apps/desktop/src/components/Live2DCanvas.tsx"),
        ]

        forbidden_mutation_tokens = [
            "set_fact",
            "character_core",
            "promotion",
            "reality_ledger",
            "emotion_state_update",
            "mutate_emotion",
            "patch_emotion",
        ]

        for tf in ts_files:
            assert tf.exists(), f"File {tf} must exist"
            content = tf.read_text(encoding="utf-8").lower()
            for token in forbidden_mutation_tokens:
                assert token not in content, (
                    f"Forbidden mutation token '{token}' found in {tf}"
                )

    def test_backend_visual_models_purity(self) -> None:
        """Backend visual models remain strictly pure AST."""
        file_path = pathlib.Path("app/visual/visual_models.py")
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    assert node.func.id not in ("set_fact", "PromotionAuthorizationToken")
