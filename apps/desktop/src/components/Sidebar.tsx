import React, { useState } from "react";
import {
  CharacterDebugResponse,
  CharacterStateResponse,
  LifeResponse,
  MemoryItem,
  RelationshipResponse,
} from "../types";

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  activeTab: "about" | "relationship" | "memories" | "debug";
  onSelectTab: (tab: "about" | "relationship" | "memories" | "debug") => void;
  characterState: CharacterStateResponse | null;
  relationship: RelationshipResponse | null;
  life: LifeResponse | null;
  memories: MemoryItem[];
  onDeleteMemory: (id: string) => Promise<void>;
  debugData: CharacterDebugResponse | null;
  activeConversationId: string | null;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  onClose,
  activeTab,
  onSelectTab,
  characterState,
  relationship,
  life,
  memories,
  onDeleteMemory,
  debugData,
  activeConversationId,
}) => {
  const [memoryFilter, setMemoryFilter] = useState<"ALL" | "USER" | "AEVUM">("ALL");
  const [deletingMemoryId, setDeletingMemoryId] = useState<string | null>(null);

  if (!isOpen) return null;

  const filteredMemories = memories.filter((m) => {
    if (memoryFilter === "ALL") return true;
    return m.subject_entity === memoryFilter;
  });

  const handleDelete = async (id: string) => {
    if (confirm("Are you sure you want Aevum to forget this memory?")) {
      setDeletingMemoryId(id);
      try {
        await onDeleteMemory(id);
      } finally {
        setDeletingMemoryId(null);
      }
    }
  };

  return (
    <aside className="companion-sidebar">
      <div className="sidebar-header">
        <div className="sidebar-tabs">
          <button
            className={`tab-btn ${activeTab === "about" ? "active" : ""}`}
            onClick={() => onSelectTab("about")}
          >
            Life & Identity
          </button>
          <button
            className={`tab-btn ${activeTab === "relationship" ? "active" : ""}`}
            onClick={() => onSelectTab("relationship")}
          >
            Relationship
          </button>
          <button
            className={`tab-btn ${activeTab === "memories" ? "active" : ""}`}
            onClick={() => onSelectTab("memories")}
          >
            Memories ({memories.length})
          </button>
          <button
            className={`tab-btn ${activeTab === "debug" ? "active" : ""}`}
            onClick={() => onSelectTab("debug")}
          >
            Debug
          </button>
        </div>
        <button className="close-btn" onClick={onClose} title="Close sidebar">
          ✕
        </button>
      </div>

      <div className="sidebar-content">
        {/* Tab 1: Life & Identity */}
        {activeTab === "about" && (
          <div className="tab-pane">
            <div className="panel-section">
              <h4 className="section-heading">Current Situation</h4>
              <div className="info-card highlight-card">
                <div className="info-row">
                  <span className="info-label">Activity:</span>
                  <span className="info-val capitalize">{life?.current_activity || characterState?.current_activity || "Resting"}</span>
                </div>
                <div className="info-row">
                  <span className="info-label">Location:</span>
                  <span className="info-val capitalize">{life?.current_location || characterState?.current_location || "Home"}</span>
                </div>
                <div className="info-row">
                  <span className="info-label">Mood:</span>
                  <span className="info-val">{characterState?.natural_mood || "Calm"}</span>
                </div>
                <div className="info-row">
                  <span className="info-label">Energy:</span>
                  <div className="progress-bar-container">
                    <div
                      className="progress-bar-fill"
                      style={{ width: `${Math.round((characterState?.energy ?? 0.5) * 100)}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>

            <div className="panel-section">
              <h4 className="section-heading">Identity Profile</h4>
              <div className="info-card">
                <div className="info-row">
                  <span className="info-label">Name:</span>
                  <span className="info-val">{characterState?.name || "Aevum"}</span>
                </div>
                <div className="info-row">
                  <span className="info-label">Occupation:</span>
                  <span className="info-val">{characterState?.occupation || "Independent"}</span>
                </div>
                <div className="bio-block">
                  <span className="info-label">Background:</span>
                  <p className="bio-text">{characterState?.background}</p>
                </div>
              </div>
            </div>

            {life?.recent_events && life.recent_events.length > 0 && (
              <div className="panel-section">
                <h4 className="section-heading">Recent Life Events</h4>
                <div className="event-list">
                  {life.recent_events.map((ev) => (
                    <div key={ev.id} className="event-item">
                      <div className="event-title">{ev.title}</div>
                      <div className="event-desc">{ev.description}</div>
                      <div className="event-meta">
                        <span className="event-badge">{ev.event_type}</span>
                        <span className="event-time">
                          {new Date(ev.occurred_at).toLocaleDateString([], {
                            month: "short",
                            day: "numeric",
                          })}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {life?.active_goals && life.active_goals.length > 0 && (
              <div className="panel-section">
                <h4 className="section-heading">Personal Intentions & Goals</h4>
                <div className="goal-list">
                  {life.active_goals.map((goal) => (
                    <div key={goal.id} className="goal-item">
                      <div className="goal-title">{goal.title}</div>
                      <div className="goal-desc">{goal.description}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Relationship */}
        {activeTab === "relationship" && (
          <div className="tab-pane">
            <div className="panel-section">
              <h4 className="section-heading">Relational Dynamic</h4>
              <div className="info-card narrative-card">
                <p className="narrative-text">
                  {relationship?.summary || "You are still getting to know each other."}
                </p>
              </div>
            </div>

            <div className="panel-section">
              <h4 className="section-heading">Relational Dimensions</h4>
              <div className="dimension-list">
                <div className="dimension-item">
                  <div className="dim-header">
                    <span className="dim-name">Familiarity</span>
                    <span className="dim-pct">{Math.round((relationship?.familiarity ?? 0) * 100)}%</span>
                  </div>
                  <div className="progress-bar-container">
                    <div
                      className="progress-bar-fill cyan"
                      style={{ width: `${Math.round((relationship?.familiarity ?? 0) * 100)}%` }}
                    />
                  </div>
                  <div className="dim-desc">{relationship?.familiarity_label}</div>
                </div>

                <div className="dimension-item">
                  <div className="dim-header">
                    <span className="dim-name">Trust</span>
                    <span className="dim-pct">{Math.round((relationship?.trust ?? 0) * 100)}%</span>
                  </div>
                  <div className="progress-bar-container">
                    <div
                      className="progress-bar-fill emerald"
                      style={{ width: `${Math.round((relationship?.trust ?? 0) * 100)}%` }}
                    />
                  </div>
                  <div className="dim-desc">{relationship?.trust_label}</div>
                </div>

                <div className="dimension-item">
                  <div className="dim-header">
                    <span className="dim-name">Comfort</span>
                    <span className="dim-pct">{Math.round((relationship?.comfort ?? 0) * 100)}%</span>
                  </div>
                  <div className="progress-bar-container">
                    <div
                      className="progress-bar-fill indigo"
                      style={{ width: `${Math.round((relationship?.comfort ?? 0) * 100)}%` }}
                    />
                  </div>
                  <div className="dim-desc">{relationship?.comfort_label}</div>
                </div>

                <div className="dimension-item">
                  <div className="dim-header">
                    <span className="dim-name">Respect</span>
                    <span className="dim-pct">{Math.round((relationship?.respect ?? 0) * 100)}%</span>
                  </div>
                  <div className="progress-bar-container">
                    <div
                      className="progress-bar-fill purple"
                      style={{ width: `${Math.round((relationship?.respect ?? 0) * 100)}%` }}
                    />
                  </div>
                  <div className="dim-desc">Respect for boundaries, integrity, and agency.</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: Memories */}
        {activeTab === "memories" && (
          <div className="tab-pane">
            <div className="memories-filter-bar">
              <button
                className={`filter-chip ${memoryFilter === "ALL" ? "active" : ""}`}
                onClick={() => setMemoryFilter("ALL")}
              >
                All ({memories.length})
              </button>
              <button
                className={`filter-chip ${memoryFilter === "USER" ? "active" : ""}`}
                onClick={() => setMemoryFilter("USER")}
              >
                About You ({memories.filter((m) => m.subject_entity === "USER").length})
              </button>
              <button
                className={`filter-chip ${memoryFilter === "AEVUM" ? "active" : ""}`}
                onClick={() => setMemoryFilter("AEVUM")}
              >
                About Aevum ({memories.filter((m) => m.subject_entity === "AEVUM").length})
              </button>
            </div>

            <div className="memories-list">
              {filteredMemories.length === 0 ? (
                <div className="empty-memories">
                  No long-term memories in this category yet. As you converse, important facts and
                  preferences will be distilled and retained here.
                </div>
              ) : (
                filteredMemories.map((mem) => (
                  <div key={mem.id} className="memory-card">
                    <div className="memory-card-header">
                      <div className="memory-badges">
                        <span className={`entity-badge ${mem.subject_entity.toLowerCase()}`}>
                          {mem.subject_entity === "USER" ? "You" : "Aevum"}
                        </span>
                        <span className="category-badge">{mem.category}</span>
                      </div>
                      <button
                        className="forget-btn"
                        onClick={() => handleDelete(mem.id)}
                        disabled={deletingMemoryId === mem.id}
                        title="Forget this memory"
                      >
                        {deletingMemoryId === mem.id ? "Forgetting..." : "Forget"}
                      </button>
                    </div>
                    <div className="memory-content">{mem.content}</div>
                    <div className="memory-footer">
                      <span className="recalled-count">
                        Recalled {mem.times_recalled} {mem.times_recalled === 1 ? "time" : "times"}
                      </span>
                      <span className="memory-date">
                        {new Date(mem.created_at).toLocaleDateString([], {
                          month: "short",
                          day: "numeric",
                        })}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* Tab 4: Developer Diagnostics */}
        {activeTab === "debug" && (
          <div className="tab-pane">
            <div className="debug-section">
              <h4 className="section-heading">Active Session</h4>
              <div className="debug-card">
                <div className="info-row">
                  <span className="info-label">Conversation ID:</span>
                  <code className="debug-code">{activeConversationId || "None"}</code>
                </div>
                <div className="info-row">
                  <span className="info-label">State Version:</span>
                  <span className="info-val">{debugData?.state_version ?? "—"}</span>
                </div>
                <div className="info-row">
                  <span className="info-label">Relational Version:</span>
                  <span className="info-val">{debugData?.relationship_version ?? "—"}</span>
                </div>
                <div className="info-row">
                  <span className="info-label">Total Memories in DB:</span>
                  <span className="info-val">{debugData?.total_memories ?? 0}</span>
                </div>
              </div>
            </div>

            <div className="debug-section">
              <h4 className="section-heading">Continuous State Vector</h4>
              <pre className="debug-json">
                {JSON.stringify(debugData?.raw_state, null, 2) || "Loading..."}
              </pre>
            </div>

            <div className="debug-section">
              <h4 className="section-heading">Relational Vector</h4>
              <pre className="debug-json">
                {JSON.stringify(debugData?.raw_relationship, null, 2) || "Loading..."}
              </pre>
            </div>

            <div className="debug-section">
              <h4 className="section-heading">Active Emotion Stance</h4>
              <pre className="debug-json">
                {JSON.stringify(debugData?.raw_emotion, null, 2) || "Loading..."}
              </pre>
            </div>

            <div className="debug-notice">
              Internal reasoning (thoughts) and system prompt text are strictly isolated in the backend
              and never leaked over HTTP/WebSocket.
            </div>
          </div>
        )}
      </div>
    </aside>
  );
};
