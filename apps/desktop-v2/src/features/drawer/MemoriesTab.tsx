import React, { useEffect, useState } from "react";
import { useCharacterStore } from "../../stores/useCharacterStore";
import styles from "./MemoriesTab.module.css";

type FilterType = "ALL" | "USER" | "AEVUM";

export const MemoriesTab: React.FC = () => {
  const memories = useCharacterStore((s) => s.memories);
  const fetchMemories = useCharacterStore((s) => s.fetchMemories);
  const deleteMemory = useCharacterStore((s) => s.deleteMemory);

  const [filter, setFilter] = useState<FilterType>("ALL");
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    fetchMemories();
  }, [fetchMemories]);

  const filteredMemories = memories.filter((m) => {
    if (filter === "USER") return m.subject_entity === "USER";
    if (filter === "AEVUM") return m.subject_entity !== "USER";
    return true;
  });

  const handleDelete = async (id: string, content: string) => {
    if (window.confirm(`确定要让伴侣遗忘这段记忆吗？\n"${content.substring(0, 40)}..."`)) {
      setDeletingId(id);
      try {
        await deleteMemory(id);
      } finally {
        setDeletingId(null);
      }
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h3 className={styles.title}>沉淀的共同记忆</h3>
        <span className={styles.countBadge}>{memories.length} 条记忆</span>
      </div>

      <div className={styles.filterBar}>
        <button
          type="button"
          className={`${styles.filterPill} ${filter === "ALL" ? styles.filterPillActive : ""}`}
          onClick={() => setFilter("ALL")}
        >
          全部 ({memories.length})
        </button>
        <button
          type="button"
          className={`${styles.filterPill} ${filter === "USER" ? styles.filterPillActive : ""}`}
          onClick={() => setFilter("USER")}
        >
          关于你 ({memories.filter((m) => m.subject_entity === "USER").length})
        </button>
        <button
          type="button"
          className={`${styles.filterPill} ${filter === "AEVUM" ? styles.filterPillActive : ""}`}
          onClick={() => setFilter("AEVUM")}
        >
          关于伴侣 ({memories.filter((m) => m.subject_entity !== "USER").length})
        </button>
      </div>

      {filteredMemories.length === 0 ? (
        <div className={styles.emptyState}>
          暂无匹配的长期记忆。在对话中分享你的喜好与生活，伴侣会自动提取并沉淀！
        </div>
      ) : (
        <div className={styles.list}>
          {filteredMemories.map((m) => (
            <div key={m.id} className={styles.card}>
              <div className={styles.cardHeader}>
                <div className={styles.tagGroup}>
                  <span className={styles.categoryTag}>{m.category}</span>
                  <span className={styles.subjectTag}>
                    {m.subject_entity === "USER" ? "关于你" : "关于伴侣"}
                  </span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span className={styles.dateText}>
                    {new Date(m.created_at).toLocaleDateString()}
                  </span>
                  <button
                    type="button"
                    className={styles.deleteBtn}
                    onClick={() => handleDelete(m.id, m.content)}
                    disabled={deletingId === m.id}
                    title="遗忘这段记忆"
                  >
                    ✕
                  </button>
                </div>
              </div>

              <p className={styles.content}>{m.content}</p>

              <div className={styles.footer}>
                <span className={styles.recallBadge}>
                  <span>🔄</span>
                  <span>被唤起 {m.times_recalled ?? 0} 次</span>
                </span>
                <span>置信度 {Math.round((m.confidence ?? 0.9) * 100)}%</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
