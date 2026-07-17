// desktop/src/runtime/executive/priority-manager.ts
//
// Milestone 1.4 — Priority Manager.
//
// Resolves the current activity's priority band and an absolute urgency scalar
// from goal weight, interrupt salience, and world context. It is a private
// subsystem of the Executive Runtime.

import { Priority } from './types'

export interface PriorityInput {
  goalWeight?: number
  interruptSalience?: number
  worldSalience?: number
  confidence?: number
}

export class PriorityManager {
  // Combine signals into a single 0..1 urgency scalar.
  computeUrgency(input: PriorityInput): number {
    const goal = clamp01(input.goalWeight ?? 0.3)
    const interrupt = clamp01(input.interruptSalience ?? 0)
    const world = clamp01(input.worldSalience ?? 0)
    // Interrupts dominate urgency; a full-salience interrupt drives urgency to
    // its max. Goal and world add weight beneath that ceiling.
    const base = clamp01(goal * 0.25 + world * 0.15)
    const urgency = clamp01(Math.max(interrupt, base))
    return urgency
  }

  // Map an urgency scalar to a discrete priority band.
  band(urgency: number): Priority {
    if (urgency >= 0.8) return 'critical'
    if (urgency >= 0.55) return 'high'
    if (urgency >= 0.3) return 'normal'
    if (urgency >= 0.1) return 'low'
    return 'background'
  }

  resolve(input: PriorityInput): { priority: Priority; urgency: number } {
    const urgency = this.computeUrgency(input)
    return { priority: this.band(urgency), urgency }
  }
}

function clamp01(v: number): number {
  if (Number.isNaN(v)) return 0
  return Math.min(1, Math.max(0, v))
}
