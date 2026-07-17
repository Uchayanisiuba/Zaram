// desktop/tests/runtime/capability/capability-runtime.test.ts
//
// Unit + integration tests — Milestone 1.5 Capability Runtime.
//
// Verifies: registration, lookup, filtering, snapshot, dependency injection,
// the Executive Runtime consuming it strictly through ICapabilityRuntime
// (requesting capabilities, never tools), and renderer/embodiment independence
// (asserted structurally — no drawing-layer/body-layer imports).

import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import {
  CapabilityRuntime,
  CapabilityRegistry,
  CapabilityResolver
} from '../../../src/runtime/capability'
import type { CapabilityRegistration, CapabilityDescriptor } from '../../../src/runtime/capability/types'
import { Container, TOKENS } from '../../../src/runtime/di/container'
import { bootstrapPresence } from '../../../src/runtime/bootstrap'
import { ExecutiveRuntime } from '../../../src/runtime/executive'

function reg(over: Partial<CapabilityRegistration> = {}): CapabilityRegistration {
  return {
    id: 'fs.read',
    name: 'Read File',
    description: 'Read a file from disk',
    category: 'filesystem',
    permissions: ['filesystem:read'],
    location: 'local',
    ...over
  }
}

describe('Capability Runtime — registration & lookup', () => {
  it('registers and looks up a capability by id (O(1))', () => {
    const rt = new CapabilityRuntime()
    rt.register(reg())
    expect(rt.has('fs.read')).toBe(true)
    expect(rt.get('fs.read')?.name).toBe('Read File')
  })

  it('returns null for unknown id', () => {
    const rt = new CapabilityRuntime()
    expect(rt.get('nope')).toBeNull()
  })

  it('rejects duplicate registration', () => {
    const rt = new CapabilityRuntime()
    rt.register(reg())
    expect(() => rt.register(reg())).toThrow(/already registered/)
  })

  it('unregister removes a capability', () => {
    const rt = new CapabilityRuntime()
    rt.register(reg())
    expect(rt.unregister('fs.read')).toBe(true)
    expect(rt.has('fs.read')).toBe(false)
  })

  it('update changes metadata and bumps revision', () => {
    const rt = new CapabilityRuntime()
    rt.register(reg())
    const rev0 = rt.get('fs.read')!.revision
    rt.update('fs.read', { enabled: false })
    const d = rt.get('fs.read')!
    expect(d.enabled).toBe(false)
    expect(d.revision).toBe(rev0 + 1)
  })
})

describe('Capability Runtime — category & filtering', () => {
  it('getByCategory returns only that category', () => {
    const rt = new CapabilityRuntime()
    rt.register(reg({ id: 'fs.read', category: 'filesystem' }))
    rt.register(reg({ id: 'fs.write', category: 'filesystem' }))
    rt.register(reg({ id: 'browser.open', category: 'workspace' }))
    expect(rt.getByCategory('filesystem').map((d) => d.id).sort()).toEqual(['fs.read', 'fs.write'])
  })

  it('filter by enabledOnly excludes disabled', () => {
    const rt = new CapabilityRuntime()
    rt.register(reg({ id: 'a', enabled: true }))
    rt.register(reg({ id: 'b', enabled: false }))
    const out = rt.filter({ enabledOnly: true })
    expect(out.map((d) => d.id)).toEqual(['a'])
  })

  it('filter by cloudOnly', () => {
    const rt = new CapabilityRuntime()
    rt.register(reg({ id: 'local', location: 'local' }))
    rt.register(reg({ id: 'cloud', location: 'cloud' }))
    const out = rt.filter({ cloudOnly: true })
    expect(out.map((d) => d.id)).toEqual(['cloud'])
  })

  it('filter by permissions (AND)', () => {
    const rt = new CapabilityRuntime()
    rt.register(reg({ id: 'read', permissions: ['filesystem:read'] }))
    rt.register(reg({ id: 'readwrite', permissions: ['filesystem:read', 'filesystem:write'] }))
    const out = rt.filter({ permissions: ['filesystem:read', 'filesystem:write'] })
    expect(out.map((d) => d.id)).toEqual(['readwrite'])
  })
})

