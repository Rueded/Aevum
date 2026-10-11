import { fetchJson, BACKEND_BASE_URL } from "./client";
import { characterApi } from "./character";
import { conversationsApi } from "./conversations";
import { desktopApi } from "./desktop";
import { voiceApi } from "./voice";
import { genesisApi } from "./genesis";
import { profileApi } from "./profile";
import { avatarApi } from "./avatar";
import { callApi } from "./call";
import type { HealthData } from "../types";

export { BACKEND_BASE_URL, fetchJson };
export { characterApi } from "./character";
export { conversationsApi } from "./conversations";
export { desktopApi } from "./desktop";
export { voiceApi } from "./voice";
export { genesisApi } from "./genesis";
export { profileApi } from "./profile";
export { avatarApi } from "./avatar";
export { callApi } from "./call";

// Unified api object providing drop-in compatibility with legacy client methods
export const api = {
  getHealth: (): Promise<HealthData> => fetchJson<HealthData>("/health"),

  // Conversations
  createConversation: conversationsApi.create,
  getConversations: conversationsApi.list,
  deleteConversation: conversationsApi.delete,
  getConversation: conversationsApi.get,
  sendMessage: conversationsApi.sendMessage,
  sendVoiceMessage: conversationsApi.sendVoiceMessage,
  checkIdleNudge: conversationsApi.checkIdleNudge,

  // Character
  getCharacterState: characterApi.getState,
  updateCharacterState: characterApi.updateState,
  getRelationship: characterApi.getRelationship,
  updateRelationship: characterApi.updateRelationship,
  getLife: characterApi.getLife,
  getMemories: characterApi.getMemories,
  deleteMemory: characterApi.deleteMemory,
  getDebug: characterApi.getDebug,
  getLongitudinalMemory: characterApi.getLongitudinalMemory,
  setSituation: characterApi.setSituation,

  // Profile
  getProfile: profileApi.get,
  updateCoreProfile: profileApi.updateCore,
  lockFact: profileApi.lockFact,
  unlockFact: profileApi.unlockFact,
  confirmFact: profileApi.confirmFact,
  rejectFact: profileApi.rejectFact,
  deleteFact: profileApi.deleteFact,

  // Desktop
  getDesktopSettings: desktopApi.getSettings,
  updateDesktopSettings: desktopApi.updateSettings,
  setDND: desktopApi.setDND,
  sendHeartbeat: desktopApi.sendHeartbeat,
  getNotificationHistory: desktopApi.getNotificationHistory,
  getPendingNotifications: desktopApi.getPendingNotifications,
  getNotificationById: desktopApi.getNotificationById,
  claimNotification: desktopApi.claimNotification,
  completeNotification: desktopApi.completeNotification,
  releaseNotification: desktopApi.releaseNotification,
  interactNotification: desktopApi.interactNotification,
  triggerProactiveTest: desktopApi.triggerProactiveTest,

  // Voice
  transcribeVoice: voiceApi.transcribe,
  synthesizeVoice: voiceApi.synthesize,
  getCachedAudioUrl: voiceApi.getCachedAudioUrl,

  // Genesis
  getGenesisPresets: genesisApi.getPresets,
  createGenesis: genesisApi.create,
  aiGenerateGenesis: genesisApi.aiGenerate,
  getBlueprint: genesisApi.getBlueprint,
  updateBlueprint: genesisApi.updateBlueprint,

  // Avatar
  resolveLocalModel: avatarApi.resolveLocalModel,
  uploadLive2DZip: avatarApi.uploadLive2DZip,
  getCurrentModel: avatarApi.getCurrentModel,
  listAvailableModels: avatarApi.listAvailableModels,
  setActiveModel: avatarApi.setActiveModel,

  // Call
  createCallSession: callApi.createSession,
  getCallSession: callApi.getSession,
  getCallStreamWsUrl: callApi.getStreamWsUrl,
};
