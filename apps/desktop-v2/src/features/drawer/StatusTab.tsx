import React, { useEffect, useState } from "react";
import { useCharacterStore } from "../../stores/useCharacterStore";
import { DatingSituationModal } from "../stage/DatingSituationModal";
import styles from "./StatusTab.module.css";

export const StatusTab: React.FC = () => {
  const [isDatingModalOpen, setIsDatingModalOpen] = useState<boolean>(false);
  const characterState = useCharacterStore((s) => s.characterState);
  const life = useCharacterStore((s) => s.life);
  const debugData = useCharacterStore((s) => s.debugData);
  const fetchCharacterState = useCharacterStore((s) => s.fetchCharacterState);
  const fetchLife = useCharacterStore((s) => s.fetchLife);
  const fetchDebug = useCharacterStore((s) => s.fetchDebug);

  useEffect(() => {
    fetchCharacterState();
    fetchLife();
    fetchDebug();
  }, [fetchCharacterState, fetchLife, fetchDebug]);

  if (!characterState) {
    return <div className={styles.container}>正在读取伴侣状态...</div>;
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h3 className={styles.title}>伴侣实时状态与作息</h3>
        <button
          onClick={() => setIsDatingModalOpen(true)}
          style={{
            background: "linear-gradient(135deg, rgba(147, 112, 219, 0.25), rgba(186, 104, 200, 0.25))",
            border: "1px solid rgba(147, 112, 219, 0.4)",
            borderRadius: "8px",
            color: "#e0d0f5",
            fontSize: "12px",
            fontWeight: 500,
            padding: "5px 10px",
            cursor: "pointer",
          }}
        >
          📍 约会地点签到
        </button>
      </div>

      <div className={styles.card}>
        <span className={styles.cardTitle}>身份与当下拉境</span>
        <div className={styles.row}>
          <span className={styles.label}>姓名</span>
          <span className={styles.value}>{characterState.name}</span>
        </div>
        <div className={styles.row}>
          <span className={styles.label}>年龄 / 职业</span>
          <span className={styles.value}>
            {characterState.age} 岁 · {characterState.occupation}
          </span>
        </div>
        <div className={styles.row}>
          <span className={styles.label}>当前心情</span>
          <span className={styles.moodTag}>{characterState.natural_mood || characterState.mood}</span>
        </div>
        <div className={styles.row}>
          <span className={styles.label}>所在地点</span>
          <span className={styles.value}>{characterState.current_location || "家中"}</span>
        </div>
        <div className={styles.row}>
          <span className={styles.label}>正在进行</span>
          <span className={styles.value}>
            {characterState.current_activity || "日常活动中"}
          </span>
        </div>
        <div className={styles.row}>
          <span className={styles.label}>精力状态</span>
          <span className={styles.value}>
            {Math.round((characterState.energy ?? 0.8) * 100)}%
          </span>
        </div>
        {debugData && (
          <div className={styles.row}>
            <span className={styles.label}>沉淀总记忆数</span>
            <span className={styles.value}>{debugData.total_memories} 条</span>
          </div>
        )}
      </div>

      {life?.recent_events && life.recent_events.length > 0 && (
        <div className={styles.card}>
          <span className={styles.cardTitle}>近期生活经历</span>
          {life.recent_events.slice(0, 5).map((ev) => (
            <div key={ev.id} className={styles.eventItem}>
              <span className={styles.eventTitle}>{ev.title}</span>
              <span className={styles.eventDesc}>{ev.description}</span>
            </div>
          ))}
        </div>
      )}

      {life?.active_goals && life.active_goals.length > 0 && (
        <div className={styles.card}>
          <span className={styles.cardTitle}>当前生活目标</span>
          {life.active_goals.map((goal) => (
            <div key={goal.id} className={styles.goalItem}>
              <span>{goal.title}</span>
              <span className={styles.goalStatus}>{goal.status}</span>
            </div>
          ))}
        </div>
      )}

      <DatingSituationModal
        isOpen={isDatingModalOpen}
        onClose={() => setIsDatingModalOpen(false)}
      />
    </div>
  );
};
