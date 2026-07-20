// desktop/src/capabilities/knowledge/knowledge-types.ts
//
// Milestone 3.1 — Knowledge Capability Pack types.
//

export interface KnowledgeHandlerContext {
  emit: (eventType: string, data: Record<string, unknown>) => void
  recordOperation: (capabilityId: string) => void
}

export interface KnowledgeMetrics {
  operationsExecuted: number
  searchCount: number
}

export const DEFAULT_KNOWLEDGE_METRICS: KnowledgeMetrics = {
  operationsExecuted: 0,
  searchCount: 0,
}
