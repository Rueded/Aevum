import React, { useState } from "react";
import { ChatPanel } from "../chat/ChatPanel";
import { ConversationHistoryView } from "../conversations/ConversationHistoryView";
import { BiographicalMemoryView } from "../biographical/BiographicalMemoryView";
import { MemoriesTab } from "./MemoriesTab";
import { BondTab } from "./BondTab";
import { StatusTab } from "./StatusTab";
import type { MessageItem } from "../../types";
import styles from "./CompanionDrawer.module.css";

export type CompanionDrawerTab = "chat" | "history" | "journey" | "memories" | "bond" | "about";

interface CompanionDrawerProps {
  onToggleOpen: () => void;
  onPlayAudio?: (message: MessageItem) => void;
  onStopAudio?: () => void;
  onSendVoiceMessage?: (audioBase64: string, durationMs: number) => Promise<void>;
  onOpenSettings?: () => void;
}

export const CompanionDrawer: React.FC<CompanionDrawerProps> = ({
  onToggleOpen,
  onPlayAudio,
  onStopAudio,
  onSendVoiceMessage,
  onOpenSettings,
}) => {
  const [activeTab, setActiveTab] = useState<CompanionDrawerTab>("chat");

  return (
    <aside className={styles.drawer}>
      <div className={styles.header}>
        <div className={styles.tabs} role="tablist">
          <button
            type="button"
            className={`${styles.tabBtn} ${activeTab === "chat" ? styles.tabBtnActive : ""}`}
            onClick={() => setActiveTab("chat")}
            title="聊天面板"
          >
            💬 对话
          </button>
          <button
            type="button"
            className={`${styles.tabBtn} ${activeTab === "history" ? styles.tabBtnActive : ""}`}
            onClick={() => setActiveTab("history")}
            title="历史会话"
          >
            📜 会话
          </button>
          <button
            type="button"
            className={`${styles.tabBtn} ${activeTab === "journey" ? styles.tabBtnActive : ""}`}
            onClick={() => setActiveTab("journey")}
            title="Aevum 纵向自传与人生历程"
          >
            📖 历程
          </button>
          <button
            type="button"
            className={`${styles.tabBtn} ${activeTab === "memories" ? styles.tabBtnActive : ""}`}
            onClick={() => setActiveTab("memories")}
            title="沉淀的共同记忆"
          >
            💫 记忆
          </button>
          <button
            type="button"
            className={`${styles.tabBtn} ${activeTab === "bond" ? styles.tabBtnActive : ""}`}
            onClick={() => setActiveTab("bond")}
            title="多维情感羁绊"
          >
            💖 羁绊
          </button>
          <button
            type="button"
            className={`${styles.tabBtn} ${activeTab === "about" ? styles.tabBtnActive : ""}`}
            onClick={() => setActiveTab("about")}
            title="伴侣当前实时状态"
          >
            🌿 状态
          </button>
        </div>

        <button
          type="button"
          className={styles.toggleBtn}
          onClick={onToggleOpen}
          title="收起抽屉"
        >
          ✕
        </button>
      </div>

      <div className={styles.body}>
        {activeTab === "chat" && (
          <ChatPanel
            onPlayAudio={onPlayAudio}
            onStopAudio={onStopAudio}
            onSendVoiceMessage={onSendVoiceMessage}
            onOpenHistory={() => setActiveTab("history")}
            onOpenSettings={onOpenSettings}
          />
        )}
        {activeTab === "history" && (
          <ConversationHistoryView
            onSelectConversation={() => setActiveTab("chat")}
            onNewConversation={() => setActiveTab("chat")}
          />
        )}
        {activeTab === "journey" && <BiographicalMemoryView />}
        {activeTab === "memories" && <MemoriesTab />}
        {activeTab === "bond" && <BondTab />}
        {activeTab === "about" && <StatusTab />}
      </div>
    </aside>
  );
};
