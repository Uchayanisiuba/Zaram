// desktop/src/runtime/execution/index.ts
//
// Milestone 1.6 — Execution Runtime barrel.
//
// The Execution Runtime is the ONLY runtime allowed to invoke capabilities.
// It is the single authority for execution lifecycle, timeout, retry,
// cancellation, progress, audit, rollback, and permission enforcement.
// It is fully display-independent and advanced on the existing 30Hz tick
// (no new timers, no polling, no requestAnimationFrame).

export { ExecutionRuntime } from './execution-runtime'
export type {
  ExecutionRuntimeOptions,
  IExecutionRuntime
} from './execution-runtime'

export {
  ExecutionInvoker
} from './execution-invoker'
export type {
  IExecutionInvoker
} from './execution-invoker'

export {
  createContext,
  createRequest,
  newExecutionId,
  executionNow
} from './execution-context'

export {
  EXECUTION_TRANSITIONS,
  EXECUTION_TERMINAL,
  isTerminal,
  canTransition,
  transition
} from './execution-state-machine'

export type {
  ExecutionStatus,
  ExecutionContext,
  ExecutionRequest,
  ExecutionOptions,
  ExecutionResult,
  ExecutionError,
  ExecutionAuditEntry,
  ExecutionHistoryEntry,
  ExecutionControls,
  ExecutionHandler,
  ExecutionRollback,
  ExecutionEventType,
  ExecutionEvent
} from './types'
