import React, { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { DesktopSettings, DesktopSettingsUpdate, NotificationHistoryItem } from "../types";

interface DesktopSettingsViewProps {
  isOpen: boolean;
  onClose: () => void;
  characterId?: string;
}

export const DesktopSettingsView: React.FC<DesktopSettingsViewProps> = ({
  isOpen,
  onClose,
  characterId = "aevum",
}) => {
  const [settings, setSettings] = useState<DesktopSettings | null>(null);
  const [history, setHistory] = useState<NotificationHistoryItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Form local state for editing
  const [proactiveEnabled, setProactiveEnabled] = useState<boolean>(false);
  const [idleAwarenessEnabled, setIdleAwarenessEnabled] = useState<boolean>(false);
  const [idleThreshold, setIdleThreshold] = useState<number>(300);
  const [timezone, setTimezone] = useState<string>("Asia/Shanghai");
  const [quietHoursEnabled, setQuietHoursEnabled] = useState<boolean>(false);
  const [quietHoursStart, setQuietHoursStart] = useState<string>("23:00");
  const [quietHoursEnd, setQuietHoursEnd] = useState<string>("08:00");
  const [maxDaily, setMaxDaily] = useState<number>(3);
  const [minCooldown, setMinCooldown] = useState<number>(120);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const [s, h] = await Promise.all([
        api.getDesktopSettings(characterId),
        api.getNotificationHistory(characterId, 50).catch(() => []),
      ]);
      setSettings(s);
      setHistory(h);

      // Populate local form
      setProactiveEnabled(s.proactive_enabled);
      setIdleAwarenessEnabled(s.idle_awareness_enabled);
      setIdleThreshold(s.idle_threshold_seconds);
      setTimezone(s.timezone);
      setQuietHoursEnabled(s.quiet_hours_enabled);
      setQuietHoursStart(s.quiet_hours_start || "23:00");
      setQuietHoursEnd(s.quiet_hours_end || "08:00");
      setMaxDaily(s.max_daily_reach_outs);
      setMinCooldown(s.min_cooldown_minutes);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load desktop settings");
    } finally {
      setIsLoading(false);
    }
  }, [characterId]);

  useEffect(() => {
    if (isOpen) {
      loadData();
    }
  }, [isOpen, loadData]);

  const handleSaveSettings = async () => {
    setIsSaving(true);
    setErrorMsg(null);
    setStatusMsg(null);
    try {
      const updates: DesktopSettingsUpdate = {
        proactive_enabled: proactiveEnabled,
        idle_awareness_enabled: idleAwarenessEnabled,
        idle_threshold_seconds: idleThreshold,
        timezone,
        quiet_hours_enabled: quietHoursEnabled,
        quiet_hours_start: quietHoursStart,
        quiet_hours_end: quietHoursEnd,
        max_daily_reach_outs: maxDaily,
        min_cooldown_minutes: minCooldown,
      };

      const updated = await api.updateDesktopSettings(updates, characterId);
      setSettings(updated);
      setStatusMsg("Desktop settings saved successfully.");
      setTimeout(() => setStatusMsg(null), 3000);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to save settings");
    } finally {
      setIsSaving(false);
    }
  };

  const handleSetDND = async (durationMinutes: number) => {
    setErrorMsg(null);
    try {
      const res = await api.setDND({ duration_minutes: durationMinutes }, characterId);
      if (settings) {
        setSettings({ ...settings, dnd_until: res.dnd_until });
      }
      setStatusMsg(`Do-Not-Disturb set for ${durationMinutes} minutes.`);
      setTimeout(() => setStatusMsg(null), 3000);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to set DND");
    }
  };

  const handleClearDND = async () => {
    setErrorMsg(null);
    try {
      const res = await api.setDND({ clear: true }, characterId);
      if (settings) {
        setSettings({ ...settings, dnd_until: res.dnd_until });
      }
      setStatusMsg("Do-Not-Disturb cleared.");
      setTimeout(() => setStatusMsg(null), 3000);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to clear DND");
    }
  };

  if (!isOpen) return null;

  const isDndActive = Boolean(settings?.dnd_until && new Date(settings.dnd_until) > new Date());

  return (
    <div className="desktop-settings-backdrop" onClick={onClose}>
      <div className="desktop-settings-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-row">
            <h2>Desktop Integration & Notifications</h2>
            <button className="close-btn" onClick={onClose} title="Close settings">
              ✕
            </button>
          </div>
          <p className="modal-subtitle">
            Configure proactive reach-outs, quiet hours, zero-storage telemetry, and review notification audits.
          </p>
        </div>

        {statusMsg && <div className="settings-banner success">{statusMsg}</div>}
        {errorMsg && <div className="settings-banner error">{errorMsg}</div>}

        {isLoading ? (
          <div className="settings-loading">Loading configuration...</div>
        ) : (
          <div className="settings-scroll-body">
            {/* 1. Proactive Reach-Out Master Switch */}
            <section className="settings-section">
              <div className="section-header-row">
                <div className="switch-text">
                  <h3>Proactive Reach-Outs</h3>
                  <p>Allow Aevum to autonomously initiate conversations when she thinks of you.</p>
                </div>
                <label className="toggle-switch">
                  <input
                    type="checkbox"
                    checked={proactiveEnabled}
                    onChange={(e) => setProactiveEnabled(e.target.checked)}
                  />
                  <span className="slider" />
                </label>
              </div>
            </section>

            {/* 2. Privacy & Idle Awareness Consent (Phase 8.3 Zero-Persistence) */}
            <section className="settings-section">
              <div className="section-header-row">
                <div className="switch-text">
                  <h3>Desktop Idle Awareness (Privacy-Gated)</h3>
                  <p>Check if you are active on your computer before dispatching notifications.</p>
                </div>
                <label className="toggle-switch">
                  <input
                    type="checkbox"
                    checked={idleAwarenessEnabled}
                    onChange={(e) => setIdleAwarenessEnabled(e.target.checked)}
                  />
                  <span className="slider" />
                </label>
              </div>

              <div className="privacy-callout">
                <strong>Zero-Persistence Guarantee (Phase 8.3):</strong> Telemetry heartbeats are processed exclusively in volatile memory to detect availability. Telemetry is never written to disk, never enters long-term memory, and expires automatically after 120 seconds. Disabling this switch immediately purges any transient context.
              </div>

              {idleAwarenessEnabled && (
                <div className="field-group" style={{ marginTop: "12px" }}>
                  <label>Idle Detection Threshold (seconds): {idleThreshold}s</label>
                  <input
                    type="range"
                    min="30"
                    max="1800"
                    step="30"
                    value={idleThreshold}
                    onChange={(e) => setIdleThreshold(Number(e.target.value))}
                  />
                  <span className="field-hint">Consider user idle after this many seconds of inactivity.</span>
                </div>
              )}
            </section>

            {/* 3. Schedule & Quiet Hours */}
            <section className="settings-section">
              <h3>Schedule & Quiet Hours</h3>
              <div className="form-grid">
                <div className="field-group">
                  <label>IANA Timezone</label>
                  <input
                    type="text"
                    value={timezone}
                    onChange={(e) => setTimezone(e.target.value)}
                    placeholder="e.g. Asia/Shanghai, America/New_York, UTC"
                  />
                  <span className="field-hint">Authoritative timezone for quiet hours evaluation.</span>
                </div>

                <div className="field-group">
                  <div className="switch-row-compact">
                    <label>Quiet Hours Filter</label>
                    <input
                      type="checkbox"
                      checked={quietHoursEnabled}
                      onChange={(e) => setQuietHoursEnabled(e.target.checked)}
                    />
                  </div>
                  <div className="time-range-row">
                    <input
                      type="time"
                      value={quietHoursStart}
                      disabled={!quietHoursEnabled}
                      onChange={(e) => setQuietHoursStart(e.target.value)}
                    />
                    <span>to</span>
                    <input
                      type="time"
                      value={quietHoursEnd}
                      disabled={!quietHoursEnabled}
                      onChange={(e) => setQuietHoursEnd(e.target.value)}
                    />
                  </div>
                  <span className="field-hint">Suppress reach-outs during your resting hours (supports midnight wrap).</span>
                </div>
              </div>
            </section>

            {/* 4. Pacing & Frequency Limits */}
            <section className="settings-section">
              <h3>Frequency Limits & Cooldown</h3>
              <div className="form-grid">
                <div className="field-group">
                  <label>Max Daily Reach-Outs: {maxDaily}</label>
                  <input
                    type="range"
                    min="1"
                    max="10"
                    value={maxDaily}
                    onChange={(e) => setMaxDaily(Number(e.target.value))}
                  />
                  <span className="field-hint">Hard ceiling on successful deliveries per calendar day.</span>
                </div>

                <div className="field-group">
                  <label>Minimum Cooldown: {minCooldown} min</label>
                  <input
                    type="range"
                    min="15"
                    max="720"
                    step="15"
                    value={minCooldown}
                    onChange={(e) => setMinCooldown(Number(e.target.value))}
                  />
                  <span className="field-hint">Minimum quiet time required between consecutive reach-outs.</span>
                </div>
              </div>
            </section>

            {/* 5. Quick Do-Not-Disturb (DND) */}
            <section className="settings-section">
              <h3>Do-Not-Disturb (DND)</h3>
              <p>Temporarily suppress all proactive reach-outs immediately.</p>
              <div className="dnd-status-row">
                <span className={`status-pill ${isDndActive ? "dnd-active" : "dnd-inactive"}`}>
                  {isDndActive
                    ? `Active until ${new Date(settings!.dnd_until!).toLocaleTimeString()}`
                    : "Inactive"}
                </span>
                <div className="dnd-btn-group">
                  <button className="dnd-btn" onClick={() => handleSetDND(60)}>
                    DND 1 Hour
                  </button>
                  <button className="dnd-btn" onClick={() => handleSetDND(240)}>
                    DND 4 Hours
                  </button>
                  {isDndActive && (
                    <button className="dnd-btn clear-btn" onClick={handleClearDND}>
                      Clear DND
                    </button>
                  )}
                </div>
              </div>
            </section>

            {/* Save Settings Action Button */}
            <div className="settings-action-bar">
              <button
                className="save-settings-btn"
                disabled={isSaving}
                onClick={handleSaveSettings}
              >
                {isSaving ? "Saving..." : "Save Settings"}
              </button>
            </div>

            {/* 6. Dual Notification Audit Trail (Standard 33) */}
            <section className="settings-section audit-section">
              <div className="audit-header-row">
                <h3>Notification Audit Trail</h3>
                <button className="refresh-audit-btn" onClick={loadData} title="Refresh audit log">
                  Refresh Log
                </button>
              </div>
              <p className="field-hint">Dual audit history tracking delivered items and suppressed candidates.</p>

              {history.length === 0 ? (
                <div className="audit-empty">No notification history recorded yet.</div>
              ) : (
                <div className="audit-table-wrapper">
                  <table className="audit-table">
                    <thead>
                      <tr>
                        <th>Time</th>
                        <th>Trigger</th>
                        <th>Status</th>
                        <th>Title & Body</th>
                        <th>Audit Reason</th>
                      </tr>
                    </thead>
                    <tbody>
                      {history.map((item) => (
                        <tr key={item.id} className={`row-status-${item.status.toLowerCase()}`}>
                          <td className="time-cell">
                            {new Date(item.created_at).toLocaleTimeString([], {
                              month: "numeric",
                              day: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </td>
                          <td>
                            <span className="trigger-badge">{item.trigger_type}</span>
                          </td>
                          <td>
                            <span className={`status-tag status-${item.status.toLowerCase()}`}>
                              {item.status}
                            </span>
                          </td>
                          <td className="content-cell">
                            <strong>{item.title}</strong>
                            <p>{item.body}</p>
                          </td>
                          <td className="reason-cell">
                            {item.suppression_reason ? (
                              <span className="suppression-reason">{item.suppression_reason}</span>
                            ) : item.delivered_at ? (
                              <span className="delivered-time">Delivered {new Date(item.delivered_at).toLocaleTimeString()}</span>
                            ) : item.claimed_by ? (
                              <span className="claimed-info">Lease: {item.claimed_by}</span>
                            ) : (
                              "—"
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </div>
        )}
      </div>
    </div>
  );
};
