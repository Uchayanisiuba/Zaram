// desktop/src/runtime/cognitive/types.ts
//
// Core types for the Milestone 1.2 Cognitive Runtime.
//
// The cognitive layer is the AI's internal state — fully independent of rendering.
// It is the single source of "what the AI is thinking/planning/attending to"
// separate from how the embodiment expresses it. The embodiment (CharacterRuntime
// and below) consumes the cognitive state; the renderer never sees it.

import { clampUnit } from '../types'

// --- Reasoning --------------------------------------------------------------

export type ReasoningState =
  | 'idle'
  | 'perceiving'
  | 'reasoning'
  | 'planning'
  | 'reflecting'
  | 'deciding'

// --- Conversation Intent ----------------------------------------------------

export type ConversationIntent =
  | 'none'
  | 'greet'
  | 'listen'
  | 'ask'
  | 'answer'
  | 'clarify'
  | 'acknowledge'
  | 'farewell'

// --- Task / Plan ------------------------------------------------------------

export interface CognitiveTask {
  id: string
  label: string
  // 0 (low) .. 1 (critical)
  priority: number
  // true once pulled into the active plan
  planned: boolean
  // true once completed
  done: boolean
  createdAt: number
}

export interface PlanningState {
  active: boolean
  // 0 .. 1 progress of the current plan
  progress: number
  // ordered plan step labels
  steps: string[]
}

// --- Knowledge / Memory Requests --------------------------------------------

export interface KnowledgeRequest {
  id: string
  query: string
  issuedAt: number
  resolved: boolean
}

export interface MemoryRequest {
  id: string
  query: string
  issuedAt: number
  resolved: boolean
}

// --- Cognitive State (the full internal snapshot) ---------------------------

export interface CognitiveState {
  reasoning: ReasoningState
  intent: ConversationIntent
  // internal goals as free-form weighted items
  goals: Array<{ id: string; label: string; weight: number }>
  planning: PlanningState
  // pending task queue (not yet planned)
  taskQueue: CognitiveTask[]
  // current attention priority 0..1 (how demanding the current focus is)
  attentionPriority: number
  // explicit thinking status flag (independent of rendering)
  thinking: boolean
  // outstanding knowledge requests
  knowledgeRequests: KnowledgeRequest[]
  // outstanding memory requests
  memoryRequests: MemoryRequest[]
  // monotonically increasing revision so consumers can detect change
  revision: number
  updatedAt: number
}

// Events the cognitive runtime reacts to. Injected by runtimes, never set by
// the user directly.
export type CognitiveEvent =
  | { kind: 'phase'; phase: 'idle' | 'listening' | 'thinking' | 'generating' | 'working' | 'speaking' | 'interrupted' | 'error' | 'sleeping' }
  | { kind: 'intent'; intent: ConversationIntent }
  | { kind: 'goal'; id: string; label: string; weight: number }
  | { kind: 'task'; task: Omit<CognitiveTask, 'planned' | 'done' | 'createdAt'> }
  | { kind: 'plan'; steps: string[] }
  | { kind: 'planProgress'; progress: number }
  | { kind: 'thinking'; value: boolean }
  | { kind: 'attention'; priority: number }
  | { kind: 'knowledgeRequest'; query: string }
  | { kind: 'knowledgeResolved'; id: string }
  | { kind: 'memoryRequest'; query: string }
  | { kind: 'memoryResolved'; id: string }

let _taskSeq = 0
function nextId(prefix: string): string {
  _taskSeq += 1
  return `${prefix}-${Date.now().toString(36)}-${_taskSeq}`
}

export class CognitiveRuntime {
  private state: CognitiveState = defaultCognitiveState()
  private readonly subscribers = new Set<(s: CognitiveState) => void>()

  // --- Event ingestion (runtime sources push; user does not) ----------------

  emit(event: CognitiveEvent): void {
    this.apply(event)
    this.bump()
    const snapshot = this.getState()
    this.subscribers.forEach((l) => l(snapshot))
  }

  subscribe(listener: (s: CognitiveState) => void): () => void {
    this.subscribers.add(listener)
    return () => {
      this.subscribers.delete(listener)
    }
  }

