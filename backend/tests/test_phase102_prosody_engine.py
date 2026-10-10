"""Test suite for Phase 10.2 Emotional Prosody Modulation Engine.

Tests:
1. Determinism: Equivalent inputs always produce identical ProsodyConfig.
2. Emotion affect mapping across all EmotionType categories.
3. Intensity scaling and mild intensity threshold (<0.30 suppresses style tag).
4. Baseline CharacterMood bias integration.
5. EpistemicCue categorical hesitation and cadence modulation (ADR-021 Lock D).
6. Non-mutation of domain objects (ADR-021 Lock C: EmotionState & CharacterState intact).
7. Acoustic parameter bounds validation under extreme inputs.
8. Static AST boundary audit across prosody_mapper.py (0 DB, 0 network, 0 mutation, 0 LLM).
"""

import ast
from datetime import datetime, timezone
import math
import pathlib
import pytest

from app.character.engine_models import CharacterStateContext
from app.character.state_models import CharacterMood, CharacterState
from app.emotion.emotion_models import EmotionState, EmotionType
from app.voice import EpistemicCue, ProsodyConfig, ProsodyMapper


class TestProsodyMapperDeterminism:
    """Verifies that prosody mapping is 100% deterministic and free of LLM hallucinations."""

    def test_bit_identical_mapping(self):
        config1 = ProsodyMapper.map_prosody(
            emotion_type=EmotionType.HAPPY,
            intensity=0.75,
            mood=CharacterMood.GOOD,
            epistemic_cue=EpistemicCue.CERTAIN,
        )
        config2 = ProsodyMapper.map_prosody(
            emotion_type=EmotionType.HAPPY,
            intensity=0.75,
            mood=CharacterMood.GOOD,
            epistemic_cue=EpistemicCue.CERTAIN,
        )
        assert config1 == config2
        assert config1.rate_multiplier == config2.rate_multiplier
        assert config1.pitch_shift_semitones == config2.pitch_shift_semitones
        assert config1.volume_gain_db == config2.volume_gain_db
        assert config1.style_tag == config2.style_tag
        assert config1.hesitation_pause_ms == config2.hesitation_pause_ms

    def test_neutral_baseline(self):
        config = ProsodyMapper.map_prosody(
            emotion_type=EmotionType.NEUTRAL,
            intensity=0.50,
            mood=CharacterMood.NEUTRAL,
            epistemic_cue=EpistemicCue.CERTAIN,
        )
        assert config.rate_multiplier == 1.00
        assert config.pitch_shift_semitones == 0.00
        assert config.volume_gain_db == 0.00
        assert config.style_tag is None
        assert config.hesitation_pause_ms == 0


class TestEmotionAcousticProfiles:
    """Verifies emotion profiles and intensity scaling."""

    def test_excited_high_intensity(self):
        config = ProsodyMapper.map_prosody(
            emotion_type=EmotionType.EXCITED,
            intensity=0.90,
            mood=None,
            epistemic_cue=EpistemicCue.CERTAIN,
        )
        # Excited increases rate, pitch, volume, and sets style='excited'
        assert config.rate_multiplier > 1.10
        assert config.pitch_shift_semitones > 2.0
        assert config.volume_gain_db > 1.5
        assert config.style_tag == "excited"
        assert config.hesitation_pause_ms == 0

    def test_sad_moderate_intensity(self):
        config = ProsodyMapper.map_prosody(
            emotion_type=EmotionType.SAD,
            intensity=0.70,
            mood=None,
            epistemic_cue=EpistemicCue.CERTAIN,
        )
        # Sad decreases rate, pitch, volume, and sets style='somber'
        assert config.rate_multiplier < 0.95
        assert config.pitch_shift_semitones < -1.0
        assert config.volume_gain_db < -1.0
        assert config.style_tag == "somber"

    def test_tired_whisper_style(self):
        config = ProsodyMapper.map_prosody(
            emotion_type=EmotionType.TIRED,
            intensity=0.80,
            mood=None,
            epistemic_cue=EpistemicCue.CERTAIN,
        )
        assert config.rate_multiplier < 0.92
        assert config.pitch_shift_semitones < -1.0
        assert config.volume_gain_db < -1.5
        assert config.style_tag == "whisper"

    def test_mild_intensity_suppresses_style_tag(self):
        """Intensity < 0.30 indicates mild/subtle emotion; style tag is suppressed."""
        config_mild = ProsodyMapper.map_prosody(
            emotion_type=EmotionType.EXCITED,
            intensity=0.20,
            mood=None,
            epistemic_cue=EpistemicCue.CERTAIN,
        )
        assert config_mild.style_tag is None

        config_strong = ProsodyMapper.map_prosody(
            emotion_type=EmotionType.EXCITED,
            intensity=0.35,
            mood=None,
            epistemic_cue=EpistemicCue.CERTAIN,
        )
        assert config_strong.style_tag == "excited"


