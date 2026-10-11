import { create } from "zustand";
import { api } from "../api";
import type { DesktopSettings, DesktopSettingsUpdate } from "../types";

interface SettingsStoreState {
  settings: DesktopSettings | null;
  isLoading: boolean;
  bubbleMode: "multi" | "single";
  emojiRenderingEnabled: boolean;
  showEmojiLabel: boolean;
  useStickers: boolean;
  stickerStandaloneLine: boolean;
  useKaomoji: boolean;
  voiceConsentGranted: boolean;
  autoPlayVoice: boolean;

  fetchSettings: (characterId?: string) => Promise<void>;
  updateSettings: (updates: DesktopSettingsUpdate, characterId?: string) => Promise<void>;
  setBubbleMode: (mode: "multi" | "single") => void;
  setEmojiRenderingEnabled: (enabled: boolean) => void;
  setShowEmojiLabel: (show: boolean) => void;
  setUseStickers: (use: boolean) => void;
  setStickerStandaloneLine: (standalone: boolean) => void;
  setUseKaomoji: (use: boolean) => void;
  setVoiceConsentGranted: (granted: boolean) => void;
  setAutoPlayVoice: (autoplay: boolean) => void;
}

export const useSettingsStore = create<SettingsStoreState>((set) => ({
  settings: null,
  isLoading: false,
  bubbleMode: (localStorage.getItem("aevum_bubble_mode") as "multi" | "single") || "multi",
  emojiRenderingEnabled: localStorage.getItem("aevum_emoji_rendering") !== "false",
  showEmojiLabel: localStorage.getItem("aevum_show_emoji_label") !== "false",
  useStickers: localStorage.getItem("aevum_use_stickers") !== "false",
  stickerStandaloneLine: localStorage.getItem("aevum_sticker_standalone_line") === "true",
  useKaomoji: localStorage.getItem("aevum_use_kaomoji") !== "false",
  voiceConsentGranted: localStorage.getItem("aevum_voice_consent_granted") === "true",
  autoPlayVoice: localStorage.getItem("aevum_voice_autoplay") !== "false",

  fetchSettings: async (characterId = "aevum") => {
    set({ isLoading: true });
    try {
      const data = await api.getDesktopSettings(characterId);
      set({ settings: data });
    } catch (e) {
      console.error("Failed to fetch desktop settings", e);
    } finally {
      set({ isLoading: false });
    }
  },

  updateSettings: async (updates: DesktopSettingsUpdate, characterId = "aevum") => {
    try {
      const updated = await api.updateDesktopSettings(updates, characterId);
      set({ settings: updated });
    } catch (e) {
      console.error("Failed to update desktop settings", e);
      throw e;
    }
  },

  setBubbleMode: (mode: "multi" | "single") => {
    localStorage.setItem("aevum_bubble_mode", mode);
    set({ bubbleMode: mode });
  },

  setEmojiRenderingEnabled: (enabled: boolean) => {
    localStorage.setItem("aevum_emoji_rendering", String(enabled));
    set({ emojiRenderingEnabled: enabled });
  },

  setShowEmojiLabel: (show: boolean) => {
    localStorage.setItem("aevum_show_emoji_label", String(show));
    set({ showEmojiLabel: show });
  },

  setUseStickers: (use: boolean) => {
    localStorage.setItem("aevum_use_stickers", String(use));
    set({ useStickers: use });
  },

  setStickerStandaloneLine: (standalone: boolean) => {
    localStorage.setItem("aevum_sticker_standalone_line", String(standalone));
    set({ stickerStandaloneLine: standalone });
  },

  setUseKaomoji: (use: boolean) => {
    localStorage.setItem("aevum_use_kaomoji", String(use));
    set({ useKaomoji: use });
  },

  setVoiceConsentGranted: (granted: boolean) => {
    localStorage.setItem("aevum_voice_consent_granted", String(granted));
    set({ voiceConsentGranted: granted });
  },

  setAutoPlayVoice: (autoplay: boolean) => {
    localStorage.setItem("aevum_voice_autoplay", String(autoplay));
    set({ autoPlayVoice: autoplay });
  },
}));
