/**
 * Audio Amplitude Lip-Sync Engine (Phase 11.3).
 *
 * Governed by ADR-022:
 * - Lock 3: Audio-Driven Lip-Sync Without Epistemic Authority (Audio RMS -> ParamMouthOpenY only).
 * - ParamMouthForm is strictly untouched by amplitude (reserved for future viseme providers).
 * - Barge-in Latch: When barge-in occurs, mouth_open_y instantly clamps to 0.0 and stays
 *   latched until a new playback session explicitly starts.
 * - Decoupled: Does not alter Phase 10 TTS contracts, audio cache, or backend state machines.
 */

import { LipSyncMouthState } from "./types";

export interface LipSyncConfig {
  /** Minimum RMS threshold to register mouth opening (cuts off background hiss) */
  noiseGateThreshold: number;
  /** Multiplier scaling normalized RMS to Live2D [0.0, 1.0] range */
  gainMultiplier: number;
  /** Speed at which mouth opens when energy rises (higher = faster attack) */
  attackRate: number;
  /** Speed at which mouth closes when energy drops (lower = smoother trailing) */
  decayRate: number;
}

export const DEFAULT_LIPSYNC_CONFIG: LipSyncConfig = {
  noiseGateThreshold: 0.015,
  gainMultiplier: 3.8,
  attackRate: 0.65,
  decayRate: 0.28,
};

/**
 * Calculates Root Mean Square (RMS) volume from float audio sample buffer.
 */
export function calculateRMS(samples: ArrayLike<number>): number {
  if (samples.length === 0) return 0.0;
  let sum = 0.0;
  for (let i = 0; i < samples.length; i++) {
    sum += samples[i] * samples[i];
  }
  return Math.sqrt(sum / samples.length);
}

/**
 * Normalizes raw RMS value to target mouth opening ratio [0.0, 1.0] with noise gate.
 */
export function normalizeRMSToMouthOpen(
  rms: number,
  noiseGate: number = DEFAULT_LIPSYNC_CONFIG.noiseGateThreshold,
  gain: number = DEFAULT_LIPSYNC_CONFIG.gainMultiplier
): number {
  if (rms <= noiseGate) return 0.0;
  const signal = (rms - noiseGate) * gain;
  return Math.max(0.0, Math.min(1.0, signal));
}

/**
 * Applies asymmetrical attack/decay low-pass filter to smooth mouth opening across frames.
 */
export function smoothMouthOpen(
  current: number,
  target: number,
  attackRate: number = DEFAULT_LIPSYNC_CONFIG.attackRate,
  decayRate: number = DEFAULT_LIPSYNC_CONFIG.decayRate
): number {
  if (target > current) {
    return current + attackRate * (target - current);
  } else {
    return current + decayRate * (target - current);
  }
}

/**
 * Client-side audio analyzer driving real-time lip-sync mouth opening.
 */
export class LipSyncAnalyzer {
  private config: LipSyncConfig;
  private currentMouthOpen: number = 0.0;
  private isSpeaking: boolean = false;
  private bargeInLatched: boolean = false;

  private audioContext: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private sourceNode: MediaElementAudioSourceNode | null = null;
  private sampleBuffer: Float32Array | null = null;
  private connectedElement: HTMLAudioElement | null = null;

  constructor(config: Partial<LipSyncConfig> = {}) {
    this.config = { ...DEFAULT_LIPSYNC_CONFIG, ...config };
  }

