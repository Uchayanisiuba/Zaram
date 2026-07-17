// desktop/src/runtime/executive/types.ts
//
// Milestone 1.4 — Executive Runtime (Decision Engine) types.
//
// The Executive Runtime is the AI's executive control system. It coordinates
// every cognitive subsystem (Attention, Emotion, Behaviour, World, Memory,
// Relationship, Conversation) and is the SINGLE authority for high-level
// AI decision-making. It produces an ExecutiveState and a high-level Intent.
//
// This file is purely additive. It must NOT import the drawing layer, the body
// layer, concrete avatars, the character projection, the animation engine,
// frame snapshots, the orb drawing code, the desktop shell, any GPU/3D engine,
// or platform-specific graphics code.

// --- Focus -------------------------------------------------------------------

export type FocusTarget =
  | 'none'
  | 'conversation'
  | 'speaker'
  | 'memory'
  | 'knowledge'
  | 'world'
  | 'internal'
  | 'task'
  | 'automation'
  | 'tool'
  | 'plugin'
  | 'self'

// --- Priorities --------------------------------------------------------------

export type Priority = 'critical' | 'high' | 'normal' | 'low' | 'background'

// --- Interrupts --------------------------------------------------------------

export type InterruptSeverity = 'critical' | 'high' | 'medium' | 'low'

export interface Interrupt {
  id: string
  reason: string
  severity: InterruptSeverity
  // 0 (ignore) .. 1 (must handle immediately)
  salience: number
  // the subsystem that raised the interrupt
  source: string
  arrivedAt: number
  handled: boolean
}

export type InterruptState =
  | 'clear'
  | 'pending'
  | 'handling'
  | 'preempted'

// --- Reasoning / thinking modes ----------------------------------------------

export type ReasoningMode =
  | 'reactive'
  | 'deliberative'
  | 'reflective'
  | 'creative'
  | 'analytical'

export type ThinkingMode =
  | 'idle'
  | 'shallow'
  | 'deep'
  | 'continuous'

// --- The single high-level decision surface -----------------------------------

export type ExecutiveDecision =
  | 'reply'
  | 'wait'
  | 'listen'
  | 'continue-thinking'
  | 'look'
  | 'remember'
  | 'ignore'
  | 'interrupt-self'
  | 'cancel-task'
  | 'switch-context'
  | 'launch-automation'
  | 'call-tool'
  | 'ask-clarification'
  | 'be-proactive'

// --- Goal --------------------------------------------------------------------

export interface ExecutiveGoal {
  id: string
  label: string
  // 0 (low) .. 1 (critical)
  weight: number
  // ordered position in the stack (0 = current)
  order: number
  createdAt: number
  // explicit suspension flag (context switch without dropping the goal)
  suspended: boolean
  // true when explicitly switched-to (pinned to the top of the stack)
  pinned: boolean
}

// --- Intent (the only thing CharacterRuntime ever receives) ------------------

export interface ExecutiveIntent {
  // high-level action the AI should take now
  decision: ExecutiveDecision
  // what the AI is currently focused on
  focus: FocusTarget
  // 0 (distracted) .. 1 (locked in)
  focusStrength: number
  // 0 (uncertain) .. 1 (confident)
  confidence: number
  // 0 (calm) .. 1 (urgent)
  urgency: number
  // how strongly to pursue proactive behaviour
  proactivity: number
  // true when the AI should interrupt its current flow
  shouldInterrupt: boolean
  // a short human-readable note for diagnostics (never sent to the drawing layer)
  note: string
  // monotonically increasing revision
  revision: number
  updatedAt: number
}
