import React, { useEffect, useRef, useState } from "react";
import { MessageItem } from "../types";
import { renderContentWithStickersAndEmojis } from "../presentation/stickerRenderer";
import { StickerPickerModal } from "./StickerPickerModal";

interface ChatViewProps {
  messages: MessageItem[];
  isGenerating: boolean;
  input: string;
  onInputChange: (val: string) => void;
  onSendMessage: (textToSend?: string) => void;
  error: string | null;
  onRetry?: () => void;
  characterName: string;
  highlightedMessageId?: string | null;
  voiceConsentGranted?: boolean;
  onSendVoiceMessage?: (audioBase64: string, durationMs: number) => Promise<void>;
  playingMessageId?: string | null;
  onPlayAudio?: (message: MessageItem) => void;
  onStopAudio?: () => void;
  onOpenSettings?: () => void;
  bubbleMode?: "multi" | "single";
  emojiRenderingEnabled?: boolean;
  onOpenHistory?: () => void;
  onNewChat?: () => void;
}

export const ChatView: React.FC<ChatViewProps> = ({
  messages,
  isGenerating,
  input,
  onInputChange,
  onSendMessage,
  error,
  onRetry,
  characterName,
  highlightedMessageId,
  voiceConsentGranted = false,
  onSendVoiceMessage,
  playingMessageId,
  onPlayAudio,
  onStopAudio,
  onOpenSettings,
  bubbleMode = "multi",
  emojiRenderingEnabled = true,
  onOpenHistory,
  onNewChat,
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Phase 10: Push-to-Talk (PTT) recording state
  const [isRecording, setIsRecording] = React.useState<boolean>(false);
  const [recordingDuration, setRecordingDuration] = React.useState<number>(0);
  const [isStickerPickerOpen, setIsStickerPickerOpen] = useState<boolean>(false);
  const [showEmojiLabel, setShowEmojiLabel] = useState<boolean>(() => {
    return localStorage.getItem("aevum_show_emoji_label") === "true";
  });
  const [useStickers, setUseStickers] = useState<boolean>(() => {
    return localStorage.getItem("aevum_use_stickers") !== "false";
  });
  const [stickerStandaloneLine, setStickerStandaloneLine] = useState<boolean>(() => {
    return localStorage.getItem("aevum_sticker_standalone_line") !== "false";
  });

  useEffect(() => {
    const handlePreferencesUpdate = () => {
      setShowEmojiLabel(localStorage.getItem("aevum_show_emoji_label") === "true");
      setUseStickers(localStorage.getItem("aevum_use_stickers") !== "false");
      setStickerStandaloneLine(localStorage.getItem("aevum_sticker_standalone_line") !== "false");
    };
    window.addEventListener("aevum-preferences-updated", handlePreferencesUpdate);
    window.addEventListener("storage", handlePreferencesUpdate);
    return () => {
      window.removeEventListener("aevum-preferences-updated", handlePreferencesUpdate);
      window.removeEventListener("storage", handlePreferencesUpdate);
    };
  }, []);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const recordTimerRef = useRef<number | null>(null);
  const startTimeRef = useRef<number>(0);

  const handleSelectSticker = (stickerId: string) => {
    triggerBargeIn();
    const tag = `[sticker:${stickerId}]`;
    if (!input.trim()) {
      onSendMessage(tag);
    } else {
      const nextVal = `${input.trim()} ${tag}`;
      onInputChange(nextVal);
      if (textareaRef.current) {
        textareaRef.current.focus();
      }
    }
  };

  // Auto-scroll to bottom on new messages or generation change (unless highlighting a specific message)
  useEffect(() => {
    if (!highlightedMessageId && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isGenerating, highlightedMessageId]);

  // Scroll to highlighted message when requested via deep link
  useEffect(() => {
    if (highlightedMessageId) {
      const el = document.getElementById(`msg-${highlightedMessageId}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }
  }, [highlightedMessageId]);

  // Barge-in: Stop playing companion audio when user interacts
  const triggerBargeIn = () => {
    if (onStopAudio) {
      onStopAudio();
    }
  };

  // Adjust textarea height dynamically
  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    triggerBargeIn();
    onInputChange(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (input.trim()) {
        triggerBargeIn();
        onSendMessage();
        if (textareaRef.current) {
          textareaRef.current.style.height = "auto";
          textareaRef.current.focus();
        }
      }
    }
  };

  // Push-To-Talk microphone capture (Phase 10 / Rule 18)
  const startRecording = async () => {
    if (isGenerating || isRecording) return;
    triggerBargeIn();

    if (!voiceConsentGranted) {
      if (onOpenSettings) onOpenSettings();
      return;
    }

    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        console.warn("Microphone not available in this environment.");
        return;
      }
      const selectedInputId = localStorage.getItem("aevum_selected_audio_input_id");
      const audioConstraints: MediaTrackConstraints | boolean =
        selectedInputId && selectedInputId !== "default"
          ? { deviceId: { exact: selectedInputId } }
          : true;
      const stream = await navigator.mediaDevices.getUserMedia({ audio: audioConstraints });
      audioChunksRef.current = [];
      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };
      recorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/wav" });
        stream.getTracks().forEach((track) => track.stop());
        const elapsed = Math.max(100, Math.round(Date.now() - startTimeRef.current));
        const reader = new FileReader();
        reader.onloadend = () => {
          const resultStr = reader.result as string;
          const base64Data = resultStr ? resultStr.split(",")[1] : null;
          if (base64Data && onSendVoiceMessage) {
            onSendVoiceMessage(base64Data, elapsed);
          }
        };
        reader.readAsDataURL(audioBlob);
      };
      recorder.start();
      mediaRecorderRef.current = recorder;
      startTimeRef.current = Date.now();
      setIsRecording(true);
      setRecordingDuration(0);
      recordTimerRef.current = window.setInterval(() => {
        setRecordingDuration(Math.round((Date.now() - startTimeRef.current) / 1000));
      }, 500);
    } catch (err) {
      console.warn("Could not start microphone recording:", err);
      setIsRecording(false);
    }
  };

  const stopRecording = () => {
    if (recordTimerRef.current) {
      clearInterval(recordTimerRef.current);
      recordTimerRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
  };


  const formatTime = (isoString: string) => {
    try {
      if (!isoString) return "";
      let normalized = isoString;
      // If naive UTC string like "2026-10-09T13:12:47" or "2026-10-09 13:12:47", treat as UTC
      if (!normalized.endsWith("Z") && !/[+-]\d{2}:\d{2}$/.test(normalized)) {
        normalized = normalized.replace(" ", "T") + "Z";
      }
      const date = new Date(normalized);
      if (isNaN(date.getTime())) return "";
      return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch {
      return "";
    }
  };

  return (
    <div className="chat-view">
      <div className="chat-header-bar">
        <div className="chat-header-title">
          <span className="chat-header-avatar-dot"></span>
          <span className="chat-header-name">{characterName}</span>
        </div>
        <div className="chat-header-actions">
          {onOpenHistory && (
            <button
              type="button"
              className="chat-header-action-btn"
              onClick={onOpenHistory}
              title="查看与管理历史会话"
            >
              📜 历史会话
            </button>
          )}
          {onNewChat && (
            <button
              type="button"
              className="chat-header-action-btn"
              onClick={onNewChat}
              title="开启全新会话"
            >
              ＋ 新会话
            </button>
          )}
        </div>
      </div>

      <div className="messages-container" ref={scrollContainerRef}>
        {messages.length === 0 ? (
          <div className="chat-empty-state">
            <div className="empty-avatar">{characterName ? characterName[0] : "棠"}</div>
            <h3>与 {characterName || "苏棠"} 的日常对话</h3>
            <p className="empty-subtext">
              {characterName || "苏棠"}是一个真实生活在吉隆坡的计算机系大四学生兼独立游戏开发者，拥有自己的作息习惯、情绪起伏与长久记忆。
              跟她打个招呼，或者聊聊今天发生的事吧。
            </p>
            <div className="starter-chips">
              <button
                className="chip-btn"
                onClick={() => onInputChange(`${characterName || "苏棠"}，你今天都在忙些什么呀？`)}
              >
                "你今天都在忙些什么呀？"
              </button>
              <button
                className="chip-btn"
                onClick={() => onInputChange("现在心情怎么样？有发生什么好玩的事吗？")}
              >
                "现在心情怎么样？"
              </button>
              <button
                className="chip-btn"
                onClick={() => onInputChange("你平时喜欢听什么音乐或者玩什么游戏呀？")}
              >
                "平时喜欢听什么音乐或玩游戏？"
              </button>
            </div>
          </div>
        ) : (
          messages.map((msg) => {
            const isUser = msg.role === "user";
            return (
              <div
                key={msg.id}
                id={`msg-${msg.id}`}
                className={`message-row ${isUser ? "user-row" : "companion-row"} ${
                  highlightedMessageId === msg.id ? "highlighted-message" : ""
                }`}
              >
                {!isUser && <div className="bubble-avatar">晚</div>}
                {!isUser && bubbleMode !== "single" && msg.speech_bubbles && msg.speech_bubbles.length > 1 ? (
                  <div className="multi-bubble-column">
                    <div className="message-header-small">
                      <span className="sender-name">{characterName}</span>
                      <span className="timestamp">{formatTime(msg.created_at)}</span>
                    </div>
                    <div className="sequential-speech-bubbles">
                      {msg.speech_bubbles.map((bubble, bIdx) => (
                        <div
                          key={bIdx}
                          className="message-bubble companion-bubble sequential-burst-bubble"
                          style={{
                            animationDelay: `${bIdx * 140}ms`,
                          }}
                        >
                          <div className="bubble-text">
                            {renderContentWithStickersAndEmojis(bubble, {
                              emojiEnabled: emojiRenderingEnabled,
                              showEmojiLabel,
                              stickersEnabled: useStickers,
                              standaloneLine: stickerStandaloneLine,
                            })}
                          </div>
                        </div>
                      ))}
                    </div>
                    {msg.audio_cache_key && (
                      <button
                        type="button"
                        className={`audio-play-button ${playingMessageId === msg.id ? "playing" : ""}`}
                        onClick={() => {
                          if (playingMessageId === msg.id) {
                            onStopAudio?.();
                          } else {
                            onPlayAudio?.(msg);
                          }
                        }}
                        title="Play spoken voice"
                      >
                        <svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor">
                          {playingMessageId === msg.id ? (
                            <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
                          ) : (
                            <path d="M8 5v14l11-7z" />
                          )}
                        </svg>
                        <span>{playingMessageId === msg.id ? "Playing..." : "Voice"}</span>
                      </button>
                    )}
                    {msg.audio_status === "failed" && (
                      <div className="audio-status-badge">Audio unavailable</div>
                    )}
                  </div>
                ) : (
                  <div className={`message-bubble ${isUser ? "user-bubble" : "companion-bubble"}`}>
                    <div className="message-header-small">
                      <span className="sender-name">{isUser ? "你" : characterName}</span>
                      <span className="timestamp">{formatTime(msg.created_at)}</span>
                    </div>
                    <div className="bubble-text">
                      {msg.content.split("\n").map((line, idx) => (
                        <React.Fragment key={idx}>
                          {renderContentWithStickersAndEmojis(line, {
                            emojiEnabled: emojiRenderingEnabled,
                            showEmojiLabel,
                            stickersEnabled: useStickers,
                            standaloneLine: stickerStandaloneLine,
                          })}
                          {idx < msg.content.split("\n").length - 1 && <br />}
                        </React.Fragment>
                      ))}
                    </div>
                    {!isUser && msg.audio_cache_key && (
                      <button
                        type="button"
                        className={`audio-play-button ${playingMessageId === msg.id ? "playing" : ""}`}
                        onClick={() => {
                          if (playingMessageId === msg.id) {
                            onStopAudio?.();
                          } else {
                            onPlayAudio?.(msg);
                          }
                        }}
                        title="Play spoken voice"
                      >
                        <svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor">
                          {playingMessageId === msg.id ? (
                            <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
                          ) : (
                            <path d="M8 5v14l11-7z" />
                          )}
                        </svg>
                        <span>{playingMessageId === msg.id ? "Playing..." : "Voice"}</span>
                      </button>
                    )}
                    {!isUser && msg.audio_status === "failed" && (
                      <div className="audio-status-badge">Audio unavailable</div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}

        {isGenerating && (
          <div className="message-row companion-row">
            <div className="bubble-avatar">A</div>
            <div className="message-bubble companion-bubble typing-bubble">
              <div className="message-header-small">
                <span className="sender-name">{characterName}</span>
              </div>
              <div className="typing-indicator">
                <span className="dot" />
                <span className="dot" />
                <span className="dot" />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {error && (
        <div className="chat-error-banner">
          <span className="error-text">{error}</span>
          {onRetry && (
            <button className="error-retry-btn" onClick={onRetry}>
              Retry
            </button>
          )}
        </div>
      )}

      <div className="chat-input-area">
        {isRecording && (
          <div className="recording-indicator-bar">
            <span className="recording-dot" />
            <span>Recording voice ({recordingDuration}s)... Click or release PTT button to send</span>
          </div>
        )}
        <div className="input-wrapper">
          <textarea
            ref={textareaRef}
            className="chat-textarea"
            rows={1}
            placeholder={
              isGenerating
                ? `${characterName || "苏棠"}正在思考与回应中... (您可以继续输入并直接发送)`
                : `跟${characterName || "苏棠"}说点什么... (Enter 发送, Shift+Enter 换行)`
            }
            value={input}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            disabled={isRecording}
          />
          <button
            type="button"
            className={`sticker-picker-trigger-btn ${isStickerPickerOpen ? "active" : ""}`}
            title="发送表情包 (斗图)"
            disabled={isRecording}
            onClick={() => setIsStickerPickerOpen(!isStickerPickerOpen)}
          >
            <span role="img" aria-label="sticker">🎨</span>
          </button>
          <button
            type="button"
            className={`ptt-button ${isRecording ? "recording" : ""}`}
            title={
              !voiceConsentGranted
                ? "Microphone disabled (Rule 18). Click to open Settings."
                : isRecording
                ? "Recording... Click or release to send"
                : "Push-To-Talk: Hold or click to speak"
            }
            disabled={isGenerating}
            onMouseDown={() => startRecording()}
            onMouseUp={() => stopRecording()}
            onTouchStart={() => startRecording()}
            onTouchEnd={() => stopRecording()}
            onClick={() => {
              if (!voiceConsentGranted) {
                onOpenSettings?.();
              } else if (isRecording) {
                stopRecording();
              } else {
                startRecording();
              }
            }}
          >
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              <line x1="12" y1="19" x2="12" y2="23" />
              <line x1="8" y1="23" x2="16" y2="23" />
            </svg>
          </button>
          <button
            className="send-button"
            onClick={() => {
              if (input.trim()) {
                onSendMessage();
                if (textareaRef.current) {
                  textareaRef.current.style.height = "auto";
                  textareaRef.current.focus();
                }
              }
            }}
            disabled={!input.trim() || isRecording}
            title={isGenerating ? "发送并排队 (继续输入并发送)" : "发送消息 (Enter)"}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" className="send-icon">
              <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
            </svg>
          </button>
        </div>

        {/* Floating Sticker Picker Popover */}
        <StickerPickerModal
          isOpen={isStickerPickerOpen}
          onClose={() => setIsStickerPickerOpen(false)}
          onSelectSticker={handleSelectSticker}
        />
      </div>
    </div>
  );
};
