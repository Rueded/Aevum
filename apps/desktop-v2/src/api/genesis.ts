import { fetchJson } from "./client";
import type {
  GenesisPresetsResponse,
  CharacterCreationPayload,
  CharacterCreationResponse,
  CharacterBlueprintResponse,
  BlueprintUpdateRequest,
} from "../types";

export const genesisApi = {
  getPresets: (): Promise<GenesisPresetsResponse> => {
    return fetchJson<GenesisPresetsResponse>("/character/genesis/presets");
  },

  create: (payload: CharacterCreationPayload): Promise<CharacterCreationResponse> => {
    return fetchJson<CharacterCreationResponse>("/character/genesis", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  aiGenerate: (prompt: string): Promise<CharacterCreationPayload> => {
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
};
