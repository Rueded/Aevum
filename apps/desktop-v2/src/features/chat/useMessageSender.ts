import { useConversationStore } from "../../stores/useConversationStore";
import { useChatStore } from "../../stores/useChatStore";
import { useCharacterStore } from "../../stores/useCharacterStore";
import { useVisualStore } from "../../stores/useVisualStore";
import { useSettingsStore } from "../../stores/useSettingsStore";
import { conversationsApi } from "../../api/conversations";
import { deriveVisualExpression } from "../../visual/visualMappers";
import type { MessageItem } from "../../types";

export function useMessageSender(
  onPlayAudio?: (message: MessageItem) => void
) {
  const activeConversationId = useConversationStore((s) => s.activeConversationId);
  const createConversation = useConversationStore((s) => s.createConversation);
  const addOptimisticMessage = useConversationStore((s) => s.addOptimisticMessage);
  const selectConversation = useConversationStore((s) => s.selectConversation);

  const inputMessage = useChatStore((s) => s.inputMessage);
  const setInputMessage = useChatStore((s) => s.setInputMessage);
  const isGenerating = useChatStore((s) => s.isGenerating);
  const setIsGenerating = useChatStore((s) => s.setIsGenerating);
  const setChatError = useChatStore((s) => s.setChatError);
  const setLastFailedMessage = useChatStore((s) => s.setLastFailedMessage);
  const enqueueMessage = useChatStore((s) => s.enqueueMessage);
  const drainMessageQueue = useChatStore((s) => s.drainMessageQueue);

  const fetchCharacterState = useCharacterStore((s) => s.fetchCharacterState);
  const fetchRelationship = useCharacterStore((s) => s.fetchRelationship);
  const fetchLife = useCharacterStore((s) => s.fetchLife);
  const fetchMemories = useCharacterStore((s) => s.fetchMemories);
  const setVisualExpression = useVisualStore((s) => s.setVisualExpression);
  const autoPlayVoice = useSettingsStore((s) => s.autoPlayVoice);

  const sendMessage = async (overrideText?: string) => {
    const textToSend = (overrideText !== undefined ? overrideText : inputMessage).trim();
    if (!textToSend) return;

    // Ensure we have an active conversation
    let convId = activeConversationId;
    if (!convId) {
      convId = await createConversation();
    }

    // Clear input field if we sent the current input
    if (overrideText === undefined) {
      setInputMessage("");
    }

    // If already generating, enqueue message to prevent interleaved single-character turns
    if (isGenerating) {
      const queuedUserMsg: MessageItem = {
        id: `queued-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
        conversation_id: convId,
        role: "user",
        content: textToSend,
        created_at: new Date().toISOString(),
      };
      addOptimisticMessage(queuedUserMsg);
      enqueueMessage(textToSend);
      return;
    }

    // Optimistically add user message
    const tempUserMsgId = `temp-user-${Date.now()}`;
    const optimisticUserMsg: MessageItem = {
      id: tempUserMsgId,
      conversation_id: convId,
      role: "user",
      content: textToSend,
      created_at: new Date().toISOString(),
    };
    addOptimisticMessage(optimisticUserMsg);

    setIsGenerating(true);
    setChatError(null);

    try {
      const res = await conversationsApi.sendMessage(convId, textToSend);

      // Reload conversation to get canonical DB IDs and response
      await selectConversation(convId);

      // Post-turn companion mind synchronizations
      fetchCharacterState();
      fetchRelationship();
      fetchLife();
      setTimeout(() => fetchMemories(), 1500);

      // Visual emotion expression synchronization
      if (res.assistant_response) {
        const expr = deriveVisualExpression(
          undefined,
          undefined,
          res.assistant_response.content
        );
        setVisualExpression(expr);

        // Auto-play TTS voice reply if available
        if (autoPlayVoice && res.assistant_response.audio_cache_key && onPlayAudio) {
          onPlayAudio(res.assistant_response);
        }
      }
    } catch (err: any) {
      console.error("Failed to send message:", err);
      const errMsg = err?.message || "发送失败，请检查网络或后端状态";
      setChatError(errMsg);
      setLastFailedMessage(textToSend);
    } finally {
      setIsGenerating(false);

      // Check if user queued additional rapid bursts while waiting
      const pendingUnifiedText = drainMessageQueue();
      if (pendingUnifiedText) {
        setTimeout(() => sendMessage(pendingUnifiedText), 150);
      }
    }
  };

  const retryLastFailed = () => {
    const lastFailed = useChatStore.getState().lastFailedMessage;
    if (lastFailed) {
      setChatError(null);
      setLastFailedMessage(null);
      sendMessage(lastFailed);
    }
  };

  return { sendMessage, retryLastFailed };
}
