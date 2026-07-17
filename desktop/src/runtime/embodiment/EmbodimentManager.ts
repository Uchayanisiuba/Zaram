// desktop/src/runtime/embodiment/EmbodimentManager.ts
//
// Embodiment Manager: selects and switches between embodiments without
// modifying the runtime. Supported today via the DI-driven registry:
// Living Orb (and the Null embodiment). Future embodiments (MetaHuman,
// GNM-generated MetaHuman, Robots, XR Avatars) register descriptors and are
// resolved through the same registry — never instantiated directly.

import { IEmbodiment, IRenderTransport } from '../interfaces'
import { EmbodimentStatus, EmbodimentType } from '../types'
import { EmbodimentContext, EmbodimentDescriptor, EmbodimentRegistry } from './registry'
import { createBuiltInRegistry } from './descriptors'

export interface EmbodimentManagerOptions {
  transport: IRenderTransport
  // Optional injected registry. Defaults to the built-in registry so the manager
  // is self-contained; the bootstrap may supply a richer registry.
  registry?: EmbodimentRegistry
  // Initial embodiment type. Defaults to living-orb.
  initial?: EmbodimentType
  // Optional injected adapters for future embodiments (MetaHuman, GNM head gen).
  metaHuman?: import('./metahuman').IMetaHumanAdapter
  headGenerator?: import('./gnm').IHeadGenerator
}

export class EmbodimentManager implements IEmbodiment {
  private readonly registry: EmbodimentRegistry
  private readonly context: EmbodimentContext
  private current: IEmbodiment
  private currentType: EmbodimentType

  constructor(options: EmbodimentManagerOptions) {
    this.registry = options.registry ?? createBuiltInRegistry()
    // Ensure built-in embodiments are always available, even when an external
    // registry is injected (idempotent — re-registration is harmless).
    for (const d of createBuiltInRegistry().list()) {
      if (!this.registry.has(d.type)) this.registry.register(d)
    }
    this.context = {
      transport: options.transport,
      metaHuman: options.metaHuman,
      headGenerator: options.headGenerator
    }
    const initial = options.initial ?? 'living-orb'
    this.currentType = initial
    this.current = this.registry.resolve(initial, this.context)
  }

  // Registration. Accepts either a full EmbodimentDescriptor (preferred) or the
  // legacy (type, embodiment) tuple used by Milestone 1.0 tests.
  register(descriptor: EmbodimentDescriptor): void
  register(type: EmbodimentType, embodiment: IEmbodiment): void
  register(
    descriptorOrType: EmbodimentDescriptor | EmbodimentType,
    maybeEmbodiment?: IEmbodiment
  ): void {
    if (typeof descriptorOrType === 'string') {
      const type = descriptorOrType
      const embodiment = maybeEmbodiment as IEmbodiment
      this.registry.register({
        type,
        label: type,
        description: 'Runtime-registered embodiment',
        enabled: true,
        create: () => embodiment
      })
      return
    }
    this.registry.register(descriptorOrType)
  }

  getAvailable(): EmbodimentType[] {
    return this.registry.types()
  }

  getDescriptors(): EmbodimentDescriptor[] {
    return this.registry.list()
  }

  getCurrentType(): EmbodimentType {
    return this.currentType
  }

  async switchTo(type: EmbodimentType): Promise<void> {
    if (type === this.currentType) return
    if (!this.registry.has(type)) {
      throw new Error(`Unknown embodiment type: ${type}`)
    }

    if (this.currentType !== 'none') {
      try {
        await this.current.shutdown()
      } catch {
        /* best-effort shutdown */
      }
    }

    this.current = this.registry.resolve(type, this.context)
    this.currentType = type
    await this.current.initialize()
    await this.current.start()
  }

  async initialize(): Promise<void> {
    await this.current.initialize()
  }

  async start(): Promise<void> {
    await this.current.start()
  }

  async pause(): Promise<void> {
    await this.current.pause()
  }

  async resume(): Promise<void> {
    await this.current.resume()
  }

  async shutdown(): Promise<void> {
    try {
      await this.current.shutdown()
    } catch {
      /* best-effort */
    }
    this.currentType = 'none'
  }

  setFrameState(frameState: any): void {
    this.current.setFrameState(frameState)
  }

  getStatus(): EmbodimentStatus {
    return this.current.getStatus()
  }
}
