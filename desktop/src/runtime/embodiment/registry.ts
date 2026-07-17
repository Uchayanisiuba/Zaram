// desktop/src/runtime/embodiment/registry.ts
//
// PART 1 — Embodiment Registry
//
// A renderer-independent embodiment system. Embodiments declare themselves by
// registering an EmbodimentDescriptor. Nothing instantiates an embodiment
// directly: a resolver (the DI container) uses the EmbodimentFactory closure
// to construct it on demand with injected dependencies.
//
// This layer is the abstraction future embodiments (Living Orb, MetaHuman,
// GNM-generated MetaHuman, Robots, ...) plug into. It does NOT depend on any
// renderer.

import { IEmbodiment } from '../interfaces'
import { EmbodimentType } from '../types'

// A descriptor is a static, declarative registration. It carries metadata and a
// factory but holds no live instance.
export interface EmbodimentDescriptor {
  type: EmbodimentType
  label: string
  // Short human description; used for diagnostics/selection only.
  description: string
  // Whether this embodiment is selectable at runtime (built-ins true, future
  // adapters may register as false until dependency-injected deps are present).
  enabled: boolean
  // Factory that builds the live IEmbodiment. Receives the injected context so
  // the embodiment never reaches for globals or news up its own dependencies.
  create: EmbodimentFactory
}

// The dependency context every embodiment receives. This is the *entire* set of
// injectables an embodiment may use — nothing else. Keeps embodiments free of
// ad-hoc imports.
export interface EmbodimentContext {
  transport?: import('../interfaces').IRenderTransport
  // Future embodiments may request optional adapters; absent ones are undefined.
  metaHuman?: import('./metahuman').IMetaHumanAdapter
  headGenerator?: import('./gnm').IHeadGenerator
}

export type EmbodimentFactory = (context: EmbodimentContext) => IEmbodiment

export class EmbodimentRegistry {
  private readonly descriptors = new Map<EmbodimentType, EmbodimentDescriptor>()

  register(descriptor: EmbodimentDescriptor): void {
    this.descriptors.set(descriptor.type, descriptor)
  }

  has(type: EmbodimentType): boolean {
    return this.descriptors.has(type)
  }

  get(type: EmbodimentType): EmbodimentDescriptor | undefined {
    return this.descriptors.get(type)
  }

  list(): EmbodimentDescriptor[] {
    return Array.from(this.descriptors.values())
  }

  enabled(): EmbodimentDescriptor[] {
    return this.list().filter((d) => d.enabled)
  }

  types(): EmbodimentType[] {
    return Array.from(this.descriptors.keys())
  }

  // Build a live embodiment via its factory. This is the ONLY sanctioned way to
  // obtain an IEmbodiment instance.
  resolve(type: EmbodimentType, context: EmbodimentContext): IEmbodiment {
    const descriptor = this.descriptors.get(type)
    if (!descriptor) {
      throw new Error(`No embodiment descriptor registered for: ${type}`)
    }
    return descriptor.create(context)
  }
}
