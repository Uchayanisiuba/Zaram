// desktop/tests/runtime/executive/benchmarks.test.ts
//
// Performance benchmarks — Milestone 1.4 Executive Runtime.
//
// Run with the existing vitest suite (no new tooling). Asserts that 10,000
// updates complete well under 100ms and that the decision pipeline is cheap
// enough to run every 30Hz frame. Also asserts the structural contract: no
// setInterval / setTimeout / requestAnimationFrame / polling loops.

import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { ExecutiveRuntime } from '../../../src/runtime/executive'

function nowMs(): number {
  return performance.now()
}

describe('Executive Runtime — performance benchmarks', () => {
  it('executes 10,000 updates in under 100ms', () => {
    const e = new ExecutiveRuntime({ now: () => 0 })
    e.addGoal({ label: 'reply', weight: 0.8 })
    e.ingestConversation({ phase: 'thinking' })
    e.ingestAttention({ confidence: 0.7 })
    // Seed once so the measured window is the steady-state decision pipeline.
    e.update(1 / 30)

    const N = 10000
    const t0 = nowMs()
    for (let i = 0; i < N; i++) {
      e.update(1 / 30)
    }
    const t1 = nowMs()
    const elapsed = t1 - t0
    // eslint-disable-next-line no-console
    console.log(`[bench] executive 10000 updates in ${elapsed.toFixed(2)}ms`)
    expect(elapsed).toBeLessThan(100)
  })

  it('sustains 30Hz decision updates within frame budget', () => {
    const e = new ExecutiveRuntime({ now: () => 0 })
    e.addGoal({ label: 'g', weight: 0.5 })
    const frames = 30
    const dt = 1 / 30
    const t0 = nowMs()
    for (let i = 0; i < frames; i++) {
      e.ingestConversation({ phase: 'thinking' })
      e.update(dt)
    }
    const t1 = nowMs()
    const perFrame = (t1 - t0) / frames
    // eslint-disable-next-line no-console
    console.log(`[bench] executive.update avg ${perFrame.toFixed(5)}ms/frame @30Hz`)
    expect(perFrame).toBeLessThan(1)
  })

  it('handles 10,000 interrupt raises + handles under budget', () => {
    const e = new ExecutiveRuntime({ now: () => 0 })
    const t0 = nowMs()
    for (let i = 0; i < 10000; i++) {
      e.raiseInterrupt({ reason: `r${i}`, severity: 'medium' })
      e.handleTopInterrupt()
    }
    const t1 = nowMs()
    const elapsed = t1 - t0
    // eslint-disable-next-line no-console
    console.log(`[bench] executive 10000 interrupt cycles in ${elapsed.toFixed(2)}ms`)
    expect(elapsed).toBeLessThan(100)
  })

  it('does not introduce timers, RAF, or polling loops in the executive module', () => {
    const dir = join(__dirname, '..', '..', '..', 'src', 'runtime', 'executive')
    const files = [
      'index.ts',
      'types.ts',
      'executive-state.ts',
      'executive-runtime.ts',
      'goal-manager.ts',
      'focus-manager.ts',
      'interrupt-manager.ts',
      'priority-manager.ts',
      'intent-generator.ts'
    ]
    for (const f of files) {
      const src = readFileSync(join(dir, f), 'utf8')
      expect(src).not.toMatch(/setInterval\s*\(/)
      expect(src).not.toMatch(/setTimeout\s*\(/)
      expect(src).not.toMatch(/requestAnimationFrame\s*\(/)
      expect(src).not.toMatch(/while\s*\(/)
      expect(src).not.toMatch(/for\s*\(;;/)
    }
  })
})
