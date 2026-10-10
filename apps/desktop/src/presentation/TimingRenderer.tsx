/**
 * Presentation Track — Timing Renderer
 * 
 * Thin visual timing container orchestrating bubble cadence, typing indicator,
 * and sequential appearance without altering message substance.
 */

import React, { useEffect, useState } from "react";
import { PresentationEnvelope } from "./contracts";
import { EnvelopeRenderer } from "./MessageRenderer";

interface TimingRendererProps {
  envelope: PresentationEnvelope;
  simulateTiming?: boolean;
}

/**
 * TimingRenderer:
 * Thin presentation container executing explicit upstream timing configurations.
 * 
 * Strict Boundaries:
 * - Pure execution of explicit timing configurations; zero emotional or cognitive inference.
 * - Bubble count and text length do NOT automatically imply delays.
 * - When timing is unspecified or <= 0, bubbles render immediately without artificial delays.
 */
export const TimingRenderer: React.FC<TimingRendererProps> = ({
  envelope,
  simulateTiming = true,
}) => {
  // Explicitly check configured delay; if not specified or <= 0, delay is 0 (immediate).
  const configuredDelay =
    envelope.bubbles[0]?.inter_bubble_delay_ms ??
    envelope.timing?.default_inter_bubble_ms ??
    0;

  const shouldAnimate =
    simulateTiming && envelope.bubbles.length > 1 && configuredDelay > 0;

  const [revealedCount, setRevealedCount] = useState<number>(
    shouldAnimate ? 1 : envelope.bubbles.length
  );
  const [isTypingNext, setIsTypingNext] = useState<boolean>(shouldAnimate);

  useEffect(() => {
    if (!shouldAnimate) {
      setRevealedCount(envelope.bubbles.length);
      setIsTypingNext(false);
      return;
    }

    setRevealedCount(1);
    setIsTypingNext(true);

    const timer = setTimeout(() => {
      setRevealedCount(envelope.bubbles.length);
      setIsTypingNext(false);
    }, configuredDelay);

    return () => clearTimeout(timer);
  }, [envelope, simulateTiming, shouldAnimate, configuredDelay]);

  return (
    <div className="timing-renderer-root">
      <EnvelopeRenderer
        envelope={envelope}
        revealedCount={revealedCount}
      />
      {isTypingNext && (
        <div style={{ marginTop: "6px" }}>
          <div className="presentation-typing-indicator">
            <span className="typing-dot" />
            <span className="typing-dot" />
            <span className="typing-dot" />
          </div>
        </div>
      )}
    </div>
  );
};
