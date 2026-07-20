// desktop/src/runtime/execution/execution-runtime.ts
//
// Milestone 1.6 — Execution Runtime.
//
// The ONLY runtime allowed to invoke capabilities. The Capability Runtime
// exposes metadata only; the Executive Runtime decides but never executes.
// This runtime is fully display-independent and advanced on the existing
// 30Hz tick (no new timers, no polling, no requestAnimationFrame).
//
// It integrates through Dependency Injection, the Runtime Registry, and
// the Event Bus (per-runtime pub/sub, same pattern as World/Cognitive/Executive).

import {
  ExecutionControls,
  ExecutionError,
  ExecutionEvent,
  ExecutionEventType,
  ExecutionHandler,
  ExecutionOptions,
  ExecutionRequest,
  ExecutionResult,
  ExecutionRollback,
  ExecutionStatus,
  ExecutionAuditEntry,
  ExecutionHistoryEntry
} from './types'
import { canTransition, EXECUTION_TRANSITIONS, isTerminal, transition } from './execution-state-machine'
import { IExecutionInvoker } from './execution-invoker'
import { createContext, createRequest, newExecutionId, executionNow } from './execution-context'
import type { ICapabilityRuntime } from '../capability'

export interface ExecutionRuntimeOptions {
  invoker?: IExecutionInvoker
  capabilityRuntime?: ICapabilityRuntime
  now?: () => number
}

export interface IExecutionRuntime {
  execute(request: ExecutionRequest): string
  cancel(id: string): boolean
  retry(id: string): boolean
  rollback(id: string): boolean
  getExecution(id: string): ExecutionResult | null
  getHistory(): ExecutionResult[]
  update(dt: number): void
}

export class ExecutionRuntime implements IExecutionRuntime {
  private readonly invoker: IExecutionInvoker
  private readonly capabilityRuntime?: ICapabilityRuntime
  private readonly now: () => number

  private readonly executions = new Map<string, ExecutionResult>()
  private readonly subscribers = new Set<(event: ExecutionEvent) => void>()
  private eventSeq = 0
  private revision = 0

  constructor(options: ExecutionRuntimeOptions = {}) {
    this.invoker = options.invoker ?? ({} as IExecutionInvoker)
    this.capabilityRuntime = options.capabilityRuntime
    this.now = options.now ?? executionNow
  }

  // --- Public API -----------------------------------------------------------

  execute(request: ExecutionRequest): string {
    const id = request.id ?? newExecutionId()
    const exec: ExecutionResult = {
      id,
      capabilityId: request.capabilityId,
      status: 'queued',
      output: null,
      error: null,
      progress: 0,
      attempts: 1,
      correlationId: request.context.correlationId,
      createdAt: this.now(),
      startedAt: null,
      finishedAt: null,
      durationMs: null,
      history: [],
      audit: [],
      cancelled: false,
      rolledBack: false,
      permissions: request.context.grantedPermissions,
      tag: request.options?.tag,
      options: request.options,
      elapsedMs: 0,
      input: request.input
    }
    this.executions.set(id, exec)
    this.addAudit(exec, 'execute', 'info', `Queued execution for capability ${request.capabilityId}`)
    this.publish('execution.queued', exec)
    return id
  }

  cancel(id: string): boolean {
    const exec = this.executions.get(id)
    if (!exec) return false
    if (exec.cancelled) return true
    if (!this.canCancel(exec)) return false

    exec.cancelled = true
    this.addAudit(exec, 'cancel', 'info', 'Cancellation requested by caller')

    if (exec.status === 'queued') {
      this.transition(exec, 'cancelled')
      exec.finishedAt = this.now()
      exec.durationMs = exec.finishedAt - exec.createdAt
      this.addHistory(exec, 'cancelled')
      this.addAudit(exec, 'cancel', 'info', 'Execution cancelled')
      this.publish('execution.cancelled', exec)

      if (exec.options?.rollbackSupported) {
        this.invokeRollback(exec)
      }
    }
    // If running/waiting/retrying, the tick will observe exec.cancelled and transition.
    return true
  }

