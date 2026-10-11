import React, { useEffect, useState } from "react";
import { useConversationStore } from "../../stores/useConversationStore";
import { useCharacterStore } from "../../stores/useCharacterStore";
import styles from "./ConversationHistoryView.module.css";

interface ConversationHistoryViewProps {
  onSelectConversation?: (id: string) => void;
  onNewConversation?: () => void;
}

function formatTimestamp(isoStr: string) {
  try {
    let normalized = isoStr;
    if (!normalized.endsWith("Z") && !/[+-]\d{2}:\d{2}$/.test(normalized)) {
      normalized = normalized.replace(" ", "T") + "Z";
    }
    const d = new Date(normalized);
    if (isNaN(d.getTime())) return isoStr;
    return d.toLocaleString([], {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return isoStr;
  }
}

export const ConversationHistoryView: React.FC<ConversationHistoryViewProps> = ({
  onSelectConversation,
  onNewConversation,
}) => {
  const conversations = useConversationStore((s) => s.conversations);
  const activeConversationId = useConversationStore((s) => s.activeConversationId);
  const isLoadingList = useConversationStore((s) => s.isLoadingList);
  const fetchConversations = useConversationStore((s) => s.fetchConversations);
  const selectConversation = useConversationStore((s) => s.selectConversation);
  const deleteConversation = useConversationStore((s) => s.deleteConversation);
  const createConversation = useConversationStore((s) => s.createConversation);

  const characterState = useCharacterStore((s) => s.characterState);
  const characterName = characterState?.name || "苏棠";

  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  const handleSelect = (id: string) => {
    selectConversation(id);
    onSelectConversation?.(id);
  };

  const handleNew = async () => {
    await createConversation();
    onNewConversation?.();
  };

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (window.confirm("确定要删除此会话记录吗？删除后不可恢复。")) {
      setDeletingId(id);
      try {
        await deleteConversation(id);
      } finally {
        setDeletingId(null);
      }
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div>
          <span className={styles.title}>历史会话列表</span>
          <span className={styles.countBadge}>{conversations.length} 个会话</span>
        </div>
        <div className={styles.actions}>
          <button
            type="button"
            className={styles.chipBtn}
            onClick={() => fetchConversations()}
            disabled={isLoadingList}
            title="刷新列表"
          >
            🔄
          </button>
          <button
            type="button"
            className={styles.chipBtn}
            onClick={handleNew}
            title="创建新对话"
          >
            ＋ 新建对话
          </button>
        </div>
      </div>

      {conversations.length === 0 ? (
        <div className={styles.emptyState}>
          <p>暂无历史会话记录。</p>
          <button type="button" className={styles.chipBtn} onClick={handleNew}>
            与 {characterName} 开启第一次对话
          </button>
        </div>
      ) : (
        <div className={styles.list}>
          {conversations.map((item) => {
            const isActive = item.id === activeConversationId;
            const isDeleting = deletingId === item.id;

            return (
              <div
                key={item.id}
                className={`${styles.card} ${isActive ? styles.activeCard : ""}`}
                onClick={() => handleSelect(item.id)}
              >
                <div className={styles.cardHeader}>
                  <div className={styles.metaRow}>
                    {isActive && <span className={styles.activePill}>当前会话</span>}
                    <span className={styles.timestamp}>{formatTimestamp(item.updated_at)}</span>
                    <span className={styles.msgCount}>{item.message_count} 条消息</span>
                  </div>
                  <button
                    type="button"
                    className={styles.deleteBtn}
                    disabled={isDeleting}
                    onClick={(e) => handleDelete(item.id, e)}
                    title="删除该会话"
                  >
                    {isDeleting ? "..." : "🗑️"}
                  </button>
                </div>

                <p className={styles.previewSnippet}>
                  {item.last_message_preview || "暂无消息记录"}
                </p>

                <div className={styles.cardFooter}>
                  <span className={styles.switchBtn}>
                    {isActive ? "正在交谈中 ➔" : "切换到此对话 ➔"}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
