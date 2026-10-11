import React from "react";
import styles from "./DimensionBar.module.css";

interface DimensionBarProps {
  label: string;
  value: number; // 0.0 - 1.0
  type: "trust" | "familiarity" | "comfort" | "respect" | "affection";
  icon?: string;
}

export const DimensionBar: React.FC<DimensionBarProps> = ({
  label,
  value,
  type,
  icon,
}) => {
  const percent = Math.min(100, Math.max(0, Math.round((value ?? 0) * 100)));

  const fillClass =
    type === "trust"
      ? styles.fillTrust
      : type === "familiarity"
      ? styles.fillFamiliarity
      : type === "comfort"
      ? styles.fillComfort
      : type === "respect"
      ? styles.fillRespect
      : styles.fillAffection;

  return (
    <div className={styles.metricRow}>
      <div className={styles.metricInfo}>
        <span className={styles.metricLabel}>
          {icon && <span>{icon}</span>}
          <span>{label}</span>
        </span>
        <span className={styles.metricValue}>{percent}%</span>
      </div>
      <div className={styles.barTrack}>
        <div className={`${styles.barFill} ${fillClass}`} style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
};
