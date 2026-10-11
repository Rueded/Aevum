import React, { useState } from "react";
import { api } from "../../api";
import { useCharacterStore } from "../../stores/useCharacterStore";
import styles from "./DatingSituationModal.module.css";

interface DatingSituationModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface SituationPreset {
  id: string;
  name: string;
  activity: string;
  location: string;
  durationHours: number;
  status: string;
  emoji: string;
  desc: string;
}

const PRESETS: SituationPreset[] = [
  {
    id: "rabbit_hole",
    name: "The Rabbit Hole 咖啡馆",
    activity: "约会品尝咖啡与甜点聊天",
    location: "Changkat Bukit Bintang - The Rabbit Hole",
    durationHours: 2.0,
    status: "约会咖啡聊天中",
    emoji: "☕",
    desc: "在舒适静谧的绿植咖啡馆喝咖啡，享受午后慢时光",
  },
  {
    id: "cinema",
    name: "大地影院看电影",
    activity: "看电影约会 (吉伊卡哇 / 动画电影)",
    location: "Pavilion Kuala Lumpur 大地影院",
    durationHours: 2.5,
    status: "电影院约会观影中",
    emoji: "🎬",
    desc: "依偎在一起看期待已久的电影，爆米花与可乐香气萦绕",
  },
  {
    id: "horizon_grill",
    name: "Horizon Grill 高空夜景餐厅",
    activity: "吉隆坡KLCC双子塔夜景浪漫晚餐",
    location: "Banyan Tree 58F - Horizon Grill",
    durationHours: 2.5,
    status: "夜景高空晚餐约会中",
    emoji: "🍷",
    desc: "俯瞰吉隆坡璀璨夜景，享受精致牛排与烛光微醺",
  },
  {
    id: "park_walk",
    name: "KLCC 公园漫步",
    activity: "饭后公园散步吹风",
    location: "KLCC Park 城市公园",
    durationHours: 1.5,
    status: "公园牵手散步中",
    emoji: "🌸",
    desc: "伴随微风与喷泉夜色，肩并肩散步闲聊",
  },
  {
    id: "home_cat",
    name: "老家撸猫日常",
    activity: "在家陪小橘玩耍与看书",
    location: "雪隆老家家中",
    durationHours: 3.0,
    status: "居家日常放松中",
    emoji: "🐱",
    desc: "舒适地靠在沙发上，小橘蜷在脚边打呼噜",
  },
];

