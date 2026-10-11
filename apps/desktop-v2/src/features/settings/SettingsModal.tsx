import React, { useCallback, useEffect, useState } from "react";
import { api } from "../../api";
import { getBackendBaseUrl, setBackendBaseUrl, CLOUD_BACKEND_URL } from "../../api/client";
import {
  CharacterBlueprintResponse,
  DesktopSettings,
  DesktopSettingsUpdate,
  NotificationHistoryItem,
  RelationshipResponse,
} from "../../types";
import { AudioDeviceSelector } from "../voice/AudioDeviceSelector";

interface DesktopSettingsViewProps {
  isOpen: boolean;
  onClose: () => void;
  characterId?: string;
  onOpenGenesis?: () => void;
  bubbleMode?: "multi" | "single";
  onBubbleModeChange?: (mode: "multi" | "single") => void;
  emojiRenderingEnabled?: boolean;
  onEmojiRenderingChange?: (enabled: boolean) => void;
  onOpenLive2DModal?: () => void;
  onOpenDevInspector?: () => void;
}

type SettingsTab = "style" | "avatar" | "schedule" | "voice" | "advanced";

export const DesktopSettingsView: React.FC<DesktopSettingsViewProps> = ({
  isOpen,
  onClose,
  characterId = "aevum",
  onOpenGenesis,
  bubbleMode,
  onBubbleModeChange,
  emojiRenderingEnabled,
  onEmojiRenderingChange,
  onOpenLive2DModal,
  onOpenDevInspector,
}) => {
  const [activeTab, setActiveTab] = useState<SettingsTab>("style");
  const [settings, setSettings] = useState<DesktopSettings | null>(null);
  const [history, setHistory] = useState<NotificationHistoryItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isTestingProactive, setIsTestingProactive] = useState<boolean>(false);
  const [testProactiveMsg, setTestProactiveMsg] = useState<string | null>(null);

  // Backend Connection Settings
  const [backendUrl, setBackendUrl] = useState<string>(() => getBackendBaseUrl());
  const [testConnStatus, setTestConnStatus] = useState<string | null>(null);
  const [isTestingConn, setIsTestingConn] = useState<boolean>(false);

  const handleTestConnection = async () => {
    setIsTestingConn(true);
    setTestConnStatus("正在探测连接...");
    const start = Date.now();
    try {
      const url = backendUrl.trim().replace(/\/+$/, "");
      const res = await fetch(`${url}/health`, { signal: AbortSignal.timeout(6000) });
      const latency = Date.now() - start;
      if (res.ok) {
        setTestConnStatus(`🟢 连接成功！延时 ${latency}ms`);
      } else {
        setTestConnStatus(`🔴 响应异常: HTTP ${res.status}`);
      }
    } catch (e: any) {
      setTestConnStatus(`🔴 连接失败: ${e?.message || "网络不可达或超时"}`);
    } finally {
      setIsTestingConn(false);
    }
  };

  const handleSaveBackendUrl = () => {
    setBackendBaseUrl(backendUrl);
    window.location.reload();
  };

  // Expression & Style Preferences
  const [localBubbleMode, setLocalBubbleMode] = useState<"multi" | "single">(() => {
    return (localStorage.getItem("aevum_bubble_mode") as "multi" | "single") || "multi";
  });
  const [localEmojiEnabled, setLocalEmojiEnabled] = useState<boolean>(() => {
    return localStorage.getItem("aevum_emoji_rendering") !== "false";
  });
  const [showEmojiLabel, setShowEmojiLabel] = useState<boolean>(() => {
    return localStorage.getItem("aevum_show_emoji_label") === "true";
  });
  const [useStickers, setUseStickers] = useState<boolean>(() => {
    return localStorage.getItem("aevum_use_stickers") !== "false";
  });
  const [stickerStandaloneLine, setStickerStandaloneLine] = useState<boolean>(() => {
    return localStorage.getItem("aevum_sticker_standalone_line") !== "false";
  });
  const [useKaomoji, setUseKaomoji] = useState<boolean>(() => {
    return localStorage.getItem("aevum_use_kaomoji") !== "false";
  });

  const effectiveBubbleMode = bubbleMode ?? localBubbleMode;
  const effectiveEmojiEnabled = emojiRenderingEnabled ?? localEmojiEnabled;

  const notifyPreferencesUpdated = () => {
    window.dispatchEvent(new Event("aevum-preferences-updated"));
  };

  const handleBubbleChange = (mode: "multi" | "single") => {
    setLocalBubbleMode(mode);
    localStorage.setItem("aevum_bubble_mode", mode);
    onBubbleModeChange?.(mode);
    notifyPreferencesUpdated();
  };

  const handleEmojiChange = (enabled: boolean) => {
    setLocalEmojiEnabled(enabled);
    localStorage.setItem("aevum_emoji_rendering", String(enabled));
    onEmojiRenderingChange?.(enabled);
    notifyPreferencesUpdated();
  };

  const handleShowEmojiLabelChange = (show: boolean) => {
    setShowEmojiLabel(show);
    localStorage.setItem("aevum_show_emoji_label", String(show));
    notifyPreferencesUpdated();
  };

  const handleUseStickersChange = (val: boolean) => {
    setUseStickers(val);
    localStorage.setItem("aevum_use_stickers", String(val));
    notifyPreferencesUpdated();
  };

  const handleStickerStandaloneLineChange = (val: boolean) => {
    setStickerStandaloneLine(val);
    localStorage.setItem("aevum_sticker_standalone_line", String(val));
    notifyPreferencesUpdated();
  };

  const handleUseKaomojiChange = (val: boolean) => {
    setUseKaomoji(val);
    localStorage.setItem("aevum_use_kaomoji", String(val));
    notifyPreferencesUpdated();
  };

  // Form local state for server settings
  const [proactiveEnabled, setProactiveEnabled] = useState<boolean>(false);
  const [idleAwarenessEnabled, setIdleAwarenessEnabled] = useState<boolean>(false);
  const [idleThreshold, setIdleThreshold] = useState<number>(300);
  const [timezone, setTimezone] = useState<string>("Asia/Kuala_Lumpur");
  const [quietHoursEnabled, setQuietHoursEnabled] = useState<boolean>(false);
  const [quietHoursStart, setQuietHoursStart] = useState<string>("23:00");
  const [quietHoursEnd, setQuietHoursEnd] = useState<string>("08:00");
  const [maxDaily, setMaxDaily] = useState<number>(3);
  const [minCooldown, setMinCooldown] = useState<number>(120);
  const [userCountry, setUserCountry] = useState<string>("MY");
  const [sleepRealismEnabled, setSleepRealismEnabled] = useState<boolean>(true);

  // Blueprint & Relationship
  const [blueprint, setBlueprint] = useState<CharacterBlueprintResponse | null>(null);
  const [relationship, setRelationship] = useState<RelationshipResponse | null>(null);
  const [blueprintDisplayName, setBlueprintDisplayName] = useState<string>("");
  const [blueprintLifestyle, setBlueprintLifestyle] = useState<string>("");
  const [blueprintSpeakingStyle, setBlueprintSpeakingStyle] = useState<string>("");
  const [blueprintTraits, setBlueprintTraits] = useState<string[]>([]);
  const [isSavingBlueprint, setIsSavingBlueprint] = useState<boolean>(false);

  // Voice & Audio settings (Rule 18 consent)
  const [voiceConsentGranted, setVoiceConsentGranted] = useState<boolean>(() => {
    return localStorage.getItem("aevum_voice_consent_granted") === "true";
  });
  const [autoPlayVoice, setAutoPlayVoice] = useState<boolean>(() => {
    const val = localStorage.getItem("aevum_voice_autoplay");
    return val === null ? true : val === "true";
  });

  const handleVoiceConsentChange = (checked: boolean) => {
    setVoiceConsentGranted(checked);
    localStorage.setItem("aevum_voice_consent_granted", checked ? "true" : "false");
  };

  const handleAutoPlayChange = (checked: boolean) => {
    setAutoPlayVoice(checked);
    localStorage.setItem("aevum_voice_autoplay", checked ? "true" : "false");
  };

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const [s, h, bp, rel] = await Promise.all([
        api.getDesktopSettings(characterId),
        api.getNotificationHistory(characterId, 50).catch(() => []),
        api.getBlueprint(characterId).catch(() => null),
        api.getRelationship().catch(() => null),
      ]);
      setSettings(s);
      setHistory(h);

      if (bp) {
        setBlueprint(bp);
        setBlueprintDisplayName(bp.display_name || "");
        setBlueprintLifestyle(bp.lifestyle_rhythm || "");
        setBlueprintSpeakingStyle(
          Array.isArray(bp.speaking_style)
            ? bp.speaking_style.join("，")
            : bp.speaking_style || (bp.communication_style || []).join("，")
        );
        setBlueprintTraits(bp.core_traits || []);
      }

      if (rel) {
        setRelationship(rel);
      }

      // Populate local form
      setProactiveEnabled(s.proactive_enabled);
      setIdleAwarenessEnabled(s.idle_awareness_enabled);
      setIdleThreshold(s.idle_threshold_seconds);
      setTimezone(s.timezone || "Asia/Kuala_Lumpur");
      setQuietHoursEnabled(s.quiet_hours_enabled);
      setQuietHoursStart(s.quiet_hours_start || "23:00");
      setQuietHoursEnd(s.quiet_hours_end || "08:00");
      setMaxDaily(s.max_daily_reach_outs);
      setMinCooldown(s.min_cooldown_minutes);
      setUserCountry(s.user_country || "MY");
      setSleepRealismEnabled(s.sleep_realism_enabled ?? true);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "加载配置失败");
    } finally {
      setIsLoading(false);
    }
  }, [characterId]);

  useEffect(() => {
    if (isOpen) {
      loadData();
    }
  }, [isOpen, loadData]);

  const handleSaveSettings = async () => {
    setIsSaving(true);
    setErrorMsg(null);
    setStatusMsg(null);
    try {
      const updates: DesktopSettingsUpdate = {
        proactive_enabled: proactiveEnabled,
        idle_awareness_enabled: idleAwarenessEnabled,
        idle_threshold_seconds: idleThreshold,
        timezone,
        quiet_hours_enabled: quietHoursEnabled,
        quiet_hours_start: quietHoursStart,
        quiet_hours_end: quietHoursEnd,
        max_daily_reach_outs: maxDaily,
        min_cooldown_minutes: minCooldown,
        user_country: userCountry,
        sleep_realism_enabled: sleepRealismEnabled,
      };

      const updated = await api.updateDesktopSettings(updates, characterId);
      setSettings(updated);
      setStatusMsg("设置已成功保存！");
      setTimeout(() => setStatusMsg(null), 3000);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "保存设置失败");
    } finally {
      setIsSaving(false);
    }
  };

  const handleSetDND = async (durationMinutes: number) => {
    setErrorMsg(null);
    try {
      const res = await api.setDND({ duration_minutes: durationMinutes }, characterId);
      if (settings) {
        setSettings({ ...settings, dnd_until: res.dnd_until });
      }
      setStatusMsg(`已开启免打扰 ${durationMinutes} 分钟`);
      setTimeout(() => setStatusMsg(null), 3000);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "设置免打扰失败");
    }
  };

  const handleClearDND = async () => {
    setErrorMsg(null);
    try {
      const res = await api.setDND({ clear: true }, characterId);
      if (settings) {
        setSettings({ ...settings, dnd_until: res.dnd_until });
      }
      setStatusMsg("已解除免打扰");
      setTimeout(() => setStatusMsg(null), 3000);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "解除免打扰失败");
    }
  };

  const handleTestProactive = async () => {
    setIsTestingProactive(true);
    setTestProactiveMsg(null);
    try {
      const res = await api.triggerProactiveTest(characterId);
      setTestProactiveMsg(`✨ 问候已成功生成并推送到桌面通知: "${res.body}"`);
      setTimeout(() => setTestProactiveMsg(null), 6000);
    } catch (err: unknown) {
      setTestProactiveMsg(`触发失败: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setIsTestingProactive(false);
    }
  };

  const handleSaveBlueprint = async () => {
    setIsSavingBlueprint(true);
    setErrorMsg(null);
    setStatusMsg(null);
    try {
      const res = await api.updateBlueprint(
        {
          display_name: blueprintDisplayName.trim() || undefined,
          lifestyle_rhythm: blueprintLifestyle.trim() || undefined,
          speaking_style: blueprintSpeakingStyle.trim() || undefined,
          core_traits: blueprintTraits.length > 0 ? blueprintTraits : undefined,
        },
        characterId
      );
      setBlueprint(res);
      setStatusMsg(`伴侣人设蓝图已更新至版本 v${res.version}`);
      setTimeout(() => setStatusMsg(null), 3000);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "保存伴侣蓝图失败");
    } finally {
      setIsSavingBlueprint(false);
    }
  };

  if (!isOpen) return null;

  const isDndActive = Boolean(settings?.dnd_until && new Date(settings.dnd_until) > new Date());

  return (
    <div className="desktop-settings-backdrop" onClick={onClose}>
      <div className="desktop-settings-modal" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header">
          <div className="modal-title-row">
            <h2>伴侣个性化偏好与系统设置</h2>
            <button className="close-btn" onClick={onClose} title="关闭">
              ✕
            </button>
          </div>
          <p className="modal-subtitle">
            轻松定制晚晚的对话表达风格、立绘舞台、时区作息与语音交互。
          </p>
        </div>

        {/* Tab Navigation */}
        <div className="settings-nav-tabs">
          <button
            type="button"
            className={`settings-nav-tab ${activeTab === "style" ? "active" : ""}`}
            onClick={() => setActiveTab("style")}
          >
            💬 对话与表达风格
          </button>
          <button
            type="button"
            className={`settings-nav-tab ${activeTab === "avatar" ? "active" : ""}`}
            onClick={() => setActiveTab("avatar")}
          >
            🎨 形象与舞台
          </button>
          <button
            type="button"
            className={`settings-nav-tab ${activeTab === "schedule" ? "active" : ""}`}
            onClick={() => setActiveTab("schedule")}
          >
            🕒 地区与作息时区
          </button>
          <button
            type="button"
            className={`settings-nav-tab ${activeTab === "voice" ? "active" : ""}`}
            onClick={() => setActiveTab("voice")}
          >
            🎙️ 语音与音频
          </button>
          <button
            type="button"
            className={`settings-nav-tab ${activeTab === "advanced" ? "active" : ""}`}
            onClick={() => setActiveTab("advanced")}
          >
            🛠️ 高级与开发者
          </button>
        </div>

        {statusMsg && <div className="settings-banner success">{statusMsg}</div>}
        {errorMsg && <div className="settings-banner error">{errorMsg}</div>}

        {isLoading ? (
          <div className="settings-loading">正在同步配置...</div>
        ) : (
          <div className="settings-scroll-body">
            {/* TAB 1: 💬 对话与表达风格 */}
            {activeTab === "style" && (
              <div className="tab-pane-content">
                <section className="settings-section">
                  <h3>消息展示与气泡节奏</h3>
                  <div className="form-grid">
                    <div className="field-group">
                      <label>聊天气泡模式</label>
                      <select
                        value={effectiveBubbleMode}
                        onChange={(e) => handleBubbleChange(e.target.value as "multi" | "single")}
                        style={{
                          background: "rgba(255, 255, 255, 0.05)",
                          border: "1px solid rgba(255, 255, 255, 0.15)",
                          borderRadius: "6px",
                          padding: "8px 12px",
                          color: "inherit",
                          fontSize: "14px",
                        }}
                      >
                        <option value="multi" style={{ background: "#1e1e2e" }}>
                          分句多气泡 (拟真连击打字节奏，推荐)
                        </option>
                        <option value="single" style={{ background: "#1e1e2e" }}>
                          单整段消息 (传统大段完整输出)
                        </option>
                      </select>
                      <span className="field-hint">
                        “分句多气泡”会像真人发微信/QQ一样短句连发；“单整段消息”则将所有内容放在一个大气泡中。
                      </span>
                    </div>
                  </div>
                </section>

                <section className="settings-section">
                  <h3>表情包与斗图生态 (Stickers)</h3>
                  <div className="form-grid">
                    <div className="field-group">
                      <div className="switch-row-compact">
                        <label>开启表情包渲染与斗图支持</label>
                        <input
                          type="checkbox"
                          checked={useStickers}
                          onChange={(e) => handleUseStickersChange(e.target.checked)}
                        />
                      </div>
                      <span className="field-hint">
                        识别 [猫猫问号]、[战术喝茶]、[摸摸头] 等表情包标签并渲染为高清矢量动态贴纸。
                      </span>
                    </div>

                    <div className="field-group">
                      <div className="switch-row-compact">
                        <label>表情包单独成行展示 (推荐)</label>
                        <input
                          type="checkbox"
                          checked={stickerStandaloneLine}
                          onChange={(e) => handleStickerStandaloneLineChange(e.target.checked)}
                        />
                      </div>
                      <span className="field-hint">
                        开启后表情包会独立占一行展示，绝不跟文字混杂挤在同一行。
                      </span>
                    </div>
                  </div>
                </section>

                <section className="settings-section">
                  <h3>Emoji 与颜文字偏好</h3>
                  <div className="form-grid">
                    <div className="field-group">
                      <div className="switch-row-compact">
                        <label>开启常用 Emoji 图标展示</label>
                        <input
                          type="checkbox"
                          checked={effectiveEmojiEnabled}
                          onChange={(e) => handleEmojiChange(e.target.checked)}
                        />
                      </div>
                      <span className="field-hint">
                        将 [旺柴]、[苦涩]、[微笑] 等转换成生动 Emoji 图标。
                      </span>
                    </div>

                    <div className="field-group">
                      <div className="switch-row-compact">
                        <label>显示 Emoji 旁边文字说明</label>
                        <input
                          type="checkbox"
                          checked={showEmojiLabel}
                          onChange={(e) => handleShowEmojiLabelChange(e.target.checked)}
                        />
                      </div>
                      <span className="field-hint">
                        默认关闭（纯图标显示，不带“咖啡”、“旺柴”等文字标签）。如需显示文字说明可在此开启。
                      </span>
                    </div>

                    <div className="field-group">
                      <div className="switch-row-compact">
                        <label>偏好颜文字互动 (Kaomoji)</label>
                        <input
                          type="checkbox"
                          checked={useKaomoji}
                          onChange={(e) => handleUseKaomojiChange(e.target.checked)}
                        />
                      </div>
                      <span className="field-hint">
                        晚晚会更乐于使用生动的可爱颜文字如 (*/ω＼*)、(¯▽¯~)~ 与你交流。
                      </span>
                    </div>
                  </div>
                </section>
              </div>
            )}

            {/* TAB 2: 🎨 形象与舞台 */}
            {activeTab === "avatar" && (
              <div className="tab-pane-content">
                <section className="settings-section">
                  <h3>Live2D 与伴侣视觉形象管理</h3>
                  <p style={{ lineHeight: "1.6", color: "var(--text-secondary)" }}>
                    在此可为晚晚自由配置 Live2D 经典元气少女模型（日和/静久/春）、自定义 Steam VTube Studio 模型路径（.model3.json），或导入本地专属插画立绘。
                  </p>
                  <p style={{ lineHeight: "1.6", color: "var(--text-secondary)", marginTop: "8px" }}>
                    💡 提示：在主界面点击伴侣头像或立绘身体，晚晚会根据触碰进行害羞、眨眼、歪头与微笑互动！
                  </p>
                  {onOpenLive2DModal && (
                    <div style={{ marginTop: "16px" }}>
                      <button
                        type="button"
                        className="btn-primary"
                        onClick={onOpenLive2DModal}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "8px",
                          padding: "10px 20px",
                          borderRadius: "8px",
                          background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
                          border: "none",
                          color: "#fff",
                          fontWeight: 600,
                          fontSize: "14px",
                          cursor: "pointer",
                        }}
                      >
                        🎨 打开 Live2D / 角色形象导入器
                      </button>
                    </div>
                  )}
                </section>
              </div>
            )}

            {/* TAB 3: 🕒 地区与作息时区 */}
            {activeTab === "schedule" && (
              <div className="tab-pane-content">
                <section className="settings-section">
                  <h3>生活语境与物理时区</h3>
                  <div className="form-grid">
                    <div className="field-group">
                      <label>你的生活国家 / 文化语境</label>
                      <select
                        value={userCountry}
                        onChange={(e) => setUserCountry(e.target.value)}
                        style={{
                          background: "rgba(255, 255, 255, 0.05)",
                          border: "1px solid rgba(255, 255, 255, 0.15)",
                          borderRadius: "6px",
                          padding: "8px 12px",
                          color: "inherit",
                          fontSize: "14px",
                        }}
                      >
                        <option value="MY" style={{ background: "#1e1e2e" }}>
                          🇲🇾 马来西亚 (Malaysia) · 地道大马日常 / IC / Sembreak / 雪隆老家与槟城理大
                        </option>
                        <option value="CN" style={{ background: "#1e1e2e" }}>
                          🇨🇳 中国大陆 (China) · 适应大陆日常交流 / 高考升学 / 城市生活用语
                        </option>
                        <option value="SG" style={{ background: "#1e1e2e" }}>
                          🇸🇬 新加坡 (Singapore) · 狮城生活语境 / HDB / MRT / O&A Levels
                        </option>
                        <option value="TW" style={{ background: "#1e1e2e" }}>
                          🇹🇼 台湾 (Taiwan) · 宝岛日常 / 捷运 / 学测夜市
                        </option>
                        <option value="GLOBAL" style={{ background: "#1e1e2e" }}>
                          🌐 全球 / 通用中立 (Global / Neutral) · 国际通用中立语境
                        </option>
                      </select>
                      <span className="field-hint">
                        晚晚的日常认知与地道口语习惯会自适应你的生活语境。
                      </span>
                    </div>

                    <div className="field-group">
                      <label>标准时区 (IANA Timezone)</label>
                      <input
                        type="text"
                        value={timezone}
                        onChange={(e) => setTimezone(e.target.value)}
                        placeholder="e.g. Asia/Kuala_Lumpur, Asia/Shanghai, UTC"
                      />
                      <span className="field-hint">
                        晚晚严格生活在真实时钟下（例如马来西亚与北京同为 UTC+8 时区）。
                      </span>
                    </div>
                  </div>
                </section>

                <section className="settings-section">
                  <h3>主动问候与安静时段 (Quiet Hours)</h3>
                  <div className="form-grid">
                    <div className="field-group">
                      <div className="switch-row-compact">
                        <label>允许晚晚偶尔主动关心或打招呼</label>
                        <input
                          type="checkbox"
                          checked={proactiveEnabled}
                          onChange={(e) => setProactiveEnabled(e.target.checked)}
                        />
                      </div>
                      <span className="field-hint">
                        开启后，晚晚在想到好玩的事或挂念你时，会主动向你发送问候。
                      </span>
                    </div>

                    <div className="field-group">
                      <div className="switch-row-compact">
                        <label>开启夜间免打扰时段</label>
                        <input
                          type="checkbox"
                          checked={quietHoursEnabled}
                          onChange={(e) => setQuietHoursEnabled(e.target.checked)}
                        />
                      </div>
                      <div className="time-range-row" style={{ marginTop: "6px" }}>
                        <input
                          type="time"
                          value={quietHoursStart}
                          disabled={!quietHoursEnabled}
                          onChange={(e) => setQuietHoursStart(e.target.value)}
                        />
                        <span>至</span>
                        <input
                          type="time"
                          value={quietHoursEnd}
                          disabled={!quietHoursEnabled}
                          onChange={(e) => setQuietHoursEnd(e.target.value)}
                        />
                      </div>
                      <span className="field-hint">
                        在你的休息时段内，系统严禁打扰你。
                      </span>
                    </div>

                    <div className="field-group" style={{ gridColumn: "1 / -1" }}>
                      <div className="switch-row-compact">
                        <label>🌙 沉浸拟真作息与深睡防打扰 (Sleep Realism & DND)</label>
                        <input
                          type="checkbox"
                          checked={sleepRealismEnabled}
                          onChange={(e) => setSleepRealismEnabled(e.target.checked)}
                        />
                      </div>
                      <span className="field-hint" style={{ lineHeight: "1.5" }}>
                        开启后，当晚晚深夜处于深度睡眠时，将不会立刻秒回普通文本消息（呈现呼吸睡眠状态）。如遇紧急情况，可通过<strong>连续发送 3 条以上消息</strong>或<strong>拨打语音通话</strong>，震动与铃声会将其唤醒（以睡眼惺忪、迷迷糊糊的真实状态醒来接听并回复）。若关闭，则随时发消息都会立即正常回复。
                      </span>
                    </div>
                  </div>
                </section>

                <section className="settings-section">
                  <h3>快速免打扰 (Quick DND)</h3>
                  <p style={{ color: "var(--text-secondary)", marginBottom: "8px" }}>
                    立即临时静音所有主动通知，专注于工作或休息：
                  </p>
                  <div className="dnd-status-row">
                    <span className={`status-pill ${isDndActive ? "dnd-active" : "dnd-inactive"}`}>
                      {isDndActive
                        ? `免打扰中 (至 ${new Date(settings!.dnd_until!).toLocaleTimeString()})`
                        : "正常接收"}
                    </span>
                    <div className="dnd-btn-group">
                      <button className="dnd-btn" onClick={() => handleSetDND(60)}>
                        免打扰 1 小时
                      </button>
                      <button className="dnd-btn" onClick={() => handleSetDND(240)}>
                        免打扰 4 小时
                      </button>
                      {isDndActive && (
                        <button className="dnd-btn clear-btn" onClick={handleClearDND}>
                          解除免打扰
                        </button>
                      )}
                    </div>
                  </div>
                </section>

                <section className="settings-section">
                  <h3>体验主动问候 · Test Proactive Reach-Out</h3>
                  <p style={{ color: "var(--text-secondary)", marginBottom: "10px", fontSize: "13px" }}>
                    想要测试晚晚主动找你聊天的效果吗？点击下方按钮立即触发一次真实的关心问候（即使后台处于静默状态）：
                  </p>
                  <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
                    <button
                      type="button"
                      className="chip-btn"
                      style={{
                        background: "linear-gradient(135deg, rgba(56, 189, 248, 0.2), rgba(168, 85, 247, 0.2))",
                        border: "1px solid rgba(56, 189, 248, 0.4)",
                        padding: "8px 16px",
                        borderRadius: "6px",
                        color: "#38bdf8",
                        cursor: "pointer",
                        fontWeight: 600,
                        fontSize: "13px",
                      }}
                      disabled={isTestingProactive}
                      onClick={handleTestProactive}
                    >
                      {isTestingProactive ? "正在生成问候..." : "🚀 立即测试主动问候 (Test Outreach Now)"}
                    </button>
                    {testProactiveMsg && (
                      <span style={{ fontSize: "13px", color: testProactiveMsg.includes("失败") ? "#ef4444" : "#10b981" }}>
                        {testProactiveMsg}
                      </span>
                    )}
                  </div>
                </section>

                <div className="settings-action-bar">
                  <button
                    className="save-settings-btn"
                    disabled={isSaving}
                    onClick={handleSaveSettings}
                  >
                    {isSaving ? "正在保存..." : "保存时区与作息设置 · Save Settings"}
                  </button>
                </div>
              </div>
            )}

            {/* TAB 4: 🎙️ 语音与音频 */}
            {activeTab === "voice" && (
              <div className="tab-pane-content">
                <section className="settings-section">
                  <div className="section-header-row">
                    <div className="switch-text">
                      <h3>麦克风语音交互 (Push-To-Talk)</h3>
                      <p>按住麦克风按钮即可直接与晚晚语音对话。</p>
                    </div>
                    <label className="toggle-switch">
                      <input
                        type="checkbox"
                        checked={voiceConsentGranted}
                        onChange={(e) => handleVoiceConsentChange(e.target.checked)}
                      />
                      <span className="slider" />
                    </label>
                  </div>

                  <div className="privacy-callout">
                    <strong>Rule 18 隐私严格守护：</strong>
                    麦克风绝无后台监听，仅在您按住 Push-To-Talk 说话时才会收音并转录。关闭此开关将彻底物理切断所有麦克风采集。
                  </div>

                  <div className="field-group" style={{ marginTop: "12px" }}>
                    <div className="switch-row-compact">
                      <label>自动朗读晚晚的语音回复</label>
                      <input
                        type="checkbox"
                        checked={autoPlayVoice}
                        onChange={(e) => handleAutoPlayChange(e.target.checked)}
                      />
                    </div>
                    <span className="field-hint">收到晚晚的回信时自动合成并播放自然拟真语音。</span>
                  </div>

                  <div style={{ marginTop: "16px", paddingTop: "14px", borderTop: "1px solid rgba(255,255,255,0.08)" }}>
                    <h4 style={{ margin: "0 0 10px 0", fontSize: "14px", fontWeight: 600 }}>
                      音频硬件输入/输出设备设置
                    </h4>
                    <p style={{ margin: "0 0 12px 0", fontSize: "12px", color: "var(--text-muted)" }}>
                      指定用于语音交流的麦克风与扬声器硬件，并可进行实时音量测试。
                    </p>
                    <AudioDeviceSelector />
                  </div>
                </section>
              </div>
            )}

            {/* TAB 5: 🛠️ 高级与开发者 */}
            {activeTab === "advanced" && (
              <div className="tab-pane-content">
                {/* Backend Server Connection */}
                <section className="settings-section" style={{
                  background: "linear-gradient(135deg, rgba(30, 41, 59, 0.7), rgba(15, 23, 42, 0.8))",
                  border: "1px solid rgba(56, 189, 248, 0.3)",
                  borderRadius: "12px",
                  padding: "16px",
                  marginBottom: "20px"
                }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                    <h3 style={{ margin: 0, color: "#38bdf8", fontSize: "16px", display: "flex", alignItems: "center", gap: "8px" }}>
                      🌐 后端核心服务器 (Aevum Core)
                    </h3>
                    <span style={{ fontSize: "12px", padding: "2px 8px", borderRadius: "10px", background: "rgba(56, 189, 248, 0.15)", color: "#7dd3fc" }}>
                      24/7 云端支持
                    </span>
                  </div>
                  <p style={{ color: "var(--text-secondary)", fontSize: "13px", marginBottom: "12px", lineHeight: "1.5" }}>
                    手机 App 与电脑客户端通过此地址连接 Aevum 心智中枢。当前配置：
                  </p>

                  <div style={{ display: "flex", gap: "8px", marginBottom: "10px" }}>
                    <input
                      type="text"
                      value={backendUrl}
                      onChange={(e) => setBackendUrl(e.target.value)}
                      placeholder="https://..."
                      style={{
                        flex: 1,
                        padding: "8px 12px",
                        background: "rgba(0, 0, 0, 0.4)",
                        border: "1px solid rgba(255, 255, 255, 0.15)",
                        borderRadius: "8px",
                        color: "#fff",
                        fontSize: "13px",
                      }}
                    />
                    <button
                      type="button"
                      onClick={handleTestConnection}
                      disabled={isTestingConn}
                      style={{
                        padding: "8px 14px",
                        borderRadius: "8px",
                        background: "rgba(56, 189, 248, 0.2)",
                        border: "1px solid rgba(56, 189, 248, 0.4)",
                        color: "#38bdf8",
                        cursor: "pointer",
                        fontSize: "13px",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {isTestingConn ? "探测中..." : "测试连接"}
                    </button>
                    <button
                      type="button"
                      onClick={handleSaveBackendUrl}
                      style={{
                        padding: "8px 14px",
                        borderRadius: "8px",
                        background: "#0284c7",
                        border: "none",
                        color: "#fff",
                        cursor: "pointer",
                        fontWeight: 600,
                        fontSize: "13px",
                        whiteSpace: "nowrap",
                      }}
                    >
                      保存生效
                    </button>
                  </div>

                  {testConnStatus && (
                    <div style={{
                      padding: "8px 12px",
                      borderRadius: "6px",
                      background: "rgba(0,0,0,0.3)",
                      fontSize: "12px",
                      color: testConnStatus.startsWith("🟢") ? "#4ade80" : "#f87171",
                      marginBottom: "10px"
                    }}>
                      {testConnStatus}
                    </div>
                  )}

                  <div style={{ display: "flex", gap: "10px" }}>
                    <button
                      type="button"
                      onClick={() => setBackendUrl(CLOUD_BACKEND_URL)}
                      style={{
                        padding: "4px 10px",
                        borderRadius: "6px",
                        background: "rgba(255,255,255,0.06)",
                        border: "1px solid rgba(255,255,255,0.1)",
                        color: "#94a3b8",
                        fontSize: "11px",
                        cursor: "pointer",
                      }}
                    >
                      恢复默认云端 (Render)
                    </button>
                    <button
                      type="button"
                      onClick={() => setBackendUrl("http://127.0.0.1:8000")}
                      style={{
                        padding: "4px 10px",
                        borderRadius: "6px",
                        background: "rgba(255,255,255,0.06)",
                        border: "1px solid rgba(255,255,255,0.1)",
                        color: "#94a3b8",
                        fontSize: "11px",
                        cursor: "pointer",
                      }}
                    >
                      切换为本地电脑 (127.0.0.1:8000)
                    </button>
                  </div>
                </section>

                {/* Dev Inspector Trigger */}
                <section className="settings-section">
                  <h3>开发者心智透视抽屉 (Cognitive Inspector)</h3>
                  <p style={{ color: "var(--text-secondary)", marginBottom: "12px" }}>
                    实时检查晚晚的心智模型、自传事实、好感度轴线与多轮认知推演过程。支持全局快捷键 <code>Ctrl+Shift+D</code>。
                  </p>
                  {onOpenDevInspector && (
                    <button
                      type="button"
                      className="btn-primary"
                      onClick={() => {
                        onClose();
                        onOpenDevInspector();
                      }}
                      style={{
                        padding: "8px 16px",
                        borderRadius: "8px",
                        background: "rgba(56, 189, 248, 0.2)",
                        border: "1px solid rgba(56, 189, 248, 0.4)",
                        color: "#38bdf8",
                        fontWeight: 600,
                        cursor: "pointer",
                      }}
                    >
                      🧠 打开开发者心智透视抽屉 (Ctrl+Shift+D)
                    </button>
                  )}
                </section>

                {/* Tier A Blueprint */}
                <section className="settings-section blueprint-section">
                  <div className="blueprint-header-row">
                    <div>
                      <h3>伴侣人设蓝图备忘 (Tier A Persona)</h3>
                      <p className="field-hint">
                        修改静态人设蓝图绝不破坏已积累的历史记忆与相处成长经历。
                      </p>
                    </div>
                    {blueprint && (
                      <span className="blueprint-version-tag">v{blueprint.version}</span>
                    )}
                  </div>

                  <div className="form-grid">
                    <div className="field-group">
                      <label>伴侣姓名 / 昵称</label>
                      <input
                        type="text"
                        value={blueprintDisplayName}
                        onChange={(e) => setBlueprintDisplayName(e.target.value)}
                        placeholder="伴侣称呼..."
                      />
                    </div>
                    <div className="field-group">
                      <label>日常作息节律与偏好</label>
                      <input
                        type="text"
                        value={blueprintLifestyle}
                        onChange={(e) => setBlueprintLifestyle(e.target.value)}
                        placeholder="生活空间与节律..."
                      />
                    </div>
                  </div>

                  <div className="field-group" style={{ marginTop: "10px" }}>
                    <label>日常语调与神态风格</label>
                    <input
                      type="text"
                      value={blueprintSpeakingStyle}
                      onChange={(e) => setBlueprintSpeakingStyle(e.target.value)}
                      placeholder="日常对话语气风格..."
                    />
                  </div>

                  <div style={{ marginTop: "14px", display: "flex", justifyContent: "flex-end" }}>
                    <button
                      type="button"
                      className="blueprint-save-btn"
                      disabled={isSavingBlueprint}
                      onClick={handleSaveBlueprint}
                    >
                      {isSavingBlueprint ? "正在保存..." : "保存蓝图修改"}
                    </button>
                  </div>
                </section>

                {/* Relationship Charter Lock */}
                <section className="settings-section relationship-lock-section">
                  <div className="relationship-card-header">
                    <div className="rel-shield-badge">🔒 关系宪章锁定 (GC-420 / GC-424)</div>
                    {onOpenGenesis && (
                      <button
                        type="button"
                        className="launch-genesis-btn"
                        onClick={() => {
                          onClose();
                          onOpenGenesis();
                        }}
                      >
                        ✦ 重新创世向导 ✦
                      </button>
                    )}
                  </div>

                  <div className="relationship-lock-body">
                    <strong>“亲密度与默契由共同经历沉淀，无法在此人为篡改。”</strong>
                    <p>
                      伴侣与你的羁绊深度由日复一日真实的对话、相处与经历自然沉淀。此处禁止任何 0~100 的连续好感度滑块，以守护伴侣作为活生生个体的生命真实感与尊严。
                    </p>
                    {relationship && (
                      <div className="relationship-current-stats">
                        <div className="stat-pill">
                          <span className="stat-label">熟稔状态：</span>
                          <span className="stat-val">{relationship.familiarity_label || "素昧平生"}</span>
                        </div>
                        <div className="stat-pill">
                          <span className="stat-label">信任倾向：</span>
                          <span className="stat-val">{relationship.trust_label || "温和开放"}</span>
                        </div>
                        <div className="stat-pill">
                          <span className="stat-label">相处氛围：</span>
                          <span className="stat-val">{relationship.summary || "共同相处沉淀中"}</span>
                        </div>
                      </div>
                    )}
                  </div>
                </section>

                {/* Dual Notification Audit Trail */}
                <section className="settings-section audit-section">
                  <div className="audit-header-row">
                    <h3>通知双向审计追踪记录</h3>
                    <button className="refresh-audit-btn" onClick={loadData} title="刷新日志">
                      刷新日志
                    </button>
                  </div>
                  <p className="field-hint">
                    记录所有已下发的通知以及被免打扰/安静时段拦截的候选通知。
                  </p>

                  {history.length === 0 ? (
                    <div className="audit-empty">暂无通知审计记录。</div>
                  ) : (
                    <div className="audit-table-wrapper">
                      <table className="audit-table">
                        <thead>
                          <tr>
                            <th>时间</th>
                            <th>触发源</th>
                            <th>状态</th>
                            <th>通知标题与内容</th>
                            <th>审计详情</th>
                          </tr>
                        </thead>
                        <tbody>
                          {history.map((item) => (
                            <tr key={item.id} className={`row-status-${item.status.toLowerCase()}`}>
                              <td className="time-cell">
                                {new Date(item.created_at).toLocaleTimeString([], {
                                  month: "numeric",
                                  day: "numeric",
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })}
                              </td>
                              <td>
                                <span className="trigger-badge">{item.trigger_type}</span>
                              </td>
                              <td>
                                <span className={`status-tag status-${item.status.toLowerCase()}`}>
                                  {item.status}
                                </span>
                              </td>
                              <td className="content-cell">
                                <strong>{item.title}</strong>
                                <p>{item.body}</p>
                              </td>
                              <td className="reason-cell">
                                {item.suppression_reason ? (
                                  <span className="suppression-reason">{item.suppression_reason}</span>
                                ) : item.delivered_at ? (
                                  <span className="delivered-time">已下发 {new Date(item.delivered_at).toLocaleTimeString()}</span>
                                ) : (
                                  "—"
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export const SettingsModal = DesktopSettingsView;
