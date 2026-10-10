/**
 * Desktop Live2D Cubism Renderer Manager (Phase 11.4).
 *
 * Governed by ADR-022:
 * - Lock 1: Visual State != Canonical Reality (Presentation-only, zero DB or mutation authority).
 * - Lock 2: Unidirectional Affective Visual Mapping (Consumes render instructions).
 * - Lock 3: Audio-Driven Lip-Sync Without Epistemic Authority (Applies mouth_open_y).
 * - Lock 4: Pure Visual Presentation Scope (Zero hit-testing / touch interaction).
 * - Lock 5: Fail-Closed & Graceful Visual Degradability (WebGL failure -> DEGRADED_FALLBACK).
 * - Lock 7: Renderer State != Character State (Blink timers, motion queues, physics are isolated).
 */

import * as PIXI from "pixi.js";
import { Live2DModel } from "pixi-live2d-display/cubism4";
import {
  GazeParameters,
  LipSyncMouthState,
  RendererState,
  VisualExpressionConfig,
  VisualExpressionType,
  VisualMotionArchetype,
  VisualMotionCommand,
} from "./types";
import { GazeTracker } from "./gazeTracker";

// Expose PIXI to window (required by pixi-live2d-display)
if (typeof window !== "undefined") {
  (window as unknown as { PIXI: typeof PIXI }).PIXI = PIXI;
  try {
    Live2DModel.registerTicker(PIXI.Ticker as any);
  } catch {
    // Already registered
  }
}

export interface CubismInternalRendererState {
  rendererState: RendererState;
  activeExpression: VisualExpressionType;
  expressionIntensity: number;
  activeMotion: VisualMotionArchetype;
  motionPriority: number;
  motionProgressMs: number;
  blinkTimerMs: number;
  nextBlinkIntervalMs: number;
  isBlinking: boolean;
  breathPhase: number;
  mouthOpenY: number;
  gaze: GazeParameters;
  errorMessage?: string;
}

export class CubismRendererManager {
  private canvas: HTMLCanvasElement | null = null;
  private app: PIXI.Application | null = null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private activeModel: any = null;
  private state: RendererState = "uninitialized";
  private loadGeneration: number = 0;
  private tickerAttached: boolean = false;

  // Zoom, scale, and pan positioning
  private baseScale: number = 1.0;
  private zoomLevel: number = 1.0;
  private panX: number = 0;
  private panY: number = 0;

  // Gentle affective reaction state
  private isTouchReacting: boolean = false;
  private touchReactionTimerMs: number = 0;
  private touchReactionDurationMs: number = 2600;

  // ADR-022 Lock 7: Isolated internal Renderer State
  private internalState: CubismInternalRendererState = {
    rendererState: "uninitialized",
    activeExpression: "neutral",
    expressionIntensity: 1.0,
    activeMotion: "idle_normal",
    motionPriority: 1,
    motionProgressMs: 0,
    blinkTimerMs: 0,
    nextBlinkIntervalMs: 3600,
    isBlinking: false,
    breathPhase: 0.0,
    mouthOpenY: 0.0,
    gaze: {
      eyeball_x: 0.0,
      eyeball_y: 0.0,
      angle_x: 0.0,
      angle_y: 0.0,
      angle_z: 0.0,
    },
  };

  private onStateChangeCallback?: (state: RendererState) => void;
  private gazeTracker: GazeTracker | null = null;

  constructor(onStateChange?: (state: RendererState) => void) {
    this.onStateChangeCallback = onStateChange;
  }

