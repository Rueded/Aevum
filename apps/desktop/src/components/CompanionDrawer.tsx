import React from "react";
import {
  CharacterDebugResponse,
  CharacterStateResponse,
  ConversationDetail,
  LifeResponse,
  MemoryItem,
  MessageItem,
  RelationshipResponse,
} from "../types";
import { BiographicalMemoryView } from "./BiographicalMemoryView";
import { ChatView } from "./ChatView";
import { ConversationHistoryView } from "./ConversationHistoryView";

export type CompanionDrawerTab = "chat" | "history" | "journey" | "memories" | "bond" | "about";

export interface CompanionDrawerProps {
  isOpen: boolean;
  onToggleOpen: () => void;
  activeTab: CompanionDrawerTab;
  onSelectTab: (tab: CompanionDrawerTab) => void;
  // Chat Data
  conversation: ConversationDetail | null;
  isGenerating: boolean;
  inputMessage: string;
  onInputChange: (val: string) => void;
  onSendMessage: () => void;
  chatError: string | null;
  onRetry?: () => void;
  highlightedMessageId?: string | null;
  voiceConsentGranted: boolean;
  onSendVoiceMessage: (audioBase64: string, durationMs: number) => Promise<void>;
  playingMessageId: string | null;
  onPlayAudio: (msg: MessageItem) => void;
  onStopAudio: () => void;
  onOpenSettings: () => void;
  bubbleMode?: "multi" | "single";
  emojiRenderingEnabled?: boolean;
  onSelectConversation?: (id: string) => void;
  onNewConversation?: () => void;
  // Companion Read-Only Projections
  characterState: CharacterStateResponse | null;
  relationship: RelationshipResponse | null;
  life: LifeResponse | null;
  memories: MemoryItem[];
  debugData?: CharacterDebugResponse | null;
  onDeleteMemory?: (id: string) => Promise<void>;
}

