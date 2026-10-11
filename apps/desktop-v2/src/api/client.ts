// Base HTTP Client for Aevum Core API
import { Capacitor } from "@capacitor/core";

export const CLOUD_BACKEND_URL = "https://aevum-1mcy.onrender.com";

export function getBackendBaseUrl(): string {
  if (typeof window !== "undefined") {
    const isNativeMobile = Capacitor.isNativePlatform() || (window as any).Capacitor !== undefined;
    const saved = localStorage.getItem("aevum_backend_url");

    if (saved && saved.trim()) {
      const clean = saved.trim().replace(/\/+$/, "");
      // On mobile native app, ignore accidental/legacy localhost/127.0.0.1 settings
      if (isNativeMobile && (clean.includes("localhost") || clean.includes("127.0.0.1"))) {
        localStorage.removeItem("aevum_backend_url");
        return CLOUD_BACKEND_URL;
      }
      return clean;
    }

    // If running inside Capacitor Native Mobile App, default to 24/7 cloud backend
    if (isNativeMobile) {
      return CLOUD_BACKEND_URL;
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
  const url = `${getBackendBaseUrl()}${endpoint}`;
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