  retry(id: string): boolean {
    const exec = this.executions.get(id)
    if (!exec || exec.status !== 'failed') return false

    const maxRetries = exec.options?.maxRetries ?? 1
    if (exec.attempts >= maxRetries) return false

    this.transition(exec, 'retrying')
    exec.retryDelayRemainingMs = exec.options?.retryDelayMs ?? 0
    this.addAudit(exec, 'retry', 'info', `Retry requested (next attempt ${exec.attempts + 1})`)
    this.publish('execution.retrying', exec)
    return true
  }

  rollback(id: string): boolean {
    const exec = this.executions.get(id)
    if (!exec) return false
    if (isTerminal(exec.status) && exec.status !== 'failed' && exec.status !== 'cancelled') return false

    return this.invokeRollback(exec)
  }

  getExecution(id: string): ExecutionResult | null {
    const exec = this.executions.get(id)
    if (!exec) return null
    return this.cloneResult(exec)
  }

  getHistory(): ExecutionResult[] {
    return Array.from(this.executions.values()).map((e) => this.cloneResult(e))
  }

  // --- 30Hz tick advancement -----------------------------------------------

  update(dt: number): void {
    const dtMs = dt * 1000
    for (const exec of this.executions.values()) {
      if (isTerminal(exec.status)) continue

      switch (exec.status) {
        case 'queued':
          this.tickQueued(exec)
          break
        case 'preparing':
          this.tickPreparing(exec)
          break
        case 'running':
          this.tickRunning(exec, dtMs)
          break
        case 'waiting':
          this.tickWaiting(exec)
          break
        case 'retrying':
          this.tickRetrying(exec, dtMs)
          break
      }
    }
  }

  private tickQueued(exec: ExecutionResult): void {
    this.transition(exec, 'preparing')
    exec.startedAt = this.now()
    this.publish('execution.preparing', exec)

    if (this.capabilityRuntime) {
      const descriptor = this.capabilityRuntime.get(exec.capabilityId)
      if (!descriptor) {
        this.completeFail(exec, { code: 'capability-unavailable', message: `Capability not found: ${exec.capabilityId}`, attempt: exec.attempts, kind: 'capability-unavailable' })
        return
      }
      const missing = descriptor.permissions.filter((p) => !exec.permissions.includes(p))
      if (missing.length > 0) {
        this.completeFail(exec, { code: 'permission', message: `Missing permissions: ${missing.join(', ')}`, attempt: exec.attempts, kind: 'permission' })
        return
      }
    }

    this.transition(exec, 'running')
    this.publish('execution.running', exec)
    this.invokeHandler(exec)
  }

  private tickPreparing(exec: ExecutionResult): void {
    this.transition(exec, 'running')
    this.publish('execution.running', exec)
    this.invokeHandler(exec)
  }

  private tickRunning(exec: ExecutionResult, dtMs: number): void {
    exec.elapsedMs = (this.now() - exec.startedAt!)

    if (exec.cancelled) {
      this.completeCancel(exec)
      return
    }

    if (exec.options?.timeoutMs && exec.elapsedMs >= exec.options.timeoutMs) {
      this.completeFail(exec, { code: 'timeout', message: `Execution timed out after ${exec.options.timeoutMs}ms`, attempt: exec.attempts, kind: 'timeout' })
      return
    }
  }

  private tickWaiting(exec: ExecutionResult): void {
    if (exec.cancelled) {
      this.completeCancel(exec)
    }
  }

  private tickRetrying(exec: ExecutionResult, dtMs: number): void {
    const retryDelayMs = exec.options?.retryDelayMs ?? 0
    const remaining = (exec as unknown as { retryDelayRemainingMs?: number }).retryDelayRemainingMs ?? 0

    if (remaining <= 0 && retryDelayMs <= 0) {
      exec.attempts += 1
      this.transition(exec, 'preparing')
      this.publish('execution.preparing', exec)
      this.transition(exec, 'running')
      this.publish('execution.running', exec)
      this.invokeHandler(exec)
    } else {
      ;(exec as unknown as { retryDelayRemainingMs: number }).retryDelayRemainingMs = Math.max(0, remaining - dtMs)
    }
  }

  // --- Subscriptions --------------------------------------------------------

