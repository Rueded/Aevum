import { fetchJson } from "./client";
import type {
  ConversationListItem,
  ConversationDetail,
  MessageCreateResponse,
  VoiceMessageCreate,
  VoiceMessageResponse,
} from "../types";

export const conversationsApi = {
  create: (): Promise<{ id: string; created_at: string; updated_at: string }> => {
    return fetchJson<{ id: string; created_at: string; updated_at: string }>("/conversations", {
      method: "POST",
    });
  },

  list: (limit: number = 50): Promise<ConversationListItem[]> => {
    return fetchJson<ConversationListItem[]>(`/conversations?limit=${limit}`);
  },

  delete: (conversationId: string): Promise<void> => {
    return fetchJson<void>(`/conversations/${encodeURIComponent(conversationId)}`, {
      method: "DELETE",
    });
  },

  get: (conversationId: string): Promise<ConversationDetail> => {
    return fetchJson<ConversationDetail>(`/conversations/${encodeURIComponent(conversationId)}`);
  },

  sendMessage: (conversationId: string, content: string): Promise<MessageCreateResponse> => {
    return fetchJson<MessageCreateResponse>(`/conversations/${encodeURIComponent(conversationId)}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role: "user", content }),
    });
  },

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

  checkIdleNudge: (
    conversationId: string,
    idleThreshold: number = 75
  ): Promise<{ nudged: boolean; message?: MessageCreateResponse["assistant_response"] }> => {
    return fetchJson<{ nudged: boolean; message?: MessageCreateResponse["assistant_response"] }>(
      `/conversations/${encodeURIComponent(conversationId)}/check-idle?idle_threshold=${idleThreshold}`,
      {
        method: "POST",
      }
    );
  },
};
