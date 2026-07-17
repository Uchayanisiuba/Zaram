// desktop/src/runtime/capability/types.ts
//
// Milestone 1.5 — Capability Runtime types.
//
// The Capability Runtime is the OS capability discovery and execution layer. It
// answers "What can Zaram do?" — NOT "How should Zaram think?". It is the single
// source of truth for every capability available to the OS (filesystem, browser,
// calculator, clipboard, email, vision, speech, camera, OCR, code execution,
// search, plugins, automation, future agents).
//
// This file is purely additive. It must NOT import the drawing layer, the body
// layer, concrete avatars, the character projection, the animation engine, frame
// snapshots, the orb drawing code, the desktop shell, any GPU/3D engine, or
// platform-specific graphics code. It must NOT depend on the Emotion, Behaviour,
// Presence, Character, or body-layer runtimes.


// --- Capability categories ------------------------------------------------

export type CapabilityCategory =
  | 'system'
  | 'workspace'
  | 'filesystem'
  | 'communication'
  | 'ai'
  | 'automation'
  | 'developer'
  | 'media'
  | 'vision'
  | 'speech'
  | 'plugins'
  | 'security'

// --- Availability / environment --------------------------------------------

export type CapabilityAvailability =
  | 'available'
  | 'unavailable'
  | 'disabled'
  | 'requires-setup'
  | 'degraded'

export type CapabilityExecutionLocation = 'local' | 'cloud'

// A coarse permission identifier a capability declares it requires.
export type CapabilityPermission =
  | 'filesystem:read'
  | 'filesystem:write'
  | 'filesystem:admin'
  | 'network:read'
  | 'network:write'
  | 'network:admin'
  | 'clipboard:read'
  | 'clipboard:write'
  | 'camera:read'
  | 'microphone:read'
  | 'email:read'
  | 'email:write'
  | 'system:execute'
  | 'system:admin'
  | 'automation:run'
  | 'memory:read'
  | 'memory:write'
  | 'ai:inference'
  | 'plugin:install'
  | 'plugin:execute'
  | 'security:elevated'

// --- Capability descriptor (capability metadata only; never behaviour) -----

export interface CapabilityDescriptor {
  // Stable unique identifier (e.g. "filesystem.read", "browser.open").
  id: string
  // Human-readable name.
  name: string
  // Human-readable description of what the capability does.
  description: string
  // Coarse grouping used for filtering and discovery.
  category: CapabilityCategory
  // Declared permissions required to invoke the capability.
  permissions: CapabilityPermission[]
  // JSON-Schema-like description of the expected input. Exposed as metadata,
  // never executed by this runtime.
  inputSchema: CapabilitySchema
  // JSON-Schema-like description of the produced output.
  outputSchema: CapabilitySchema
  // Current availability.
  availability: CapabilityAvailability
  // Latency estimate in milliseconds (metadata for planning; not measured here).
  latencyEstimateMs: number
  // Where the capability executes.
  location: CapabilityExecutionLocation
  // Relative cost 0 (free) .. 1 (expensive cloud call) for planning.
  cost: number
  // Whether the capability is currently enabled (user/OS toggle).
  enabled: boolean
  // Optional owning subsystem/runtime id (e.g. "world", "conversation").
  source?: string
  // Optional semantic tags for richer discovery.
  tags?: string[]
  // Monotonic revision bumped whenever the descriptor changes.
  revision: number
  // Epoch ms when the descriptor was last updated.
  updatedAt: number
}

// A minimal, serialisable schema description (metadata only).
export interface CapabilitySchema {
  type: 'object' | 'string' | 'number' | 'boolean' | 'array' | 'null'
  properties?: Record<string, CapabilitySchema>
  required?: string[]
  description?: string
}

// The input contract for registering a new capability. `id` is required; the
// runtime fills `revision`/`updatedAt` and clamps `cost`.
export interface CapabilityRegistration {
  id: string
  name: string
  description: string
  category: CapabilityCategory
  permissions?: CapabilityPermission[]
  inputSchema?: CapabilitySchema
  outputSchema?: CapabilitySchema
  availability?: CapabilityAvailability
  latencyEstimateMs?: number
  location?: CapabilityExecutionLocation
  cost?: number
  enabled?: boolean
  source?: string
  tags?: string[]
}

// --- Filtering --------------------------------------------------------------

export interface CapabilityFilter {
  // Match any of the supplied categories (OR). Empty = any.
  categories?: CapabilityCategory[]
  // Require ALL of the supplied permissions (AND). Empty = any.
  permissions?: CapabilityPermission[]
  // Require this availability. Omit to ignore.
  availability?: CapabilityAvailability
  // Require local execution.
  localOnly?: boolean
  // Require cloud execution.
  cloudOnly?: boolean
  // Require the capability to be enabled.
  enabledOnly?: boolean
}

// --- Resolution result ------------------------------------------------------

export interface CapabilityResolution {
  // The matched descriptor, or null when nothing matched.
  capability: CapabilityDescriptor | null
  // When the resolver had candidates but none matched constraints.
  found: boolean
  // The candidate ids considered (for diagnostics/observability).
  candidates: string[]
}

// --- Read model -------------------------------------------------------------

export interface CapabilitySnapshot {
  revision: number
  total: number
  enabled: number
  byCategory: Partial<Record<CapabilityCategory, number>>
  capabilities: CapabilityDescriptor[]
}
