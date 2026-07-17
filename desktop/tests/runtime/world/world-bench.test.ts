// desktop/tests/runtime/world/world-bench.ts
//
// Performance benchmarks — Milestone 1.3 World Runtime.
//
// These are run with the existing vitest suite (no new tooling). They assert
// that the World Runtime is cheap enough to be advanced every 30Hz frame and
// that read-only snapshot production stays sub-millisecond. They also assert
// the design contract: no setInterval / setTimeout / requestAnimationFrame are
// introduced by the world module.

import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { WorldRuntime } from '../../../src/runtime/world'

function nowNs(): number {
  // High-resolution timing via performance.now() (ms, fractional).
  return performance.now()
}

describe('World Runtime — performance benchmarks', () => {
  it('produces an immutable snapshot well under 1ms (p50 over 1000 reads)', () => {
    const w = new WorldRuntime()
    w.setSystem({ load: 0.5 })
    w.setEnvironment({ isForeground: false })
    w.deliverNotification({ id: 'n1', title: 't', severity: 0.7 })

    const N = 1000
    const times: number[] = []
    for (let i = 0; i < N; i++) {
      const t0 = nowNs()
      const s = w.getWorldState()
      const t1 = nowNs()
      // Touch the snapshot to prevent dead-code elimination.
      void s.revision
      void s.notification.active.length
      times.push(t1 - t0)
    }
    times.sort((a, b) => a - b)
    const p50 = times[Math.floor(N * 0.5)]
    const p99 = times[Math.floor(N * 0.99)]
    // eslint-disable-next-line no-console
    console.log(`[bench] getWorldState p50=${p50.toFixed(4)}ms p99=${p99.toFixed(4)}ms`)
    expect(p50).toBeLessThan(1)
    expect(p99).toBeLessThan(5)
  })

  it('sustains 30Hz advance (update) within frame budget', () => {
    const w = new WorldRuntime({ notificationDecayPerSec: 0.4 })
    w.deliverNotification({ id: 'n1', title: 't', severity: 1 })

    // One second of 30Hz frames.
    const frames = 30
    const dt = 1 / 30
    const t0 = nowNs()
    for (let i = 0; i < frames; i++) w.update(dt)
    const t1 = nowNs()
    const perFrame = (t1 - t0) / frames
    // eslint-disable-next-line no-console
    console.log(`[bench] world.update avg ${perFrame.toFixed(5)}ms/frame @30Hz`)
    expect(perFrame).toBeLessThan(1)
  })

  it('handles high-frequency perception ingestion (10000 events < 150ms)', () => {
    const w = new WorldRuntime()
    const t0 = nowNs()
    for (let i = 0; i < 10000; i++) {
      w.setSystem({ load: (i % 100) / 100 })
      w.setEnvironment({ occlusion: (i % 100) / 100 })
    }
    const t1 = nowNs()
    const elapsed = t1 - t0
    // eslint-disable-next-line no-console
    console.log(`[bench] 10000 perception writes in ${elapsed.toFixed(2)}ms`)
    expect(elapsed).toBeLessThan(150)
  })

  it('does not introduce timers, RAF, or polling loops in the world module', () => {
    const dir = join(__dirname, '..', '..', '..', 'src', 'runtime', 'world')
    const files = ['index.ts', 'types.ts', 'world-runtime.ts']
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
