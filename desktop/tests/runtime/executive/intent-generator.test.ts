// desktop/tests/runtime/executive/intent-generator.test.ts
//
// Unit tests — Milestone 1.4 Intent Generator.
//
// Verifies that the decision core maps context to the correct high-level
// ExecutiveDecision and that it produces an Intent carrying only the high-level
// surface (no goals/planning/confidence-as-internal detail leaks beyond the
// defined Intent shape).

import { describe, it, expect } from 'vitest'
import { IntentGenerator } from '../../../src/runtime/executive/intent-generator'
import { ExecutiveIntent } from '../../../src/runtime/executive/types'

function base() {
  return {
    focus: 'none' as const,
    focusStrength: 0,
    priority: 'background' as const,
    urgency: 0,
    confidence: 0.5,
    reasoningMode: 'reactive',
    interrupting: false,
    hasPendingTask: false,
    goalActive: false,
    conversationPhase: 'idle',
    worldSalience: 0,
    proactivitySignal: 0,
    needsClarification: false,
    inProgress: false
  }
}

describe('Executive Intent Generator', () => {
  it('waits when idle with no goal', () => {
    const g = new IntentGenerator()
    const intent = g.generate(base())
    expect(intent.decision).toBe('wait')
    expectTypeShape(intent)
  })

  it('listens while the user is speaking (listening phase)', () => {
    const g = new IntentGenerator()
    const intent = g.generate({ ...base(), conversationPhase: 'listening' })
    expect(intent.decision).toBe('listen')
  })

  it('replies while speaking phase', () => {
    const g = new IntentGenerator()
    const intent = g.generate({ ...base(), conversationPhase: 'speaking' })
    expect(intent.decision).toBe('reply')
  })

  it('continues thinking while mid-plan', () => {
    const g = new IntentGenerator()
    const intent = g.generate({ ...base(), conversationPhase: 'thinking', inProgress: true })
    expect(intent.decision).toBe('continue-thinking')
  })

  it('asks clarification when upstream requests it', () => {
    const g = new IntentGenerator()
    const intent = g.generate({ ...base(), needsClarification: true })
    expect(intent.decision).toBe('ask-clarification')
  })

  it('interrupts self on critical priority', () => {
    const g = new IntentGenerator()
    const intent = g.generate({ ...base(), priority: 'critical', interrupting: true })
    expect(intent.decision).toBe('interrupt-self')
    expect(intent.shouldInterrupt).toBe(true)
  })

  it('launches automation when a pending automation task is active', () => {
    const g = new IntentGenerator()
    const intent = g.generate({
      ...base(),
      focus: 'automation',
      hasPendingTask: true,
      goalActive: true,
      conversationPhase: 'idle'
    })
    expect(intent.decision).toBe('launch-automation')
  })

  it('calls a tool when a pending tool task is active', () => {
    const g = new IntentGenerator()
    const intent = g.generate({
      ...base(),
      focus: 'tool',
      hasPendingTask: true,
      goalActive: true,
      conversationPhase: 'idle'
    })
    expect(intent.decision).toBe('call-tool')
  })

  it('is proactive about a goal when familiarity is high and idle', () => {
    const g = new IntentGenerator()
    const intent = g.generate({
      ...base(),
      goalActive: true,
      conversationPhase: 'idle',
      proactivitySignal: 0.9
    })
    expect(intent.decision).toBe('be-proactive')
  })

  it('monotonically increases revision across generations', () => {
    const g = new IntentGenerator()
    const a = g.generate(base())
    const b = g.generate(base())
    expect(b.revision).toBeGreaterThan(a.revision)
  })

  it('clamps confidence/urgency/focusStrength into [0,1]', () => {
    const g = new IntentGenerator()
    const intent = g.generate({ ...base(), confidence: 5, urgency: 5, focusStrength: 5 })
    expect(intent.confidence).toBeLessThanOrEqual(1)
    expect(intent.urgency).toBeLessThanOrEqual(1)
    expect(intent.focusStrength).toBeLessThanOrEqual(1)
  })
})

function expectTypeShape(i: ExecutiveIntent): void {
  expect(typeof i.decision).toBe('string')
  expect(typeof i.focus).toBe('string')
  expect(typeof i.focusStrength).toBe('number')
  expect(typeof i.confidence).toBe('number')
  expect(typeof i.urgency).toBe('number')
  expect(typeof i.proactivity).toBe('number')
  expect(typeof i.shouldInterrupt).toBe('boolean')
  expect(typeof i.note).toBe('string')
  expect(typeof i.revision).toBe('number')
  expect(typeof i.updatedAt).toBe('number')
}
