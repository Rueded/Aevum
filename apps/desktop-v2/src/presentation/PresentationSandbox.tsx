/**
 * Presentation Track — Interactive Presentation Sandbox
 * 
 * Lightweight standalone developer testbench allowing instant preview and inspection
 * of handcrafted Cases A through G without touching the core dialogue pipeline.
 */

import React, { useState } from "react";
import { PRESENTATION_FIXTURES } from "./fixtures";
import { TimingRenderer } from "./TimingRenderer";
import "./presentation.css";

export const PresentationSandbox: React.FC<{ onClose?: () => void }> = ({ onClose }) => {
  const caseKeys = Object.keys(PRESENTATION_FIXTURES);
  const [selectedKey, setSelectedKey] = useState<string>(caseKeys[0]);
  const [simulateTiming, setSimulateTiming] = useState<boolean>(true);
  const [replayCount, setReplayCount] = useState<number>(0);

  const activeEnvelope = PRESENTATION_FIXTURES[selectedKey];

  return (
    <div className="presentation-sandbox-container">
      <div className="sandbox-header">
        <div>
          <h3 style={{ margin: 0, fontSize: "1.05rem", color: "#f8fafc" }}>
            Presentation Track — Rendering Sandbox
          </h3>
          <p style={{ margin: "4px 0 0", fontSize: "0.75rem", color: "#94a3b8" }}>
            Verifying that multi-dimensional expressive resources (Kaomoji, Emojis, Multi-bubbles, Silence)
            are preserved rather than flattened into a single text string.
          </p>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            style={{
              background: "transparent",
              border: "none",
              color: "#94a3b8",
              cursor: "pointer",
              fontSize: "1.1rem",
            }}
          >
            ✕
          </button>
        )}
      </div>

      {/* Case Selector Tabs */}
      <div className="sandbox-nav-chips">
        {caseKeys.map((k) => {
          const item = PRESENTATION_FIXTURES[k];
          return (
            <button
              key={k}
              className={`sandbox-chip-btn ${selectedKey === k ? "active" : ""}`}
              onClick={() => {
                setSelectedKey(k);
                setReplayCount((c) => c + 1);
              }}
            >
              {item.case_name}
            </button>
          );
        })}
      </div>

      {/* Description & Controls */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ fontSize: "0.82rem", color: "#cbd5e1" }}>
          <strong>Scenario:</strong> {activeEnvelope.description}
        </div>
        <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
          <label style={{ fontSize: "0.75rem", color: "#94a3b8", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={simulateTiming}
              onChange={(e) => setSimulateTiming(e.target.checked)}
              style={{ marginRight: "4px" }}
            />
            Simulate Cadence
          </label>
          <button
            className="sandbox-chip-btn"
            style={{ padding: "3px 8px", fontSize: "0.72rem" }}
            onClick={() => setReplayCount((c) => c + 1)}
          >
            ↻ Replay Cadence
          </button>
        </div>
      </div>

      {/* Live Rendered Companion Stage */}
      <div className="sandbox-stage">
        <div className="message-row companion-row" style={{ width: "100%" }}>
          <div className="bubble-avatar">A</div>
          <div style={{ flex: 1 }}>
            <div className="message-header-small" style={{ marginBottom: "4px" }}>
              <span className="sender-name">Aevum</span>
              <span className="timestamp" style={{ marginLeft: "8px" }}>
                Visual Density: {activeEnvelope.visual_density || "normal"} | State: {activeEnvelope.manifestation_state}
              </span>
            </div>
            <TimingRenderer
              key={`${selectedKey}_${replayCount}`}
              envelope={activeEnvelope}
              simulateTiming={simulateTiming}
            />
          </div>
        </div>
      </div>

      {/* Raw Presentation Contract JSON Inspection */}
      <details style={{ marginTop: "4px" }}>
        <summary
          style={{
            fontSize: "0.75rem",
            color: "#94a3b8",
            cursor: "pointer",
            userSelect: "none",
          }}
        >
          View Underlying Presentation Contract DTO (JSON)
        </summary>
        <pre
          style={{
            fontSize: "0.72rem",
            background: "rgba(0,0,0,0.4)",
            padding: "10px",
            borderRadius: "6px",
            overflowX: "auto",
            marginTop: "6px",
            color: "#38bdf8",
          }}
        >
          {JSON.stringify(activeEnvelope, null, 2)}
        </pre>
      </details>

      <div className="sandbox-meta-row">
        <span>Layer: Manifestation / Presentation Track</span>
        <span>Aevum Core State: 100% Decoupled & Untouched</span>
      </div>
    </div>
  );
};
