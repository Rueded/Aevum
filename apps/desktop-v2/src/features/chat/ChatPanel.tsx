import React from "react";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { useMessageSender } from "./useMessageSender";
import { useIdleNudge } from "./useIdleNudge";
import { useCharacterStore } from "../../stores/useCharacterStore";
import { useConversationStore } from "../../stores/useConversationStore";
import type { MessageItem } from "../../types";
import styles from "./ChatPanel.module.css";

interface ChatPanelProps {
  onPlayAudio?: (message: MessageItem) => void;
  onStopAudio?: () => void;
  onSendVoiceMessage?: (audioBase64: string, durationMs: number) => Promise<void>;
  onOpenHistory?: () => void;
  onOpenSettings?: () => void;
}

export const ChatPanel: React.FC<ChatPanelProps> = ({
  onPlayAudio,
  onStopAudio,
  onSendVoiceMessage,
  onOpenHistory,
  onOpenSettings,
}) => {
  const characterState = useCharacterStore((s) => s.characterState);
  const relationship = useCharacterStore((s) => s.relationship);
  const characterName = characterState?.name || "苏棠";
  const createConversation = useConversationStore((s) => s.createConversation);

  const { sendMessage, retryLastFailed } = useMessageSender(onPlayAudio);
  useIdleNudge(onPlayAudio);

  return (
    <div className={styles.panel}>
      <div className={styles.subHeader}>
        <div className={styles.titleArea}>
          <span className={styles.dot} />
          <span className={styles.name}>{characterName}</span>
          <span
            style={{
              marginLeft: "8px",
              padding: "2px 8px",
              borderRadius: "10px",
              fontSize: "11px",
              fontWeight: 500,
              background: "rgba(236, 72, 153, 0.15)",
              color: "#f472b6",
              border: "1px solid rgba(236, 72, 153, 0.3)",
              cursor: "pointer",
            }}
            title={`好感度: ${Math.round((relationship?.affection ?? 0.64) * 100)}% · 信任度: ${Math.round((relationship?.trust ?? 0.8) * 100)}%`}
          >
            💖 {Math.round((relationship?.affection ?? 0.64) * 100)}%
          </span>
        </div>

        <div className={styles.actions}>
          {onOpenHistory && (
            <button
              type="button"
              className={styles.actionBtn}
              onClick={onOpenHistory}
              title="查看与管理历史会话"
            >
              📜 历史会话
            </button>
          )}
          <button
            type="button"
            className={styles.actionBtn}
            onClick={() => createConversation()}
            title="开启全新会话"
          >
            ＋ 新会话
          </button>
        </div>
      </div>

      <MessageList
        onPlayAudio={onPlayAudio}
        onStopAudio={onStopAudio}
        onRetry={retryLastFailed}
      />

      <ChatInput
        onSendMessage={sendMessage}
        onSendVoiceMessage={onSendVoiceMessage}
        onStopAudio={onStopAudio}
        onOpenSettings={onOpenSettings}
      />
    </div>
  );
};
