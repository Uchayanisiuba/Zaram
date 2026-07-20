// desktop/src/capabilities/knowledge/knowledge-capability.ts
//
// Milestone 3.1 — Knowledge Capability Pack.
//
// Implements ICapabilityPack. Registers knowledge capability descriptors
// with the Capability Runtime and handlers with the Execution Invoker.
// Internet search is opt-in via the backend /knowledge/search endpoint.
// If unavailable, Executive Runtime falls back to local reasoning.

import type { ICapabilityRuntime } from '../../runtime/capability'
import type { IExecutionInvoker, ExecutionHandler, ExecutionRollback } from '../../runtime/execution'
import type { KnowledgeHandlerContext, KnowledgeMetrics } from './knowledge-types'
import { handleSearch, createKnowledgeHandlers } from './knowledge-handler'

const KNOWLEDGE_CAPABILITIES: Array<{
  id: string
  name: string
  description: string
  category: 'ai'
  permissions: string[]
  latencyEstimateMs: number
}> = [
  {
    id: 'knowledge.search',
    name: 'Search Internet',
    description: 'Search the internet for current information',
    category: 'ai',
    permissions: ['knowledge:search', 'internet:access'],
    latencyEstimateMs: 2000,
  },
]

export const DEFAULT_KNOWLEDGE_METRICS: KnowledgeMetrics = {
  operationsExecuted: 0,
  searchCount: 0,
}

export class KnowledgeCapabilityPack {
  private readonly subscribers = new Set<(event: { eventType: string; data: Record<string, unknown> }) => void>()
  private readonly metrics: KnowledgeMetrics = { ...DEFAULT_KNOWLEDGE_METRICS }

  constructor(private readonly capabilityRuntime: ICapabilityRuntime) {}

  getMetrics(): KnowledgeMetrics {
    return { ...this.metrics }
  }

  recordOperation(capabilityId: string): void {
    this.metrics.operationsExecuted += 1
    if (capabilityId === 'knowledge.search') this.metrics.searchCount += 1
  }

  registerHandlers(invoker: IExecutionInvoker): void {
    const emit = (eventType: string, data: Record<string, unknown>) => {
      this.publish(eventType, data)
    }
    const ctx = createKnowledgeHandlers(emit, (capabilityId) => this.recordOperation(capabilityId))

    invoker.register('knowledge.search', wrapHandler(ctx, handleSearch(ctx)))
  }

  registerDescriptors(capabilityRuntime: ICapabilityRuntime): void {
    for (const cap of KNOWLEDGE_CAPABILITIES) {
      capabilityRuntime.register({
        id: cap.id,
        name: cap.name,
        description: cap.description,
        category: cap.category,
        permissions: cap.permissions as any,
        inputSchema: { type: 'object', properties: { query: { type: 'string' } }, required: ['query'] },
        outputSchema: { type: 'object', properties: { results: { type: 'array' } } },
        availability: 'available',
        latencyEstimateMs: cap.latencyEstimateMs,
        location: 'cloud',
        cost: 0,
        enabled: true,
        source: 'knowledge-pack',
        tags: ['knowledge', 'internet', 'search']
      })
    }
  }

  subscribe(listener: (event: { eventType: string; data: Record<string, unknown> }) => void): () => void {
    this.subscribers.add(listener)
    return () => { this.subscribers.delete(listener) }
  }

  private publish(eventType: string, data: Record<string, unknown>): void {
    for (const listener of this.subscribers) {
      try { listener({ eventType, data }) } catch { /* subscriber errors must not break operations */ }
    }
  }
}

function wrapHandler(ctx: KnowledgeHandlerContext, handler: ExecutionHandler): ExecutionHandler {
  return (req, c, controls) => {
    const result = handler(req, c, controls)
    if (result && typeof result.then === 'function') {
      return result.then((res) => {
        ctx.recordOperation(req.capabilityId)
        return res
      }).catch(() => {
        ctx.recordOperation(req.capabilityId)
      })
    }
    ctx.recordOperation(req.capabilityId)
    return result
  }
}

export function buildKnowledgeRollback(): ExecutionRollback {
  return (_req, _ctx) => {
    // Knowledge operations are read-only; no rollback needed.
  }
}