  /**
   * Initializes the WebGL canvas and Live2D renderer.
   * Lock 5: If WebGL is unavailable or fails, gracefully falls back to DEGRADED_FALLBACK.
   */
  public async initialize(
    canvas: HTMLCanvasElement,
    modelPath?: string
  ): Promise<RendererState> {
    this.canvas = canvas;
    this.setState("loading");

    try {
      // 1. Check WebGL support
      const gl =
        canvas.getContext("webgl2") ||
        canvas.getContext("webgl") ||
        (canvas.getContext("experimental-webgl") as WebGLRenderingContext | null);

      if (!gl) {
        console.warn("CubismRendererManager: WebGL unavailable. Engaging DEGRADED_FALLBACK.");
        this.setState("degraded_fallback");
        return this.state;
      }

      // 2. Check if window.Live2DCubismCore is present
      const hasCubismCore =
        typeof (window as unknown as { Live2DCubismCore?: unknown }).Live2DCubismCore !== "undefined";

      if (!hasCubismCore) {
        console.info(
          "CubismRendererManager: Live2DCubismCore runtime not detected in window. Using clean visual fallback."
        );
        this.setState("degraded_fallback");
        return this.state;
      }

      // 3. Initialize PIXI Application with High-DPI support
      if (!this.app) {
        const dpr = typeof window !== "undefined" ? Math.max(window.devicePixelRatio || 1, 2) : 2;
        this.app = new PIXI.Application({
          view: canvas,
          backgroundAlpha: 0,
          autoStart: true,
          width: canvas.width || 800,
          height: canvas.height || 1000,
          resolution: dpr,
          autoDensity: true,
          antialias: true,
        });

        // Bind single coordinated ticker for physics and parameters
        if (!this.tickerAttached) {
          this.app.ticker.add(this.onTickerUpdate);
          this.tickerAttached = true;
        }
      }

      // 4. Load model if path provided
      if (modelPath && (modelPath.includes(".json") || modelPath.startsWith("http"))) {
        const loaded = await this.loadModel(modelPath);
        if (!loaded) {
          this.setState("degraded_fallback");
          return this.state;
        }
      } else {
        // Lock 5: No model path specified -> fallback presentation
        this.clearModel();
        this.setState("degraded_fallback");
        return this.state;
      }

      return this.state;
    } catch (err) {
      console.warn("CubismRendererManager initialization error. Falling back safely:", err);
      this.internalState.errorMessage = err instanceof Error ? err.message : String(err);
      this.setState("degraded_fallback");
      return this.state;
    }
  }

  /**
   * Clears the current model and all children on the stage to prevent stacking.
   */
  public clearModel(): void {
    if (this.app?.stage) {
      this.app.stage.removeChildren();
    }
    if (this.activeModel) {
      try {
        this.activeModel.destroy({ children: true });
      } catch {
        // ignore
      }
      this.activeModel = null;
    }
  }

  /**
   * Loads a Live2D Cubism model from URL and scales/centers it smoothly as a strict singleton.
   */
  public async loadModel(url: string): Promise<boolean> {
    if (!this.app) return false;

    // Atomically increment load generation token
    const generation = ++this.loadGeneration;
    this.setState("loading");

    // Immediately clear any active model on stage before loading new one
    this.clearModel();

    try {
      const model = await Live2DModel.from(url, {
        autoInteract: false,
        autoUpdate: true,
      });

      // Concurrency check: If another loadModel was initiated while downloading, discard this model
      if (this.loadGeneration !== generation || !this.app) {
        try {
          model.destroy({ children: true });
        } catch {
          // ignore
        }
        return false;
      }

      // Fit and center model nicely within stage boundaries
      const width = this.canvas?.width || 800;
      const height = this.canvas?.height || 1000;

      const modelWidth = model.internalModel?.width || model.width || 800;
      const modelHeight = model.internalModel?.height || model.height || 1000;

      this.baseScale = Math.min((width * 0.95) / modelWidth, (height * 0.95) / modelHeight);
      this.updateModelTransform(model);

      // Single hook beforeModelUpdate to cleanly set parameters right before skinning
      if (model.internalModel && typeof model.internalModel.on === "function") {
        model.internalModel.on("beforeModelUpdate", () => {
          this.applyParametersToModel(model);
        });
      }

      // Ensure stage is pristine and add ONLY this single model
      this.app.stage.removeChildren();
      this.app.stage.addChild(model as any);
      this.activeModel = model;

      // Start idle motion if available
      try {
        const mm = (model as any).internalModel?.motionManager;
        if (mm && mm.definitions) {
          const groupKeys = Object.keys(mm.definitions);
          const idleKey = groupKeys.find((k) => k.toLowerCase().includes("idle")) || groupKeys[0];
          if (idleKey && typeof (model as any).motion === "function") {
            (model as any).motion(idleKey);
          }
        } else if (typeof (model as any).motion === "function") {
          (model as any).motion("Idle") || (model as any).motion("idle");
        }
      } catch {
        // Optional
      }

      this.setState("ready");
      return true;
    } catch (err) {
      console.warn("Failed to load Live2DModel from:", url, err);
      this.clearModel();
      this.setState("degraded_fallback");
      return false;
    }
  }

