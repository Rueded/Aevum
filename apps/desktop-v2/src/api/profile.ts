import { fetchJson } from "./client";
import type {
  ProfileResponse,
  UpdateCoreRequest,
  FactMutationResponse,
} from "../types";

export const profileApi = {
  get: (characterId: string = "aevum"): Promise<ProfileResponse> => {
    return fetchJson<ProfileResponse>(`/character/profile?character_id=${encodeURIComponent(characterId)}`);
  },

  updateCore: (payload: UpdateCoreRequest, characterId: string = "aevum"): Promise<ProfileResponse> => {
    return fetchJson<ProfileResponse>(`/character/profile/core?character_id=${encodeURIComponent(characterId)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  lockFact: (factKey: string, characterId: string = "aevum"): Promise<FactMutationResponse> => {
    return fetchJson<FactMutationResponse>(
      `/character/profile/core/${encodeURIComponent(factKey)}/lock?character_id=${encodeURIComponent(characterId)}`,
      { method: "POST" }
    );
  },

  unlockFact: (factKey: string, characterId: string = "aevum"): Promise<FactMutationResponse> => {
    return fetchJson<FactMutationResponse>(
      `/character/profile/core/${encodeURIComponent(factKey)}/unlock?character_id=${encodeURIComponent(characterId)}`,
      { method: "POST" }
    );
  },

  confirmFact: (factKey: string, characterId: string = "aevum"): Promise<FactMutationResponse> => {
    return fetchJson<FactMutationResponse>(
      `/character/profile/core/${encodeURIComponent(factKey)}/confirm?character_id=${encodeURIComponent(characterId)}`,
      { method: "POST" }
    );
  },

  rejectFact: (factKey: string, characterId: string = "aevum"): Promise<FactMutationResponse> => {
    return fetchJson<FactMutationResponse>(
      `/character/profile/core/${encodeURIComponent(factKey)}/reject?character_id=${encodeURIComponent(characterId)}`,
      { method: "POST" }
    );
  },

  deleteFact: (factKey: string, characterId: string = "aevum"): Promise<FactMutationResponse> => {
    return fetchJson<FactMutationResponse>(
      `/character/profile/core/${encodeURIComponent(factKey)}?character_id=${encodeURIComponent(characterId)}`,
      { method: "DELETE" }
    );
  },
};
