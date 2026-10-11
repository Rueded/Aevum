import { create } from "zustand";
import { api } from "../api";
import type { HealthData } from "../types";

interface HealthState {
  health: HealthData | null;
  isBackendOnline: boolean;
  backendCrashed: boolean;
  backendCrashError: string | null;
  fetchHealth: () => Promise<void>;
  setBackendCrashed: (crashed: boolean, error?: string) => void;
}

export const useHealthStore = create<HealthState>((set) => ({
  health: null,
  isBackendOnline: false,
  backendCrashed: false,
  backendCrashError: null,

  fetchHealth: async () => {
    try {
      const data = await api.getHealth();
      set({ health: data, isBackendOnline: data.status === "ok" || data.status === "healthy" });
    } catch {
      set({ isBackendOnline: false });
    }
  },

  setBackendCrashed: (crashed: boolean, error?: string) => {
    set({ backendCrashed: crashed, backendCrashError: error || null });
  },
}));
