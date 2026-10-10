"""test_phase111_visual_contracts.py — Dedicated Unit Tests for Phase 11.1 Visual Contracts.

Verifies:
1. Immutability, frozen status, and extra='forbid' across all Visual models.
2. Canonical enums: VisualSubsystemType, VisualExpressionType, VisualMotionArchetype, RendererState.
3. Render Instructions: VisualExpressionConfig & VisualMotionCommand semantics.
4. Gaze Target & Gaze Parameters coordinate boundaries.
5. LipSync Mouth State (ParamMouthOpenY bounded, ParamMouthForm baseline).
6. RendererPresentationConfig presentation behavior boundaries.
7. Live2D Model Manifest and Parameter Mapping structures.
8. Pure static AST constitutional boundary audit (zero WebGL, zero DB, zero set_fact, zero pseudo-confidence).
"""

from __future__ import annotations

import ast
import pathlib
import pytest
from pydantic import ValidationError

from app.visual.visual_models import (
    GazeParameters,
    GazeTarget,
    LipSyncMouthState,
    Live2DModelManifest,
    Live2DParameterMapping,
    RendererPresentationConfig,
    RendererState,
    VisualExpressionConfig,
    VisualExpressionType,
    VisualMotionArchetype,
    VisualMotionCommand,
    VisualSubsystemType,
)


class TestVisualEnums:
    """Verifies all Phase 11 visual categorical enums."""

    def test_visual_subsystem_type_members(self) -> None:
        """Verifies the 4 decoupled visual subsystems per ADR-022."""
        subsystems = {s.value for s in VisualSubsystemType}
        assert subsystems == {"EXPRESSION", "MOTION", "GAZE", "LIPSYNC"}
        assert len(VisualSubsystemType) == 4

    def test_visual_expression_type_members(self) -> None:
        """Verifies the 10 canonical expression archetypes."""
        expected = {
            "neutral", "joy", "smile", "sad", "pout",
            "surprise", "thinking", "blush", "worried", "tired",
        }
        actual = {e.value for e in VisualExpressionType}
        assert actual == expected

    def test_visual_motion_archetype_members(self) -> None:
        """Verifies the 7 canonical motion presets."""
        expected = {
            "idle_normal", "idle_drowsy", "idle_energetic",
            "talking_casual", "thinking_tilt", "nod", "shake_head",
        }
        actual = {m.value for m in VisualMotionArchetype}
        assert actual == expected

    def test_renderer_state_members(self) -> None:
        """Verifies the 5 renderer lifecycle operational states."""
        expected = {"uninitialized", "loading", "ready", "degraded_fallback", "error"}
        actual = {r.value for r in RendererState}
        assert actual == expected


class TestVisualExpressionConfig:
    """Verifies VisualExpressionConfig render instruction boundaries."""

    def test_default_instantiation(self) -> None:
        config = VisualExpressionConfig()
        assert config.expression == VisualExpressionType.NEUTRAL
        assert config.intensity == 1.0
        assert config.parameter_overrides == {}
        assert config.transition_duration_ms == 300

    def test_custom_instantiation(self) -> None:
        config = VisualExpressionConfig(
            expression=VisualExpressionType.JOY,
            intensity=0.85,
            parameter_overrides={"ParamCheek": 0.8, "ParamEyeLSmile": 1.0},
            transition_duration_ms=450,
        )
        assert config.expression == VisualExpressionType.JOY
        assert config.intensity == 0.85
        assert config.parameter_overrides["ParamCheek"] == 0.8
        assert config.transition_duration_ms == 450

    def test_frozen_immutability(self) -> None:
        config = VisualExpressionConfig()
        with pytest.raises(ValidationError):
            config.intensity = 0.5  # type: ignore[misc]

    def test_extra_forbid(self) -> None:
        with pytest.raises(ValidationError):
            VisualExpressionConfig(unknown_field="injected")  # type: ignore[call-arg]

    def test_intensity_bounds(self) -> None:
        with pytest.raises(ValidationError):
            VisualExpressionConfig(intensity=-0.1)
        with pytest.raises(ValidationError):
            VisualExpressionConfig(intensity=1.01)

    def test_duration_bounds(self) -> None:
        with pytest.raises(ValidationError):
            VisualExpressionConfig(transition_duration_ms=-1)
        with pytest.raises(ValidationError):
            VisualExpressionConfig(transition_duration_ms=5001)

    def test_parameter_overrides_validation(self) -> None:
        # Valid overrides
        config = VisualExpressionConfig(parameter_overrides={"ParamAngleX": 15.0})
        assert config.parameter_overrides["ParamAngleX"] == 15.0

        # Out-of-bounds parameter value
        with pytest.raises(ValidationError):
            VisualExpressionConfig(parameter_overrides={"ParamAngleX": 35.0})

        # Empty string parameter name
        with pytest.raises(ValidationError):
            VisualExpressionConfig(parameter_overrides={"": 1.0})


