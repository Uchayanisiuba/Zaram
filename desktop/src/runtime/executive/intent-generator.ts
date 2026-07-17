// desktop/src/runtime/executive/intent-generator.ts
//
// Milestone 1.4 — Intent Generator.
//
// The decision core. Given the resolved executive context (focus, priority,
// interrupts, goal, confidence, world salience, conversation phase), it decides
// the single high-level action the AI should take NOW and packages it into an
// ExecutiveIntent. This is the ONLY surface the body layer (CharacterRuntime)
// consumes; it never receives goals, planning, confidence, reasoning, memory,
// or relationship internals.

import {
  ExecutiveDecision,
  ExecutiveIntent,
  FocusTarget,
  Priority
} from './types'
import { defaultExecutiveState } from './executive-state'

export interface IntentContext {
  focus: FocusTarget
  focusStrength: number
  priority: Priority
  urgency: number
  confidence: number
  reasoningMode: string
  interrupting: boolean
  hasPendingTask: boolean
  goalActive: boolean
  // conversation phase from the source pipeline
  conversationPhase?: string
  // world notification salience (0..1)
  worldSalience?: number
  // relationship familiarity / interaction frequency (0..1) for proactivity
  proactivitySignal?: number
  // explicit "needs clarification" flag from upstream cognition
  needsClarification?: boolean
  // true when the AI is mid-plan and should continue
  inProgress?: boolean
}

export class IntentGenerator {
  private revision = 0
  private lastDecision: ExecutiveDecision = 'wait'

  reset(): void {
    this.revision = 0
    this.lastDecision = 'wait'
  }

  generate(ctx: IntentContext): ExecutiveIntent {
    const decision = this.decide(ctx)
    this.lastDecision = decision
    this.revision += 1

    const proactivity = this.computeProactivity(ctx)
    const focusStrength = clamp01(ctx.focusStrength)
    const confidence = clamp01(ctx.confidence)
    const urgency = clamp01(ctx.urgency)

    return {
      decision,
      focus: ctx.focus,
      focusStrength,
      confidence,
      urgency,
      proactivity,
      shouldInterrupt: ctx.interrupting || decision === 'interrupt-self',
      note: this.makeNote(decision, ctx),
      revision: this.revision,
      updatedAt: now()
    }
  }

  private decide(ctx: IntentContext): ExecutiveDecision {
    // 1. Hard interrupts always win: preempt the current flow.
    if (ctx.interrupting || ctx.priority === 'critical') {
      return 'interrupt-self'
    }
    // 2. Upstream asked for clarification.
    if (ctx.needsClarification) {
      return 'ask-clarification'
    }
    // 3. Mid-plan / working: keep thinking unless something blocks.
    if (ctx.inProgress && (ctx.conversationPhase === 'thinking' || ctx.conversationPhase === 'generating' || ctx.conversationPhase === 'working')) {
      return 'continue-thinking'
    }
    // 4. Conversation is expecting a reply.
    if (ctx.conversationPhase === 'listening') {
      return 'listen'
    }
    if (ctx.conversationPhase === 'speaking') {
      return 'reply'
    }
    // 5. Knowledge gap -> remember / look things up.
    if (ctx.focus === 'knowledge' || ctx.focus === 'memory') {
      return 'remember'
    }
    // 6. A pending task waits for a launch trigger.
    if (ctx.hasPendingTask && ctx.goalActive) {
      if (ctx.focus === 'automation') return 'launch-automation'
      if (ctx.focus === 'tool') return 'call-tool'
      return 'switch-context'
    }
    // 7. High world salience but not interrupting -> glance.
    if ((ctx.worldSalience ?? 0) > 0.4 && ctx.focus === 'world') {
      return 'look'
    }
    // 8. Idle but a goal exists -> be proactive about it.
    if (ctx.goalActive && (ctx.conversationPhase === 'idle' || ctx.conversationPhase === 'sleeping')) {
      if (ctx.proactivitySignal && ctx.proactivitySignal > 0.5) return 'be-proactive'
      return 'wait'
    }
    // 9. No goal, low salience -> idle wait.
    return 'wait'
  }

  private computeProactivity(ctx: IntentContext): number {
    const base = clamp01(ctx.proactivitySignal ?? 0)
    // Interrupts and urgency suppress proactivity (react instead of act).
    const suppress = clamp01(ctx.urgency) * 0.5 + (ctx.interrupting ? 0.3 : 0)
    return clamp01(base - suppress)
  }

  private makeNote(decision: ExecutiveDecision, ctx: IntentContext): string {
    const bits: string[] = [decision]
    if (ctx.focus !== 'none') bits.push(`focus=${ctx.focus}`)
    if (ctx.goalActive) bits.push('goal')
    if (ctx.interrupting) bits.push('interrupt')
    return bits.join(' ')
  }

  getLastDecision(): ExecutiveDecision {
    return this.lastDecision
  }
}

function clamp01(v: number): number {
  if (Number.isNaN(v)) return 0
  return Math.min(1, Math.max(0, v))
}

function now(): number {
  return typeof performance !== 'undefined' ? performance.now() : Date.now()
}

export { defaultExecutiveState }
