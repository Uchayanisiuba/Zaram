// desktop/tests/runtime/executive/focus-manager.test.ts
//
// Unit tests — Milestone 1.4 Focus Manager.
//
// Verifies focus selection from conversation phase / goal / world, focus
// transitions, and that strength eases toward the target on the existing tick
// (no timers).

import { describe, it, expect } from 'vitest'
import { FocusManager } from '../../../src/runtime/executive/focus-manager'

describe('Executive Focus Manager', () => {
  it('selects focus from conversation phase', () => {
    const m = new FocusManager()
    expect(m.select({ conversationPhase: 'listening' }).focus).toBe('speaker')
    expect(m.select({ conversationPhase: 'speaking' }).focus).toBe('conversation')
    expect(m.select({ conversationPhase: 'thinking', goalFocus: 'memory' }).focus).toBe('memory')
  })

  it('defers to goal focus when idle', () => {
    const m = new FocusManager()
    const sel = m.select({ conversationPhase: 'idle', goalFocus: 'task' })
    expect(sel.focus).toBe('task')
  })

  it('prioritises world focus during an interrupt', () => {
    const m = new FocusManager()
    const sel = m.select({ conversationPhase: 'speaking', interrupting: true, worldSalience: 0.9 })
    expect(sel.focus).toBe('world')
    expect(sel.strength).toBeGreaterThan(0.5)
  })

  it('eases strength toward the target over ticks (no timers)', () => {
    const m = new FocusManager()
    m.select({ conversationPhase: 'listening' })
    const start = m.getStrength()
    // ~0.5s of 30Hz frames.
    for (let i = 0; i < 15; i++) m.ease(1 / 30)
    const end = m.getStrength()
    expect(end).toBeGreaterThan(start)
    expect(end).toBeLessThanOrEqual(1)
  })

  it('snaps focus label when strength is low and target differs', () => {
    const m = new FocusManager()
    m.select({ conversationPhase: 'idle', goalFocus: 'task' })
    m.ease(1 / 30)
    expect(m.getFocus()).toBe('task')
  })
})
