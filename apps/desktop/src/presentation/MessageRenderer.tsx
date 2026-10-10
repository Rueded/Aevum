/**
 * Presentation Track — Message Renderer
 * 
 * Thin visual component mapping PresentationEnvelope and PresentationBubble segments
 * (TEXT, KAOMOJI, EMOJI, STICKER, etc.) to structured DOM elements.
 * 
 * Constitutional Guard:
 * Zero cognitive logic, zero state mutations, zero LLM prompts.
 */

import React from "react";
import {
  BubbleSegment,
  PresentationBubble,
  PresentationEnvelope,
} from "./contracts";
import "./presentation.css";

export const SegmentRenderer: React.FC<{ segment: BubbleSegment }> = ({ segment }) => {
  switch (segment.kind) {
    case "KAOMOJI":
      return (
        <span
          className="paralinguistic-kaomoji"
          title={segment.metadata?.alt_text || segment.metadata?.kaomoji_mood || "kaomoji"}
        >
          {segment.raw}
        </span>
      );

    case "EMOJI":
      return (
        <span
          className="paralinguistic-emoji"
          title={segment.metadata?.alt_text || "emoji"}
        >
          {segment.raw}
        </span>
      );

    case "STICKER":
      return (
        <div className="presentation-sticker" title={segment.metadata?.alt_text || "sticker"}>
          <div className="sticker-placeholder-icon">🍵</div>
          <div className="sticker-caption">{segment.raw}</div>
        </div>
      );

    case "TEXT":
    default:
      return <span>{segment.raw}</span>;
  }
};

export const BubbleRenderer: React.FC<{ bubble: PresentationBubble }> = ({ bubble }) => {
  const isCompact = bubble.density === "compact";

  return (
    <div
      className={`message-bubble companion-bubble ${
        isCompact ? "minimal-expansion-bubble compact-bubble" : ""
      }`}
    >
      <div className="bubble-text">
        {bubble.segments.map((seg, idx) => (
          <SegmentRenderer key={idx} segment={seg} />
        ))}
        {isCompact && <span className="minimal-expansion-tag">compact</span>}
      </div>
    </div>
  );
};

export const EnvelopeRenderer: React.FC<{
  envelope: PresentationEnvelope;
  revealedCount?: number;
}> = ({ envelope, revealedCount }) => {
  // Case G: Pure Design Preview for Future Zero-Message Manifestation
  if (envelope.manifestation_state === "NO_MESSAGE_DESIGN_PREVIEW") {
    return (
      <div className="silence-presentation-card">
        <span className="silence-icon">✦</span>
        <div className="silence-meta">
          <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "3px" }}>
            <span className="silence-badge">[设计预览] NO_MESSAGE_DESIGN_PREVIEW</span>
          </div>
          <span className="silence-title">（静默未言 · 留白）</span>
          <span className="silence-desc">
            此卡片仅展示未来可能的无消息表现样式。它不是实际的 assistant 消息，当前通信接口仍需返回消息，本卡片亦不能作为真正 NO_MESSAGE 已实现的证据。
          </span>
        </div>
      </div>
    );
  }

  const count =
    revealedCount !== undefined ? revealedCount : envelope.bubbles.length;
  const visibleBubbles = envelope.bubbles.slice(0, count);

  return (
    <div className="presentation-bubbles-flow">
      {visibleBubbles.map((b) => (
        <div key={b.id} className="presentation-bubble-item">
          <BubbleRenderer bubble={b} />
        </div>
      ))}
    </div>
  );
};
