import React, { useEffect, useState } from "react";
import { api } from "../../api";
import type { CompanionOverviewItem } from "../../types";
import styles from "./CompanionSwitcherModal.module.css";

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
      className={styles.overlay}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className={styles.container}>
        {/* Header */}
        <div className={styles.header}>
          <div>
            <h2 className={styles.headerTitle}>
              <span>👥</span>
              <span>伴侣人设选择与切换</span>
            </h2>
            <p className={styles.headerSubtitle}>
              自由切换不同的陪伴者。苏棠与新人设之间<strong>记忆独立、关系好感独立、对话记录互不干扰</strong>，随时可无缝切回。
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className={styles.closeBtn}
            aria-label="关闭"
          >
            ✕
          </button>
        </div>

        {/* Feedback Alerts */}
        {errorMsg && (
          <div className={styles.alertError}>
            ⚠️ {errorMsg}
          </div>
        )}

        {statusMsg && (
          <div className={styles.alertSuccess}>
            ✨ {statusMsg}
          </div>
        )}

        {/* Action Toggle (List vs Create) */}
        <div className={styles.modeToggle}>
          <button
            type="button"
            onClick={() => setIsCreating(false)}
            className={`${styles.modeBtn} ${!isCreating ? styles.modeBtnActiveList : ""}`}
          >
            现有伴侣人设 ({companions.length})
          </button>
          <button
            type="button"
            onClick={() => setIsCreating(true)}
            className={`${styles.modeBtn} ${isCreating ? styles.modeBtnActiveCreate : ""}`}
          >
            ➕ 创建全新独立新人设
          </button>
        </div>

        {/* Mode 1: Companion List */}
        {!isCreating && (
          <div className={styles.companionList}>
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
                    className={`${styles.companionCard} ${isCurActive ? styles.companionCardActive : ""}`}
                  >
                    {/* Main Avatar & Meta Info */}
                    <div className={styles.cardMainInfo}>
                      <div
                        className={`${styles.avatarCircle} ${
                          isCurActive ? styles.avatarCircleActive : ""
                        }`}
                      >
                        {comp.avatar_url || (comp.name ? comp.name[0] : "伴")}
                      </div>

                      <div className={styles.cardMetaContent}>
                        <div className={styles.nameRow}>
                          <span className={styles.nameText}>
                            {comp.name}
                          </span>
                          <span className={styles.roleBadge}>
                            {comp.role}
                          </span>
                          {isCurActive && (
                            <span className={styles.activeStatusBadge}>
                              ● 当前陪伴中
                            </span>
                          )}
                        </div>

                        {comp.description && (
                          <div className={styles.cardDesc} title={comp.description}>
                            {comp.description}
                          </div>
                        )}

                        {/* Metrics Badges */}
                        <div className={styles.metricsRow}>
                          <span className={styles.metricPill} style={{ color: "#93c5fd" }}>
                            🧠 <strong>{comp.memory_count}</strong> 条共同记忆
                          </span>
                          <span className={styles.metricPill} style={{ color: "#c084fc" }}>
                            💬 <strong>{comp.message_count}</strong> 条历史记录
                          </span>
                          <span className={styles.metricPill} style={{ color: "#f472b6" }}>
                            ❤️ 好感度 <strong>{affectionPct}%</strong>
                          </span>
                          <span className={styles.metricPill} style={{ color: "#34d399" }}>
                            🤝 信任度 <strong>{trustPct}%</strong>
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Switch Action Button (prominent touch target on mobile) */}
                    <div className={styles.cardActionWrap}>
                      {isCurActive ? (
                        <button
                          type="button"
                          disabled
                          className={styles.activeDisabledBtn}
                        >
                          使用中
                        </button>
                      ) : (
                        <button
                          type="button"
                          disabled={loading}
                          onClick={() => handleSwitch(comp.id)}
                          className={styles.switchActionBtn}
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
          <form onSubmit={handleCreateSubmit} className={styles.createForm}>
            {/* Presets Bar */}
            <div className={styles.presetsBox}>
              <div className={styles.presetsTitle}>
                💡 快速灵感预设（点击一键填入）：
              </div>
              <div className={styles.presetsWrap}>
                {PRESET_NEW_PERSONAS.map((p) => (
                  <button
                    key={p.name}
                    type="button"
                    onClick={() => handleApplyPreset(p)}
                    className={styles.presetBtn}
                  >
                    ✨ {p.name} · {p.occupation.split("/")[0]}
                  </button>
                ))}
              </div>
            </div>

            {/* Field: Name */}
            <div className={styles.fieldGroup}>
              <label className={styles.fieldLabel}>
                伴侣姓名 / 昵称 *
              </label>
              <input
                type="text"
                required
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="例如：叶微凉、林晨、小夏..."
                className={styles.fieldInput}
              />
            </div>

            {/* Field: Occupation */}
            <div className={styles.fieldGroup}>
              <label className={styles.fieldLabel}>
                身份 / 职业标签
              </label>
              <input
                type="text"
                value={newOccupation}
                onChange={(e) => setNewOccupation(e.target.value)}
                placeholder="例如：临床医学系大三学生、自由摄影师、插画师..."
                className={styles.fieldInput}
              />
            </div>

            {/* Field: Personality Traits */}
            <div className={styles.fieldGroup}>
              <label className={styles.fieldLabel}>
                核心性格标签 (逗号隔开)
              </label>
              <input
                type="text"
                value={newTraits}
                onChange={(e) => setNewTraits(e.target.value)}
                placeholder="例如：温柔, 清冷, 幽默, 执着..."
                className={styles.fieldInput}
              />
            </div>

            {/* Field: Background */}
            <div className={styles.fieldGroup}>
              <label className={styles.fieldLabel}>
                人物生活背景与日常写照
              </label>
              <textarea
                rows={3}
                value={newBackground}
                onChange={(e) => setNewBackground(e.target.value)}
                placeholder="简短描述Ta的日常生活、习惯、爱好，或者与你初识的情景..."
                className={styles.fieldTextarea}
              />
            </div>

            {/* Field: Speaking Style */}
            <div className={styles.fieldGroup}>
              <label className={styles.fieldLabel}>
                说话语调风格
              </label>
              <input
                type="text"
                value={newSpeakingStyle}
                onChange={(e) => setNewSpeakingStyle(e.target.value)}
                placeholder="例如：轻柔慢条斯理、开朗元气爱开玩笑、清冷克制..."
                className={styles.fieldInput}
              />
            </div>

            {/* Submit Button */}
            <div className={styles.formFooter}>
              <button
                type="button"
                onClick={() => setIsCreating(false)}
                className={styles.cancelBtn}
              >
                取消
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                className={styles.submitBtn}
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
