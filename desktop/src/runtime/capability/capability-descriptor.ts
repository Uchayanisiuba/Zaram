// desktop/src/runtime/capability/capability-descriptor.ts
//
// Milestone 1.5 — Capability Descriptor factory.
//
// Produces immutable, validated CapabilityDescriptor records from
// CapabilityRegistration input. This is the ONLY place a raw registration is
// turned into the canonical descriptor shape. The runtime never mutates a
// descriptor in place; updates produce a new revisioned descriptor.

import {
  CapabilityAvailability,
  CapabilityDescriptor,
  CapabilityExecutionLocation,
  CapabilityPermission,
  CapabilityRegistration,
  CapabilitySchema
} from './types'

const DEFAULT_INPUT_SCHEMA: CapabilitySchema = { type: 'object', properties: {}, required: [] }
const DEFAULT_OUTPUT_SCHEMA: CapabilitySchema = { type: 'object', properties: {}, required: [] }

function clampCost(v: number | undefined): number {
  if (v === undefined || Number.isNaN(v)) return 0
  return Math.min(1, Math.max(0, v))
}

function now(): number {
  return typeof performance !== 'undefined' ? performance.now() : Date.now()
}

// Validate an id is a non-empty dotted/kebab identifier. Returns an error string
// or null when valid. Kept strict so the registry can detect bad input early.
export function validateCapabilityId(id: string): string | null {
  if (typeof id !== 'string' || id.length === 0) return 'id must be a non-empty string'
  if (id.length > 128) return 'id must be at most 128 characters'
  if (!/^[a-z0-9]+(?:[._-][a-z0-9]+)*$/.test(id)) {
    return 'id must match ^[a-z0-9]+(?:[._-][a-z0-9]+)*$'
  }
  return null
}

export function createDescriptor(reg: CapabilityRegistration, revision = 1): CapabilityDescriptor {
  const idError = validateCapabilityId(reg.id)
  if (idError) throw new Error(`Invalid capability id "${reg.id}": ${idError}`)
  if (!reg.name || !reg.description) {
    throw new Error(`Capability "${reg.id}" requires a name and description`)
  }
  return {
    id: reg.id,
    name: reg.name,
    description: reg.description,
    category: reg.category,
    permissions: (reg.permissions ?? []) as CapabilityPermission[],
    inputSchema: reg.inputSchema ?? { ...DEFAULT_INPUT_SCHEMA },
    outputSchema: reg.outputSchema ?? { ...DEFAULT_OUTPUT_SCHEMA },
    availability: (reg.availability ?? 'available') as CapabilityAvailability,
    latencyEstimateMs: reg.latencyEstimateMs ?? 0,
    location: (reg.location ?? 'local') as CapabilityExecutionLocation,
    cost: clampCost(reg.cost),
    enabled: reg.enabled ?? true,
    source: reg.source,
    tags: reg.tags ? [...reg.tags] : undefined,
    revision,
    updatedAt: now()
  }
}

// Produce a new descriptor with updated fields and a bumped revision. Used by
// the registry for availability/enabled transitions without mutating state.
export function reviseDescriptor(
  prev: CapabilityDescriptor,
  patch: Partial<CapabilityRegistration>
): CapabilityDescriptor {
  const merged: CapabilityRegistration = {
    id: prev.id,
    name: patch.name ?? prev.name,
    description: patch.description ?? prev.description,
    category: patch.category ?? prev.category,
    permissions: patch.permissions ?? prev.permissions,
    inputSchema: patch.inputSchema ?? prev.inputSchema,
    outputSchema: patch.outputSchema ?? prev.outputSchema,
    availability: patch.availability ?? prev.availability,
    latencyEstimateMs: patch.latencyEstimateMs ?? prev.latencyEstimateMs,
    location: patch.location ?? prev.location,
    cost: patch.cost ?? prev.cost,
    enabled: patch.enabled ?? prev.enabled,
    source: patch.source ?? prev.source,
    tags: patch.tags ?? prev.tags
  }
  return {
    ...createDescriptor(merged, prev.revision + 1)
  }
}

// Deep-ish clone of a descriptor for safe external exposure. Schema objects are
// shallow-cloned (they are treated as immutable metadata).
export function cloneDescriptor(d: CapabilityDescriptor): CapabilityDescriptor {
  return {
    ...d,
    permissions: [...d.permissions],
    inputSchema: { ...d.inputSchema },
    outputSchema: { ...d.outputSchema },
    tags: d.tags ? [...d.tags] : undefined
  }
}
