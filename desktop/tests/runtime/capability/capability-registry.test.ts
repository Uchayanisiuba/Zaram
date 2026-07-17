// desktop/tests/runtime/capability/capability-registry.test.ts
//
// Unit tests — Milestone 1.5 Capability Registry.
//
// Verifies O(1) lookup by id, indexed lookup by category, duplicate detection,
// update/unregister, and revision bookkeeping. The registry stores ONLY
// capability metadata.

import { describe, it, expect } from 'vitest'
import { CapabilityRegistry } from '../../../src/runtime/capability/capability-registry'
import { validateCapabilityId } from '../../../src/runtime/capability/capability-descriptor'
import type { CapabilityRegistration } from '../../../src/runtime/capability/types'

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

describe('Capability Registry — registration', () => {
  it('registers a capability and returns a cloned descriptor', () => {
    const r = new CapabilityRegistry()
    const d = r.register(reg())
    expect(d.id).toBe('fs.read')
    expect(d.category).toBe('filesystem')
    expect(d.enabled).toBe(true)
    expect(d.revision).toBe(1)
  })

  it('applies defaults for optional fields', () => {
    const r = new CapabilityRegistry()
    const d = r.register({ id: 'x', name: 'X', description: 'd', category: 'ai' })
    expect(d.availability).toBe('available')
    expect(d.location).toBe('local')
    expect(d.cost).toBe(0)
    expect(d.permissions).toEqual([])
  })

  it('clamps cost into [0,1]', () => {
    const r = new CapabilityRegistry()
    expect(r.register(reg({ cost: 5 })).cost).toBe(1)
    expect(r.register(reg({ id: 'b', cost: -1 })).cost).toBe(0)
  })

  it('auto-stamps updatedAt and clamps latency', () => {
    const r = new CapabilityRegistry()
    const d = r.register(reg({ latencyEstimateMs: 42 }))
    expect(d.latencyEstimateMs).toBe(42)
    expect(d.updatedAt).toBeGreaterThan(0)
  })
})

describe('Capability Registry — duplicate detection', () => {
  it('throws when registering a duplicate id', () => {
    const r = new CapabilityRegistry()
    r.register(reg())
    expect(() => r.register(reg())).toThrow(/already registered/)
  })

  it('registerOrReplace allows idempotent re-registration', () => {
    const r = new CapabilityRegistry()
    const a = r.register(reg({ name: 'A' }))
    const b = r.registerOrReplace(reg({ name: 'B' }))
    expect(b.name).toBe('B')
    expect(b.revision).toBe(1)
    expect(r.get('fs.read')?.name).toBe('B')
    expect(a).not.toBe(r.get('fs.read'))
  })

  it('keeps only one entry after replace (count stable)', () => {
    const r = new CapabilityRegistry()
    r.register(reg())
    r.registerOrReplace(reg({ name: 'B' }))
    expect(r.count()).toBe(1)
  })
})

describe('Capability Registry — O(1) lookup by id', () => {
  it('returns the descriptor for a known id', () => {
    const r = new CapabilityRegistry()
    r.register(reg())
    expect(r.get('fs.read')?.id).toBe('fs.read')
  })

  it('returns null for an unknown id', () => {
    const r = new CapabilityRegistry()
    expect(r.get('nope')).toBeNull()
  })

  it('returns independent clones (no shared mutable references)', () => {
    const r = new CapabilityRegistry()
    r.register(reg({ permissions: ['filesystem:read'] }))
    const a = r.get('fs.read')!
    const b = r.get('fs.read')!
    a.permissions.push('filesystem:write')
    expect(b.permissions).toEqual(['filesystem:read'])
  })

  it('getMany returns only known ids in order', () => {
    const r = new CapabilityRegistry()
    r.register(reg({ id: 'a', category: 'ai' }))
    r.register(reg({ id: 'b', category: 'ai' }))
    const out = r.getMany(['b', 'a', 'missing'])
    expect(out.map((d) => d.id)).toEqual(['b', 'a'])
  })
})