describe('Capability Runtime — resolution', () => {
  it('resolves a capability by id', () => {
    const rt = new CapabilityRuntime()
    rt.register(reg({ id: 'fs.read' }))
    const res = rt.resolve({ id: 'fs.read' })
    expect(res.found).toBe(true)
    expect(res.capability?.id).toBe('fs.read')
  })

  it('resolves the best capability by category need', () => {
    const rt = new CapabilityRuntime()
    rt.register(reg({ id: 'fs.read', category: 'filesystem', cost: 0.1 }))
    rt.register(reg({ id: 'fs.write', category: 'filesystem', cost: 0.2 }))
    const res = rt.resolve({ category: 'filesystem' })
    expect(res.capability?.id).toBe('fs.read')
  })

  it('returns found=false when no capable candidate', () => {
    const rt = new CapabilityRuntime()
    rt.register(reg({ id: 'vision.ocr', category: 'vision', enabled: false }))
    const res = rt.resolve({ category: 'vision' })
    expect(res.found).toBe(false)
  })
})

describe('Capability Runtime — snapshot', () => {
  it('exposes counts and per-category tallies', () => {
    const rt = new CapabilityRuntime()
    rt.register(reg({ id: 'a', category: 'ai' }))
    rt.register(reg({ id: 'b', category: 'ai' }))
    rt.register(reg({ id: 'c', category: 'vision', enabled: false }))
    const snap = rt.getSnapshot()
    expect(snap.total).toBe(3)
    expect(snap.enabled).toBe(2)
    expect(snap.byCategory.ai).toBe(2)
    expect(snap.byCategory.vision).toBe(1)
    expect(snap.capabilities.length).toBe(3)
    expect(snap.revision).toBe(rt.getRevision())
  })

  it('snapshot capabilities are metadata-only descriptors', () => {
    const rt = new CapabilityRuntime()
    rt.register(reg({ id: 'fs.read', permissions: ['filesystem:read'] }))
    const d: CapabilityDescriptor = rt.getSnapshot().capabilities[0]
    expect(d.id).toBe('fs.read')
    expect(d.permissions).toEqual(['filesystem:read'])
    // No behaviour/execution surface is exposed.
    expect((d as unknown as Record<string, unknown>).execute).toBeUndefined()
    expect((d as unknown as Record<string, unknown>).invoke).toBeUndefined()
  })
})

describe('Capability Runtime — dependency injection', () => {
  it('registers as a singleton in the DI container', () => {
    const { container } = bootstrapPresence()
    expect(container.has(TOKENS.capabilityRuntime)).toBe(true)
    const a = container.resolve(TOKENS.capabilityRuntime)
    const b = container.resolve(TOKENS.capabilityRuntime)
    expect(a).toBe(b)
    expect(a).toBeInstanceOf(CapabilityRuntime)
  })

  it('can be resolved standalone and used', () => {
    const c = new Container()
    let built = false
    c.register(TOKENS.capabilityRuntime, () => {
      built = true
      return new CapabilityRuntime()
    })
    const rt = c.resolve<CapabilityRuntime>(TOKENS.capabilityRuntime)
    rt.register(reg({ id: 'x' }))
    expect(built).toBe(true)
    expect(rt.has('x')).toBe(true)
  })
})

