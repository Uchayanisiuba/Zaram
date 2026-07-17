// desktop/src/runtime/capability/capability-registry.ts
//
// Milestone 1.5 — Capability Registry.
//
// The single source of truth for all registered capabilities. Provides:
//   - O(1) lookup by id (Map)
//   - indexed lookup by category (maintained Map<category, Set<id>>)
//   - duplicate detection (registering an existing id throws)
//   - enabled/availability bookkeeping
//
// It stores ONLY capability metadata. It does not execute capabilities, does
// not know about the drawing layer, body layer, or any runtime implementation.

import {
  CapabilityCategory,
  CapabilityDescriptor,
  CapabilityRegistration
} from './types'
import { cloneDescriptor, createDescriptor, reviseDescriptor } from './capability-descriptor'

export class CapabilityRegistry {
  private readonly byId = new Map<string, CapabilityDescriptor>()
  private readonly byCategory = new Map<CapabilityCategory, Set<string>>()
  private revision = 0

  reset(): void {
    this.byId.clear()
    this.byCategory.clear()
    this.revision = 0
  }

  // Register a new capability. Throws on duplicate id or invalid input so
  // callers get immediate, deterministic feedback (no silent overwrite).
  register(reg: CapabilityRegistration): CapabilityDescriptor {
    if (this.byId.has(reg.id)) {
      throw new Error(`Capability "${reg.id}" is already registered`)
    }
    const descriptor = createDescriptor(reg)
    this.index(descriptor)
    return cloneDescriptor(descriptor)
  }

  // Register, replacing any existing entry (used by idempotent seeders). The
  // replacement keeps a fresh revision.
  registerOrReplace(reg: CapabilityRegistration): CapabilityDescriptor {
    if (this.byId.has(reg.id)) {
      this.unindex(this.byId.get(reg.id)!)
    }
    const descriptor = createDescriptor(reg)
    this.index(descriptor)
    return cloneDescriptor(descriptor)
  }

  // Update availability/enabled metadata in place (immutably via revision). The
  // id is not part of the patch; it identifies the target.
  update(
    id: string,
    patch: Partial<Omit<CapabilityRegistration, 'id'>>
  ): CapabilityDescriptor | null {
    const prev = this.byId.get(id)
    if (!prev) return null
    const next = reviseDescriptor(prev, patch)
    this.unindex(prev)
    this.index(next)
    return cloneDescriptor(next)
  }

  unregister(id: string): boolean {
    const prev = this.byId.get(id)
    if (!prev) return false
    this.unindex(prev)
    this.byId.delete(id)
    return true
  }

  has(id: string): boolean {
    return this.byId.has(id)
  }

  // O(1) descriptor lookup by id.
  get(id: string): CapabilityDescriptor | null {
    const d = this.byId.get(id)
    return d ? cloneDescriptor(d) : null
  }

  getMany(ids: string[]): CapabilityDescriptor[] {
    const out: CapabilityDescriptor[] = []
    for (const id of ids) {
      const d = this.byId.get(id)
      if (d) out.push(cloneDescriptor(d))
    }
    return out
  }

  // O(1) indexed lookup by category.
  getByCategory(category: CapabilityCategory): CapabilityDescriptor[] {
    const ids = this.byCategory.get(category)
    if (!ids) return []
    const out: CapabilityDescriptor[] = []
    for (const id of ids) {
      const d = this.byId.get(id)
      if (d) out.push(cloneDescriptor(d))
    }
    return out
  }

  categories(): CapabilityCategory[] {
    return [...this.byCategory.keys()]
  }

  ids(): string[] {
    return [...this.byId.keys()]
  }

  all(): CapabilityDescriptor[] {
    return [...this.byId.values()].map(cloneDescriptor)
  }

  count(): number {
    return this.byId.size
  }

  enabledCount(): number {
    let n = 0
    for (const d of this.byId.values()) if (d.enabled) n++
    return n
  }

  getRevision(): number {
    return this.revision
  }

  // --- internals -------------------------------------------------------------

  private index(d: CapabilityDescriptor): void {
    this.byId.set(d.id, d)
    let set = this.byCategory.get(d.category)
    if (!set) {
      set = new Set<string>()
      this.byCategory.set(d.category, set)
    }
    set.add(d.id)
    this.revision += 1
  }

  private unindex(d: CapabilityDescriptor): void {
    const set = this.byCategory.get(d.category)
    if (set) {
      set.delete(d.id)
      if (set.size === 0) this.byCategory.delete(d.category)
    }
    this.revision += 1
  }
}
