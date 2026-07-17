// desktop/src/runtime/executive/executive-state.ts
//
// Milestone 1.4 — ExecutiveState.
//
// The single read model produced by the Executive Runtime. It carries ONLY
// executive/decision data: focus, priorities, interrupt handling, task
// switching, context selection, goal management, and intention generation.
//
// It contains NO drawing-layer data, NO body-layer data, and NO character
// projection.

import {
  ExecutiveDecision,
  ExecutiveGoal,
  FocusTarget,
  InterruptState,
  Priority,
  ReasoningMode,
  ThinkingMode
} from './types'

export interface ExecutiveState {
  // The goal the AI is actively pursuing right now.
  currentGoal: ExecutiveGoal | null
  // Ordered stack of active goals (currentGoal is goalStack[0] when present).
  goalStack: ExecutiveGoal[]
  // Where attention/effort is currently directed.
  focus: FocusTarget
  // 0 (diffuse) .. 1 (locked in)
  focusStrength: number
  // The current high-level intent (the only signal the body layer consumes).
  currentIntent: ExecutiveDecision
  // Resolved priority band for the current activity.
  priority: Priority
  // Interrupt bookkeeping.
  interruptState: InterruptState
  // pending interrupts awaiting handling (highest-salience first)
  pendingInterrupts: Array<{ id: string; reason: string; severity: string; salience: number }>
  // Reasoning strategy currently engaged.
  reasoningMode: ReasoningMode
  // 0 (guessing) .. 1 (certain)
  confidence: number
  // 0 (no rush) .. 1 (act now)
  urgency: number
  // Thinking depth currently committed.
  thinkingMode: ThinkingMode
  // monotincreasing revision so consumers can detect change
  revision: number
  updatedAt: number
}

export function defaultExecutiveState(): ExecutiveState {
  return {
    currentGoal: null,
    goalStack: [],
    focus: 'none',
    focusStrength: 0,
    currentIntent: 'wait',
    priority: 'background',
    interruptState: 'clear',
    pendingInterrupts: [],
    reasoningMode: 'reactive',
    confidence: 0.5,
    urgency: 0,
    thinkingMode: 'idle',
    revision: 0,
    updatedAt: 0
  }
}

export function cloneExecutiveState(s: ExecutiveState): ExecutiveState {
  return {
    currentGoal: s.currentGoal ? { ...s.currentGoal } : null,
    goalStack: s.goalStack.map((g) => ({ ...g })),
    focus: s.focus,
    focusStrength: s.focusStrength,
    currentIntent: s.currentIntent,
    priority: s.priority,
    interruptState: s.interruptState,
    pendingInterrupts: s.pendingInterrupts.map((p) => ({ ...p })),
    reasoningMode: s.reasoningMode,
    confidence: s.confidence,
    urgency: s.urgency,
    thinkingMode: s.thinkingMode,
    revision: s.revision,
    updatedAt: s.updatedAt
  }
}
