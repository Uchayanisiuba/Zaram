// desktop/src/runtime/executive/focus-manager.ts
//
// Milestone 1.4 — Focus Manager.
//
// Owns where the AI's attention/effort is directed and how strongly. It resolves
// focus transitions based on the active goal, conversation phase, world
// salience, and interrupts. It is a private subsystem of the Executive Runtime.

import { FocusTarget } from './types'

export interface FocusInput {
  goalFocus?: FocusTarget
  conversationPhase?: string
  worldSalience?: number
  interrupting?: boolean
}

export class FocusManager {
  private current: FocusTarget = 'none'
  private strength = 0
  private target: FocusTarget = 'none'
  private targetStrength = 0

  reset(): void {
    this.current = 'none'
    this.strength = 0
    this.target = 'none'
    this.targetStrength = 0
  }

  // Select a target focus + strength from the current context.
  select(input: FocusInput): { focus: FocusTarget; strength: number } {
    let focus: FocusTarget = 'none'
    let strength = 0.2

    if (input.interrupting) {
      focus = 'world'
      strength = clamp01(input.worldSalience ?? 0.8)
    } else if (input.conversationPhase === 'listening') {
      focus = 'speaker'
      strength = 0.7
    } else if (input.conversationPhase === 'speaking') {
      focus = 'conversation'
      strength = 0.7
    } else if (input.conversationPhase === 'thinking' || input.conversationPhase === 'generating' || input.conversationPhase === 'working') {
      focus = input.goalFocus ?? 'internal'
      strength = 0.6
    } else if (input.conversationPhase === 'interrupted') {
      focus = 'world'
      strength = clamp01(input.worldSalience ?? 0.8)
    } else if (input.goalFocus) {
      focus = input.goalFocus
      strength = 0.5
    }

    this.target = focus
    this.targetStrength = strength
    return { focus, strength: strength }
  }

  // Ease current focus strength toward the target. No timers: called from the
  // existing 30Hz tick via ExecutiveRuntime.update().
  ease(dt: number): { focus: FocusTarget; strength: number } {
    const k = clamp01(dt * 4)
    this.strength += (this.targetStrength - this.strength) * k
    // Snap focus label immediately when target differs and strength is low
    // (avoid mid-strength flicker to a new target).
    if (this.current !== this.target && this.strength < 0.3) {
      this.current = this.target
    } else if (this.current === this.target) {
      this.current = this.target
    }
    return { focus: this.current, strength: this.strength }
  }

  getFocus(): FocusTarget {
    return this.current
  }

  getStrength(): number {
    return this.strength
  }
}

function clamp01(v: number): number {
  if (Number.isNaN(v)) return 0
  return Math.min(1, Math.max(0, v))
}
