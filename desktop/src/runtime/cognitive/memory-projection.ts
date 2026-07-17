// desktop/src/runtime/cognitive/memory-projection.ts
//
// PART 4 — Memory Projection (interfaces only)
//
// The Memory Runtime is NOT modified. These are projection interfaces that read
// the Memory Runtime's snapshot and project it into the cognitive layer's view.
// No implementation here — only the contracts future/projected adapters satisfy.

import type { MemorySnapshot } from '../sources/types'

// A single memory deemed relevant to the current context.
export interface RelevantMemory {
  id: string
  // short textual summary used by cognition (never the raw store)
  summary: string
  // 0..1 relevance to the active conversation
  relevance: number
  // 0..1 recency
  recency: number
  // tags for grouping
  tags: string[]
}

// Aggregate summary of memory state for the cognitive layer.
export interface MemorySummary {
  // count of memories available
  count: number
  // 0..1 overall recall readiness
  recall: number
  // 0..1 current activity
  activity: number
  // the most relevant items right now
  relevant: RelevantMemory[]
}

// The conversational context assembled from memory + recent turns.
export interface ConversationContext {
  // rolling summary of the current conversation
  summary: string
  // recent participant ids in order
  participants: string[]
  // key topics extracted
  topics: string[]
  // number of turns observed
  turnCount: number
}

// The projection contract: turns a Memory Runtime snapshot (+ optional richer
// source) into the cognitive view. Implementations are injected; the interface
// keeps the cognitive layer decoupled from the memory store internals.
export interface MemoryProjection {
  project(snapshot: MemorySnapshot): MemorySummary
  buildContext(snapshot: MemorySnapshot, turns: ConversationContext): ConversationContext
  rankRelevant(snapshot: MemorySnapshot, limit?: number): RelevantMemory[]
}
