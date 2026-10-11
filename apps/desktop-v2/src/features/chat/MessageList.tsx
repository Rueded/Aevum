import React, { useEffect, useRef } from "react";
import { MessageBubble } from "./MessageBubble";
import { useConversationStore } from "../../stores/useConversationStore";
import { useCharacterStore } from "../../stores/useCharacterStore";
import { useChatStore } from "../../stores/useChatStore";
import type { MessageItem } from "../../types";
import styles from "./MessageList.module.css";

interface MessageListProps {
  onPlayAudio?: (message: MessageItem) => void;
  onStopAudio?: () => void;
  onRetry?: () => void;
}

export const MessageList: React.FC<MessageListProps> = ({
  onPlayAudio,
  onStopAudio,
  onRetry,
}) => {
  const currentConversation = useConversationStore((s) => s.currentConversation);
  const characterState = useCharacterStore((s) => s.characterState);
  const isGenerating = useChatStore((s) => s.isGenerating);
  const chatError = useChatStore((s) => s.chatError);
  const highlightedMessageId = useChatStore((s) => s.highlightedMessageId);
  const setInputMessage = useChatStore((s) => s.setInputMessage);

  const messages = currentConversation?.messages || [];
  const characterName = characterState?.name || "苏棠";
  const avatarLetter = characterName.charAt(0) || "棠";

  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll on new message or generation change
  useEffect(() => {
    if (!highlightedMessageId && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages.length, isGenerating, highlightedMessageId]);

  // Deep-link scroll to highlighted message
  useEffect(() => {
    if (highlightedMessageId) {
      const el = document.getElementById(`msg-${highlightedMessageId}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }
  }, [highlightedMessageId]);

  return (
    <div className={styles.container} ref={scrollRef}>
      {messages.length === 0 ? (
        <div className={styles.emptyState}>
          <div className={styles.emptyAvatar}>{avatarLetter}</div>
          <h3 className={styles.emptyTitle}>与 {characterName} 的日常对话</h3>
          <p className={styles.emptyDesc}>
            {characterName} 拥有真实的作息规律、起伏情绪与长久记忆。
            跟她打个招呼，或者聊聊今天发生的事吧。
          </p>
          <div className={styles.starterChips}>
            <button
              className={styles.chipBtn}
              onClick={() => setInputMessage(`${characterName}，你今天都在忙些什么呀？`)}
            >
              "你今天都在忙些什么呀？"
            </button>
            <button
              className={styles.chipBtn}
              onClick={() => setInputMessage("现在心情怎么样？有发生什么好玩的事吗？")}
            >
              "现在心情怎么样？"
            </button>
            <button
              className={styles.chipBtn}
              onClick={() => setInputMessage("你平时喜欢听什么音乐或者玩什么游戏呀？")}
            >
              "平时喜欢听什么音乐或玩游戏？"
            </button>
          </div>
        </div>
      ) : (
        messages.map((msg) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            onPlayAudio={onPlayAudio}
            onStopAudio={onStopAudio}
          />
        ))
      )}

      {isGenerating && (
        <div className={styles.typingRow}>
          <div className={styles.emptyAvatar} style={{ width: 32, height: 32, fontSize: 14 }}>
            {avatarLetter}
          </div>
          <div className={styles.typingBubble}>
            <span className={styles.dot} />
            <span className={styles.dot} />
            <span className={styles.dot} />
          </div>
        </div>
      )}

      {chatError && (
        <div className={styles.errorBanner}>
          <span>{chatError}</span>
          {onRetry && (
            <button className={styles.retryBtn} onClick={onRetry}>
              重试
            </button>
          )}
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
};
