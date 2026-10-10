import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import "./App.css";
import { api } from "./api";
import { CallHUD } from "./components/CallHUD";
import { CompanionDrawer, CompanionDrawerTab } from "./components/CompanionDrawer";
import { CompanionStage } from "./components/CompanionStage";
import { DesktopSettingsView } from "./components/DesktopSettingsView";
import { PresenceHeader } from "./components/PresenceHeader";
import { CharacterGenesisModal } from "./components/CharacterGenesisModal";
import { Live2DModelModal } from "./components/Live2DModelModal";
import { PresentationSandbox } from "./presentation/PresentationSandbox";
import { DevCognitiveInspector } from "./components/DevCognitiveInspector";
import {
  CallMode,
  CharacterCreationResponse,
  CharacterDebugResponse,
  CharacterStateResponse,
  ConversationDetail,
  HealthData,
  InterruptFlushPayload,
  LifeResponse,
  MemoryItem,
  MessageItem,
  RealtimeErrorPayload,
  RelationshipResponse,
  TranscriptEventPayload,
  VisualDirectivePayload,
} from "./types";
import { LipSyncAnalyzer } from "./visual/lipSyncAnalyzer";
import { RealtimeLipSyncEngine } from "./visual/realtimeLipSync";
import { LipSyncMouthState } from "./visual/types";
import { deriveVisualExpression, deriveVisualMotion } from "./visual/visualMappers";

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
  const messageQueueRef = useRef<string[]>([]);

  // Phase 11.5: Live2D stage visibility
  const [isStageVisible, setIsStageVisible] = useState<boolean>(() => {
    return localStorage.getItem("aevum_visual_stage_visible") !== "false";
  });

  const handleToggleStage = useCallback(() => {
    setIsStageVisible((prev) => {
      const next = !prev;
      localStorage.setItem("aevum_visual_stage_visible", String(next));
      return next;
    });
  }, []);

  // Phase 10 & 11: Audio playback, barge-in latch & Lip-sync state
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);
  const [playingMessageId, setPlayingMessageId] = useState<string | null>(null);
  const lipSyncAnalyzerRef = useRef<LipSyncAnalyzer | null>(null);
  const [lipSyncState, setLipSyncState] = useState<LipSyncMouthState>({
    mouth_open_y: 0.0,
    mouth_form: 0.0,
    is_speaking: false,
  });

  // Phase 13: Realtime Voice Call state
  const [callMode, setCallMode] = useState<CallMode>("IDLE");
  const [activeCallSessionId, setActiveCallSessionId] = useState<string | null>(null);
  const [activeGenerationId, setActiveGenerationId] = useState<number>(0);
  const [partialTranscript, setPartialTranscript] = useState<string>("");
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [callError, setCallError] = useState<string | null>(null);
  const callWsRef = useRef<WebSocket | null>(null);
  const callMicStreamRef = useRef<MediaStream | null>(null);

  if (!lipSyncAnalyzerRef.current) {
    lipSyncAnalyzerRef.current = new LipSyncAnalyzer();
  }

  // Phase 13.5: Realtime Streaming LipSync Engine
  const realtimeLipSyncRef = useRef<RealtimeLipSyncEngine | null>(null);
  if (!realtimeLipSyncRef.current) {
    realtimeLipSyncRef.current = new RealtimeLipSyncEngine();
  }

  const stopAudioPlayback = useCallback(() => {
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
      audioPlayerRef.current.currentTime = 0;
    }
    // Lock 3 & Lock 4: Instant client-local clamp to 0.0
    if (lipSyncAnalyzerRef.current) {
      lipSyncAnalyzerRef.current.triggerBargeIn();
    }
    if (realtimeLipSyncRef.current) {
      realtimeLipSyncRef.current.triggerBargeIn();
    }
    setLipSyncState({ mouth_open_y: 0.0, mouth_form: 0.0, is_speaking: false });
    setPlayingMessageId(null);
  }, []);

  const playAudio = useCallback(
    (messageId: string, audioUrl: string) => {
      stopAudioPlayback();
      const audio = new Audio(audioUrl);

      // Route audio to user-selected speaker output device if supported
      const outputDeviceId = localStorage.getItem("aevum_selected_audio_output_id");
      if (outputDeviceId && outputDeviceId !== "default" && "setSinkId" in HTMLMediaElement.prototype) {
        try {
          (audio as unknown as { setSinkId: (id: string) => Promise<void> }).setSinkId(outputDeviceId).catch((err) => {
            console.warn("[playAudio] setSinkId warning:", err);
          });
        } catch (e) {
          console.warn("[playAudio] setSinkId error:", e);
        }
      }

      if (lipSyncAnalyzerRef.current) {
        lipSyncAnalyzerRef.current.resetLatch();
        lipSyncAnalyzerRef.current.attachAudioElement(audio);
      }
      audio.onended = () => {
        setPlayingMessageId(null);
        setLipSyncState({ mouth_open_y: 0.0, mouth_form: 0.0, is_speaking: false });
      };
      audio.onerror = () => {
        setPlayingMessageId(null);
        setLipSyncState({ mouth_open_y: 0.0, mouth_form: 0.0, is_speaking: false });
      };
      audioPlayerRef.current = audio;
      setPlayingMessageId(messageId);
      audio.play().catch((err) => {
        console.warn("Audio playback failed:", err);
        setPlayingMessageId(null);
        setLipSyncState({ mouth_open_y: 0.0, mouth_form: 0.0, is_speaking: false });
      });
    },
    [stopAudioPlayback]
  );

  // Lip-sync frame update loop during assistant speech playback or active call
  useEffect(() => {
    if (!playingMessageId && callMode !== "ACTIVE") return;

    let animId: number;
    const loop = () => {
      if (callMode === "ACTIVE" && realtimeLipSyncRef.current) {
        const mouth = realtimeLipSyncRef.current.updateFrame();
        setLipSyncState(mouth);
      } else if (lipSyncAnalyzerRef.current) {
        const mouth = lipSyncAnalyzerRef.current.updateFrame();
        setLipSyncState(mouth);
      }
      animId = requestAnimationFrame(loop);
    };

    animId = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(animId);
    };
  }, [playingMessageId, callMode]);

  // Layout & modal state
  const [isDrawerOpen, setIsDrawerOpen] = useState<boolean>(true);
  const [drawerTab, setDrawerTab] = useState<CompanionDrawerTab>("chat");
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);
  const [isGenesisModalOpen, setIsGenesisModalOpen] = useState<boolean>(false);
  const [isPresentationSandboxOpen, setIsPresentationSandboxOpen] = useState<boolean>(false);
  const [isDevInspectorOpen, setIsDevInspectorOpen] = useState<boolean>(false);
  const [isLive2DModalOpen, setIsLive2DModalOpen] = useState<boolean>(false);
  const [highlightedMessageId, setHighlightedMessageId] = useState<string | null>(null);

  // Presentation preferences (Multi-bubble vs Single-block & WeChat emojis)
  const [bubbleMode, setBubbleMode] = useState<"multi" | "single">(() => {
    return (localStorage.getItem("aevum_bubble_mode") as "multi" | "single") || "multi";
  });
  const [emojiRenderingEnabled, setEmojiRenderingEnabled] = useState<boolean>(() => {
    return localStorage.getItem("aevum_emoji_rendering") !== "false";
  });

  const handleBubbleModeChange = useCallback((mode: "multi" | "single") => {
    setBubbleMode(mode);
    localStorage.setItem("aevum_bubble_mode", mode);
  }, []);

  const handleEmojiRenderingChange = useCallback((enabled: boolean) => {
    setEmojiRenderingEnabled(enabled);
    localStorage.setItem("aevum_emoji_rendering", String(enabled));
  }, []);

  // Global hotkey: Ctrl+Shift+D or Cmd+Shift+D toggles Developer Cognitive Inspector
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === "D" || e.key === "d")) {
        e.preventDefault();
        setIsDevInspectorOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

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
  const handleCreateNewConversation = useCallback(async (): Promise<string | null> => {
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
      return created.id;
    } catch (err: unknown) {
      setChatError(err instanceof Error ? err.message : "Failed to create conversation");
      return null;
    }
  }, [refreshCompanionState]);

  // Phase 17: Character Genesis completion handler
  const handleGenesisComplete = useCallback(
    async (_res: CharacterCreationResponse) => {
      await refreshCompanionState();
      // Initialize fresh chat context upon new awakening
      await handleCreateNewConversation();
      setIsDrawerOpen(true);
      setDrawerTab("chat");
      window.dispatchEvent(new CustomEvent("aevum-character-genesis-completed", { detail: _res }));
    },
    [refreshCompanionState, handleCreateNewConversation]
  );

  // Phase 13.4: Realtime Call Controls
  const handleStartCall = useCallback(async () => {
    if (callMode === "ACTIVE" || callMode === "CONNECTING") return;
    try {
      setCallError(null);
      setCallMode("CONNECTING");
      let convId = activeConversationId;
      if (!convId) {
        convId = await handleCreateNewConversation();
      }
      if (!convId) {
        setCallError("Could not initialize conversation for call");
        setCallMode("IDLE");
        return;
      }
      const session = await api.createCallSession(convId);
      setActiveCallSessionId(session.session_id);
      setActiveGenerationId(session.active_generation_id);

      const wsUrl = api.getCallStreamWsUrl(session.session_id, convId);
      const ws = new WebSocket(wsUrl);
      callWsRef.current = ws;

      ws.onopen = () => {
        setCallMode("ACTIVE");
      };

      ws.onmessage = (event) => {
        if (typeof event.data === "string") {
          try {
            const payload = JSON.parse(event.data);
            if (payload.event_type === "SESSION_STARTED") {
              setCallMode("ACTIVE");
              if (typeof payload.active_generation_id === "number") {
                setActiveGenerationId(payload.active_generation_id);
                realtimeLipSyncRef.current?.resetLatch(payload.active_generation_id);
              }
            } else if (payload.event_type === "TRANSCRIPT_EVENT") {
              const tEvent = payload as TranscriptEventPayload;
              if (tEvent.lifecycle_state === "PARTIAL") {
                setPartialTranscript(tEvent.text);
              } else if (tEvent.lifecycle_state === "COMMITTED") {
                setPartialTranscript("");
                if (convId) {
                  loadConversation(convId);
                }
                refreshCompanionState();
              }
            } else if (payload.event_type === "INTERRUPT_FLUSH") {
              const flush = payload as InterruptFlushPayload;
              setActiveGenerationId(flush.generation_id);
              if (realtimeLipSyncRef.current) {
                realtimeLipSyncRef.current.triggerBargeIn(flush.generation_id);
              }
              stopAudioPlayback();
              setPartialTranscript("");
            } else if (payload.event_type === "VISUAL_DIRECTIVE") {
              const directive = payload as VisualDirectivePayload;
              if (directive.mouth_open_override !== undefined && directive.mouth_open_override !== null) {
                setLipSyncState({
                  mouth_open_y: Math.max(0.0, Math.min(1.0, directive.mouth_open_override)),
                  mouth_form: 0.0,
                  is_speaking: directive.is_speaking,
                });
              }
            } else if (payload.event_type === "ERROR_EVENT") {
              const errEvent = payload as RealtimeErrorPayload;
              setCallError(errEvent.message);
            } else if (payload.event_type === "SESSION_CLOSED") {
              if (callWsRef.current) {
                callWsRef.current.close();
                callWsRef.current = null;
              }
              setCallMode("IDLE");
              setPartialTranscript("");
              stopAudioPlayback();
            }
          } catch (e) {
            console.warn("Error parsing control websocket event:", e);
          }
        }
      };

      ws.onerror = (e) => {
        console.warn("Call stream WebSocket error:", e);
        setCallError("Realtime connection error");
      };

      ws.onclose = () => {
        setCallMode((prev) => {
          if (prev === "ACTIVE") {
            // 13.2-LOCK-A: Enter reconnecting state with 30s lease
            return "RECONNECTING";
          }
          return "IDLE";
        });
      };
      // Capture microphone stream using selected audio input device
      try {
        const inputDeviceId = localStorage.getItem("aevum_selected_audio_input_id");
        const micConstraints: MediaStreamConstraints = {
          audio: inputDeviceId && inputDeviceId !== "default" ? { deviceId: { exact: inputDeviceId } } : true,
        };
        const micStream = await navigator.mediaDevices.getUserMedia(micConstraints);
        callMicStreamRef.current = micStream;
      } catch (micErr) {
        console.warn("[handleStartCall] Microphone capture error or permission denied:", micErr);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to start realtime call";
      setCallError(msg);
      setCallMode("IDLE");
    }
  }, [activeConversationId, callMode, handleCreateNewConversation, loadConversation, refreshCompanionState, stopAudioPlayback]);

  const handleEndCall = useCallback(() => {
    if (callMicStreamRef.current) {
      callMicStreamRef.current.getTracks().forEach((track) => track.stop());
      callMicStreamRef.current = null;
    }
    if (callWsRef.current) {
      if (callWsRef.current.readyState === WebSocket.OPEN) {
        try {
          callWsRef.current.send(
            JSON.stringify({
              event_type: "SESSION_CLOSED",
              session_id: activeCallSessionId,
              reason: "user_hangup",
            })
          );
        } catch {
          // ignore socket close errors
        }
      }
      callWsRef.current.close();
      callWsRef.current = null;
    }
    setCallMode("IDLE");
    setPartialTranscript("");
    stopAudioPlayback();
  }, [activeCallSessionId, stopAudioPlayback]);

  const handleBargeIn = useCallback(() => {
    // Instant client-local clamp (ADR-024 Lock 4: P95 <= 20ms)
    stopAudioPlayback();
    setPartialTranscript("");
    if (realtimeLipSyncRef.current) {
      realtimeLipSyncRef.current.triggerBargeIn(activeGenerationId);
    }
    if (callWsRef.current && callWsRef.current.readyState === WebSocket.OPEN) {
      callWsRef.current.send(
        JSON.stringify({
          event_type: "BARGE_IN",
          session_id: activeCallSessionId,
          generation_id: activeGenerationId,
          reason: "user_barge_in",
        })
      );
    }
    setActiveGenerationId((prev) => prev + 1);
  }, [activeCallSessionId, activeGenerationId, stopAudioPlayback]);

  const handleToggleMute = useCallback(() => {
    setIsMuted((prev) => {
      const nextMuted = !prev;
      if (callMicStreamRef.current) {
        callMicStreamRef.current.getAudioTracks().forEach((track) => {
          track.enabled = !nextMuted;
        });
      }
      return nextMuted;
    });
  }, []);

  // Cleanup WebSocket and microphone on unmount
  useEffect(() => {
    return () => {
      if (callMicStreamRef.current) {
        callMicStreamRef.current.getTracks().forEach((track) => track.stop());
        callMicStreamRef.current = null;
      }
      if (callWsRef.current) {
        callWsRef.current.close();
        callWsRef.current = null;
      }
    };
  }, []);

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

  // Refresh debug data when about tab is viewed in drawer
  useEffect(() => {
    if (isDrawerOpen && drawerTab === "about") {
      refreshDebugData();
    }
  }, [isDrawerOpen, drawerTab, refreshDebugData]);

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

  // Send message with retry and continuous queueing support
  const handleSendMessage = async (textToSend?: string) => {
    stopAudioPlayback();
    const content = (textToSend !== undefined ? textToSend : inputMessage).trim();
    if (!content) return;

    if (textToSend === undefined) {
      setInputMessage("");
    }

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

    // If Aevum is currently generating, queue message and optimistically render in chat
    if (isGenerating) {
      messageQueueRef.current.push(content);
      const queuedUserMsg: MessageItem = {
        id: `queued-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        conversation_id: convId,
        role: "user",
        content: content,
        created_at: new Date().toISOString(),
      };
      setConversation((prev) => ({
        id: convId!,
        created_at: prev?.created_at || new Date().toISOString(),
        updated_at: new Date().toISOString(),
        messages: [...(prev?.messages || []), queuedUserMsg],
      }));
      return;
    }

    setLastFailedMessage(null);
    setChatError(null);
    setIsGenerating(true);

    // Optimistically render user message immediately
    const tempUserMsgId = `temp-${Date.now()}`;
    setConversation((prev) => {
      // If already displayed as queued message, keep it
      const alreadyShown = prev?.messages.some(
        (m) => m.role === "user" && m.content === content && m.id.startsWith("queued-")
      );
      if (alreadyShown) {
        return prev;
      }
      const tempUserMsg: MessageItem = {
        id: tempUserMsgId,
        conversation_id: convId!,
        role: "user",
        content: content,
        created_at: new Date().toISOString(),
      };
      return {
        id: convId!,
        created_at: prev?.created_at || new Date().toISOString(),
        updated_at: new Date().toISOString(),
        messages: [...(prev?.messages || []), tempUserMsg],
      };
    });

    try {
      const res = await api.sendMessage(convId, content);

      // Successfully generated and persisted
      if (res.assistant_response) {
        setConversation((prev) => {
          if (!prev) return prev;
          const currentMessages = prev.messages || [];

          // Find the exact placeholder index (either tempUserMsgId or the first matching queued message)
          const targetIdx = currentMessages.findIndex(
            (m) => m.id === tempUserMsgId || (m.id.startsWith("queued-") && m.content === content)
          );

          if (targetIdx !== -1) {
            const before = currentMessages.slice(0, targetIdx);
            const after = currentMessages.slice(targetIdx + 1);
            return {
              ...prev,
              updated_at: new Date().toISOString(),
              messages: [...before, res.message, res.assistant_response!, ...after],
            };
          }

          return {
            ...prev,
            updated_at: new Date().toISOString(),
            messages: [...currentMessages, res.message, res.assistant_response!],
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

      if (isDrawerOpen && drawerTab === "about") {
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
      // Automatically drain queued messages in aggregate to prevent fragmented single-character interleaving
      if (messageQueueRef.current.length > 0) {
        const queuedBurst = messageQueueRef.current.splice(0);
        const combined = queuedBurst.join("\n").trim();
        if (combined) {
          setTimeout(() => {
            handleSendMessage(combined);
          }, 150);
        }
      }
    }
  };

  // Push-To-Talk voice message submission (Phase 10.5)
  const handleSendVoiceMessage = async (audioBase64: string, durationMs: number) => {
    stopAudioPlayback();
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

    setChatError(null);
    setIsGenerating(true);

    try {
      const res = await api.sendVoiceMessage(convId, {
        audio_base64: audioBase64,
        format: "WAV",
        sample_rate_hz: 16000,
        channels: "MONO",
        duration_ms: durationMs,
        user_consent_granted: true,
        input_mode: "PTT",
        synthesize_reply_audio: true,
      });

      // Update conversation with user message and assistant reply
      setConversation((prev) => {
        const messages = [...(prev?.messages || [])];
        messages.push(res.message);
        if (res.assistant_response) {
          const assistantWithAudio: MessageItem = {
            ...res.assistant_response,
            audio_cache_key: res.audio_cache_key,
            audio_status: res.audio_status,
          };
          messages.push(assistantWithAudio);
        }
        return {
          id: convId!,
          created_at: prev?.created_at || new Date().toISOString(),
          updated_at: new Date().toISOString(),
          messages,
        };
      });

      // Autoplay spoken audio if enabled and available
      const autoplay = localStorage.getItem("aevum_voice_autoplay") !== "false";
      if (autoplay && res.audio_cache_key && res.assistant_response) {
        const audioUrl = api.getCachedAudioUrl(res.audio_cache_key);
        playAudio(res.assistant_response.id, audioUrl);
      }

      // Refresh companion state
      refreshCompanionState();
      setTimeout(() => {
        api.getMemories().then(setMemories).catch(() => {});
      }, 1500);

      if (isDrawerOpen && drawerTab === "about") {
        refreshDebugData();
      }
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "Failed to process voice message";
      setChatError(errMsg);
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
    if (isDrawerOpen && drawerTab === "about") {
      refreshDebugData();
    }
  };

  // Phase 11.2 / 11.5: Unidirectional Affective Visual Mapping (Mind -> Render Instructions)
  const visualExpression = useMemo(() => {
    return deriveVisualExpression(
      characterState?.emotion?.type,
      characterState?.emotion?.intensity,
      characterState?.mood,
      isGenerating
    );
  }, [
    characterState?.emotion?.type,
    characterState?.emotion?.intensity,
    characterState?.mood,
    isGenerating,
  ]);

  const visualMotion = useMemo(() => {
    return deriveVisualMotion(
      characterState?.mood,
      playingMessageId !== null,
      isGenerating
    );
  }, [characterState?.mood, playingMessageId, isGenerating]);

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
        onNewConversation={async () => {
          await handleCreateNewConversation();
          setIsDrawerOpen(true);
          setDrawerTab("chat");
        }}
        isSidebarOpen={isDrawerOpen}
        onToggleSidebar={() => setIsDrawerOpen((prev) => !prev)}
        isStageVisible={isStageVisible}
        onToggleStage={handleToggleStage}
        activeTab={
          drawerTab === "journey"
            ? "biography"
            : drawerTab === "bond"
            ? "relationship"
            : drawerTab === "memories"
            ? "memories"
            : "about"
        }
        onSelectTab={(tab) => {
          if (tab === "debug") {
            setIsDevInspectorOpen(true);
            return;
          }
          setIsDrawerOpen(true);
          if (tab === "biography") setDrawerTab("journey");
          else if (tab === "relationship") setDrawerTab("bond");
          else if (tab === "memories") setDrawerTab("memories");
          else setDrawerTab("about");
        }}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onOpenGenesis={() => setIsGenesisModalOpen(true)}
        onOpenPresentationSandbox={() => setIsPresentationSandboxOpen(true)}
        onOpenDevInspector={() => setIsDevInspectorOpen(true)}
      />

      <div className="companion-main-body">
        {/* Phase 13.4: Desktop Product Shell Center Stage Embodiment */}
        {isStageVisible && (
          <main className="companion-center-stage">
            <CompanionStage
              characterName={characterState?.name || "Aevum"}
              characterState={characterState}
              life={life}
              visualExpression={visualExpression}
              visualMotion={visualMotion}
              lipSyncState={lipSyncState}
              isBackendReady={backendStatus.ready}
              isGenerating={isGenerating}
              isInCall={callMode === "ACTIVE" || callMode === "CONNECTING"}
              callMode={callMode}
            />

            {/* Floating Call HUD */}
            <CallHUD
              callMode={callMode}
              activeGenerationId={activeGenerationId}
              partialTranscript={partialTranscript}
              isMuted={isMuted}
              onToggleMute={handleToggleMute}
              onStartCall={handleStartCall}
              onEndCall={handleEndCall}
              onBargeIn={handleBargeIn}
              errorMessage={callError}
              characterName={characterState?.name || "Aevum"}
              onSendVoiceMessage={handleSendVoiceMessage}
              isCompanionSpeaking={playingMessageId !== null || lipSyncState.is_speaking}
            />
          </main>
        )}

        {/* Sliding Drawer for Chat / Journey / Memories / Bond / Status */}
        <CompanionDrawer
          isOpen={isDrawerOpen}
          onToggleOpen={() => setIsDrawerOpen((prev) => !prev)}
          activeTab={drawerTab}
          onSelectTab={setDrawerTab}
          conversation={conversation}
          isGenerating={isGenerating}
          inputMessage={inputMessage}
          onInputChange={setInputMessage}
          onSendMessage={(text?: string) => {
            void handleSendMessage(text);
          }}
          chatError={chatError}
          onRetry={lastFailedMessage ? () => handleSendMessage(lastFailedMessage) : undefined}
          highlightedMessageId={highlightedMessageId}
          voiceConsentGranted={localStorage.getItem("aevum_voice_consent_granted") === "true"}
          onSendVoiceMessage={handleSendVoiceMessage}
          playingMessageId={playingMessageId}
          onPlayAudio={(msg) => {
            if (msg.audio_cache_key) {
              playAudio(msg.id, api.getCachedAudioUrl(msg.audio_cache_key));
            }
          }}
          onStopAudio={stopAudioPlayback}
          onOpenSettings={() => setIsSettingsOpen(true)}
          bubbleMode={bubbleMode}
          emojiRenderingEnabled={emojiRenderingEnabled}
          onSelectConversation={(id) => {
            setActiveConversationId(id);
            localStorage.setItem(LOCAL_STORAGE_CONV_KEY, id);
            loadConversation(id);
          }}
          onNewConversation={async () => {
            await handleCreateNewConversation();
          }}
          characterState={characterState}
          relationship={relationship}
          life={life}
          memories={memories}
          debugData={debugData}
          onDeleteMemory={handleDeleteMemory}
        />
      </div>

      <DesktopSettingsView
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        characterId="aevum"
        onOpenGenesis={() => setIsGenesisModalOpen(true)}
        bubbleMode={bubbleMode}
        onBubbleModeChange={handleBubbleModeChange}
        emojiRenderingEnabled={emojiRenderingEnabled}
        onEmojiRenderingChange={handleEmojiRenderingChange}
        onOpenLive2DModal={() => setIsLive2DModalOpen(true)}
        onOpenDevInspector={() => setIsDevInspectorOpen(true)}
      />

      <Live2DModelModal
        isOpen={isLive2DModalOpen}
        onClose={() => setIsLive2DModalOpen(false)}
        onModelChanged={() => {
          window.dispatchEvent(new Event("aevum-avatar-updated"));
        }}
      />

      <DevCognitiveInspector
        isOpen={isDevInspectorOpen}
        onClose={() => setIsDevInspectorOpen(false)}
        bubbleMode={bubbleMode}
        onBubbleModeChange={handleBubbleModeChange}
        emojiRenderingEnabled={emojiRenderingEnabled}
        onEmojiRenderingChange={handleEmojiRenderingChange}
        onOpenGenesis={() => setIsGenesisModalOpen(true)}
        onOpenPresentationSandbox={() => setIsPresentationSandboxOpen(true)}
        onStateModified={() => {
          refreshCompanionState();
          api.getMemories().then(setMemories).catch(() => {});
        }}
      />

      <CharacterGenesisModal
        isOpen={isGenesisModalOpen}
        onClose={() => setIsGenesisModalOpen(false)}
        onGenesisComplete={handleGenesisComplete}
      />

      {isPresentationSandboxOpen && (
        <div
          className="genesis-modal-backdrop"
          onClick={() => setIsPresentationSandboxOpen(false)}
        >
          <div
            className="genesis-modal-container"
            style={{ maxWidth: "720px", width: "95%" }}
            onClick={(e) => e.stopPropagation()}
          >
            <PresentationSandbox onClose={() => setIsPresentationSandboxOpen(false)} />
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
