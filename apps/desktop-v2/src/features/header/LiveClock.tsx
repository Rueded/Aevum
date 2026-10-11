import React, { useEffect, useState } from "react";
import styles from "./LiveClock.module.css";

export const LiveClock: React.FC = () => {
  const [timeStr, setTimeStr] = useState<string>(() =>
    new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
  );

  useEffect(() => {
    const updateTime = () => {
      setTimeStr(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
    };
    const timer = setInterval(updateTime, 5000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className={styles.clockPill} title="当前真实时间 · 与马来西亚同在 UTC+8 时区">
      <span className={styles.icon}>🕒</span>
      <span className={styles.time}>{timeStr}</span>
      <span className={styles.tz}>UTC+8</span>
    </div>
  );
};
