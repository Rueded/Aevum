import { fetchJson } from "./client";
import type {
  DesktopSettings,
  DesktopSettingsUpdate,
  SetDNDPayload,
  HeartbeatPayload,
  HeartbeatResponse,
  NotificationHistoryItem,
  NotificationItem,
} from "../types";

export const desktopApi = {
  getSettings: (characterId: string = "aevum"): Promise<DesktopSettings> => {
    return fetchJson<DesktopSettings>(`/desktop/settings?character_id=${encodeURIComponent(characterId)}`);
  },

  updateSettings: (updates: DesktopSettingsUpdate, characterId: string = "aevum"): Promise<DesktopSettings> => {
    return fetchJson<DesktopSettings>(`/desktop/settings?character_id=${encodeURIComponent(characterId)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    });
  },

  setDND: (payload: SetDNDPayload, characterId: string = "aevum"): Promise<{ status: string; dnd_until: string | null }> => {
    return fetchJson<{ status: string; dnd_until: string | null }>(
      `/desktop/settings/dnd?character_id=${encodeURIComponent(characterId)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }
    );
  },

  sendHeartbeat: (payload: HeartbeatPayload, characterId: string = "aevum"): Promise<HeartbeatResponse> => {
    return fetchJson<HeartbeatResponse>(`/desktop/heartbeat?character_id=${encodeURIComponent(characterId)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  getNotificationHistory: (characterId: string = "aevum", limit: number = 50): Promise<NotificationHistoryItem[]> => {
    return fetchJson<NotificationHistoryItem[]>(
      `/desktop/notifications/history?character_id=${encodeURIComponent(characterId)}&limit=${limit}`
    );
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
    return fetchJson<{ status: string; claimed: boolean; notification_id: string }>(
      `/desktop/notifications/${encodeURIComponent(id)}/claim`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          worker_id: workerId,
          character_id: characterId,
          lease_timeout_seconds: leaseTimeoutSeconds,
        }),
      }
    );
  },

  completeNotification: (
    id: string,
    workerId: string,
    characterId: string = "aevum"
  ): Promise<{ status: string; completed: boolean; notification_id: string }> => {
    return fetchJson<{ status: string; completed: boolean; notification_id: string }>(
      `/desktop/notifications/${encodeURIComponent(id)}/complete`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          worker_id: workerId,
          character_id: characterId,
        }),
      }
    );
  },

  releaseNotification: (
    id: string,
    workerId: string,
    characterId: string = "aevum"
  ): Promise<{ status: string; released: boolean; notification_id: string }> => {
    return fetchJson<{ status: string; released: boolean; notification_id: string }>(
      `/desktop/notifications/${encodeURIComponent(id)}/release`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          worker_id: workerId,
          character_id: characterId,
        }),
      }
    );
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
};
