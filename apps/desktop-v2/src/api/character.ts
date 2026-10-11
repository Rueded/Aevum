import { fetchJson } from "./client";
import type {
  CharacterStateResponse,
  CharacterStateUpdateRequest,
  RelationshipResponse,
  RelationshipUpdateRequest,
  LifeResponse,
  MemoryItem,
  CharacterDebugResponse,
  LongitudinalMemoryResponse,
} from "../types";

export const characterApi = {
  getState: (): Promise<CharacterStateResponse> => {
    return fetchJson<CharacterStateResponse>("/character/state");
  },

  updateState: (payload: CharacterStateUpdateRequest): Promise<CharacterStateResponse> => {
    return fetchJson<CharacterStateResponse>("/character/state", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  getRelationship: (): Promise<RelationshipResponse> => {
    return fetchJson<RelationshipResponse>("/character/relationship");
  },

  updateRelationship: (payload: RelationshipUpdateRequest): Promise<RelationshipResponse> => {
    return fetchJson<RelationshipResponse>("/character/relationship", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  getLife: (): Promise<LifeResponse> => {
    return fetchJson<LifeResponse>("/character/life");
  },

  getMemories: (): Promise<MemoryItem[]> => {
    return fetchJson<MemoryItem[]>("/character/memories");
  },

  deleteMemory: (memoryId: string): Promise<{ status: string; id: string }> => {
    return fetchJson<{ status: string; id: string }>(`/character/memories/${encodeURIComponent(memoryId)}`, {
      method: "DELETE",
    });
  },

  getDebug: (): Promise<CharacterDebugResponse> => {
    return fetchJson<CharacterDebugResponse>("/character/debug");
  },

  getLongitudinalMemory: (): Promise<LongitudinalMemoryResponse> => {
    return fetchJson<LongitudinalMemoryResponse>("/character/longitudinal-memory");
  },

  setSituation: (payload: {
    activity: string;
    location: string;
    duration_hours?: number;
    status?: string;
  }): Promise<{ success: boolean; activity: string; location: string; status: string; expires_at: string }> => {
    return fetchJson("/character/life/situation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },
};
