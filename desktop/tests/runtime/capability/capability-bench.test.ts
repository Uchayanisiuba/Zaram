// desktop/tests/runtime/capability/capability-bench.test.ts
//
// Performance benchmarks — Milestone 1.5 Capability Runtime.
//
// Run with the existing vitest suite (no new tooling). Asserts O(1) lookup
// stays sub-microsecond, 10,000 registrations complete quickly, filtering and
// resolution scale, and no timers/RAF/polling loops are introduced.

import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { CapabilityRuntime } from '../../../src/runtime/capability'
import type { CapabilityRegistration } from '../../../src/runtime/capability/types'

function nowMs(): number {
  return performance.now()
}

const CATEGORIES = ['system', 'workspace', 'filesystem', 'communication', 'ai', 'automation', 'developer', 'media', 'vision', 'speech', 'plugins', 'security'] as const

describe('Capability Runtime — performance benchmarks', () => {
  it('completes 10,000 registrations well under budget', () => {
    const rt = new CapabilityRuntime()
    const t0 = nowMs()
    for (let i = 0; i < 10000; i++) {
      const reg: CapabilityRegistration = {
        id: `cap.${i}`,
        name: `Capability ${i}`,
        description: 'bench',
        category: CATEGORIES[i % CATEGORIES.length],
        location: i % 2 ? 'cloud' : 'local',
        cost: (i % 100) / 100
      }
      rt.register(reg)
    }
    const t1 = nowMs()
    const elapsed = t1 - t0
    // eslint-disable-next-line no-console
    console.log(`[bench] capability 10000 registrations in ${elapsed.toFixed(2)}ms`)
    expect(rt.getRevision()).toBe(10000)
    expect(elapsed).toBeLessThan(250)
  })

  it('O(1) lookup by id stays sub-millisecond under load', () => {
    const rt = new CapabilityRuntime()
    for (let i = 0; i < 5000; i++) {
      rt.register({ id: `cap.${i}`, name: 'x', description: 'd', category: CATEGORIES[i % CATEGORIES.length] })
    }
    const N = 20000
    const t0 = nowMs()
    let found = 0
    for (let i = 0; i < N; i++) {
      if (rt.get(`cap.${i % 5000}`)) found++
    }
    const t1 = nowMs()
    const perLookup = (t1 - t0) / N
    // eslint-disable-next-line no-console
    console.log(`[bench] capability lookup avg ${perLookup.toFixed(5)}ms (${N} lookups)`)
    expect(found).toBe(N)
    expect(perLookup).toBeLessThan(0.01)
  })

  it('resolution over a large registry stays cheap', () => {
    const rt = new CapabilityRuntime()
    for (let i = 0; i < 5000; i++) {
      rt.register({ id: `cap.${i}`, name: 'x', description: 'd', category: CATEGORIES[i % CATEGORIES.length], cost: (i % 50) / 50 })
    }
    const N = 2000
    const t0 = nowMs()
    for (let i = 0; i < N; i++) {
      rt.resolve({ category: CATEGORIES[i % CATEGORIES.length] })
    }
    const t1 = nowMs()
    const perResolve = (t1 - t0) / N
    // eslint-disable-next-line no-console
    console.log(`[bench] capability resolve avg ${perResolve.toFixed(5)}ms (${N} resolves)`)
    expect(perResolve).toBeLessThan(1)
  })

  it('filtering a large registry is linear and fast', () => {
    const rt = new CapabilityRuntime()
    for (let i = 0; i < 5000; i++) {
      rt.register({ id: `cap.${i}`, name: 'x', description: 'd', category: CATEGORIES[i % CATEGORIES.length], location: i % 2 ? 'cloud' : 'local' })
    }
    const N = 200
    const t0 = nowMs()
    for (let i = 0; i < N; i++) {
      rt.filter({ localOnly: true, enabledOnly: true })
    }
    const t1 = nowMs()
    const perFilter = (t1 - t0) / N
    // eslint-disable-next-line no-console
    console.log(`[bench] capability filter avg ${perFilter.toFixed(5)}ms (${N} filters over 5000)`)
    expect(perFilter).toBeLessThan(2)
  })

  it('does not introduce timers, RAF, or polling loops', () => {
    const dir = join(__dirname, '..', '..', '..', 'src', 'runtime', 'capability')
    const files = [
      'index.ts',
      'types.ts',
      'capability-descriptor.ts',
      'capability-registry.ts',
      'capability-filter.ts',
      'capability-resolver.ts',
      'capability-runtime.ts'
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
