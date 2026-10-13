import React, { useEffect, useState, useCallback } from "react";
import { AppShell } from "./layouts/AppShell";
import { CompanionStage } from "./features/stage/CompanionStage";
import { CompanionDrawer } from "./features/drawer/CompanionDrawer";
import { SettingsModal } from "./features/settings/SettingsModal";
import { CharacterGenesisModal } from "./features/genesis/CharacterGenesisModal";
import { DevCognitiveInspector } from "./features/dev-inspector/DevCognitiveInspector";
import { CallHUD } from "./features/call/CallHUD";
import { PresentationSandbox } from "./presentation/PresentationSandbox";
import { MobileChatView } from "./features/chat/MobileChatView";
import { CompanionSwitcherModal } from "./features/switcher/CompanionSwitcherModal";

import { useHealthStore } from "./stores/useHealthStore";
import { useCharacterStore } from "./stores/useCharacterStore";
import { useConversationStore } from "./stores/useConversationStore";
import { useSettingsStore } from "./stores/useSettingsStore";
import { useVisualStore } from "./stores/useVisualStore";
import { useCallStore } from "./stores/useCallStore";
import { useChatStore } from "./stores/useChatStore";

import { useHeartbeatWorker } from "./hooks/useHeartbeatWorker";
import { useNotificationWorker } from "./hooks/useNotificationWorker";
import { useAudioPlayback } from "./features/voice/useAudioPlayback";
import { useCallManager } from "./hooks/useCallManager";
import { conversationsApi } from "./api/conversations";