export const CompanionDrawer: React.FC<CompanionDrawerProps> = ({
  isOpen,
  onToggleOpen,
  activeTab,
  onSelectTab,
  conversation,
  isGenerating,
  inputMessage,
  onInputChange,
  onSendMessage,
  chatError,
  onRetry,
  highlightedMessageId,
  voiceConsentGranted,
  onSendVoiceMessage,
  playingMessageId,
  onPlayAudio,
  onStopAudio,
  onOpenSettings,
  bubbleMode,
  emojiRenderingEnabled,
  onSelectConversation,
  onNewConversation,
  characterState,
  relationship,
  life,
  memories,
  debugData,
  onDeleteMemory,
}) => {
  return (
    <aside className={`companion-drawer ${isOpen ? "open" : "collapsed"}`}>
      {/* Drawer Header with Navigation Tabs */}
      <div className="drawer-header">
        <div className="drawer-tabs" role="tablist">
          <button
            type="button"
            className={`drawer-tab-btn ${activeTab === "chat" ? "active" : ""}`}
            onClick={() => onSelectTab("chat")}
            title="Chat Transcript"
          >
            💬 Chat
          </button>
          <button
            type="button"
            className={`drawer-tab-btn ${activeTab === "history" ? "active" : ""}`}
            onClick={() => onSelectTab("history")}
            title="历史会话列表"
          >
            📜 会话
          </button>
          <button
            type="button"
            className={`drawer-tab-btn ${activeTab === "journey" ? "active" : ""}`}
            onClick={() => onSelectTab("journey")}
            title="Aevum's Life Journey & Autobiographical Timeline"
          >
            📖 Journey
          </button>
          <button
            type="button"
            className={`drawer-tab-btn ${activeTab === "memories" ? "active" : ""}`}
            onClick={() => onSelectTab("memories")}
            title="Shared Memories with You"
          >
            💫 Memories
          </button>
          <button
            type="button"
            className={`drawer-tab-btn ${activeTab === "bond" ? "active" : ""}`}
            onClick={() => onSelectTab("bond")}
            title="Relational Dynamics & Emotional Bond"
          >
            💖 Bond
          </button>
          <button
            type="button"
            className={`drawer-tab-btn ${activeTab === "about" ? "active" : ""}`}
            onClick={() => onSelectTab("about")}
            title="About Aevum's Current Life"
          >
            🌿 Status
          </button>
        </div>

        <button
          type="button"
          className="drawer-toggle-btn"
          onClick={onToggleOpen}
          title={isOpen ? "Collapse Drawer" : "Expand Drawer"}
        >
          {isOpen ? "✕" : "◀"}
        </button>
      </div>

      {/* Drawer Body Content */}
      <div className="drawer-body">
        {/* Tab 1: Chat Transcript & Direct Messaging */}
        {activeTab === "chat" && (
          <div className="drawer-tab-content tab-chat">
            <ChatView
              messages={conversation?.messages || []}
              isGenerating={isGenerating}
              input={inputMessage}
              onInputChange={onInputChange}
              onSendMessage={onSendMessage}
              error={chatError}
              onRetry={onRetry}
              characterName={characterState?.name || "Aevum"}
              highlightedMessageId={highlightedMessageId}
              voiceConsentGranted={voiceConsentGranted}
              onSendVoiceMessage={onSendVoiceMessage}
              playingMessageId={playingMessageId}
              onPlayAudio={onPlayAudio}
              onStopAudio={onStopAudio}
              onOpenSettings={onOpenSettings}
              bubbleMode={bubbleMode}
              emojiRenderingEnabled={emojiRenderingEnabled}
              onOpenHistory={() => onSelectTab("history")}
              onNewChat={onNewConversation}
            />
          </div>
        )}

        {/* Tab 1.5: Conversation History Management */}
        {activeTab === "history" && (
          <div className="drawer-tab-content tab-history">
            <ConversationHistoryView
              activeConversationId={conversation?.id || null}
              onSelectConversation={(id) => {
                onSelectConversation?.(id);
                onSelectTab("chat");
              }}
              onNewConversation={() => {
                onNewConversation?.();
                onSelectTab("chat");
              }}
              characterName={characterState?.name || "晚晚"}
            />
          </div>
        )}

        {/* Tab 2: Biographical Journey (Phase 12 Read-Only Projection) */}
        {activeTab === "journey" && (
          <div className="drawer-tab-content tab-journey">
            <BiographicalMemoryView />
          </div>
        )}

        {/* Tab 3: Shared Memories */}
        {activeTab === "memories" && (
          <div className="drawer-tab-content tab-memories">
            <div className="section-header">
              <h3>Shared Memories</h3>
              <span className="badge">{memories.length} episodes</span>
            </div>
            {memories.length === 0 ? (
              <div className="empty-state">No shared memories recorded yet. Start conversing with Aevum!</div>
            ) : (
              <div className="memories-list">
                {memories.map((m) => (
                  <div key={m.id} className="memory-card">
                    <div className="memory-card-header">
                      <span className="memory-type">{m.category}</span>
                      <span className="memory-date">{new Date(m.created_at).toLocaleDateString()}</span>
                      {onDeleteMemory && (
                        <button
                          type="button"
                          className="memory-delete-btn"
                          onClick={() => onDeleteMemory(m.id)}
                          title="Delete memory"
                        >
                          ✕
                        </button>
                      )}
                    </div>
                    <div className="memory-content">{m.content}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tab 4: Relational Bond (Strictly Read-Only Projection, Rule 19 Compliant) */}
        {activeTab === "bond" && (
          <div className="drawer-tab-content tab-bond">
            <div className="section-header">
              <h3>Emotional Bond & Dynamics</h3>
              <span className="badge-readonly">Read-Only Projection</span>
            </div>
            {relationship ? (
              <div className="bond-metrics-container">
                <div className="bond-summary-box">
                  <span className="bond-summary-title">Relational Horizon</span>
                  <p className="bond-summary-text">{relationship.summary}</p>
                </div>

                <div className="metric-row">
                  <div className="metric-info">
                    <span className="metric-label">Trust</span>
                    <span className="metric-val">{Math.round((relationship.trust ?? 0) * 100)}%</span>
                  </div>
                  <div className="metric-bar-bg">
                    <div
                      className="metric-bar-fill fill-trust"
                      style={{ width: `${Math.min(100, Math.max(0, (relationship.trust ?? 0) * 100))}%` }}
                    />
                  </div>
                </div>

                <div className="metric-row">
                  <div className="metric-info">
                    <span className="metric-label">Familiarity</span>
                    <span className="metric-val">{Math.round((relationship.familiarity ?? 0) * 100)}%</span>
                  </div>
                  <div className="metric-bar-bg">
                    <div
                      className="metric-bar-fill fill-familiarity"
                      style={{ width: `${Math.min(100, Math.max(0, (relationship.familiarity ?? 0) * 100))}%` }}
                    />
                  </div>
                </div>

                <div className="metric-row">
                  <div className="metric-info">
                    <span className="metric-label">Comfort</span>
                    <span className="metric-val">{Math.round((relationship.comfort ?? 0) * 100)}%</span>
                  </div>
                  <div className="metric-bar-bg">
                    <div
                      className="metric-bar-fill fill-comfort"
                      style={{ width: `${Math.min(100, Math.max(0, (relationship.comfort ?? 0) * 100))}%` }}
                    />
                  </div>
                </div>

                <div className="metric-row">
                  <div className="metric-info">
                    <span className="metric-label">Respect</span>
                    <span className="metric-val">{Math.round((relationship.respect ?? 0) * 100)}%</span>
                  </div>
                  <div className="metric-bar-bg">
                    <div
                      className="metric-bar-fill fill-respect"
                      style={{ width: `${Math.min(100, Math.max(0, (relationship.respect ?? 0) * 100))}%` }}
                    />
                  </div>
                </div>

                <div className="metric-row">
                  <div className="metric-info">
                    <span className="metric-label">Affection</span>
                    <span className="metric-val">{Math.round((relationship.affection ?? 0) * 100)}%</span>
                  </div>
                  <div className="metric-bar-bg">
                    <div
                      className="metric-bar-fill fill-affection"
                      style={{ width: `${Math.min(100, Math.max(0, (relationship.affection ?? 0) * 100))}%` }}
                    />
                  </div>
                </div>

                <div className="bond-footnote">
                  <p style={{ margin: "0 0 4px 0", color: "var(--text-secondary)" }}>
                    💡 <strong>关系与好感沉淀规则</strong>：好感度（Affection）与信任（Trust）源于真实的日常相处——关心作息健康、分享生活趣事与内心想法、默契玩笑与真诚赞赏都会让情感自然累积；强行表白或施压会触发晚晚的矜持与心理防线。
                  </p>
                  <span style={{ fontSize: "0.75rem", opacity: 0.7 }}>
                    Dynamics are governed exclusively by Aevum Core based on authentic interaction history.
                  </span>
                </div>
              </div>
            ) : (
              <div className="empty-state">Relational data is loading...</div>
            )}
          </div>
        )}

        {/* Tab 5: About & Current Status */}
        {activeTab === "about" && (
          <div className="drawer-tab-content tab-about">
            <div className="section-header">
              <h3>Companion Presence</h3>
            </div>
            {characterState ? (
              <div className="about-details">
                <div className="about-item">
                  <span className="about-label">Name</span>
                  <span className="about-value">{characterState.name}</span>
                </div>
                <div className="about-item">
                  <span className="about-label">Occupation</span>
                  <span className="about-value">{characterState.occupation}</span>
                </div>
                <div className="about-item">
                  <span className="about-label">Mood</span>
                  <span className="about-value mood-tag">{characterState.mood}</span>
                </div>
                <div className="about-item">
                  <span className="about-label">Current Activity</span>
                  <span className="about-value">{characterState.current_activity || "Resting / Contemplating"}</span>
                </div>
                <div className="about-item">
                  <span className="about-label">Location</span>
                  <span className="about-value">{characterState.current_location || "Home"}</span>
                </div>
                {life && (
                  <div className="about-item">
                    <span className="about-label">Life Status</span>
                    <span className="about-value">{life.status || "Active"}</span>
                  </div>
                )}
                {debugData && (
                  <div className="about-item">
                    <span className="about-label">Total Memories</span>
                    <span className="about-value">{debugData.total_memories}</span>
                  </div>
                )}
              </div>
            ) : (
              <div className="empty-state">Status is loading...</div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
};