describe('Capability Registry — indexed lookup by category', () => {
  it('getByCategory returns only that category', () => {
    const r = new CapabilityRegistry()
    r.register(reg({ id: 'fs.read', category: 'filesystem' }))
    r.register(reg({ id: 'fs.write', category: 'filesystem' }))
    r.register(reg({ id: 'browser.open', category: 'workspace' }))
    const fs = r.getByCategory('filesystem')
    expect(fs.map((d) => d.id).sort()).toEqual(['fs.read', 'fs.write'])
    expect(r.getByCategory('vision')).toEqual([])
  })

  it('maintains the category index when a capability is updated to a new category', () => {
    const r = new CapabilityRegistry()
    r.register(reg({ id: 'tool', category: 'developer' }))
    expect(r.getByCategory('developer').length).toBe(1)
    r.update('tool', { category: 'ai' })
    expect(r.getByCategory('developer')).toEqual([])
    expect(r.getByCategory('ai').map((d) => d.id)).toEqual(['tool'])
  })

  it('drops empty category buckets', () => {
    const r = new CapabilityRegistry()
    r.register(reg({ id: 'only', category: 'media' }))
    expect(r.categories()).toContain('media')
    r.unregister('only')
    expect(r.categories()).not.toContain('media')
  })
})

describe('Capability Registry — update / unregister / revision', () => {
  it('update changes availability and bumps revision', () => {
    const r = new CapabilityRegistry()
    r.register(reg())
    const before = r.get('fs.read')!.revision
    const updated = r.update('fs.read', { availability: 'degraded', enabled: false })
    expect(updated?.availability).toBe('degraded')
    expect(updated?.enabled).toBe(false)
    expect(updated?.revision).toBe(before + 1)
  })

  it('update returns null for unknown id', () => {
    const r = new CapabilityRegistry()
    expect(r.update('missing', { enabled: false })).toBeNull()
  })

  it('unregister removes the entry', () => {
    const r = new CapabilityRegistry()
    r.register(reg())
    expect(r.unregister('fs.read')).toBe(true)
    expect(r.has('fs.read')).toBe(false)
    expect(r.unregister('fs.read')).toBe(false)
  })

  it('tracks total + enabled counts', () => {
    const r = new CapabilityRegistry()
    r.register(reg({ id: 'a', enabled: true }))
    r.register(reg({ id: 'b', enabled: false }))
    expect(r.count()).toBe(2)
    expect(r.enabledCount()).toBe(1)
  })

  it('revision increases on every mutation', () => {
    const r = new CapabilityRegistry()
    const v0 = r.getRevision()
    r.register(reg())
    const v1 = r.getRevision()
    r.update('fs.read', { enabled: false })
    const v2 = r.getRevision()
    expect(v1).toBeGreaterThan(v0)
    expect(v2).toBeGreaterThan(v1)
  })

  it('reset clears all state', () => {
    const r = new CapabilityRegistry()
    r.register(reg())
    r.reset()
    expect(r.count()).toBe(0)
    expect(r.getRevision()).toBe(0)
  })
})

describe('Capability Registry — id validation', () => {
  it('accepts valid dotted/kebab ids', () => {
    expect(validateCapabilityId('fs.read')).toBeNull()
    expect(validateCapabilityId('browser-open')).toBeNull()
    expect(validateCapabilityId('a1.b2-c3')).toBeNull()
  })

  it('rejects empty / uppercase / invalid ids', () => {
    expect(validateCapabilityId('')).not.toBeNull()
    expect(validateCapabilityId('Bad')).not.toBeNull()
    expect(validateCapabilityId('with space')).not.toBeNull()
    expect(validateCapabilityId('.leading')).not.toBeNull()
  })

  it('register throws on invalid id', () => {
    const r = new CapabilityRegistry()
    expect(() => r.register(reg({ id: 'Bad ID' }))).toThrow(/Invalid capability id/)
  })
})