  private apply(event: CognitiveEvent): void {
    switch (event.kind) {
      case 'phase':
        this.state.reasoning = toReasoning(event.phase)
        if (event.phase === 'thinking' || event.phase === 'generating' || event.phase === 'working') {
          this.state.thinking = true
        } else if (event.phase === 'idle' || event.phase === 'sleeping') {
          this.state.thinking = false
        }
        break
      case 'intent':
        this.state.intent = event.intent
        break
      case 'goal':
        this.state.goals = this.state.goals.filter((g) => g.id !== event.id)
        this.state.goals.push({ id: event.id, label: event.label, weight: clampUnit(event.weight) })
        this.state.goals.sort((a, b) => b.weight - a.weight)
        break
      case 'task': {
        const task: CognitiveTask = {
          ...event.task,
          priority: clampUnit(event.task.priority),
          planned: false,
          done: false,
          createdAt: Date.now()
        }
        this.state.taskQueue.push(task)
        this.state.taskQueue.sort((a, b) => b.priority - a.priority)
        break
      }
      case 'plan':
        this.state.planning = { active: event.steps.length > 0, progress: 0, steps: [...event.steps] }
        // Pull the highest-priority queued task into the plan.
        const next = this.state.taskQueue.find((t) => !t.planned && !t.done)
        if (next) next.planned = true
        break
      case 'planProgress':
        this.state.planning = { ...this.state.planning, progress: clampUnit(event.progress) }
        break
      case 'thinking':
        this.state.thinking = event.value
        break
      case 'attention':
        this.state.attentionPriority = clampUnit(event.priority)
        break
      case 'knowledgeRequest':
        this.state.knowledgeRequests.push({
          id: nextId('kreq'),
          query: event.query,
          issuedAt: Date.now(),
          resolved: false
        })
        break
      case 'knowledgeResolved':
        this.state.knowledgeRequests = this.state.knowledgeRequests.map((r) =>
          r.id === event.id ? { ...r, resolved: true } : r
        )
        break
      case 'memoryRequest':
        this.state.memoryRequests.push({
          id: nextId('mreq'),
          query: event.query,
          issuedAt: Date.now(),
          resolved: false
        })
        break
      case 'memoryResolved':
        this.state.memoryRequests = this.state.memoryRequests.map((r) =>
          r.id === event.id ? { ...r, resolved: true } : r
        )
        break
    }
  }

  private bump(): void {
    this.state = { ...this.state, revision: this.state.revision + 1, updatedAt: Date.now() }
  }

  // --- External queries -----------------------------------------------------

  getState(): CognitiveState {
    return clone(this.state)
  }

  getThinking(): boolean {
    return this.state.thinking
  }

  getIntent(): ConversationIntent {
    return this.state.intent
  }

  getAttentionPriority(): number {
    return this.state.attentionPriority
  }

  getReasoning(): ReasoningState {
    return this.state.reasoning
  }

  getPendingTasks(): CognitiveTask[] {
    return this.state.taskQueue.filter((t) => !t.done)
  }

  getOpenKnowledgeRequests(): number {
    return this.state.knowledgeRequests.filter((r) => !r.resolved).length
  }

  getOpenMemoryRequests(): number {
    return this.state.memoryRequests.filter((r) => !r.resolved).length
  }

  // Mark a queued task complete by id (used when a plan step finishes).
  completeTask(id: string): void {
    let changed = false
    this.state.taskQueue = this.state.taskQueue.map((t) => {
      if (t.id === id && !t.done) {
        changed = true
        return { ...t, done: true }
      }
      return t
    })
    if (changed) this.bump()
  }

  reset(): void {
    this.state = defaultCognitiveState()
  }
}

// --- Helpers ----------------------------------------------------------------

function toReasoning(phase: string): ReasoningState {
  switch (phase) {
    case 'listening':
      return 'perceiving'
    case 'thinking':
    case 'generating':
      return 'reasoning'
    case 'working':
      return 'planning'
    case 'speaking':
      return 'deciding'
    case 'interrupted':
      return 'reflecting'
    case 'sleeping':
    case 'idle':
    default:
      return 'idle'
  }
}

function defaultCognitiveState(): CognitiveState {
  return {
    reasoning: 'idle',
    intent: 'none',
    goals: [],
    planning: { active: false, progress: 0, steps: [] },
    taskQueue: [],
    attentionPriority: 0.1,
    thinking: false,
    knowledgeRequests: [],
    memoryRequests: [],
    revision: 0,
    updatedAt: Date.now()
  }
}

function clone(s: CognitiveState): CognitiveState {
  return {
    reasoning: s.reasoning,
    intent: s.intent,
    goals: s.goals.map((g) => ({ ...g })),
    planning: { ...s.planning, steps: [...s.planning.steps] },
    taskQueue: s.taskQueue.map((t) => ({ ...t })),
    attentionPriority: s.attentionPriority,
    thinking: s.thinking,
    knowledgeRequests: s.knowledgeRequests.map((r) => ({ ...r })),
    memoryRequests: s.memoryRequests.map((r) => ({ ...r })),
    revision: s.revision,
    updatedAt: s.updatedAt
  }
}

// local clamp helper (the cognitive layer has no other use for embodiment types)
function clamp(v: number): number {
  return Math.max(-1, Math.min(1, v))
}
