/**
 * Realtime Streaming Lip-Sync & Visual Embodiment Engine (Phase 13.5).
 *
 * Governed by ADR-024 (Revision 2) & Phase 13.5 Constitutional Constraints:
 * 1. RMS -> ParamMouthOpenY Unidirectional Mapping:
 *    - Web Audio RMS energy drives ParamMouthOpenY exclusively.
 *    - ParamMouthForm is strictly clamped at 0.0 (preserved for visemes).
 *    - Audio energy NEVER touches EmotionState, CharacterMood, or Reality.
 * 2. Instant Client-Local Barge-In Latch (P95 <= 20ms benchmark):
 *    - Clamps mouth_open_y to 0.0 instantaneously without server roundtrip.
 *    - Latches against generation_id, preventing stale audio from lifting latch.
 * 3. Playback / Microphone Isolation (13.2-LOCK-F):
 *    - Analyzes assistant playback audio stream only.
 *    - User microphone audio is strictly segregated and never routed to mouth analyzer.
 * 4. Stale/Late Generation Fencing:
 *    - Incoming audio packets with generation_id < activeGenerationId are dropped.
 *    - Stale packets NEVER trigger RMS calculation or open mouth.
 * 5. Rule 19 Zero Reverse State Mutation:
 *    - Pure presentation output: produces LipSyncMouthState only.
 *    - Zero state mutation tokens or database writes.
 */

import {
  calculateRMS,
  DEFAULT_LIPSYNC_CONFIG,
  LipSyncConfig,
  normalizeRMSToMouthOpen,
  smoothMouthOpen,
} from "./lipSyncAnalyzer";
import { LipSyncMouthState } from "./types";

export interface RealtimeLipSyncConfig extends LipSyncConfig {
  /** Maximum allowable audio lag window in milliseconds before decaying mouth */
  maxLagMs: number;
}

export const DEFAULT_REALTIME_LIPSYNC_CONFIG: RealtimeLipSyncConfig = {
  ...DEFAULT_LIPSYNC_CONFIG,
  maxLagMs: 80,
};

export class RealtimeLipSyncEngine {
  private config: RealtimeLipSyncConfig;
  private currentMouthOpen: number = 0.0;
  private isSpeaking: boolean = false;
  private activeGenerationId: number = 0;
  private latchedBargeInGeneration: number = -1;

  // Audio stream tracking
  private lastFrameProcessedTimestamp: number = 0;
  private audioContext: AudioContext | null = null;
  private playbackGainNode: GainNode | null = null;
  private connectedElement: HTMLAudioElement | null = null;

  constructor(config: Partial<RealtimeLipSyncConfig> = {}) {
    this.config = { ...DEFAULT_REALTIME_LIPSYNC_CONFIG, ...config };
  }

  /**
   * Updates the active generation counter from session manager or transport.
   * Any future frames with generation_id < activeGenerationId will be dropped.
   */
  public setGeneration(generationId: number): void {
    if (generationId > this.activeGenerationId) {
      this.activeGenerationId = generationId;
    }
  }

  /**
   * Triggers the Instant Client-Local Barge-In Latch (ADR-024 Lock 4).
   *
   * Target: P95 <= 20ms client-local latency without waiting for server roundtrip.
   * Immediately clamps mouth opening to 0.0 and latches current generation.
   */
  public triggerBargeIn(generationId?: number): LipSyncMouthState {
    const targetGen = generationId !== undefined ? generationId : this.activeGenerationId;
    this.latchedBargeInGeneration = targetGen;
    this.activeGenerationId = Math.max(this.activeGenerationId, targetGen);
    this.currentMouthOpen = 0.0;
    this.isSpeaking = false;

    // Instantly mute active playback audio element if attached
    if (this.connectedElement) {
      this.connectedElement.pause();
      this.connectedElement.currentTime = 0;
    }

    if (this.playbackGainNode) {
      this.playbackGainNode.gain.setValueAtTime(0, this.audioContext?.currentTime || 0);
    }

    return this.getCurrentMouthState();
  }

  /**
   * Resets the barge-in latch when a new generation stream officially begins.
   */
  public resetLatch(newGenerationId: number): void {
    this.activeGenerationId = newGenerationId;
    this.latchedBargeInGeneration = -1;
    this.currentMouthOpen = 0.0;
    this.isSpeaking = false;
  }

