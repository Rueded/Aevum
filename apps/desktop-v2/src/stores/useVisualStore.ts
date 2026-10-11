import { create } from "zustand";
import type {
  VisualExpressionConfig,
  VisualMotionCommand,
  LipSyncMouthState,
  RendererState,
} from "../visual/types";

interface VisualStoreState {
  isStageVisible: boolean;
  visualExpression: VisualExpressionConfig;
  visualMotion: VisualMotionCommand;
  lipSyncState: LipSyncMouthState;
  rendererState: RendererState;
  customAvatarUrl: string;
  customLive2dUrl: string;
  selectedPreset: string;

  toggleStageVisible: () => void;
  setStageVisible: (visible: boolean) => void;
  setVisualExpression: (expr: VisualExpressionConfig) => void;
  setVisualMotion: (motion: VisualMotionCommand) => void;
  setLipSyncState: (state: LipSyncMouthState) => void;
  setRendererState: (state: RendererState) => void;
  setCustomAvatarUrl: (url: string) => void;
  setCustomLive2dUrl: (url: string) => void;
  setSelectedPreset: (preset: string) => void;
}

export const useVisualStore = create<VisualStoreState>((set) => ({
  isStageVisible: localStorage.getItem("aevum_visual_stage_visible") !== "false",
  visualExpression: {
    expression: "neutral",
    intensity: 1.0,
    parameter_overrides: {},
    transition_duration_ms: 300,
  },
  visualMotion: {
    archetype: "idle_normal",
    priority: 1,
    loop: true,
    fade_in_ms: 500,
    fade_out_ms: 500,
  },
  lipSyncState: {
    mouth_open_y: 0.0,
    mouth_form: 0.0,
    is_speaking: false,
  },
  rendererState: "uninitialized",
  customAvatarUrl: localStorage.getItem("aevum_custom_avatar_url") || "",
  customLive2dUrl: localStorage.getItem("aevum_custom_live2d_url") || "",
  selectedPreset: localStorage.getItem("aevum_live2d_selected_preset") || "hiyori",

  toggleStageVisible: () => {
    set((state) => {
      const next = !state.isStageVisible;
      localStorage.setItem("aevum_visual_stage_visible", String(next));
      return { isStageVisible: next };
    });
  },

  setStageVisible: (visible: boolean) => {
    localStorage.setItem("aevum_visual_stage_visible", String(visible));
    set({ isStageVisible: visible });
  },

  setVisualExpression: (visualExpression) => set({ visualExpression }),
  setVisualMotion: (visualMotion) => set({ visualMotion }),
  setLipSyncState: (lipSyncState) => set({ lipSyncState }),
  setRendererState: (rendererState) => set({ rendererState }),

  setCustomAvatarUrl: (url: string) => {
    localStorage.setItem("aevum_custom_avatar_url", url);
    set({ customAvatarUrl: url });
  },

  setCustomLive2dUrl: (url: string) => {
    localStorage.setItem("aevum_custom_live2d_url", url);
    set({ customLive2dUrl: url });
  },

  setSelectedPreset: (preset: string) => {
    localStorage.setItem("aevum_live2d_selected_preset", preset);
    set({ selectedPreset: preset });
  },
}));
