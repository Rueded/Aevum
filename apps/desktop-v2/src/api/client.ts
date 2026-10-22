// Base HTTP Client for Aevum Core API
import { Capacitor } from "@capacitor/core";

export const CLOUD_BACKEND_URL = "https://aevum-1mcy.onrender.com";

export function getBackendBaseUrl(): string {
  if (typeof window !== "undefined") {
    const saved = localStorage.getItem("aevum_backend_url");

    if (saved && saved.trim()) {
      const clean = saved.trim().replace(/\/+$/, "");
      // Discard expired Render URL so it never gets stuck
      if (clean.includes("onrender.com")) {
        localStorage.removeItem("aevum_backend_url");
      } else {
        return clean;
      }
    }

    if (
      window.location.hostname &&
      window.location.hostname !== "localhost" &&
      window.location.hostname !== "127.0.0.1" &&
      !window.location.hostname.includes("tauri")
    ) {
      return `http://${window.location.hostname}:8000`;
    }
  }
  return "http://127.0.0.1:8000";
}

export function setBackendBaseUrl(url: string): void {
  if (typeof window !== "undefined") {
    const clean = url.trim().replace(/\/+$/, "");
    if (clean) {
      localStorage.setItem("aevum_backend_url", clean);
    } else {
      localStorage.removeItem("aevum_backend_url");
    }
  }
}

export const BACKEND_BASE_URL = getBackendBaseUrl();

export async function fetchJson<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const baseUrl = getBackendBaseUrl();
  let response: Response;
  try {
    response = await fetch(`${baseUrl}${endpoint}`, options);
  } catch (netErr: any) {
    throw new Error(
      `无法连接到 Aevum 后端服务 (${baseUrl})。请确认本地电脑已运行后端服务 (uvicorn port 8000)。错误: ${netErr.message || netErr}`
    );
  }

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
