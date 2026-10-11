import { useRef, useCallback, useEffect } from "react";
import { useCallStore } from "../stores/useCallStore";
import { useConversationStore } from "../stores/useConversationStore";
import { useVisualStore } from "../stores/useVisualStore";
import { callApi } from "../api/call";
import { deriveVisualExpression } from "../visual/visualMappers";
import type { RealtimeControlEventType } from "../types";

export function useCallManager() {
  const wsRef = useRef<WebSocket | null>(null);
  const activeConversationId = useConversationStore((s) => s.activeConversationId);
  const addOptimisticMessage = useConversationStore((s) => s.addOptimisticMessage);

  const callMode = useCallStore((s) => s.callMode);
  const setCallMode = useCallStore((s) => s.setCallMode);
  const activeCallSessionId = useCallStore((s) => s.activeCallSessionId);
  const setActiveCallSessionId = useCallStore((s) => s.setActiveCallSessionId);
  const setActiveGenerationId = useCallStore((s) => s.setActiveGenerationId);
  const setPartialTranscript = useCallStore((s) => s.setPartialTranscript);
  const setCallError = useCallStore((s) => s.setCallError);
  const setIsCompanionSpeaking = useCallStore((s) => s.setIsCompanionSpeaking);
  const resetCall = useCallStore((s) => s.resetCall);

  const setVisualExpression = useVisualStore((s) => s.setVisualExpression);

  const endCall = useCallback(() => {
    if (wsRef.current) {
      try {
        wsRef.current.send(JSON.stringify({ event_type: "SESSION_CLOSED" }));
        wsRef.current.close();
      } catch {
        // Ignore
      }
      wsRef.current = null;
    }
    resetCall();
  }, [resetCall]);

  const triggerBargeIn = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          event_type: "BARGE_IN",
          session_id: activeCallSessionId,
        })
      );
    }
  }, [activeCallSessionId]);

  const startCall = useCallback(async () => {
    if (!activeConversationId) return;

    setCallMode("CONNECTING");
    setCallError(null);

    try {
      const session = await callApi.createSession(activeConversationId);
      setActiveCallSessionId(session.session_id);
      setActiveGenerationId(session.active_generation_id);

      const wsUrl = callApi.getStreamWsUrl(session.session_id, activeConversationId);
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setCallMode("ACTIVE");
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          const type: RealtimeControlEventType = payload.event_type;

          if (type === "TRANSCRIPT_EVENT") {
            setPartialTranscript(payload.text || "");
            if (payload.is_final && payload.text) {
              addOptimisticMessage({
                id: `call-msg-${Date.now()}`,
                conversation_id: activeConversationId,
                role: "assistant",
                content: payload.text,
                created_at: new Date().toISOString(),
              });
            }
          } else if (type === "VISUAL_DIRECTIVE") {
            setIsCompanionSpeaking(Boolean(payload.is_speaking));
            if (payload.expression_archetype) {
              const expr = deriveVisualExpression(
                payload.expression_archetype,
                payload.intensity
              );
              setVisualExpression(expr);
            }
          } else if (type === "INTERRUPT_FLUSH") {
            setPartialTranscript("");
            setIsCompanionSpeaking(false);
          } else if (type === "ERROR_EVENT") {
            setCallError(payload.message || "通话发生错误");
          }
        } catch {
          // Ignored
        }
      };

      ws.onerror = () => {
        setCallError("通话连接异常中断");
        setCallMode("RECONNECTING");
      };

      ws.onclose = () => {
        setCallMode("IDLE");
      };
    } catch (err: any) {
      console.error("Failed to start voice call session:", err);
      setCallError(err?.message || "无法建立语音通话");
      setCallMode("IDLE");
    }
  }, [
    activeConversationId,
    setCallMode,
    setCallError,
    setActiveCallSessionId,
    setActiveGenerationId,
    setPartialTranscript,
    setIsCompanionSpeaking,
    addOptimisticMessage,
    setVisualExpression,
  ]);

  useEffect(() => {
    return () => {
      endCall();
    };
  }, [endCall]);

  return {
    callMode,
    startCall,
    endCall,
    triggerBargeIn,
  };
}
