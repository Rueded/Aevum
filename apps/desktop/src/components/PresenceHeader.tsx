import React from "react";
import { CharacterStateResponse, HealthData } from "../types";

interface PresenceHeaderProps {
  health: HealthData | null;
  characterState: CharacterStateResponse | null;
  isGenerating: boolean;
  onNewConversation: () => void;
  isSidebarOpen: boolean;
  onToggleSidebar: () => void;
  activeTab: string;
  onSelectTab: (tab: "about" | "relationship" | "memories" | "debug") => void;
  onOpenSettings?: () => void;
}

const ACTIVITY_LABELS: Record<string, string> = {
  REST: "Resting",
  READING: "Reading",
  MUSIC: "Practicing music",
  STUDY: "Studying",
  CLASS: "In class",
  GAME: "Playing a game",
  ANIME: "Watching anime",
  MOVIE: "Watching a film",
  EXERCISE: "Exercising",
  COOKING: "Cooking",
  SOCIAL: "Spending time with friends",
  OUTING: "Out and about",
  PERSONAL_PROJECT: "Working on a personal project",
};

const LOCATION_LABELS: Record<string, string> = {
  HOME: "home",
  CAMPUS: "campus",
  LIBRARY: "the library",
  CAFE: "a cafe",
  OUTSIDE: "outside",
};

function formatNaturalPresence(activity?: string, location?: string): string {
  if (!activity) return "Resting at home";
  const act = activity.toUpperCase().trim();
  const loc = (location || "HOME").toUpperCase().trim();

  const actLabel = ACTIVITY_LABELS[act] || `${act.charAt(0) + act.slice(1).toLowerCase()}`;
  const locLabel = LOCATION_LABELS[loc] || loc.toLowerCase();

  return `${actLabel} at ${locLabel}`;
}

export const PresenceHeader: React.FC<PresenceHeaderProps> = ({
  health,
  characterState,
  isGenerating,
  onNewConversation,
  isSidebarOpen,
  onToggleSidebar,
  activeTab,
  onSelectTab,
  onOpenSettings,
}) => {
  const isOnline = health?.status === "ok";

  const presenceText = characterState
    ? `${characterState.natural_mood} · ${formatNaturalPresence(characterState.current_activity, characterState.current_location)}`
    : isOnline
    ? "Awake and attentive"
    : "Connecting to core...";

  return (
    <header className="presence-header">
      <div className="presence-left">
        <div className={`avatar-container ${isGenerating ? "generating" : isOnline ? "online" : "offline"}`}>
          <div className="avatar">A</div>
          <span className="status-dot" />
        </div>
        <div className="character-info">
          <div className="name-row">
            <span className="character-name">{characterState?.name || "Aevum"}</span>
            <span className={`health-badge ${isOnline ? "online" : "offline"}`}>
              {isOnline ? "Core Online" : "Connecting..."}
            </span>
          </div>
          <div className="presence-status" title={presenceText}>
            {isGenerating ? (
              <span className="generating-text">Aevum is formulating thoughts...</span>
            ) : (
              <span>{presenceText}</span>
            )}
          </div>
        </div>
      </div>

      <div className="presence-actions">
        <button
          className="header-btn"
          onClick={onNewConversation}
          title="Start a new conversation session"
        >
          <svg className="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 5v14M5 12h14" />
          </svg>
          <span className="btn-text">New Chat</span>
        </button>

        {onOpenSettings && (
          <button
            className="header-btn"
            onClick={onOpenSettings}
            title="Desktop & Notification Settings"
          >
            <svg className="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z" />
            </svg>
            <span className="btn-text">Settings</span>
          </button>
        )}

        <div className="tab-pill-group">
          <button
            className={`tab-pill ${isSidebarOpen && activeTab === "about" ? "active" : ""}`}
            onClick={() => {
              if (!isSidebarOpen) onToggleSidebar();
              onSelectTab("about");
            }}
          >
            Life
          </button>
          <button
            className={`tab-pill ${isSidebarOpen && activeTab === "relationship" ? "active" : ""}`}
            onClick={() => {
              if (!isSidebarOpen) onToggleSidebar();
              onSelectTab("relationship");
            }}
          >
            Bond
          </button>
          <button
            className={`tab-pill ${isSidebarOpen && activeTab === "memories" ? "active" : ""}`}
            onClick={() => {
              if (!isSidebarOpen) onToggleSidebar();
              onSelectTab("memories");
            }}
          >
            Memories
          </button>
          <button
            className={`tab-pill ${isSidebarOpen && activeTab === "debug" ? "active" : ""}`}
            onClick={() => {
              if (!isSidebarOpen) onToggleSidebar();
              onSelectTab("debug");
            }}
            title="Inspect developer diagnostics"
          >
            Diagnostics
          </button>
        </div>

        <button
          className={`sidebar-toggle-btn ${isSidebarOpen ? "open" : ""}`}
          onClick={onToggleSidebar}
          title={isSidebarOpen ? "Collapse sidebar" : "Expand companion details"}
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