  subscribe(listener: (event: ExecutionEvent) => void): () => void {
    this.subscribers.add(listener)
    return () => {
      this.subscribers.delete(listener)
    }
  }

  // --- Internals ------------------------------------------------------------

  private invokeHandler(exec: ExecutionResult): void {
    const handler = this.invoker.resolve(exec.capabilityId)
    if (!handler) {
      console.error(`[ExecutionRuntime] No handler registered for ${exec.capabilityId}`)
      this.completeFail(exec, { code: 'capability-unavailable', message: `No handler registered for ${exec.capabilityId}`, attempt: exec.attempts, kind: 'capability-unavailable' })
      return
    }

    const request: ExecutionRequest = {
      capabilityId: exec.capabilityId,
      input: exec.input ?? null,
      context: {
        correlationId: exec.correlationId,
        grantedPermissions: exec.permissions,
        createdAt: exec.createdAt
      },
      id: exec.id,
      options: exec.options
    }

    const controls: ExecutionControls = {
      reportProgress: (p) => {
        if (isTerminal(exec.status)) return
        exec.progress = Math.max(0, Math.min(1, p))
        this.publish('execution.progress', exec)
      },
      succeed: (output) => {
        if (isTerminal(exec.status)) return
        exec.output = output
        exec.finishedAt = this.now()
        exec.durationMs = exec.finishedAt - exec.createdAt
        this.transition(exec, 'completed')
        this.addHistory(exec, 'completed')
        this.addAudit(exec, 'succeed', 'ok', `Completed in ${exec.durationMs.toFixed(1)}ms`)
        this.publish('execution.completed', exec)
      },
      fail: (error) => {
        if (isTerminal(exec.status)) return
        const err: ExecutionError = error instanceof Error
          ? { code: 'handler', message: error.message, attempt: exec.attempts, kind: 'handler' }
          : typeof error === 'string'
            ? { code: 'handler', message: error, attempt: exec.attempts, kind: 'handler' }
            : error
        console.error(`[ExecutionRuntime] Handler failed for ${exec.capabilityId}:`, err.message)
        this.completeFail(exec, err)
      },
      isCancelled: () => exec.cancelled,
      elapsedMs: () => (this.now() - (exec.startedAt ?? exec.createdAt))
    }

    try {
      console.log(`[ExecutionRuntime] Invoking handler for ${exec.capabilityId}`)
      const result = handler(request, request.context, controls)
      if (result && typeof result.then === 'function') {
        result.then(
          () => {
            // Handler explicitly called succeed/fail; no-op
          },
          (err) => {
            if (!isTerminal(exec.status)) {
              const msg = err instanceof Error ? err.message : String(err)
              console.error(`[ExecutionRuntime] Handler promise rejected for ${exec.capabilityId}:`, msg)
              this.completeFail(exec, { code: 'handler', message: msg, attempt: exec.attempts, kind: 'handler' })
            }
          }
        )
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      console.error(`[ExecutionRuntime] Handler threw for ${exec.capabilityId}:`, msg)
      this.completeFail(exec, { code: 'handler', message: msg, attempt: exec.attempts, kind: 'handler' })
    }
  }

  private completeFail(exec: ExecutionResult, error: ExecutionError): void {
    exec.error = error
    exec.finishedAt = this.now()
    exec.durationMs = exec.finishedAt - exec.createdAt
    this.transition(exec, 'failed')
    this.addHistory(exec, 'failed')
    this.addAudit(exec, 'fail', 'error', error.message)

    if (exec.options?.rollbackSupported) {
      this.invokeRollback(exec)
    } else {
      this.publish('execution.failed', exec)
    }
  }

  private completeCancel(exec: ExecutionResult): void {
    exec.error = { code: 'cancelled', message: 'Execution cancelled by caller', attempt: exec.attempts, kind: 'cancelled' }
    exec.finishedAt = this.now()
    exec.durationMs = exec.finishedAt - exec.createdAt
    this.transition(exec, 'cancelled')
    this.addHistory(exec, 'cancelled')
    this.addAudit(exec, 'cancel', 'info', 'Execution cancelled')
    this.publish('execution.cancelled', exec)

    if (exec.options?.rollbackSupported) {
      this.invokeRollback(exec)
    }
  }

  private invokeRollback(exec: ExecutionResult): boolean {
    const rollback = this.invoker.resolveRollback(exec.capabilityId)
    if (!rollback) {
      this.addAudit(exec, 'rollback', 'error', 'No rollback hook registered')
      this.publish('execution.failed', exec)
      return false
    }

    this.addAudit(exec, 'rollback', 'info', 'Rollback hook invoked')
    try {
      const ctx = {
        correlationId: exec.correlationId,
        grantedPermissions: exec.permissions,
        createdAt: exec.createdAt
      }
      const req = {
        capabilityId: exec.capabilityId,
        input: exec.input ?? null,
        context: ctx,
        id: exec.id,
        options: exec.options
      }
      rollback(req, ctx)
    } catch (err) {
      this.addAudit(exec, 'rollback', 'error', `Rollback hook failed: ${err instanceof Error ? err.message : String(err)}`)
      this.publish('execution.failed', exec)
      return false
    }

    exec.rolledBack = true
    this.transition(exec, 'rolledback')
    exec.finishedAt = this.now()
    exec.durationMs = exec.finishedAt - exec.createdAt
    this.addHistory(exec, 'rolledback')
    this.addAudit(exec, 'rollback', 'ok', 'Rollback completed')
    this.publish('execution.rolledback', exec)
    return true
  }

  private canCancel(exec: ExecutionResult): boolean {
    if (isTerminal(exec.status)) return false
    if (exec.options?.cancellable === false) return false
    return true
  }

  private transition(exec: ExecutionResult, to: ExecutionStatus): void {
    const from = exec.status
    if (from === to) return
    if (!canTransition(from, to)) {
      throw new Error(`Illegal execution transition: ${from} -> ${to}`)
    }
    exec.status = to
    this.revision += 1
    this.addAudit(exec, 'transition', 'info', `${from} -> ${to}`)
  }

  private cloneResult(exec: ExecutionResult): ExecutionResult {
    return {
      id: exec.id,
      capabilityId: exec.capabilityId,
      status: exec.status,
      output: exec.output,
      error: exec.error,
      progress: exec.progress,
      attempts: exec.attempts,
      correlationId: exec.correlationId,
      createdAt: exec.createdAt,
      startedAt: exec.startedAt,
      finishedAt: exec.finishedAt,
      durationMs: exec.durationMs,
      history: exec.history.map((h) => ({ ...h })),
      audit: exec.audit.map((a) => ({ ...a })),
      cancelled: exec.cancelled,
      rolledBack: exec.rolledBack,
      permissions: [...exec.permissions],
      tag: exec.tag,
      options: exec.options,
      elapsedMs: exec.elapsedMs,
      input: exec.input
    }
  }

  private addHistory(exec: ExecutionResult, status: ExecutionStatus): void {
    const now = this.now()
    const startedAt = exec.startedAt ?? exec.createdAt
    exec.history.push({
      attempt: exec.attempts,
      status,
      startedAt,
      finishedAt: now,
      durationMs: now - startedAt,
      error: exec.error?.message
    })
  }

  private addAudit(exec: ExecutionResult, action: string, outcome: ExecutionAuditEntry['outcome'], detail?: string): void {
    exec.audit.push({
      eventId: String(++this.eventSeq),
      timestamp: this.now(),
      action,
      outcome,
      detail
    })
  }

  private publish(type: ExecutionEventType, exec: ExecutionResult): void {
    const event: ExecutionEvent = {
      event_id: String(++this.eventSeq),
      timestamp: this.now(),
      source_runtime: 'execution',
      event_type: type,
      version: 1,
      priority: type === 'execution.failed' || type === 'execution.cancelled' ? 'high' : 'normal',
      data: { 
        executionId: exec.id, 
        status: exec.status, 
        capabilityId: exec.capabilityId, 
        progress: exec.progress,
        output: isTerminal(exec.status) ? exec.output : undefined,
        error: isTerminal(exec.status) ? exec.error : undefined,
        durationMs: exec.durationMs,
      },
      correlation_id: exec.correlationId
    }
    this.subscribers.forEach((l) => {
      try { l(event) } catch { /* subscriber errors must not break the tick */ }
    })
  }
}
