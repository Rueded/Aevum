/**
 * Presentation Track — Expression & Rendering Contracts
 * 
 * Defines the presentation layer data structures separating:
 * "What Aevum decided to express" -> Presentation Contract -> "How Frontend Renders It"
 * 
 * Constitutional Boundaries:
 * - Pure presentation structures, NOT core cognitive state.
 * - Presentation != Who Aevum Is (State != Manifestation).
 * - "Can be rendered this way" != "Must speak this way".
 * - Zero LLM prompts, zero heuristic engines, zero orchestrator bloat.
 */

export type ExpressionResourceKind =
  | "TEXT"
  | "EMOJI"
  | "KAOMOJI"
  | "PUNCTUATION"
  | "STRETCHED_VOWEL"
  | "STICKER"
  | "GIF_MEME";

export type TimingAffordance =
  | "immediate"
  | "short_pause"
  | "conversational_delay";

/**
 * Manifestation State:
 * Distinguishes how the presentation envelope should visually manifest.
 * 
 * Boundary Note:
 * NO_MESSAGE_DESIGN_PREVIEW is purely a frontend design preview showing how
 * the UI might gracefully represent an empty turn in the future.
 * It is NOT an assistant message, and NOT evidence of zero-message REST API implementation.
 */
export type ManifestationState =
  | "MANIFESTED"                 // Normal dialogue turn with visible bubbles
  | "MINIMAL_MANIFESTED"         // Terse reaction rendered with compact density styling
  | "NO_MESSAGE_DESIGN_PREVIEW"; // Pure design preview of future zero-message state

export interface BubbleSegment {
  kind: ExpressionResourceKind;
  raw: string;
  metadata?: {
    sticker_id?: string;
    sticker_url?: string;
    kaomoji_mood?: string;
    alt_text?: string;
  };
}

export interface PresentationBubble {
  id: string;
  segments: BubbleSegment[];
  timing_affordance?: TimingAffordance;
  inter_bubble_delay_ms?: number;
  emphasis?: "subtle" | "normal" | "highlight";
  /**
   * Pure visual density styling.
   * "compact" renders minimal padding/fit-content.
   * Renderer consumes this purely as a layout style without inferring upstream character motivations.
   */
  density?: "compact" | "normal";
}

export interface PresentationEnvelope {
  envelope_id: string;
  case_name: string;
  description: string;
  manifestation_state: ManifestationState;
  /**
   * Pure visual layout density hint across the envelope.
   */
  visual_density?: "compact" | "normal";
  bubbles: PresentationBubble[];
  /**
   * Explicit presentation timing configuration.
   * When missing or 0, rendering must be immediate without fallback delays.
   */
  timing?: {
    pre_response_delay_ms?: number;
    default_inter_bubble_ms?: number;
  };
  raw_fallback_text: string;
}

