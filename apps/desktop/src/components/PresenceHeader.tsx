import React, { useEffect, useState } from "react";
import { CharacterStateResponse, HealthData } from "../types";

interface PresenceHeaderProps {
  health: HealthData | null;
  characterState: CharacterStateResponse | null;
  isGenerating: boolean;
  onNewConversation: () => void;
  isSidebarOpen: boolean;
  onToggleSidebar: () => void;
  isStageVisible?: boolean;
  onToggleStage?: () => void;
  activeTab?: string;
  onSelectTab?: (tab: "about" | "biography" | "relationship" | "memories" | "debug") => void;
  onOpenSettings?: () => void;
  onOpenGenesis?: () => void;
  onOpenPresentationSandbox?: () => void;
  onOpenDevInspector?: () => void;
  onOpenCompanionSwitcher?: () => void;
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
  if (!activity) return "📍 雪隆老家 · 休息中";
  const act = activity.toUpperCase().trim();
  const loc = (location || "HOME").toUpperCase().trim();

  const locLabel = LOCATION_LABELS_ZH[loc] || "家中";
  const actLabel = ACTIVITY_LABELS_ZH[act] || "日常中";

  return `📍 ${locLabel} · ${actLabel}`;
}

export const PresenceHeader: React.FC<PresenceHeaderProps> = ({
  health,
  characterState,
  isGenerating,
  onNewConversation,
  isSidebarOpen,
  onToggleSidebar,
  isStageVisible,
  onToggleStage,
  onOpenSettings,
  onOpenCompanionSwitcher,
}) => {
  const isOnline = health?.status === "ok";

  const [currentTimeStr, setCurrentTimeStr] = useState<string>(() => {
    return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  });

  useEffect(() => {
    const updateTime = () => {
      setCurrentTimeStr(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
    };
    const timer = setInterval(updateTime, 5000);
    return () => clearInterval(timer);
  }, []);

  const presenceText = characterState
    ? `${characterState.natural_mood} (${formatNaturalPresence(characterState.current_activity, characterState.current_location)})`
    : isOnline
    ? "在线并注视着你"
    : "连接中...";

  return (
    <header className="presence-header">
      <div className="presence-left">
        <div
          className={`avatar-container ${isGenerating ? "generating" : isOnline ? "online" : "offline"}`}
          onClick={onOpenCompanionSwitcher}
          style={{ cursor: onOpenCompanionSwitcher ? "pointer" : "default" }}
          title={onOpenCompanionSwitcher ? "点击切换伴侣人设" : undefined}
        >
          <div className="avatar">{characterState?.name ? characterState.name[0] : "棠"}</div>
          <span className="status-dot" />
        </div>
        <div className="character-info">
          <div
            className="name-row"
            onClick={onOpenCompanionSwitcher}
            style={{ cursor: onOpenCompanionSwitcher ? "pointer" : "default" }}
            title={onOpenCompanionSwitcher ? "点击切换伴侣人设" : undefined}
          >
            <span className="character-name">{characterState?.name || "Aevum · 苏棠"}</span>
            <span className={`health-badge ${isOnline ? "online" : "offline"}`}>
              {isOnline ? "在线" : "连接中"}
            </span>
            <div className="header-clock-pill" title="当前真实时间 · 与马来西亚同在 UTC+8 时区">
              <span className="clock-icon">🕒</span>
              <span className="clock-time">{currentTimeStr}</span>
              <span className="clock-tz">UTC+8</span>
            </div>
          </div>
          <div className="presence-status" title={presenceText}>
            {isGenerating ? (
              <span className="generating-text">{characterState?.name || "苏棠"}正在思考与打字中...</span>
            ) : (
              <span>{presenceText}</span>
            )}
          </div>
        </div>
      </div>

      <div className="presence-actions">
        {onOpenCompanionSwitcher && (
          <button
            className="header-btn"
            onClick={onOpenCompanionSwitcher}
            title="选择或切换伴侣人设（支持苏棠与全新独立新人设）"
            style={{
              background: "rgba(99, 102, 241, 0.15)",
              borderColor: "rgba(99, 102, 241, 0.35)",
              color: "#c7d2fe",
            }}
          >
            <svg className="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" />
              <circle cx="9" cy="7" r="4" />
              <path d="M23 21v-2a4 4 0 00-3-3.87" />
              <path d="M16 3.13a4 4 0 010 7.75" />
            </svg>
            <span className="btn-text">换人设</span>
          </button>
        )}

        <button
          className="header-btn"
          onClick={onNewConversation}
          title="开启新的一轮对话会话"
        >
          <svg className="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 5v14M5 12h14" />
          </svg>
          <span className="btn-text">新对话</span>
        </button>

        {onToggleStage && (
          <button
            className={`header-btn ${isStageVisible ? "active" : ""}`}
            onClick={onToggleStage}
            title={isStageVisible ? "收起伴侣立绘舞台" : "展开伴侣立绘舞台"}
          >
            <svg className="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
            <span className="btn-text">形象舞台</span>
          </button>
        )}

        {onOpenSettings && (
          <button
            className="header-btn"
            onClick={onOpenSettings}
            title="个性化风格、时区与偏好设置"
          >
            <svg className="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z" />
            </svg>
            <span className="btn-text">设置</span>
          </button>
        )}

        <button
          className={`sidebar-toggle-btn ${isSidebarOpen ? "open" : ""}`}
          onClick={onToggleSidebar}
          title={isSidebarOpen ? "收起伴侣侧边栏" : "展开伴侣侧边栏 (状态/记忆/关系/调试)"}
        >
          <svg className="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
            <line x1="15" y1="3" x2="15" y2="21" />
          </svg>
        </button>
      </div>
    </header>
  );
};