class TestVisualMotionCommand:
    """Verifies VisualMotionCommand render instruction boundaries."""

    def test_default_instantiation(self) -> None:
        cmd = VisualMotionCommand()
        assert cmd.archetype == VisualMotionArchetype.IDLE_NORMAL
        assert cmd.priority == 1
        assert cmd.loop is True
        assert cmd.fade_in_ms == 500
        assert cmd.fade_out_ms == 500

    def test_custom_instantiation(self) -> None:
        cmd = VisualMotionCommand(
            archetype=VisualMotionArchetype.NOD,
            priority=5,
            loop=False,
            fade_in_ms=200,
            fade_out_ms=300,
        )
        assert cmd.archetype == VisualMotionArchetype.NOD
        assert cmd.priority == 5
        assert cmd.loop is False
        assert cmd.fade_in_ms == 200
        assert cmd.fade_out_ms == 300

    def test_frozen_immutability(self) -> None:
        cmd = VisualMotionCommand()
        with pytest.raises(ValidationError):
            cmd.priority = 2  # type: ignore[misc]

    def test_extra_forbid(self) -> None:
        with pytest.raises(ValidationError):
            VisualMotionCommand(unsupported_flag=True)  # type: ignore[call-arg]

    def test_priority_bounds(self) -> None:
        with pytest.raises(ValidationError):
            VisualMotionCommand(priority=-1)
        with pytest.raises(ValidationError):
            VisualMotionCommand(priority=11)

    def test_fade_duration_bounds(self) -> None:
        with pytest.raises(ValidationError):
            VisualMotionCommand(fade_in_ms=-1)
        with pytest.raises(ValidationError):
            VisualMotionCommand(fade_out_ms=5001)


class TestGazeModels:
    """Verifies GazeTarget and GazeParameters coordinate boundaries."""

    def test_gaze_target_valid_and_clamped(self) -> None:
        target = GazeTarget(x=0.5, y=-0.5, is_tracked=True)
        assert target.x == 0.5
        assert target.y == -0.5
        assert target.is_tracked is True

    def test_gaze_target_out_of_bounds(self) -> None:
        with pytest.raises(ValidationError):
            GazeTarget(x=1.1, y=0.0)
        with pytest.raises(ValidationError):
            GazeTarget(x=0.0, y=-1.1)

    def test_gaze_target_frozen_and_extra_forbid(self) -> None:
        target = GazeTarget(x=0.0, y=0.0)
        with pytest.raises(ValidationError):
            target.x = 0.5  # type: ignore[misc]
        with pytest.raises(ValidationError):
            GazeTarget(x=0.0, y=0.0, extra="prohibited")  # type: ignore[call-arg]

    def test_gaze_parameters_valid(self) -> None:
        params = GazeParameters(
            eyeball_x=0.2,
            eyeball_y=-0.1,
            angle_x=12.5,
            angle_y=-8.0,
            angle_z=3.0,
        )
        assert params.eyeball_x == 0.2
        assert params.angle_x == 12.5

    def test_gaze_parameters_out_of_bounds(self) -> None:
        with pytest.raises(ValidationError):
            GazeParameters(eyeball_x=1.05)
        with pytest.raises(ValidationError):
            GazeParameters(angle_x=31.0)
        with pytest.raises(ValidationError):
            GazeParameters(angle_z=-30.5)


class TestLipSyncMouthState:
    """Verifies LipSyncMouthState boundaries per ADR-022 Lock 3."""

    def test_default_resting_state(self) -> None:
        mouth = LipSyncMouthState()
        assert mouth.mouth_open_y == 0.0
        assert mouth.mouth_form == 0.0
        assert mouth.is_speaking is False

    def test_active_speech_state(self) -> None:
        mouth = LipSyncMouthState(mouth_open_y=0.75, mouth_form=0.0, is_speaking=True)
        assert mouth.mouth_open_y == 0.75
        assert mouth.mouth_form == 0.0
        assert mouth.is_speaking is True

    def test_mouth_open_y_bounds(self) -> None:
        with pytest.raises(ValidationError):
            LipSyncMouthState(mouth_open_y=-0.05)
        with pytest.raises(ValidationError):
            LipSyncMouthState(mouth_open_y=1.05)

    def test_mouth_form_bounds(self) -> None:
        with pytest.raises(ValidationError):
            LipSyncMouthState(mouth_form=-1.05)
        with pytest.raises(ValidationError):
            LipSyncMouthState(mouth_form=1.05)

    def test_frozen_and_extra_forbid(self) -> None:
        mouth = LipSyncMouthState()
        with pytest.raises(ValidationError):
            mouth.mouth_open_y = 0.5  # type: ignore[misc]
        with pytest.raises(ValidationError):
            LipSyncMouthState(viseme_type="AIUEO")  # type: ignore[call-arg]


