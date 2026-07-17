// desktop/src/runtime/capability/capability-filter.ts
//
// Milestone 1.5 — Capability Filter.
//
// Pure, allocation-light predicate logic for selecting capabilities that match a
// CapabilityFilter. No state, no timers, no I/O. Used by the resolver and by
// external queries.

import { CapabilityDescriptor, CapabilityFilter } from './types'

// Returns true when the descriptor satisfies the filter constraints. An empty
// filter (all optional fields unset) matches everything.
export function matchesFilter(d: CapabilityDescriptor, filter: CapabilityFilter): boolean {
  if (filter.categories && filter.categories.length > 0) {
    if (!filter.categories.includes(d.category)) return false
  }
  if (filter.permissions && filter.permissions.length > 0) {
    // Require ALL declared permissions (AND semantics).
    for (const p of filter.permissions) {
      if (!d.permissions.includes(p)) return false
    }
  }
  if (filter.availability !== undefined && d.availability !== filter.availability) {
    return false
  }
  if (filter.localOnly && d.location !== 'local') return false
  if (filter.cloudOnly && d.location !== 'cloud') return false
  if (filter.enabledOnly && !d.enabled) return false
  return true
}

// Filter a list of descriptors. Preserves input order for stable results.
export function applyFilter(
  descriptors: CapabilityDescriptor[],
  filter: CapabilityFilter
): CapabilityDescriptor[] {
  const out: CapabilityDescriptor[] = []
  for (const d of descriptors) {
    if (matchesFilter(d, filter)) out.push(d)
  }
  return out
}

// Convenience builders for the common filter shapes.
export function filterByCategory(...categories: CapabilityDescriptor['category'][]): CapabilityFilter {
  return { categories }
}

export function filterEnabledOnly(): CapabilityFilter {
  return { enabledOnly: true }
}

export function filterLocalOnly(): CapabilityFilter {
  return { localOnly: true }
}

export function filterCloudOnly(): CapabilityFilter {
  return { cloudOnly: true }
}
