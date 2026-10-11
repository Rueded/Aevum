import { create } from "zustand";
import type { CallMode } from "../types";

interface CallStoreState {
  callMode: CallMode;
  activeCallSessionId: string | null;
  activeGenerationId: number;
  partialTranscript: string;
  isMuted: boolean;
  callError: string | null;
  isCompanionSpeaking: boolean;

  setCallMode: (mode: CallMode) => void;
  setActiveCallSessionId: (id: string | null) => void;
  setActiveGenerationId: (id: number) => void;
  setPartialTranscript: (text: string) => void;
  setIsMuted: (muted: boolean) => void;
  toggleMute: () => void;
  setCallError: (error: string | null) => void;
  setIsCompanionSpeaking: (speaking: boolean) => void;
  resetCall: () => void;
}

export const useCallStore = create<CallStoreState>((set) => ({
  callMode: "IDLE",
  activeCallSessionId: null,
  activeGenerationId: 0,
  partialTranscript: "",
  isMuted: false,
  callError: null,
  isCompanionSpeaking: false,

  setCallMode: (callMode) => set({ callMode }),
  setActiveCallSessionId: (activeCallSessionId) => set({ activeCallSessionId }),
  setActiveGenerationId: (activeGenerationId) => set({ activeGenerationId }),
  setPartialTranscript: (partialTranscript) => set({ partialTranscript }),
  setIsMuted: (isMuted) => set({ isMuted }),
  toggleMute: () => set((state) => ({ isMuted: !state.isMuted })),
  setCallError: (callError) => set({ callError }),
  setIsCompanionSpeaking: (isCompanionSpeaking) => set({ isCompanionSpeaking }),
  resetCall: () =>
    set({
      callMode: "IDLE",
      activeCallSessionId: null,
      activeGenerationId: 0,
      partialTranscript: "",
      isMuted: false,
      callError: null,
      isCompanionSpeaking: false,
    }),
}));