  /**
   * Updates model position and scale based on baseScale, zoomLevel, and pan offsets.
   */
  public updateModelTransform(targetModel = this.activeModel): void {
    if (!targetModel) return;
    const width = this.canvas?.width || 800;
    const height = this.canvas?.height || 1000;
    const currentScale = this.baseScale * this.zoomLevel;
    targetModel.scale.set(currentScale);

    if (targetModel.anchor && typeof targetModel.anchor.set === "function") {
      targetModel.anchor.set(0.5, 0.5);
      targetModel.x = width / 2 + this.panX;
      targetModel.y = height / 2 + this.panY;
    } else {
      const modelWidth = targetModel.internalModel?.width || targetModel.width || width;
      const modelHeight = targetModel.internalModel?.height || targetModel.height || height;
      targetModel.x = (width - modelWidth * currentScale) / 2 + this.panX;
      targetModel.y = (height - modelHeight * currentScale) / 2 + this.panY;
    }
  }

  public setZoom(zoom: number): void {
    this.zoomLevel = Math.max(0.4, Math.min(4.0, zoom));
    this.updateModelTransform();
  }

  public zoomBy(delta: number): number {
    this.setZoom(this.zoomLevel + delta);
    return this.zoomLevel;
  }

  public panBy(dx: number, dy: number): void {
    this.panX += dx;
    this.panY += dy;
    this.updateModelTransform();
  }

  public resetTransform(): void {
    this.zoomLevel = 1.0;
    this.panX = 0;
    this.panY = 0;
    this.updateModelTransform();
  }

  public getTransform(): { zoom: number; panX: number; panY: number } {
    return { zoom: this.zoomLevel, panX: this.panX, panY: this.panY };
  }

  /**
   * Triggers an interactive motion or cute expression when user clicks or pets the model.
   */
  public triggerInteractiveReaction(): string {
    if (!this.activeModel) return "";

    this.isTouchReacting = true;
    this.touchReactionTimerMs = 0;

    const cuteExpressions: VisualExpressionType[] = ["smile", "joy", "blush", "surprise"];
    const chosenExpr = cuteExpressions[Math.floor(Math.random() * cuteExpressions.length)];
    this.setExpression({
      expression: chosenExpr,
      intensity: 1.0,
      parameter_overrides: {},
      transition_duration_ms: 300,
    });

    // Try starting any available motion group in the model
    try {
      const mm = this.activeModel.internalModel?.motionManager;
      if (mm && mm.definitions) {
        const groups = Object.keys(mm.definitions).filter((g) => g.toLowerCase() !== "idle");
        if (groups.length > 0) {
          const targetGroup = groups[Math.floor(Math.random() * groups.length)];
          this.activeModel.motion(targetGroup);
        } else if (typeof this.activeModel.motion === "function") {
          this.activeModel.motion("Tap_Body") || this.activeModel.motion("Tap") || this.activeModel.motion("Idle");
        }
      } else if (typeof this.activeModel.motion === "function") {
        this.activeModel.motion("Tap_Body") || this.activeModel.motion("Tap") || this.activeModel.motion("Idle");
      }
    } catch {
      // ignore
    }

    setTimeout(() => {
      this.setExpression({
        expression: "neutral",
        intensity: 1.0,
        parameter_overrides: {},
        transition_duration_ms: 600,
      });
    }, 2600);

    return chosenExpr;
  }

