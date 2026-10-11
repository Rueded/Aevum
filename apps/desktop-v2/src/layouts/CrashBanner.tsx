import React from "react";
import { useHealthStore } from "../stores/useHealthStore";
import styles from "./CrashBanner.module.css";

export const CrashBanner: React.FC = () => {
  const backendCrashed = useHealthStore((s) => s.backendCrashed);
  const errorMsg = useHealthStore((s) => s.backendCrashError);

  if (!backendCrashed) return null;

  return (
    <div className={styles.banner}>
      <div className={styles.content}>
        <span className={styles.icon}>⚠️</span>
        <span className={styles.message}>
          伴侣核心服务进程意外退出。{errorMsg ? `(${errorMsg})` : ""} 为保护数据一致性已暂停自动重启。
        </span>
      </div>
      <span className={styles.restartHint}>请重新启动 Aevum 桌面客户端</span>
    </div>
  );
};