  /**
   * Connects the analyzer to an HTMLAudioElement.
   */
  public attachAudioElement(audioElement: HTMLAudioElement): void {
    this.bargeInLatched = false; // Unlatch for newly attached audio
    this.isSpeaking = true;
    this.connectedElement = audioElement;

    try {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!AudioCtx) return;

      if (!this.audioContext || this.audioContext.state === "closed") {
        this.audioContext = new AudioCtx();
      }

      if (this.audioContext.state === "suspended") {
        this.audioContext.resume().catch(() => {});
      }

      if (!this.analyser) {
        this.analyser = this.audioContext.createAnalyser();
        this.analyser.fftSize = 512;
        this.sampleBuffer = new Float32Array(this.analyser.fftSize);
      }

      // Avoid creating multiple source nodes for the same element
      if (!this.sourceNode) {
        this.sourceNode = this.audioContext.createMediaElementSource(audioElement);
        this.sourceNode.connect(this.analyser);
        this.analyser.connect(this.audioContext.destination);
      }
    } catch (err) {
      console.warn("LipSyncAnalyzer: Web Audio connection notice:", err);
    }
  }

  /**
   * Detaches the active audio element and safely releases streaming state.
   */
  public detachAudioElement(): void {
    this.connectedElement = null;
    this.isSpeaking = false;
    this.currentMouthOpen = 0.0;
  }

  /**
   * Triggers the Barge-in Immediate-Zero Latch (ADR-022 Lock 3).
   *
   * Clamps mouth opening instantly to 0.0 and latches until new audio is explicitly started.
   */
  public triggerBargeIn(): LipSyncMouthState {
    this.bargeInLatched = true;
    this.isSpeaking = false;
    this.currentMouthOpen = 0.0;
    return this.getCurrentMouthState();
  }

  /**
   * Resets the latch when a new assistant audio playback turn begins.
   */
  public resetLatch(): void {
    this.bargeInLatched = false;
  }

  /**
   * Updates and returns the current mouth state for the current animation frame.
   */
  public updateFrame(): LipSyncMouthState {
    // 1. If barge-in is latched, enforce zero opening immediately
    if (this.bargeInLatched) {
      this.currentMouthOpen = 0.0;
      this.isSpeaking = false;
      return this.getCurrentMouthState();
    }

    // 2. If no audio element is actively playing, decay mouth to rest
    if (!this.connectedElement || this.connectedElement.paused || this.connectedElement.ended) {
      this.isSpeaking = false;
      this.currentMouthOpen = smoothMouthOpen(this.currentMouthOpen, 0.0, this.config.attackRate, this.config.decayRate);
      if (this.currentMouthOpen < 0.01) {
        this.currentMouthOpen = 0.0;
      }
      return this.getCurrentMouthState();
    }

    // 3. Extract time-domain samples and compute RMS
    if (this.analyser && this.sampleBuffer) {
      this.analyser.getFloatTimeDomainData(this.sampleBuffer as any);
      const rms = calculateRMS(this.sampleBuffer);
      const targetOpen = normalizeRMSToMouthOpen(
        rms,
        this.config.noiseGateThreshold,
        this.config.gainMultiplier
      );
      this.currentMouthOpen = smoothMouthOpen(
        this.currentMouthOpen,
        targetOpen,
        this.config.attackRate,
        this.config.decayRate
      );
      this.isSpeaking = this.currentMouthOpen > 0.05;
    }

    return this.getCurrentMouthState();
  }

  /**
   * Returns current snapshot of mouth state.
   * Lock 3: mouth_form is strictly untouched (0.0).
   */
  public getCurrentMouthState(): LipSyncMouthState {
    return {
      mouth_open_y: Math.max(0.0, Math.min(1.0, this.currentMouthOpen)),
      mouth_form: 0.0,
      is_speaking: this.isSpeaking && !this.bargeInLatched,
    };
  }

  /**
   * Pure simulation step for testing or offline calculation.
   */
  public stepSimulation(rmsInput: number): LipSyncMouthState {
    if (this.bargeInLatched) {
      this.currentMouthOpen = 0.0;
      this.isSpeaking = false;
      return this.getCurrentMouthState();
    }

    const targetOpen = normalizeRMSToMouthOpen(
      rmsInput,
      this.config.noiseGateThreshold,
      this.config.gainMultiplier
    );
    this.currentMouthOpen = smoothMouthOpen(
      this.currentMouthOpen,
      targetOpen,
      this.config.attackRate,
      this.config.decayRate
    );
    this.isSpeaking = this.currentMouthOpen > 0.05;

    return this.getCurrentMouthState();
  }
}
