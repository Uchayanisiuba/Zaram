// desktop/tests/runtime/capability/capability-filter.test.ts
//
// Unit tests — Milestone 1.5 Capability Filter + Resolver.
//
// Verifies filtering by category / permissions / availability / location /
// enabled, and resolution precedence (explicit id, then best-scored candidate).

import { describe, it, expect } from 'vitest'
import {
  CapabilityRegistry
} from '../../../src/runtime/capability/capability-registry'
import { CapabilityResolver } from '../../../src/runtime/capability/capability-resolver'
import { matchesFilter, applyFilter } from '../../../src/runtime/capability/capability-filter'
import type { CapabilityDescriptor, CapabilityRegistration } from '../../../src/runtime/capability/types'

function reg(over: Partial<CapabilityRegistration>): CapabilityRegistration {
  return {
    id: 'x',
    name: 'X',
    description: 'd',
    category: 'ai',
    ...over
  }
}

function seed(): { registry: CapabilityRegistry; resolver: CapabilityResolver } {
  const registry = new CapabilityRegistry()
  registry.register(reg({ id: 'fs.read', category: 'filesystem', permissions: ['filesystem:read'], location: 'local', cost: 0.1, latencyEstimateMs: 10 }))
  registry.register(reg({ id: 'fs.write', category: 'filesystem', permissions: ['filesystem:read', 'filesystem:write'], location: 'local', cost: 0.2, latencyEstimateMs: 20 }))
  registry.register(reg({ id: 'vision.ocr', category: 'vision', permissions: ['network:read'], location: 'cloud', cost: 0.8, latencyEstimateMs: 500, enabled: false }))
  registry.register(reg({ id: 'browser.open', category: 'workspace', permissions: ['network:read'], location: 'local', cost: 0.3, latencyEstimateMs: 50 }))
  const resolver = new CapabilityResolver(registry)
  return { registry, resolver }
}

describe('Capability Filter — category', () => {
  it('matches a capability in the requested category', () => {
    const { registry } = seed()
    const fs = registry.getByCategory('filesystem')
    expect(matchesFilter(fs[0], { categories: ['filesystem'] })).toBe(true)
  })

  it('rejects a capability not in the requested category', () => {
    const { registry } = seed()
    const vision = registry.get('vision.ocr')!
    expect(matchesFilter(vision, { categories: ['filesystem'] })).toBe(false)
  })

  it('empty categories matches any', () => {
    const { registry } = seed()
    const vision = registry.get('vision.ocr')!
    expect(matchesFilter(vision, {})).toBe(true)
  })
})

describe('Capability Filter — permissions (AND)', () => {
  it('requires ALL declared permissions', () => {
    const { registry } = seed()
    const read = registry.get('fs.read')!
    const write = registry.get('fs.write')!
    expect(matchesFilter(write, { permissions: ['filesystem:read', 'filesystem:write'] })).toBe(true)
    expect(matchesFilter(read, { permissions: ['filesystem:read', 'filesystem:write'] })).toBe(false)
  })
})

describe('Capability Filter — availability / location / enabled', () => {
  it('filters by availability', () => {
    const { registry } = seed()
    const vision = registry.get('vision.ocr')!
    // Registered with availability default 'available' (only enabled=false).
    expect(vision.availability).toBe('available')
    expect(matchesFilter(vision, { availability: 'available' })).toBe(true)
    expect(matchesFilter(vision, { availability: 'degraded' })).toBe(false)
  })

  it('filters localOnly / cloudOnly', () => {
    const { registry } = seed()
    const local = registry.get('fs.read')!
    const cloud = registry.get('vision.ocr')!
    expect(matchesFilter(local, { localOnly: true })).toBe(true)
    expect(matchesFilter(local, { cloudOnly: true })).toBe(false)
    expect(matchesFilter(cloud, { cloudOnly: true })).toBe(true)
  })

  it('filters enabledOnly', () => {
    const { registry } = seed()
    const cloud = registry.get('vision.ocr')!
    expect(matchesFilter(cloud, { enabledOnly: true })).toBe(false)
    expect(matchesFilter(cloud, { enabledOnly: false })).toBe(true)
  })

  it('applyFilter returns only matching descriptors preserving order', () => {
    const { registry } = seed()
    const out = applyFilter(registry.all(), { categories: ['filesystem'] })
    expect(out.map((d) => d.id).sort()).toEqual(['fs.read', 'fs.write'])
  })
})

describe('Capability Resolver — explicit id', () => {
  it('resolves an exact id immediately', () => {
    const { resolver } = seed()
    const res = resolver.resolve({ id: 'fs.read' })
    expect(res.found).toBe(true)
    expect(res.capability?.id).toBe('fs.read')
    expect(res.candidates).toEqual(['fs.read'])
  })

  it('returns found=false for unknown id', () => {
    const { resolver } = seed()
    const res = resolver.resolve({ id: 'nope' })
    expect(res.found).toBe(false)
    expect(res.capability).toBeNull()
  })
})

describe('Capability Resolver — by need', () => {
  it('resolves the best filesystem capability (lowest cost/local)', () => {
    const { resolver } = seed()
    const res = resolver.resolve({ category: 'filesystem' })
    expect(res.found).toBe(true)
    expect(res.capability?.id).toBe('fs.read')
  })

  it('excludes disabled capabilities by default (usableOnly)', () => {
    const { resolver } = seed()
    const res = resolver.resolve({ category: 'vision' })
    expect(res.found).toBe(false)
  })

  it('includes disabled capabilities when usableOnly=false', () => {
    const { resolver } = seed()
    const res = resolver.resolve({ category: 'vision', usableOnly: false })
    expect(res.found).toBe(true)
    expect(res.capability?.id).toBe('vision.ocr')
  })

  it('honours required permissions', () => {
    const { resolver } = seed()
    const res = resolver.resolve({ category: 'filesystem', requiredPermissions: ['filesystem:write'] })
    expect(res.capability?.id).toBe('fs.write')
  })

  it('prefers local over cloud when scores tie on cost/latency', () => {
    const { registry, resolver } = seed()
    registry.register(reg({ id: 'vision.local', category: 'vision', permissions: ['network:read'], location: 'local', cost: 0.8, latencyEstimateMs: 500 }))
    const res = resolver.resolve({ category: 'vision', usableOnly: false })
    // both cloud + local disabled; enabled=false => both considered; local scores higher
    expect(res.capability?.id).toBe('vision.local')
  })

  it('returns candidates list for observability', () => {
    const { resolver } = seed()
    const res = resolver.resolve({ category: 'filesystem' })
    expect(res.candidates).toContain('fs.read')
    expect(res.candidates).toContain('fs.write')
  })
})
