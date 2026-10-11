import React from "react";
import { CrashBanner } from "./CrashBanner";
import { PresenceHeader } from "../features/header/PresenceHeader";
import { useVisualStore } from "../stores/useVisualStore";
import styles from "./AppShell.module.css";

interface AppShellProps {
  isDrawerOpen: boolean;
  onToggleDrawer: () => void;
  onOpenSettings: () => void;
  onOpenDevInspector?: () => void;
  onSwitchToMobile?: () => void;
  stageSlot?: React.ReactNode;
  drawerSlot?: React.ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({
  isDrawerOpen,
  onToggleDrawer,
  onOpenSettings,
  onOpenDevInspector,
  onSwitchToMobile,
  stageSlot,
  drawerSlot,
}) => {
  const isStageVisible = useVisualStore((s) => s.isStageVisible);

  return (
    <div className={styles.shell}>
      <CrashBanner />
      <PresenceHeader
        isDrawerOpen={isDrawerOpen}
        onToggleDrawer={onToggleDrawer}
        onOpenSettings={onOpenSettings}
        onOpenDevInspector={onOpenDevInspector}
        onSwitchToMobile={onSwitchToMobile}
      />
      <div className={styles.mainArea}>
        <div className={`${styles.stageContainer} ${!isStageVisible ? styles.stageHidden : ""}`}>
          {stageSlot}
        </div>
        <div
          className={`${styles.drawerContainer} ${!isDrawerOpen ? styles.drawerClosed : ""} ${
            !isStageVisible ? styles.drawerExpandedFull : ""
          }`}
        >
          {drawerSlot}
        </div>
      </div>
    </div>
  );
};
