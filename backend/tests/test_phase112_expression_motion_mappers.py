"""test_phase112_expression_motion_mappers.py — Dedicated Unit Tests for Phase 11.2.

Verifies:
1. ExpressionMapper covers all 17 canonical EmotionTypes.
2. Intensity scaling is deterministic and bounded.
3. Baseline mood bias modulation without mutating EmotionState.
4. MotionMapper covers all 7 canonical CharacterMoods.
5. Situational motion overlays (speaking, thinking) with strict priority ordering.
6. Pure read-only consumer isolation: zero mutation of EmotionState or CharacterMood.
7. Pure static AST constitutional boundary audit across both mapper modules
   (0 DB, 0 network, 0 LLM, 0 set_fact, 0 WebGL).
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import pathlib
import pytest

from app.character.state_models import CharacterMood
from app.emotion.emotion_models import EmotionState, EmotionType
from app.visual.expression_mapper import ExpressionMapper
from app.visual.motion_mapper import MotionMapper
from app.visual.visual_models import (
    VisualExpressionConfig,
    VisualExpressionType,
    VisualMotionArchetype,
    VisualMotionCommand,
)


def _create_mock_emotion_state(
    emotion_type: EmotionType = EmotionType.NEUTRAL,
    intensity: float = 0.5,
) -> EmotionState:
    """Helper to instantiate a valid, frozen EmotionState for testing."""
    now = datetime.now(timezone.utc)
    return EmotionState(
        id="test-emotion-id-123",
        character_id="aevum",
        emotion_type=emotion_type,
        intensity=intensity,
        created_at=now,
        updated_at=now,
        version=1,
    )


class TestExpressionMapper:
    """Verifies ExpressionMapper deterministic presentation policy per ADR-022."""

    def test_all_17_emotion_types_covered(self) -> None:
        """Requirement: ExpressionMapper must cover all 17 canonical EmotionTypes."""
        assert len(EmotionType) == 17, "EmotionType enum must have exactly 17 canonical values."

        for emotion_type in EmotionType:
            config = ExpressionMapper.from_types(emotion_type=emotion_type, intensity=0.8)
            assert isinstance(config, VisualExpressionConfig)
            assert isinstance(config.expression, VisualExpressionType)
            assert 0.0 <= config.intensity <= 1.0
            assert 0 <= config.transition_duration_ms <= 5000

    def test_intensity_deterministic_scaling(self) -> None:
        """Requirement: Intensity deterministically modulates expression and parameters."""
        # Low-intensity HAPPY presents as gentle SMILE
        config_low = ExpressionMapper.from_types(emotion_type=EmotionType.HAPPY, intensity=0.3)
        assert config_low.expression == VisualExpressionType.SMILE
        assert config_low.intensity == 0.3

        # High-intensity HAPPY presents as full JOY
        config_high = ExpressionMapper.from_types(emotion_type=EmotionType.HAPPY, intensity=0.9)
        assert config_high.expression == VisualExpressionType.JOY
        assert config_high.intensity == 0.9

        # EXCITED parameter overrides scale with intensity
        config_excited_low = ExpressionMapper.from_types(emotion_type=EmotionType.EXCITED, intensity=0.2)
        config_excited_high = ExpressionMapper.from_types(emotion_type=EmotionType.EXCITED, intensity=1.0)
        assert config_excited_low.parameter_overrides["ParamCheek"] < config_excited_high.parameter_overrides["ParamCheek"]

    def test_mood_bias_presentation(self) -> None:
        """Requirement: Baseline CharacterMood biases presentation when emotion is neutral."""
        # NEUTRAL emotion with TIRED mood -> TIRED expression
        config_tired = ExpressionMapper.from_types(
            emotion_type=EmotionType.NEUTRAL,
            intensity=0.5,
            mood=CharacterMood.TIRED,
        )
        assert config_tired.expression == VisualExpressionType.TIRED

        # NEUTRAL emotion with GOOD mood -> SMILE expression
        config_good = ExpressionMapper.from_types(
            emotion_type=EmotionType.NEUTRAL,
            intensity=0.5,
            mood=CharacterMood.GOOD,
        )
        assert config_good.expression == VisualExpressionType.SMILE

        # NEUTRAL emotion with LOW mood -> SAD expression
        config_low = ExpressionMapper.from_types(
            emotion_type=EmotionType.NEUTRAL,
            intensity=0.5,
            mood=CharacterMood.LOW,
        )
        assert config_low.expression == VisualExpressionType.SAD

        # Distinct active emotion overrides baseline mood bias (e.g. HAPPY still yields JOY even if mood is TIRED)
        config_happy_tired = ExpressionMapper.from_types(
            emotion_type=EmotionType.HAPPY,
            intensity=0.9,
            mood=CharacterMood.TIRED,
        )
        assert config_happy_tired.expression == VisualExpressionType.JOY

    def test_mood_does_not_mutate_emotion_state(self) -> None:
        """Lock 2: Mapping must strictly never mutate the passed EmotionState."""
        original_emotion = _create_mock_emotion_state(
            emotion_type=EmotionType.CONTENT,
            intensity=0.75,
        )

        # Map multiple times with different moods
        _ = ExpressionMapper.map_expression(original_emotion, mood=CharacterMood.TIRED)
        _ = ExpressionMapper.map_expression(original_emotion, mood=CharacterMood.IRRITATED)

        # Assert all fields remain exactly as initialized
        assert original_emotion.emotion_type == EmotionType.CONTENT
        assert original_emotion.intensity == 0.75
        assert original_emotion.id == "test-emotion-id-123"
        assert original_emotion.version == 1

    def test_intensity_clamping_safeguards(self) -> None:
        """Verify out-of-bounds intensity values are clamped gracefully to [0.0, 1.0]."""
        config_under = ExpressionMapper.from_types(emotion_type=EmotionType.CALM, intensity=-0.5)
        assert config_under.intensity == 0.0

        config_over = ExpressionMapper.from_types(emotion_type=EmotionType.CALM, intensity=1.5)
        assert config_over.intensity == 1.0

    def test_pure_determinism(self) -> None:
        """Verify re-running map_expression with identical inputs produces identical outputs."""
        emotion = _create_mock_emotion_state(emotion_type=EmotionType.AMUSED, intensity=0.6)
        res1 = ExpressionMapper.map_expression(emotion, mood=CharacterMood.GOOD)
        res2 = ExpressionMapper.map_expression(emotion, mood=CharacterMood.GOOD)
        assert res1 == res2


class TestMotionMapper:
    """Verifies MotionMapper deterministic presentation policy per ADR-022."""

    def test_all_7_character_moods_covered(self) -> None:
        """Requirement: MotionMapper must cover all 7 canonical CharacterMoods."""
        assert len(CharacterMood) == 7, "CharacterMood enum must have exactly 7 canonical values."

        for mood in CharacterMood:
            cmd = MotionMapper.from_mood(mood)
            assert isinstance(cmd, VisualMotionCommand)
            assert isinstance(cmd.archetype, VisualMotionArchetype)
            assert 0 <= cmd.priority <= 10
            assert 0 <= cmd.fade_in_ms <= 5000
            assert 0 <= cmd.fade_out_ms <= 5000

    def test_deterministic_idle_motion_selection(self) -> None:
        """Requirement: Distinct moods produce deterministic, appropriate motion archetypes."""
        assert MotionMapper.from_mood(CharacterMood.NEUTRAL).archetype == VisualMotionArchetype.IDLE_NORMAL
        assert MotionMapper.from_mood(CharacterMood.GOOD).archetype == VisualMotionArchetype.IDLE_ENERGETIC
        assert MotionMapper.from_mood(CharacterMood.TIRED).archetype == VisualMotionArchetype.IDLE_DROWSY
        assert MotionMapper.from_mood(CharacterMood.LOW).archetype == VisualMotionArchetype.IDLE_DROWSY
        assert MotionMapper.from_mood(CharacterMood.FOCUSED).archetype == VisualMotionArchetype.THINKING_TILT
        assert MotionMapper.from_mood(CharacterMood.IRRITATED).archetype == VisualMotionArchetype.SHAKE_HEAD

    def test_situational_overlays_and_priorities(self) -> None:
        """Requirement: Situational overlays (speaking, thinking) preempt baseline idle with higher priority."""
        baseline_cmd = MotionMapper.map_motion(CharacterMood.NEUTRAL, is_speaking=False, is_thinking=False)
        assert baseline_cmd.priority == 1
        assert baseline_cmd.archetype == VisualMotionArchetype.IDLE_NORMAL

        thinking_cmd = MotionMapper.map_motion(CharacterMood.NEUTRAL, is_speaking=False, is_thinking=True)
        assert thinking_cmd.priority == 2
        assert thinking_cmd.archetype == VisualMotionArchetype.THINKING_TILT

        speaking_cmd = MotionMapper.map_motion(CharacterMood.NEUTRAL, is_speaking=True, is_thinking=False)
        assert speaking_cmd.priority == 3
        assert speaking_cmd.archetype == VisualMotionArchetype.TALKING_CASUAL

        # Speaking takes precedence over thinking
        speaking_thinking_cmd = MotionMapper.map_motion(CharacterMood.NEUTRAL, is_speaking=True, is_thinking=True)
        assert speaking_thinking_cmd.priority == 3
        assert speaking_thinking_cmd.archetype == VisualMotionArchetype.TALKING_CASUAL

    def test_no_state_mutation(self) -> None:
        """Lock 2 & Lock 7: Motion mapping must strictly never mutate any character or emotion state."""
        mood = CharacterMood.GOOD
        cmd = MotionMapper.map_motion(mood=mood, is_speaking=True)
        assert mood == CharacterMood.GOOD
        assert cmd.archetype == VisualMotionArchetype.TALKING_CASUAL

    def test_pure_determinism(self) -> None:
        """Verify re-running MotionMapper produces identical outputs."""
        cmd1 = MotionMapper.map_motion(CharacterMood.TIRED, is_speaking=False, is_thinking=False)
        cmd2 = MotionMapper.map_motion(CharacterMood.TIRED, is_speaking=False, is_thinking=False)
        assert cmd1 == cmd2


class TestConstitutionalMapperBoundariesAST:
    """Pure static AST inspection ensuring zero constitutional boundary violations in Phase 11.2."""

    @pytest.mark.parametrize(
        "module_path",
        [
            "app/visual/expression_mapper.py",
            "app/visual/motion_mapper.py",
        ],
    )
    def test_zero_db_network_llm_imports(self, module_path: str) -> None:
        """Lock 6: Mapper modules must never import DB, network, or LLM engines."""
        file_path = pathlib.Path(module_path)
        assert file_path.exists(), f"File {file_path} not found"
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        forbidden_modules = {
            "sqlite3", "sqlalchemy", "httpx", "aiohttp", "requests", "urllib",
            "google", "openai", "anthropic", "webgl", "canvas", "pygame", "pyglet",
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

    @pytest.mark.parametrize(
        "module_path",
        [
            "app/visual/expression_mapper.py",
            "app/visual/motion_mapper.py",
        ],
    )
    def test_zero_set_fact_or_promotion_authority(self, module_path: str) -> None:
        """Lock 1: Mappers have strictly 0 set_fact or promotion authority."""
        file_path = pathlib.Path(module_path)
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
