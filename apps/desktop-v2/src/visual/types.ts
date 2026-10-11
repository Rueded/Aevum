/**
 * Visual subsystem frontend types (Phase 11.1 / 11.3).
 * Governed by ADR-022:
 * "Live2D is Aevum's visible body, not its second mind."
 */

export type VisualExpressionType =
  | "neutral"
  | "joy"
  | "smile"
  | "sad"
  | "pout"
  | "surprise"
  | "thinking"
  | "blush"
  | "worried"
  | "tired";

export type VisualMotionArchetype =
  | "idle_normal"
  | "idle_drowsy"
  | "idle_energetic"
  | "talking_casual"
  | "thinking_tilt"
  | "nod"
  | "shake_head";

export type RendererState =
  | "uninitialized"
  | "loading"
  | "ready"
  | "degraded_fallback"
  | "error";

export interface VisualExpressionConfig {
  expression: VisualExpressionType;
  intensity: number;
  parameter_overrides: Record<string, number>;
  transition_duration_ms: number;
}

export interface VisualMotionCommand {
  archetype: VisualMotionArchetype;
  priority: number;
  loop: boolean;
  fade_in_ms: number;
  fade_out_ms: number;
}

export interface LipSyncMouthState {
  /** Vertical mouth opening parameter in [0.0, 1.0], driven by audio RMS energy */
  mouth_open_y: number;
  /** Horizontal/form mouth parameter in [-1.0, 1.0], baseline/viseme unmanaged by RMS */
  mouth_form: number;
  /** Whether speech audio playback is actively outputting sound */
  is_speaking: boolean;
}

export interface GazeTarget {
  x: number; // [-1.0, 1.0] relative to canvas center
  y: number; // [-1.0, 1.0]
  is_tracked: boolean;
}

export interface GazeParameters {
  eyeball_x: number; // [-1.0, 1.0]
  eyeball_y: number; // [-1.0, 1.0]
  angle_x: number;   // [-30.0, 30.0]
  angle_y: number;   // [-30.0, 30.0]
  angle_z: number;   // [-30.0, 30.0]
}
