// desktop/src/runtime/execution/execution-invoker.ts
//
// Milestone 1.6 — Execution invoker registry.
//
// The Execution Runtime is the ONLY runtime permitted to invoke capabilities.
// Concrete capability implementations are wrapped by ExecutionHandlers and
// registered here. The registry is injected into the runtime via DI (an
// interface), keeping the runtime decoupled from concrete capability code.
//
// This is the single sanctioned bridge between "an execution request" and "a
// capability actually running". The Capability Runtime (metadata) and the
// Executive Runtime (decisions) never touch handlers.

import { ExecutionHandler, ExecutionRollback } from './types'

export interface IExecutionInvoker {
  // Register a handler for a capability id.
  register(capabilityId: string, handler: ExecutionHandler): void
  // Register (or replace) a handler + optional rollback hook.
  registerWithRollback(capabilityId: string, handler: ExecutionHandler, rollback?: ExecutionRollback): void
  // True when a handler exists for the capability id.
  has(capabilityId: string): boolean
  // Resolve the handler for a capability id (or undefined).
  resolve(capabilityId: string): ExecutionHandler | undefined
  // Resolve the rollback hook for a capability id (or undefined).
  resolveRollback(capabilityId: string): ExecutionRollback | undefined
  // Remove a handler.
  unregister(capabilityId: string): boolean
  // Number of registered handlers (diagnostics).
  count(): number
  reset(): void
}

export class ExecutionInvoker implements IExecutionInvoker {
  private readonly handlers = new Map<string, ExecutionHandler>()
  private readonly rollbacks = new Map<string, ExecutionRollback>()

  register(capabilityId: string, handler: ExecutionHandler): void {
    this.handlers.set(capabilityId, handler)
  }

  registerWithRollback(capabilityId: string, handler: ExecutionHandler, rollback?: ExecutionRollback): void {
    this.handlers.set(capabilityId, handler)
    if (rollback) this.rollbacks.set(capabilityId, rollback)
  }

  has(capabilityId: string): boolean {
    return this.handlers.has(capabilityId)
  }

  resolve(capabilityId: string): ExecutionHandler | undefined {
    return this.handlers.get(capabilityId)
  }

  resolveRollback(capabilityId: string): ExecutionRollback | undefined {
    return this.rollbacks.get(capabilityId)
  }

  unregister(capabilityId: string): boolean {
    const had = this.handlers.delete(capabilityId)
    this.rollbacks.delete(capabilityId)
    return had
  }

  count(): number {
    return this.handlers.size
  }

  reset(): void {
    this.handlers.clear()
    this.rollbacks.clear()
  }
}
