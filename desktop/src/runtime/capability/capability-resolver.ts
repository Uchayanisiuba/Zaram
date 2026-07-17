// desktop/src/runtime/capability/capability-resolver.ts
//
// Milestone 1.5 — Capability Resolver.
//
// Given a query (category preference, required permissions, location, and an
// explicit filter), resolves the most appropriate registered capability. This is
// the lookup surface the Executive Runtime uses: it never receives concrete
// implementations, only descriptors.
//
// Resolution precedence (highest first):
//   1. explicit id match (when supplied)
//   2. enabled + available candidates
//   3. lowest cost, then lowest latency estimate, then lexicographic id

import {
  CapabilityDescriptor,
  CapabilityFilter,
  CapabilityResolution,
  CapabilityCategory
} from './types'
import { applyFilter } from './capability-filter'
import { CapabilityRegistry } from './capability-registry'

export interface CapabilityQuery {
  // Optional explicit capability id (exact match wins immediately).
  id?: string
  // Preferred category when resolving by need.
  category?: CapabilityCategory
  // Required permissions the resolved capability must declare.
  requiredPermissions?: CapabilityFilter['permissions']
  // Additional free-form filter.
  filter?: CapabilityFilter
  // When true, disabled/unavailable capabilities are excluded (default true).
  usableOnly?: boolean
}

// Pure scoring used to order candidate descriptors. Higher is better.
function score(d: CapabilityDescriptor): number {
  const enabledBonus = d.enabled ? 1_000_000 : 0
  const availableBonus = d.availability === 'available' ? 100_000 : d.availability === 'degraded' ? 10_000 : 0
  const localBonus = d.location === 'local' ? 1_000 : 0
  // Lower cost/latency is better, so invert into the score.
  const costScore = Math.round((1 - d.cost) * 100)
  const latencyScore = Math.round(Math.max(0, 1000 - d.latencyEstimateMs) / 10)
  return enabledBonus + availableBonus + localBonus + costScore + latencyScore
}

function compare(a: CapabilityDescriptor, b: CapabilityDescriptor): number {
  const s = score(b) - score(a)
  if (s !== 0) return s
  return a.id < b.id ? -1 : a.id > b.id ? 1 : 0
}

export class CapabilityResolver {
  constructor(private readonly registry: CapabilityRegistry) {}

  // Resolve the best capability for a query. Never throws; returns a result with
  // `found=false` and `capability=null` when nothing matches.
  resolve(query: CapabilityQuery): CapabilityResolution {
    if (query.id) {
      const exact = this.registry.get(query.id)
      if (exact) {
        return { capability: exact, found: true, candidates: [exact.id] }
      }
      return { capability: null, found: false, candidates: [] }
    }

    const filter: CapabilityFilter = {
      categories: query.category ? [query.category] : query.filter?.categories,
      permissions: query.requiredPermissions ?? query.filter?.permissions,
      availability: query.filter?.availability,
      localOnly: query.filter?.localOnly,
      cloudOnly: query.filter?.cloudOnly,
      enabledOnly: query.usableOnly ?? query.filter?.enabledOnly ?? true
    }

    const pool = query.category
      ? this.registry.getByCategory(query.category)
      : this.registry.all()
    const candidates = applyFilter(pool, filter)
    if (candidates.length === 0) {
      return { capability: null, found: false, candidates: [] }
    }
    candidates.sort(compare)
    const best = candidates[0]
    return {
      capability: best,
      found: true,
      candidates: candidates.map((c) => c.id)
    }
  }

  // Resolve but require an explicit id; returns null when absent. Thin wrapper
  // used by callers that already know the capability they want.
  resolveById(id: string): CapabilityDescriptor | null {
    return this.registry.get(id)
  }
}
