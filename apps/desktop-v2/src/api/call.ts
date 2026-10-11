import { fetchJson, getBackendBaseUrl } from "./client";
import type { CallSessionResponse } from "../types";

export const callApi = {
  createSession: (conversationId: string, sessionId?: string): Promise<CallSessionResponse> => {
    return fetchJson<CallSessionResponse>("/api/v1/call/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: conversationId,
        session_id: sessionId || null,
      }),
    });
  },

  getSession: (sessionId: string): Promise<CallSessionResponse> => {
    return fetchJson<CallSessionResponse>(`/api/v1/call/sessions/${encodeURIComponent(sessionId)}`);
  },

  getStreamWsUrl: (sessionId: string, conversationId?: string): string => {
    const wsBase = getBackendBaseUrl().replace(/^http/, "ws");
    const query = conversationId ? `?conversation_id=${encodeURIComponent(conversationId)}` : "";
    return `${wsBase}/api/v1/call/stream/${encodeURIComponent(sessionId)}${query}`;
  },
};