class TestRendererPresentationConfig:
    """Verifies RendererPresentationConfig per ADR-022 Lock 7."""

    def test_default_presentation_config(self) -> None:
        config = RendererPresentationConfig()
        assert config.blink_interval_mean_ms == 4000
        assert config.blink_duration_ms == 150
        assert config.saccade_enabled is True
        assert config.saccade_interval_mean_ms == 2500
        assert config.breath_cycle_ms == 6000

    def test_presentation_bounds(self) -> None:
        with pytest.raises(ValidationError):
            RendererPresentationConfig(blink_interval_mean_ms=500)  # min 1000
        with pytest.raises(ValidationError):
            RendererPresentationConfig(blink_duration_ms=40)  # min 50
        with pytest.raises(ValidationError):
            RendererPresentationConfig(breath_cycle_ms=15000)  # max 12000

    def test_frozen_and_extra_forbid(self) -> None:
        config = RendererPresentationConfig()
        with pytest.raises(ValidationError):
            config.saccade_enabled = False  # type: ignore[misc]
        with pytest.raises(ValidationError):
            RendererPresentationConfig(emotion_feedback=True)  # type: ignore[call-arg]


class TestLive2DManifestAndParameters:
    """Verifies manifest and parameter mapping models."""

    def test_parameter_mapping(self) -> None:
        param = Live2DParameterMapping(
            parameter_id="ParamMouthOpenY",
            default_value=0.0,
            min_value=0.0,
            max_value=1.0,
            description="Controls vertical mouth opening.",
        )
        assert param.parameter_id == "ParamMouthOpenY"
        assert param.min_value == 0.0
        assert param.max_value == 1.0

    def test_model_manifest(self) -> None:
        manifest = Live2DModelManifest(
            model_id="aevum_hina_v1",
            name="Aevum Hina Baseline",
            version="1.0.0",
            model_path="models/hina/hina.model3.json",
            texture_paths=["models/hina/textures/texture_00.png"],
            motion_groups={"Idle": ["motions/idle_01.motion3.json"]},
            expression_map={"joy": "expressions/joy.exp3.json"},
            supported_parameters=[
                Live2DParameterMapping(parameter_id="ParamEyeBallX")
            ],
        )
        assert manifest.model_id == "aevum_hina_v1"
        assert len(manifest.texture_paths) == 1
        assert manifest.motion_groups["Idle"] == ["motions/idle_01.motion3.json"]


class TestConstitutionalVisualBoundariesAST:
    """Pure static AST inspection ensuring zero constitutional boundary violations in Phase 11.1."""

    def test_zero_webgl_canvas_dom_in_backend_models(self) -> None:
        """Lock 6: Backend visual contracts must never import WebGL, Canvas, or DOM."""
        file_path = pathlib.Path("app/visual/visual_models.py")
        assert file_path.exists(), f"File {file_path} not found"
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        forbidden_modules = {
            "webgl", "canvas", "document", "window", "pygame", "pyglet",
            "PIL", "cv2", "sqlite3", "sqlalchemy", "httpx", "aiohttp",
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_pkg = alias.name.split(".")[0]
                    assert root_pkg not in forbidden_modules, (
                        f"Forbidden import '{alias.name}' found in {file_path}"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root_pkg = node.module.split(".")[0]
                    assert root_pkg not in forbidden_modules, (
                        f"Forbidden import from '{node.module}' found in {file_path}"
                    )

    def test_zero_set_fact_or_promotion_authority(self) -> None:
        """Lock 1: Visual contracts have strictly 0 set_fact or promotion authority."""
        file_path = pathlib.Path("app/visual/visual_models.py")
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    assert node.func.id not in ("set_fact", "PromotionAuthorizationToken"), (
                        f"Forbidden call to '{node.func.id}' in {file_path}"
                    )
                elif isinstance(node.func, ast.Attribute):
                    assert node.func.attr not in ("set_fact", "PromotionAuthorizationToken"), (
                        f"Forbidden call to '{node.func.attr}' in {file_path}"
                    )

    def test_zero_pseudo_confidence_floats(self) -> None:
        """Lock 6 & ADR-022: Strict rejection of pseudo-confidence float attributes."""
        file_path = pathlib.Path("app/visual/visual_models.py")
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                        assert item.target.id != "confidence", (
                            f"Illegal field 'confidence' found on class '{node.name}' in {file_path}"
                        )