describe('Capability Runtime — Executive Runtime integration (interface only)', () => {
  it('the executive is wired with a capability runtime via DI', () => {
    const { container } = bootstrapPresence()
    const exec = container.resolve<ExecutiveRuntime>(TOKENS.executiveRuntime)
    expect(exec.hasCapabilityRuntime()).toBe(true)
  })

  it('the executive requests capabilities only through the interface (never tools)', () => {
    const { container } = bootstrapPresence()
    const exec = container.resolve<ExecutiveRuntime>(TOKENS.executiveRuntime)
    const cap = container.resolve<CapabilityRuntime>(TOKENS.capabilityRuntime)
    cap.register(reg({ id: 'fs.read', category: 'filesystem' }))
    const res = exec.requestCapability({ id: 'fs.read' })
    expect(res?.found).toBe(true)
    expect(res?.capability?.id).toBe('fs.read')
  })

  it('the executive never calls tools directly (returns null without capability runtime)', () => {
    const exec = new ExecutiveRuntime() // no capabilityRuntime injected
    expect(exec.hasCapabilityRuntime()).toBe(false)
    expect(exec.requestCapability({ id: 'x' })).toBeNull()
  })

  it('the executive queries capability presence without importing implementations', () => {
    const { container } = bootstrapPresence()
    const exec = container.resolve<ExecutiveRuntime>(TOKENS.executiveRuntime)
    const cap = container.resolve<CapabilityRuntime>(TOKENS.capabilityRuntime)
    cap.register(reg({ id: 'tool.x' }))
    expect(exec.hasCapability('tool.x')).toBe(true)
    expect(exec.hasCapability('tool.missing')).toBe(false)
  })
})

describe('Capability Runtime — no timers / polling / rendering deps', () => {
  it('does not introduce setInterval / setTimeout / RAF / loops', () => {
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
      expect(src, `${f} must not use setInterval`).not.toMatch(/setInterval\s*\(/)
      expect(src, `${f} must not use setTimeout`).not.toMatch(/setTimeout\s*\(/)
      expect(src, `${f} must not use requestAnimationFrame`).not.toMatch(/requestAnimationFrame\s*\(/)
      expect(src, `${f} must not use while loops`).not.toMatch(/while\s*\(/)
      expect(src, `${f} must not use unbounded for`).not.toMatch(/for\s*\(;;/)
    }
  })

  it('does not import the drawing layer or body layer', () => {
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
      expect(src, `${f} must not reference renderer`).not.toMatch(/renderer/i)
      expect(src, `${f} must not reference embodiment`).not.toMatch(/embodiment/i)
      expect(src, `${f} must not reference CharacterFrame`).not.toMatch(/CharacterFrame/i)
      expect(src, `${f} must not reference animation-runtime`).not.toMatch(/animation-runtime/i)
      expect(src, `${f} must not reference frame-state`).not.toMatch(/frame-state|FrameState/i)
      expect(src, `${f} must not import engine`).not.toMatch(/@zaram\/engine/)
      expect(src, `${f} must not reference orb-renderer`).not.toMatch(/orb-renderer|OrbRenderer/i)
      expect(src, `${f} must not reference electron`).not.toMatch(/electron/i)
      expect(src, `${f} must not reference threejs`).not.toMatch(/three/i)
      expect(src, `${f} must not reference webgpu`).not.toMatch(/webgpu/i)
      expect(src, `${f} must not reference unreal`).not.toMatch(/unreal/i)
      expect(src, `${f} must not reference arkit`).not.toMatch(/arkit/i)
      expect(src, `${f} must not reference gnm`).not.toMatch(/gnm/i)
      expect(src, `${f} must not reference metahuman`).not.toMatch(/metahuman/i)
      expect(src, `${f} must not reference living-orb`).not.toMatch(/living-orb|LivingOrb/i)
      expect(src, `${f} must not reference robot`).not.toMatch(/robot/i)
      // Must not depend on the emotion/behaviour/presence/character runtimes.
      expect(src, `${f} must not reference Emotion`).not.toMatch(/EmotionRuntime|emotion-runtime/i)
      expect(src, `${f} must not reference Behaviour`).not.toMatch(/BehaviourRuntime|behaviour-runtime/i)
      expect(src, `${f} must not reference Presence`).not.toMatch(/PresenceRuntime|presence-runtime/i)
      expect(src, `${f} must not reference Character`).not.toMatch(/CharacterRuntime|character-runtime/i)
    }
  })
})
