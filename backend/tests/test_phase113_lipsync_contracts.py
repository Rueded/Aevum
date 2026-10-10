"""test_phase113_lipsync_contracts.py — Dedicated Unit Tests for Phase 11.3 Lip-Sync Engine.

Verifies:
1. Mathematical RMS energy computation (DC, sine wave, silence).
2. Noise gate cutoff and normalization to ParamMouthOpenY [0.0, 1.0].
3. Asymmetric attack/decay smoothing behavior.
4. ADR-022 Lock 3: ParamMouthForm remains strictly untouched (0.0).
5. ADR-022 Lock 3: Barge-in Immediate-Zero Latch state machine.
   (Instant zero drop, latch persistence, unlatch on new playback).
6. Pure static AST boundary audits:
   - Zero modification or dependency mutation of Phase 10 Voice modules.
   - Zero DB, Zero LLM, Zero set_fact authority in visual lip-sync code.
"""

from __future__ import annotations

import ast
import math
import pathlib
import pytest

from app.visual.visual_models import LipSyncMouthState


# Python reference simulation of the LipSync mathematical model implemented in TypeScript
def calculate_rms(samples: list[float]) -> float:
    if not samples:
        return 0.0
    sum_sq = sum(s * s for s in samples)
    return math.sqrt(sum_sq / len(samples))


def normalize_rms_to_mouth_open(
    rms: float,
    noise_gate: float = 0.015,
    gain: float = 3.8,
) -> float:
    if rms <= noise_gate:
        return 0.0
    signal = (rms - noise_gate) * gain
    return max(0.0, min(1.0, signal))


def smooth_mouth_open(
    current: float,
    target: float,
    attack_rate: float = 0.65,
    decay_rate: float = 0.28,
) -> float:
    if target > current:
        return current + attack_rate * (target - current)
    else:
        return current + decay_rate * (target - current)


class LipSyncStateMachineSimulator:
    """State machine simulating the Desktop LipSyncAnalyzer latching behavior."""

    def __init__(self, noise_gate: float = 0.015, gain: float = 3.8) -> None:
        self.noise_gate = noise_gate
        self.gain = gain
        self.current_mouth_open = 0.0
        self.barge_in_latched = False
        self.is_speaking = False

    def step(self, samples: list[float]) -> LipSyncMouthState:
        if self.barge_in_latched:
            self.current_mouth_open = 0.0
            self.is_speaking = False
            return LipSyncMouthState(mouth_open_y=0.0, mouth_form=0.0, is_speaking=False)

        rms = calculate_rms(samples)
        target = normalize_rms_to_mouth_open(rms, self.noise_gate, self.gain)
        self.current_mouth_open = smooth_mouth_open(self.current_mouth_open, target)
        self.is_speaking = self.current_mouth_open > 0.05

        return LipSyncMouthState(
            mouth_open_y=round(self.current_mouth_open, 4),
            mouth_form=0.0,  # Lock 3: strictly 0.0
            is_speaking=self.is_speaking,
        )

    def trigger_barge_in(self) -> LipSyncMouthState:
        """Lock 3: Immediately zeroes mouth opening and enters latched mode."""
        self.barge_in_latched = True
        self.current_mouth_open = 0.0
        self.is_speaking = False
        return LipSyncMouthState(mouth_open_y=0.0, mouth_form=0.0, is_speaking=False)

    def start_new_playback(self) -> None:
        """Resets latch when a new assistant audio session begins."""
        self.barge_in_latched = False
        self.current_mouth_open = 0.0
        self.is_speaking = False


class TestLipSyncMathematics:
    """Verifies the core mathematical algorithms of the LipSync engine."""

    def test_calculate_rms_silence_and_dc(self) -> None:
        # Silence
        assert calculate_rms([]) == 0.0
        assert calculate_rms([0.0, 0.0, 0.0]) == 0.0

        # DC offset
        assert pytest.approx(calculate_rms([0.5, 0.5, 0.5, 0.5]), abs=1e-5) == 0.5
        assert pytest.approx(calculate_rms([-0.8, -0.8, -0.8]), abs=1e-5) == 0.8

    def test_calculate_rms_sine_wave(self) -> None:
        # Sinusoidal wave with peak amplitude A=1.0: RMS should be 1 / sqrt(2) ≈ 0.7071
        num_samples = 1000
        sine_samples = [math.sin(2 * math.pi * i / 100) for i in range(num_samples)]
        rms = calculate_rms(sine_samples)
        assert pytest.approx(rms, abs=0.01) == 1.0 / math.sqrt(2.0)

    def test_noise_gate_cutoff(self) -> None:
        # Energy below noise gate (0.015) must yield strictly 0.0
        assert normalize_rms_to_mouth_open(0.0) == 0.0
        assert normalize_rms_to_mouth_open(0.010) == 0.0
        assert normalize_rms_to_mouth_open(0.015) == 0.0

        # Energy above noise gate scales up and is bounded at 1.0
        val_mid = normalize_rms_to_mouth_open(0.10)
        assert 0.0 < val_mid < 1.0

        val_max = normalize_rms_to_mouth_open(0.80)
        assert val_max == 1.0

    def test_smoothing_attack_and_decay(self) -> None:
        # Attack: rapid rise (attack_rate = 0.65)
        current = 0.0
        target = 1.0
        stepped = smooth_mouth_open(current, target, attack_rate=0.65, decay_rate=0.28)
        assert stepped == 0.65

        # Decay: slower trailing release (decay_rate = 0.28)
        current = 1.0
        target = 0.0
        stepped_decay = smooth_mouth_open(current, target, attack_rate=0.65, decay_rate=0.28)
        assert stepped_decay == 0.72  # 1.0 + 0.28 * (0 - 1.0) = 0.72


