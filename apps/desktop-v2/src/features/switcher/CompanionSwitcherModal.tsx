import React, { useEffect, useState } from "react";
import { api } from "../../api";
import type { CompanionOverviewItem } from "../../types";

interface CompanionSwitcherModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCompanionSwitched: (characterId: string) => void;
}

const PRESET_NEW_PERSONAS = [
  {
    name: "叶微凉",
    occupation: "临床医学系大三学生 / 医院见习",
    traits: ["清冷", "自律", "外冷内热", "观察敏锐"],
    background: "平日里在医院各个科室轮转见习，话不多但默默关心人。夜晚喜欢喝热红茶听雨声。",
    speaking_style: "言简意赅、温和理性中带着隐秘的关切",
  },
  {
    name: "林晨",
    occupation: "自由摄影师 / 独立旅行博主",
    traits: ["阳光", "直率", "好奇心强", "浪漫"],
    background: "常年在各地采风拍摄风景与人文，背着大单反包。喜欢分享抓拍到的光影瞬间与旅途奇遇。",
    speaking_style: "开朗明快、幽默随和、富有感染力",
  },
  {
    name: "夏语竹",
    occupation: "图书档案管理员 / 古籍修复师",
    traits: ["文静", "恬淡", "沉静安宁", "善解人意"],
    background: "在清幽的古籍藏书室工作，指尖带着淡淡墨香。对古典文学与民间传说有深厚的研究。",
    speaking_style: "温软轻柔、从容优雅、娓娓道来",
  },
];

