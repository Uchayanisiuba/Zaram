// desktop/src/runtime/execution/execution-context.ts
//
// Milestone 1.6 — Execution context & request helpers.
//
// Pure factory helpers for building ExecutionContext / ExecutionRequest with
// sensible defaults. No behaviour, no side effects, no forbidden imports.

import { ExecutionContext, ExecutionRequest } from './types'

let _seq = 0
function nextId(prefix: string): string {
  _seq += 1
  return `${prefix}-${Date.now().toString(36)}-${_seq.toString(36)}`
}

function now(): number {
  return typeof performance !== 'undefined' ? performance.now() : Date.now()
}

export function createContext(
  partial: Partial<ExecutionContext> & { correlationId?: string; grantedPermissions?: string[] }
): ExecutionContext {
  return {
    correlationId: partial.correlationId ?? nextId('corr'),
    grantedPermissions: partial.grantedPermissions ?? [],
    actor: partial.actor,
    parentId: partial.parentId,
    metadata: partial.metadata,
    priority: partial.priority ?? 0,
    createdAt: partial.createdAt ?? now()
  }
}

export function createRequest(
  capabilityId: string,
  input: unknown,
  partial: Partial<Omit<ExecutionRequest, 'capabilityId' | 'input'>> & {
    context?: Partial<ExecutionContext>
  } = {}
): ExecutionRequest {
  const ctxPartial = partial.context ?? {}
  return {
    capabilityId,
    input,
    context: createContext(ctxPartial),
    id: partial.id,
    options: partial.options
  }
}

export function newExecutionId(): string {
  return nextId('exec')
}

export { now as executionNow }
