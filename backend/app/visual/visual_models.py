"""Pure immutable data contracts and domain models for the Visual subsystem (Phase 11.1).

Governed by ADR-022:
- Mind/Body Boundary: Live2D is Aevum's visible body, not its second mind.
- Backend Character Engine remains the sole mind, sole emotion authority, and single source of truth.
- Lock 1: Visual State != Canonical Reality (Canvas, meshes, motions, physics are transient presentation artifacts; 0 DB mutation authority, 0 set_fact).
- Lock 2: Unidirectional Affective Visual Mapping (Backend EmotionState/Mood -> Render Instructions -> Renderer; zero reverse state mutation).
- Lock 3: Audio-Driven Lip-Sync Without Epistemic Authority (Audio RMS -> ParamMouthOpenY only; ParamMouthForm reserved for future visemes; barge-in zero latch).
- Lock 4: Pure Visual Presentation Scope (Hit-testing / touch interaction is strictly deferred).
- Lock 5: Fail-Closed & Graceful Visual Degradability (WebGL failure falls back to text/voice UI without breaking backend).
- Lock 6: Hermetic Testability & Zero WebGL Backend Leakage (Zero WebGL/Canvas/DOM imports in backend).
- Lock 7: Renderer State != Character State (Blink timers, micro-saccades, and physics state are isolated Renderer State).
"""

from __future__ import annotations

import enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class VisualSubsystemType(str, enum.Enum):
    """The four decoupled visual subsystems (ADR-022 Subsystem Separation).

    Strictly forbids combining into a monolithic visual manager.
    """

    EXPRESSION = "EXPRESSION"
    MOTION = "MOTION"
    GAZE = "GAZE"
    LIPSYNC = "LIPSYNC"


class VisualExpressionType(str, enum.Enum):
    """Canonical visual expression archetypes."""

    NEUTRAL = "neutral"
    JOY = "joy"
    SMILE = "smile"
    SAD = "sad"
    POUT = "pout"
    SURPRISE = "surprise"
    THINKING = "thinking"
    BLUSH = "blush"
    WORRIED = "worried"
    TIRED = "tired"


class VisualMotionArchetype(str, enum.Enum):
    """Canonical visual motion and idle posture archetypes."""

    IDLE_NORMAL = "idle_normal"
    IDLE_DROWSY = "idle_drowsy"
    IDLE_ENERGETIC = "idle_energetic"
    TALKING_CASUAL = "talking_casual"
    THINKING_TILT = "thinking_tilt"
    NOD = "nod"
    SHAKE_HEAD = "shake_head"


class RendererState(str, enum.Enum):
    """Categorical renderer lifecycle state (ADR-022 Lock 7).

    Designates operational status of the desktop WebGL renderer.
    Strictly isolated from CharacterState and EmotionState.
    """

    UNINITIALIZED = "uninitialized"
    LOADING = "loading"
    READY = "ready"
    DEGRADED_FALLBACK = "degraded_fallback"
    ERROR = "error"


class VisualExpressionConfig(BaseModel):
    """Render instruction defining the target facial expression (ADR-022 Lock 2 & Lock 7).

    Strict semantic: "Renderer, please present this appearance",
    NOT "Character has transitioned state".
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    expression: VisualExpressionType = Field(
        default=VisualExpressionType.NEUTRAL,
        description="Target visual expression archetype.",
    )
    intensity: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Expression blending weight, bounded in [0.0, 1.0].",
    )
    parameter_overrides: Dict[str, float] = Field(
        default_factory=dict,
        description="Direct Live2D parameter overrides (e.g. ParamCheek -> 0.8).",
    )
    transition_duration_ms: int = Field(
        default=300,
        ge=0,
        le=5000,
        description="Cross-fade duration in milliseconds.",
    )

    @field_validator("parameter_overrides")
    @classmethod
    def validate_parameter_overrides(cls, v: Dict[str, float]) -> Dict[str, float]:
        for param_name, param_val in v.items():
            if not isinstance(param_name, str) or not param_name.strip():
                raise ValueError("Parameter name must be a non-empty string.")
            if not isinstance(param_val, (int, float)):
                raise ValueError(f"Parameter value for '{param_name}' must be numeric.")
            if not (-30.0 <= float(param_val) <= 30.0):
                raise ValueError(
                    f"Parameter value for '{param_name}' out of safe range [-30.0, 30.0]: {param_val}"
                )
        return v


class VisualMotionCommand(BaseModel):
    """Render instruction defining an animation or posture command (ADR-022 Lock 2 & Lock 7).

    Strict semantic: "Renderer, please execute this animation",
    NOT "Character has transitioned state".
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    archetype: VisualMotionArchetype = Field(
        default=VisualMotionArchetype.IDLE_NORMAL,
        description="Target motion archetype.",
    )
    priority: int = Field(
        default=1,
        ge=0,
        le=10,
        description="Motion queue priority (higher priority preempts lower).",
    )
    loop: bool = Field(
        default=True,
        description="Whether the motion should loop indefinitely until replaced.",
    )
    fade_in_ms: int = Field(
        default=500,
        ge=0,
        le=5000,
        description="Fade-in transition duration in milliseconds.",
    )
    fade_out_ms: int = Field(
        default=500,
        ge=0,
        le=5000,
        description="Fade-out transition duration in milliseconds.",
    )


