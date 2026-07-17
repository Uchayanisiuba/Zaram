// desktop/src/runtime/capability/capability-runtime.ts
//
// Milestone 1.5 — Capability Runtime (Discovery & Execution Interface).
//
// The Operating System's capability discovery layer. It is the single source of
// truth for every capability available to the OS (filesystem, browser,
// calculator, clipboard, email, vision, speech, camera, OCR, code execution,
// search, plugins, automation, future agents).
//
// It answers "What can Zaram do?" — NOT "How should Zaram think?". It owns:
//   - registration / unregistration of capability descriptors
//   - O(1) lookup by id and indexed lookup by category
//   - filtering by category / permissions / availability / location / enabled
//   - resolution of the best capability for a need (via the resolver)
//
// It exposes ONLY capability metadata. It does not execute capabilities, does
// not import the drawing layer, the body layer, concrete avatars, the character
// projection, the animation engine, frame snapshots, the orb drawing code, the
// desktop shell, any GPU/3D engine, or the Emotion/Behaviour/Presence/Character/
// body-layer runtimes.
//
// The Executive Runtime consumes it strictly through ICapabilityRuntime — never
// a concrete implementation — and requests capabilities, never tools.

import {
  CapabilityCategory,
  CapabilityDescriptor,
  CapabilityFilter,
  CapabilityRegistration,
  CapabilityResolution,
  CapabilitySnapshot
} from './types'
import { CapabilityRegistry } from './capability-registry'
import { CapabilityResolver, CapabilityQuery } from './capability-resolver'
import { applyFilter } from './capability-filter'

// The contract the Executive Runtime depends on. The executive never sees the
// concrete CapabilityRuntime, only this interface.
export interface ICapabilityRuntime {
  register(reg: CapabilityRegistration): CapabilityDescriptor
  registerOrReplace(reg: CapabilityRegistration): CapabilityDescriptor
  unregister(id: string): boolean
  update(id: string, patch: Partial<Omit<CapabilityRegistration, 'id'>>): CapabilityDescriptor | null
  has(id: string): boolean
  get(id: string): CapabilityDescriptor | null
  getByCategory(category: CapabilityCategory): CapabilityDescriptor[]
  all(): CapabilityDescriptor[]
  filter(filter: CapabilityFilter): CapabilityDescriptor[]
  resolve(query: CapabilityQuery): CapabilityResolution
  getSnapshot(): CapabilitySnapshot
  getRevision(): number
}

export class CapabilityRuntime implements ICapabilityRuntime {
  private readonly registry = new CapabilityRegistry()
  private readonly resolver: CapabilityResolver

  constructor() {
    this.resolver = new CapabilityResolver(this.registry)
  }

  register(reg: CapabilityRegistration): CapabilityDescriptor {
    return this.registry.register(reg)
  }

  registerOrReplace(reg: CapabilityRegistration): CapabilityDescriptor {
    return this.registry.registerOrReplace(reg)
  }

  unregister(id: string): boolean {
    return this.registry.unregister(id)
  }

  update(id: string, patch: Partial<Omit<CapabilityRegistration, 'id'>>): CapabilityDescriptor | null {
    return this.registry.update(id, patch)
  }

  has(id: string): boolean {
    return this.registry.has(id)
  }

  // O(1) lookup by id.
  get(id: string): CapabilityDescriptor | null {
    return this.registry.get(id)
  }

  // O(1) indexed lookup by category.
  getByCategory(category: CapabilityCategory): CapabilityDescriptor[] {
    return this.registry.getByCategory(category)
  }

  all(): CapabilityDescriptor[] {
    return this.registry.all()
  }

  // Declarative filtering by category / permissions / availability / location /
  // enabled. Pure predicate over the registry snapshot.
  filter(filter: CapabilityFilter): CapabilityDescriptor[] {
    return applyFilter(this.registry.all(), filter)
  }

  // Resolve the best capability for a need. Returns metadata only.
  resolve(query: CapabilityQuery): CapabilityResolution {
    return this.resolver.resolve(query)
  }

  // Read-only snapshot of all capability metadata + counts. Freely copyable;
  // descriptors are already clones, safe to expose.
  getSnapshot(): CapabilitySnapshot {
    const all = this.registry.all()
    const byCategory: Partial<Record<CapabilityCategory, number>> = {}
    let enabled = 0
    for (const d of all) {
      byCategory[d.category] = (byCategory[d.category] ?? 0) + 1
      if (d.enabled) enabled += 1
    }
    return {
      revision: this.registry.getRevision(),
      total: all.length,
      enabled,
      byCategory,
      capabilities: all
    }
  }

  getRevision(): number {
    return this.registry.getRevision()
  }

  reset(): void {
    this.registry.reset()
  }
}
