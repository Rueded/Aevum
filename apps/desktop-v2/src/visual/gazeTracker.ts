/**
 * Gaze Tracking Subsystem (Phase 11.5).
 *
 * Governed by ADR-022:
 * - Lock 1: Visual State != Canonical Reality (Presentation only, zero DB mutations).
 * - Lock 4: Pure Visual Presentation Scope (Mouse tracking -> Gaze parameters).
 * - Lock 7: Renderer State != Character State:
 *   - Micro-saccades and Focus Release are strictly internal renderer presentation behaviors.
 *   - Focus Release is visual re-centering, NOT character "loss of interest/attention" psychological fact.
 * - Performance: Operates decoupled from React renders; updates directly in animation loop.
 */

import { GazeParameters, GazeTarget } from "./types";

export interface GazeTrackerConfig {
  /** Maximum head turn angle around X axis (nod up/down) */
  maxAngleX: number;
  /** Maximum head turn angle around Y axis (look left/right) */
  maxAngleY: number;
  /** Maximum head tilt roll around Z axis */
  maxAngleZ: number;
  /** Maximum eyeball displacement ratio */
  maxEyeBall: number;
  /** Smoothing rate for head and eye interpolation (0.01 = very slow, 1.0 = instant) */
  smoothingRate: number;
  /** Saccade (eye-dart) interval mean in milliseconds */
  saccadeIntervalMs: number;
  /** Saccade displacement amplitude */
  saccadeAmplitude: number;
}

export const DEFAULT_GAZE_CONFIG: GazeTrackerConfig = {
  maxAngleX: 20.0,
  maxAngleY: 15.0,
  maxAngleZ: 8.0,
  maxEyeBall: 0.85,
  smoothingRate: 0.12,
  saccadeIntervalMs: 2800,
  saccadeAmplitude: 0.06,
};

export class GazeTracker {
  private config: GazeTrackerConfig;
  private currentTarget: GazeTarget = { x: 0.0, y: 0.0, is_tracked: false };

  // Current interpolated presentation parameters (Renderer State)
  private currentParams: GazeParameters = {
    eyeball_x: 0.0,
    eyeball_y: 0.0,
    angle_x: 0.0,
    angle_y: 0.0,
    angle_z: 0.0,
  };

  // Internal micro-saccade renderer state
  private saccadeTimerMs: number = 0;
  private currentSaccadeOffset: { x: number; y: number } = { x: 0.0, y: 0.0 };

  private isListening: boolean = false;
  private targetElement: HTMLElement | Window | null = null;

  constructor(config: Partial<GazeTrackerConfig> = {}) {
    this.config = { ...DEFAULT_GAZE_CONFIG, ...config };
  }

  /**
   * Binds global or container pointer events without triggering React re-renders.
   */
  public attach(container?: HTMLElement): void {
    if (this.isListening) return;

    this.targetElement = container || (typeof window !== "undefined" ? window : null);
    if (!this.targetElement) return;

    this.targetElement.addEventListener("pointermove", this.handlePointerMove as EventListener);
    this.targetElement.addEventListener("pointerleave", this.handlePointerLeave as EventListener);

    if (typeof window !== "undefined") {
      window.addEventListener("blur", this.handlePointerLeave as EventListener);
    }

    this.isListening = true;
  }

  /**
   * Unbinds pointer listeners.
   */
  public detach(): void {
    if (!this.isListening || !this.targetElement) return;

    this.targetElement.removeEventListener("pointermove", this.handlePointerMove as EventListener);
    this.targetElement.removeEventListener("pointerleave", this.handlePointerLeave as EventListener);

    if (typeof window !== "undefined") {
      window.removeEventListener("blur", this.handlePointerLeave as EventListener);
    }

    this.isListening = false;
    this.targetElement = null;
    this.handlePointerLeave();
  }

