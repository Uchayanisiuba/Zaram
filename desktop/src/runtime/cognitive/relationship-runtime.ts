// desktop/src/runtime/cognitive/relationship-runtime.ts
//
// PART 3 — Relationship Runtime
//
// Tracks the evolving relationship with the user/participants. All metrics are
// continuous and evolve GRADUALLY (small per-event deltas, optional easing). No
// metric jumps instantly. Event-driven: interaction events nudge the state.

import { clampUnit } from '../types'

export interface RelationshipState {
  // 0 (distrustful) .. 1 (trusting)
  trust: number
  // 0 (stranger) .. 1 (intimate familiarity)
  familiarity: number
  // 0..1 weight of accumulated conversation history
  conversationHistoryWeight: number
  // 0..1 confidence the runtime has in the user's stated preferences
  preferenceConfidence: number
  // 0..1 how frequently the user interacts (decays when idle)
  interactionFrequency: number
  // 0 (disrespectful) .. 1 (respected)
  respect: number
  // 0 (mismatch) .. 1 (shared humor)
  humorCompatibility: number
  // monotonically increasing interaction count
  interactions: number
  updatedAt: number
}

export interface RelationshipEvent {
  // a completed interaction (speech turn, message, etc.)
  interaction?: boolean
  // user did something that built trust
  trustDelta?: number
  // user did something that eroded trust
  distrustDelta?: number
  // observed a user preference
  preferenceObserved?: number
  // shared a humorous moment
  humor?: number
  // respectful / disrespectful signal
  respectDelta?: number
  // explicit familiarity nudge (e.g. returning user)
  familiarityDelta?: number
  // seconds of inactivity used to decay frequency (applied in update)
}

export interface RelationshipRuntimeOptions {
  // max fraction of full range a single event may move a metric (gradual change)
  maxStep?: number
  // per-second decay of interactionFrequency when idle
  frequencyDecayPerSec?: number
  // smoothing factor for history weight accumulation
  historyWeightRate?: number
}

export class RelationshipRuntime {
  private state: RelationshipState = defaultRelationship()
  private readonly maxStep: number
  private readonly frequencyDecayPerSec: number
  private readonly historyWeightRate: number
  private readonly subscribers = new Set<(s: RelationshipState) => void>()

  constructor(options: RelationshipRuntimeOptions = {}) {
    this.maxStep = options.maxStep ?? 0.05
    this.frequencyDecayPerSec = options.frequencyDecayPerSec ?? 0.02
    this.historyWeightRate = options.historyWeightRate ?? 0.01
  }

  emit(event: RelationshipEvent): void {
    this.apply(event)
    this.bump()
    const snapshot = this.getState()
    this.subscribers.forEach((l) => l(snapshot))
  }

  subscribe(listener: (s: RelationshipState) => void): () => void {
    this.subscribers.add(listener)
    return () => {
      this.subscribers.delete(listener)
    }
  }

  // Called on the existing frame loop; decays interaction frequency when idle so
  // "frequency" reflects recency. No new timers.
  update(dt: number): RelationshipState {
    this.state.interactionFrequency = Math.max(
      0,
      this.state.interactionFrequency - this.frequencyDecayPerSec * dt
    )
    // History weight creeps up with accumulated interactions (capped).
    if (this.state.interactions > 0) {
      this.state.conversationHistoryWeight = clampUnit(
        this.state.conversationHistoryWeight + this.historyWeightRate * dt
      )
    }
    this.bump()
    return this.getState()
  }

  private apply(event: RelationshipEvent): void {
    const s = this.state
    if (event.interaction) {
      s.interactions += 1
      s.interactionFrequency = clampUnit(s.interactionFrequency + this.maxStep * 2)
      s.familiarity = step(s.familiarity, this.maxStep, 1)
    }
    if (event.trustDelta) s.trust = step(s.trust, this.maxStep, clampUnit(s.trust + event.trustDelta))
    if (event.distrustDelta)
      s.trust = step(s.trust, this.maxStep, clampUnit(s.trust - event.distrustDelta))
    if (event.preferenceObserved)
      s.preferenceConfidence = step(
        s.preferenceConfidence,
        this.maxStep,
        clampUnit(s.preferenceConfidence + event.preferenceObserved)
      )
    if (event.humor) s.humorCompatibility = step(s.humorCompatibility, this.maxStep, clampUnit(s.humorCompatibility + event.humor))
    if (event.respectDelta) s.respect = step(s.respect, this.maxStep, clampUnit(s.respect + event.respectDelta))
    if (event.familiarityDelta)
      s.familiarity = step(s.familiarity, this.maxStep, clampUnit(s.familiarity + event.familiarityDelta))
  }

  private bump(): void {
    this.state = { ...this.state, updatedAt: Date.now() }
  }

  getState(): RelationshipState {
    return { ...this.state }
  }

  reset(): void {
    this.state = defaultRelationship()
  }
}

// Move `current` toward `target` by at most `maxStep` of the full 0..1 range.
function step(current: number, maxStep: number, target: number): number {
  const delta = target - current
  const capped = Math.max(-maxStep, Math.min(maxStep, delta))
  return clampUnit(current + capped)
}

function defaultRelationship(): RelationshipState {
  return {
    trust: 0.5,
    familiarity: 0.2,
    conversationHistoryWeight: 0.1,
    preferenceConfidence: 0.3,
    interactionFrequency: 0.2,
    respect: 0.6,
    humorCompatibility: 0.5,
    interactions: 0,
    updatedAt: Date.now()
  }
}
