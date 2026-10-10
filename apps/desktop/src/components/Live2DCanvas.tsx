/**
 * Live2D Desktop Companion Canvas Component (Phase 11.4).
 *
 * Governed by ADR-022:
 * - Lock 1: Visual State != Canonical Reality (Presentation only, 0 DB mutations).
 * - Lock 2: Unidirectional Affective Visual Mapping (Consumes render instructions).
 * - Lock 3: Audio-Driven Lip-Sync Without Epistemic Authority (Mouth movement).
 * - Lock 4: Pure Visual Presentation Scope (Zero hit-testing / touch interaction).
 * - Lock 5: Fail-Closed & Graceful Visual Degradability (Fallback avatar on WebGL failure).
 * - Lock 7: Renderer State != Character State (Renderer state stays in component).
 */

import React, { useEffect, useRef, useState } from "react";
import { CubismRendererManager } from "../visual/cubismManager";
import { GazeTracker } from "../visual/gazeTracker";
import {
  GazeParameters,
  LipSyncMouthState,
  RendererState,
  VisualExpressionConfig,
  VisualMotionCommand,
} from "../visual/types";

interface Live2DCanvasProps {
  expression?: VisualExpressionConfig;
  motion?: VisualMotionCommand;
  lipSyncState?: LipSyncMouthState;
  gazeParams?: GazeParameters;
  enableGazeTracking?: boolean;
  onRendererStateChange?: (state: RendererState) => void;
  className?: string;
  characterName?: string;
}