class Live2DParameterMapping(BaseModel):
    """Specification of a single Live2D model parameter with boundaries."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    parameter_id: str = Field(min_length=1, description="Live2D parameter identifier (e.g. ParamMouthOpenY).")
    default_value: float = Field(default=0.0, description="Default parameter value.")
    min_value: float = Field(default=-1.0, description="Minimum parameter value.")
    max_value: float = Field(default=1.0, description="Maximum parameter value.")
    description: Optional[str] = Field(default=None, description="Human-readable description of parameter function.")


class Live2DModelManifest(BaseModel):
    """Metadata describing a validated Live2D model asset package."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_id: str = Field(min_length=1, description="Unique identifier for this model configuration.")
    name: str = Field(min_length=1, description="Human-readable model name.")
    version: str = Field(default="1.0.0", description="Model asset package version.")
    model_path: str = Field(min_length=1, description="Relative path to model3.json file.")
    texture_paths: List[str] = Field(default_factory=list, description="List of texture image relative paths.")
    motion_groups: Dict[str, List[str]] = Field(default_factory=dict, description="Named motion groups mapping to motion files.")
    expression_map: Dict[str, str] = Field(default_factory=dict, description="Mapping from expression key to .exp3.json path.")
    supported_parameters: List[Live2DParameterMapping] = Field(
        default_factory=list,
        description="List of supported Live2D parameters exposed by this model.",
    )


class GazeTarget(BaseModel):
    """Normalized target coordinate for gaze tracking (ADR-022 Subsystem Gaze).

    Coordinates are normalized in [-1.0, 1.0] relative to canvas center:
    (-1.0, -1.0) = Top-Left, (0.0, 0.0) = Center, (1.0, 1.0) = Bottom-Right.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    x: float = Field(ge=-1.0, le=1.0, description="Normalized X coordinate in [-1.0, 1.0].")
    y: float = Field(ge=-1.0, le=1.0, description="Normalized Y coordinate in [-1.0, 1.0].")
    is_tracked: bool = Field(default=True, description="Whether active gaze tracking is engaged.")


class GazeParameters(BaseModel):
    """Calculated Live2D gaze and head angle output parameters."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    eyeball_x: float = Field(default=0.0, ge=-1.0, le=1.0, description="ParamEyeBallX in [-1.0, 1.0].")
    eyeball_y: float = Field(default=0.0, ge=-1.0, le=1.0, description="ParamEyeBallY in [-1.0, 1.0].")
    angle_x: float = Field(default=0.0, ge=-30.0, le=30.0, description="ParamAngleX in [-30.0, 30.0].")
    angle_y: float = Field(default=0.0, ge=-30.0, le=30.0, description="ParamAngleY in [-30.0, 30.0].")
    angle_z: float = Field(default=0.0, ge=-30.0, le=30.0, description="ParamAngleZ in [-30.0, 30.0].")


class LipSyncMouthState(BaseModel):
    """Mouth parameter state driven by audio amplitude (ADR-022 Lock 3).

    ParamMouthOpenY is strictly driven by RMS audio energy envelope.
    ParamMouthForm remains unmanaged by amplitude (reserved for future visemes).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    mouth_open_y: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="ParamMouthOpenY opening value in [0.0, 1.0], driven by audio RMS.",
    )
    mouth_form: float = Field(
        default=0.0,
        ge=-1.0,
        le=1.0,
        description="ParamMouthForm value in [-1.0, 1.0], baseline/viseme unmanaged by RMS.",
    )
    is_speaking: bool = Field(
        default=False,
        description="Whether active speech audio playback is occurring.",
    )


class RendererPresentationConfig(BaseModel):
    """Presentation configuration for the Live2D renderer (ADR-022 Lock 7).

    Defines presentation behaviors (e.g. blink intervals, saccade timing).
    Strictly designated as renderer configuration, NOT emotional measurements.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    blink_interval_mean_ms: int = Field(
        default=4000,
        ge=1000,
        le=15000,
        description="Mean interval between natural blinks in milliseconds.",
    )
    blink_duration_ms: int = Field(
        default=150,
        ge=50,
        le=500,
        description="Duration of a single eye blink in milliseconds.",
    )
    saccade_enabled: bool = Field(
        default=True,
        description="Whether natural eye-dart micro-saccades are enabled.",
    )
    saccade_interval_mean_ms: int = Field(
        default=2500,
        ge=500,
        le=10000,
        description="Mean interval between micro-saccades in milliseconds.",
    )
    breath_cycle_ms: int = Field(
        default=6000,
        ge=2000,
        le=12000,
        description="ParamBreath cycle duration in milliseconds.",
    )
