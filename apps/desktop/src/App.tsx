import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import "./App.css";
import { api } from "./api";
import { ChatView } from "./components/ChatView";
import { DesktopSettingsView } from "./components/DesktopSettingsView";
import { PresenceHeader } from "./components/PresenceHeader";
import { Sidebar } from "./components/Sidebar";
import {
  CharacterDebugResponse,
  CharacterStateResponse,
  ConversationDetail,
  HealthData,
  LifeResponse,
  MemoryItem,
  MessageItem,
  RelationshipResponse,
} from "./types";

const LOCAL_STORAGE_CONV_KEY = "aevum_active_conversation_id";

export function App() {
  // Unique worker ID for atomic notification claiming per desktop session
  const workerIdRef = useRef<string>(
    `desktop-worker-${Math.random().toString(36).substring(2, 9)}`
  );

  // Backend & companion state
  const [health, setHealth] = useState<HealthData | null>(null);
  const [backendStatus, setBackendStatus] = useState<{
    ready: boolean;
    crashed?: boolean;
    mode?: string;
    error?: string;
  }>({ ready: true });
  const [characterState, setCharacterState] = useState<CharacterStateResponse | null>(null);
  const [relationship, setRelationship] = useState<RelationshipResponse | null>(null);
  const [life, setLife] = useState<LifeResponse | null>(null);
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [debugData, setDebugData] = useState<CharacterDebugResponse | null>(null);

  // Active chat session state
  const [activeConversationId, setActiveConversationId] = useState<string | null>(() => {
    return localStorage.getItem(LOCAL_STORAGE_CONV_KEY);
  });
  const [conversation, setConversation] = useState<ConversationDetail | null>(null);
  const [inputMessage, setInputMessage] = useState<string>("");
  const [lastFailedMessage, setLastFailedMessage] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [chatError, setChatError] = useState<string | null>(null);

  // Layout & modal state
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<"about" | "relationship" | "memories" | "debug">("about");
  const [highlightedMessageId, setHighlightedMessageId] = useState<string | null>(null);

  // Load backend health
  const checkHealth = useCallback(async () => {
    try {
      const data = await api.getHealth();
      setHealth(data);
    } catch {
      setHealth(null);
    }
  }, []);

  // Refresh character domain state (read-only projection)
  const refreshCompanionState = useCallback(async () => {
    try {
      const [charData, relData, lifeData, memData] = await Promise.all([
        api.getCharacterState().catch(() => null),
        api.getRelationship().catch(() => null),
        api.getLife().catch(() => null),
        api.getMemories().catch(() => []),
      ]);

      if (charData) setCharacterState(charData);
      if (relData) setRelationship(relData);
      if (lifeData) setLife(lifeData);
      if (memData) setMemories(memData);
    } catch (err) {
      console.warn("Failed to refresh companion state:", err);
    }
  }, []);

  // Refresh debug data when tab is active
  const refreshDebugData = useCallback(async () => {
    try {
      const data = await api.getDebug();
      setDebugData(data);
    } catch (err) {
      console.warn("Failed to refresh debug data:", err);
    }
  }, []);

  // Fetch conversation messages
  const loadConversation = useCallback(async (convId: string) => {
    try {
      const data = await api.getConversation(convId);
      setConversation(data);
      setChatError(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error loading conversation";
      if (msg.includes("404") || msg.includes("not found")) {
        // Conversation was deleted or reset
        localStorage.removeItem(LOCAL_STORAGE_CONV_KEY);
        setActiveConversationId(null);
        setConversation(null);
      } else {
        setChatError(msg);
      }
    }
  }, []);

  // Initialize or create conversation on demand
  const handleCreateNewConversation = useCallback(async () => {
    setChatError(null);
    setLastFailedMessage(null);
    try {
      const created = await api.createConversation();
      localStorage.setItem(LOCAL_STORAGE_CONV_KEY, created.id);
      setActiveConversationId(created.id);
      setConversation({
        id: created.id,
        created_at: created.created_at,
        updated_at: created.updated_at,
        messages: [],
      });
      await refreshCompanionState();
    } catch (err: unknown) {
      setChatError(err instanceof Error ? err.message : "Failed to create conversation");
    }
  }, [refreshCompanionState]);

  // Initial load
  useEffect(() => {
    checkHealth();
    refreshCompanionState();

    if (activeConversationId) {
      loadConversation(activeConversationId);
    } else {
      // Auto-create initial conversation if none saved
      handleCreateNewConversation();
    }
  }, [checkHealth, refreshCompanionState, activeConversationId, loadConversation, handleCreateNewConversation]);

  // Refresh debug data when debug tab is viewed
  useEffect(() => {
    if (isSidebarOpen && activeTab === "debug") {
      refreshDebugData();
    }
  }, [isSidebarOpen, activeTab, refreshDebugData]);

  // ===========================================================================
  // Step 4B: Independent Notification Polling Worker (12s interval)
  // Authoritative lifecycle: GET pending -> claim -> send_native_toast -> complete
  // Recoverable error: release
  // Decoupled from Heartbeat & zero LLM generation.
  // ===========================================================================
  useEffect(() => {
    let isCancelled = false;

    const pollNotifications = async () => {
      if (isCancelled) return;
      try {
        const pending = await api.getPendingNotifications("aevum");
        if (!pending || pending.length === 0 || isCancelled) return;

        for (const notif of pending) {
          if (isCancelled) break;

          // 1. Atomic lease claim
          let claimed = false;
          try {
            const claimRes = await api.claimNotification(
              notif.id,
              workerIdRef.current,
              "aevum",
              60.0
            );
            claimed = claimRes.claimed;
          } catch {
            // Lost race, lease conflict, or expired (>24h)
            continue;
          }

          if (!claimed || isCancelled) continue;

          // 2. Dispatch native Windows Toast
          let dispatched = false;
          try {
            if (typeof window !== "undefined" && "__TAURI_INTERNALS__" in window) {
              await invoke("send_native_toast", {
                id: notif.id,
                title: notif.title,
                body: notif.body,
              });
              dispatched = true;
            } else {
              console.log("[NotificationWorker] Simulated native toast for browser:", notif.id);
              dispatched = true;
            }
          } catch (dispatchErr) {
            console.error("[NotificationWorker] Native toast dispatch failed:", dispatchErr);
            // Recoverable dispatch failure -> release back to PENDING
            await api.releaseNotification(notif.id, workerIdRef.current, "aevum").catch(() => {});
            continue;
          }

          // 3. Mark delivery as complete
          if (dispatched && !isCancelled) {
            await api.completeNotification(notif.id, workerIdRef.current, "aevum").catch(() => {});
          }
        }
      } catch {
        // Network or backend unavailable; retry on next tick
      }
    };

    const initialTimer = setTimeout(pollNotifications, 2000);
    const intervalId = setInterval(pollNotifications, 12000);

    return () => {
      isCancelled = true;
      clearTimeout(initialTimer);
      clearInterval(intervalId);
    };
  }, []);

  // ===========================================================================
  // Step 4C: Independent Heartbeat Worker (30s interval)
  // Respects idle_awareness_enabled (purged by backend when disabled).
  // Strictly zero persistence when disabled. No LLM / psychological inferences.
  // ===========================================================================
  useEffect(() => {
    let lastActivityTime = Date.now();

    const handleUserActivity = () => {
      lastActivityTime = Date.now();
    };

    window.addEventListener("mousemove", handleUserActivity, { passive: true });
    window.addEventListener("keydown", handleUserActivity, { passive: true });
    window.addEventListener("scroll", handleUserActivity, { passive: true });
    window.addEventListener("focus", handleUserActivity);

    const sendHeartbeatTick = async () => {
      try {
        const now = Date.now();
        const idleSeconds = Math.max(0, Math.floor((now - lastActivityTime) / 1000));
        const hasFocus = document.hasFocus();

        await api.sendHeartbeat(
          {
            client_id: "desktop-client-main",
            client_timestamp: new Date().toISOString(),
            is_idle: idleSeconds >= 300,
            idle_seconds: idleSeconds,
            window_focused: hasFocus,
            app_active: !document.hidden,
          },
          "aevum"
        );
      } catch {
        // Backend unavailable; retry on next tick
      }
    };

    const initialHb = setTimeout(sendHeartbeatTick, 4000);
    const hbInterval = setInterval(sendHeartbeatTick, 30000);

    return () => {
      window.removeEventListener("mousemove", handleUserActivity);
      window.removeEventListener("keydown", handleUserActivity);
      window.removeEventListener("scroll", handleUserActivity);
      window.removeEventListener("focus", handleUserActivity);
      clearTimeout(initialHb);
      clearInterval(hbInterval);
    };
  }, []);

  // ===========================================================================
  // Step 4D: Deterministic Notification Activation via Deep-Link
  // Flow: Windows Toast -> aevum://notification/{id} -> Tauri -> notification-activated
  //       -> GET /notifications/{id} -> conversation_message_id -> highlight message
  //       -> POST /notifications/{id}/interact (CLICKED)
  // Hard Invariant: Zero LLM calls, zero focus heuristics, exact ID matching.
  // ===========================================================================
  const handleNotificationActivated = useCallback(
    async (notificationId: string) => {
      if (!notificationId) return;

      try {
        // 1. Fetch authoritative notification record from backend
        const notif = await api.getNotificationById(notificationId, "aevum");
        if (!notif || !notif.conversation_message_id) return;

        const targetMsgId = notif.conversation_message_id;

        // 2. Ensure current conversation contains targetMsgId
        if (activeConversationId) {
          const currentConv = await api.getConversation(activeConversationId);
          setConversation(currentConv);
        }

        // 3. Highlight message in ChatView
        setHighlightedMessageId(targetMsgId);
        setTimeout(() => {
          setHighlightedMessageId(null);
        }, 4000);

        // 4. Record interaction (CLICKED) idempotently
        await api.interactNotification(notificationId, "CLICKED", "aevum");
      } catch (err) {
        console.warn("[Activation] Failed to activate notification:", err);
      }
    },
    [activeConversationId]
  );

  useEffect(() => {
    if (typeof window !== "undefined" && "__TAURI_INTERNALS__" in window) {
      let unlistenAct: (() => void) | undefined;
      let unlistenTray: (() => void) | undefined;
      let unlistenStatus: (() => void) | undefined;

      // Listen for backend crash / status changes
      listen<{ ready: boolean; crashed?: boolean; mode?: string; error?: string }>(
        "backend-status-changed",
        (event) => {
          setBackendStatus(event.payload);
        }
      ).then((u) => {
        unlistenStatus = u;
      });

      // Probe initial backend status
      invoke<{ healthy: boolean; mode: string; crashed: boolean }>("get_backend_status")
        .then((status) => {
          setBackendStatus({
            ready: status.healthy,
            crashed: status.crashed,
            mode: status.mode,
          });
        })
        .catch(() => {});

      // Running instance deep link
      listen<{ notificationId: string }>("notification-activated", (event) => {
        if (event.payload?.notificationId) {
          handleNotificationActivated(event.payload.notificationId);
        }
      }).then((u) => {
        unlistenAct = u;
      });

      // System Tray DND toggles
      listen<{ enabled: boolean; duration_minutes?: number }>("tray-dnd-toggle", async (event) => {
        try {
          if (event.payload?.enabled) {
            await api.setDND({ duration_minutes: event.payload.duration_minutes || 60 }, "aevum");
          } else {
            await api.setDND({ clear: true }, "aevum");
          }
        } catch (err) {
          console.warn("[Tray] Failed to toggle DND:", err);
        }
      }).then((u) => {
        unlistenTray = u;
      });

      // Cold-start initial activation check
      invoke<string | null>("get_initial_notification_activation")
        .then((initId) => {
          if (initId) {
            handleNotificationActivated(initId);
          }
        })
        .catch(() => {});

      return () => {
        if (unlistenAct) unlistenAct();
        if (unlistenTray) unlistenTray();
        if (unlistenStatus) unlistenStatus();
      };
    }
  }, [handleNotificationActivated]);

  // Send message with retry support
  const handleSendMessage = async (textToSend?: string) => {
    const content = (textToSend !== undefined ? textToSend : inputMessage).trim();
    if (!content || isGenerating) return;

    let convId = activeConversationId;
    if (!convId) {
      try {
        const created = await api.createConversation();
        convId = created.id;
        localStorage.setItem(LOCAL_STORAGE_CONV_KEY, convId);
        setActiveConversationId(convId);
      } catch (err: unknown) {
        setChatError(err instanceof Error ? err.message : "Failed to initialize conversation session");
        return;
      }
    }

    if (textToSend === undefined) {
      setInputMessage("");
    }
    setLastFailedMessage(null);
    setChatError(null);
    setIsGenerating(true);

    // Optimistically render user message immediately
    const tempUserMsg: MessageItem = {
      id: `temp-${Date.now()}`,
      conversation_id: convId,
      role: "user",
      content: content,
      created_at: new Date().toISOString(),
    };

    setConversation((prev) => ({
      id: convId!,
      created_at: prev?.created_at || new Date().toISOString(),
      updated_at: new Date().toISOString(),
      messages: [...(prev?.messages || []), tempUserMsg],
    }));

    try {
      const res = await api.sendMessage(convId, content);

      // Successfully generated and persisted
      if (res.assistant_response) {
        setConversation((prev) => {
          const filtered = (prev?.messages || []).filter((m) => m.id !== tempUserMsg.id);
          return {
            id: convId!,
            created_at: prev?.created_at || new Date().toISOString(),
            updated_at: new Date().toISOString(),
            messages: [...filtered, res.message, res.assistant_response!],
          };
        });
      } else {
        await loadConversation(convId);
      }

      setLastFailedMessage(null);

      // Update companion domain state in background (relationship, life, memories)
      refreshCompanionState();

      // P3: Refresh memories shortly after turn to sync post-turn background distillation
      setTimeout(() => {
        api.getMemories().then(setMemories).catch(() => {});
      }, 1500);

      if (isSidebarOpen && activeTab === "debug") {
        refreshDebugData();
      }
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "Failed to get response from Aevum";
      setChatError(`Response issue: ${errMsg}`);
      setLastFailedMessage(content);
      // Reload actual persisted messages from backend (user message is persisted even on 502)
      if (convId) {
        loadConversation(convId);
      }
    } finally {
      setIsGenerating(false);
    }
  };

  // Delete memory
  const handleDeleteMemory = async (memoryId: string) => {
    await api.deleteMemory(memoryId);
    setMemories((prev) => prev.filter((m) => m.id !== memoryId));
    if (isSidebarOpen && activeTab === "debug") {
      refreshDebugData();
    }
  };

  return (
    <div className="companion-app-root">
      {backendStatus.crashed && (
        <div className="backend-crashed-banner">
          ⚠️ Backend process exited unexpectedly. Automatic restart is disabled in production to protect data integrity. Please restart Aevum.
        </div>
      )}

      <PresenceHeader
        health={health}
        characterState={characterState}
        isGenerating={isGenerating}
        onNewConversation={handleCreateNewConversation}
        isSidebarOpen={isSidebarOpen}
        onToggleSidebar={() => setIsSidebarOpen((prev) => !prev)}
        activeTab={activeTab}
        onSelectTab={(tab) => setActiveTab(tab)}
        onOpenSettings={() => setIsSettingsOpen(true)}
      />

      <div className="companion-main-body">
        <main className="chat-main-column">
          <ChatView
            messages={conversation?.messages || []}
            isGenerating={isGenerating}
            input={inputMessage}
            onInputChange={setInputMessage}
            onSendMessage={() => handleSendMessage()}
            error={chatError}
            onRetry={lastFailedMessage ? () => handleSendMessage(lastFailedMessage) : undefined}
            characterName={characterState?.name || "Aevum"}
            highlightedMessageId={highlightedMessageId}
          />
        </main>

        <Sidebar
          isOpen={isSidebarOpen}
          onClose={() => setIsSidebarOpen(false)}
          activeTab={activeTab}
          onSelectTab={setActiveTab}
          characterState={characterState}
          relationship={relationship}
          life={life}
          memories={memories}
          onDeleteMemory={handleDeleteMemory}
          debugData={debugData}
          activeConversationId={activeConversationId}
        />
      </div>

      <DesktopSettingsView
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        characterId="aevum"
      />
    </div>
  );
}

export default App;
