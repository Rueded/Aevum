import React, { useEffect, useState } from "react";
import { api } from "../../api";
import type {
  BiographicalFactProjection,
  LifeEventProjection,
  LongitudinalMemoryResponse,
  PersonalPreferenceProjection,
  QualiaAnchorProjection,
  SharedHistoryEpisodeProjection,
} from "../../types";

export const BiographicalMemoryView: React.FC = () => {
  const [data, setData] = useState<LongitudinalMemoryResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSubTab, setSelectedSubTab] = useState<"milestones" | "preferences" | "shared" | "relational">("milestones");

  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const resp = await api.getLongitudinalMemory();
      setData(resp);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load longitudinal memory projection";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  if (isLoading && !data) {
    return (
      <div className="biography-view-loading" style={{ padding: 24, textAlign: "center", color: "var(--text-tertiary)" }}>
        <p>正在读取 Aevum 纵向记忆自传映射...</p>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="biography-view-error" style={{ padding: 24, textAlign: "center", color: "var(--color-danger)" }}>
        <p>⚠️ {error}</p>
        <button type="button" onClick={loadData} style={{ marginTop: 8, padding: "4px 12px", borderRadius: 4, background: "rgba(255,255,255,0.08)" }}>
          重试
        </button>
      </div>
    );
  }

  const qualiaMap = new Map<string, QualiaAnchorProjection>();
  data?.qualia.forEach((q: QualiaAnchorProjection) => qualiaMap.set(q.id, q));

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", padding: 16, overflowY: "auto", gap: 14 }}>
      {/* Rule 19 Constitutional Guard Header */}
      <div style={{ background: "rgba(255,255,255,0.03)", border: "1px dashed var(--border-subtle)", borderRadius: "var(--radius-sm)", padding: 10, fontSize: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <strong>🔒 只读人生映射 (Rule 19)</strong>
          <button type="button" onClick={loadData} title="刷新记忆快照" style={{ cursor: "pointer", color: "var(--text-secondary)" }}>
            ↻
          </button>
        </div>
        <p style={{ color: "var(--text-secondary)", marginTop: 4 }}>
          伴侣的心智核心完全驻留于 Aevum Core 后端，前端仅作真实投影呈现。
        </p>
      </div>

      {/* Sub-tab Navigation */}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        <button
          type="button"
          onClick={() => setSelectedSubTab("milestones")}
          style={{
            padding: "4px 10px",
            borderRadius: "var(--radius-full)",
            fontSize: 12,
            background: selectedSubTab === "milestones" ? "var(--accent-primary)" : "rgba(255,255,255,0.05)",
            color: selectedSubTab === "milestones" ? "#fff" : "var(--text-secondary)",
          }}
        >
          里程碑 ({data?.life_events.length || 0})
        </button>
        <button
          type="button"
          onClick={() => setSelectedSubTab("preferences")}
          style={{
            padding: "4px 10px",
            borderRadius: "var(--radius-full)",
            fontSize: 12,
            background: selectedSubTab === "preferences" ? "var(--accent-primary)" : "rgba(255,255,255,0.05)",
            color: selectedSubTab === "preferences" ? "#fff" : "var(--text-secondary)",
          }}
        >
          偏好根源 ({data?.preferences.length || 0})
        </button>
        <button
          type="button"
          onClick={() => setSelectedSubTab("shared")}
          style={{
            padding: "4px 10px",
            borderRadius: "var(--radius-full)",
            fontSize: 12,
            background: selectedSubTab === "shared" ? "var(--accent-primary)" : "rgba(255,255,255,0.05)",
            color: selectedSubTab === "shared" ? "#fff" : "var(--text-secondary)",
          }}
        >
          共同经历 ({data?.shared_episodes.length || 0})
        </button>
        <button
          type="button"
          onClick={() => setSelectedSubTab("relational")}
          style={{
            padding: "4px 10px",
            borderRadius: "var(--radius-full)",
            fontSize: 12,
            background: selectedSubTab === "relational" ? "var(--accent-primary)" : "rgba(255,255,255,0.05)",
            color: selectedSubTab === "relational" ? "#fff" : "var(--text-secondary)",
          }}
        >
          多维羁绊 (Rule 16)
        </button>
      </div>

      <div>
        {/* Sub-tab 1: Life Milestones & Eras */}
        {selectedSubTab === "milestones" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {data?.life_events.map((evt: LifeEventProjection) => (
              <div key={evt.id} style={{ background: "var(--bg-tertiary)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>{evt.headline}</span>
                  <span style={{ fontSize: 11, background: "rgba(255,255,255,0.08)", padding: "1px 6px", borderRadius: 4 }}>
                    {evt.era.replace("_", " ")}
                  </span>
                </div>
                <p style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.5 }}>{evt.summary}</p>
                {evt.qualia_ids && evt.qualia_ids.length > 0 && (
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
                    {evt.qualia_ids.map((qid: string) => {
                      const q = qualiaMap.get(qid);
                      if (!q) return null;
                      return (
                        <span key={qid} style={{ fontSize: 11, color: "var(--accent-primary-hover)", background: "var(--accent-soft)", padding: "2px 6px", borderRadius: 4 }}>
                          ✨ {q.sensory_modality}: {q.description}
                        </span>
                      );
                    })}
                  </div>
                )}
              </div>
            ))}

            <h4 style={{ marginTop: 12, marginBottom: 8, fontSize: 13, color: "var(--text-tertiary)" }}>
              确立传记基石
            </h4>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 8 }}>
              {data?.facts.map((fact: BiographicalFactProjection) => (
                <div key={fact.id} style={{ background: "var(--bg-tertiary)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)", padding: 8 }}>
                  <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>{fact.attribute_key.replace(/_/g, " ")}</div>
                  <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text-primary)", marginTop: 2 }}>{fact.attribute_value}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Sub-tab 2: Preferences */}
        {selectedSubTab === "preferences" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {data?.preferences.map((pref: PersonalPreferenceProjection) => (
              <div key={pref.id} style={{ background: "var(--bg-tertiary)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>{pref.object_name}</span>
                  <span style={{ fontSize: 11, color: "var(--accent-primary-hover)", background: "var(--accent-soft)", padding: "1px 6px", borderRadius: 4 }}>
                    {pref.category} · {pref.affinity}
                  </span>
                </div>
                <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 4 }}>
                  {pref.causal_state === "KNOWN" ? "🔗 关联经历根源" : "🌱 先天偏好 (自然倾向)"}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Sub-tab 3: Shared History */}
        {selectedSubTab === "shared" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {data?.shared_episodes.length === 0 ? (
              <div style={{ textAlign: "center", padding: 30, color: "var(--text-tertiary)", fontSize: 13 }}>
                暂未沉淀深度共同历程。多与伴侣经历重要时刻！
              </div>
            ) : (
              data?.shared_episodes.map((ep: SharedHistoryEpisodeProjection) => (
                <div key={ep.id} style={{ background: "var(--bg-tertiary)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: 12 }}>
                  <div style={{ fontWeight: 600, color: "var(--text-primary)" }}>{ep.title}</div>
                  <p style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 4, lineHeight: 1.5 }}>{ep.summary}</p>
                  {ep.key_learnings && ep.key_learnings.length > 0 && (
                    <ul style={{ marginTop: 8, paddingLeft: 18, fontSize: 12, color: "var(--text-tertiary)" }}>
                      {ep.key_learnings.map((item: string, idx: number) => (
                        <li key={idx}>{item}</li>
                      ))}
                    </ul>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {/* Sub-tab 4: Relational Dynamics */}
        {selectedSubTab === "relational" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {data?.relational_dynamics &&
              Object.entries(data.relational_dynamics).map(([metric, val]) => {
                const numericVal = typeof val === "number" ? val : 0;
                const percent = Math.round(numericVal * 100);
                return (
                  <div key={metric} style={{ background: "var(--bg-tertiary)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: 12 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 6 }}>
                      <span style={{ fontWeight: 500, color: "var(--text-primary)" }}>{metric.toUpperCase()}</span>
                      <span style={{ fontWeight: 600, color: "var(--text-secondary)" }}>{percent}%</span>
                    </div>
                    <div style={{ height: 6, background: "rgba(255,255,255,0.08)", borderRadius: 999, overflow: "hidden" }}>
                      <div style={{ height: "100%", width: `${percent}%`, background: "var(--accent-gradient)" }} />
                    </div>
                  </div>
                );
              })}
          </div>
        )}
      </div>
    </div>
  );
};
