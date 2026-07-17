// desktop/tests/runtime/executive/goal-manager.test.ts
//
// Unit tests — Milestone 1.4 Goal Manager.
//
// Verifies goal addition, ordering by weight, goal switching (context switch),
// suspension/resume, completion, and that the current goal is the highest-weight
// non-suspended goal.

import { describe, it, expect } from 'vitest'
import { GoalManager } from '../../../src/runtime/executive/goal-manager'

describe('Executive Goal Manager', () => {
  it('adds goals and exposes them via list()', () => {
    const m = new GoalManager()
    const a = m.add({ label: 'learn', weight: 0.3 })
    const b = m.add({ label: 'reply', weight: 0.6 })
    expect(m.count()).toBe(2)
    // list() is ordered by weight (highest first), not insertion order.
    expect(m.list().map((g) => g.id)).toEqual([b.id, a.id])
  })

  it('keeps the stack ordered by weight (current = highest weight, non-suspended)', () => {
    const m = new GoalManager()
    m.add({ label: 'low', weight: 0.2 })
    const high = m.add({ label: 'high', weight: 0.9 })
    m.add({ label: 'mid', weight: 0.5 })
    const cur = m.current()
    expect(cur?.id).toBe(high.id)
    expect(m.list()[0].id).toBe(high.id)
  })

  it('switches the current goal (context switch) by id', () => {
    const m = new GoalManager()
    const a = m.add({ label: 'A', weight: 0.2 })
    const b = m.add({ label: 'B', weight: 0.9 })
    expect(m.current()?.id).toBe(b.id)
    m.switchTo(a.id)
    expect(m.current()?.id).toBe(a.id)
  })

  it('suspends the current goal and promotes the next active goal', () => {
    const m = new GoalManager()
    const a = m.add({ label: 'A', weight: 0.9 })
    const b = m.add({ label: 'B', weight: 0.5 })
    expect(m.current()?.id).toBe(a.id)
    m.suspendCurrent()
    expect(m.current()?.id).toBe(b.id)
    // a is still present, just suspended
    expect(m.has(a.id)).toBe(true)
  })

  it('resumes a suspended goal back to the active path', () => {
    const m = new GoalManager()
    const a = m.add({ label: 'A', weight: 0.9 })
    m.add({ label: 'B', weight: 0.5 })
    m.suspendCurrent()
    m.resume(a.id)
    expect(m.current()?.id).toBe(a.id)
  })

  it('completes a goal and removes it from the stack', () => {
    const m = new GoalManager()
    const a = m.add({ label: 'A', weight: 0.9 })
    m.add({ label: 'B', weight: 0.5 })
    m.complete(a.id)
    expect(m.has(a.id)).toBe(false)
    expect(m.count()).toBe(1)
  })

  it('clamps goal weight into [0,1]', () => {
    const m = new GoalManager()
    const g = m.add({ label: 'x', weight: 5 })
    expect(g.weight).toBe(1)
    const h = m.add({ label: 'y', weight: -1 })
    expect(h.weight).toBe(0)
  })

  it('reset clears all goals', () => {
    const m = new GoalManager()
    m.add({ label: 'x' })
    m.reset()
    expect(m.count()).toBe(0)
    expect(m.current()).toBeNull()
  })
})
