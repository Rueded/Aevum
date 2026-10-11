import { fetchJson, getBackendBaseUrl } from "./client";
import type {
  VoiceTTSRequest,
  VoiceTTSResponse,
  VoiceSTTRequest,
  VoiceSTTResponse,
} from "../types";

export const voiceApi = {
  transcribe: (payload: VoiceSTTRequest): Promise<VoiceSTTResponse> => {
    return fetchJson<VoiceSTTResponse>("/voice/stt", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  synthesize: (payload: VoiceTTSRequest): Promise<VoiceTTSResponse> => {
    return fetchJson<VoiceTTSResponse>("/voice/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  getCachedAudioUrl: (cacheKey: string): string => {
    return `${getBackendBaseUrl()}/voice/audio/${encodeURIComponent(cacheKey)}`;
  },
};
