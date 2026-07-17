// desktop/src/runtime/embodiment/descriptors.ts
//
// Built-in EmbodimentDescriptor declarations.
//
// Each embodiment registers declaratively. The factory closures pull their
// dependencies exclusively from the injected EmbodimentContext — they never
// `new` a transport or reach for module-level singletons. This is what makes
// the system dependency-injected and renderer-independent.

import { EmbodimentDescriptor, EmbodimentRegistry } from './registry'
import { LivingOrbAdapter } from '../presence/living-orb-adapter'
import { NullEmbodiment } from './null-embodiment'
// Future adapters (MetaHuman, Robot) are interface-only stubs right now; their
// descriptors show how they will register once implementations land. The factory
// shapes are exercised by tests via injected mock adapters.

export const livingOrbDescriptor: EmbodimentDescriptor = {
  type: 'living-orb',
  label: 'Living Orb',
  description: 'GPU-first living orb presence driven through the render transport.',
  enabled: true,
  create: (ctx) => {
    if (!ctx.transport) {
      throw new Error('LivingOrbDescriptor requires a render transport')
    }
    return new LivingOrbAdapter(ctx.transport)
  }
}

export const nullEmbodimentDescriptor: EmbodimentDescriptor = {
  type: 'none',
  label: 'Null Embodiment',
  description: 'Inert embodiment used for headless runs and as a safe default.',
  enabled: true,
  create: () => new NullEmbodiment()
}

export const metaHumanDescriptor: EmbodimentDescriptor = {
  type: 'metahuman',
  label: 'MetaHuman',
  description: 'Future Unreal/MetaHuman adapter. Registered as disabled until the adapter dependency is injected.',
  enabled: false,
  create: (ctx) => {
    if (!ctx.metaHuman) {
      throw new Error('MetaHumanDescriptor requires an injected IMetaHumanAdapter')
    }
    return ctx.metaHuman.createEmbodiment()
  }
}

export const robotDescriptor: EmbodimentDescriptor = {
  type: 'xr-avatar',
  label: 'Robot / XR Avatar',
  description: 'Future robot or XR embodiment. Registered as disabled; enabled when a transport is injected.',
  enabled: false,
  create: (ctx) => {
    if (!ctx.transport) {
      throw new Error('RobotDescriptor requires a render transport')
    }
    return new LivingOrbAdapter(ctx.transport)
  }
}

// Builds a registry pre-seeded with all built-in descriptors.
export function createBuiltInRegistry(): EmbodimentRegistry {
  const registry = new EmbodimentRegistry()
  registry.register(nullEmbodimentDescriptor)
  registry.register(livingOrbDescriptor)
  registry.register(metaHumanDescriptor)
  registry.register(robotDescriptor)
  return registry
}