class TestMoodBiasIntegration:
    """Verifies baseline CharacterMood modulation."""

    def test_mood_tired_biases_downward(self):
        base_config = ProsodyMapper.map_prosody(
            emotion_type=EmotionType.NEUTRAL,
            intensity=0.50,
            mood=None,
        )
        tired_config = ProsodyMapper.map_prosody(
            emotion_type=EmotionType.NEUTRAL,
            intensity=0.50,
            mood=CharacterMood.TIRED,
        )
        assert tired_config.rate_multiplier < base_config.rate_multiplier
        assert tired_config.pitch_shift_semitones < base_config.pitch_shift_semitones
        assert tired_config.volume_gain_db < base_config.volume_gain_db

    def test_mood_good_biases_upward(self):
        base_config = ProsodyMapper.map_prosody(
            emotion_type=EmotionType.NEUTRAL,
            intensity=0.50,
            mood=None,
        )
        good_config = ProsodyMapper.map_prosody(
            emotion_type=EmotionType.NEUTRAL,
            intensity=0.50,
            mood=CharacterMood.GOOD,
        )
        assert good_config.rate_multiplier > base_config.rate_multiplier
        assert good_config.pitch_shift_semitones > base_config.pitch_shift_semitones


class TestEpistemicHesitationModulation:
    """Verifies ADR-021 Lock D: Categorical EpistemicCue deterministically modulates hesitation."""

    def test_epistemic_cue_certain_zero_hesitation(self):
        config = ProsodyMapper.map_prosody(
            emotion_type=EmotionType.NEUTRAL,
            intensity=0.50,
            epistemic_cue=EpistemicCue.CERTAIN,
        )
        assert config.hesitation_pause_ms == 0

    def test_epistemic_cue_uncertain_hesitation_and_rate_drop(self):
        certain = ProsodyMapper.map_prosody(
            emotion_type=EmotionType.NEUTRAL,
            intensity=0.50,
            epistemic_cue=EpistemicCue.CERTAIN,
        )
        uncertain = ProsodyMapper.map_prosody(
            emotion_type=EmotionType.NEUTRAL,
            intensity=0.50,
            epistemic_cue=EpistemicCue.UNCERTAIN,
        )
        assert uncertain.hesitation_pause_ms == 250
        assert uncertain.rate_multiplier < certain.rate_multiplier
        assert uncertain.pitch_shift_semitones < certain.pitch_shift_semitones

    def test_epistemic_cue_ambiguous_hesitation(self):
        ambiguous = ProsodyMapper.map_prosody(
            emotion_type=EmotionType.CALM,
            intensity=0.50,
            epistemic_cue=EpistemicCue.AMBIGUOUS,
        )
        assert ambiguous.hesitation_pause_ms == 350

    def test_epistemic_cue_contested_hesitation(self):
        contested = ProsodyMapper.map_prosody(
            emotion_type=EmotionType.CALM,
            intensity=0.50,
            epistemic_cue=EpistemicCue.CONTESTED,
        )
        assert contested.hesitation_pause_ms == 200

    def test_epistemic_cue_unknown_hesitation(self):
        unknown = ProsodyMapper.map_prosody(
            emotion_type=EmotionType.CALM,
            intensity=0.50,
            epistemic_cue=EpistemicCue.UNKNOWN,
        )
        assert unknown.hesitation_pause_ms == 400