  /**
   * Connects the engine to an HTMLAudioElement for playback lip-sync.
   * Segregation: Strictly for companion playback, never connected to microphone stream.
   */
  public attachPlaybackElement(audioElement: HTMLAudioElement, generationId?: number): void {
    if (generationId !== undefined) {
      this.resetLatch(generationId);
    } else {
      this.latchedBargeInGeneration = -1;
    }
    this.connectedElement = audioElement;
    this.isSpeaking = true;
  }

  /**
   * Detaches active playback element and resets mouth to 0.0.
   */
  public detachPlaybackElement(): void {
    this.connectedElement = null;
    this.currentMouthOpen = 0.0;
    this.isSpeaking = false;
  }

  /**
   * Processes a raw PCM audio chunk or amplitude packet from the realtime stream.
   *
   * Enforces:
   * 1. Generation Fence: Drops frame if generation_id < activeGenerationId.
   * 2. Barge-in Fence: Drops frame if generation_id <= latchedBargeInGeneration.
   * 3. RMS -> ParamMouthOpenY mapping only (mouth_form strictly 0.0).
   *
   * @param samples Audio samples (float or integer PCM)
   * @param generationId The generation ID stamped on this audio frame envelope
   * @returns Current mouth state
   */
  public processStreamingAudioChunk(
    samples: Float32Array | number[],
    generationId: number
  ): LipSyncMouthState {
    // 1. Generation Fence Check (ADR-024 Lock 2)
    if (generationId < this.activeGenerationId) {
      // Stale generation audio frame - DROP without mutating mouth
      return this.getCurrentMouthState();
    }

    // 2. Barge-in Latch Check (ADR-024 Lock 4)
    if (generationId <= this.latchedBargeInGeneration) {
      // Latched generation - clamp mouth to 0.0
      this.currentMouthOpen = 0.0;
      this.isSpeaking = false;
      return this.getCurrentMouthState();
    }

    // Update active generation if advancing forward
    if (generationId > this.activeGenerationId) {
      this.activeGenerationId = generationId;
      this.latchedBargeInGeneration = -1;
    }

    // 3. Calculate RMS energy from incoming PCM chunk
    const rms = calculateRMS(samples);

    // 4. Normalize with noise gate and gain multiplier
    const targetOpen = normalizeRMSToMouthOpen(
      rms,
      this.config.noiseGateThreshold,
      this.config.gainMultiplier
    );

    // 5. Apply asymmetric smoothing filter (fast attack, smooth decay)
    this.currentMouthOpen = smoothMouthOpen(
      this.currentMouthOpen,
      targetOpen,
      this.config.attackRate,
      this.config.decayRate
    );

    this.isSpeaking = this.currentMouthOpen > 0.04;
    this.lastFrameProcessedTimestamp = Date.now();

    return this.getCurrentMouthState();
  }

  /**
   * Updates mouth state for animation frame loop (handles natural decay when speech pauses).
   */
  public updateFrame(): LipSyncMouthState {
    // If barge-in is latched, clamp to 0.0
    if (this.latchedBargeInGeneration >= this.activeGenerationId) {
      this.currentMouthOpen = 0.0;
      this.isSpeaking = false;
      return this.getCurrentMouthState();
    }

    // If no recent audio chunk (silence or stream paused), decay mouth to neutral
    const elapsedSinceAudio = Date.now() - this.lastFrameProcessedTimestamp;
    if (elapsedSinceAudio > this.config.maxLagMs) {
      this.currentMouthOpen = smoothMouthOpen(
        this.currentMouthOpen,
        0.0,
        this.config.attackRate,
        this.config.decayRate
      );
      if (this.currentMouthOpen < 0.01) {
        this.currentMouthOpen = 0.0;
      }
      this.isSpeaking = this.currentMouthOpen > 0.04;
    }

    return this.getCurrentMouthState();
  }

  /**
   * Returns current snapshot of mouth state.
   * Lock 1 & Lock 3: mouth_open_y in [0.0, 1.0], mouth_form strictly 0.0.
   * Zero reverse state mutation.
   */
  public getCurrentMouthState(): LipSyncMouthState {
    return {
      mouth_open_y: Math.max(0.0, Math.min(1.0, this.currentMouthOpen)),
      mouth_form: 0.0, // Strictly preserved for visemes
      is_speaking: this.isSpeaking && this.latchedBargeInGeneration < this.activeGenerationId,
    };
  }

  public getActiveGenerationId(): number {
    return this.activeGenerationId;
  }

  public isBargeInLatched(): boolean {
    return this.latchedBargeInGeneration >= this.activeGenerationId;
  }
}
