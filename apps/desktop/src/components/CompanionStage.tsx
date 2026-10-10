/**
 * Companion Stage Component (Phase 13.4).
 *
 * The permanent center-stage visual embodiment for Aevum.
 * Houses the Live2D canvas, mood aura, and ambient life presence.
 *
 * Constitutional Invariants:
 * - Rule 19: Desktop UI is NOT the source of truth for character state. Pure presentation.
 * - Lock 1: Visual State != Canonical Reality (Presentation only, 0 DB mutations).
 * - Lock 4: Pure Visual Presentation Scope (Zero touch/hit mutation).
 */

import React, { useState } from "react";
import { CallMode, CharacterStateResponse, LifeResponse } from "../types";
import { LipSyncMouthState, VisualExpressionConfig, VisualMotionCommand } from "../visual/types";
import { Live2DCanvas } from "./Live2DCanvas";
import { Live2DModelModal } from "./Live2DModelModal";

export interface CompanionStageProps {
  characterName: string;
  characterState: CharacterStateResponse | null;
  life: LifeResponse | null;
  visualExpression: VisualExpressionConfig;
  visualMotion: VisualMotionCommand;
  lipSyncState: LipSyncMouthState;
  isBackendReady: boolean;
  isGenerating: boolean;
  isInCall: boolean;
  callMode: CallMode;
}

export const CompanionStage: React.FC<CompanionStageProps> = ({
  characterName,
  characterState,
  life,
  visualExpression,
  visualMotion,
  lipSyncState,
  isBackendReady,
  isGenerating,
  isInCall,
  callMode,
}) => {
  const [isModelModalOpen, setIsModelModalOpen] = useState(false);
  const mood = characterState?.mood || "NEUTRAL";
  const emotion = characterState?.emotion?.type || "NEUTRAL";
  const currentActivity = life?.current_activity || characterState?.current_activity || "Present with you";
  const currentLocation = life?.current_location || characterState?.current_location || "家中";

  return (
    <div className={`companion-stage-wrapper mood-${mood.toLowerCase()}`}>
      {/* Ambient Aura Background */}
      <div className={`stage-ambient-aura ${isGenerating ? "thinking" : isInCall ? "in-call" : "calm"}`} />

      {/* Stage Header Info Banner */}
      <div className="stage-presence-banner">
        <div className="presence-info">
          <span className={`presence-status-dot ${isBackendReady ? "online" : "offline"}`} />
          <span className="presence-name">{characterName}</span>
          <span className="presence-activity">· {currentActivity}</span>
          <span className="presence-location" style={{ marginLeft: "8px", opacity: 0.75, fontSize: "12px" }}>
            📍 {currentLocation}
          </span>
        </div>
        <div className="presence-chips" style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <button
            type="button"
            className="presence-model-btn"
            onClick={() => setIsModelModalOpen(true)}
            title="选择或导入伴侣形象与 Live2D 模型"
            style={{
              background: "linear-gradient(135deg, rgba(99, 102, 241, 0.45), rgba(139, 92, 246, 0.45))",
              border: "1px solid rgba(165, 180, 252, 0.4)",
              borderRadius: "14px",
              padding: "3px 10px",
              color: "#ffffff",
              fontSize: "12px",
              fontWeight: 500,
              cursor: "pointer",
              boxShadow: "0 2px 6px rgba(0, 0, 0, 0.2)",
              display: "flex",
              alignItems: "center",
              gap: "4px",
            }}
          >
            <span>🎨</span>
            <span>形象与Live2D</span>
          </button>
          <span className="presence-chip mood-chip">{mood}</span>
          <span className="presence-chip emotion-chip">{emotion}</span>
          {isInCall && <span className="presence-chip call-chip">VOICE CALL ({callMode})</span>}
        </div>
      </div>

      {/* Center Live2D Embodiment */}
      <div className="stage-canvas-container">
        <Live2DCanvas
          expression={visualExpression}
          motion={visualMotion}
          lipSyncState={lipSyncState}
          characterName={characterName}
          className="stage-live2d-canvas"
        />
      </div>

      {/* Live2D / Avatar Import Modal */}
      <Live2DModelModal
        isOpen={isModelModalOpen}
        onClose={() => setIsModelModalOpen(false)}
      />
    </div>
  );
};