export const Live2DCanvas: React.FC<Live2DCanvasProps> = ({
  expression,
  motion,
  lipSyncState,
  gazeParams,
  enableGazeTracking = true,
  onRendererStateChange,
  className = "",
  characterName = "Aevum",
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const managerRef = useRef<CubismRendererManager | null>(null);
  const gazeTrackerRef = useRef<GazeTracker | null>(null);
  const [rendererState, setRendererState] = useState<RendererState>("uninitialized");
  const getEffectiveAvatar = () => {
    const isTextureAtlas = (url: string) => {
      const lower = url.toLowerCase();
      return lower.includes("texture_") || lower.includes("/textures/") || lower.includes("\\textures\\");
    };

    const avatar = localStorage.getItem("aevum_custom_avatar_url");
    if (avatar) {
      if (isTextureAtlas(avatar)) {
        try {
          localStorage.removeItem("aevum_custom_avatar_url");
        } catch {
          // ignore
        }
      } else {
        return avatar;
      }
    }
    const live2d = localStorage.getItem("aevum_custom_live2d_url");
    if (
      live2d &&
      !isTextureAtlas(live2d) &&
      (/\.(png|jpe?g|webp|gif|svg)($|\?)/i.test(live2d) || live2d.startsWith("data:image/"))
    ) {
      return live2d;
    }
    return "";
  };

  const [customAvatarUrl, setCustomAvatarUrl] = useState<string>(getEffectiveAvatar);
  const [currentZoom, setCurrentZoom] = useState<number>(1.0);
  const [reactionEffect, setReactionEffect] = useState<{ id: number; symbol: string } | null>(null);

  const isDraggingRef = useRef<boolean>(false);
  const dragStartRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const dragDistanceRef = useRef<number>(0);

  const showReactionEffect = (symbol?: string) => {
    const emojis = ["💖", "✨", "🌸", "⭐", "🥰"];
    const chosen = symbol || emojis[Math.floor(Math.random() * emojis.length)];
    setReactionEffect({ id: Date.now(), symbol: chosen });
    setTimeout(() => {
      setReactionEffect(null);
    }, 1200);
  };

  const handleWheel = (e: React.WheelEvent) => {
    if (rendererState !== "ready" || !managerRef.current) return;
    const delta = e.deltaY < 0 ? 0.08 : -0.08;
    const newZoom = managerRef.current.zoomBy(delta);
    setCurrentZoom(newZoom);
  };

  const handlePointerDown = (e: React.PointerEvent) => {
    if (rendererState !== "ready" || !managerRef.current) return;
    isDraggingRef.current = true;
    dragStartRef.current = { x: e.clientX, y: e.clientY };
    dragDistanceRef.current = 0;
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    if (!isDraggingRef.current || !managerRef.current) return;
    const dx = e.clientX - dragStartRef.current.x;
    const dy = e.clientY - dragStartRef.current.y;
    dragStartRef.current = { x: e.clientX, y: e.clientY };
    dragDistanceRef.current += Math.hypot(dx, dy);
    managerRef.current.panBy(dx, dy);
  };

  const lastReactionTimeRef = useRef<number>(0);
  const triggerReaction = () => {
    const now = Date.now();
    if (now - lastReactionTimeRef.current < 350) return;
    lastReactionTimeRef.current = now;
    if (managerRef.current && rendererState === "ready") {
      const reactionExpr = managerRef.current.triggerInteractiveReaction();
      if (reactionExpr) {
        showReactionEffect();
      }
    } else {
      showReactionEffect();
    }
  };

  const handlePointerUp = (e: React.PointerEvent) => {
    if (!isDraggingRef.current) return;
    isDraggingRef.current = false;
    try {
      (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
    } catch {
      // ignore
    }
    // Interactive click / tap reaction (sub-threshold movement: under 20px)
    if (dragDistanceRef.current < 20) {
      triggerReaction();
    }
  };

  useEffect(() => {
    const handleStorage = () => {
      setCustomAvatarUrl(getEffectiveAvatar());
    };
    handleStorage();
    window.addEventListener("storage", handleStorage);
    window.addEventListener("aevum-avatar-updated", handleStorage);
    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener("aevum-avatar-updated", handleStorage);
    };
  }, []);

  // Initialize renderer manager and decoupled gaze tracking on mount
  useEffect(() => {
    const manager = new CubismRendererManager((newState) => {
      setRendererState(newState);
      if (onRendererStateChange) {
        onRendererStateChange(newState);
      }
    });
    managerRef.current = manager;

    if (enableGazeTracking) {
      const tracker = new GazeTracker();
      tracker.attach();
      gazeTrackerRef.current = tracker;
      manager.attachGazeTracker(tracker);
    }

    if (canvasRef.current) {
      const live2dUrl = localStorage.getItem("aevum_custom_live2d_url");
      const visualMode = localStorage.getItem("aevum_visual_mode") || "live2d";
      const modelToLoad =
        visualMode === "live2d" && live2dUrl && (live2dUrl.includes(".json") || live2dUrl.startsWith("http"))
          ? live2dUrl
          : undefined;

      manager.initialize(canvasRef.current, modelToLoad).catch((err) => {
        console.warn("Live2DCanvas initialize caught error:", err);
      });
    }

    const handleDynamicModelReload = async () => {
      const live2dUrl = localStorage.getItem("aevum_custom_live2d_url");
      const visualMode = localStorage.getItem("aevum_visual_mode");
      if (
        managerRef.current &&
        visualMode === "live2d" &&
        live2dUrl &&
        (live2dUrl.includes(".json") || live2dUrl.startsWith("http"))
      ) {
        await managerRef.current.loadModel(live2dUrl);
      } else if (managerRef.current && visualMode === "image") {
        managerRef.current.clearModel();
        setRendererState("degraded_fallback");
      }
    };
    window.addEventListener("aevum-avatar-updated", handleDynamicModelReload);

    return () => {
      window.removeEventListener("aevum-avatar-updated", handleDynamicModelReload);
      if (gazeTrackerRef.current) {
        gazeTrackerRef.current.detach();
        gazeTrackerRef.current = null;
      }
      manager.dispose();
      managerRef.current = null;
    };
  }, [enableGazeTracking, onRendererStateChange]);

  // Update expression render instruction
  useEffect(() => {
    if (expression && managerRef.current) {
      managerRef.current.setExpression(expression);
    }
  }, [expression]);

  // Update motion command
  useEffect(() => {
    if (motion && managerRef.current) {
      managerRef.current.setMotion(motion);
    }
  }, [motion]);

  // Update lip-sync mouth state
  useEffect(() => {
    if (lipSyncState && managerRef.current) {
      managerRef.current.setLipSync(lipSyncState);
    }
  }, [lipSyncState]);

  // Update gaze tracking
  useEffect(() => {
    if (gazeParams && managerRef.current) {
      managerRef.current.setGaze(gazeParams);
    }
  }, [gazeParams]);

  const activeExpr = expression?.expression || "neutral";
  const isSpeaking = lipSyncState?.is_speaking || false;

  return (
    <div
      className={`live2d-stage-container ${className}`}
      onWheel={handleWheel}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={() => {
        isDraggingRef.current = false;
      }}
      onClick={() => {
        if (dragDistanceRef.current < 25) {
          triggerReaction();
        }
      }}
      style={{
        touchAction: "none",
        cursor: rendererState === "ready" ? "grab" : "default",
      }}
    >
      {/* 1. WebGL Live2D Canvas with HiDPI Buffer */}
      <canvas
        ref={canvasRef}
        className={`live2d-webgl-canvas ${rendererState === "ready" ? "visible" : "hidden"}`}
        width={800}
        height={1000}
      />

      {/* Floating Zoom and Pan Controls */}
      {rendererState === "ready" && (
        <div
          className="live2d-stage-controls"
          onPointerDown={(e) => e.stopPropagation()}
          onWheel={(e) => e.stopPropagation()}
        >
          <button
            type="button"
            className="live2d-control-btn"
            title="缩小 (鼠标滚轮向下)"
            onClick={() => {
              if (managerRef.current) {
                const z = managerRef.current.zoomBy(-0.15);
                setCurrentZoom(z);
              }
            }}
          >
            －
          </button>
          <button
            type="button"
            className="live2d-control-btn zoom-indicator"
            title="点击重置缩放与视角"
            onClick={() => {
              if (managerRef.current) {
                managerRef.current.resetTransform();
                setCurrentZoom(1.0);
              }
            }}
          >
            {Math.round(currentZoom * 100)}%
          </button>
          <button
            type="button"
            className="live2d-control-btn"
            title="放大 (鼠标滚轮向上)"
            onClick={() => {
              if (managerRef.current) {
                const z = managerRef.current.zoomBy(0.15);
                setCurrentZoom(z);
              }
            }}
          >
            ＋
          </button>
          <button
            type="button"
            className="live2d-control-btn reset-btn"
            title="复位视角与位置"
            onClick={() => {
              if (managerRef.current) {
                managerRef.current.resetTransform();
                setCurrentZoom(1.0);
              }
            }}
          >
            ↺
          </button>
        </div>
      )}

      {/* Interactive Cute Reaction Particle / Emote Feedback */}
      {reactionEffect && (
        <div key={reactionEffect.id} className="live2d-reaction-particle">
          {reactionEffect.symbol}
        </div>
      )}

      {/* 2. Lock 5: Fail-Closed & Graceful Visual Degradability Container */}
      {(rendererState === "degraded_fallback" || rendererState === "uninitialized") && (
        <div className="live2d-fallback-card">
          <div className={`fallback-avatar-wrapper ${isSpeaking ? "speaking-pulse" : "ambient-pulse"}`}>
            <div
              className="fallback-avatar-circle"
              style={{ overflow: "hidden", cursor: "pointer" }}
              onClick={(e) => {
                e.stopPropagation();
                triggerReaction();
              }}
              title="点击抚摸伴侣"
            >
              {customAvatarUrl ? (
                <img
                  src={customAvatarUrl}
                  alt={characterName}
                  className="fallback-avatar-image"
                  style={{
                    width: "100%",
                    height: "100%",
                    objectFit: "cover",
                    borderRadius: "50%",
                  }}
                />
              ) : (
                <span className="fallback-avatar-initial">{characterName.charAt(0)}</span>
              )}
              {isSpeaking && (
                <div className="speaking-soundwave-indicator">
                  <span className="wave-bar bar-1"></span>
                  <span className="wave-bar bar-2"></span>
                  <span className="wave-bar bar-3"></span>
                </div>
              )}
            </div>
          </div>
          <div className="fallback-character-meta">
            <span className="fallback-name">{characterName}</span>
            <div className="fallback-badges">
              <span className="fallback-expression-badge">{activeExpr}</span>
              {motion && <span className="fallback-motion-badge">{motion.archetype}</span>}
            </div>
            <span className="fallback-mode-hint">
              {customAvatarUrl ? "自定义专属伴侣立绘 (Active Custom Portrait)" : "Visual presentation mode (degraded fallback)"}
            </span>
          </div>
        </div>
      )}

      {/* 3. Loading placeholder */}
      {rendererState === "loading" && (
        <div className="live2d-loading-card">
          <div className="loading-spinner"></div>
          <span className="loading-text">Loading avatar...</span>
        </div>
      )}
    </div>
  );
};
