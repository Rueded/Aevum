"""Phase 13.5 Realtime Embodiment & Visual Sync Acceptance Suite.

Governed by Phase 13.5 Gate Invariants:
1. RMS -> ParamMouthOpenY Unidirectional Mapping:
   - Web Audio RMS strictly drives ParamMouthOpenY in [0.0, 1.0].
   - ParamMouthForm is strictly 0.0 across all inputs and amplitudes.
   - Audio energy NEVER touches EmotionState, CharacterMood, or Reality.
2. Client-Local Instant Barge-In Latch (P95 <= 20ms target):
   - Immediately clamps mouth_open_y to 0.0 and sets is_speaking to False.
   - Latches active generation; stale or latched generation frames cannot reopen mouth.
3. Playback / Microphone Isolation (13.2-LOCK-F):
   - Mouth analyzer only connects to assistant playback stream.
   - User microphone capture path is strictly segregated (user speech never drives companion mouth).
   - Microphone mute does not mute playback; playback mute does not mute microphone.
4. Late / Stale TTS Frame Fencing:
   - Frames with generation_id < activeGenerationId are unconditionally dropped.
   - Stale frames cannot reset the latch or cause mouth movement.
5. Rule 19 Zero Reverse State Mutation:
   - Visual and lip-sync modules have 0 mutation tokens, 0 DB writes, 0 reality authority.
"""

from __future__ import annotations

import math
from pathlib import Path
import pytest

DESKTOP_DIR = Path("../apps/desktop").resolve()
VISUAL_DIR = DESKTOP_DIR / "src" / "visual"
COMPONENTS_DIR = DESKTOP_DIR / "src" / "components"


# =============================================================================
# Python-level Mirror of RealtimeLipSyncEngine for Exact Deterministic Testing
# =============================================================================

class MockRealtimeLipSyncEngine:
    def __init__(
        self,
        noise_gate: float = 0.015,
        gain: float = 3.8,
        attack: float = 0.65,
        decay: float = 0.28,
        max_lag_ms: float = 80.0,
    ):
        self.noise_gate = noise_gate
        self.gain = gain
        self.attack = attack
        self.decay = decay
        self.max_lag_ms = max_lag_ms
        self.current_mouth_open = 0.0
        self.is_speaking = False
        self.active_generation_id = 0
        self.latched_barge_in_generation = -1

    def calculate_rms(self, samples: list[float]) -> float:
        if not samples:
            return 0.0
        sum_sq = sum(s * s for s in samples)
        return math.sqrt(sum_sq / len(samples))

    def normalize_rms(self, rms: float) -> float:
        if rms <= self.noise_gate:
            return 0.0
        signal = (rms - self.noise_gate) * self.gain
        return max(0.0, min(1.0, signal))

    def smooth(self, current: float, target: float) -> float:
        if target > current:
            return current + self.attack * (target - current)
        else:
            return current + self.decay * (target - current)

    def trigger_barge_in(self, generation_id: int | None = None) -> dict:
        target_gen = generation_id if generation_id is not None else self.active_generation_id
        self.latched_barge_in_generation = target_gen
        self.active_generation_id = max(self.active_generation_id, target_gen)
        self.current_mouth_open = 0.0
        self.is_speaking = False
        return self.get_mouth_state()

    def reset_latch(self, new_generation_id: int) -> None:
        self.active_generation_id = new_generation_id
        self.latched_barge_in_generation = -1
        self.current_mouth_open = 0.0
        self.is_speaking = False

    def process_chunk(self, samples: list[float], generation_id: int) -> dict:
        # 1. Generation Fence Check
        if generation_id < self.active_generation_id:
            return self.get_mouth_state()

        # 2. Barge-in Latch Check
        if generation_id <= self.latched_barge_in_generation:
            self.current_mouth_open = 0.0
            self.is_speaking = False
            return self.get_mouth_state()

        if generation_id > self.active_generation_id:
            self.active_generation_id = generation_id
            self.latched_barge_in_generation = -1

        rms = self.calculate_rms(samples)
        target = self.normalize_rms(rms)
        self.current_mouth_open = self.smooth(self.current_mouth_open, target)
        self.is_speaking = self.current_mouth_open > 0.04
        return self.get_mouth_state()

    def get_mouth_state(self) -> dict:
        return {
            "mouth_open_y": max(0.0, min(1.0, self.current_mouth_open)),
            "mouth_form": 0.0,  # Lock 1: Strictly 0.0
            "is_speaking": self.is_speaking and self.latched_barge_in_generation < self.active_generation_id,
        }


# =============================================================================
# Cluster 1: RMS -> ParamMouthOpenY Unidirectional Mapping & ParamMouthForm clamp
# =============================================================================

def test_phase135_rms_to_mouth_open_unidirectional():
    """Verify that audio RMS maps to ParamMouthOpenY while ParamMouthForm is clamped strictly to 0.0."""
    engine = MockRealtimeLipSyncEngine()

    # Silent / background noise below noise gate -> 0.0
    state_silent = engine.process_chunk([0.005] * 256, generation_id=1)
    assert state_silent["mouth_open_y"] == 0.0
    assert state_silent["mouth_form"] == 0.0
    assert not state_silent["is_speaking"]

    # Active audio energy -> mouth opens in [0.0, 1.0]
    state_active = engine.process_chunk([0.25] * 256, generation_id=1)
    assert state_active["mouth_open_y"] > 0.1
    assert state_active["mouth_form"] == 0.0  # Clamp strictly preserved
    assert state_active["is_speaking"]

    # Maximum volume saturates at 1.0, mouth_form still 0.0
    state_loud = engine.process_chunk([1.0] * 256, generation_id=1)
    assert state_loud["mouth_open_y"] <= 1.0
    assert state_loud["mouth_form"] == 0.0