export const DatingSituationModal: React.FC<DatingSituationModalProps> = ({
  isOpen,
  onClose,
}) => {
  const fetchCharacterState = useCharacterStore((s) => s.fetchCharacterState);
  const fetchLife = useCharacterStore((s) => s.fetchLife);
  const [selectedPreset, setSelectedPreset] = useState<string>("rabbit_hole");
  const [isCustom, setIsCustom] = useState<boolean>(false);
  const [customLocation, setCustomLocation] = useState<string>("");
  const [customActivity, setCustomActivity] = useState<string>("");
  const [customDuration, setCustomDuration] = useState<number>(2);
  const [customStatus, setCustomStatus] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleApply = async () => {
    setIsSubmitting(true);
    setSuccessMsg(null);
    setErrorMsg(null);
    try {
      if (isCustom) {
        if (!customLocation.trim() || !customActivity.trim()) {
          setErrorMsg("请填写约会地点和正在进行的活动！");
          setIsSubmitting(false);
          return;
        }
        await api.setSituation({
          location: customLocation.trim(),
          activity: customActivity.trim(),
          duration_hours: customDuration,
          status: customStatus.trim() || customActivity.trim(),
        });
      } else {
        const preset = PRESETS.find((p) => p.id === selectedPreset);
        if (preset) {
          await api.setSituation({
            location: preset.location,
            activity: preset.activity,
            duration_hours: preset.durationHours,
            status: preset.status,
          });
        }
      }

      await fetchCharacterState();
      await fetchLife();
      setSuccessMsg("约会现场签到成功！状态已切换。");
      setTimeout(() => {
        setSuccessMsg(null);
        onClose();
      }, 900);
    } catch (err: any) {
      console.error("Failed to update situation", err);
      setErrorMsg(err.message || "更新签到失败，请稍后重试");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <div className={styles.titleGroup}>
            <span className={styles.icon}>📍</span>
            <h3>动态约会地点与生活现场</h3>
          </div>
          <button className={styles.closeBtn} onClick={onClose}>
            ✕
          </button>
        </div>

        <p className={styles.subtitle}>
          切换当下约会场景与地点，伴侣的状态、对话反应和环境心境将随真实场景动态流转。
        </p>

        {successMsg && <div className={styles.successBadge}>✓ {successMsg}</div>}
        {errorMsg && <div className={styles.errorBadge || styles.successBadge} style={{ color: "#ff4d4f", borderColor: "#ff4d4f", background: "rgba(255, 77, 79, 0.1)" }}>⚠️ {errorMsg}</div>}

        <div className={styles.tabs}>
          <button
            className={`${styles.tabBtn} ${!isCustom ? styles.tabActive : ""}`}
            onClick={() => setIsCustom(false)}
          >
            浪漫约会预设
          </button>
          <button
            className={`${styles.tabBtn} ${isCustom ? styles.tabActive : ""}`}
            onClick={() => setIsCustom(true)}
          >
            自定义约会行程
          </button>
        </div>

        {!isCustom ? (
          <div className={styles.presetsGrid}>
            {PRESETS.map((p) => {
              const isSelected = selectedPreset === p.id;
              return (
                <div
                  key={p.id}
                  className={`${styles.presetCard} ${isSelected ? styles.presetCardSelected : ""}`}
                  onClick={() => setSelectedPreset(p.id)}
                >
                  <div className={styles.presetTop}>
                    <span className={styles.presetEmoji}>{p.emoji}</span>
                    <span className={styles.presetName}>{p.name}</span>
                    <span className={styles.durationTag}>{p.durationHours}h</span>
                  </div>
                  <div className={styles.presetLoc}>📍 {p.location}</div>
                  <div className={styles.presetDesc}>{p.desc}</div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className={styles.customForm}>
            <div className={styles.formGroup}>
              <label>约会 / 现场地点</label>
              <input
                type="text"
                placeholder="例如：Changkat The Rabbit Hole, Pavilion 电影院"
                value={customLocation}
                onChange={(e) => setCustomLocation(e.target.value)}
              />
            </div>
            <div className={styles.formGroup}>
              <label>正在进行的活动</label>
              <input
                type="text"
                placeholder="例如：一起喝拿铁吃提拉米苏聊天"
                value={customActivity}
                onChange={(e) => setCustomActivity(e.target.value)}
              />
            </div>
            <div className={styles.formGroup}>
              <label>实时状态标识 (用于顶部状态栏)</label>
              <input
                type="text"
                placeholder="例如：约会咖啡慢聊中"
                value={customStatus}
                onChange={(e) => setCustomStatus(e.target.value)}
              />
            </div>
            <div className={styles.formGroup}>
              <label>持续时间 (小时)</label>
              <input
                type="number"
                min="0.5"
                max="12"
                step="0.5"
                value={customDuration}
                onChange={(e) => setCustomDuration(parseFloat(e.target.value) || 2)}
              />
            </div>
          </div>
        )}

        <div className={styles.footer}>
          <button className={styles.cancelBtn} onClick={onClose} disabled={isSubmitting}>
            取消
          </button>
          <button className={styles.submitBtn} onClick={handleApply} disabled={isSubmitting}>
            {isSubmitting ? "正在前往现场..." : "确认签到并切换现场"}
          </button>
        </div>
      </div>
    </div>
  );
};