export const CompanionSwitcherModal: React.FC<CompanionSwitcherModalProps> = ({
  isOpen,
  onClose,
  onCompanionSwitched,
}) => {
  const [companions, setCompanions] = useState<CompanionOverviewItem[]>([]);
  const [activeId, setActiveId] = useState<string>("aevum");
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  // New companion form state
  const [isCreating, setIsCreating] = useState<boolean>(false);
  const [newName, setNewName] = useState<string>("");
  const [newOccupation, setNewOccupation] = useState<string>("");
  const [newTraits, setNewTraits] = useState<string>("真诚, 温和, 好奇");
  const [newBackground, setNewBackground] = useState<string>("");
  const [newSpeakingStyle, setNewSpeakingStyle] = useState<string>("温和自然、真诚随和");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const fetchCompanions = async () => {
    try {
      setLoading(true);
      setErrorMsg(null);
      const res = await api.getAllCompanions();
      setCompanions(res.companions || []);
      setActiveId(res.active_character_id || "aevum");
    } catch (err: any) {
      setErrorMsg(err.message || "获取伴侣人设列表失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchCompanions();
      setIsCreating(false);
      setStatusMsg(null);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSwitch = async (charId: string) => {
    if (charId === activeId) return;
    try {
      setLoading(true);
      setErrorMsg(null);
      const res = await api.switchCompanion(charId);
      setActiveId(res.active_character_id || charId);
      setCompanions(res.companions || []);
      setStatusMsg(`已成功切换伴侣！`);
      onCompanionSwitched(charId);
      setTimeout(() => {
        onClose();
      }, 600);
    } catch (err: any) {
      setErrorMsg(err.message || "切换人设失败");
    } finally {
      setLoading(false);
    }
  };

  const handleApplyPreset = (preset: (typeof PRESET_NEW_PERSONAS)[0]) => {
    setNewName(preset.name);
    setNewOccupation(preset.occupation);
    setNewTraits(preset.traits.join(", "));
    setNewBackground(preset.background);
    setNewSpeakingStyle(preset.speaking_style);
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) {
      setErrorMsg("请填写伴侣名字");
      return;
    }
    try {
      setIsSubmitting(true);
      setErrorMsg(null);
      const traitsArray = newTraits
        .split(/[,，、]/)
        .map((t) => t.trim())
        .filter(Boolean);

      const res = await api.createNewCompanion({
        name: newName.trim(),
        role: newOccupation.trim() || "新朋友 / 探索者",
        description: newBackground.trim() || `初次见面的伙伴，性格特点：${traitsArray.join("、")}`,
        speaking_style: [newSpeakingStyle.trim() || "温和自然、真诚随和"],
      });

      const newCharId = res.character_id || res.id;
      setStatusMsg(`成功创建新人设「${newName}」！`);
      await fetchCompanions();
      setIsCreating(false);
      onCompanionSwitched(newCharId);
      setTimeout(() => {
        onClose();
      }, 700);
    } catch (err: any) {
      setErrorMsg(err.message || "创建新人设失败");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      className="modal-overlay"
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: "rgba(0, 0, 0, 0.78)",
        backdropFilter: "blur(8px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 2050,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="modal-container"
        style={{
          width: "640px",
          maxWidth: "94vw",
          maxHeight: "88vh",
          overflowY: "auto",
          background: "#161622",
          border: "1px solid rgba(255, 255, 255, 0.12)",
          borderRadius: "18px",
          padding: "24px",
          boxShadow: "0 24px 60px rgba(0, 0, 0, 0.75)",
          color: "#e2e8f0",
        }}
      >
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px" }}>
          <div>
            <h2 style={{ margin: 0, fontSize: "19px", fontWeight: 700, display: "flex", alignItems: "center", gap: "8px" }}>
              <span>👥</span>
              <span>伴侣人设选择与切换</span>
            </h2>
            <p style={{ margin: "6px 0 0 0", fontSize: "12.5px", color: "rgba(255, 255, 255, 0.55)", lineHeight: 1.5 }}>
              自由切换不同的陪伴者。苏棠与新人设之间<strong>记忆独立、关系好感独立、对话记录互不干扰</strong>，随时可无缝切回。
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: "transparent",
              border: "none",
              color: "rgba(255,255,255,0.6)",
              fontSize: "20px",
              cursor: "pointer",
              padding: "4px 8px",
            }}
          >
            ✕
          </button>
        </div>

        {/* Feedback Alerts */}
        {errorMsg && (
          <div
            style={{
              padding: "10px 14px",
              marginBottom: "14px",
              borderRadius: "8px",
              background: "rgba(239, 68, 68, 0.15)",
              border: "1px solid rgba(239, 68, 68, 0.35)",
              color: "#fca5a5",
              fontSize: "12.5px",
            }}
          >
            ⚠️ {errorMsg}
          </div>
        )}

        {statusMsg && (
          <div
            style={{
              padding: "10px 14px",
              marginBottom: "14px",
              borderRadius: "8px",
              background: "rgba(34, 197, 94, 0.15)",
              border: "1px solid rgba(34, 197, 94, 0.35)",
              color: "#86efac",
              fontSize: "12.5px",
            }}
          >
            ✨ {statusMsg}
          </div>
        )}

        {/* Action Toggle (List vs Create) */}
        <div style={{ display: "flex", gap: "10px", marginBottom: "18px" }}>
          <button
            type="button"
            onClick={() => setIsCreating(false)}
            style={{
              flex: 1,
              padding: "8px 14px",
              borderRadius: "8px",
              border: !isCreating ? "1px solid rgba(99, 102, 241, 0.5)" : "1px solid rgba(255, 255, 255, 0.1)",
              background: !isCreating ? "rgba(99, 102, 241, 0.2)" : "rgba(255, 255, 255, 0.04)",
              color: !isCreating ? "#c7d2fe" : "rgba(255, 255, 255, 0.7)",
              fontSize: "13px",
              fontWeight: 600,
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
          >
            现有伴侣人设 ({companions.length})
          </button>
          <button
            type="button"
            onClick={() => setIsCreating(true)}
            style={{
              flex: 1,
              padding: "8px 14px",
              borderRadius: "8px",
              border: isCreating ? "1px solid rgba(168, 85, 247, 0.5)" : "1px solid rgba(255, 255, 255, 0.1)",
              background: isCreating ? "rgba(168, 85, 247, 0.2)" : "rgba(255, 255, 255, 0.04)",
              color: isCreating ? "#d8b4fe" : "rgba(255, 255, 255, 0.7)",
              fontSize: "13px",
              fontWeight: 600,
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
          >
            ➕ 创建全新独立新人设
          </button>
        </div>

        {/* Mode 1: Companion List */}
        {!isCreating && (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {loading && companions.length === 0 ? (
              <div style={{ textAlign: "center", padding: "30px", color: "rgba(255, 255, 255, 0.5)" }}>
                正在加载伴侣列表...
              </div>
            ) : companions.length === 0 ? (
              <div style={{ textAlign: "center", padding: "30px", color: "rgba(255, 255, 255, 0.5)" }}>
                暂无伴侣人设
              </div>
            ) : (
              companions.map((comp) => {
                const isCurActive = comp.id === activeId;
                const affectionPct = Math.round((comp.affection || 0) * 100);
                const trustPct = Math.round((comp.trust || 0.2) * 100);

                return (
                  <div
                    key={comp.id}
                    style={{
                      background: isCurActive ? "rgba(99, 102, 241, 0.12)" : "rgba(255, 255, 255, 0.03)",
                      border: isCurActive
                        ? "1.5px solid rgba(99, 102, 241, 0.55)"
                        : "1px solid rgba(255, 255, 255, 0.08)",
                      borderRadius: "14px",
                      padding: "16px",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: "16px",
                      transition: "all 0.2s ease",
                    }}
                  >
                    {/* Left: Avatar & Info */}
                    <div style={{ display: "flex", alignItems: "center", gap: "14px", flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          width: "48px",
                          height: "48px",
                          borderRadius: "50%",
                          background: isCurActive
                            ? "linear-gradient(135deg, #6366f1, #a855f7)"
                            : "rgba(255, 255, 255, 0.1)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontSize: "20px",
                          fontWeight: 700,
                          color: "#ffffff",
                          flexShrink: 0,
                          boxShadow: isCurActive ? "0 4px 14px rgba(99, 102, 241, 0.4)" : "none",
                        }}
                      >
                        {comp.avatar_url || (comp.name ? comp.name[0] : "伴")}
                      </div>

                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap", marginBottom: "4px" }}>
                          <span style={{ fontSize: "16px", fontWeight: 700, color: "#ffffff" }}>
                            {comp.name}
                          </span>
                          <span
                            style={{
                              fontSize: "11px",
                              padding: "2px 8px",
                              borderRadius: "10px",
                              background: "rgba(255, 255, 255, 0.08)",
                              color: "rgba(255, 255, 255, 0.75)",
                            }}
                          >
                            {comp.role}
                          </span>
                          {isCurActive && (
                            <span
                              style={{
                                fontSize: "11px",
                                fontWeight: 600,
                                padding: "2px 8px",
                                borderRadius: "10px",
                                background: "rgba(34, 197, 94, 0.2)",
                                color: "#4ade80",
                                border: "1px solid rgba(34, 197, 94, 0.4)",
                              }}
                            >
                              ● 当前陪伴中
                            </span>
                          )}
                        </div>

                        {comp.description && (
                          <div
                            style={{
                              fontSize: "12px",
                              color: "rgba(255, 255, 255, 0.6)",
                              whiteSpace: "nowrap",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              marginBottom: "8px",
                            }}
                            title={comp.description}
                          >
                            {comp.description}
                          </div>
                        )}

                        {/* Metrics Badges */}
                        <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", fontSize: "11.5px" }}>
                          <span style={{ color: "#93c5fd", display: "inline-flex", alignItems: "center", gap: "3px" }}>
                            🧠 <strong>{comp.memory_count}</strong> 条共同记忆
                          </span>
                          <span style={{ color: "#c084fc", display: "inline-flex", alignItems: "center", gap: "3px" }}>
                            💬 <strong>{comp.message_count}</strong> 条历史记录
                          </span>
                          <span style={{ color: "#f472b6", display: "inline-flex", alignItems: "center", gap: "3px" }}>
                            ❤️ 好感度 <strong>{affectionPct}%</strong>
                          </span>
                          <span style={{ color: "#34d399", display: "inline-flex", alignItems: "center", gap: "3px" }}>
                            🤝 信任度 <strong>{trustPct}%</strong>
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Right: Switch Action Button */}
                    <div>
                      {isCurActive ? (
                        <button
                          type="button"
                          disabled
                          style={{
                            padding: "8px 16px",
                            borderRadius: "8px",
                            background: "rgba(255, 255, 255, 0.05)",
                            border: "1px solid rgba(255, 255, 255, 0.15)",
                            color: "rgba(255, 255, 255, 0.4)",
                            fontSize: "12.5px",
                            fontWeight: 600,
                            cursor: "default",
                          }}
                        >
                          使用中
                        </button>
                      ) : (
                        <button
                          type="button"
                          disabled={loading}
                          onClick={() => handleSwitch(comp.id)}
                          style={{
                            padding: "8px 16px",
                            borderRadius: "8px",
                            background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
                            border: "none",
                            color: "#ffffff",
                            fontSize: "12.5px",
                            fontWeight: 600,
                            cursor: "pointer",
                            boxShadow: "0 4px 12px rgba(99, 102, 241, 0.3)",
                            transition: "all 0.15s ease",
                          }}
                        >
                          切换为此人设
                        </button>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        )}

        {/* Mode 2: Create Brand New Independent Companion */}
        {isCreating && (
          <form onSubmit={handleCreateSubmit} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            {/* Presets Bar */}
            <div style={{ background: "rgba(255, 255, 255, 0.02)", padding: "12px", borderRadius: "10px", border: "1px solid rgba(255, 255, 255, 0.06)" }}>
              <div style={{ fontSize: "12px", color: "rgba(255, 255, 255, 0.55)", marginBottom: "8px" }}>
                💡 快速灵感预设（点击一键填入）：
              </div>
              <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                {PRESET_NEW_PERSONAS.map((p) => (
                  <button
                    key={p.name}
                    type="button"
                    onClick={() => handleApplyPreset(p)}
                    style={{
                      background: "rgba(255, 255, 255, 0.06)",
                      border: "1px solid rgba(255, 255, 255, 0.12)",
                      borderRadius: "6px",
                      padding: "5px 10px",
                      fontSize: "12px",
                      color: "#c7d2fe",
                      cursor: "pointer",
                    }}
                  >
                    ✨ {p.name} · {p.occupation.split("/")[0]}
                  </button>
                ))}
              </div>
            </div>

            {/* Field: Name */}
            <div>
              <label style={{ display: "block", fontSize: "12.5px", fontWeight: 600, color: "rgba(255, 255, 255, 0.8)", marginBottom: "5px" }}>
                伴侣姓名 / 昵称 *
              </label>
              <input
                type="text"
                required
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="例如：叶微凉、林晨、小夏..."
                style={{
                  width: "100%",
                  boxSizing: "border-box",
                  background: "rgba(255, 255, 255, 0.06)",
                  border: "1px solid rgba(255, 255, 255, 0.15)",
                  borderRadius: "8px",
                  padding: "9px 12px",
                  color: "#ffffff",
                  fontSize: "13.5px",
                }}
              />
            </div>

            {/* Field: Occupation */}
            <div>
              <label style={{ display: "block", fontSize: "12.5px", fontWeight: 600, color: "rgba(255, 255, 255, 0.8)", marginBottom: "5px" }}>
                身份 / 职业标签
              </label>
              <input
                type="text"
                value={newOccupation}
                onChange={(e) => setNewOccupation(e.target.value)}
                placeholder="例如：临床医学系大三学生、自由摄影师、插画师..."
                style={{
                  width: "100%",
                  boxSizing: "border-box",
                  background: "rgba(255, 255, 255, 0.06)",
                  border: "1px solid rgba(255, 255, 255, 0.15)",
                  borderRadius: "8px",
                  padding: "9px 12px",
                  color: "#ffffff",
                  fontSize: "13.5px",
                }}
              />
            </div>

            {/* Field: Personality Traits */}
            <div>
              <label style={{ display: "block", fontSize: "12.5px", fontWeight: 600, color: "rgba(255, 255, 255, 0.8)", marginBottom: "5px" }}>
                核心性格标签 (逗号隔开)
              </label>
              <input
                type="text"
                value={newTraits}
                onChange={(e) => setNewTraits(e.target.value)}
                placeholder="例如：温柔, 清冷, 幽默, 执着..."
                style={{
                  width: "100%",
                  boxSizing: "border-box",
                  background: "rgba(255, 255, 255, 0.06)",
                  border: "1px solid rgba(255, 255, 255, 0.15)",
                  borderRadius: "8px",
                  padding: "9px 12px",
                  color: "#ffffff",
                  fontSize: "13.5px",
                }}
              />
            </div>

            {/* Field: Background */}
            <div>
              <label style={{ display: "block", fontSize: "12.5px", fontWeight: 600, color: "rgba(255, 255, 255, 0.8)", marginBottom: "5px" }}>
                人物生活背景与日常写照
              </label>
              <textarea
                rows={3}
                value={newBackground}
                onChange={(e) => setNewBackground(e.target.value)}
                placeholder="简短描述Ta的日常生活、习惯、爱好，或者与你初识的情景..."
                style={{
                  width: "100%",
                  boxSizing: "border-box",
                  background: "rgba(255, 255, 255, 0.06)",
                  border: "1px solid rgba(255, 255, 255, 0.15)",
                  borderRadius: "8px",
                  padding: "9px 12px",
                  color: "#ffffff",
                  fontSize: "13px",
                  lineHeight: 1.5,
                  resize: "vertical",
                }}
              />
            </div>

            {/* Field: Speaking Style */}
            <div>
              <label style={{ display: "block", fontSize: "12.5px", fontWeight: 600, color: "rgba(255, 255, 255, 0.8)", marginBottom: "5px" }}>
                说话语调风格
              </label>
              <input
                type="text"
                value={newSpeakingStyle}
                onChange={(e) => setNewSpeakingStyle(e.target.value)}
                placeholder="例如：轻柔慢条斯理、开朗元气爱开玩笑、清冷克制..."
                style={{
                  width: "100%",
                  boxSizing: "border-box",
                  background: "rgba(255, 255, 255, 0.06)",
                  border: "1px solid rgba(255, 255, 255, 0.15)",
                  borderRadius: "8px",
                  padding: "9px 12px",
                  color: "#ffffff",
                  fontSize: "13px",
                }}
              />
            </div>

            {/* Submit Button */}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "10px" }}>
              <button
                type="button"
                onClick={() => setIsCreating(false)}
                style={{
                  padding: "9px 18px",
                  borderRadius: "8px",
                  background: "rgba(255, 255, 255, 0.08)",
                  border: "1px solid rgba(255, 255, 255, 0.15)",
                  color: "rgba(255, 255, 255, 0.8)",
                  fontSize: "13px",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                取消
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                style={{
                  padding: "9px 22px",
                  borderRadius: "8px",
                  background: "linear-gradient(135deg, #a855f7, #6366f1)",
                  border: "none",
                  color: "#ffffff",
                  fontSize: "13px",
                  fontWeight: 600,
                  cursor: isSubmitting ? "not-allowed" : "pointer",
                  boxShadow: "0 4px 14px rgba(168, 85, 247, 0.35)",
                }}
              >
                {isSubmitting ? "正在生成独立新人物..." : "✨ 生成并立即开始对话"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