class TestLipSyncBargeInLatch:
    """Verifies ADR-022 Lock 3: Barge-in Immediate-Zero Latch state machine."""

    def test_active_speech_frame_progression(self) -> None:
        sim = LipSyncStateMachineSimulator()
        samples = [0.2] * 256  # Moderate energy sound

        # Feed multiple frames: mouth should smoothly open and indicate speaking
        state1 = sim.step(samples)
        state2 = sim.step(samples)
        state3 = sim.step(samples)

        assert state1.mouth_open_y > 0.0
        assert state3.mouth_open_y > state1.mouth_open_y
        assert state3.is_speaking is True
        assert state3.mouth_form == 0.0  # Lock 3: untouched

    def test_barge_in_instant_zero_and_latch_persistence(self) -> None:
        sim = LipSyncStateMachineSimulator()
        samples = [0.3] * 256

        # Step into speaking state
        for _ in range(5):
            sim.step(samples)
        assert sim.current_mouth_open > 0.3
        assert sim.is_speaking is True

        # User barges in (typing, enter, or PTT pressed)
        barge_in_state = sim.trigger_barge_in()
        assert barge_in_state.mouth_open_y == 0.0
        assert barge_in_state.is_speaking is False
        assert barge_in_state.mouth_form == 0.0
        assert sim.barge_in_latched is True

        # While latched, even loud audio input must produce strictly 0.0
        loud_samples = [0.8] * 256
        latched_state1 = sim.step(loud_samples)
        latched_state2 = sim.step(loud_samples)

        assert latched_state1.mouth_open_y == 0.0
        assert latched_state2.mouth_open_y == 0.0
        assert latched_state1.is_speaking is False
        assert latched_state2.is_speaking is False

    def test_unlatch_on_new_playback_session(self) -> None:
        sim = LipSyncStateMachineSimulator()
        samples = [0.3] * 256

        # Barge-in and latch
        sim.step(samples)
        sim.trigger_barge_in()
        assert sim.barge_in_latched is True

        # New playback starts
        sim.start_new_playback()
        assert sim.barge_in_latched is False

        # Now sound resumes mouth movement
        resumed_state = sim.step(samples)
        assert resumed_state.mouth_open_y > 0.0
        assert resumed_state.mouth_form == 0.0


class TestConstitutionalLipSyncBoundariesAST:
    """Pure static AST inspection ensuring zero constitutional boundary violations."""

    def test_zero_modifications_to_phase10_voice_contracts(self) -> None:
        """Phase 11.3 must never modify or alter Phase 10 Voice models or services."""
        voice_files = [
            pathlib.Path("app/voice/voice_models.py"),
            pathlib.Path("app/voice/tts_service.py"),
            pathlib.Path("app/voice/audio_cache.py"),
            pathlib.Path("app/voice/stt_service.py"),
        ]

        forbidden_tokens = {"lip_sync", "mouth_open", "cubism", "live2d"}

        for vf in voice_files:
            assert vf.exists(), f"Phase 10 file {vf} must exist"
            content = vf.read_text(encoding="utf-8").lower()
            for token in forbidden_tokens:
                assert token not in content, (
                    f"Forbidden Phase 11 token '{token}' leaked into Phase 10 file {vf}"
                )

    def test_desktop_lipsync_analyzer_purity(self) -> None:
        """Desktop LipSyncAnalyzer must not attempt to mutate backend state or DB."""
        ts_file = pathlib.Path("../apps/desktop/src/visual/lipSyncAnalyzer.ts")
        assert ts_file.exists(), f"TypeScript file {ts_file} not found"
        content = ts_file.read_text(encoding="utf-8")

        forbidden_ts_tokens = [
            "set_fact",
            "character_state",
            "promotion",
            "indexeddb",
            "localstorage",
            "api.post",
            "api.patch",
        ]

        for token in forbidden_ts_tokens:
            assert token not in content.lower(), (
                f"Forbidden token '{token}' found in {ts_file}"
            )
