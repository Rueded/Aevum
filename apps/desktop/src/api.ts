import {
  CharacterDebugResponse,
  CharacterStateResponse,
  ConversationDetail,
  ConversationListItem,
  HealthData,
  FactMutationResponse,
  LifeResponse,
  MemoryItem,
  MessageCreateResponse,
  ProfileResponse,
  RelationshipResponse,
  RelationshipUpdateRequest,
  UpdateCoreRequest,
  DesktopSettings,
  DesktopSettingsUpdate,
  SetDNDPayload,
  NotificationHistoryItem,
  NotificationItem,
  HeartbeatPayload,
  HeartbeatResponse,
  VoiceMessageCreate,
  VoiceMessageResponse,
  VoiceTTSRequest,
  VoiceTTSResponse,
  VoiceSTTRequest,
  VoiceSTTResponse,
  LongitudinalMemoryResponse,
  CallSessionResponse,
  CharacterBlueprintResponse,
  CharacterCreationPayload,
  CharacterCreationResponse,
  GenesisPresetsResponse,
  BlueprintUpdateRequest,
  ResolveLocalModelResponse,
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
        if (typeof errorJson.detail === "string") {
          errorDetail = errorJson.detail;
        } else if (Array.isArray(errorJson.detail)) {
          errorDetail = errorJson.detail
            .map((d: any) => `${d.loc ? d.loc.slice(1).join(".") : "field"}: ${d.msg}`)
            .join("; ");
        } else {
          errorDetail = JSON.stringify(errorJson.detail);
        }
      }
    } catch {
      // Ignore json parse error and use statusText
    }
    throw new Error(errorDetail);
  }

  if (response.status === 204 || response.headers.get("content-length") === "0") {
    return undefined as unknown as T;
  }

  const text = await response.text();
  if (!text || !text.trim()) {
    return undefined as unknown as T;
  }

  try {
    return JSON.parse(text) as T;
  } catch {
    return text as unknown as T;
  }
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

  getConversations: (limit: number = 50): Promise<ConversationListItem[]> => {
    return fetchJson<ConversationListItem[]>(`/conversations?limit=${limit}`);
  },

  deleteConversation: (conversationId: string): Promise<void> => {
    return fetchJson<void>(`/conversations/${encodeURIComponent(conversationId)}`, {
      method: "DELETE",
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

  updateCharacterState: (payload: {
    mood?: string;
    emotion_type?: string;
    intensity?: number;
    energy?: number;
    stress?: number;
    social_energy?: number;
    current_activity?: string;
    current_location?: string;
  }): Promise<CharacterStateResponse> => {
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

  triggerProactiveTest: (
    characterId: string = "aevum",
    conversationId?: string
  ): Promise<{ status: string; notification_id: string; title: string; body: string; conversation_message_id: string }> => {
    const query = conversationId
      ? `?character_id=${encodeURIComponent(characterId)}&conversation_id=${encodeURIComponent(conversationId)}`
      : `?character_id=${encodeURIComponent(characterId)}`;
    return fetchJson<{ status: string; notification_id: string; title: string; body: string; conversation_message_id: string }>(
      `/desktop/proactive/trigger-test${query}`,
      { method: "POST" }
    );
  },

  // ===========================================================================
  // Phase 10: Voice & Audio API
  // ===========================================================================

  sendVoiceMessage: (
    conversationId: string,
    payload: VoiceMessageCreate
  ): Promise<VoiceMessageResponse> => {
    return fetchJson<VoiceMessageResponse>(`/conversations/${encodeURIComponent(conversationId)}/voice-messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  transcribeVoice: (payload: VoiceSTTRequest): Promise<VoiceSTTResponse> => {
    return fetchJson<VoiceSTTResponse>("/voice/stt", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  synthesizeVoice: (payload: VoiceTTSRequest): Promise<VoiceTTSResponse> => {
    return fetchJson<VoiceTTSResponse>("/voice/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  getCachedAudioUrl: (cacheKey: string): string => {
    return `${BACKEND_BASE_URL}/voice/audio/${encodeURIComponent(cacheKey)}`;
  },

  getLongitudinalMemory: (): Promise<LongitudinalMemoryResponse> => {
    return fetchJson<LongitudinalMemoryResponse>("/character/longitudinal-memory");
  },

  // ===========================================================================
  // Phase 13: Realtime Voice Call & Stream API
  // ===========================================================================

  createCallSession: (conversationId: string, sessionId?: string): Promise<CallSessionResponse> => {
    return fetchJson<CallSessionResponse>("/api/v1/call/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: conversationId,
        session_id: sessionId || null,
      }),
    });
  },

  getCallSession: (sessionId: string): Promise<CallSessionResponse> => {
    return fetchJson<CallSessionResponse>(`/api/v1/call/sessions/${encodeURIComponent(sessionId)}`);
  },

  getCallStreamWsUrl: (sessionId: string, conversationId?: string): string => {
    const wsBase = BACKEND_BASE_URL.replace(/^http/, "ws");
    const query = conversationId ? `?conversation_id=${encodeURIComponent(conversationId)}` : "";
    return `${wsBase}/api/v1/call/stream/${encodeURIComponent(sessionId)}${query}`;
  },

  // ===========================================================================
  // Phase 17: Character Genesis & Blueprint API
  // ===========================================================================

  getGenesisPresets: (): Promise<GenesisPresetsResponse> => {
    return fetchJson<GenesisPresetsResponse>("/character/genesis/presets");
  },

  createGenesis: (payload: CharacterCreationPayload): Promise<CharacterCreationResponse> => {
    return fetchJson<CharacterCreationResponse>("/character/genesis", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  aiGenerateGenesis: (prompt: string): Promise<CharacterCreationPayload> => {
    return fetchJson<CharacterCreationPayload>("/character/genesis/ai-generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });
  },

  getBlueprint: (characterId: string = "aevum"): Promise<CharacterBlueprintResponse> => {
    return fetchJson<CharacterBlueprintResponse>(`/character/blueprint?character_id=${encodeURIComponent(characterId)}`);
  },

  updateBlueprint: (
    payload: BlueprintUpdateRequest,
    characterId: string = "aevum"
  ): Promise<CharacterBlueprintResponse> => {
    return fetchJson<CharacterBlueprintResponse>(`/character/blueprint?character_id=${encodeURIComponent(characterId)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  resolveLocalModel: (filePath: string): Promise<ResolveLocalModelResponse> => {
    return fetchJson<ResolveLocalModelResponse>("/character/avatar/resolve-local-model", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_path: filePath }),
    });
  },

  uploadLive2DZip: async (file: File): Promise<ResolveLocalModelResponse> => {
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch(`${BACKEND_BASE_URL}/character/avatar/upload-live2d-zip`, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      let errorDetail = `HTTP ${response.status}: ${response.statusText}`;
      try {
        const errorJson = await response.json();
        if (errorJson && typeof errorJson === "object" && "detail" in errorJson) {
          errorDetail = String(errorJson.detail);
        }
      } catch {
        // Fall back to HTTP status
      }
      throw new Error(errorDetail);
    }
    return response.json();
  },
};


