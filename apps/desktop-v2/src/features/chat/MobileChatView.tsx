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
            type="button"
            className={`${styles.iconBtn} ${styles.callBtn}`}
            onClick={onStartCall}
            title="拨打实时语音通话"
            aria-label="实时语音通话"
          >
            📞
          </button>
          <button
            type="button"
            className={styles.iconBtn}
            onClick={() => createConversation()}
            title="新开一轮会话"
            aria-label="新开会话"
          >
            ＋
          </button>
          <button
            type="button"
            className={`${styles.iconBtn} ${mobileDrawerTab ? styles.iconBtnActive : ""}`}
            onClick={() => setMobileDrawerTab("memories")}
            title="伴侣抽屉 (记忆 / 羁绊 / 历程 / 历史)"
            aria-label="伴侣抽屉"
          >
            ☰
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

      {/* Mobile Drawer Bottom Sheet for Memories, Bond, Journey, History */}
      {mobileDrawerTab && (
        <div
          className={styles.drawerOverlay}
          onClick={() => setMobileDrawerTab(null)}
        >
          <div
            className={styles.bottomSheet}
            onClick={(e) => e.stopPropagation()}
          >
            <div className={styles.dragHandle} />

            {/* Companion Profile Card in Drawer */}
            <div className={styles.drawerCompanionHeader}>
              <div className={styles.drawerAvatarWrap}>
                <div className={styles.drawerAvatarCircle}>{avatarLetter}</div>
                <span
                  className={`${styles.onlineDot} ${
                    isBackendOnline ? styles.onlineDotActive : styles.onlineDotOffline
                  }`}
                />
              </div>
              <div className={styles.drawerCompanionMeta}>
                <div className={styles.drawerCompanionTitleRow}>
                  <span className={styles.drawerCompanionName}>{characterName}</span>
                  <span className={styles.moodBadge}>
                    {characterState?.natural_mood || characterState?.mood || "平静"}
                  </span>
                  <span className={styles.bondBadge}>
                    💖 好感度 {Math.round((relationship?.affection ?? 0.64) * 100)}%
                  </span>
                </div>
                <div
                  className={styles.drawerLocationRow}
                  onClick={() => {
                    setMobileDrawerTab(null);
                    setIsDatingModalOpen(true);
                  }}
                  title="点击切换约会地点与现场"
                >
                  <span>{statusSummary}</span>
                  <span className={styles.switchLocationPill}>切换地点 ➔</span>
                </div>
              </div>
              <button
                type="button"
                className={styles.sheetCloseBtn}
                onClick={() => setMobileDrawerTab(null)}
                aria-label="关闭"
              >
                ✕
              </button>
            </div>

            {/* Header Tabs */}
            <div className={styles.sheetTabsRow}>
              <button
                type="button"
                className={`${styles.sheetTab} ${mobileDrawerTab === "memories" ? styles.sheetTabActive : ""}`}
                onClick={() => setMobileDrawerTab("memories")}
              >
                💫 共同记忆
              </button>
              <button
                type="button"
                className={`${styles.sheetTab} ${mobileDrawerTab === "bond" ? styles.sheetTabActive : ""}`}
                onClick={() => setMobileDrawerTab("bond")}
              >
                💖 情感羁绊
              </button>
              <button
                type="button"
                className={`${styles.sheetTab} ${mobileDrawerTab === "journey" ? styles.sheetTabActive : ""}`}
                onClick={() => setMobileDrawerTab("journey")}
              >
                📖 人生成长
              </button>
              <button
                type="button"
                className={`${styles.sheetTab} ${mobileDrawerTab === "history" ? styles.sheetTabActive : ""}`}
                onClick={() => setMobileDrawerTab("history")}
              >
                🕒 会话历史
              </button>
            </div>

            {/* Tab Body */}
            <div className={styles.sheetBody}>
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

            {/* Bottom Actions inside Sheet */}
            <div className={styles.sheetFooter}>
              <button
                type="button"
                className={styles.sheetFooterBtn}
                onClick={() => {
                  setMobileDrawerTab(null);
                  onOpenSettings();
                }}
              >
                ⚙️ 伴侣与系统设置
              </button>
              <button
                type="button"
                className={styles.sheetFooterBtnSecondary}
                onClick={() => {
                  setMobileDrawerTab(null);
                  onSwitchToDesktop();
                }}
              >
                🖥️ 切换为桌面模式
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