  /**
   * Updates target expression from VisualExpressionConfig render instruction.
   * Lock 2: Unidirectional affective mapping (read-only render instruction).
   */
  public setExpression(config: VisualExpressionConfig): void {
    this.internalState.activeExpression = config.expression;
    this.internalState.expressionIntensity = config.intensity;
    if (this.activeModel && typeof this.activeModel.expression === "function") {
      try {
        this.activeModel.expression(config.expression);
      } catch {
        // Fallback or ignore unsupported expressions
      }
    }
  }

  /**
   * Updates motion command from VisualMotionCommand render instruction.
   * Lock 7: Preempts only if incoming priority is greater than or equal to current.
   */
  public setMotion(command: VisualMotionCommand): void {
    if (command.priority >= this.internalState.motionPriority) {
      this.internalState.activeMotion = command.archetype;
      this.internalState.motionPriority = command.priority;
      this.internalState.motionProgressMs = 0;
      if (this.activeModel && typeof this.activeModel.motion === "function") {
        try {
          this.activeModel.motion(command.archetype);
        } catch {
          // Fallback or ignore
        }
      }
    }
  }

  /**
   * Updates lip-sync mouth opening parameter from LipSyncMouthState.
   * Lock 3: Applies mouth_open_y. mouth_form remains unmanaged.
   */
  public setLipSync(mouthState: LipSyncMouthState): void {
    this.internalState.mouthOpenY = Math.max(0.0, Math.min(1.0, mouthState.mouth_open_y));
  }

  /**
   * Attaches a decoupled GazeTracker to drive eye and head tracking during render loops.
   */
  public attachGazeTracker(tracker: GazeTracker): void {
    this.gazeTracker = tracker;
  }

  /**
   * Detaches the active GazeTracker.
   */
  public detachGazeTracker(): void {
    this.gazeTracker = null;
  }

  /**
   * Updates gaze parameters manually or via external instruction.
   */
  public setGaze(gaze: GazeParameters): void {
    this.internalState.gaze = gaze;
  }

  /**
   * Reads current internal Renderer State (read-only snapshot).
   * Lock 7: Strictly Renderer State, never CharacterState.
   */
  public getInternalState(): Readonly<CubismInternalRendererState> {
    return { ...this.internalState };
  }

  public getState(): RendererState {
    return this.state;
  }

  public getCanvas(): HTMLCanvasElement | null {
    return this.canvas;
  }

  private setState(newState: RendererState): void {
    this.state = newState;
    this.internalState.rendererState = newState;
    if (this.onStateChangeCallback) {
      this.onStateChangeCallback(newState);
    }
  }

  /**
   * Computes the current eye open ratio based on natural cosine-smoothed blinking.
   */
  private getBlinkEyeOpenValue(): number {
    if (!this.internalState.isBlinking) {
      return 1.0;
    }
    const t = this.internalState.blinkTimerMs;
    // Fast closing (60ms), graceful opening (100ms)
    if (t < 60) {
      return Math.max(0, 1.0 - t / 60);
    } else {
      return Math.min(1.0, (t - 60) / 100);
    }
  }

  /**
   * Ticker update handler bound to Pixi Ticker for exact frame synchronization.
   */
  private onTickerUpdate = (delta: number): void => {
    const deltaMs = this.app?.ticker.deltaMS || delta * 16.66;
    this.updateSimulation(deltaMs);
  };

  /**
   * Performs per-frame internal state simulations (gaze, blinking, breathing phase).
   */
  public updateSimulation(deltaMs: number): void {
    try {
      // 0. Advance decoupled gaze tracking
      if (this.gazeTracker) {
        this.internalState.gaze = this.gazeTracker.update(deltaMs);
      }

      // 1. Advance motion progress
      this.internalState.motionProgressMs += deltaMs;

      // 2. Natural eye blinking presentation behavior
      this.internalState.blinkTimerMs += deltaMs;
      if (!this.internalState.isBlinking && this.internalState.blinkTimerMs > this.internalState.nextBlinkIntervalMs) {
        this.internalState.isBlinking = true;
        this.internalState.blinkTimerMs = 0;
      } else if (this.internalState.isBlinking && this.internalState.blinkTimerMs > 160) {
        this.internalState.isBlinking = false;
        this.internalState.blinkTimerMs = 0;
        this.internalState.nextBlinkIntervalMs = 3000 + Math.random() * 2500;
      }

      // 3. Organic breathing cycle
      this.internalState.breathPhase =
        (this.internalState.breathPhase + (deltaMs / 4000) * Math.PI * 2) % (Math.PI * 2);

      // 4. Affective reaction progress
      if (this.isTouchReacting) {
        this.touchReactionTimerMs += deltaMs;
        if (this.touchReactionTimerMs >= this.touchReactionDurationMs) {
          this.isTouchReacting = false;
          this.touchReactionTimerMs = 0;
        }
      }
    } catch (err) {
      console.warn("CubismRendererManager simulation update error:", err);
    }
  }

