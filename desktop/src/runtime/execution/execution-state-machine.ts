// desktop/src/runtime/execution/execution-state-machine.ts
//
// Milestone 1.6 — Deterministic execution state machine.
//
// Encodes the legal lifecycle transitions as an explicit, inspectable map so
// transitions are provably deterministic (no implicit edges). The Execution
// Runtime is the only caller; every transition is validated here.

import { ExecutionStatus } from './types'

// Allowed transitions. A status may only move to one of the listed targets.
export const EXECUTION_TRANSITIONS: Record<ExecutionStatus, ExecutionStatus[]> = {
  queued: ['preparing', 'cancelled', 'failed'],
  preparing: ['running', 'waiting', 'cancelled', 'failed'],
  running: ['waiting', 'completed', 'cancelled', 'failed', 'retrying'],
  waiting: ['running', 'completed', 'cancelled', 'failed', 'retrying'],
  retrying: ['preparing', 'cancelled', 'failed'],
  completed: [],
  cancelled: ['rolledback'],
  failed: ['rolledback', 'retrying'],
  rolledback: []
}

// Terminal states: nothing further happens without a new execution.
export const EXECUTION_TERMINAL: ReadonlySet<ExecutionStatus> = new Set<ExecutionStatus>([
  'completed',
  'cancelled',
  'failed',
  'rolledback'
])

export function isTerminal(status: ExecutionStatus): boolean {
  return EXECUTION_TERMINAL.has(status)
}

export function canTransition(from: ExecutionStatus, to: ExecutionStatus): boolean {
  return EXECUTION_TRANSITIONS[from]?.includes(to) ?? false
}

// Apply a transition, throwing on an illegal edge. Returns the new status.
export function transition(from: ExecutionStatus, to: ExecutionStatus): ExecutionStatus {
  if (from === to) return from
  if (!canTransition(from, to)) {
    throw new Error(`Illegal execution transition: ${from} -> ${to}`)
  }
  return to
}
