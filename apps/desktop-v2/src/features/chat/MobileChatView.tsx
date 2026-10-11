import React from "react";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { useMessageSender } from "./useMessageSender";
import { useIdleNudge } from "./useIdleNudge";
import { useCharacterStore } from "../../stores/useCharacterStore";
import { useHealthStore } from "../../stores/useHealthStore";
import { useConversationStore } from "../../stores/useConversationStore";
import { useCallStore } from "../../stores/useCallStore";
import { CallHUD } from "../call/CallHUD";
import { DatingSituationModal } from "../stage/DatingSituationModal";
import { MemoriesTab } from "../drawer/MemoriesTab";
import { BondTab } from "../drawer/BondTab";
import { BiographicalMemoryView } from "../biographical/BiographicalMemoryView";
import { ConversationHistoryView } from "../conversations/ConversationHistoryView";
import type { MessageItem } from "../../types";
import styles from "./MobileChatView.module.css";

interface MobileChatViewProps {
  onSwitchToDesktop: () => void;
  onOpenSettings: () => void;
  onOpenHistory?: () => void;
  onPlayAudio?: (message: MessageItem) => void;
  onStopAudio?: () => void;
  onSendVoiceMessage?: (audioBase64: string, durationMs: number) => Promise<void>;
  onStartCall: () => void;
  onEndCall: () => void;
  onBargeIn: () => void;
}

