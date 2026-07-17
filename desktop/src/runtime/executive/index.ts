// desktop/src/runtime/executive/index.ts
//
// Milestone 1.4 — Executive Runtime barrel.
//
// The Executive Runtime is the AI's single authority for high-level decision
// making. It is wired into PresenceRuntime via DI (optional consumer) and into
// the existing 30Hz tick (no new timers). It never imports the drawing layer,
// the body layer, concrete avatars, the character projection, the animation
// engine, frame snapshots, the orb drawing code, the desktop shell, any GPU/3D
// engine, or platform-specific graphics code.

export { ExecutiveRuntime } from './executive-runtime'
export type {
  ExecutiveRuntimeOptions,
  ExecutiveSnapshot,
  ConversationSignal,
  MemorySignal,
  WorldSignal,
  AttentionSignal,
  RelationshipSignal,
  CognitiveSignal
} from './executive-runtime'

export { defaultExecutiveState, cloneExecutiveState } from './executive-state'
export type { ExecutiveState } from './executive-state'

export { GoalManager } from './goal-manager'
export type { GoalInput } from './goal-manager'

export { FocusManager } from './focus-manager'
export type { FocusInput } from './focus-manager'

export { InterruptManager } from './interrupt-manager'
export type { InterruptInput } from './interrupt-manager'

export { PriorityManager } from './priority-manager'
export type { PriorityInput } from './priority-manager'

export { IntentGenerator } from './intent-generator'
export type { IntentContext } from './intent-generator'

// Re-export the capability interface the executive depends on, so consumers can
// depend on the contract without importing the concrete capability module.
export type {
  ICapabilityRuntime,
  CapabilityQuery,
  CapabilityResolution
} from '../capability'

export type {
  ExecutiveGoal,
  ExecutiveIntent,
  ExecutiveDecision,
  FocusTarget,
  Priority,
  Interrupt,
  InterruptSeverity,
  InterruptState,
  ReasoningMode,
  ThinkingMode
} from './types'