  /**
   * Applies all continuous live parameters strictly via setParameterValueById (no compounding additions).
   */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private applyParametersToModel(model: any): void {
    if (!model) return;
    const core = model.internalModel?.coreModel;
    if (!core || typeof core.setParameterValueById !== "function") return;

    try {
      // 1. Natural eye blinking (1.0 -> 0.0 -> 1.0)
      const blinkVal = this.getBlinkEyeOpenValue();
      core.setParameterValueById("ParamEyeLOpen", blinkVal);
      core.setParameterValueById("ParamEyeROpen", blinkVal);
      core.setParameterValueById("PARAM_EYE_L_OPEN", blinkVal);
      core.setParameterValueById("PARAM_EYE_R_OPEN", blinkVal);

      // 2. Continuous organic breathing rhythm (0.0 to 1.0)
      const breathVal = (Math.sin(this.internalState.breathPhase) + 1) / 2;
      core.setParameterValueById("ParamBreath", breathVal);
      core.setParameterValueById("PARAM_BREATH", breathVal);

      // 3. Alive respiratory chest & head vertical oscillation
      const respiratoryBodyY = Math.sin(this.internalState.breathPhase) * 2.8;
      const respiratoryHeadY = Math.sin(this.internalState.breathPhase) * 1.5;

      // 3.1 Subtle organic micro-sways synchronized with breathing
      const microSwayX = Math.sin(this.internalState.breathPhase * 0.5) * 1.8;
      const microSwayY = Math.cos(this.internalState.breathPhase) * 1.2;
      const microTiltZ = Math.sin(this.internalState.breathPhase * 0.7) * 1.0;

      // 3.2 Procedural active motion synthesis (breathing, thinking tilt, talking nod, head shake)
      let motionAngleX = 0;
      let motionAngleY = 0;
      let motionAngleZ = 0;
      let motionBodyX = 0;
      let motionBodyY = 0;
      let motionEyeballX = 0;
      let motionEyeballY = 0;

      const motionProg = this.internalState.motionProgressMs;
      const activeMotion = this.internalState.activeMotion;

      if (activeMotion === "thinking_tilt") {
        // Thoughtful tilt when model is generating or pondering
        motionAngleZ += 8.5 + Math.sin(motionProg * 0.003) * 1.8;
        motionAngleY += 3.5 + Math.cos(motionProg * 0.002) * 1.2;
        motionEyeballY += 0.32;
        motionEyeballX -= 0.22;
        core.setParameterValueById("ParamBrowLY", 0.3);
        core.setParameterValueById("ParamBrowRY", 0.1);
      } else if (activeMotion === "talking_casual") {
        // Natural conversational head nods when speaking
        const nod = Math.sin(motionProg * 0.008) * 3.5;
        motionAngleY += nod;
        motionAngleX += Math.cos(motionProg * 0.004) * 1.8;
        motionBodyY += nod * 0.4;
      } else if (activeMotion === "shake_head") {
        // Subtle or defensive head shake
        const shake = Math.sin(motionProg * 0.012) * 8.0 * Math.exp(-motionProg * 0.0008);
        motionAngleX += shake;
        motionAngleZ -= shake * 0.3;
      } else if (activeMotion === "nod") {
        // Gentle agreement nod
        const nodVal = Math.sin(motionProg * 0.008) * 4.5 * Math.exp(-motionProg * 0.001);
        motionAngleY += nodVal;
        motionBodyY += nodVal * 0.5;
      } else if (activeMotion === "idle_energetic") {
        // Gentle energetic lift
        const bounce = Math.abs(Math.sin(motionProg * 0.006)) * 2.5;
        motionAngleY += bounce;
        motionBodyY += bounce * 0.4;
      }

      // 3.5. Affective reaction animation overlay
      let touchTiltZ = 0;
      if (this.isTouchReacting) {
        const progress = Math.min(1.0, this.touchReactionTimerMs / this.touchReactionDurationMs);
        const intensity = Math.sin((1 - progress) * Math.PI); // Smooth peak & ease out
        touchTiltZ = Math.sin(this.touchReactionTimerMs * 0.008) * 6.0 * intensity;
        const blush = 0.9 * intensity;
        const smile = 1.0 * intensity;
        core.setParameterValueById("ParamCheek", blush);
        core.setParameterValueById("PARAM_CHEEK", blush);
        if (blush > 0.3) {
          core.setParameterValueById("ParamHeartEye", 1.0);
        }
        core.setParameterValueById("ParamEyeLSmile", smile);
        core.setParameterValueById("ParamEyeRSmile", smile);
        core.setParameterValueById("PARAM_EYE_L_SMILE", smile);
        core.setParameterValueById("PARAM_EYE_R_SMILE", smile);
        core.setParameterValueById("ParamMouthForm", smile);
        core.setParameterValueById("PARAM_MOUTH_FORM", smile);
      }

      // 4. Smooth Gaze and head angle following + micro-sways + motion synthesis + touch reaction
      const baseAngleX = this.internalState.gaze?.angle_x ?? 0.0;
      const baseAngleY = this.internalState.gaze?.angle_y ?? 0.0;
      const baseAngleZ = this.internalState.gaze?.angle_z ?? 0.0;
      const eyeballX = this.internalState.gaze?.eyeball_x ?? 0.0;
      const eyeballY = this.internalState.gaze?.eyeball_y ?? 0.0;

      const totalAngleX = baseAngleX + microSwayX + motionAngleX;
      const totalAngleY = baseAngleY + microSwayY + respiratoryHeadY + motionAngleY;
      const totalAngleZ = baseAngleZ + microTiltZ + touchTiltZ + motionAngleZ;

      core.setParameterValueById("ParamAngleX", totalAngleX);
      core.setParameterValueById("ParamAngleY", totalAngleY);
      core.setParameterValueById("ParamAngleZ", totalAngleZ);
      core.setParameterValueById("PARAM_ANGLE_X", totalAngleX);
      core.setParameterValueById("PARAM_ANGLE_Y", totalAngleY);
      core.setParameterValueById("PARAM_ANGLE_Z", totalAngleZ);

      const totalEyeballX = Math.max(-1.0, Math.min(1.0, eyeballX + motionEyeballX));
      const totalEyeballY = Math.max(-1.0, Math.min(1.0, eyeballY + motionEyeballY));

      core.setParameterValueById("ParamEyeBallX", totalEyeballX);
      core.setParameterValueById("ParamEyeBallY", totalEyeballY);
      core.setParameterValueById("PARAM_EYE_BALL_X", totalEyeballX);
      core.setParameterValueById("PARAM_EYE_BALL_Y", totalEyeballY);

      const totalBodyAngleX = totalAngleX * 0.35 + motionBodyX;
      const totalBodyAngleY = respiratoryBodyY + motionBodyY;
      const totalBodyAngleZ = totalAngleZ * 0.25;

      core.setParameterValueById("ParamBodyAngleX", totalBodyAngleX);
      core.setParameterValueById("ParamBodyAngleY", totalBodyAngleY);
      core.setParameterValueById("ParamBodyAngleZ", totalBodyAngleZ);
      core.setParameterValueById("PARAM_BODY_ANGLE_X", totalBodyAngleX);
      core.setParameterValueById("PARAM_BODY_ANGLE_Y", totalBodyAngleY);
      core.setParameterValueById("PARAM_BODY_ANGLE_Z", totalBodyAngleZ);

      // 5. Speech Lip-Sync mouth movement (0.0 to 1.0)
      if (this.internalState.mouthOpenY > 0) {
        core.setParameterValueById("ParamMouthOpen", this.internalState.mouthOpenY);
        core.setParameterValueById("ParamMouthOpenY", this.internalState.mouthOpenY);
        core.setParameterValueById("PARAM_MOUTH_OPEN_Y", this.internalState.mouthOpenY);
      } else {
        core.setParameterValueById("ParamMouthOpen", 0.0);
        core.setParameterValueById("ParamMouthOpenY", 0.0);
        core.setParameterValueById("PARAM_MOUTH_OPEN_Y", 0.0);
      }

      // 6. Emotional expression overrides
      this.applyEmotionalParameters(core);
    } catch {
      // Ignore individual parameter errors for diverse model schemas
    }
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private applyEmotionalParameters(core: any): void {
    if (typeof core.setParameterValueById !== "function") return;
    const expr = this.internalState.activeExpression;
    const intensity = this.internalState.expressionIntensity ?? 1.0;

    switch (expr) {
      case "joy":
      case "smile":
        core.setParameterValueById("ParamEyeLSmile", 1.0 * intensity);
        core.setParameterValueById("ParamEyeRSmile", 1.0 * intensity);
        core.setParameterValueById("ParamCheek", 0.6 * intensity);
        core.setParameterValueById("ParamMouthForm", 1.0 * intensity);
        break;
      case "blush":
        core.setParameterValueById("ParamHeartEye", 1.0 * intensity);
        core.setParameterValueById("ParamCheek", 1.0 * intensity);
        core.setParameterValueById("ParamEyeLSmile", 0.7 * intensity);
        core.setParameterValueById("ParamEyeRSmile", 0.7 * intensity);
        break;
      case "sad":
      case "worried":
        core.setParameterValueById("ParamTears", 0.8 * intensity);
        core.setParameterValueById("ParamBrowLY", -0.6 * intensity);
        core.setParameterValueById("ParamBrowRY", -0.6 * intensity);
        core.setParameterValueById("ParamMouthForm", -0.8 * intensity);
        break;
      case "pout":
        core.setParameterValueById("ParamAngrySign", 1.0 * intensity);
        core.setParameterValueById("ParamBrowLY", -0.9 * intensity);
        core.setParameterValueById("ParamBrowRY", -0.9 * intensity);
        core.setParameterValueById("ParamMouthForm", -0.5 * intensity);
        break;
      case "surprise":
        core.setParameterValueById("ParamShock", 1.0 * intensity);
        core.setParameterValueById("ParamEyeShockVisible", 1.0);
        core.setParameterValueById("ParamEyeLOpen", 1.2 * intensity);
        core.setParameterValueById("ParamEyeROpen", 1.2 * intensity);
        break;
      case "tired":
      case "thinking":
        core.setParameterValueById("ParamEyeLOpen", 0.75);
        core.setParameterValueById("ParamEyeROpen", 0.75);
        break;
      case "neutral":
      default:
        core.setParameterValueById("ParamCheek", 0.0);
        core.setParameterValueById("ParamTears", 0.0);
        core.setParameterValueById("ParamShock", 0.0);
        core.setParameterValueById("ParamAngrySign", 0.0);
        core.setParameterValueById("ParamHeartEye", 0.0);
        break;
    }
  }

  /**
   * Safely disposes WebGL and animation resources.
   */
  public dispose(): void {
    if (this.app && this.tickerAttached) {
      this.app.ticker.remove(this.onTickerUpdate);
      this.tickerAttached = false;
    }
    if (this.gazeTracker) {
      this.gazeTracker.detach();
      this.gazeTracker = null;
    }
    this.clearModel();
    if (this.app) {
      try {
        this.app.destroy(true, { children: true, texture: true, baseTexture: true });
      } catch {
        // ignore
      }
      this.app = null;
    }
    this.canvas = null;
    this.setState("uninitialized");
  }
}