export const MobileChatView: React.FC<MobileChatViewProps> = ({
  onSwitchToDesktop,
  onOpenSettings,
  onOpenHistory,
  onPlayAudio,
  onStopAudio,
  onSendVoiceMessage,
  onStartCall,
  onEndCall,
  onBargeIn,
}) => {
  const characterState = useCharacterStore((s) => s.characterState);
  const relationship = useCharacterStore((s) => s.relationship);
  const isBackendOnline = useHealthStore((s) => s.isBackendOnline);
  const createConversation = useConversationStore((s) => s.createConversation);

  const callMode = useCallStore((s) => s.callMode);
  const activeGenerationId = useCallStore((s) => s.activeGenerationId);
  const partialTranscript = useCallStore((s) => s.partialTranscript);
  const isMuted = useCallStore((s) => s.isMuted);
  const toggleMute = useCallStore((s) => s.toggleMute);
  const callError = useCallStore((s) => s.callError);
  const isCompanionSpeaking = useCallStore((s) => s.isCompanionSpeaking);

  const [isDatingModalOpen, setIsDatingModalOpen] = React.useState(false);
  const [mobileDrawerTab, setMobileDrawerTab] = React.useState<"memories" | "bond" | "journey" | "history" | null>(null);

  const { sendMessage, retryLastFailed } = useMessageSender(onPlayAudio);
  useIdleNudge(onPlayAudio);

  const characterName = characterState?.name || "苏棠";
  const avatarLetter = characterName.charAt(0) || "棠";
  const currentLoc = characterState?.current_location || "雪隆老家";
  const currentAct = characterState?.current_activity || "休息中";
  const statusSummary = `📍 ${currentLoc} · ${currentAct}`;

  return (
    <div className={styles.mobileContainer}>
      {/* Mobile Top Navigation & Status Bar */}
      <header className={styles.mobileHeader}>
        <div className={styles.leftInfo}>
          <div className={styles.avatarWrap}>
            <div className={styles.avatarCircle}>{avatarLetter}</div>
            <span
              className={`${styles.onlineDot} ${
                isBackendOnline ? styles.onlineDotActive : styles.onlineDotOffline
              }`}
            />
          </div>
          <div className={styles.nameMeta}>
            <div className={styles.nameRow}>
              <span className={styles.companionName}>{characterName}</span>
              <span className={styles.moodBadge}>
                {characterState?.natural_mood || characterState?.mood || "平静"}
              </span>
              <span
                className={styles.moodBadge}
                style={{
                  background: "rgba(236, 72, 153, 0.15)",
                  color: "#f472b6",
                  border: "1px solid rgba(236, 72, 153, 0.3)",
                  cursor: "pointer",
                }}
                onClick={() => setMobileDrawerTab("bond")}
                title={`好感度: ${Math.round((relationship?.affection ?? 0.64) * 100)}% · 信任度: ${Math.round((relationship?.trust ?? 0.8) * 100)}%`}
              >
                💖 {Math.round((relationship?.affection ?? 0.64) * 100)}%
              </span>
            </div>
            <div
              className={styles.locationSubtitle}
              onClick={() => setIsDatingModalOpen(true)}
              title="点击切换约会地点与现场"
            >
              {statusSummary}
            </div>
          </div>
        </div>

        <div className={styles.rightActions}>
          <button
            className={styles.iconBtn}
            onClick={() => setMobileDrawerTab("memories")}
            title="共同记忆"
          >
            💫
          </button>
          <button
            className={styles.iconBtn}
            onClick={() => setMobileDrawerTab("bond")}
            title="情感羁绊"
          >
            💖
          </button>
          <button
            className={styles.iconBtn}
            onClick={() => setMobileDrawerTab("history")}
            title="历史会话"
          >
            🕒
          </button>
          <button
            className={styles.iconBtn}
            onClick={onStartCall}
            title="拨打语音通话"
          >
            📞
          </button>
          <button
            className={styles.iconBtn}
            onClick={() => createConversation()}
            title="新开一轮会话"
          >
            ＋
          </button>
          <button
            className={styles.iconBtn}
            onClick={onOpenSettings}
            title="伴侣与系统设置"
          >
            ⚙️
          </button>
          <button
            className={styles.switchModeBtn}
            onClick={onSwitchToDesktop}
            title="切换回电脑桌面形象模式"
          >
            🖥️ 桌面版
          </button>
        </div>
      </header>

      {/* Realtime Call Overlay when in call */}
      {callMode !== "IDLE" && (
        <div className={styles.callOverlay}>
          <CallHUD
            callMode={callMode}
            activeGenerationId={activeGenerationId}
            partialTranscript={partialTranscript}
            isMuted={isMuted}
            onToggleMute={toggleMute}
            onStartCall={onStartCall}
            onEndCall={onEndCall}
            onBargeIn={onBargeIn}
            errorMessage={callError}
            characterName={characterName}
            onSendVoiceMessage={onSendVoiceMessage}
            isCompanionSpeaking={isCompanionSpeaking}
          />
        </div>
      )}

      {/* Pure Chat Messages Body */}
      <main className={styles.chatBody}>
        <MessageList
          onPlayAudio={onPlayAudio}
          onStopAudio={onStopAudio}
          onRetry={retryLastFailed}
        />
      </main>

      {/* Bottom Pure Chat Input */}
      <footer className={styles.chatFooter}>
        <ChatInput
          onSendMessage={sendMessage}
          onSendVoiceMessage={onSendVoiceMessage}
          onStopAudio={onStopAudio}
          onOpenSettings={onOpenSettings}
        />
      </footer>

      <DatingSituationModal
        isOpen={isDatingModalOpen}
        onClose={() => setIsDatingModalOpen(false)}
      />

      {/* Mobile Drawer Slide-over / Modal for Memories, Bond, Journey, History */}
      {mobileDrawerTab && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.75)",
            backdropFilter: "blur(6px)",
            zIndex: 1000,
            display: "flex",
            flexDirection: "column",
            justifyContent: "flex-end",
          }}
          onClick={() => setMobileDrawerTab(null)}
        >
          <div
            style={{
              width: "100%",
              height: "82vh",
              background: "var(--bg-secondary, #18181b)",
              borderTopLeftRadius: 20,
              borderTopRightRadius: 20,
              borderTop: "1px solid var(--border-default, #27272a)",
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header Tabs */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "12px 16px",
                borderBottom: "1px solid var(--border-subtle, rgba(255,255,255,0.06))",
              }}
            >
              <div style={{ display: "flex", gap: 8, overflowX: "auto" }}>
                <button
                  type="button"
                  style={{
                    padding: "6px 12px",
                    borderRadius: 16,
                    fontSize: 13,
                    fontWeight: 600,
                    border: "none",
                    cursor: "pointer",
                    background: mobileDrawerTab === "memories" ? "var(--color-primary, #ec4899)" : "rgba(255,255,255,0.06)",
                    color: "#fff",
                  }}
                  onClick={() => setMobileDrawerTab("memories")}
                >
                  💫 记忆
                </button>
                <button
                  type="button"
                  style={{
                    padding: "6px 12px",
                    borderRadius: 16,
                    fontSize: 13,
                    fontWeight: 600,
                    border: "none",
                    cursor: "pointer",
                    background: mobileDrawerTab === "bond" ? "var(--color-primary, #ec4899)" : "rgba(255,255,255,0.06)",
                    color: "#fff",
                  }}
                  onClick={() => setMobileDrawerTab("bond")}
                >
                  💖 羁绊
                </button>
                <button
                  type="button"
                  style={{
                    padding: "6px 12px",
                    borderRadius: 16,
                    fontSize: 13,
                    fontWeight: 600,
                    border: "none",
                    cursor: "pointer",
                    background: mobileDrawerTab === "journey" ? "var(--color-primary, #ec4899)" : "rgba(255,255,255,0.06)",
                    color: "#fff",
                  }}
                  onClick={() => setMobileDrawerTab("journey")}
                >
                  📖 历程
                </button>
                <button
                  type="button"
                  style={{
                    padding: "6px 12px",
                    borderRadius: 16,
                    fontSize: 13,
                    fontWeight: 600,
                    border: "none",
                    cursor: "pointer",
                    background: mobileDrawerTab === "history" ? "var(--color-primary, #ec4899)" : "rgba(255,255,255,0.06)",
                    color: "#fff",
                  }}
                  onClick={() => setMobileDrawerTab("history")}
                >
                  🕒 历史
                </button>
              </div>
              <button
                type="button"
                style={{
                  background: "transparent",
                  border: "none",
                  color: "var(--text-tertiary, #a1a1aa)",
                  fontSize: 18,
                  cursor: "pointer",
                  padding: "4px 8px",
                }}
                onClick={() => setMobileDrawerTab(null)}
              >
                ✕
              </button>
            </div>

            {/* Tab Body */}
            <div style={{ flex: 1, overflowY: "auto", padding: "12px 16px" }}>
              {mobileDrawerTab === "memories" && <MemoriesTab />}
              {mobileDrawerTab === "bond" && <BondTab />}
              {mobileDrawerTab === "journey" && <BiographicalMemoryView />}
              {mobileDrawerTab === "history" && (
                <ConversationHistoryView
                  onSelectConversation={() => setMobileDrawerTab(null)}
                  onNewConversation={() => setMobileDrawerTab(null)}
                />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
