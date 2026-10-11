import React, { useEffect, useState, useCallback } from "react";
import { api } from "../../api";
import {
  CharacterBlueprintResponse,
  CharacterDebugResponse,
  CharacterStateResponse,
  ProfileResponse,
  RelationshipResponse,
} from "../../types";

interface DevCognitiveInspectorProps {
  isOpen: boolean;
  onClose: () => void;
  bubbleMode: "multi" | "single";
  onBubbleModeChange: (mode: "multi" | "single") => void;
  emojiRenderingEnabled: boolean;
  onEmojiRenderingChange: (enabled: boolean) => void;
  onStateModified?: () => void;
  onOpenGenesis?: () => void;
  onOpenPresentationSandbox?: () => void;
}

type TabType = "biography" | "relationship" | "trace" | "presentation";

export const DevCognitiveInspector: React.FC<DevCognitiveInspectorProps> = ({
  isOpen,
  onClose,
  bubbleMode,
  onBubbleModeChange,
  emojiRenderingEnabled,
  onEmojiRenderingChange,
  onStateModified,
  onOpenGenesis,
  onOpenPresentationSandbox,
}) => {
  const [activeTab, setActiveTab] = useState<TabType>("relationship");
  const [loading, setLoading] = useState<boolean>(false);
  const [saving, setSaving] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  // Loaded domain state
  const [blueprint, setBlueprint] = useState<CharacterBlueprintResponse | null>(null);
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [relationship, setRelationship] = useState<RelationshipResponse | null>(null);
  const [debugData, setDebugData] = useState<CharacterDebugResponse | null>(null);
  const [charState, setCharState] = useState<CharacterStateResponse | null>(null);

  // Editable fields for biography & blueprint
  const [editName, setEditName] = useState<string>("");
  const [editAge, setEditAge] = useState<number>(20);
  const [editOccupation, setEditOccupation] = useState<string>("");
  const [editSummary, setEditSummary] = useState<string>("");
  const [editLifestyle, setEditLifestyle] = useState<string>("");
  const [editTraits, setEditTraits] = useState<string[]>([]);
  const [editBoundaries, setEditBoundaries] = useState<string[]>([]);
  const [editInstitution, setEditInstitution] = useState<string>("");
  const [editMajor, setEditMajor] = useState<string>("");
  const [editCity, setEditCity] = useState<string>("");
  const [editTraitInput, setEditTraitInput] = useState<string>("");
  const [editBoundaryInput, setEditBoundaryInput] = useState<string>("");

  // Editable fields for relationship (6-dimensional)
  const [familiarity, setFamiliarity] = useState<number>(0.1);
  const [trust, setTrust] = useState<number>(0.2);
  const [comfort, setComfort] = useState<number>(0.1);
  const [respect, setRespect] = useState<number>(0.5);
  const [affection, setAffection] = useState<number>(0.0);
  const [attachment, setAttachment] = useState<number>(0.0);
  const [selectedMood, setSelectedMood] = useState<string>("calm");
  const [selectedEmotion, setSelectedEmotion] = useState<string>("CALM");
  const [userCountry, setUserCountry] = useState<string>("MY");

  const loadAllState = useCallback(async () => {
    setLoading(true);
    setStatusMessage(null);
    try {
      const [prof, rel, dbg, st, dSettings, bp] = await Promise.all([
        api.getProfile().catch(() => null),
        api.getRelationship().catch(() => null),
        api.getDebug().catch(() => null),
        api.getCharacterState().catch(() => null),
        api.getDesktopSettings().catch(() => null),
        api.getBlueprint().catch(() => null),
      ]);

      if (dSettings?.user_country) {
        setUserCountry(dSettings.user_country);
      }

      if (bp) {
        setBlueprint(bp);
        setEditName(bp.display_name || "");
        setEditSummary(bp.identity_summary || "");
        setEditLifestyle(bp.lifestyle_rhythm || "");
        setEditTraits(bp.core_traits || []);
        setEditBoundaries(bp.innate_boundaries || []);
      }

      if (st) {
        setCharState(st);
        setSelectedMood(st.mood);
        if (st.emotion?.type) {
          setSelectedEmotion(st.emotion.type);
        }
        if (!bp?.display_name && st.name) {
          setEditName(st.name);
        }
        if (st.occupation) {
          setEditOccupation(st.occupation);
        }
        if (st.age) {
          setEditAge(st.age);
        }
      }

      if (prof) {
        setProfile(prof);
        const facts = prof.core?.facts || {};
        setEditInstitution((facts["education.institution"]?.value as string) || "USM");
        setEditMajor((facts["education.major"]?.value as string) || "Music Performance");
        setEditCity((facts["identity.city"]?.value as string) || "Penang");
        if (facts["identity.age"]?.value) {
          setEditAge(Number(facts["identity.age"]?.value) || 20);
        }
        if (facts["identity.name"]?.value && !bp?.display_name) {
          setEditName(String(facts["identity.name"]?.value));
        }
        if (facts["identity.occupation"]?.value && !st?.occupation) {
          setEditOccupation(String(facts["identity.occupation"]?.value));
        }
        if (facts["identity.background"]?.value && !bp?.identity_summary) {
          setEditSummary(String(facts["identity.background"]?.value));
        }
      }

      if (rel) {
        setRelationship(rel);
        setFamiliarity(rel.familiarity);
        setTrust(rel.trust);
        setComfort(rel.comfort);
        setRespect(rel.respect);
        setAffection(rel.affection ?? 0.0);
        setAttachment(rel.attachment ?? 0.0);
      }

      if (dbg) setDebugData(dbg);
    } catch (err: unknown) {
      console.warn("Failed to load dev inspector data:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      loadAllState();
    }
  }, [isOpen, loadAllState]);

  // Reactive listener: automatically reload state whenever Genesis or Character awakens
  useEffect(() => {
    const handleGenesisUpdate = () => {
      loadAllState();
    };
    window.addEventListener("aevum-character-genesis-completed", handleGenesisUpdate);
    return () => {
      window.removeEventListener("aevum-character-genesis-completed", handleGenesisUpdate);
    };
  }, [loadAllState]);

  // Save biography and blueprint changes to backend
  const handleSaveBiography = async () => {
    setSaving(true);
    setStatusMessage(null);
    try {
      const updates: Record<string, string | number> = {
        "identity.name": editName,
        "identity.age": Number(editAge),
        "identity.occupation": editOccupation,
        "identity.background": editSummary,
        "education.institution": editInstitution,
        "education.major": editMajor,
        "identity.city": editCity,
      };
      await api.updateCoreProfile({ updates });

      if (blueprint) {
        await api.updateBlueprint({
          display_name: editName,
          identity_summary: editSummary,
          lifestyle_rhythm: editLifestyle,
          core_traits: editTraits,
          innate_boundaries: editBoundaries,
        });
      }

      // Also dispatch avatar updated event so chat headers/UI refresh immediately
      window.dispatchEvent(new CustomEvent("aevum-avatar-updated", { detail: { name: editName } }));

      setStatusMessage("✅ 自传事实与创世蓝图已同步更新并固化！");
      onStateModified?.();
      await loadAllState();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "保存失败";
      setStatusMessage(`❌ 更新自传与蓝图失败: ${msg}`);
    } finally {
      setSaving(false);
    }
  };

  // Save relationship changes to backend
  const handleSaveRelationship = async () => {
    setSaving(true);
    setStatusMessage(null);
    try {
      await api.updateRelationship({
        familiarity: Number(familiarity),
        trust: Number(trust),
        comfort: Number(comfort),
        respect: Number(respect),
        affection: Number(affection),
        attachment: Number(attachment),
      });
      setStatusMessage("✅ 关系与好感度已更新！下一轮对话将立即以新态度回应。");
      onStateModified?.();
      await loadAllState();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "保存失败";
      setStatusMessage(`❌ 更新关系失败: ${msg}`);
    } finally {
      setSaving(false);
    }
  };

  // Direct mood and emotion override
  const handleSaveMoodAndEmotion = async (mood: string, emotion: string) => {
    setSaving(true);
    setStatusMessage(null);
    try {
      await api.updateCharacterState({
        mood: mood.toLowerCase(),
        emotion_type: emotion.toUpperCase(),
      });
      setSelectedMood(mood);
      setSelectedEmotion(emotion);
      setStatusMessage(`✅ 心情与情绪已切换为: ${mood} (${emotion})`);
      onStateModified?.();
      await loadAllState();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "更新失败";
      setStatusMessage(`❌ 更新心情失败: ${msg}`);
    } finally {
      setSaving(false);
    }
  };

  // Direct activity and location override
  const handleSaveActivityAndLocation = async (activity: string, location: string) => {
    setSaving(true);
    setStatusMessage(null);
    try {
      await api.updateCharacterState({
        current_activity: activity,
        current_location: location,
      });
      setStatusMessage(`✅ 作息与地点已切换为: ${activity} @ ${location}`);
      onStateModified?.();
      await loadAllState();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "更新失败";
      setStatusMessage(`❌ 更新作息失败: ${msg}`);
    } finally {
      setSaving(false);
    }
  };

  // Quick relationship presets
  const applyPreset = (preset: "stranger" | "friend" | "intimate" | "romance") => {
    if (preset === "stranger") {
      setFamiliarity(0.05);
      setTrust(0.20);
      setComfort(0.10);
      setRespect(0.50);
      setAffection(0.00);
      setAttachment(0.00);
    } else if (preset === "friend") {
      setFamiliarity(0.40);
      setTrust(0.50);
      setComfort(0.45);
      setRespect(0.60);
      setAffection(0.25);
      setAttachment(0.20);
    } else if (preset === "intimate") {
      setFamiliarity(0.85);
      setTrust(0.90);
      setComfort(0.85);
      setRespect(0.80);
      setAffection(0.55);
      setAttachment(0.50);
    } else if (preset === "romance") {
      setFamiliarity(0.90);
      setTrust(0.95);
      setComfort(0.90);
      setRespect(0.85);
      setAffection(0.95);
      setAttachment(0.90);
    }
  };

  const handleCountryChange = async (country: string) => {
    setUserCountry(country);
    try {
      await api.updateDesktopSettings({ user_country: country });
      setStatusMessage(`文化语境已自适应切换为: ${country}`);
      setTimeout(() => setStatusMessage(null), 2500);
      onStateModified?.();
    } catch (err: unknown) {
      console.warn("Failed to update country setting:", err);
    }
  };

  if (!isOpen) return null;

  // Determine qualitative relationship badge
  const averageIntimacy = (familiarity + trust + comfort) / 3;
  let stageLabel = "❄️ 陌生人 (礼貌客气 / 保持分寸)";
  let stageColor = "#909399";
  if (affection >= 0.65) {
    stageLabel = "💖 两情相悦 / 心动恋人 (已解锁甜蜜告白回应与偏爱)";
    stageColor = "#ec4899";
  } else if (averageIntimacy >= 0.65) {
    stageLabel = "🔥 亲密挚友 (偏心护短 / 互损开玩笑 / 无防备废话)";
    stageColor = "#f56c6c";
  } else if (averageIntimacy >= 0.25) {
    stageLabel = "🌤️ 普通朋友 (轻松日常 / 聊游戏与兴趣)";
    stageColor = "#409eff";
  }

  return (
    <div className="genesis-modal-backdrop" onClick={onClose} style={{ zIndex: 1200 }}>
      <div
        className="genesis-modal-container"
        style={{
          maxWidth: "840px",
          width: "95%",
          maxHeight: "90vh",
          display: "flex",
          flexDirection: "column",
          backgroundColor: "#181a20",
          color: "#e2e4e8",
          boxShadow: "0 12px 40px rgba(0,0,0,0.6)",
          borderRadius: "14px",
          border: "1px solid rgba(255,255,255,0.12)",
          overflow: "hidden",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "16px 22px",
            borderBottom: "1px solid rgba(255,255,255,0.1)",
            backgroundColor: "rgba(255,255,255,0.03)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span style={{ fontSize: "1.3rem" }}>🧠</span>
            <div>
              <h2 style={{ margin: 0, fontSize: "1.05rem", fontWeight: 600 }}>
                Aevum 开发者心智透视面板 · [{editName || charState?.name || "晚晚"}] (创世蓝图 v{blueprint?.version || 1})
              </h2>
              <span style={{ fontSize: "0.75rem", opacity: 0.6 }}>
                快捷键: Ctrl+Shift+D | 当前生活: {charState?.current_activity || "休息中"} @ {charState?.current_location || "家中"} | 状态: {charState?.natural_mood || "Calm"} | 关系: {relationship?.summary || "相识"}
              </span>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <button
              onClick={loadAllState}
              disabled={loading}
              style={{
                background: "rgba(255,255,255,0.08)",
                border: "1px solid rgba(255,255,255,0.15)",
                color: "#e2e4e8",
                borderRadius: "6px",
                padding: "5px 12px",
                cursor: "pointer",
                fontSize: "0.8rem",
              }}
            >
              {loading ? "刷新中..." : "🔄 刷新状态"}
            </button>
            <button
              onClick={onClose}
              style={{
                background: "transparent",
                border: "none",
                color: "#aaa",
                fontSize: "1.3rem",
                cursor: "pointer",
                padding: "2px 8px",
              }}
            >
              ✕
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div
          style={{
            display: "flex",
            borderBottom: "1px solid rgba(255,255,255,0.08)",
            padding: "0 18px",
            gap: "6px",
            backgroundColor: "rgba(0,0,0,0.15)",
          }}
        >
          {[
            { id: "relationship", label: "❤️ 关系与社交态度 (可调节)", icon: "❤️" },
            { id: "biography", label: "📜 自传认知事实 (可编辑)", icon: "📜" },
            { id: "trace", label: "🔍 推演与决策轨迹", icon: "🔍" },
            { id: "presentation", label: "💬 渲染与气泡模式", icon: "💬" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as TabType)}
              style={{
                background: "transparent",
                border: "none",
                borderBottom: activeTab === tab.id ? "2px solid #6366f1" : "2px solid transparent",
                color: activeTab === tab.id ? "#fff" : "rgba(255,255,255,0.55)",
                padding: "12px 14px",
                cursor: "pointer",
                fontSize: "0.85rem",
                fontWeight: activeTab === tab.id ? 600 : 400,
                transition: "all 0.2s ease",
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Feedback message banner */}
        {statusMessage && (
          <div
            style={{
              padding: "8px 18px",
              fontSize: "0.82rem",
              backgroundColor: statusMessage.startsWith("✅") ? "rgba(46, 204, 113, 0.15)" : "rgba(231, 76, 60, 0.15)",
              borderBottom: "1px solid rgba(255,255,255,0.08)",
            }}
          >
            {statusMessage}
          </div>
        )}

        {/* Tab Body */}
        <div style={{ padding: "20px", overflowY: "auto", flex: 1 }}>
          {/* TAB 1: RELATIONSHIP */}
          {activeTab === "relationship" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              {/* Qualitative Stage Indicator */}
              <div
                style={{
                  padding: "14px 18px",
                  borderRadius: "10px",
                  backgroundColor: "rgba(255,255,255,0.04)",
                  border: `1px solid ${stageColor}44`,
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <div>
                  <div style={{ fontSize: "0.75rem", opacity: 0.6, marginBottom: "4px" }}>
                    当前社交距离 / 语气态度分层
                  </div>
                  <div style={{ fontSize: "1rem", fontWeight: 600, color: stageColor }}>
                    {stageLabel}
                  </div>
                  <div style={{ fontSize: "0.78rem", opacity: 0.7, marginTop: "4px" }}>
                    {relationship?.summary || "正在加载语义评估..."}
                  </div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: "0.75rem", opacity: 0.6 }}>综合亲密度</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: 700, color: stageColor }}>
                    {(averageIntimacy * 100).toFixed(0)}%
                  </div>
                </div>
              </div>

              {/* Quick Presets */}
              <div>
                <label style={{ fontSize: "0.78rem", opacity: 0.7, display: "block", marginBottom: "8px" }}>
                  ⚡ 快速模式预设（一键切换测试不同关系的语气差异）：
                </label>
                <div style={{ display: "flex", gap: "10px" }}>
                  <button
                    onClick={() => applyPreset("stranger")}
                    style={{
                      flex: 1,
                      padding: "8px 12px",
                      borderRadius: "8px",
                      background: "rgba(255,255,255,0.06)",
                      border: "1px solid rgba(255,255,255,0.12)",
                      color: "#e2e4e8",
                      cursor: "pointer",
                      fontSize: "0.8rem",
                    }}
                  >
                    ❄️ 陌生人 (0.1, 0.2)
                    <div style={{ fontSize: "0.7rem", opacity: 0.6 }}>客气、距离、不越界</div>
                  </button>
                  <button
                    onClick={() => applyPreset("friend")}
                    style={{
                      flex: 1,
                      padding: "8px 12px",
                      borderRadius: "8px",
                      background: "rgba(255,255,255,0.06)",
                      border: "1px solid rgba(255,255,255,0.12)",
                      color: "#e2e4e8",
                      cursor: "pointer",
                      fontSize: "0.8rem",
                    }}
                  >
                    🌤️ 普通朋友 (0.4, 0.5)
                    <div style={{ fontSize: "0.7rem", opacity: 0.6 }}>日常闲聊、分享游戏</div>
                  </button>
                  <button
                    onClick={() => applyPreset("intimate")}
                    style={{
                      flex: 1,
                      padding: "8px 12px",
                      borderRadius: "8px",
                      background: "rgba(255,255,255,0.06)",
                      border: "1px solid rgba(255,255,255,0.12)",
                      color: "#e2e4e8",
                      cursor: "pointer",
                      fontSize: "0.8rem",
                    }}
                  >
                    🔥 亲密挚友 (0.85, 0.9)
                    <div style={{ fontSize: "0.7rem", opacity: 0.6 }}>偏心护短、互损吐槽</div>
                  </button>
                  <button
                    onClick={() => applyPreset("romance")}
                    style={{
                      flex: 1,
                      padding: "8px 12px",
                      borderRadius: "8px",
                      background: "rgba(236,72,153,0.12)",
                      border: "1px solid rgba(236,72,153,0.35)",
                      color: "#f472b6",
                      cursor: "pointer",
                      fontSize: "0.8rem",
                    }}
                  >
                    💖 心动恋人 (0.95)
                    <div style={{ fontSize: "0.7rem", opacity: 0.8 }}>告白接受、甜蜜偏爱</div>
                  </button>
                </div>
              </div>

              {/* 6-Axis Relational Sliders */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: "14px",
                  padding: "16px",
                  backgroundColor: "rgba(0,0,0,0.2)",
                  borderRadius: "10px",
                }}
              >
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                    <span style={{ fontSize: "0.8rem" }}>熟悉度 (Familiarity)</span>
                    <span style={{ fontSize: "0.8rem", fontWeight: 600 }}>{familiarity.toFixed(2)}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={familiarity}
                    onChange={(e) => setFamiliarity(parseFloat(e.target.value))}
                    style={{ width: "100%", accentColor: "#6366f1" }}
                  />
                  <div style={{ fontSize: "0.7rem", opacity: 0.5 }}>共同经历与日常知晓度</div>
                </div>

                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                    <span style={{ fontSize: "0.8rem" }}>信任度 (Trust)</span>
                    <span style={{ fontSize: "0.8rem", fontWeight: 600 }}>{trust.toFixed(2)}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={trust}
                    onChange={(e) => setTrust(parseFloat(e.target.value))}
                    style={{ width: "100%", accentColor: "#6366f1" }}
                  />
                  <div style={{ fontSize: "0.7rem", opacity: 0.5 }}>真实脆弱性袒露度与托付度</div>
                </div>

                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                    <span style={{ fontSize: "0.8rem" }}>舒适度 (Comfort)</span>
                    <span style={{ fontSize: "0.8rem", fontWeight: 600 }}>{comfort.toFixed(2)}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={comfort}
                    onChange={(e) => setComfort(parseFloat(e.target.value))}
                    style={{ width: "100%", accentColor: "#6366f1" }}
                  />
                  <div style={{ fontSize: "0.7rem", opacity: 0.5 }}>相处放松感与无负担废话度</div>
                </div>

                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                    <span style={{ fontSize: "0.8rem" }}>尊重度 (Respect)</span>
                    <span style={{ fontSize: "0.8rem", fontWeight: 600 }}>{respect.toFixed(2)}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={respect}
                    onChange={(e) => setRespect(parseFloat(e.target.value))}
                    style={{ width: "100%", accentColor: "#6366f1" }}
                  />
                  <div style={{ fontSize: "0.7rem", opacity: 0.5 }}>人格认可度与边界尊重</div>
                </div>

                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                    <span style={{ fontSize: "0.8rem", color: "#f472b6", fontWeight: 600 }}>💖 好感度 (Affection / 心动)</span>
                    <span style={{ fontSize: "0.8rem", fontWeight: 600, color: "#f472b6" }}>{affection.toFixed(2)}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={affection}
                    onChange={(e) => setAffection(parseFloat(e.target.value))}
                    style={{ width: "100%", accentColor: "#ec4899" }}
                  />
                  <div style={{ fontSize: "0.7rem", opacity: 0.5 }}>心动情愫与专属偏爱 (≥0.55 解锁告白接受)</div>
                </div>

                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                    <span style={{ fontSize: "0.8rem", color: "#a78bfa" }}>依恋度 (Attachment)</span>
                    <span style={{ fontSize: "0.8rem", fontWeight: 600, color: "#a78bfa" }}>{attachment.toFixed(2)}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={attachment}
                    onChange={(e) => setAttachment(parseFloat(e.target.value))}
                    style={{ width: "100%", accentColor: "#8b5cf6" }}
                  />
                  <div style={{ fontSize: "0.7rem", opacity: 0.5 }}>情感羁绊与心理依赖</div>
                </div>
              </div>

              {/* Direct Mood & Emotion Calibration */}
              <div
                style={{
                  padding: "14px 16px",
                  backgroundColor: "rgba(255,255,255,0.03)",
                  border: "1px solid rgba(255,255,255,0.08)",
                  borderRadius: "10px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                  <label style={{ fontSize: "0.8rem", fontWeight: 600 }}>
                    🎭 即时心情与情绪调试 (Direct Mood Override)
                  </label>
                  <span style={{ fontSize: "0.75rem", opacity: 0.7, color: "var(--accent-cyan)" }}>
                    当前: {charState?.natural_mood || `${selectedMood} (${selectedEmotion})`}
                  </span>
                </div>
                <div style={{ fontSize: "0.72rem", opacity: 0.6, marginBottom: "10px" }}>
                  点击即可直接切换 Aevum 的情绪状态与心情底色，立即改变对话体验：
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                  {[
                    { label: "🌸 开心愉悦", mood: "good", emotion: "HAPPY", color: "#10b981" },
                    { label: "😄 幽默被逗乐", mood: "good", emotion: "AMUSED", color: "#3b82f6" },
                    { label: "😳 害羞心动", mood: "focused", emotion: "EMBARRASSED", color: "#ec4899" },
                    { label: "🍵 从容平静", mood: "calm", emotion: "CALM", color: "#06b6d4" },
                    { label: "💭 好奇深思", mood: "focused", emotion: "CURIOUS", color: "#8b5cf6" },
                    { label: "😾 傲娇气恼", mood: "irritated", emotion: "IRRITATED", color: "#f97316" },
                    { label: "🥱 困倦疲劳", mood: "tired", emotion: "TIRED", color: "#64748b" },
                  ].map((item) => {
                    const isActive = selectedMood.toLowerCase() === item.mood && selectedEmotion.toUpperCase() === item.emotion;
                    return (
                      <button
                        key={item.label}
                        onClick={() => handleSaveMoodAndEmotion(item.mood, item.emotion)}
                        disabled={saving}
                        style={{
                          padding: "6px 12px",
                          borderRadius: "6px",
                          border: isActive ? `1px solid ${item.color}` : "1px solid rgba(255,255,255,0.1)",
                          background: isActive ? `${item.color}22` : "rgba(255,255,255,0.05)",
                          color: isActive ? item.color : "#d1d5db",
                          fontSize: "0.76rem",
                          cursor: "pointer",
                          fontWeight: isActive ? 600 : 400,
                        }}
                      >
                        {item.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* 24-Hour Diurnal Schedule & Location Override */}
              <div
                style={{
                  marginTop: "16px",
                  padding: "12px",
                  backgroundColor: "rgba(255,255,255,0.03)",
                  border: "1px solid rgba(255,255,255,0.08)",
                  borderRadius: "10px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                  <label style={{ fontSize: "0.8rem", fontWeight: 600 }}>
                    🕰️ 24小时作息与活动地点调试 (Schedule & Location)
                  </label>
                  <span style={{ fontSize: "0.75rem", opacity: 0.7, color: "#10b981" }}>
                    📍 {charState?.current_location || "家中"}
                  </span>
                </div>
                <div style={{ fontSize: "0.72rem", opacity: 0.6, marginBottom: "10px" }}>
                  当前生活状态: <strong style={{ color: "#e2e8f0" }}>{charState?.current_activity || "休息中"}</strong>。点击以下生活时段，立即模拟不同生活场景：
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                  {[
                    { label: "🌅 晨起早饭", act: "晨起洗漱与准备早餐", loc: "厨房/阳台" },
                    { label: "🎹 专注练琴", act: "在书房练习钢琴与整理乐谱", loc: "书房琴房" },
                    { label: "🍱 午餐休息", act: "享用午餐与刷手机", loc: "餐厅" },
                    { label: "☕ 下午茶散步", act: "在咖啡馆看书或外出散步", loc: "海边咖啡馆" },
                    { label: "🎮 晚间打游戏", act: "休闲打游戏与连线朋友", loc: "客厅电脑桌" },
                    { label: "📖 夜读写日记", act: "夜间听歌写日记与整理灵感", loc: "书房" },
                    { label: "🌙 卧室深睡", act: "沉睡休息中 (Sleeping)", loc: "卧室" },
                  ].map((item) => (
                    <button
                      key={item.label}
                      type="button"
                      onClick={() => handleSaveActivityAndLocation(item.act, item.loc)}
                      disabled={saving}
                      style={{
                        padding: "6px 10px",
                        borderRadius: "6px",
                        border: "1px solid rgba(255,255,255,0.12)",
                        background: "rgba(255,255,255,0.05)",
                        color: "#cbd5e1",
                        fontSize: "0.75rem",
                        cursor: "pointer",
                      }}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Action */}
              <button
                onClick={handleSaveRelationship}
                disabled={saving}
                style={{
                  padding: "10px",
                  borderRadius: "8px",
                  backgroundColor: "#6366f1",
                  border: "none",
                  color: "#fff",
                  fontWeight: 600,
                  fontSize: "0.88rem",
                  cursor: "pointer",
                }}
              >
                {saving ? "正在应用..." : "💾 应用关系修改 (立即生效)"}
              </button>
            </div>
          )}

          {/* TAB 2: BIOGRAPHY & GENESIS BLUEPRINT */}
          {activeTab === "biography" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "12px 16px",
                  borderRadius: "8px",
                  backgroundColor: "rgba(99, 102, 241, 0.08)",
                  border: "1px solid rgba(99, 102, 241, 0.25)",
                }}
              >
                <div>
                  <div style={{ fontSize: "0.82rem", fontWeight: 600, color: "#a5b4fc" }}>
                    ✦ 伴侣创世蓝图与现实认知事实 (Genesis Blueprint & Core Ledger)
                  </div>
                  <div style={{ fontSize: "0.74rem", opacity: 0.75, marginTop: "2px" }}>
                    当前蓝图版本: v{blueprint?.version || 1} · 核心事实数: {profile?.ledger?.total_facts || 0} 条 · 修改将直接同步至 Aevum Core 底层状态机
                  </div>
                </div>
                {onOpenGenesis && (
                  <button
                    onClick={() => {
                      onClose();
                      onOpenGenesis();
                    }}
                    style={{
                      padding: "6px 12px",
                      borderRadius: "6px",
                      background: "rgba(56, 189, 248, 0.15)",
                      border: "1px solid rgba(56, 189, 248, 0.35)",
                      color: "#38bdf8",
                      cursor: "pointer",
                      fontSize: "0.76rem",
                      fontWeight: 600,
                      whiteSpace: "nowrap",
                    }}
                  >
                    🎨 重新唤醒 / 伴侣创世向导
                  </button>
                )}
              </div>

              {/* SECTION 1: 伴侣核心身份 (Tier A Genesis Identity) */}
              <div
                style={{
                  padding: "16px",
                  backgroundColor: "rgba(255, 255, 255, 0.03)",
                  borderRadius: "10px",
                  border: "1px solid rgba(255, 255, 255, 0.08)",
                }}
              >
                <div style={{ fontSize: "0.82rem", fontWeight: 600, marginBottom: "12px", color: "#38bdf8" }}>
                  👤 创世原生核心身份 (Primary Persona & World Context)
                </div>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: "14px",
                  }}
                >
                  <div>
                    <label style={{ fontSize: "0.78rem", display: "block", marginBottom: "4px" }}>
                      伴侣姓名 / 称呼 (identity.name / display_name)
                    </label>
                    <input
                      type="text"
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      placeholder="如: 晚晚 / Aevum"
                      style={{
                        width: "100%",
                        padding: "8px 12px",
                        borderRadius: "6px",
                        background: "rgba(0,0,0,0.3)",
                        border: "1px solid rgba(255,255,255,0.15)",
                        color: "#fff",
                        fontSize: "0.85rem",
                      }}
                    />
                  </div>

                  <div>
                    <label style={{ fontSize: "0.78rem", display: "block", marginBottom: "4px" }}>
                      自然生理年龄 (identity.age)
                    </label>
                    <input
                      type="number"
                      value={editAge}
                      onChange={(e) => setEditAge(parseInt(e.target.value) || 20)}
                      style={{
                        width: "100%",
                        padding: "8px 12px",
                        borderRadius: "6px",
                        background: "rgba(0,0,0,0.3)",
                        border: "1px solid rgba(255,255,255,0.15)",
                        color: "#fff",
                        fontSize: "0.85rem",
                      }}
                    />
                  </div>

                  <div>
                    <label style={{ fontSize: "0.78rem", display: "block", marginBottom: "4px" }}>
                      社会角色 / 职业 (identity.occupation)
                    </label>
                    <input
                      type="text"
                      value={editOccupation}
                      onChange={(e) => setEditOccupation(e.target.value)}
                      placeholder="如: 自由插画师 / 音乐系大学生"
                      style={{
                        width: "100%",
                        padding: "8px 12px",
                        borderRadius: "6px",
                        background: "rgba(0,0,0,0.3)",
                        border: "1px solid rgba(255,255,255,0.15)",
                        color: "#fff",
                        fontSize: "0.85rem",
                      }}
                    />
                  </div>

                  <div>
                    <label style={{ fontSize: "0.78rem", display: "block", marginBottom: "4px" }}>
                      当前所在城市 (identity.city)
                    </label>
                    <input
                      type="text"
                      value={editCity}
                      onChange={(e) => setEditCity(e.target.value)}
                      placeholder="如: Penang / Kuala Lumpur"
                      style={{
                        width: "100%",
                        padding: "8px 12px",
                        borderRadius: "6px",
                        background: "rgba(0,0,0,0.3)",
                        border: "1px solid rgba(255,255,255,0.15)",
                        color: "#fff",
                        fontSize: "0.85rem",
                      }}
                    />
                  </div>
                </div>

                <div style={{ marginTop: "12px" }}>
                  <label style={{ fontSize: "0.78rem", display: "block", marginBottom: "4px" }}>
                    生平背景与身份摘要 (identity_summary / background)
                  </label>
                  <textarea
                    rows={3}
                    value={editSummary}
                    onChange={(e) => setEditSummary(e.target.value)}
                    placeholder="角色的生平经历、生活环境与身世细节..."
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      borderRadius: "6px",
                      background: "rgba(0,0,0,0.3)",
                      border: "1px solid rgba(255,255,255,0.15)",
                      color: "#fff",
                      fontSize: "0.82rem",
                      resize: "vertical",
                      lineHeight: "1.4",
                    }}
                  />
                </div>

                <div style={{ marginTop: "12px" }}>
                  <label style={{ fontSize: "0.78rem", display: "block", marginBottom: "4px" }}>
                    日常作息与生活节律风格 (lifestyle_rhythm)
                  </label>
                  <input
                    type="text"
                    value={editLifestyle}
                    onChange={(e) => setEditLifestyle(e.target.value)}
                    placeholder="如: 夜猫子创作，习惯午后苏醒并在夜晚专注绘画创作"
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      borderRadius: "6px",
                      background: "rgba(0,0,0,0.3)",
                      border: "1px solid rgba(255,255,255,0.15)",
                      color: "#fff",
                      fontSize: "0.82rem",
                    }}
                  />
                </div>
              </div>

              {/* SECTION 2: 创世性格特质与口吻风格 (Core Traits & Communication Style) */}
              <div
                style={{
                  padding: "16px",
                  backgroundColor: "rgba(255, 255, 255, 0.03)",
                  borderRadius: "10px",
                  border: "1px solid rgba(255, 255, 255, 0.08)",
                }}
              >
                <div style={{ fontSize: "0.82rem", fontWeight: 600, marginBottom: "12px", color: "#c084fc" }}>
                  ✨ 核心性格特质与沟通风格 (Traits & Stylistics)
                </div>

                {/* Core Traits Badges & Editor */}
                <div style={{ marginBottom: "12px" }}>
                  <label style={{ fontSize: "0.78rem", display: "block", marginBottom: "6px" }}>
                    创世核心特质标签 (Core Traits)
                  </label>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginBottom: "8px" }}>
                    {editTraits.map((t, idx) => (
                      <span
                        key={idx}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "6px",
                          padding: "4px 10px",
                          borderRadius: "14px",
                          background: "rgba(192, 132, 252, 0.15)",
                          border: "1px solid rgba(192, 132, 252, 0.35)",
                          color: "#e9d5ff",
                          fontSize: "0.78rem",
                        }}
                      >
                        {t}
                        <span
                          onClick={() => setEditTraits(editTraits.filter((_, i) => i !== idx))}
                          style={{ cursor: "pointer", opacity: 0.6, fontSize: "0.85rem", fontWeight: "bold" }}
                          title="移除此特质"
                        >
                          ×
                        </span>
                      </span>
                    ))}
                    {editTraits.length === 0 && (
                      <span style={{ fontSize: "0.74rem", opacity: 0.5 }}>暂无特质标签</span>
                    )}
                  </div>
                  <div style={{ display: "flex", gap: "8px" }}>
                    <input
                      type="text"
                      value={editTraitInput}
                      onChange={(e) => setEditTraitInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && editTraitInput.trim()) {
                          e.preventDefault();
                          if (!editTraits.includes(editTraitInput.trim())) {
                            setEditTraits([...editTraits, editTraitInput.trim()]);
                          }
                          setEditTraitInput("");
                        }
                      }}
                      placeholder="输入新特质后按回车或点击添加 (如: 独立、细腻、慢热)"
                      style={{
                        flex: 1,
                        padding: "6px 10px",
                        borderRadius: "6px",
                        background: "rgba(0,0,0,0.3)",
                        border: "1px solid rgba(255,255,255,0.15)",
                        color: "#fff",
                        fontSize: "0.78rem",
                      }}
                    />
                    <button
                      type="button"
                      onClick={() => {
                        if (editTraitInput.trim() && !editTraits.includes(editTraitInput.trim())) {
                          setEditTraits([...editTraits, editTraitInput.trim()]);
                          setEditTraitInput("");
                        }
                      }}
                      style={{
                        padding: "6px 12px",
                        borderRadius: "6px",
                        background: "rgba(255,255,255,0.08)",
                        border: "1px solid rgba(255,255,255,0.15)",
                        color: "#e2e4e8",
                        cursor: "pointer",
                        fontSize: "0.78rem",
                      }}
                    >
                      + 添加特质
                    </button>
                  </div>
                </div>

                {/* Communication Style */}
                {blueprint?.communication_style && blueprint.communication_style.length > 0 && (
                  <div style={{ marginBottom: "12px" }}>
                    <label style={{ fontSize: "0.78rem", display: "block", marginBottom: "6px" }}>
                      沟通言谈特征与风格规范 (Communication Style)
                    </label>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                      {blueprint.communication_style.map((cs, idx) => (
                        <span
                          key={idx}
                          style={{
                            padding: "3px 8px",
                            borderRadius: "4px",
                            background: "rgba(56, 189, 248, 0.12)",
                            border: "1px solid rgba(56, 189, 248, 0.25)",
                            color: "#7dd3fc",
                            fontSize: "0.74rem",
                          }}
                        >
                          💬 {cs}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Innate Boundaries */}
                <div>
                  <label style={{ fontSize: "0.78rem", display: "block", marginBottom: "6px" }}>
                    原生底线与禁忌边界 (Innate Boundaries)
                  </label>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginBottom: "8px" }}>
                    {editBoundaries.map((b, idx) => (
                      <span
                        key={idx}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "6px",
                          padding: "3px 8px",
                          borderRadius: "4px",
                          background: "rgba(239, 68, 68, 0.15)",
                          border: "1px solid rgba(239, 68, 68, 0.3)",
                          color: "#fca5a5",
                          fontSize: "0.74rem",
                        }}
                      >
                        🛡️ {b}
                        <span
                          onClick={() => setEditBoundaries(editBoundaries.filter((_, i) => i !== idx))}
                          style={{ cursor: "pointer", opacity: 0.6, fontSize: "0.85rem", fontWeight: "bold" }}
                          title="移除此底线"
                        >
                          ×
                        </span>
                      </span>
                    ))}
                    {editBoundaries.length === 0 && (
                      <span style={{ fontSize: "0.74rem", opacity: 0.5 }}>暂无底线禁忌</span>
                    )}
                  </div>
                  <div style={{ display: "flex", gap: "8px" }}>
                    <input
                      type="text"
                      value={editBoundaryInput}
                      onChange={(e) => setEditBoundaryInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && editBoundaryInput.trim()) {
                          e.preventDefault();
                          if (!editBoundaries.includes(editBoundaryInput.trim())) {
                            setEditBoundaries([...editBoundaries, editBoundaryInput.trim()]);
                          }
                          setEditBoundaryInput("");
                        }
                      }}
                      placeholder="输入新底线禁忌后按回车 (如: 讨厌被强硬命令、不接受被轻视)"
                      style={{
                        flex: 1,
                        padding: "6px 10px",
                        borderRadius: "6px",
                        background: "rgba(0,0,0,0.3)",
                        border: "1px solid rgba(255,255,255,0.15)",
                        color: "#fff",
                        fontSize: "0.78rem",
                      }}
                    />
                    <button
                      type="button"
                      onClick={() => {
                        if (editBoundaryInput.trim() && !editBoundaries.includes(editBoundaryInput.trim())) {
                          setEditBoundaries([...editBoundaries, editBoundaryInput.trim()]);
                          setEditBoundaryInput("");
                        }
                      }}
                      style={{
                        padding: "6px 12px",
                        borderRadius: "6px",
                        background: "rgba(255,255,255,0.08)",
                        border: "1px solid rgba(255,255,255,0.15)",
                        color: "#e2e4e8",
                        cursor: "pointer",
                        fontSize: "0.78rem",
                      }}
                    >
                      + 添加底线
                    </button>
                  </div>
                </div>
              </div>

              {/* SECTION 3: 学业与推演事实 (Education & Derived Facts) */}
              <div
                style={{
                  padding: "16px",
                  backgroundColor: "rgba(255, 255, 255, 0.03)",
                  borderRadius: "10px",
                  border: "1px solid rgba(255, 255, 255, 0.08)",
                }}
              >
                <div style={{ fontSize: "0.82rem", fontWeight: 600, marginBottom: "12px", color: "#10b981" }}>
                  🎓 学业推演认知事实 (Derived Educational Facts)
                </div>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: "14px",
                  }}
                >
                  <div>
                    <label style={{ fontSize: "0.78rem", display: "block", marginBottom: "4px" }}>
                      毕业/就读院校 (education.institution)
                    </label>
                    <input
                      type="text"
                      value={editInstitution}
                      onChange={(e) => setEditInstitution(e.target.value)}
                      placeholder="如: USM (马来西亚理科大学)"
                      style={{
                        width: "100%",
                        padding: "8px 12px",
                        borderRadius: "6px",
                        background: "rgba(0,0,0,0.3)",
                        border: "1px solid rgba(255,255,255,0.15)",
                        color: "#fff",
                        fontSize: "0.85rem",
                      }}
                    />
                  </div>

                  <div>
                    <label style={{ fontSize: "0.78rem", display: "block", marginBottom: "4px" }}>
                      专业方向 (education.major)
                    </label>
                    <input
                      type="text"
                      value={editMajor}
                      onChange={(e) => setEditMajor(e.target.value)}
                      placeholder="如: Music Performance (音乐表演)"
                      style={{
                        width: "100%",
                        padding: "8px 12px",
                        borderRadius: "6px",
                        background: "rgba(0,0,0,0.3)",
                        border: "1px solid rgba(255,255,255,0.15)",
                        color: "#fff",
                        fontSize: "0.85rem",
                      }}
                    />
                  </div>
                </div>
              </div>

              {/* ACTION BUTTON */}
              <button
                onClick={handleSaveBiography}
                disabled={saving}
                style={{
                  padding: "12px",
                  borderRadius: "8px",
                  backgroundColor: "#10b981",
                  border: "none",
                  color: "#fff",
                  fontWeight: 600,
                  fontSize: "0.88rem",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "8px",
                }}
              >
                {saving ? "正在保存与同步..." : "💾 固化自传事实与创世蓝图 (Commit to Core & Blueprint)"}
              </button>
            </div>
          )}

          {/* TAB 3: TRACE */}
          {activeTab === "trace" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              <div style={{ fontSize: "0.8rem", opacity: 0.7 }}>
                🔍 实时观察 Aevum 内部的心智与决策痕迹（生理磨损、意图与历史修复）：
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(3, 1fr)",
                  gap: "10px",
                  padding: "12px",
                  backgroundColor: "rgba(0,0,0,0.2)",
                  borderRadius: "8px",
                }}
              >
                <div>
                  <div style={{ fontSize: "0.72rem", opacity: 0.6 }}>当前情绪 (Emotion)</div>
                  <div style={{ fontSize: "0.95rem", fontWeight: 600, color: "#6366f1" }}>
                    {charState?.emotion?.type || "NEUTRAL"} (
                    {((charState?.emotion?.intensity || 0.5) * 100).toFixed(0)}%)
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: "0.72rem", opacity: 0.6 }}>当前精力 (Energy)</div>
                  <div style={{ fontSize: "0.95rem", fontWeight: 600 }}>
                    {((charState?.energy || 1.0) * 100).toFixed(0)}%
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: "0.72rem", opacity: 0.6 }}>当前压力 (Stress)</div>
                  <div style={{ fontSize: "0.95rem", fontWeight: 600 }}>
                    {((charState?.stress || 0.0) * 100).toFixed(0)}%
                  </div>
                </div>
              </div>

              {/* Latest Decision Trace */}
              <div
                style={{
                  padding: "14px",
                  backgroundColor: "rgba(0,0,0,0.3)",
                  borderRadius: "8px",
                  border: "1px solid rgba(255,255,255,0.06)",
                }}
              >
                <div style={{ fontSize: "0.8rem", fontWeight: 600, marginBottom: "8px" }}>
                  🧠 最近行为规划痕迹 (Behavioral Decision Trace)
                </div>
                {debugData?.decision_trace ? (
                  <pre
                    style={{
                      margin: 0,
                      fontSize: "0.75rem",
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-all",
                      maxHeight: "180px",
                      overflowY: "auto",
                      color: "#a5b4fc",
                      backgroundColor: "rgba(0,0,0,0.2)",
                      padding: "8px",
                      borderRadius: "6px",
                    }}
                  >
                    {JSON.stringify(debugData.decision_trace, null, 2)}
                  </pre>
                ) : (
                  <div style={{ fontSize: "0.75rem", opacity: 0.5 }}>暂无最近决策痕迹记录</div>
                )}
              </div>

              {/* Reality Revision History */}
              <div
                style={{
                  padding: "14px",
                  backgroundColor: "rgba(0,0,0,0.3)",
                  borderRadius: "8px",
                  border: "1px solid rgba(255,255,255,0.06)",
                }}
              >
                <div style={{ fontSize: "0.8rem", fontWeight: 600, marginBottom: "8px" }}>
                  🛠️ 现实修复与修订审计 (Reality Revisions / Patches)
                </div>
                {debugData?.reality_history && debugData.reality_history.length > 0 ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                    {debugData.reality_history.slice(-3).map((rev: any, idx: number) => (
                      <div
                        key={idx}
                        style={{
                          fontSize: "0.75rem",
                          padding: "6px 10px",
                          borderRadius: "4px",
                          backgroundColor: "rgba(255,255,255,0.04)",
                        }}
                      >
                        <span style={{ color: "#38bdf8" }}>[{rev.slot_key || "slot"}]</span>:{" "}
                        {rev.previous_value} ➔ {rev.revised_value} ({rev.revision_reason || "minimal repair"})
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ fontSize: "0.75rem", opacity: 0.5 }}>未发生过现实修订或打补丁事件</div>
                )}
              </div>
            </div>
          )}

          {/* TAB 4: PRESENTATION */}
          {activeTab === "presentation" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "18px" }}>
              <div>
                <div style={{ fontSize: "0.9rem", fontWeight: 600, marginBottom: "6px" }}>
                  💬 消息呈现与打字节奏模式
                </div>
                <div style={{ fontSize: "0.78rem", opacity: 0.7, marginBottom: "12px" }}>
                  用户专属设置：根据你的阅读习惯自由选择，无需强迫使用单一显示方式。
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  <label
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: "12px",
                      padding: "12px",
                      borderRadius: "8px",
                      backgroundColor: bubbleMode === "multi" ? "rgba(99, 102, 241, 0.12)" : "rgba(255,255,255,0.03)",
                      border: bubbleMode === "multi" ? "1px solid #6366f1" : "1px solid rgba(255,255,255,0.08)",
                      cursor: "pointer",
                    }}
                  >
                    <input
                      type="radio"
                      name="bubbleMode"
                      value="multi"
                      checked={bubbleMode === "multi"}
                      onChange={() => onBubbleModeChange("multi")}
                      style={{ marginTop: "3px" }}
                    />
                    <div>
                      <div style={{ fontSize: "0.85rem", fontWeight: 600 }}>
                        自然气泡节奏模式 (Multi-Bubble Cadence)
                      </div>
                      <div style={{ fontSize: "0.74rem", opacity: 0.65, marginTop: "2px" }}>
                        像真人微信那样，按句意拆分成连续的短气泡，带有自然的打字间隔呼吸感（如芙芙：“妮妮”、“掉进”、“马桶了”）。
                      </div>
                    </div>
                  </label>

                  <label
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: "12px",
                      padding: "12px",
                      borderRadius: "8px",
                      backgroundColor: bubbleMode === "single" ? "rgba(99, 102, 241, 0.12)" : "rgba(255,255,255,0.03)",
                      border: bubbleMode === "single" ? "1px solid #6366f1" : "1px solid rgba(255,255,255,0.08)",
                      cursor: "pointer",
                    }}
                  >
                    <input
                      type="radio"
                      name="bubbleMode"
                      value="single"
                      checked={bubbleMode === "single"}
                      onChange={() => onBubbleModeChange("single")}
                      style={{ marginTop: "3px" }}
                    />
                    <div>
                      <div style={{ fontSize: "0.85rem", fontWeight: 600 }}>
                        标准整段流式模式 (Single-Block Stream)
                      </div>
                      <div style={{ fontSize: "0.74rem", opacity: 0.65, marginTop: "2px" }}>
                        单一大气泡整段完整输出，不拆分多条，适合喜欢传统整段沉浸式阅读的用户。
                      </div>
                    </div>
                  </label>
                </div>
              </div>

              <div
                style={{
                  padding: "14px",
                  borderRadius: "8px",
                  backgroundColor: "rgba(255,255,255,0.03)",
                  border: "1px solid rgba(255,255,255,0.08)",
                }}
              >
                <div style={{ fontSize: "0.9rem", fontWeight: 600, marginBottom: "6px" }}>
                  🐕 微信常用表情包与颜文字渲染
                </div>
                <div style={{ fontSize: "0.78rem", opacity: 0.7, marginBottom: "10px" }}>
                  将对话中的 [旺柴]、[苦涩]、[破涕为笑] 等标签渲染为高亮表情胶囊，还原真实聊天氛围。
                </div>
                <label style={{ display: "flex", alignItems: "center", gap: "8px", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={emojiRenderingEnabled}
                    onChange={(e) => onEmojiRenderingChange(e.target.checked)}
                  />
                  <span style={{ fontSize: "0.82rem" }}>开启微信经典表情转换 ([旺柴], [苦涩], [流泪] 等)</span>
                </label>
              </div>

              {/* Cultural Context Selector */}
              <div
                style={{
                  padding: "14px",
                  borderRadius: "8px",
                  backgroundColor: "rgba(255,255,255,0.03)",
                  border: "1px solid rgba(255,255,255,0.08)",
                }}
              >
                <div style={{ fontSize: "0.9rem", fontWeight: 600, marginBottom: "6px" }}>
                  🌏 动态文化语境与国家归属 (Cultural Guard)
                </div>
                <div style={{ fontSize: "0.78rem", opacity: 0.7, marginBottom: "10px" }}>
                  自适应拦截跨地域常识穿帮（大马语境严格禁用“户籍”、“高考”、“二本”，自适应采用 IC / SPM / Sembreak / 雪隆槟城）。
                </div>
                <select
                  value={userCountry}
                  onChange={(e) => handleCountryChange(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: "6px",
                    background: "rgba(0,0,0,0.3)",
                    border: "1px solid rgba(255,255,255,0.15)",
                    color: "#e2e4e8",
                    fontSize: "0.82rem",
                  }}
                >
                  <option value="MY" style={{ background: "#181a20" }}>
                    🇲🇾 马来西亚 (Malaysia) · 大马日常 / IC / Sembreak / 雪隆老家与槟城理大
                  </option>
                  <option value="CN" style={{ background: "#181a20" }}>
                    🇨🇳 中国大陆 (China) · 适应大陆日常交流 / 高考升学 / 城市生活用语
                  </option>
                  <option value="SG" style={{ background: "#181a20" }}>
                    🇸🇬 新加坡 (Singapore) · 狮城生活语境 / HDB / MRT / O&A Levels
                  </option>
                  <option value="TW" style={{ background: "#181a20" }}>
                    🇹🇼 台湾 (Taiwan) · 宝岛日常 / 捷运 / 学测夜市
                  </option>
                  <option value="GLOBAL" style={{ background: "#181a20" }}>
                    🌐 全球 / 通用中立 (Global / Neutral) · 国际通用中立语境
                  </option>
                </select>
              </div>

              {(onOpenGenesis || onOpenPresentationSandbox) && (
                <div
                  style={{
                    padding: "14px",
                    borderRadius: "8px",
                    backgroundColor: "rgba(255,255,255,0.03)",
                    border: "1px solid rgba(255,255,255,0.08)",
                    display: "flex",
                    gap: "10px",
                  }}
                >
                  {onOpenGenesis && (
                    <button
                      onClick={() => {
                        onClose();
                        onOpenGenesis();
                      }}
                      style={{
                        flex: 1,
                        padding: "10px",
                        borderRadius: "6px",
                        background: "rgba(56, 189, 248, 0.12)",
                        border: "1px solid rgba(56, 189, 248, 0.3)",
                        color: "#38bdf8",
                        cursor: "pointer",
                        fontSize: "0.82rem",
                        fontWeight: 600,
                      }}
                    >
                      ✦ 启动伴侣创世构建
                    </button>
                  )}
                  {onOpenPresentationSandbox && (
                    <button
                      onClick={() => {
                        onClose();
                        onOpenPresentationSandbox();
                      }}
                      style={{
                        flex: 1,
                        padding: "10px",
                        borderRadius: "6px",
                        background: "rgba(192, 132, 252, 0.12)",
                        border: "1px solid rgba(192, 132, 252, 0.3)",
                        color: "#c084fc",
                        cursor: "pointer",
                        fontSize: "0.82rem",
                        fontWeight: 600,
                      }}
                    >
                      🎨 打开表达渲染沙盒 (Cases A~G)
                    </button>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
