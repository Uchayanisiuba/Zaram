// desktop/src/runtime/capability/index.ts
//
// Milestone 1.5 — Capability Runtime barrel.
//
// The Capability Runtime is the OS capability discovery and execution
// interface. It is the single source of truth for every capability available to
// the OS, exposes ONLY capability metadata, and never imports the drawing
// layer, the body layer, concrete avatars, the character projection, the
// animation engine, frame snapshots, the orb drawing code, the desktop shell,
// any GPU/3D engine, or the Emotion/Behaviour/Presence/Character/body-layer
// runtimes. The Executive Runtime consumes it strictly through
// ICapabilityRuntime.

export { CapabilityRuntime } from './capability-runtime'
export type { ICapabilityRuntime } from './capability-runtime'

export { CapabilityRegistry } from './capability-registry'
export { CapabilityResolver } from './capability-resolver'
export type { CapabilityQuery } from './capability-resolver'

export {
  createDescriptor,
  reviseDescriptor,
  cloneDescriptor,
  validateCapabilityId
} from './capability-descriptor'

export { matchesFilter, applyFilter } from './capability-filter'

export type {
  CapabilityDescriptor,
  CapabilityRegistration,
  CapabilityCategory,
  CapabilityAvailability,
  CapabilityExecutionLocation,
  CapabilityPermission,
  CapabilitySchema,
  CapabilityFilter,
  CapabilityResolution,
  CapabilitySnapshot
} from './types'