export default function App() {
  // Mobile / Desktop View Mode
  const [viewMode, setViewMode] = useState<"desktop" | "mobile">(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const urlView = params.get("view");
      if (urlView === "mobile" || urlView === "desktop") return urlView;
    }
    const saved = localStorage.getItem("aevum_view_mode");
    if (saved === "desktop" || saved === "mobile") return saved;
    if (typeof window !== "undefined") {
      const isMobileUA = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
      if (isMobileUA || window.innerWidth < 768) return "mobile";
    }
    return "desktop";
  });

  const handleSetViewMode = (mode: "desktop" | "mobile") => {
    setViewMode(mode);
    localStorage.setItem("aevum_view_mode", mode);
  };

  // Global Modals State
  const [isDrawerOpen, setIsDrawerOpen] = useState(true);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isGenesisOpen, setIsGenesisOpen] = useState(false);
  const [isInspectorOpen, setIsInspectorOpen] = useState(false);
  const [isSandboxOpen, setIsSandboxOpen] = useState(false);
  const [isSwitcherOpen, setIsSwitcherOpen] = useState(false);

  // Store Selectors
  const isBackendOnline = useHealthStore((s) => s.isBackendOnline);
  const fetchHealth = useHealthStore((s) => s.fetchHealth);
  const setBackendCrashed = useHealthStore((s) => s.setBackendCrashed);

  const characterState = useCharacterStore((s) => s.characterState);
  const life = useCharacterStore((s) => s.life);
  const refreshAllCharacter = useCharacterStore((s) => s.refreshAll);

  const activeConversationId = useConversationStore((s) => s.activeConversationId);
  const loadActiveOrCreate = useConversationStore((s) => s.loadActiveOrCreate);

  const fetchSettings = useSettingsStore((s) => s.fetchSettings);
  const bubbleMode = useSettingsStore((s) => s.bubbleMode);
  const setBubbleMode = useSettingsStore((s) => s.setBubbleMode);
  const emojiEnabled = useSettingsStore((s) => s.emojiRenderingEnabled);
  const setEmojiEnabled = useSettingsStore((s) => s.setEmojiRenderingEnabled);

  const visualExpression = useVisualStore((s) => s.visualExpression);
  const visualMotion = useVisualStore((s) => s.visualMotion);
  const lipSyncState = useVisualStore((s) => s.lipSyncState);

  const isGenerating = useChatStore((s) => s.isGenerating);

  const callMode = useCallStore((s) => s.callMode);
  const activeGenerationId = useCallStore((s) => s.activeGenerationId);
  const partialTranscript = useCallStore((s) => s.partialTranscript);
  const isMuted = useCallStore((s) => s.isMuted);
  const toggleMute = useCallStore((s) => s.toggleMute);
  const callError = useCallStore((s) => s.callError);
  const isCompanionSpeaking = useCallStore((s) => s.isCompanionSpeaking);

  // Background Workers
  useHeartbeatWorker("aevum");
  useNotificationWorker("aevum");

  // Audio Playback & Realtime Call
  const { playAudio, stopAudio } = useAudioPlayback();
  const { startCall, endCall, triggerBargeIn } = useCallManager();

  // Initialization & Health Polling
  useEffect(() => {
    fetchHealth();
    refreshAllCharacter();
    loadActiveOrCreate();
    fetchSettings();

    const healthInterval = setInterval(fetchHealth, 5000);
    return () => clearInterval(healthInterval);
  }, [fetchHealth, refreshAllCharacter, loadActiveOrCreate, fetchSettings]);

  // Listen to Tauri Backend Crash IPC & Genesis completion
  useEffect(() => {
    const handleGenesisCompleted = () => {
      refreshAllCharacter();
    };

    window.addEventListener("aevum-character-genesis-completed", handleGenesisCompleted);

    let unlistenCrash: (() => void) | undefined;
    if (typeof window !== "undefined" && "__TAURI_INTERNALS__" in window) {
      import("@tauri-apps/api/event").then(({ listen }) => {
        listen<{ message?: string }>("backend_crashed", (event) => {
          setBackendCrashed(true, event.payload?.message);
        }).then((unsub) => {
          unlistenCrash = unsub;
        });
      });
    }

    return () => {
      window.removeEventListener("aevum-character-genesis-completed", handleGenesisCompleted);
      if (unlistenCrash) unlistenCrash();
    };
  }, [refreshAllCharacter, setBackendCrashed]);

  // Dev Inspector Keyboard Shortcut (Ctrl+Shift+D)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && (e.key === "D" || e.key === "d")) {
        e.preventDefault();
        setIsInspectorOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const handleSendVoiceMessage = useCallback(
    async (audioBase64: string, durationMs: number) => {
      if (!activeConversationId) return;
      try {
        const res = await conversationsApi.sendVoiceMessage(activeConversationId, {
          audio_base64: audioBase64,
          duration_ms: durationMs,
          user_consent_granted: true,
          synthesize_reply_audio: true,
        });
        if (res.assistant_response?.audio_cache_key) {
          playAudio(res.assistant_response);
        }
        refreshAllCharacter();
      } catch (err) {
        console.error("Failed to send voice message:", err);
      }
    },
    [activeConversationId, playAudio, refreshAllCharacter]
  );

  const handleSendMessageText = useCallback(
    async (text: string) => {
      if (!activeConversationId) return;
      try {
        await conversationsApi.sendMessage(activeConversationId, text);
        refreshAllCharacter();
      } catch (err) {
        console.error("Failed to send message:", err);
      }
    },
    [activeConversationId, refreshAllCharacter]
  );

  const handleCompanionSwitched = useCallback(
    async (charId: string) => {
      console.log("Companion switched to:", charId);
      await refreshAllCharacter();
      await loadActiveOrCreate();
    },
    [refreshAllCharacter, loadActiveOrCreate]
  );

  const characterName = characterState?.name || "苏棠";

  return (
    <>
      {viewMode === "mobile" ? (
        <MobileChatView
          onSwitchToDesktop={() => handleSetViewMode("desktop")}
          onOpenSettings={() => setIsSettingsOpen(true)}
          onPlayAudio={playAudio}
          onStopAudio={stopAudio}
          onSendVoiceMessage={handleSendVoiceMessage}
          onStartCall={startCall}
          onEndCall={endCall}
          onBargeIn={triggerBargeIn}
          onOpenCompanionSwitcher={() => setIsSwitcherOpen(true)}
        />
      ) : (
        <AppShell
          isDrawerOpen={isDrawerOpen}
          onToggleDrawer={() => setIsDrawerOpen((v) => !v)}
          onOpenSettings={() => setIsSettingsOpen(true)}
          onOpenDevInspector={() => setIsInspectorOpen(true)}
          onSwitchToMobile={() => handleSetViewMode("mobile")}
          onOpenCompanionSwitcher={() => setIsSwitcherOpen(true)}
          stageSlot={
            <>
              <CompanionStage
                characterName={characterName}
                characterState={characterState}
                life={life}
                visualExpression={visualExpression}
                visualMotion={visualMotion}
                lipSyncState={lipSyncState}
                isBackendReady={isBackendOnline}
                isGenerating={isGenerating}
                isInCall={callMode === "ACTIVE" || callMode === "CONNECTING"}
                callMode={callMode}
              />
              {callMode !== "IDLE" && (
                <CallHUD
                  callMode={callMode}
                  activeGenerationId={activeGenerationId}
                  partialTranscript={partialTranscript}
                  isMuted={isMuted}
                  onToggleMute={toggleMute}
                  onStartCall={startCall}
                  onEndCall={endCall}
                  onBargeIn={triggerBargeIn}
                  errorMessage={callError}
                  characterName={characterName}
                  onSendVoiceMessage={handleSendVoiceMessage}
                  onSendMessage={handleSendMessageText}
                  isCompanionSpeaking={isCompanionSpeaking}
                />
              )}
            </>
          }
          drawerSlot={
            <CompanionDrawer
              onToggleOpen={() => setIsDrawerOpen(false)}
              onPlayAudio={playAudio}
              onStopAudio={stopAudio}
              onSendVoiceMessage={handleSendVoiceMessage}
              onOpenSettings={() => setIsSettingsOpen(true)}
            />
          }
        />
      )}

      {/* Global Modals */}
      <CompanionSwitcherModal
        isOpen={isSwitcherOpen}
        onClose={() => setIsSwitcherOpen(false)}
        onCompanionSwitched={handleCompanionSwitched}
        onOpenGenesis={() => {
          setIsSwitcherOpen(false);
          setIsGenesisOpen(true);
        }}
      />

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        onOpenGenesis={() => {
          setIsSettingsOpen(false);
          setIsGenesisOpen(true);
        }}
        bubbleMode={bubbleMode}
        onBubbleModeChange={setBubbleMode}
        emojiRenderingEnabled={emojiEnabled}
        onEmojiRenderingChange={setEmojiEnabled}
        onOpenDevInspector={() => {
          setIsSettingsOpen(false);
          setIsInspectorOpen(true);
        }}
      />

      <CharacterGenesisModal
        isOpen={isGenesisOpen}
        onClose={() => setIsGenesisOpen(false)}
        onGenesisComplete={() => {
          refreshAllCharacter();
          setIsGenesisOpen(false);
        }}
      />

      <DevCognitiveInspector
        isOpen={isInspectorOpen}
        onClose={() => setIsInspectorOpen(false)}
        bubbleMode={bubbleMode}
        onBubbleModeChange={setBubbleMode}
        emojiRenderingEnabled={emojiEnabled}
        onEmojiRenderingChange={setEmojiEnabled}
        onStateModified={refreshAllCharacter}
        onOpenGenesis={() => {
          setIsInspectorOpen(false);
          setIsGenesisOpen(true);
        }}
        onOpenPresentationSandbox={() => {
          setIsInspectorOpen(false);
          setIsSandboxOpen(true);
        }}
      />

      {isSandboxOpen && (
        <div
          onClick={() => setIsSandboxOpen(false)}
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.75)",
            backdropFilter: "blur(8px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            padding: 24,
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              width: "100%",
              maxWidth: 960,
              maxHeight: "90vh",
              overflowY: "auto",
              background: "var(--bg-secondary)",
              borderRadius: "var(--radius-lg)",
              border: "1px solid var(--border-default)",
              boxShadow: "var(--shadow-lg)",
            }}
          >
            <PresentationSandbox onClose={() => setIsSandboxOpen(false)} />
          </div>
        </div>
      )}
    </>
  );
}
