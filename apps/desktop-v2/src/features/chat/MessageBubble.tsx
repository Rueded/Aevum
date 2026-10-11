import React from "react";
import type { MessageItem } from "../../types";
import { renderContentWithStickersAndEmojis } from "../../presentation/stickerRenderer";
import { useSettingsStore } from "../../stores/useSettingsStore";
import { useCharacterStore } from "../../stores/useCharacterStore";
import { useChatStore } from "../../stores/useChatStore";
import styles from "./MessageBubble.module.css";

interface MessageBubbleProps {
  message: MessageItem;
  onPlayAudio?: (message: MessageItem) => void;
  onStopAudio?: () => void;
}

function formatTime(isoString?: string): string {
  if (!isoString) return "";
  try {
    let normalized = isoString;
    if (!normalized.endsWith("Z") && !/[+-]\d{2}:\d{2}$/.test(normalized)) {
      normalized = normalized.replace(" ", "T") + "Z";
    }
    const d = new Date(normalized);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({
  message,
  onPlayAudio,
  onStopAudio,
}) => {
  const isUser = message.role === "user";
  const characterState = useCharacterStore((s) => s.characterState);
  const characterName = characterState?.name || "苏棠";
  const avatarLetter = characterName.charAt(0) || "棠";

  const bubbleMode = useSettingsStore((s) => s.bubbleMode);
  const emojiEnabled = useSettingsStore((s) => s.emojiRenderingEnabled);
  const showEmojiLabel = useSettingsStore((s) => s.showEmojiLabel);
  const useStickers = useSettingsStore((s) => s.useStickers);
  const standaloneLine = useSettingsStore((s) => s.stickerStandaloneLine);

  const playingMessageId = useChatStore((s) => s.playingMessageId);
  const highlightedMessageId = useChatStore((s) => s.highlightedMessageId);
  const isHighlighted = highlightedMessageId === message.id;
  const isPlaying = playingMessageId === message.id;

  const renderOptions = {
    emojiEnabled,
    showEmojiLabel,
    stickersEnabled: useStickers,
    standaloneLine,
  };

  const handleAudioClick = () => {
    if (isPlaying) {
      onStopAudio?.();
    } else {
      onPlayAudio?.(message);
    }
  };

  const hasMultiBubbles =
    !isUser &&
    bubbleMode !== "single" &&
    Array.isArray(message.speech_bubbles) &&
    message.speech_bubbles.length > 1;

  return (
    <div
      id={`msg-${message.id}`}
      className={`${styles.messageRow} ${isUser ? styles.userRow : styles.companionRow} ${
        isHighlighted ? styles.highlighted : ""
      }`}
    >
      {!isUser && <div className={styles.avatar}>{avatarLetter}</div>}

      <div className={styles.bubbleColumn}>
        <div className={`${styles.headerSmall} ${isUser ? styles.userHeader : ""}`}>
          <span>{isUser ? "你" : characterName}</span>
          <span>{formatTime(message.created_at)}</span>
        </div>

        {hasMultiBubbles ? (
          message.speech_bubbles!.map((bubble, idx) => (
            <div
              key={idx}
              className={`${styles.bubble} ${styles.companionBubble} ${styles.burstBubble}`}
              style={{ animationDelay: `${idx * 140}ms` }}
            >
              {renderContentWithStickersAndEmojis(bubble, renderOptions)}
            </div>
          ))
        ) : (
          <div className={`${styles.bubble} ${isUser ? styles.userBubble : styles.companionBubble}`}>
            {message.content.split("\n").map((line, idx, arr) => (
              <React.Fragment key={idx}>
                {renderContentWithStickersAndEmojis(line, renderOptions)}
                {idx < arr.length - 1 && <br />}
              </React.Fragment>
            ))}
          </div>
        )}

        {!isUser && message.audio_cache_key && (
          <button
            type="button"
            className={`${styles.audioBtn} ${isPlaying ? styles.audioBtnPlaying : ""}`}
            onClick={handleAudioClick}
            title="播放伴侣原声语音"
          >
            <svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor">
              {isPlaying ? (
                <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
              ) : (
                <path d="M8 5v14l11-7z" />
              )}
            </svg>
            <span>{isPlaying ? "播放中..." : "语音"}</span>
          </button>
        )}

        {!isUser && message.audio_status === "failed" && (
          <div className={styles.audioBadge}>语音生成暂不可用</div>
        )}
      </div>
    </div>
  );
};
