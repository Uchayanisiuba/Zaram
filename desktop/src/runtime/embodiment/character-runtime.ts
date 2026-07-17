// desktop/src/runtime/embodiment/character-runtime.ts
//
// PART 2 — Character Runtime
//
// Converts AI/external state into embodiment state. Owns the high-level,
// renderer-independent character subsystems:
//
//   Emotion State   (EmotionRuntime)
//   Eye / Head      (GazeController)
//   Blink           (GazeController)
//   Breathing       (internal phase)
//   Idle Behaviour  (BehaviourRuntime)
//   Thinking        (BehaviourRuntime)
//   Listening       (BehaviourRuntime)
//   Speaking        (BehaviourRuntime)
//   Micro Movement  (derived)
//
// It outputs a CharacterState. PresenceRuntime consumes CharacterState and
// projects it into the renderer-neutral CharacterFrame. AnimationRuntime is
// untouched.

import { BehaviourRuntime, SystemIntent } from './behaviour-runtime'
import { EmotionRuntime } from './emotion-runtime'
import { EmotionEvent, EmotionState } from './types'
import { GazeController, GazePoint } from './gaze-controller'
import {
  BehaviourState,
  CharacterState,
  GazeState,
  MicroExpression
} from './types'

export interface CharacterRuntimeOptions {
  smoothing?: number
  transientDuration?: number
  blinkInterval?: number
  gazeMode?: import('./types').GazeMode
}

export class CharacterRuntime {
  private readonly emotion: EmotionRuntime
  private readonly behaviour: BehaviourRuntime
  private readonly gaze: GazeController
  private breathPhase = 0
  private microMovement = 0

  constructor(options: CharacterRuntimeOptions = {}) {
    this.emotion = new EmotionRuntime({ smoothing: options.smoothing })
    this.behaviour = new BehaviourRuntime({ transientDuration: options.transientDuration })
    this.gaze = new GazeController({ blinkInterval: options.blinkInterval })
    if (options.gazeMode) this.gaze.setMode(options.gazeMode)
  }

  // --- External event ingestion (runtime sources push; user does not) --------

  emitEmotion(event: EmotionEvent): void {
    this.emotion.emit(event)
  }

  setIntent(intent: SystemIntent): void {
    this.behaviour.setIntent(intent)
  }

  setGazeTarget(point: GazePoint): void {
    this.gaze.setTarget(point)
  }

  setGazeMode(mode: import('./types').GazeMode): void {
    this.gaze.setMode(mode)
  }

  triggerGreeting(): void {
    this.behaviour.triggerGreeting()
  }

  triggerWaiting(): void {
    this.behaviour.triggerWaiting()
  }

  triggerAcknowledgement(): void {
    this.behaviour.triggerAcknowledgement()
  }

  triggerSurprise(): void {
    this.behaviour.triggerSurprise()
  }

  triggerMicroExpression(expr: MicroExpression): void {
    this.behaviour.triggerMicroExpression(expr)
  }

  // --- Tick (called by the owning runtime on its existing frame loop) ---------

  update(dt: number): CharacterState {
    const emotion: EmotionState = this.emotion.update(dt)
    const behaviour: BehaviourState = this.behaviour.update(dt)
    const gaze: GazeState = this.gaze.update(dt)

    // Breathing phase advances with time; renderer maps phase -> sine.
    this.breathPhase = (this.breathPhase + dt * (0.25 + emotion.arousal * 0.4)) % 1

    // Micro movement amplitude rises slightly with arousal and thinking load.
    const targetMicro = 0.15 + emotion.arousal * 0.35 + emotion.thinkingLoad * 0.2
    this.microMovement += (targetMicro - this.microMovement) * clamp(dt * 3)

    return this.getState()
  }

  getState(): CharacterState {
    const emotion = this.emotion.getState()
    const behaviour = this.behaviour.getState()
    const gaze = this.gaze.getState()
    return {
      emotion,
      behaviour,
      gaze,
      breath: this.breathPhase,
      microMovement: this.microMovement
    }
  }
}

function clamp(v: number): number {
  return Math.max(0, Math.min(1, v))
}
