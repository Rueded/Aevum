import React from "react";
import { LiveClock } from "./LiveClock";
import { useHealthStore } from "../../stores/useHealthStore";
import { useCharacterStore } from "../../stores/useCharacterStore";
import { useChatStore } from "../../stores/useChatStore";
import { useVisualStore } from "../../stores/useVisualStore";
import { useConversationStore } from "../../stores/useConversationStore";
import { DatingSituationModal } from "../stage/DatingSituationModal";
import styles from "./PresenceHeader.module.css";

interface PresenceHeaderProps {
  isDrawerOpen: boolean;
  onToggleDrawer: () => void;
  onOpenSettings: () => void;
  onOpenDevInspector?: () => void;
  onSwitchToMobile?: () => void;
}

const ACTIVITY_LABELS_ZH: Record<string, string> = {
  REST: "休息中",
  READING: "阅读看书中",
  MUSIC: "练琴弹奏中",
  STUDY: "自习备考中",
  CLASS: "大学上课中",
  GAME: "打游戏中",
  ANIME: "补番中",
  MOVIE: "看电影中",
  EXERCISE: "散步运动中",
  COOKING: "准备好吃的",
  SOCIAL: "与好友闲聊",
  OUTING: "外出闲逛中",
  PERSONAL_PROJECT: "乐理创作中",
};

const LOCATION_LABELS_ZH: Record<string, string> = {
  HOME: "雪隆老家",
  CAMPUS: "槟城理大",
  LIBRARY: "图书馆",
  CAFE: "咖啡馆",
  OUTSIDE: "街上户外",
};

function formatNaturalPresence(activity?: string, location?: string): string {
  if (!activity && !location) return "📍 雪隆老家 · 休息中";
  const loc = location?.trim() || "雪隆老家";
  const act = activity?.trim() || "日常活动中";

  const locLabel = LOCATION_LABELS_ZH[loc.toUpperCase()] || loc;
  const actLabel = ACTIVITY_LABELS_ZH[act.toUpperCase()] || act;

  return `📍 ${locLabel} · ${actLabel}`;
}

export const PresenceHeader: React.FC<PresenceHeaderProps> = ({
  isDrawerOpen,
  onToggleDrawer,
  onOpenSettings,
  onOpenDevInspector,
  onSwitchToMobile,
}) => {
  const [isDatingModalOpen, setIsDatingModalOpen] = React.useState<boolean>(false);
  const isBackendOnline = useHealthStore((s) => s.isBackendOnline);
  const characterState = useCharacterStore((s) => s.characterState);
  const isGenerating = useChatStore((s) => s.isGenerating);
  const isStageVisible = useVisualStore((s) => s.isStageVisible);
  const toggleStageVisible = useVisualStore((s) => s.toggleStageVisible);
  const createConversation = useConversationStore((s) => s.createConversation);

  const characterName = characterState?.name || "苏棠";
  const avatarLetter = characterName.charAt(0) || "棠";

  const presenceText = characterState
    ? `${characterState.natural_mood || characterState.mood} (${formatNaturalPresence(
        characterState.current_activity,
        characterState.current_location
      )})`
    : isBackendOnline
    ? "在线并注视着你"
    : "正在连接伴侣核心...";

  const statusClass = isGenerating
    ? styles.statusGenerating
    : isBackendOnline
    ? styles.statusOnline
    : styles.statusOffline;

  return (
    <header className={styles.header}>
      <div className={styles.leftSection}>
        <div className={styles.avatarContainer}>
          <div className={styles.avatar}>{avatarLetter}</div>
          <span className={`${styles.statusDot} ${statusClass}`} />
        </div>

        <div className={styles.metaInfo}>
          <div className={styles.titleRow}>
            <span className={styles.companionName}>{characterName}</span>
            <span
              className={`${styles.healthBadge} ${
                isBackendOnline ? styles.healthBadgeOnline : styles.healthBadgeOffline
              }`}
            >
              {isBackendOnline ? "在线" : "离线"}
            </span>
            <LiveClock />
          </div>

          <div className={styles.presenceStatus} title={presenceText}>
            {isGenerating ? (
              <span className={styles.generatingText}>
                {characterName} 正在思考与打字中...
              </span>
            ) : (
              <span>{presenceText}</span>
            )}
          </div>
        </div>
      </div>

      <div className={styles.rightSection}>
        <button
          className={styles.actionBtn}
          onClick={() => createConversation()}
          title="开启新的一轮对话会话"
        >
          <svg className={styles.icon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 5v14M5 12h14" />
          </svg>
          <span>新对话</span>
        </button>

        <button
          className={`${styles.actionBtn} ${isStageVisible ? styles.actionBtnActive : ""}`}
          onClick={toggleStageVisible}
          title={isStageVisible ? "收起伴侣立绘舞台" : "展开伴侣立绘舞台"}
        >
          <svg className={styles.icon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
          <span>形象舞台</span>
        </button>

        <button
          className={styles.actionBtn}
          onClick={onOpenSettings}
          title="个性化风格、时区与偏好设置"
        >
          <svg className={styles.icon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z" />
          </svg>
          <span>设置</span>
        </button>

        {onOpenDevInspector && (
          <button
            className={styles.iconOnlyBtn}
            onClick={onOpenDevInspector}
            title="开发者心智透视面板 (Ctrl+Shift+D)"
          >
            <span style={{ fontSize: 13, fontWeight: 700 }}>⚡</span>
          </button>
        )}

        <button
          className={styles.actionBtn}
          onClick={() => setIsDatingModalOpen(true)}
          title="约会地点签到与当下生活现场"
        >
          <span style={{ fontSize: 13 }}>📍</span>
          <span>约会地点</span>
        </button>

        {onSwitchToMobile && (
          <button
            className={styles.actionBtn}
            onClick={onSwitchToMobile}
            title="切换为手机纯聊模式（无模型渲染，纯粹极速对话）"
          >
            <span style={{ fontSize: 13 }}>📱</span>
            <span>手机纯聊</span>
          </button>
        )}

        <button
          className={`${styles.iconOnlyBtn} ${isDrawerOpen ? styles.iconOnlyBtnActive : ""}`}
          onClick={onToggleDrawer}
          title={isDrawerOpen ? "收起伴侣抽屉" : "展开伴侣抽屉 (会话/记忆/关系/状态)"}
        >
          <svg className={styles.icon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
            <line x1="15" y1="3" x2="15" y2="21" />
          </svg>
        </button>
      </div>

      <DatingSituationModal
        isOpen={isDatingModalOpen}
        onClose={() => setIsDatingModalOpen(false)}
      />
    </header>
  );
};