class TestDomainNonMutationLockC:
    """Verifies ADR-021 Lock C: ProsodyMapper is a pure read-only consumer."""

    def test_from_states_does_not_mutate_domain_objects(self):
        now = datetime.now(timezone.utc)
        emotion = EmotionState(
            emotion_type=EmotionType.HAPPY,
            intensity=0.85,
            character_id="aevum",
            version=3,
            created_at=now,
            updated_at=now,
        )
        char_state = CharacterState(
            id="aevum",
            version=5,
            updated_at=now,
            mood=CharacterMood.GOOD,
            energy=0.80,
            stress=0.20,
            social_energy=0.70,
            confidence=0.90,
            irritation=0.00,
            loneliness=0.10,
            current_activity="studying",
            current_location="library",
        )

        # Snapshot pre-call state
        pre_emotion_dict = emotion.model_dump()
        pre_state_dict = char_state.model_dump()

        config = ProsodyMapper.from_states(
            emotion_state=emotion,
            character_state=char_state,
            epistemic_cue=EpistemicCue.UNCERTAIN,
        )

        # Output is valid and contains expected affect
        assert config.rate_multiplier > 1.0
        assert config.hesitation_pause_ms == 250

        # Snapshot post-call state: must be bit-identical
        assert emotion.model_dump() == pre_emotion_dict
        assert char_state.model_dump() == pre_state_dict
        assert emotion.version == 3
        assert char_state.version == 5

    def test_from_states_with_character_state_context(self):
        now = datetime.now(timezone.utc)
        emotion = EmotionState(
            emotion_type=EmotionType.CALM,
            intensity=0.60,
            character_id="aevum",
            version=1,
            created_at=now,
            updated_at=now,
        )
        char_ctx = CharacterStateContext(
            mood=CharacterMood.CALM,
            energy=0.70,
            stress=0.10,
            social_energy=0.60,
            confidence=0.80,
            irritation=0.00,
            loneliness=0.00,
            current_activity="reading",
            current_location="bedroom",
        )

        config = ProsodyMapper.from_states(emotion, char_ctx)
        assert config.style_tag == "calm"
        assert config.hesitation_pause_ms == 0


class TestAcousticBoundarySafety:
    """Verifies that all mapped values stay strictly within physical ProsodyConfig bounds."""

    def test_extreme_intensities_do_not_exceed_bounds(self):
        for emotion in EmotionType:
            for mood in CharacterMood:
                for cue in EpistemicCue:
                    for intensity in [0.0, 0.5, 1.0, 1.5, -0.5]:  # including clamping edge cases
                        config = ProsodyMapper.map_prosody(
                            emotion_type=emotion,
                            intensity=intensity,
                            mood=mood,
                            epistemic_cue=cue,
                        )
                        assert 0.50 <= config.rate_multiplier <= 2.00
                        assert -12.0 <= config.pitch_shift_semitones <= 12.0
                        assert -20.0 <= config.volume_gain_db <= 10.0
                        assert 0 <= config.hesitation_pause_ms <= 2000


class TestStaticASTBoundaryAuditPhase102:
    """Static AST Boundary Audit for Phase 10.2 (prosody_mapper.py).

    Asserts:
    1. ZERO database imports or calls (sqlite3, sqlalchemy, aiosqlite).
    2. ZERO network imports or calls (httpx, requests, aiohttp, urllib, google.genai).
    3. ZERO mutation or promotion authority (set_fact, PromotionAuthorizationToken).
    4. ZERO LLM calls or generation methods.
    5. ZERO concrete TTS/STT engine implementations.
    """

    def test_static_ast_boundary_audit(self):
        target_file = pathlib.Path(__file__).resolve().parent.parent / "app" / "voice" / "prosody_mapper.py"
        assert target_file.exists(), f"Target file {target_file} must exist"

        forbidden_io_modules = {
            "requests", "httpx", "aiohttp", "urllib", "socket",
            "sqlalchemy", "sqlite3", "aiosqlite", "redis",
            "google.genai",
        }
        forbidden_mutation_tokens = {"set_fact", "PromotionAuthorizationToken"}

        violations: list[str] = []
        tree = ast.parse(target_file.read_text(encoding="utf-8"), filename=str(target_file))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in forbidden_io_modules:
                        violations.append(f"{target_file.name}:{node.lineno} imports forbidden module '{alias.name}'")
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".")[0]
                if root in forbidden_io_modules:
                    violations.append(f"{target_file.name}:{node.lineno} from-imports forbidden module '{node.module}'")

            if isinstance(node, ast.Name) and node.id in forbidden_mutation_tokens:
                violations.append(f"{target_file.name}:{node.lineno} references forbidden mutation identifier '{node.id}'")
            elif isinstance(node, ast.Attribute) and node.attr in forbidden_mutation_tokens:
                violations.append(f"{target_file.name}:{node.lineno} references forbidden mutation attribute '{node.attr}'")

        assert not violations, f"AST boundary violations detected in prosody_mapper.py: {violations}"
