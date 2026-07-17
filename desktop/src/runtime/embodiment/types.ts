// desktop/src/runtime/embodiment/types.ts
//
// Core types for the Milestone 1.1 Embodiment Framework.
//
// These types are renderer-independent. They describe the *internal* state of a
// living character (emotion, behaviour, gaze, micro movement) using a
// continuous model. The Renderer consumes only the projection of this state into
// a CharacterFrame — it never sees emotion/thinking/conversation/voice/
// memory/knowledge concerns directly.

import { clampUnit } from '../types'

// --- Emotion (continuous, smoothed) ----------------------------------------

// A continuous emotional model. These are not discrete labels; they are
// floating point activations that drift via smoothing toward targets derived
// from internal state. The user never sets these directly.
export interface EmotionState {
  // -1 (negative) .. +1 (positive)
  valence: number
  // 0 (calm) .. 1 (aroused/excited)
  arousal: number
  // 0 (uncertain) .. 1 (confident)
  confidence: number
  // 0 (distracted) .. 1 (fully attending)
  attention: number
  // 0 (incurious) .. 1 (curious)
  curiosity: number
  // 0 (detached) .. 1 (empathetic)
  empathy: number
  // 0 (rested) .. 1 (exhausted)
  fatigue: number
  // 0 (diffuse) .. 1 (focused)
  focus: number
  // 0 .. 1 cognitive load from active thinking
  thinkingLoad: number
  // 0 .. 1 energy spent while speaking
  speakingEnergy: number
}

// Events that nudge the emotional model. Emitted by the runtime sources,
// never by the user.
export type EmotionEventSource =
  | 'conversation'
  | 'voice'
  | 'knowledge'
  | 'system'
  | 'memory'

export interface EmotionEvent {
  source: EmotionEventSource
  // Suggested additive or absolute nudges on the continuous axes.
  // Values are deltas that are folded into smoothed targets.
  valence?: number
  arousal?: number
  confidence?: number
  attention?: number
  curiosity?: number
  empathy?: number
  fatigue?: number
  focus?: number
  thinkingLoad?: number
  speakingEnergy?: number
  // Absolute override for an axis when the source fully owns that signal
  // (e.g. voice runtime owns speakingEnergy while audio is active).
  set?: Partial<EmotionState>
}

export function defaultEmotionState(): EmotionState {
  return {
    valence: 0,
    arousal: 0.3,
    confidence: 0.6,
    attention: 0.4,
    curiosity: 0.5,
    empathy: 0.6,
    fatigue: 0.1,
    focus: 0.5,
    thinkingLoad: 0,
    speakingEnergy: 0
  }
}

export function clampEmotion(state: EmotionState): EmotionState {
  return {
    valence: Math.max(-1, Math.min(1, state.valence)),
    arousal: clampUnit(state.arousal),
    confidence: clampUnit(state.confidence),
    attention: clampUnit(state.attention),
    curiosity: clampUnit(state.curiosity),
    empathy: clampUnit(state.empathy),
    fatigue: clampUnit(state.fatigue),
    focus: clampUnit(state.focus),
    thinkingLoad: clampUnit(state.thinkingLoad),
    speakingEnergy: clampUnit(state.speakingEnergy)
  }
}

// --- Behaviour --------------------------------------------------------------

export type BehaviourMode =
  | 'idle'
  | 'thinking'
  | 'listening'
  | 'speaking'
  | 'greeting'
  | 'waiting'
  | 'acknowledgement'
  | 'surprise'

// Discrete behaviour labels that the BehaviourRuntime resolves. These are
// intent tags, not renderer instructions.
export type MicroExpression = 'none' | 'brow-raise' | 'smile' | 'frown' | 'blink-double' | 'lip-press'

export interface BehaviourState {
  mode: BehaviourMode
  microExpression: MicroExpression
  // 0 .. 1 intensity of the current behaviour
  intensity: number
  // seconds the current behaviour has been active
  activeFor: number
}

// --- Gaze ------------------------------------------------------------------

export type GazeMode =
  | 'cursor'
  | 'camera'
  | 'face'
  | 'conversation'
  | 'screen'
  | 'wander'
  | 'saccade'

export interface GazeTarget {
  // Normalised look direction, X and Y in [-1, 1].
  x: number
  y: number
}

export interface EyeTarget extends GazeTarget {
  // Convergence in world-ish units; 1 = focused near, 0 = relaxed far.
  convergence: number
  // Saccade jitter magnitude 0..1 applied by the renderer for life.
  jitter: number
}

export interface HeadTarget extends GazeTarget {
  // Roll/tilt in radians, small range for life.
  tilt: number
}

export interface BlinkState {
  // 0 = eyes open, 1 = eyes fully closed (a blink is a short spike to 1).
  closure: number
  // Seconds until next scheduled blink.
  nextIn: number
}

export interface GazeState {
  mode: GazeMode
  eye: EyeTarget
  head: HeadTarget
  blink: BlinkState
}

// --- CharacterState & CharacterFrame ----------------------------------------

// The full internal state owned by CharacterRuntime.
export interface CharacterState {
  emotion: EmotionState
  behaviour: BehaviourState
  gaze: GazeState
  // 0..1 breathing phase advancement cue (renderer drives the actual sine).
  breath: number
  // 0..1 micro-movement amplitude.
  microMovement: number
}

// The ONLY structure the Renderer receives. It projects CharacterState into a
// renderer-neutral frame. It deliberately carries no references to emotion
// semantics, thinking, conversation, voice, memory, or knowledge — only the
// values a renderer needs to render a living presence.
export interface CharacterFrame {
  version: string
  timestamp: number
  // Projected emotional projection (renderer-neutral blendshape-ish weights).
  emotion: {
    valence: number
    arousal: number
    confidence: number
    attention: number
    warmth: number
    curiosity: number
    fatigue: number
  }
  behaviour: {
    mode: BehaviourMode
    intensity: number
    microExpression: MicroExpression
  }
  gaze: {
    eyeX: number
    eyeY: number
    convergence: number
    headX: number
    headY: number
    headTilt: number
    blinkClosure: number
  }
  breath: number
  microMovement: number
  sequence: number
}
