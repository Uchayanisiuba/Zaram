// desktop/src/runtime/cognitive/index.ts
//
// Milestone 1.2 — Cognitive Runtime barrel.
//
// The cognitive layer is the AI's internal state, independent of rendering.
// It is wired into PresenceRuntime (and consumed by CharacterRuntime) via DI;
// it never touches the renderer.

export {
  CognitiveRuntime
} from './types'
export type {
  CognitiveState,
  CognitiveEvent,
  CognitiveTask,
  PlanningState,
  KnowledgeRequest,
  MemoryRequest,
  ReasoningState,
  ConversationIntent
} from './types'

export {
  AttentionRuntime,
  attentionTargetFromCognitive
} from './attention-runtime'
export type {
  AttentionState,
  AttentionEvent,
  AttentionTarget
} from './attention-runtime'

export {
  RelationshipRuntime
} from './relationship-runtime'
export type {
  RelationshipState,
  RelationshipEvent,
  RelationshipRuntimeOptions
} from './relationship-runtime'

export type {
  MemoryProjection,
  RelevantMemory,
  MemorySummary,
  ConversationContext
} from './memory-projection'

export { CognitiveBundle } from './bundle'
export type { CognitiveBundleOptions } from './bundle'

export type {
  ConversationProjection,
  ThinkingState,
  SpeakingState,
  ListeningState,
  InterruptibleState
} from './conversation-projection'
export { projectConversation } from './conversation-projection'
