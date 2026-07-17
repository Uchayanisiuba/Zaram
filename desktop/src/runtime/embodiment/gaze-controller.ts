// desktop/src/runtime/embodiment/gaze-controller.ts
//
// PART 5 — Eye Tracking
//
// Produces EyeTarget, HeadTarget, and BlinkState. No renderer logic — only
// behaviour state that a renderer projects. Supports multiple gaze sources:
// cursor, camera, face (future), conversation target, screen focus, idle
// wandering, and random saccades. Blink timing is scheduled, not polled.

import { BlinkState, EyeTarget, GazeMode, GazeState, HeadTarget } from './types'

export interface GazePoint {
  x: number // [-1, 1]
  y: number // [-1, 1]
}

export interface GazeControllerOptions {
  // Average seconds between blinks.
  blinkInterval?: number
  // Blink closure duration in seconds.
  blinkDuration?: number
  // Seconds between random saccades when wandering/idle.
  saccadeInterval?: number
  // Amplitude of idle wander in normalised units.
  wanderAmplitude?: number
}

export class GazeController {
  private mode: GazeMode = 'wander'
  private readonly target: GazePoint = { x: 0, y: 0 }
  private readonly current: GazePoint = { x: 0, y: 0 }
  private readonly headCurrent: GazePoint = { x: 0, y: 0 }
  private blink: BlinkState = { closure: 0, nextIn: 3 }
  private blinkTimer = 0
  private saccadeTimer = 0
  private saccadeTarget: GazePoint = { x: 0, y: 0 }
  private readonly blinkInterval: number
  private readonly blinkDuration: number
  private readonly saccadeInterval: number
  private readonly wanderAmplitude: number
  private rng: () => number

  constructor(options: GazeControllerOptions = {}) {
    this.blinkInterval = options.blinkInterval ?? 3.5
    this.blinkDuration = options.blinkDuration ?? 0.12
    this.saccadeInterval = options.saccadeInterval ?? 2.2
    this.wanderAmplitude = options.wanderAmplitude ?? 0.25
    this.rng = Math.random
    this.blink.nextIn = this.blinkInterval * (0.5 + this.rng())
  }

  setMode(mode: GazeMode): void {
    this.mode = mode
  }

  // External target (cursor position, conversation partner location, etc.).
  setTarget(point: GazePoint): void {
    this.target.x = clamp(point.x)
    this.target.y = clamp(point.y)
  }

  update(dt: number): GazeState {
    this.updateSaccade(dt)
    this.easeToward(dt)
    this.updateBlink(dt)
    return this.getState()
  }

  private updateSaccade(dt: number): void {
    this.saccadeTimer -= dt
    if (this.saccadeTimer <= 0) {
      this.saccadeTimer = this.saccadeInterval * (0.6 + this.rng() * 0.8)
      // Random saccade: a small jump the eye eases toward.
      this.saccadeTarget = {
        x: (this.rng() * 2 - 1),
        y: (this.rng() * 2 - 1)
      }
    }
  }

  private easeToward(dt: number): void {
    // Base point depends on mode; saccades and wander layer on top.
    let baseX = this.target.x
    let baseY = this.target.y
    if (this.mode === 'wander' || this.mode === 'screen') {
      const t = (typeof performance !== 'undefined' ? performance.now() : Date.now()) / 1000
      baseX += Math.sin(t * 0.6) * this.wanderAmplitude
      baseY += Math.cos(t * 0.43) * this.wanderAmplitude * 0.6
    }
    const sx = this.saccadeTarget.x * 0.08
    const sy = this.saccadeTarget.y * 0.08
    const k = clamp(dt * 9)
    this.current.x += (baseX + sx - this.current.x) * k
    this.current.y += (baseY + sy - this.current.y) * k
    this.headCurrent.x += (baseX * 0.6 - this.headCurrent.x) * clamp(dt * 4)
    this.headCurrent.y += (baseY * 0.4 - this.headCurrent.y) * clamp(dt * 4)
  }

  private updateBlink(dt: number): void {
    this.blinkTimer += dt
    if (this.blinkTimer >= this.blink.nextIn) {
      // Begin a blink spike.
      this.blinkTimer = 0
      this.blink.nextIn = this.blinkInterval * (0.6 + this.rng() * 0.8)
      this.blink.closure = 1
    }
    if (this.blink.closure > 0) {
      this.blink.closure = Math.max(0, this.blink.closure - dt / this.blinkDuration)
    }
  }

  getState(): GazeState {
    const eye: EyeTarget = {
      x: clamp(this.current.x),
      y: clamp(this.current.y),
      convergence: 0.5,
      jitter: this.mode === 'wander' || this.mode === 'saccade' ? 0.4 : 0.1
    }
    const head: HeadTarget = {
      x: clamp(this.headCurrent.x),
      y: clamp(this.headCurrent.y),
      tilt: Math.sin(this.headCurrent.x * 1.5) * 0.08
    }
    return {
      mode: this.mode,
      eye,
      head,
      blink: { closure: this.blink.closure, nextIn: Math.max(0, this.blink.nextIn - this.blinkTimer) }
    }
  }

  setRng(fn: () => number): void {
    this.rng = fn
  }
}

function clamp(v: number): number {
  return Math.max(-1, Math.min(1, v))
}
