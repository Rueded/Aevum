/**
 * Desktop Visual Presentation Mappers (Phase 11.2 / 11.5).
 *
 * Governed by ADR-022:
 * - Lock 2: Unidirectional Affective Visual Mapping (Mind -> Render Instructions -> Body).
 * - Lock 7: Renderer State != Character State (Render Instruction != Character State).
 * - Mind/Body Boundary: Deterministic aesthetic presentation policies,
 *   NOT psychological universal truths or emotion inference engines.
 * - Zero reverse state mutation, zero DB writes, zero canonical mutation authority.
 */

import {
  VisualExpressionConfig,
  VisualExpressionType,
  VisualMotionArchetype,
  VisualMotionCommand,
} from "./types";

/**
 * Mapping table from EmotionType string to VisualExpressionType.
 * Matches backend ExpressionMapper presentation policy table.
 */
const EMOTION_MAP: Record<string, VisualExpressionType> = {
  neutral: "neutral",
  happy: "joy",
  calm: "neutral",
  excited: "joy",
  curious: "thinking",
  amused: "smile",
  content: "smile",
  sad: "sad",
  disappointed: "sad",
  worried: "worried",
  frustrated: "pout",
  irritated: "pout",
  angry: "pout",
  lonely: "sad",
  embarrassed: "blush",
  nervous: "worried",
  tired: "tired",
};

/**
 * Baseline mood motion archetype mapping.
 * Matches backend MotionMapper policy table.
 */
const MOOD_MOTION_MAP: Record<string, VisualMotionArchetype> = {
  neutral: "idle_normal",
  good: "idle_energetic",
  calm: "idle_normal",
  low: "idle_drowsy",
  tired: "idle_drowsy",
  irritated: "shake_head",
  focused: "thinking_tilt",
};

/**
 * Derives VisualExpressionConfig from emotion, mood, and situational generation state.
 */
export function deriveVisualExpression(
  emotionType?: string,
  intensity: number = 1.0,
  mood?: string,
  isGenerating: boolean = false
): VisualExpressionConfig {
  if (isGenerating) {
    return {
      expression: "thinking",
      intensity: 0.8,
      parameter_overrides: {},
      transition_duration_ms: 250,
    };
  }

  const rawEmotion = (emotionType || "neutral").toLowerCase().trim();
  const rawMood = (mood || "neutral").toLowerCase().trim();
  const clampedIntensity = Math.max(0.0, Math.min(1.0, intensity));

  let targetExpr: VisualExpressionType = EMOTION_MAP[rawEmotion] || "neutral";

  // Low-intensity happy presents as gentle smile rather than full joy
  if (rawEmotion === "happy" && clampedIntensity <= 0.5) {
    targetExpr = "smile";
  }

  // Mood bias when emotion is neutral or calm
  if (rawEmotion === "neutral" || rawEmotion === "calm") {
    if (rawMood === "tired") targetExpr = "tired";
    else if (rawMood === "good") targetExpr = "smile";
    else if (rawMood === "low") targetExpr = "sad";
    else if (rawMood === "irritated") targetExpr = "pout";
    else if (rawMood === "focused") targetExpr = "thinking";
  }

  const overrides: Record<string, number> = {};
  if (rawEmotion === "embarrassed") {
    overrides["ParamCheek"] = Number((0.5 + 0.5 * clampedIntensity).toFixed(3));
  } else if (rawEmotion === "excited") {
    overrides["ParamCheek"] = Number((0.4 * clampedIntensity).toFixed(3));
    overrides["ParamEyeLSmile"] = Number((0.8 * clampedIntensity).toFixed(3));
    overrides["ParamEyeRSmile"] = Number((0.8 * clampedIntensity).toFixed(3));
  } else if (rawEmotion === "angry") {
    overrides["ParamBrowLAngle"] = Number((-0.6 * clampedIntensity).toFixed(3));
    overrides["ParamBrowRAngle"] = Number((-0.6 * clampedIntensity).toFixed(3));
  }

  let transitionMs = 300;
  if (targetExpr === "surprise") transitionMs = 150;
  else if (targetExpr === "tired" || targetExpr === "sad") transitionMs = 500;

  return {
    expression: targetExpr,
    intensity: clampedIntensity,
    parameter_overrides: overrides,
    transition_duration_ms: transitionMs,
  };
}

/**
 * Derives VisualMotionCommand from mood and situational flags (speaking / thinking).
 */
export function deriveVisualMotion(
  mood?: string,
  isSpeaking: boolean = false,
  isThinking: boolean = false
): VisualMotionCommand {
  if (isSpeaking) {
    return {
      archetype: "talking_casual",
      priority: 3,
      loop: true,
      fade_in_ms: 250,
      fade_out_ms: 250,
    };
  }

  if (isThinking) {
    return {
      archetype: "thinking_tilt",
      priority: 2,
      loop: true,
      fade_in_ms: 350,
      fade_out_ms: 350,
    };
  }

  const rawMood = (mood || "neutral").toLowerCase().trim();
  const archetype = MOOD_MOTION_MAP[rawMood] || "idle_normal";

  if (archetype === "shake_head") {
    return {
      archetype,
      priority: 2,
      loop: false,
      fade_in_ms: 300,
      fade_out_ms: 400,
    };
  }

  let fadeMs = 500;
  if (rawMood === "tired") fadeMs = 800;
  else if (rawMood === "good") fadeMs = 400;

  return {
    archetype,
    priority: 1,
    loop: true,
    fade_in_ms: fadeMs,
    fade_out_ms: fadeMs,
  };
}

/**
 * Maps a VisualDirectivePayload from the realtime session to VisualExpressionConfig (Phase 13.5).
 *
 * Presentation only (Rule 19 & ADR-024):
 * - Does NOT alter CharacterState or EmotionState.
 * - Provides high-priority situational render directives from the realtime session.
 */
export function mapVisualDirectiveToExpression(
  directive: {
    expression_archetype: string;
    intensity: number;
    transition_duration_ms: number;
  }
): VisualExpressionConfig {
  const archetype = (directive.expression_archetype || "neutral").toLowerCase().trim();
  const validArchetype: VisualExpressionType = (EMOTION_MAP[archetype] as VisualExpressionType) || "neutral";

  return {
    expression: validArchetype,
    intensity: Math.max(0.0, Math.min(1.0, directive.intensity)),
    parameter_overrides: {},
    transition_duration_ms: directive.transition_duration_ms || 250,
  };
}

