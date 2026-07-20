// desktop/src/capabilities/knowledge/knowledge-handler.ts
//
// Milestone 3.1 — Knowledge ExecutionHandler implementations.
//

import type { ExecutionRequest, ExecutionContext, ExecutionControls, ExecutionHandler } from '../../runtime/execution'
import type { KnowledgeHandlerContext } from './knowledge-types'

export function createKnowledgeHandlers(emit: (eventType: string, data: Record<string, unknown>) => void, recordOperation: (capabilityId: string) => void): KnowledgeHandlerContext {
  return { emit, recordOperation }
}

export function handleSearch(ctx: KnowledgeHandlerContext): ExecutionHandler {
  return async (req: ExecutionRequest, _context: ExecutionContext, controls: ExecutionControls) => {
    const query = typeof req.input === 'string' ? req.input : (req.input as any)?.query || ''
    const persona = (req.input as any)?.persona || 'zaram_prime'
    
    if (!query) {
      controls.fail({ code: 'validation_error', message: 'query is required', attempt: 0, kind: 'handler' })
      return
    }

    controls.reportProgress(0.1)
    ctx.recordOperation('knowledge.search')
    
    try {
      const response = await fetch(`http://127.0.0.1:8000/knowledge/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, persona }),
      })
      
      if (!response.ok) {
        controls.fail({ code: 'api_error', message: `Knowledge search failed: ${response.status}`, attempt: 0, kind: 'handler' })
        return
      }
      
      const data = await response.json()
      controls.reportProgress(1.0)
      controls.succeed(data)
    } catch (error) {
      controls.fail({ code: 'handler', message: String(error), attempt: 0, kind: 'handler' })
    }
  }
}
