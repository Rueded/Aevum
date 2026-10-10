import React, { useEffect, useState } from "react";
import { api } from "../api";
import { ConversationListItem } from "../types";

interface ConversationHistoryViewProps {
  activeConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
  characterName?: string;
}

export const ConversationHistoryView: React.FC<ConversationHistoryViewProps> = ({
  activeConversationId,
  onSelectConversation,
  onNewConversation,
  characterName = "晚晚",
}) => {
  const [conversations, setConversations] = useState<ConversationListItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchConversations = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.getConversations(50);
      setConversations(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "获取历史会话失败");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchConversations();
  }, []);

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const confirmed = window.confirm("确定要删除此会话记录吗？删除后不可恢复。");
    if (!confirmed) return;

    setDeletingId(id);
    try {
      await api.deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (id === activeConversationId) {
        onNewConversation();
      }
    } catch (err) {
      alert(`删除失败: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setDeletingId(null);
    }
  };

  const formatTimestamp = (isoStr: string) => {
    try {
      let normalized = isoStr;
      if (!normalized.endsWith("Z") && !/[+-]\d{2}:\d{2}$/.test(normalized)) {
        normalized = normalized.replace(" ", "T") + "Z";
      }
      const d = new Date(normalized);
      if (isNaN(d.getTime())) return isoStr;
      return d.toLocaleString([], {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return isoStr;
    }
  };

  return (
    <div className="conversation-history-view">
      <div className="section-header history-header">
        <div>
          <h3>历史会话列表</h3>
          <span className="badge">{conversations.length} 个会话</span>
        </div>
        <div className="history-actions">
          <button
            type="button"
            className="chip-btn refresh-btn"
            onClick={fetchConversations}
            disabled={isLoading}
            title="刷新列表"
          >
            🔄
          </button>
          <button
            type="button"
            className="chip-btn new-chat-btn"
            onClick={onNewConversation}
            title="创建新对话"
          >
            ＋ 新建对话
          </button>
        </div>
      </div>

      {isLoading && (
        <div className="history-loading-indicator">
          <span>正在加载与 {characterName} 的历史记忆...</span>
        </div>
      )}

      {error && (
        <div className="genesis-alert error" style={{ margin: "12px 0" }}>
          <span>{error}</span>
          <button type="button" onClick={fetchConversations} style={{ marginLeft: "8px", textDecoration: "underline", background: "none", border: "none", color: "inherit", cursor: "pointer" }}>
            重试
          </button>
        </div>
      )}

      {!isLoading && conversations.length === 0 && (
        <div className="empty-state">
          <p>暂无历史会话记录。</p>
          <button type="button" className="chip-btn" onClick={onNewConversation}>
            立即开始第一次对话
          </button>
        </div>
      )}

      <div className="history-list">
        {conversations.map((item) => {
          const isActive = item.id === activeConversationId;
          const isDeleting = deletingId === item.id;
          return (
            <div
              key={item.id}
              className={`history-card ${isActive ? "active-session" : ""}`}
              onClick={() => onSelectConversation(item.id)}
            >
              <div className="history-card-header">
                <div className="history-card-title-row">
                  {isActive && <span className="active-session-pill">当前会话</span>}
                  <span className="history-timestamp">{formatTimestamp(item.updated_at)}</span>
                  <span className="history-msg-count">{item.message_count} 条消息</span>
                </div>
                <button
                  type="button"
                  className="history-delete-btn"
                  disabled={isDeleting}
                  onClick={(e) => handleDelete(item.id, e)}
                  title="删除该会话"
                >
                  {isDeleting ? "..." : "🗑️"}
                </button>
              </div>

              <div className="history-card-preview">
                {item.last_message_preview ? (
                  <p className="preview-snippet">{item.last_message_preview}</p>
                ) : (
                  <p className="preview-snippet empty-preview">暂无消息记录</p>
                )}
              </div>

              <div className="history-card-footer">
                <button
                  type="button"
                  className={`session-enter-btn ${isActive ? "current" : ""}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectConversation(item.id);
                  }}
                >
                  {isActive ? "正在交谈中 ➔" : "切换到此对话 ➔"}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
