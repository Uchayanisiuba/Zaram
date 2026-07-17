// desktop/src/runtime/cognitive/bundle.ts
//
// CognitiveBundle: the injected unit that PresenceRuntime consumes.
//
// Bundles the three cognitive runtimes (Cognitive, Attention, Relationship),
// exposes a single event-driven `emit` and a single `update(dt)` for the
// existing frame tick. This keeps PresenceRuntime's surface tiny and avoids
// introducing any new render loop — update() is called inside the same tick
// that already drives AnimationRuntime and CharacterRuntime.

import {
  AttentionRuntime,
  AttentionEvent,
  AttentionState,
  CognitiveRuntime,
  CognitiveEvent,
  CognitiveState,
  RelationshipRuntime,
  RelationshipEvent,
  RelationshipState
} from './index'

export interface CognitiveBundleOptions {
  cognitive?: CognitiveRuntime
  attention?: AttentionRuntime
  relationship?: RelationshipRuntime
}

export class CognitiveBundle {
  readonly cognitive: CognitiveRuntime
  readonly attention: AttentionRuntime
  readonly relationship: RelationshipRuntime

  constructor(options: CognitiveBundleOptions = {}) {
    this.cognitive = options.cognitive ?? new CognitiveRuntime()
    this.attention = options.attention ?? new AttentionRuntime()
    this.relationship = options.relationship ?? new RelationshipRuntime()
  }

  emitCognitive(event: CognitiveEvent): void {
    this.cognitive.emit(event)
  }

  emitAttention(event: AttentionEvent): void {
    this.attention.emit(event)
  }

  emitRelationship(event: RelationshipEvent): void {
    this.relationship.emit(event)
  }

  // Advance all sub-runtimes on the existing frame tick. No new timers.
  update(dt: number): void {
    this.attention.update(dt)
    this.relationship.update(dt)
    // CognitiveRuntime is purely event-driven; no time-based decay required.
  }

  getCognitiveState(): CognitiveState {
    return this.cognitive.getState()
  }

  getAttentionState(): AttentionState {
    return this.attention.getState()
  }

  getRelationshipState(): RelationshipState {
    return this.relationship.getState()
  }
}
