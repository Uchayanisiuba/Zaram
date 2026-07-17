// desktop/src/runtime/executive/goal-manager.ts
//
// Milestone 1.4 — Goal Manager.
//
// Owns goal lifecycle: adding, completing, suspending, resuming, and switching
// the current goal (goal stack). It is one of the Executive Runtime's private
// subsystems; nothing outside the executive touches goals directly.

import { ExecutiveGoal } from './types'
import { defaultExecutiveState } from './executive-state'

let _goalSeq = 0
function nextGoalId(): string {
  _goalSeq += 1
  return `goal-${Date.now().toString(36)}-${_goalSeq}`
}

export interface GoalInput {
  label: string
  weight?: number
  id?: string
}

export class GoalManager {
  private goals: ExecutiveGoal[] = []
  // An explicitly switched-to goal is pinned to the top of the stack until
  // another goal is switched to or it is completed.
  private pinnedId: string | null = null

  reset(): void {
    this.goals = []
    this.pinnedId = null
  }

  // Add a goal and keep the stack ordered by weight (desc) then recency.
  add(input: GoalInput): ExecutiveGoal {
    const goal: ExecutiveGoal = {
      id: input.id ?? nextGoalId(),
      label: input.label,
      weight: clamp01(input.weight ?? 0.5),
      order: this.goals.length,
      createdAt: now(),
      suspended: false,
      pinned: false
    }
    this.goals.push(goal)
    this.reorder()
    return goal
  }

  // Promote a goal to the top of the stack (context switch without dropping).
  switchTo(id: string): ExecutiveGoal | null {
    const goal = this.goals.find((g) => g.id === id)
    if (!goal) return null
    goal.suspended = false
    this.pinnedId = id
    this.reorder()
    return this.current()
  }

  // Temporarily move the current goal off the active path (context switch).
  suspendCurrent(): void {
    const cur = this.current()
    if (cur) cur.suspended = true
    this.reorder()
  }

  resume(id: string): void {
    const goal = this.goals.find((g) => g.id === id)
    if (goal) {
      goal.suspended = false
      this.pinnedId = id
    }
    this.reorder()
  }

  complete(id: string): void {
    this.goals = this.goals.filter((g) => g.id !== id)
    if (this.pinnedId === id) this.pinnedId = null
    this.reorder()
  }

  remove(id: string): void {
    this.complete(id)
  }

  has(id: string): boolean {
    return this.goals.some((g) => g.id === id)
  }

  // The active goal = highest-weight non-suspended goal.
  current(): ExecutiveGoal | null {
    return this.orbit()[0] ?? null
  }

  list(): ExecutiveGoal[] {
    return this.orbit().map((g) => ({ ...g }))
  }

  count(): number {
    return this.goals.length
  }

  // Active goals, pinned first, then highest weight first, suspended last.
  private orbit(): ExecutiveGoal[] {
    const pinned = this.pinnedId
    return [...this.goals].sort((a, b) => {
      const aPinned = pinned !== null && a.id === pinned
      const bPinned = pinned !== null && b.id === pinned
      if (aPinned !== bPinned) return aPinned ? -1 : 1
      if (a.suspended !== b.suspended) return a.suspended ? 1 : -1
      if (b.weight !== a.weight) return b.weight - a.weight
      return a.order - b.order
    })
  }

  private reorder(): void {
    const ordered = this.orbit()
    ordered.forEach((g, i) => {
      g.order = i
      g.pinned = this.pinnedId !== null && g.id === this.pinnedId
    })
    this.goals = ordered
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
