import { create } from "zustand";
import { api } from "../api";
import type {
  CharacterStateResponse,
  RelationshipResponse,
  LifeResponse,
  MemoryItem,
  CharacterDebugResponse,
} from "../types";

interface CharacterStoreState {
  characterState: CharacterStateResponse | null;
  relationship: RelationshipResponse | null;
  life: LifeResponse | null;
  memories: MemoryItem[];
  debugData: CharacterDebugResponse | null;
  isLoading: boolean;

  fetchCharacterState: () => Promise<void>;
  fetchRelationship: () => Promise<void>;
  fetchLife: () => Promise<void>;
  fetchMemories: () => Promise<void>;
  fetchDebug: () => Promise<void>;
  refreshAll: () => Promise<void>;
  deleteMemory: (id: string) => Promise<void>;
}

export const useCharacterStore = create<CharacterStoreState>((set, get) => ({
  characterState: null,
  relationship: null,
  life: null,
  memories: [],
  debugData: null,
  isLoading: false,

  fetchCharacterState: async () => {
    try {
      const state = await api.getCharacterState();
      set({ characterState: state });
    } catch (e) {
      console.error("Failed to fetch character state", e);
    }
  },

  fetchRelationship: async () => {
    try {
      const rel = await api.getRelationship();
      set({ relationship: rel });
    } catch (e) {
      console.error("Failed to fetch relationship", e);
    }
  },

  fetchLife: async () => {
    try {
      const life = await api.getLife();
      set({ life });
    } catch (e) {
      console.error("Failed to fetch life", e);
    }
  },

  fetchMemories: async () => {
    try {
      const memories = await api.getMemories();
      set({ memories });
    } catch (e) {
      console.error("Failed to fetch memories", e);
    }
  },

  fetchDebug: async () => {
    try {
      const debugData = await api.getDebug();
      set({ debugData });
    } catch (e) {
      console.error("Failed to fetch debug data", e);
    }
  },

  refreshAll: async () => {
    set({ isLoading: true });
    try {
      await Promise.allSettled([
        get().fetchCharacterState(),
        get().fetchRelationship(),
        get().fetchLife(),
        get().fetchMemories(),
        get().fetchDebug(),
      ]);
    } finally {
      set({ isLoading: false });
    }
  },

  deleteMemory: async (id: string) => {
    await api.deleteMemory(id);
    set((state) => ({
      memories: state.memories.filter((m) => m.id !== id),
      debugData: state.debugData
        ? { ...state.debugData, total_memories: Math.max(0, state.debugData.total_memories - 1) }
        : null,
    }));
  },
}));
