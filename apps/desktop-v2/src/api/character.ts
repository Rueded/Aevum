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
  CompanionOverviewResponse,
  CreateCompanionRequest,
} from "../types";

export const characterApi = {
  getState: (characterId?: string): Promise<CharacterStateResponse> => {
    const query = characterId ? `?character_id=${encodeURIComponent(characterId)}` : "";
    return fetchJson<CharacterStateResponse>(`/character/state${query}`);
  },

  updateState: (payload: CharacterStateUpdateRequest): Promise<CharacterStateResponse> => {
    return fetchJson<CharacterStateResponse>("/character/state", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  getRelationship: (characterId?: string): Promise<RelationshipResponse> => {
    const query = characterId ? `?character_id=${encodeURIComponent(characterId)}` : "";
    return fetchJson<RelationshipResponse>(`/character/relationship${query}`);
  },

  updateRelationship: (payload: RelationshipUpdateRequest): Promise<RelationshipResponse> => {
    return fetchJson<RelationshipResponse>(`/character/relationship`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  getLife: (characterId?: string): Promise<LifeResponse> => {
    const query = characterId ? `?character_id=${encodeURIComponent(characterId)}` : "";
    return fetchJson<LifeResponse>(`/character/life${query}`);
  },

  getMemories: (characterId?: string): Promise<MemoryItem[]> => {
    const query = characterId ? `?character_id=${encodeURIComponent(characterId)}` : "";
    return fetchJson<MemoryItem[]>(`/character/memories${query}`);
  },

  getAllCompanions: (): Promise<CompanionOverviewResponse> => {
    return fetchJson<CompanionOverviewResponse>("/character/all");
  },

  switchCompanion: (characterId: string): Promise<CompanionOverviewResponse> => {
    return fetchJson<CompanionOverviewResponse>(`/character/switch/${encodeURIComponent(characterId)}`, {
      method: "POST",
    });
  },

  createNewCompanion: (payload: CreateCompanionRequest): Promise<any> => {
    return fetchJson<any>("/character/create-new", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
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