  private handlePointerMove = (e: PointerEvent): void => {
    if (typeof window === "undefined") return;

    const width = window.innerWidth || 1;
    const height = window.innerHeight || 1;

    // Normalize coordinates relative to window center: [-1.0, 1.0]
    const normX = Math.max(-1.0, Math.min(1.0, (e.clientX - width / 2) / (width / 2)));
    const normY = Math.max(-1.0, Math.min(1.0, (e.clientY - height / 2) / (height / 2)));

    this.currentTarget = {
      x: normX,
      y: normY,
      is_tracked: true,
    };
  };

  /**
   * Focus Release: Clamps target to neutral forward pose (0.0, 0.0).
   * Note: This is pure visual re-centering, NOT character loss-of-interest.
   */
  private handlePointerLeave = (): void => {
    this.currentTarget = {
      x: 0.0,
      y: 0.0,
      is_tracked: false,
    };
  };

  /**
   * Updates gaze parameters on animation frame.
   * Lock 7: Saccades and smoothing are internal Renderer State.
   */
  public update(deltaMs: number): GazeParameters {
    // 1. Advance micro-saccade behavior
    this.saccadeTimerMs += deltaMs;
    if (this.saccadeTimerMs > this.config.saccadeIntervalMs) {
      this.saccadeTimerMs = 0;
      // Small random saccadic twitch when observing
      const angle = Math.random() * Math.PI * 2;
      const mag = (Math.random() * 0.5 + 0.5) * this.config.saccadeAmplitude;
      this.currentSaccadeOffset = {
        x: Math.cos(angle) * mag,
        y: Math.sin(angle) * mag,
      };
    }

    // 2. Compute target raw parameter positions
    const targetEyeballX = Math.max(
      -1.0,
      Math.min(1.0, this.currentTarget.x * this.config.maxEyeBall + this.currentSaccadeOffset.x)
    );
    const targetEyeballY = Math.max(
      -1.0,
      Math.min(1.0, -this.currentTarget.y * this.config.maxEyeBall + this.currentSaccadeOffset.y)
    );

    // Live2D head angles: angle_x (yaw), angle_y (pitch), angle_z (roll)
    const targetAngleX = Math.max(
      -30.0,
      Math.min(30.0, this.currentTarget.x * this.config.maxAngleX)
    );
    const targetAngleY = Math.max(
      -30.0,
      Math.min(30.0, -this.currentTarget.y * this.config.maxAngleY)
    );
    const targetAngleZ = Math.max(
      -30.0,
      Math.min(30.0, this.currentTarget.x * -this.config.maxAngleZ)
    );

    // 3. Smooth exponential interpolation toward targets (damping)
    const alpha = Math.min(1.0, this.config.smoothingRate * (deltaMs / 16.6));

    this.currentParams.eyeball_x += (targetEyeballX - this.currentParams.eyeball_x) * alpha;
    this.currentParams.eyeball_y += (targetEyeballY - this.currentParams.eyeball_y) * alpha;
    this.currentParams.angle_x += (targetAngleX - this.currentParams.angle_x) * alpha;
    this.currentParams.angle_y += (targetAngleY - this.currentParams.angle_y) * alpha;
    this.currentParams.angle_z += (targetAngleZ - this.currentParams.angle_z) * alpha;

    return this.getCurrentParameters();
  }

  /**
   * Manually sets target coordinate for headless tests or custom scripts.
   */
  public setTarget(x: number, y: number, isTracked: boolean = true): void {
    this.currentTarget = {
      x: Math.max(-1.0, Math.min(1.0, x)),
      y: Math.max(-1.0, Math.min(1.0, y)),
      is_tracked: isTracked,
    };
  }

  public getTarget(): Readonly<GazeTarget> {
    return { ...this.currentTarget };
  }

  public getCurrentParameters(): GazeParameters {
    return {
      eyeball_x: Number(this.currentParams.eyeball_x.toFixed(4)),
      eyeball_y: Number(this.currentParams.eyeball_y.toFixed(4)),
      angle_x: Number(this.currentParams.angle_x.toFixed(2)),
      angle_y: Number(this.currentParams.angle_y.toFixed(2)),
      angle_z: Number(this.currentParams.angle_z.toFixed(2)),
    };
  }
}