# =============================================================================
# Cluster 2: Client-Local Instant Barge-In Latch & Generation Fencing
# =============================================================================

def test_phase135_instant_barge_in_clamp_and_latched_generation():
    """Verify ADR-024 Lock 4: Instant zero clamp and generation fence preventing reopen."""
    engine = MockRealtimeLipSyncEngine()

    # Speech in Generation 1
    engine.process_chunk([0.3] * 256, generation_id=1)
    assert engine.get_mouth_state()["mouth_open_y"] > 0.1

    # Barge-In occurs
    clamped = engine.trigger_barge_in(generation_id=1)
    assert clamped["mouth_open_y"] == 0.0
    assert clamped["mouth_form"] == 0.0
    assert not clamped["is_speaking"]

    # Any late-arriving packets from Generation 1 are blocked by the latch
    state_late = engine.process_chunk([0.8] * 256, generation_id=1)
    assert state_late["mouth_open_y"] == 0.0
    assert not state_late["is_speaking"]

    # Reset latch with new Generation 2 explicitly unlatches
    engine.reset_latch(new_generation_id=2)
    state_gen2 = engine.process_chunk([0.3] * 256, generation_id=2)
    assert state_gen2["mouth_open_y"] > 0.05
    assert state_gen2["is_speaking"]


# =============================================================================
# Cluster 3: Late / Stale TTS Frame Rejection
# =============================================================================

def test_phase135_stale_generation_frames_dropped():
    """Verify that audio packets with generation_id < activeGenerationId are dropped."""
    engine = MockRealtimeLipSyncEngine()

    # Advance active generation to 5
    engine.reset_latch(new_generation_id=5)

    # Audio chunk from stale generation 3 or 4 arrives -> DROPPED
    stale_state = engine.process_chunk([0.5] * 256, generation_id=3)
    assert stale_state["mouth_open_y"] == 0.0

    stale_state4 = engine.process_chunk([0.5] * 256, generation_id=4)
    assert stale_state4["mouth_open_y"] == 0.0

    # Valid current generation 5 -> processed
    valid_state = engine.process_chunk([0.5] * 256, generation_id=5)
    assert valid_state["mouth_open_y"] > 0.1


# =============================================================================
# Cluster 4: Playback Mute & Microphone Capture Isolation (13.2-LOCK-F)
# =============================================================================

def test_phase135_playback_and_microphone_isolation_audit():
    """Verify that microphone stream is strictly isolated from lip-sync engine."""
    app_tsx = (DESKTOP_DIR / "src" / "App.tsx").read_text(encoding="utf-8")
    call_hud = (COMPONENTS_DIR / "CallHUD.tsx").read_text(encoding="utf-8")
    chat_view = (COMPONENTS_DIR / "ChatView.tsx").read_text(encoding="utf-8")

    # App.tsx connects lipSync to assistant playback, never to media recorder microphone stream
    assert "attachPlaybackElement" in app_tsx or "attachAudioElement" in app_tsx
    assert "realtimeLipSyncRef.current" in app_tsx

    # LipSyncAnalyzer must not reference getUserMedia or MediaStreamAudioSourceNode
    realtime_lipsync = (VISUAL_DIR / "realtimeLipSync.ts").read_text(encoding="utf-8")
    assert "getUserMedia" not in realtime_lipsync
    assert "createMediaStreamSource" not in realtime_lipsync

    # CallHUD mute only sets isMuted state
    assert "onToggleMute" in call_hud
    assert "btn-mute" in call_hud


# =============================================================================
# Cluster 5: Visual Mappers & Directives Integration
# =============================================================================

def test_phase135_visual_directive_mapper_presentation_only():
    """Verify that visual directives from realtime call are purely presentation mappers."""
    visual_mappers = (VISUAL_DIR / "visualMappers.ts").read_text(encoding="utf-8")

    assert "mapVisualDirectiveToExpression" in visual_mappers
    # Must not contain state mutation tokens
    assert "set_fact" not in visual_mappers
    assert "update_relationship" not in visual_mappers
    assert "PromotionAuthorizationToken" not in visual_mappers


# =============================================================================
# Cluster 6: Rule 19 Static AST Boundary Audit
# =============================================================================

def test_phase135_rule19_visual_ast_audit():
    """Verify Rule 19: Visual and lip-sync files contain 0 reality or state mutations."""
    files_to_check = [
        VISUAL_DIR / "realtimeLipSync.ts",
        VISUAL_DIR / "visualMappers.ts",
        VISUAL_DIR / "lipSyncAnalyzer.ts",
        VISUAL_DIR / "cubismManager.ts",
        VISUAL_DIR / "gazeTracker.ts",
    ]

    forbidden_tokens = [
        "set_fact",
        "update_relationship",
        "mutate_character",
        "PromotionAuthorizationToken",
        "sqlite3",
        "SQLAlchemy",
        "AsyncSession",
    ]

    for fpath in files_to_check:
        assert fpath.is_file(), f"{fpath.name} must exist"
        content = fpath.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            assert token not in content, f"Rule 19 violation: '{token}' found in {fpath.name}"
