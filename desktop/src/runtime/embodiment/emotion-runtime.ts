// desktop/src/runtime/embodiment/emotion-runtime.ts
//
// PART 3 — Emotional State Machine (continuous model)
//
// DOES NOT implement fake emotions. Emotions are continuous activations that
// emerge from internal state fed by runtime sources (conversation, voice,
// knowledge, system, memory). The user never sets an emotion directly.
//
// Smoothing: targets are nudged by events; the *current* state eases toward the
// target every update() so transitions are never instant. Fully event-driven:
// no timers, no polling — update() is called by the owning runtime on frame
// ticks that it already owns.

import {
  EmotionEvent,
  EmotionState,
  clampEmotion,
  defaultEmotionState
} from './types'

export interface EmotionRuntimeOptions {
  smoothing?: number // 0..1 per-update ease factor (higher = faster)
  initialState?: EmotionState
}

export class EmotionRuntime {
  private current: EmotionState
  private target: EmotionState
  private readonly smoothing: number

  constructor(options: EmotionRuntimeOptions = {}) {
    this.smoothing = options.smoothing ?? 0.08
    this.current = clampEmotion(options.initialState ?? defaultEmotionState())
    this.target = { ...this.current }
  }

  // Push an event from a runtime source. Folds deltas into the target the
  // current state eases toward. Absolute `set` overrides take precedence for
  // axes a source fully owns.
  emit(event: EmotionEvent): void {
    const t = { ...this.target }
    if (typeof event.valence === 'number') t.valence += event.valence
    if (typeof event.arousal === 'number') t.arousal += event.arousal
    if (typeof event.confidence === 'number') t.confidence += event.confidence
    if (typeof event.attention === 'number') t.attention += event.attention
    if (typeof event.curiosity === 'number') t.curiosity += event.curiosity
    if (typeof event.empathy === 'number') t.empathy += event.empathy
    if (typeof event.fatigue === 'number') t.fatigue += event.fatigue
    if (typeof event.focus === 'number') t.focus += event.focus
    if (typeof event.thinkingLoad === 'number') t.thinkingLoad += event.thinkingLoad
    if (typeof event.speakingEnergy === 'number') t.speakingEnergy += event.speakingEnergy
    if (event.set) {
      for (const key of Object.keys(event.set) as (keyof EmotionState)[]) {
        ;(t as Record<string, number>)[key] = (event.set as Record<string, number>)[key]
      }
    }
    this.target = t
  }

  // Ease the current state toward the (clamped) target. Called by the owner on
  // its existing frame tick. dt is seconds; smoothing scales so behaviour is
  // framerate independent.
  update(dt: number): EmotionState {
    const k = clampRate(this.smoothing, dt)
    this.current = clampEmotion({
      valence: ease(this.current.valence, this.target.valence, k),
      arousal: ease(this.current.arousal, this.target.arousal, k),
      confidence: ease(this.current.confidence, this.target.confidence, k),
      attention: ease(this.current.attention, this.target.attention, k),
      curiosity: ease(this.current.curiosity, this.target.curiosity, k),
      empathy: ease(this.current.empathy, this.target.empathy, k),
      fatigue: ease(this.current.fatigue, this.target.fatigue, k),
      focus: ease(this.current.focus, this.target.focus, k),
      thinkingLoad: ease(this.current.thinkingLoad, this.target.thinkingLoad, k),
      speakingEnergy: ease(this.current.speakingEnergy, this.target.speakingEnergy, k)
    })
    return this.getState()
  }

  getState(): EmotionState {
    return clampEmotion(this.current)
  }

  // Test/diagnostic helper: what the model is easing toward.
  getTarget(): EmotionState {
    return clampEmotion(this.target)
  }

  reset(): void {
    this.current = defaultEmotionState()
    this.target = { ...this.current }
  }
}

function ease(current: number, target: number, k: number): number {
  return current + (target - current) * k
}

// Convert a per-30fps ease factor into a framerate-independent rate.
function clampRate(perTickEase: number, dt: number): number {
  const refDt = 1 / 30
  const rate = perTickEase * (dt / refDt)
  return Math.max(0, Math.min(1, rate))
}
