import { useEffect, useRef } from "react";
import { api } from "../../api";
import { useChatStore } from "../../stores/useChatStore";
import { useConversationStore } from "../../stores/useConversationStore";
import type { MessageItem } from "../../types";

export function useIdleNudge(onPlayAudio?: (message: MessageItem) => void) {
  const activeConversationId = useConversationStore((s) => s.activeConversationId);
  const currentConversation = useConversationStore((s) => s.currentConversation);
  const addOptimisticMessage = useConversationStore((s) => s.addOptimisticMessage);
  const isGenerating = useChatStore((s) => s.isGenerating);

  const isCheckingRef = useRef(false);

  useEffect(() => {
    if (!activeConversationId) return;

    const interval = setInterval(async () => {
      if (isCheckingRef.current || isGenerating) return;

      const conv = useConversationStore.getState().currentConversation;
      if (!conv || !conv.messages || conv.messages.length === 0) return;

      const lastMsg = conv.messages[conv.messages.length - 1];
      if (lastMsg.role !== "assistant") return;

      // Check if last message was already a nudge (two consecutive assistant messages)
      if (
        conv.messages.length >= 2 &&
        conv.messages[conv.messages.length - 2].role === "assistant"
      ) {
        return;
      }

      // Check client-side elapsed time first before pinging
      const msgTime = new Date(lastMsg.created_at).getTime();
      const now = Date.now();
      const elapsedSeconds = (now - msgTime) / 1000;
      if (elapsedSeconds < 70) return;

      try {
        isCheckingRef.current = true;
        const res = await api.checkIdleNudge(activeConversationId, 70);
        if (res && res.nudged && res.message) {
          const newMsg: MessageItem = {
            id: res.message.id,
            conversation_id: res.message.conversation_id,
            role: "assistant",
            content: res.message.content,
            created_at: res.message.created_at,
          };
          addOptimisticMessage(newMsg);
          if (onPlayAudio) {
            onPlayAudio(newMsg);
          }
        }
      } catch (err) {
        // Silently ignore network/transient failures during idle check
        console.debug("Idle nudge check skipped:", err);
      } finally {
        isCheckingRef.current = false;
      }
    }, 20000);

    return () => clearInterval(interval);
  }, [activeConversationId, isGenerating, addOptimisticMessage, onPlayAudio]);
}
