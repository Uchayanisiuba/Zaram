// desktop/src/runtime/execution/types.ts
//
// Milestone 1.6 — Execution Runtime types.
//
// The Execution Runtime is the ONLY runtime allowed to invoke capabilities.
// The Capability Runtime exposes metadata only; the Executive Runtime decides
// but never executes. This file defines the execution contracts.
//
// This file is purely additive. It must NOT import the drawing layer, the body
// layer, concrete avatars, the character projection, the animation engine, frame
// snapshots, the orb drawing code, the desktop shell, any GPU/3D engine, or the
// Emotion/Behaviour/Presence/Character/body-layer runtimes.

// --- Execution lifecycle ------------------------------------------------

export type ExecutionStatus =
  | 'queued'
  | 'preparing'
  | 'running'
  | 'waiting'
  | 'retrying'
  | 'completed'
  | 'cancelled'
  | 'failed'
  | 'rolledback'

// --- Execution context ---------------------------------------------------

export interface ExecutionContext {
  // Opaque correlation id linking this execution to a higher-level request.
  correlationId: string
  // Permissions granted to this execution (superset of capability requirements).
  grantedPermissions: string[]
  // Optional actor/user identity for the audit trail.
  actor?: string
  // Optional parent execution id (for nested executions).
  parentId?: string
  // Optional free-form metadata (locale, trace id, etc).
  metadata?: Record<string, unknown>
  // Monotonic priority used for ordering the queue (higher = sooner).
  priority?: number
  // Epoch ms when the context was created.
  createdAt: number
}

// --- Execution request ---------------------------------------------------

export interface ExecutionRequest {
  // Stable, unique capability id resolved via the Capability Runtime.
  capabilityId: string
  // Input payload forwarded to the capability invoker.
  input: unknown
  // Execution context (correlation, permissions, metadata).
  context: ExecutionContext
  // Optional explicit execution id (otherwise generated).
  id?: string
  // Execution options.
  options?: ExecutionOptions
}

export interface ExecutionOptions {
  // Hard timeout in ms; the runtime enforces this on the reused 30Hz tick.
  timeoutMs?: number
  // Maximum number of attempts (1 = no retries).
  maxRetries?: number
  // Delay between retries in ms (enforced on the tick, not via setTimeout).
  retryDelayMs?: number
  // Whether this execution may be cancelled mid-flight.
  cancellable?: boolean
  // Whether a rollback hook must be invoked on failure/cancel.
  rollbackSupported?: boolean
  // Whether the execution may enter a 'waiting' state (e.g. awaiting input).
  waitable?: boolean
  // Optional tag for grouping/history queries.
  tag?: string
}

// --- Execution result ----------------------------------------------------

export interface ExecutionAuditEntry {
  eventId: string
  timestamp: number
  action: string
  outcome: 'ok' | 'denied' | 'error' | 'info'
  detail?: string
}

export interface ExecutionHistoryEntry {
  attempt: number
  status: ExecutionStatus
  startedAt: number
  finishedAt: number | null
  durationMs: number | null
  error?: string
}

export interface ExecutionResult {
  // Execution id (stable, unique).
  id: string
  // The capability this execution invoked.
  capabilityId: string
  // Current lifecycle status.
  status: ExecutionStatus
  // Output payload (populated on completion).
  output: unknown
  // Error payload (populated on failure/cancel/timeout).
  error: ExecutionError | null
  // 0..1 progress reported during the run.
  progress: number
  // Attempt counter (1-based).
  attempts: number
  // Correlation id from the request context.
  correlationId: string
  // Started at (queued → preparing).
  createdAt: number
  // Entered 'running' at.
  startedAt: number | null
  // Finalised at (completed/failed/cancelled/rolledback).
  finishedAt: number | null
  // Total wall-clock duration in ms.
  durationMs: number | null
  // Per-attempt history.
  history: ExecutionHistoryEntry[]
  // Append-only audit trail.
  audit: ExecutionAuditEntry[]
  // Whether the execution was cancelled by a caller.
  cancelled: boolean
  // Whether a rollback hook was invoked.
  rolledBack: boolean
  // Current permissions snapshot (for observability).
  permissions: string[]
  // Optional grouping tag.
  tag?: string
  // Execution options (runtime use).
  options?: ExecutionOptions
  // Elapsed ms since this attempt entered 'running'.
  elapsedMs?: number
  // Input payload forwarded to the capability invoker.
  input?: unknown
  // Remaining ms before retry transition fires.
  retryDelayRemainingMs?: number
}

export interface ExecutionError {
  code: string
  message: string
  attempt: number
  // Optional underlying cause category.
  kind?: 'timeout' | 'cancelled' | 'permission' | 'capability-unavailable' | 'handler' | 'rollback'
}

// --- Controls handed to the invoker ------------------------------------

export interface ExecutionControls {
  // Report progress 0..1.
  reportProgress(progress: number): void
  // Finalise the current attempt successfully.
  succeed(output: unknown): void
  // Finalise the current attempt as a failure.
  fail(error: Error | string | ExecutionError): void
  // True when a caller requested cancellation.
  isCancelled(): boolean
  // Elapsed ms since this attempt entered 'running'.
  elapsedMs(): number
}

// --- Invoker contract ---------------------------------------------------

// A concrete capability implementation is wrapped by an ExecutionHandler. The
// Execution Runtime is the ONLY runtime that calls handlers. The handler is
// invoked once per attempt; it must eventually call controls.succeed/fail
// (synchronously or inside an async callback). For timer-free timeout/cancel,
// the runtime enforces limits on the reused 30Hz tick; the handler should
// honour controls.isCancelled() where practical.
export type ExecutionHandler = (
  request: ExecutionRequest,
  context: ExecutionContext,
  controls: ExecutionControls
) => void | Promise<void>

// Optional rollback hook registered alongside a handler.
export type ExecutionRollback = (request: ExecutionRequest, context: ExecutionContext) => void | Promise<void>

// --- Event bus contract (mirrors the universal event contract) ----------

export type ExecutionEventType =
  | 'execution.queued'
  | 'execution.preparing'
  | 'execution.running'
  | 'execution.waiting'
  | 'execution.retrying'
  | 'execution.progress'
  | 'execution.completed'
  | 'execution.cancelled'
  | 'execution.failed'
  | 'execution.rolledback'
  | 'execution.audit'

export interface ExecutionEvent {
  event_id: string
  timestamp: number
  source_runtime: 'execution'
  event_type: ExecutionEventType
  version: number
  priority: 'critical' | 'high' | 'normal' | 'background'
  data: Record<string, unknown>
  correlation_id: string | null
}
