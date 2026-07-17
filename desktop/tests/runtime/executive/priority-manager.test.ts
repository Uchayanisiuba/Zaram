// desktop/tests/runtime/executive/priority-manager.test.ts
//
// Unit tests — Milestone 1.4 Priority Manager.
//
// Verifies urgency computation (interrupts dominate), priority banding, and the
// combined resolve() helper.

import { describe, it, expect } from 'vitest'
import { PriorityManager } from '../../../src/runtime/executive/priority-manager'

describe('Executive Priority Manager', () => {
  it('computes higher urgency for interrupts than for goals', () => {
    const m = new PriorityManager()
    const fromGoal = m.computeUrgency({ goalWeight: 0.9, interruptSalience: 0 })
    const fromInterrupt = m.computeUrgency({ goalWeight: 0.1, interruptSalience: 0.9 })
    expect(fromInterrupt).toBeGreaterThan(fromGoal)
  })

  it('bands urgency into discrete priority levels', () => {
    const m = new PriorityManager()
    expect(m.band(0)).toBe('background')
    expect(m.band(0.15)).toBe('low')
    expect(m.band(0.35)).toBe('normal')
    expect(m.band(0.6)).toBe('high')
    expect(m.band(0.95)).toBe('critical')
  })

  it('resolves an interrupt-driven context as critical', () => {
    const m = new PriorityManager()
    const { priority, urgency } = m.resolve({ goalWeight: 0.3, interruptSalience: 0.9 })
    expect(priority).toBe('critical')
    expect(urgency).toBeGreaterThanOrEqual(0.8)
  })

  it('resolves a low-salience idle context as background', () => {
    const m = new PriorityManager()
    const { priority, urgency } = m.resolve({ goalWeight: 0, interruptSalience: 0, worldSalience: 0 })
    expect(priority).toBe('background')
    expect(urgency).toBeLessThan(0.1)
  })

  it('clamps out-of-range inputs', () => {
    const m = new PriorityManager()
    const { urgency } = m.resolve({ goalWeight: 5, interruptSalience: 5 })
    expect(urgency).toBeLessThanOrEqual(1)
  })
})
