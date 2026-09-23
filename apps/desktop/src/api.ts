import {
  CharacterDebugResponse,
  CharacterStateResponse,
  ConversationDetail,
  HealthData,
  FactMutationResponse,
  LifeResponse,
  MemoryItem,
  MessageCreateResponse,
  ProfileResponse,
  RelationshipResponse,
  UpdateCoreRequest,
  DesktopSettings,
  DesktopSettingsUpdate,
  SetDNDPayload,
  NotificationHistoryItem,
  NotificationItem,
  HeartbeatPayload,
  HeartbeatResponse,
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

  getProfile: (): Promise<ProfileResponse> => {
    return fetchJson<ProfileResponse>("/character/profile");
  },

  updateCoreProfile: (payload: UpdateCoreRequest): Promise<ProfileResponse> => {
    return fetchJson<ProfileResponse>("/character/profile/core", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  lockFact: (factKey: string): Promise<FactMutationResponse> => {
    return fetchJson<FactMutationResponse>(`/character/profile/core/${encodeURIComponent(factKey)}/lock`, {
      method: "POST",
    });
  },

  unlockFact: (factKey: string): Promise<FactMutationResponse> => {
    return fetchJson<FactMutationResponse>(`/character/profile/core/${encodeURIComponent(factKey)}/unlock`, {
      method: "POST",
    });
  },

  confirmFact: (factKey: string): Promise<FactMutationResponse> => {
    return fetchJson<FactMutationResponse>(`/character/profile/core/${encodeURIComponent(factKey)}/confirm`, {
      method: "POST",
    });
  },

  rejectFact: (factKey: string): Promise<FactMutationResponse> => {
    return fetchJson<FactMutationResponse>(`/character/profile/core/${encodeURIComponent(factKey)}/reject`, {
      method: "POST",
    });
  },

  deleteFact: (factKey: string): Promise<FactMutationResponse> => {
    return fetchJson<FactMutationResponse>(`/character/profile/core/${encodeURIComponent(factKey)}`, {
      method: "DELETE",
    });
  },

  // ===========================================================================
  // Phase 8: Desktop Integration & Settings API
  // ===========================================================================

  getDesktopSettings: (characterId: string = "aevum"): Promise<DesktopSettings> => {
    return fetchJson<DesktopSettings>(`/desktop/settings?character_id=${encodeURIComponent(characterId)}`);
  },

  updateDesktopSettings: (updates: DesktopSettingsUpdate, characterId: string = "aevum"): Promise<DesktopSettings> => {
    return fetchJson<DesktopSettings>(`/desktop/settings?character_id=${encodeURIComponent(characterId)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    });
  },

  setDND: (payload: SetDNDPayload, characterId: string = "aevum"): Promise<{ status: string; dnd_until: string | null }> => {
    return fetchJson<{ status: string; dnd_until: string | null }>(`/desktop/settings/dnd?character_id=${encodeURIComponent(characterId)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  sendHeartbeat: (payload: HeartbeatPayload, characterId: string = "aevum"): Promise<HeartbeatResponse> => {
    return fetchJson<HeartbeatResponse>(`/desktop/heartbeat?character_id=${encodeURIComponent(characterId)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  getNotificationHistory: (characterId: string = "aevum", limit: number = 50): Promise<NotificationHistoryItem[]> => {
    return fetchJson<NotificationHistoryItem[]>(`/desktop/notifications/history?character_id=${encodeURIComponent(characterId)}&limit=${limit}`);
  },

  getPendingNotifications: (characterId: string = "aevum"): Promise<NotificationItem[]> => {
    return fetchJson<NotificationItem[]>(`/desktop/notifications/pending?character_id=${encodeURIComponent(characterId)}`);
  },

  getNotificationById: (id: string, characterId?: string): Promise<NotificationItem> => {
    const query = characterId ? `?character_id=${encodeURIComponent(characterId)}` : "";
    return fetchJson<NotificationItem>(`/desktop/notifications/${encodeURIComponent(id)}${query}`);
  },

  claimNotification: (
    id: string,
    workerId: string,
    characterId: string = "aevum",
    leaseTimeoutSeconds?: number
  ): Promise<{ status: string; claimed: boolean; notification_id: string }> => {
    return fetchJson<{ status: string; claimed: boolean; notification_id: string }>(`/desktop/notifications/${encodeURIComponent(id)}/claim`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        worker_id: workerId,
        character_id: characterId,
        lease_timeout_seconds: leaseTimeoutSeconds,
      }),
    });
  },

  completeNotification: (
    id: string,
    workerId: string,
    characterId: string = "aevum"
  ): Promise<{ status: string; completed: boolean; notification_id: string }> => {
    return fetchJson<{ status: string; completed: boolean; notification_id: string }>(`/desktop/notifications/${encodeURIComponent(id)}/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        worker_id: workerId,
        character_id: characterId,
      }),
    });
  },

  releaseNotification: (
    id: string,
    workerId: string,
    characterId: string = "aevum"
  ): Promise<{ status: string; released: boolean; notification_id: string }> => {
    return fetchJson<{ status: string; released: boolean; notification_id: string }>(`/desktop/notifications/${encodeURIComponent(id)}/release`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        worker_id: workerId,
        character_id: characterId,
      }),
    });
  },

  interactNotification: (
    id: string,
    action: "CLICKED" | "DISMISSED",
    characterId: string = "aevum"
  ): Promise<{ status: string; interacted: boolean; notification_id: string; conversation_message_id: string }> => {
    return fetchJson<{ status: string; interacted: boolean; notification_id: string; conversation_message_id: string }>(
      `/desktop/notifications/${encodeURIComponent(id)}/interact`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action,
          character_id: characterId,
        }),
      }
    );
  },
};
