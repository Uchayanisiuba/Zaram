// desktop/src/runtime/embodiment/behaviour-runtime.ts
//
// PART 4 — Behaviour System
//
// Controls *behaviour state only*. No renderer logic. It resolves a BehaviourMode
// from system intent (idle/thinking/listening/speaking), injects transient
// behaviours (greeting, waiting, acknowledgement, surprise, micro expressions),
// and tracks intensity/active duration. The renderer reads the resulting state
// and decides how to animate.

import { BehaviourMode, BehaviourState, MicroExpression } from './types'

export type SystemIntent = 'idle' | 'thinking' | 'listening' | 'speaking'

export interface BehaviourRuntimeOptions {
  // seconds a transient behaviour (greeting/surprise/etc) stays active before
  // returning to the base intent.
  transientDuration?: number
}

export class BehaviourRuntime {
  private state: BehaviourState = {
    mode: 'idle',
    microExpression: 'none',
    intensity: 0.2,
    activeFor: 0
  }
  private baseIntent: SystemIntent = 'idle'
  private transientUntil = 0
  private readonly transientDuration: number
  private nowFn: () => number

  constructor(options: BehaviourRuntimeOptions = {}) {
    this.transientDuration = options.transientDuration ?? 1.5
    this.nowFn = () => (typeof performance !== 'undefined' ? performance.now() : Date.now())
  }

  // Base mode driven by the system runtime state. Transient behaviours layer on
  // top of this.
  setIntent(intent: SystemIntent): void {
    this.baseIntent = intent
  }

  triggerGreeting(): void {
    this.startTransient('greeting')
  }

  triggerWaiting(): void {
    this.startTransient('waiting')
  }

  triggerAcknowledgement(): void {
    this.startTransient('acknowledgement')
  }

  triggerSurprise(): void {
    this.startTransient('surprise', 'brow-raise')
  }

  triggerMicroExpression(expr: MicroExpression): void {
    this.state.microExpression = expr
  }

  private startTransient(mode: BehaviourMode, micro: MicroExpression = 'none'): void {
    this.state.mode = mode
    this.state.microExpression = micro
    this.state.activeFor = 0
    this.transientUntil = this.nowFn() + this.transientDuration * 1000
  }

  // Called by the owning runtime on its frame tick. dt in seconds.
  update(dt: number): BehaviourState {
    if (this.transientUntil > 0 && this.nowFn() >= this.transientUntil) {
      this.transientUntil = 0
      this.state.mode = this.baseIntent
      this.state.microExpression = 'none'
      this.state.activeFor = 0
    }

    // When no transient behaviour is active, the base intent drives the mode.
    if (this.transientUntil === 0) {
      this.state.mode = this.baseIntent
    }

    const targetIntensity = this.intensityFor(this.state.mode)
    this.state.intensity = this.state.intensity + (targetIntensity - this.state.intensity) * 0.1
    this.state.activeFor += dt
    return this.getState()
  }

  private intensityFor(mode: BehaviourMode): number {
    switch (mode) {
      case 'speaking':
        return 0.9
      case 'thinking':
        return 0.55
      case 'listening':
        return 0.6
      case 'greeting':
        return 0.95
      case 'surprise':
        return 0.85
      case 'acknowledgement':
        return 0.7
      case 'waiting':
        return 0.4
      case 'idle':
      default:
        return 0.2
    }
  }

  getState(): BehaviourState {
    return { ...this.state }
  }

  // Test hook: force the clock.
  setNow(fn: () => number): void {
    this.nowFn = fn
  }
}
