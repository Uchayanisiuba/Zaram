// desktop/src/runtime/cognitive/attention-runtime.ts
//
// PART 2 — Attention Runtime
//
// Tracks where the AI's attention is directed and how confident it is in that
// focus. This is internal cognitive state (not gaze/rendering). Smooth
// transitions are applied when the focus target changes so the embodiment can
// later map them to eased movement. Fully event-driven.

import { clampUnit } from '../types'
import { CognitiveState } from './types'

export type AttentionTarget =
  | 'none'
  | 'speaker'
  | 'conversation'
  | 'cursor'
  | 'camera'
  | 'notification'
  | 'memory'
  | 'internal'

export interface AttentionEvent {
  // who/what is currently speaking
  speaker?: string
  // conversation target id (the entity the AI is addressing)
  conversationTarget?: string
  // normalized cursor position [-1,1] x/y (screen space)
  cursor?: { x: number; y: number }
  // normalized camera focus [-1,1] x/y
  camera?: { x: number; y: number }
  // a transient system notification competing for attention
  notification?: { id: string; severity: number }
  // memory relevance 0..1 for the current context
  memoryRelevance?: number
  // explicit focus target override
  target?: AttentionTarget
}

export interface AttentionState {
  current: AttentionTarget
  speaker: string | null
  conversationTarget: string | null
  cursor: { x: number; y: number }
  camera: { x: number; y: number }
  // 0..1 how confident the AI is in its current focus
  focusConfidence: number
  // 0..1 salience of an active notification (decays over time)
  notificationSalience: number
  // 0..1 relevance of memory to the current turn
  memoryRelevance: number
  // 0..1 priority weighting of the current target (derived)
  priority: number
}

export class AttentionRuntime {
  private state: AttentionState = defaultAttention()
  // Eased "current" positions follow these targets (set by events).
  private cursorTarget = { x: 0, y: 0 }
  private cameraTarget = { x: 0, y: 0 }
  private readonly subscribers = new Set<(s: AttentionState) => void>()
  private notificationDecayPerSec = 0.4
  private nowFn: () => number = () => (typeof performance !== 'undefined' ? performance.now() : Date.now())

  emit(event: AttentionEvent): void {
    this.apply(event)
    this.bump()
    const snapshot = this.getState()
    this.subscribers.forEach((l) => l(snapshot))
  }

  subscribe(listener: (s: AttentionState) => void): () => void {
    this.subscribers.add(listener)
    return () => {
      this.subscribers.delete(listener)
    }
  }

  // Smoothly ease current -> target each tick. dt in seconds. Called by the
  // owning runtime on its existing frame loop; introduces no new timer.
  update(dt: number): AttentionState {
    const s = this.state
    const k = clampUnit(dt * 6)
    // Ease the exposed cursor/camera toward their event-driven targets so
    // transitions are smooth (no instant jumps).
    s.cursor.x = ease(s.cursor.x, this.cursorTarget.x, k)
    s.cursor.y = ease(s.cursor.y, this.cursorTarget.y, k)
    s.camera.x = ease(s.camera.x, this.cameraTarget.x, k)
    s.camera.y = ease(s.camera.y, this.cameraTarget.y, k)
    s.focusConfidence = ease(s.focusConfidence, s.focusConfidence, k)
    // Notification salience decays unless refreshed.
    s.notificationSalience = Math.max(0, s.notificationSalience - this.notificationDecayPerSec * dt)
    if (s.notificationSalience <= 0.001) s.notificationSalience = 0
    // Priority derived from target importance + salience + memory relevance.
    s.priority = clampUnit(targetWeight(s.current) * 0.5 + s.notificationSalience * 0.3 + s.memoryRelevance * 0.2)
    this.bump()
    return this.getState()
  }

  private apply(event: AttentionEvent): void {
    const s = this.state
    if (event.speaker !== undefined) s.speaker = event.speaker
    if (event.conversationTarget !== undefined) s.conversationTarget = event.conversationTarget
    if (event.cursor) {
      this.cursorTarget.x = clampUnit((event.cursor.x + 1) / 2) * 2 - 1
      this.cursorTarget.y = clampUnit((event.cursor.y + 1) / 2) * 2 - 1
    }
    if (event.camera) {
      this.cameraTarget.x = clampUnit((event.camera.x + 1) / 2) * 2 - 1
      this.cameraTarget.y = clampUnit((event.camera.y + 1) / 2) * 2 - 1
    }
    if (event.notification) {
      s.notificationSalience = clampUnit(event.notification.severity)
      if (event.notification.severity > 0.5) s.current = 'notification'
    }
    if (event.memoryRelevance !== undefined) s.memoryRelevance = clampUnit(event.memoryRelevance)
    if (event.target) s.current = event.target
    // A speaking speaker pulls attention to the speaker.
    if (event.speaker && s.current === 'none') s.current = 'speaker'
  }

  private bump(): void {
    this.state = { ...this.state }
  }

  getState(): AttentionState {
    return clone(this.state)
  }

  // Test hook.
  setNow(fn: () => number): void {
    this.nowFn = fn
  }
}

function ease(current: number, target: number, k: number): number {
  return current + (target - current) * k
}

function targetWeight(t: AttentionTarget): number {
  switch (t) {
    case 'notification':
      return 1
    case 'speaker':
    case 'conversation':
      return 0.8
    case 'camera':
      return 0.6
    case 'cursor':
      return 0.4
    case 'memory':
      return 0.5
    case 'internal':
      return 0.3
    case 'none':
    default:
      return 0.1
  }
}

function defaultAttention(): AttentionState {
  return {
    current: 'none',
    speaker: null,
    conversationTarget: null,
    cursor: { x: 0, y: 0 },
    camera: { x: 0, y: 0 },
    focusConfidence: 0.5,
    notificationSalience: 0,
    memoryRelevance: 0,
    priority: 0.05
  }
}

function clone(s: AttentionState): AttentionState {
  return {
    current: s.current,
    speaker: s.speaker,
    conversationTarget: s.conversationTarget,
    cursor: { ...s.cursor },
    camera: { ...s.camera },
    focusConfidence: s.focusConfidence,
    notificationSalience: s.notificationSalience,
    memoryRelevance: s.memoryRelevance,
    priority: s.priority
  }
}

// Helper to derive an attention target from cognitive reasoning, used by the
// presence integration so attention follows the AI's internal state.
export function attentionTargetFromCognitive(c: CognitiveState): AttentionTarget {
  switch (c.reasoning) {
    case 'perceiving':
      return 'speaker'
    case 'reasoning':
    case 'planning':
      return 'internal'
    case 'deciding':
      return 'conversation'
    case 'reflecting':
      return 'memory'
    case 'idle':
    default:
      return 'none'
  }
}
