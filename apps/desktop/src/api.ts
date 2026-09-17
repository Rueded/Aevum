import {
  CharacterDebugResponse,
  CharacterStateResponse,
  ConversationDetail,
  HealthData,
  LifeResponse,
  MemoryItem,
  MessageCreateResponse,
  RelationshipResponse,
} from "./types";

export const BACKEND_BASE_URL = "http://127.0.0.1:8000";

async function fetchJson<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${BACKEND_BASE_URL}${endpoint}`;
  const response = await fetch(url, options);

  if (!response.ok) {
    let errorDetail = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const errorJson = await response.json();
      if (errorJson && errorJson.detail) {
        errorDetail = errorJson.detail;
      }
    } catch {
      // Ignore json parse error and use statusText
    }
    throw new Error(errorDetail);
  }

  return (await response.json()) as T;
}

export const api = {
  getHealth: (): Promise<HealthData> => {
    return fetchJson<HealthData>("/health");
  },

  createConversation: (): Promise<{ id: string; created_at: string; updated_at: string }> => {
    return fetchJson<{ id: string; created_at: string; updated_at: string }>("/conversations", {
      method: "POST",
    });
  },

  getConversation: (conversationId: string): Promise<ConversationDetail> => {
    return fetchJson<ConversationDetail>(`/conversations/${conversationId}`);
  },

  sendMessage: (conversationId: string, content: string): Promise<MessageCreateResponse> => {
    return fetchJson<MessageCreateResponse>(`/conversations/${conversationId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role: "user", content }),
    });
  },

  getCharacterState: (): Promise<CharacterStateResponse> => {
    return fetchJson<CharacterStateResponse>("/character/state");
  },

  getRelationship: (): Promise<RelationshipResponse> => {
    return fetchJson<RelationshipResponse>("/character/relationship");
  },

  getLife: (): Promise<LifeResponse> => {
    return fetchJson<LifeResponse>("/character/life");
  },

  getMemories: (): Promise<MemoryItem[]> => {
    return fetchJson<MemoryItem[]>("/character/memories");
  },

  deleteMemory: (memoryId: string): Promise<{ status: string; id: string }> => {
    return fetchJson<{ status: string; id: string }>(`/character/memories/${memoryId}`, {
      method: "DELETE",
    });
  },

  getDebug: (): Promise<CharacterDebugResponse> => {
    return fetchJson<CharacterDebugResponse>("/character/debug");
  },
};
