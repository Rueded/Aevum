import React, { useEffect } from "react";
import { DimensionBar } from "../relationship/DimensionBar";
import { useCharacterStore } from "../../stores/useCharacterStore";
import styles from "./BondTab.module.css";

export const BondTab: React.FC = () => {
  const relationship = useCharacterStore((s) => s.relationship);
  const fetchRelationship = useCharacterStore((s) => s.fetchRelationship);

  useEffect(() => {
    fetchRelationship();
  }, [fetchRelationship]);

  if (!relationship) {
    return <div className={styles.emptyState}>正在读取情感羁绊数据...</div>;
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h3 className={styles.title}>情感羁绊与多维动态</h3>
        <span className={styles.readonlyBadge}>客观映射 · Rule 19</span>
      </div>

      <div className={styles.summaryBox}>
        <span className={styles.summaryTitle}>Relational Horizon</span>
        <p className={styles.summaryText}>{relationship.summary || "与你的羁绊正在建立中..."}</p>
      </div>

      <div className={styles.metricsCard}>
        <DimensionBar
          label="信任度 (Trust)"
          value={relationship.trust}
          type="trust"
          icon="🛡️"
        />
        <DimensionBar
          label="熟悉度 (Familiarity)"
          value={relationship.familiarity}
          type="familiarity"
          icon="🌿"
        />
        <DimensionBar
          label="舒适度 (Comfort)"
          value={relationship.comfort}
          type="comfort"
          icon="☕"
        />
        <DimensionBar
          label="尊重度 (Respect)"
          value={relationship.respect}
          type="respect"
          icon="🤝"
        />
        <DimensionBar
          label="好感度 (Affection)"
          value={relationship.affection}
          type="affection"
          icon="💖"
        />
      </div>

      <div className={styles.footnote}>
        <p>
          💡 <span className={styles.footnoteStrong}>好感与亲密积累规则</span>
          ：好感（Affection）与信任（Trust）源于真实的日常交互——关注作息作息、分享日常心声、共鸣音乐与默契玩笑会让情感自然生长；机械刷屏或过早施压会触发伴侣的谨慎心理防线。
        </p>
        <span className={styles.footnoteMeta}>
          Governed deterministically by Aevum Core based on authentic interaction history.
        </span>
      </div>
    </div>
  );
};
