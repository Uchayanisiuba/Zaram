// desktop/tests/runtime/executive/interrupt-manager.test.ts
//
// Unit tests — Milestone 1.4 Interrupt Manager.
//
// Verifies interrupt raising, severity/salience ordering, preemption threshold,
// handling, and that the manager reports whether the executive should interrupt
// itself.

import { describe, it, expect } from 'vitest'
import { InterruptManager } from '../../../src/runtime/executive/interrupt-manager'

describe('Executive Interrupt Manager', () => {
  it('raises an interrupt with derived salience from severity', () => {
    const m = new InterruptManager()
    const i = m.raise({ reason: 'doorbell', severity: 'high' })
    expect(i.severity).toBe('high')
    expect(i.salience).toBeCloseTo(0.75, 5)
    expect(i.handled).toBe(false)
  })

  it('orders pending interrupts by salience (highest first)', () => {
    const m = new InterruptManager()
    m.raise({ reason: 'a', salience: 0.2 })
    m.raise({ reason: 'b', salience: 0.9 })
    m.raise({ reason: 'c', salience: 0.5 })
    const pend = m.pendingSnapshot()
    expect(pend.map((p) => p.reason)).toEqual(['b', 'c', 'a'])
  })

  it('reports shouldPreempt when a pending interrupt exceeds the threshold', () => {
    const m = new InterruptManager()
    expect(m.shouldPreempt()).toBe(false)
    m.raise({ reason: 'low', salience: 0.3 })
    expect(m.shouldPreempt()).toBe(false)
    m.raise({ reason: 'big', salience: 0.9 })
    expect(m.shouldPreempt()).toBe(true)
  })

  it('respects a custom preempt threshold', () => {
    const m = new InterruptManager()
    m.setPreemptThreshold(0.9)
    m.raise({ reason: 'mid', salience: 0.7 })
    expect(m.shouldPreempt()).toBe(false)
  })

  it('handleTop clears the highest-salience interrupt and updates state', () => {
    const m = new InterruptManager()
    m.raise({ reason: 'a', salience: 0.2 })
    m.raise({ reason: 'b', salience: 0.9 })
    expect(m.getState()).toBe('pending')
    const handled = m.handleTop()
    expect(handled?.reason).toBe('b')
    expect(m.count()).toBe(1)
    expect(m.getState()).toBe('pending')
    m.handleTop()
    expect(m.getState()).toBe('clear')
  })

  it('clamps salience into [0,1]', () => {
    const m = new InterruptManager()
    const i = m.raise({ reason: 'x', salience: 5 })
    expect(i.salience).toBe(1)
  })

  it('reset clears pending interrupts', () => {
    const m = new InterruptManager()
    m.raise({ reason: 'x' })
    m.reset()
    expect(m.count()).toBe(0)
    expect(m.getState()).toBe('clear')
  })
})
