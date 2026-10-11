import { fetchJson, getBackendBaseUrl } from "./client";
import type { ResolveLocalModelResponse } from "../types";

export const avatarApi = {
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
    const response = await fetch(`${getBackendBaseUrl()}/character/avatar/upload-live2d-zip`, {
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

  getCurrentModel: (): Promise<{
    active: boolean;
    name: string;
    model_id: string;
    model_serve_url: string;
    avatar_data_url: string | null;
  }> => {
    return fetchJson("/character/avatar/current-model");
  },

  listAvailableModels: (): Promise<
    Array<{
      id: string;
      name: string;
      model_serve_url: string;
      avatar_data_url: string | null;
      is_current: boolean;
    }>
  > => {
    return fetchJson("/character/avatar/available-models");
  },

  setActiveModel: (modelId: string): Promise<{
    status: string;
    model_id: string;
    model_serve_url: string;
    avatar_data_url: string | null;
  }> => {
    return fetchJson("/character/avatar/set-active-model", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model_id: modelId }),
    });
  },
};

