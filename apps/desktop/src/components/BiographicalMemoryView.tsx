import React, { useEffect, useState } from "react";
import { api } from "../api";
import {
  BiographicalFactProjection,
  LifeEventProjection,
  LongitudinalMemoryResponse,
  PersonalPreferenceProjection,
  QualiaAnchorProjection,
  SharedHistoryEpisodeProjection,
} from "../types";

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
      <div className="biography-view-loading">
        <span className="loading-spinner" />
        <p>Loading Aevum's longitudinal memory projection...</p>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="biography-view-error">
        <p className="error-text">⚠️ {error}</p>
        <button className="retry-btn" onClick={loadData}>Retry</button>
      </div>
    );
  }

  const qualiaMap = new Map<string, QualiaAnchorProjection>();
  data?.qualia.forEach((q) => qualiaMap.set(q.id, q));

  return (
    <div className="biographical-memory-view">
      {/* Rule 19 Constitutional Guard Header */}
      <div className="biography-constitutional-banner">
        <div className="banner-icon">🔒</div>
        <div className="banner-content">
          <strong>Read-Only Memory Projection (Rule 19)</strong>
          <p>
            Character mind resides exclusively in Aevum Core. The desktop UI presents memories
            and shared history without mutating canonical reality.
          </p>
        </div>
        <button className="refresh-mini-btn" onClick={loadData} title="Refresh memory snapshot">
          ↻
        </button>
      </div>

      {/* Sub-tab Navigation */}
      <div className="biography-sub-tabs">
        <button
          className={`sub-tab-btn ${selectedSubTab === "milestones" ? "active" : ""}`}
          onClick={() => setSelectedSubTab("milestones")}
        >
          Life Milestones ({data?.life_events.length || 0})
        </button>
        <button
          className={`sub-tab-btn ${selectedSubTab === "preferences" ? "active" : ""}`}
          onClick={() => setSelectedSubTab("preferences")}
        >
          Preferences & Roots ({data?.preferences.length || 0})
        </button>
        <button
          className={`sub-tab-btn ${selectedSubTab === "shared" ? "active" : ""}`}
          onClick={() => setSelectedSubTab("shared")}
        >
          Shared Journey ({data?.shared_episodes.length || 0})
        </button>
        <button
          className={`sub-tab-btn ${selectedSubTab === "relational" ? "active" : ""}`}
          onClick={() => setSelectedSubTab("relational")}
        >
          Relational Bond (Rule 16)
        </button>
      </div>

      <div className="biography-sub-content">
        {/* Sub-tab 1: Life Milestones & Eras */}
        {selectedSubTab === "milestones" && (
          <div className="milestones-pane">
            <div className="section-title-row">
              <h4>Chronological Life Milestones</h4>
              <span className="section-subtext">Events & sensory qualia anchors across developmental eras</span>
            </div>

            <div className="events-timeline">
              {data?.life_events.map((evt: LifeEventProjection) => (
                <div key={evt.id} className="timeline-event-card">
                  <div className="event-era-badge">{evt.era.replace("_", " ")}</div>
                  <div className="event-main">
                    <div className="event-header-row">
                      <span className="event-headline">{evt.headline}</span>
                      <span className={`recall-badge ${evt.recall_level.toLowerCase()}`}>
                        {evt.recall_level}
                      </span>
                    </div>
                    <p className="event-summary">{evt.summary}</p>

                    {evt.qualia_ids && evt.qualia_ids.length > 0 && (
                      <div className="qualia-chips-row">
                        {evt.qualia_ids.map((qid) => {
                          const q = qualiaMap.get(qid);
                          if (!q) return null;
                          return (
                            <span key={qid} className="qualia-chip" title={q.description}>
                              ✨ {q.sensory_modality}: {q.description}
                            </span>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            <div className="section-title-row" style={{ marginTop: "20px" }}>
              <h4>Canonical Biographical Facts</h4>
            </div>
            <div className="facts-grid">
              {data?.facts.map((fact: BiographicalFactProjection) => (
                <div key={fact.id} className="fact-item-card">
                  <div className="fact-key">{fact.attribute_key.replace(/_/g, " ")}</div>
                  <div className="fact-value">{fact.attribute_value}</div>
                  <div className="fact-meta">
                    <span>{fact.era}</span> · <span>{fact.domain}</span> · <span>{fact.recall_level}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Sub-tab 2: Preferences & Causal Roots (Lock D) */}
        {selectedSubTab === "preferences" && (
          <div className="preferences-pane">
            <div className="section-title-row">
              <h4>Grounded Preferences & Causal Roots</h4>
              <span className="section-subtext">
                Lock D Compliance: Unknown origins remain genuine boundaries without fabrication
              </span>
            </div>

            <div className="preferences-grid">
              {data?.preferences.map((pref: PersonalPreferenceProjection) => (
                <div key={pref.id} className="preference-card">
                  <div className="preference-header">
                    <span className="pref-category">{pref.category}</span>
                    <span className={`affinity-pill ${pref.affinity.toLowerCase()}`}>{pref.affinity}</span>
                  </div>
                  <div className="pref-name">{pref.object_name}</div>
                  <div className="pref-era">Acquired in: {pref.era_acquired}</div>

                  <div className={`causal-status-box ${pref.causal_state === "KNOWN" ? "grounded" : "ungrounded"}`}>
                    {pref.causal_state === "KNOWN" ? (
                      <div>
                        <span className="causal-tag grounded">🔗 Grounded Origin</span>
                        <p className="causal-desc">
                          Causally linked to past life event (Relation ID: {pref.causal_relation_id})
                        </p>
                      </div>
                    ) : (
                      <div>
                        <span className="causal-tag ungrounded">🌱 Natural Inclination</span>
                        <p className="causal-desc">
                          Organic preference without a dramatic origin story (Lock D: UNKNOWN preserved)
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Sub-tab 3: Shared History with User (Lock 4 & Lock F) */}
        {selectedSubTab === "shared" && (
          <div className="shared-history-pane">
            <div className="section-title-row">
              <h4>Longitudinal Shared History</h4>
              <span className="section-subtext">
                Episodes experienced collaboratively with you (HistoryScope.SHARED_WITH_USER)
              </span>
            </div>

            <div className="shared-episodes-list">
              {data?.shared_episodes.map((ep: SharedHistoryEpisodeProjection) => (
                <div key={ep.id} className="shared-episode-card">
                  <div className="episode-top-bar">
                    <span className="episode-type-tag">{ep.episode_type.replace(/_/g, " ")}</span>
                    <span className="session-anchor-badge">Session: {ep.session_anchor}</span>
                    <span className="recall-level-pill">{ep.recall_level}</span>
                  </div>
                  <h5 className="episode-title">{ep.title}</h5>
                  <p className="episode-summary">{ep.summary}</p>

                  {ep.key_learnings && ep.key_learnings.length > 0 && (
                    <div className="learnings-box">
                      <div className="learnings-label">Mutual Learnings & Discoveries:</div>
                      <ul>
                        {ep.key_learnings.map((item, idx) => (
                          <li key={idx}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Sub-tab 4: Relational Dynamics (Rule 16) */}
        {selectedSubTab === "relational" && (
          <div className="relational-dynamics-pane">
            <div className="section-title-row">
              <h4>Multidimensional Relational Dynamics</h4>
              <span className="section-subtext">
                Rule 16: Independent relationship dimensions (0.0 to 1.0) without a single flat score
              </span>
            </div>

            <div className="dynamics-bars-grid">
              {data?.relational_dynamics &&
                Object.entries(data.relational_dynamics).map(([metric, val]) => (
                  <div key={metric} className="relational-meter-card">
                    <div className="meter-label-row">
                      <span className="metric-title">{metric.charAt(0).toUpperCase() + metric.slice(1)}</span>
                      <span className="metric-value">{(val * 100).toFixed(0)}%</span>
                    </div>
                    <div className="meter-bar-track">
                      <div
                        className={`meter-bar-fill ${metric}`}
                        style={{ width: `${Math.min(100, Math.max(0, val * 100))}%` }}
                      />
                    </div>
                  </div>
                ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
