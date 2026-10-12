import React, { useState } from "react";
import { useAudioDevices, type AudioDeviceInfo } from "../../audio/useAudioDevices";

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
      setErrorMsg(
        err instanceof Error
          ? `授权未完成: ${err.message}。若在手机 App 请在系统设置 -> 应用权限中允许 Aevum 麦克风权限。`
          : "无法获取麦克风权限，请检查系统设置"
      );
    } finally {
      setPermLoading(false);
    }
  };

  return (
    <div className={`audio-device-selector-container ${compact ? "compact" : ""}`}>
      {/* Audio Device Readiness Summary */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "8px",
          marginBottom: "12px",
          fontSize: "12px",
        }}
      >
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "5px",
            padding: "4px 10px",
            borderRadius: "6px",
            background: "rgba(16, 185, 129, 0.12)",
            border: "1px solid rgba(16, 185, 129, 0.3)",
            color: "#6ee7b7",
          }}
        >
          🔊 扬声器/耳机输出：<strong>正常可用 (无需授权)</strong>
        </span>
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "5px",
            padding: "4px 10px",
            borderRadius: "6px",
            background: hasPermission
              ? "rgba(16, 185, 129, 0.12)"
              : "rgba(234, 179, 8, 0.12)",
            border: hasPermission
              ? "1px solid rgba(16, 185, 129, 0.3)"
              : "1px solid rgba(234, 179, 8, 0.3)",
            color: hasPermission ? "#6ee7b7" : "#fde047",
          }}
        >
          🎙️ 麦克风输入：<strong>{hasPermission ? "已获取权限" : "待授权 (语音输入)"}</strong>
        </span>
      </div>

      {!hasPermission && (
        <div
          className="audio-permission-banner"
          style={{
            background: "rgba(234, 179, 8, 0.12)",
            border: "1px solid rgba(234, 179, 8, 0.3)",
            borderRadius: "8px",
            padding: "10px 14px",
            marginBottom: "14px",
            fontSize: "13px",
            lineHeight: "1.5",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px" }}>
            <div style={{ flex: 1, minWidth: "200px" }}>
              <div style={{ fontWeight: 600, color: "#fde047", marginBottom: "2px" }}>
                💡 为什么麦克风显示为待授权？
              </div>
              <div style={{ color: "rgba(255, 255, 255, 0.8)", fontSize: "12px" }}>
                手机与浏览器为保护隐私，默认隐藏具体硬件型号名称。伴侣语音播放走扬声器可直接发声；若要启用语音对讲或显示真实麦克风名称，请点击右侧授权。
              </div>
            </div>
            <button
              type="button"
              onClick={handleGrantPermission}
              disabled={permLoading}
              style={{
                background: "linear-gradient(135deg, #eab308, #ca8a04)",
                color: "#18181b",
                border: "none",
                borderRadius: "6px",
                padding: "8px 14px",
                fontWeight: 700,
                fontSize: "12.5px",
                cursor: "pointer",
                touchAction: "manipulation",
                whiteSpace: "nowrap",
                boxShadow: "0 2px 8px rgba(234, 179, 8, 0.25)",
              }}
            >
              {permLoading ? "正在唤起授权..." : "🎙️ 请求麦克风授权"}
            </button>
          </div>
          {errorMsg && (
            <div style={{ color: "#f87171", marginTop: "8px", fontSize: "12px", background: "rgba(239, 68, 68, 0.15)", padding: "6px 10px", borderRadius: "4px" }}>
              {errorMsg}
            </div>
          )}
        </div>
      )}

      <div className="form-grid" style={{ display: "grid", gridTemplateColumns: compact ? "1fr" : "repeat(auto-fit, minmax(240px, 1fr))", gap: "14px" }}>
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
            {inputDevices.map((dev: AudioDeviceInfo) => (
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
            {outputDevices.map((dev: AudioDeviceInfo) => (
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
