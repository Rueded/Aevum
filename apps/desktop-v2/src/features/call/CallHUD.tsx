import React, { useRef, useState } from "react";
import { CallMode } from "../../types";
import { AudioDeviceSelector } from "../voice/AudioDeviceSelector";

export interface CallHUDProps {
  callMode: CallMode;
  activeGenerationId: number;
  partialTranscript: string;
  isMuted: boolean;
  onToggleMute: () => void;
  onStartCall: () => void;
  onEndCall: () => void;
  onBargeIn: () => void;
  errorMessage?: string | null;
  characterName: string;
  onSendVoiceMessage?: (audioBase64: string, durationMs: number) => Promise<void>;
  onSendMessage?: (text: string) => Promise<void>;
  isCompanionSpeaking?: boolean;
}

export const CallHUD: React.FC<CallHUDProps> = ({
  callMode,
  activeGenerationId,
  partialTranscript,
  isMuted,
  onToggleMute,
  onStartCall,
  onEndCall,
  onBargeIn,
  errorMessage,
  characterName,
  onSendVoiceMessage,
  onSendMessage,
  isCompanionSpeaking = false,
}) => {
  const [showDeviceSettings, setShowDeviceSettings] = useState(false);
  const [isTalking, setIsTalking] = useState(false);
  const [turnStatus, setTurnStatus] = useState<string | null>(null);
  const [isHandsFree, setIsHandsFree] = useState<boolean>(() => {
    return localStorage.getItem("aevum_call_hands_free") !== "false";
  });
  const [interimSpeech, setInterimSpeech] = useState<string>("");

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const startTimeRef = useRef<number>(0);
  const recognitionRef = useRef<any>(null);
  const silenceTimeoutRef = useRef<any>(null);
  const accumulatedSpeechRef = useRef<string>("");

  const isCallActive = callMode === "ACTIVE";
  const isConnecting = callMode === "CONNECTING";
  const isReconnecting = callMode === "RECONNECTING";

  // Hands-free continuous duplex speech recognition
  React.useEffect(() => {
    if (!isCallActive || isMuted || !isHandsFree) {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {
          // ignore
        }
        recognitionRef.current = null;
      }
      setInterimSpeech("");
      return;
    }

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      return;
    }

    const rec = new SpeechRecognition();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = "zh-CN";

    rec.onresult = (e: any) => {
      let interim = "";
      let final = "";

      for (let i = e.resultIndex; i < e.results.length; ++i) {
        if (e.results[i].isFinal) {
          final += e.results[i][0].transcript;
        } else {
          interim += e.results[i][0].transcript;
        }
      }

      const liveText = (final || interim).trim();
      if (liveText) {
        setInterimSpeech(liveText);

        // Instant Barge-In: If companion is talking and user speaks, immediately interrupt
        if (isCompanionSpeaking) {
          onBargeIn();
        }

        // Fast Speculative VAD silence detection
        if (silenceTimeoutRef.current) {
          clearTimeout(silenceTimeoutRef.current);
        }

        if (final) {
          accumulatedSpeechRef.current = (accumulatedSpeechRef.current + " " + final).trim();
        }

        silenceTimeoutRef.current = setTimeout(async () => {
          const textToCommit = (accumulatedSpeechRef.current || interim).trim();
          if (textToCommit && textToCommit.length >= 1) {
            setTurnStatus("正在回复...");
            setInterimSpeech("");
            accumulatedSpeechRef.current = "";
            try {
              if (onSendMessage) {
                await onSendMessage(textToCommit);
              }
            } catch (err) {
              console.warn("Failed to commit hands-free voice speech turn", err);
            } finally {
              setTurnStatus(null);
            }
          }
        }, 550); // 550ms natural pause triggers AI turn
      }
    };

    rec.onerror = (e: any) => {
      if (e.error !== "no-speech" && e.error !== "aborted") {
        console.warn("Call speech recognition error:", e.error);
      }
    };

    rec.onend = () => {
      // Auto-restart while call is active
      if (isCallActive && !isMuted && isHandsFree && recognitionRef.current === rec) {
        try {
          rec.start();
        } catch {
          // ignore
        }
      }
    };

    try {
      rec.start();
      recognitionRef.current = rec;
    } catch (err) {
      console.warn("Could not start continuous speech recognition", err);
    }

    return () => {
      if (silenceTimeoutRef.current) clearTimeout(silenceTimeoutRef.current);
      try {
        rec.abort();
      } catch {
        // ignore
      }
      recognitionRef.current = null;
    };
  }, [isCallActive, isMuted, isHandsFree, isCompanionSpeaking, onBargeIn, onSendMessage]);

  const startTalking = async () => {
    if (!isCallActive || isMuted || isTalking) return;
    try {
      const selectedInputId = localStorage.getItem("aevum_selected_audio_input_id");
      const audioConstraints: MediaTrackConstraints | boolean =
        selectedInputId && selectedInputId !== "default"
          ? { deviceId: { exact: selectedInputId } }
          : true;
      const stream = await navigator.mediaDevices.getUserMedia({ audio: audioConstraints });
      audioChunksRef.current = [];
      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) audioChunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/wav" });
        stream.getTracks().forEach((t) => t.stop());
        const elapsed = Math.max(100, Math.round(Date.now() - startTimeRef.current));
        const reader = new FileReader();
        reader.onloadend = () => {
          const res = reader.result as string;
          const b64 = res ? res.split(",")[1] : null;
          if (b64 && onSendVoiceMessage) {
            setTurnStatus("正在转写回复...");
            onSendVoiceMessage(b64, elapsed).finally(() => {
              setTurnStatus(null);
            });
          }
        };
        reader.readAsDataURL(audioBlob);
      };
      recorder.start();
      mediaRecorderRef.current = recorder;
      startTimeRef.current = Date.now();
      setIsTalking(true);
    } catch (err) {
      console.warn("Failed to capture call mic:", err);
      setIsTalking(false);
    }
  };

  const stopTalking = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
    }
    setIsTalking(false);
  };

  return (
    <div className={`call-hud-container mode-${callMode.toLowerCase()}`}>
      <div className="call-hud-inner">
        {/* Left: Call State Indicator & Waveform */}
        <div className="call-hud-status-section">
          <div className="call-status-badge">
            <span
              className={`call-status-dot ${
                isCallActive
                  ? "active"
                  : isReconnecting
                  ? "reconnecting"
                  : isConnecting
                  ? "connecting"
                  : "idle"
              }`}
            />
            <span className="call-status-label">
              {isCompanionSpeaking
                ? `${characterName} 正在说话...`
                : isTalking
                ? "正在聆听您说话..."
                : isCallActive
                ? `通话中 · ${characterName}`
                : isConnecting
                ? "正在接通电话..."
                : isReconnecting
                ? "重新连接中..."
                : "随时可拨打语音电话"}
            </span>
            {isCallActive && (
              <span className="generation-badge" title="Active Monotonic Generation ID">
                Gen #{activeGenerationId}
              </span>
            )}
          </div>

          {/* Audio Waveform Animation (Visible when Active or Speaking) */}
          {isCallActive && !isMuted && (
            <div className="call-waveform-visualizer" aria-label="Audio Waveform">
              <span className="waveform-bar bar-1" />
              <span className="waveform-bar bar-2" />
              <span className="waveform-bar bar-3" />
              <span className="waveform-bar bar-4" />
              <span className="waveform-bar bar-5" />
            </div>
          )}
        </div>

        {/* Center: Ephemeral Partial Transcript Preview (ADR-024 Lock 3) */}
        <div className="call-hud-transcript-section">
          {turnStatus ? (
            <div className="call-partial-transcript">
              <span className="transcript-prefix">Status: </span>
              <span className="transcript-text">{turnStatus}</span>
            </div>
          ) : interimSpeech ? (
            <div className="call-partial-transcript">
              <span className="transcript-prefix">实时识别: </span>
              <span className="transcript-text" style={{ fontStyle: "italic", color: "#a5b4fc" }}>
                "{interimSpeech}"
              </span>
            </div>
          ) : partialTranscript ? (
            <div className="call-partial-transcript">
              <span className="transcript-prefix">Hearing: </span>
              <span className="transcript-text">"{partialTranscript}"</span>
            </div>
          ) : errorMessage ? (
            <div className="call-hud-error">
              <span className="error-icon">⚠️</span>
              <span className="error-text">{errorMessage}</span>
            </div>
          ) : isCompanionSpeaking ? (
            <div className="call-hud-hint" style={{ color: "var(--accent-cyan)", fontWeight: 500 }}>
              🔊 {characterName} 正在对您说话... (可直接说话打断)
            </div>
          ) : isTalking ? (
            <div className="call-hud-hint" style={{ color: "#ef4444", fontWeight: 600 }}>
              🎙️ 正在聆听您的声音 (松开按钮即刻回复)...
            </div>
          ) : isCallActive && isHandsFree ? (
            <div className="call-hud-hint" style={{ color: "#34d399", fontWeight: 500 }}>
              ✨ 免提自然通话中 · 直接说话即可，停顿后自动回复
            </div>
          ) : isCallActive ? (
            <div className="call-hud-hint">
              {isMuted ? "麦克风已静音 (Muted)" : "按住右侧【🎙️ 说话】或随时点击【✋ 打断】"}
            </div>
          ) : (
            <div className="call-hud-hint">
              点击右侧【📞 拨打电话】发起与伴侣的语音通话
            </div>
          )}
        </div>

        {/* Right: Call Actions & Controls */}
        <div className="call-hud-actions">
          {/* Audio Devices Quick Toggle Button */}
          <button
            type="button"
            className="call-action-btn btn-device-settings"
            onClick={() => setShowDeviceSettings((prev) => !prev)}
            title="音频设备设置 (Microphone & Speaker Settings)"
            style={{ background: showDeviceSettings ? "rgba(99, 102, 241, 0.4)" : "rgba(255, 255, 255, 0.08)" }}
          >
            ⚙️ 设备
          </button>

          {isCallActive || isConnecting || isReconnecting ? (
            <>
              {/* Hands-free vs PTT Mode Toggle */}
              {isCallActive && (
                <button
                  type="button"
                  className="call-action-btn"
                  onClick={() => {
                    setIsHandsFree((prev) => {
                      const next = !prev;
                      localStorage.setItem("aevum_call_hands_free", String(next));
                      return next;
                    });
                  }}
                  title={isHandsFree ? "切换为按键说话 (PTT)" : "切换为免提全双工自然通话"}
                  style={{
                    background: isHandsFree ? "rgba(16, 185, 129, 0.2)" : "rgba(255, 255, 255, 0.08)",
                    border: isHandsFree ? "1px solid rgba(16, 185, 129, 0.5)" : "1px solid rgba(255, 255, 255, 0.15)",
                    color: isHandsFree ? "#34d399" : "#ccc",
                  }}
                >
                  {isHandsFree ? "📞 免提双工" : "🎙️ 按键通话"}
                </button>
              )}

              {/* Push-to-Talk in call (Visible if not in hands-free mode) */}
              {isCallActive && !isMuted && !isHandsFree && (
                <button
                  type="button"
                  className={`call-action-btn btn-talk ${isTalking ? "talking" : ""}`}
                  onMouseDown={startTalking}
                  onMouseUp={stopTalking}
                  onTouchStart={startTalking}
                  onTouchEnd={stopTalking}
                  title="按住说话，松开后伴侣将语音回答"
                  style={{
                    background: isTalking ? "#ef4444" : "#10b981",
                    color: "#ffffff",
                    fontWeight: 600,
                    padding: "6px 14px",
                    borderRadius: "8px",
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    cursor: "pointer",
                    boxShadow: isTalking ? "0 0 12px rgba(239, 68, 68, 0.6)" : "none",
                  }}
                >
                  {isTalking ? "🔴 聆听中..." : "🎙️ 说话"}
                </button>
              )}

              {/* Mute Toggle */}
              <button
                type="button"
                className={`call-action-btn btn-mute ${isMuted ? "muted" : ""}`}
                onClick={onToggleMute}
                title={isMuted ? "Unmute Microphone" : "Mute Microphone"}
              >
                {isMuted ? "🔇 取消静音" : "🎙️ 静音"}
              </button>

              {/* Instant Barge-In Interrupt (ADR-024 Lock 4) */}
              <button
                type="button"
                className="call-action-btn btn-interrupt"
                onClick={onBargeIn}
                title="Instant Barge-In (打断伴侣说话)"
              >
                ✋ 打断
              </button>

              {/* End Call */}
              <button
                type="button"
                className="call-action-btn btn-end-call"
                onClick={onEndCall}
                title="挂断语音通话"
              >
                🔴 挂断
              </button>
            </>
          ) : (
            /* Start Call Button */
            <button
              type="button"
              className="call-action-btn btn-start-call"
              onClick={onStartCall}
              title="与 Aevum 建立实时语音通话"
            >
              📞 拨打语音电话
            </button>
          )}
        </div>
      </div>

      {/* Floating Audio Device Settings Popover */}
      {showDeviceSettings && (
        <div
          className="call-hud-device-popover"
          style={{
            position: "absolute",
            bottom: "calc(100% + 12px)",
            right: "20px",
            width: "360px",
            background: "#181825",
            border: "1px solid rgba(255, 255, 255, 0.15)",
            borderRadius: "12px",
            boxShadow: "0 12px 30px rgba(0, 0, 0, 0.6)",
            padding: "16px",
            zIndex: 1000,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
            <span style={{ fontWeight: 600, fontSize: "14px" }}>🎧 麦克风与扬声器硬件设置</span>
            <button
              type="button"
              onClick={() => setShowDeviceSettings(false)}
              style={{
                background: "transparent",
                border: "none",
                color: "rgba(255,255,255,0.6)",
                fontSize: "16px",
                cursor: "pointer",
              }}
            >
              ✕
            </button>
          </div>
          <AudioDeviceSelector compact />
        </div>
      )}
    </div>
  );
};
