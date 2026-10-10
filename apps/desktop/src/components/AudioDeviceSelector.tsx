import React, { useState } from "react";
import { useAudioDevices } from "../audio/useAudioDevices";

interface AudioDeviceSelectorProps {
  compact?: boolean;
}

export const AudioDeviceSelector: React.FC<AudioDeviceSelectorProps> = ({ compact = false }) => {
  const {
    inputDevices,
    outputDevices,
    selectedInputId,
    selectedOutputId,
    hasPermission,
    requestPermission,
    selectInput,
    selectOutput,
    micVolume,
    isTestingMic,
    startMicTest,
    stopMicTest,
    testSpeaker,
  } = useAudioDevices();

  const [permLoading, setPermLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleGrantPermission = async () => {
    setPermLoading(true);
    setErrorMsg(null);
    try {
      await requestPermission();
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "无法获取麦克风权限");
    } finally {
      setPermLoading(false);
    }
  };

  return (
    <div className={`audio-device-selector-container ${compact ? "compact" : ""}`}>
      {!hasPermission && (
        <div className="audio-permission-banner" style={{
          background: "rgba(234, 179, 8, 0.15)",
          border: "1px solid rgba(234, 179, 8, 0.3)",
          borderRadius: "8px",
          padding: "10px 14px",
          marginBottom: "12px",
          fontSize: "13px",
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span>🎙️ 尚未获取音频设备访问权限，设备名称当前显示为通用标签。</span>
            <button
              type="button"
              onClick={handleGrantPermission}
              disabled={permLoading}
              style={{
                background: "#eab308",
                color: "#18181b",
                border: "none",
                borderRadius: "4px",
                padding: "4px 10px",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              {permLoading ? "请求中..." : "授权并读取设备"}
            </button>
          </div>
          {errorMsg && <p style={{ color: "#ef4444", marginTop: "6px" }}>{errorMsg}</p>}
        </div>
      )}

      <div className="form-grid" style={{ display: "grid", gridTemplateColumns: compact ? "1fr" : "1fr 1fr", gap: "14px" }}>
        {/* Microphone Input */}
        <div className="field-group">
          <label style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span>🎙️ 麦克风输入设备 (Microphone)</span>
            <span style={{ fontSize: "11px", color: "rgba(255,255,255,0.5)" }}>
              {inputDevices.length} 个可用设备
            </span>
          </label>
          <select
            value={selectedInputId}
            onChange={(e) => selectInput(e.target.value)}
            style={{
              width: "100%",
              background: "rgba(255, 255, 255, 0.08)",
              border: "1px solid rgba(255, 255, 255, 0.2)",
              borderRadius: "6px",
              padding: "8px 10px",
              color: "inherit",
              fontSize: "13px",
            }}
          >
            <option value="default" style={{ background: "#1e1e2e" }}>
              默认麦克风 (System Default)
            </option>
            {inputDevices.map((dev) => (
              <option key={dev.deviceId} value={dev.deviceId} style={{ background: "#1e1e2e" }}>
                {dev.label || `Microphone (${dev.deviceId.slice(0, 8)})`}
              </option>
            ))}
          </select>

          {/* Live Mic Test Meter */}
          <div style={{ marginTop: "8px", display: "flex", alignItems: "center", gap: "10px" }}>
            <button
              type="button"
              onClick={isTestingMic ? stopMicTest : startMicTest}
              style={{
                background: isTestingMic ? "#ef4444" : "rgba(255,255,255,0.1)",
                color: "white",
                border: "1px solid rgba(255,255,255,0.2)",
                borderRadius: "4px",
                padding: "4px 8px",
                fontSize: "12px",
                cursor: "pointer",
              }}
            >
              {isTestingMic ? "⏹️ 停止测试" : "🎤 试音测试"}
            </button>
            <div style={{
              flex: 1,
              height: "10px",
              background: "rgba(255,255,255,0.1)",
              borderRadius: "5px",
              overflow: "hidden",
            }}>
              <div style={{
                height: "100%",
                width: `${micVolume}%`,
                background: micVolume > 70 ? "#ef4444" : micVolume > 30 ? "#10b981" : "#3b82f6",
                transition: "width 60ms ease-out",
              }} />
            </div>
            <span style={{ fontSize: "11px", minWidth: "30px", textAlign: "right", color: "rgba(255,255,255,0.6)" }}>
              {micVolume}%
            </span>
          </div>
        </div>

        {/* Speaker Output */}
        <div className="field-group">
          <label style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span>🔊 扬声器 / 耳机输出 (Speaker / Headphones)</span>
            <span style={{ fontSize: "11px", color: "rgba(255,255,255,0.5)" }}>
              {outputDevices.length} 个可用设备
            </span>
          </label>
          <select
            value={selectedOutputId}
            onChange={(e) => selectOutput(e.target.value)}
            style={{
              width: "100%",
              background: "rgba(255, 255, 255, 0.08)",
              border: "1px solid rgba(255, 255, 255, 0.2)",
              borderRadius: "6px",
              padding: "8px 10px",
              color: "inherit",
              fontSize: "13px",
            }}
          >
            <option value="default" style={{ background: "#1e1e2e" }}>
              默认输出 (System Default)
            </option>
            {outputDevices.map((dev) => (
              <option key={dev.deviceId} value={dev.deviceId} style={{ background: "#1e1e2e" }}>
                {dev.label || `Speaker (${dev.deviceId.slice(0, 8)})`}
              </option>
            ))}
          </select>

          {/* Test Speaker Button */}
          <div style={{ marginTop: "8px", display: "flex", alignItems: "center" }}>
            <button
              type="button"
              onClick={testSpeaker}
              style={{
                background: "rgba(255,255,255,0.1)",
                color: "white",
                border: "1px solid rgba(255,255,255,0.2)",
                borderRadius: "4px",
                padding: "4px 10px",
                fontSize: "12px",
                cursor: "pointer",
              }}
            >
              🎵 播放测试提示音
            </button>
            <span style={{ marginLeft: "10px", fontSize: "11px", color: "rgba(255,255,255,0.5)" }}>
              点击测试声音是否正常输出
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
