/**
 * Presentation Track — Handcrafted Fixtures (Cases A to G)
 * 
 * Static test fixtures verifying that the frontend can render rich expressive
 * differences without flattening them into a single monolithic string,
 * and without touching core backend LLM prompts or state machines.
 */

import { PresentationEnvelope } from "./contracts";

export const PRESENTATION_FIXTURES: Record<string, PresentationEnvelope> = {
  // Case A: Pure Text Only (Standard Baseline)
  caseA_textOnly: {
    envelope_id: "env_case_a_001",
    case_name: "Case A: TEXT Only",
    description: "Standard natural dialogue turn with pure textual substance.",
    manifestation_state: "MANIFESTED",
    visual_density: "normal",
    bubbles: [
      {
        id: "b_case_a_1",
        timing_affordance: "immediate",
        density: "normal",
        segments: [
          {
            kind: "TEXT",
            raw: "明天下午要去图书馆把借的那两本书还掉，顺便找找看有没有新的插画集。",
          },
        ],
      },
    ],
    timing: {
      pre_response_delay_ms: 300,
      default_inter_bubble_ms: 0,
    },
    raw_fallback_text: "明天下午要去图书馆把借的那两本书还掉，顺便找找看有没有新的插画集。",
  },

  // Case B: Text + Kaomoji (Playful Teasing with Micro-Emoticon)
  caseB_textKaomoji: {
    envelope_id: "env_case_b_002",
    case_name: "Case B: TEXT + KAOMOJI",
    description: "Teasing affective posture paired with a paralinguistic kaomoji accent.",
    manifestation_state: "MANIFESTED",
    visual_density: "normal",
    bubbles: [
      {
        id: "b_case_b_1",
        timing_affordance: "immediate",
        density: "normal",
        segments: [
          {
            kind: "TEXT",
            raw: "忘了？记性这么差～",
          },
          {
            kind: "KAOMOJI",
            raw: "(｀へ´)",
            metadata: {
              kaomoji_mood: "playful_pout",
              alt_text: "playful pout",
            },
          },
        ],
      },
    ],
    timing: {
      pre_response_delay_ms: 250,
      default_inter_bubble_ms: 0,
    },
    raw_fallback_text: "忘了？记性这么差～(｀へ´)",
  },

  // Case C: Text + Emoji (Informal Camaraderie)
  caseC_textEmoji: {
    envelope_id: "env_case_c_003",
    case_name: "Case C: TEXT + EMOJI",
    description: "Warm informal laugh accompanied by a natural emoji glyph.",
    manifestation_state: "MANIFESTED",
    visual_density: "normal",
    bubbles: [
      {
        id: "b_case_c_1",
        timing_affordance: "immediate",
        density: "normal",
        segments: [
          {
            kind: "TEXT",
            raw: "哈哈，原来被你发现了",
          },
          {
            kind: "EMOJI",
            raw: "😜",
            metadata: {
              alt_text: "winking tongue",
            },
          },
        ],
      },
    ],
    timing: {
      pre_response_delay_ms: 200,
      default_inter_bubble_ms: 0,
    },
    raw_fallback_text: "哈哈，原来被你发现了😜",
  },

  // Case D: 2 Bubbles with Short Inter-Bubble Interval (Natural Speech Rhythm)
  caseD_multiBubble: {
    envelope_id: "env_case_d_004",
    case_name: "Case D: 2 Bubbles + Short Interval",
    description: "Organic two-burst cadence: an initial reaction followed by thought completion.",
    manifestation_state: "MANIFESTED",
    visual_density: "normal",
    // Note: The 600ms delay is an explicit handcrafted demonstration parameter for this fixture.
    // It is NOT a universal timing rule; unspecified timing defaults to immediate presentation.
    bubbles: [
      {
        id: "b_case_d_1",
        timing_affordance: "short_pause",
        inter_bubble_delay_ms: 600,
        density: "normal",
        segments: [
          {
            kind: "TEXT",
            raw: "等等……",
          },
        ],
      },
      {
        id: "b_case_d_2",
        timing_affordance: "immediate",
        density: "normal",
        segments: [
          {
            kind: "TEXT",
            raw: "我刚刚好像看错书名了，以为是那本蓝皮的。",
          },
        ],
      },
    ],
    timing: {
      pre_response_delay_ms: 300,
      default_inter_bubble_ms: 600,
    },
    raw_fallback_text: "等等……\n我刚刚好像看错书名了，以为是那本蓝皮的。",
  },

  // Case E: Text + Sticker (Visual Expressive Asset)
  caseE_textSticker: {
    envelope_id: "env_case_e_005",
    case_name: "Case E: TEXT + STICKER",
    description: "Conversational line paired with a companion sticker graphic.",
    manifestation_state: "MANIFESTED",
    visual_density: "normal",
    bubbles: [
      {
        id: "b_case_e_1",
        timing_affordance: "short_pause",
        inter_bubble_delay_ms: 400,
        density: "normal",
        segments: [
          {
            kind: "TEXT",
            raw: "先喝口热茶缓一缓～",
          },
        ],
      },
      {
        id: "b_case_e_2",
        timing_affordance: "immediate",
        density: "normal",
        segments: [
          {
            kind: "STICKER",
            raw: "[🍵 Aevum Tea Sip]",
            metadata: {
              sticker_id: "stk_tea_sip_01",
              sticker_url: "sticker_tea",
              alt_text: "Aevum taking a warm sip of tea",
            },
          },
        ],
      },
    ],
    timing: {
      pre_response_delay_ms: 300,
      default_inter_bubble_ms: 400,
    },
    raw_fallback_text: "先喝口热茶缓一缓～\n[🍵 Aevum Tea Sip]",
  },

  // Case F: ZERO_EXPANSION Minimal Manifestation (Comfortable Rest Beat)
  caseF_zeroExpansion: {
    envelope_id: "env_case_f_006",
    case_name: "Case F: ZERO_EXPANSION",
    description: "Terse minimal reaction bubble using compact visual density without conversational pressure to expand.",
    manifestation_state: "MINIMAL_MANIFESTED",
    visual_density: "compact",
    bubbles: [
      {
        id: "b_case_f_1",
        timing_affordance: "immediate",
        density: "compact",
        emphasis: "subtle",
        segments: [
          {
            kind: "TEXT",
            raw: "笑死",
          },
        ],
      },
    ],
    timing: {
      pre_response_delay_ms: 150,
      default_inter_bubble_ms: 0,
    },
    raw_fallback_text: "笑死",
  },

  // Case G: Pure Design Preview for Future Zero-Message Manifestation
  caseG_noMessagePreview: {
    envelope_id: "env_case_g_007",
    case_name: "Case G: NO_MESSAGE_DESIGN_PREVIEW",
    description:
      "Design preview of future zero-message state. NOT an actual assistant message; current REST API requires returning 1 message.",
    manifestation_state: "NO_MESSAGE_DESIGN_PREVIEW",
    visual_density: "normal",
    bubbles: [],
    timing: {
      pre_response_delay_ms: 0,
      default_inter_bubble_ms: 0,
    },
    raw_fallback_text: "（静默未言 · 留白）",
  },
};
