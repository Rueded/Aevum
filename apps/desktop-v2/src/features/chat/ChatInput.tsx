import React, { useRef, useState } from "react";
import { useChatStore } from "../../stores/useChatStore";
import { useSettingsStore } from "../../stores/useSettingsStore";
import { useCharacterStore } from "../../stores/useCharacterStore";
import { StickerPickerModal } from "../stickers/StickerPickerModal";
import styles from "./ChatInput.module.css";

interface ChatInputProps {
  onSendMessage: (text?: string) => void;
  onSendVoiceMessage?: (audioBase64: string, durationMs: number) => Promise<void>;
  onStopAudio?: () => void;
  onOpenSettings?: () => void;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  onSendMessage,
  onSendVoiceMessage,
  onStopAudio,
  onOpenSettings,
}) => {
  const inputMessage = useChatStore((s) => s.inputMessage);
  const setInputMessage = useChatStore((s) => s.setInputMessage);
  const isGenerating = useChatStore((s) => s.isGenerating);
  const voiceConsentGranted = useSettingsStore((s) => s.voiceConsentGranted);
  const characterState = useCharacterStore((s) => s.characterState);
  const characterName = characterState?.name || "苏棠";

  const [isRecording, setIsRecording] = useState(false);
  const [recordingDuration, setRecordingDuration] = useState(0);
  const [isStickerPickerOpen, setIsStickerPickerOpen] = useState(false);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const recordTimerRef = useRef<number | null>(null);
  const startTimeRef = useRef<number>(0);

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (uploadEvent) => {
      const dataUrl = uploadEvent.target?.result as string;
      if (!dataUrl) return;
      triggerBargeIn();
      const current = inputMessage.trim();
      const markdownImg = `![图片](${dataUrl})`;
      const fullText = current ? `${current}\n${markdownImg}` : markdownImg;
      onSendMessage(fullText);
    };
    reader.readAsDataURL(file);
    e.target.value = "";
  };

  // Barge-in: typing or sending pauses companion voice playback
  const triggerBargeIn = () => {
    onStopAudio?.();
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    triggerBargeIn();
    setInputMessage(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (inputMessage.trim()) {
        triggerBargeIn();
        onSendMessage();
        if (textareaRef.current) {
          textareaRef.current.style.height = "auto";
          textareaRef.current.focus();
        }
      }
    }
  };

  const handleSelectSticker = (stickerId: string) => {
    triggerBargeIn();
    const tag = `[sticker:${stickerId}]`;
    if (!inputMessage.trim()) {
      onSendMessage(tag);
    } else {
      const nextVal = `${inputMessage.trim()} ${tag}`;
      setInputMessage(nextVal);
      textareaRef.current?.focus();
    }
  };

  // Push-to-Talk Recording Logic (Rule 18 Consent Gate)
  const startRecording = async () => {
    if (isGenerating || isRecording) return;
    triggerBargeIn();

    if (!voiceConsentGranted) {
      onOpenSettings?.();
      return;
    }

    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        console.warn("Microphone not available");
        return;
      }
      const selectedInputId = localStorage.getItem("aevum_selected_audio_input_id");
      const constraints: MediaTrackConstraints | boolean =
        selectedInputId && selectedInputId !== "default"
          ? { deviceId: { exact: selectedInputId } }
          : true;

      const stream = await navigator.mediaDevices.getUserMedia({ audio: constraints });
      audioChunksRef.current = [];
      const recorder = new MediaRecorder(stream);

      recorder.ondataavailable = (event) => {
        if (event.data?.size > 0) {
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
      console.warn("Microphone recording error:", err);
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

  return (
    <div className={styles.inputArea}>
      {isRecording && (
        <div className={styles.recordingBar}>
          <span className={styles.recordingDot} />
          <span>正在录制语音 ({recordingDuration}s)... 松开或再次点击完成发送</span>
        </div>
      )}

      <div className={styles.inputWrapper}>
        <textarea
          ref={textareaRef}
          className={styles.textarea}
          rows={1}
          placeholder={
            isGenerating
              ? `${characterName} 正在思考与回应中... (您可以继续发送，消息将自动排队)`
              : `跟 ${characterName} 说点什么... (Enter 发送, Shift+Enter 换行)`
          }
          value={inputMessage}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          disabled={isRecording}
        />

        <input
          type="file"
          ref={fileInputRef}
          accept="image/*"
          style={{ display: "none" }}
          onChange={handleImageUpload}
        />

        <button
          type="button"
          className={styles.iconBtn}
          title="发送图片 / 拍照"
          disabled={isRecording || isGenerating}
          onClick={() => fileInputRef.current?.click()}
        >
          <span role="img" aria-label="photo">📷</span>
        </button>

        <button
          type="button"
          className={`${styles.iconBtn} ${isStickerPickerOpen ? styles.iconBtnActive : ""}`}
          title="发送表情包"
          disabled={isRecording}
          onClick={() => setIsStickerPickerOpen(!isStickerPickerOpen)}
        >
          <span role="img" aria-label="sticker">🎨</span>
        </button>

        <button
          type="button"
          className={`${styles.pttBtn} ${isRecording ? styles.pttRecording : ""}`}
          title={
            !voiceConsentGranted
              ? "麦克风权限未开启 (Rule 18)。点击打开设置"
              : isRecording
              ? "正在录音... 松开或点击发送"
              : "按住或点击说话 (PTT)"
          }
          disabled={isGenerating}
          onMouseDown={startRecording}
          onMouseUp={stopRecording}
          onTouchStart={startRecording}
          onTouchEnd={stopRecording}
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
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            <line x1="12" y1="19" x2="12" y2="23" />
            <line x1="8" y1="23" x2="16" y2="23" />
          </svg>
        </button>

        <button
          className={styles.sendBtn}
          onClick={() => {
            if (inputMessage.trim()) {
              triggerBargeIn();
              onSendMessage();
              if (textareaRef.current) {
                textareaRef.current.style.height = "auto";
                textareaRef.current.focus();
              }
            }
          }}
          disabled={!inputMessage.trim() || isRecording}
          title={isGenerating ? "发送并排队合并" : "发送消息 (Enter)"}
        >
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.2">
            <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
          </svg>
        </button>
      </div>

      <StickerPickerModal
        isOpen={isStickerPickerOpen}
        onClose={() => setIsStickerPickerOpen(false)}
        onSelectSticker={handleSelectSticker}
      />
    </div>
  );
};
