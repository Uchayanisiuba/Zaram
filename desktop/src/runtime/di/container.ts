export const TOKENS = {
  frameStateProducer: 'FrameStateProducer',
  expressiveParams: 'ExpressiveParamsSource',
  renderTransport: 'RenderTransport',
  embodiment: 'Embodiment',
  presenceRuntime: 'PresenceRuntime',
  kernel: 'Kernel',
  conversationRuntime: 'ConversationRuntime',
  voiceRuntime: 'VoiceRuntime',
  memoryRuntime: 'MemoryRuntime',
  systemRuntime: 'SystemRuntime',
  runtimeAggregator: 'RuntimeSourceAggregator',
  animationRuntime: 'AnimationRuntime',
  engineAdapter: 'EngineAdapter',
  embodimentRegistry: 'EmbodimentRegistry',
  characterRuntime: 'CharacterRuntime',
  cognitiveRuntime: 'CognitiveRuntime',
  worldRuntime: 'WorldRuntime',
  executiveRuntime: 'ExecutiveRuntime',
  capabilityRuntime: 'CapabilityRuntime',
  executionRuntime: 'ExecutionRuntime',
  executionInvoker: 'ExecutionInvoker',
  workspaceRuntime: 'WorkspaceRuntime',
  vscodePack: 'VSCodePack'
} as const

export type Token = (typeof TOKENS)[keyof typeof TOKENS]

export interface ServiceDefinition<T> {
  factory: (container: Container) => T
  singleton: boolean
  instance?: T
}

export class Container {
  private readonly registry = new Map<string, ServiceDefinition<unknown>>()

  register<T>(
    token: string,
    factory: (container: Container) => T,
    options: { singleton?: boolean } = {}
  ): this {
    this.registry.set(token, {
      factory: factory as (container: Container) => unknown,
      singleton: options.singleton ?? true,
      instance: undefined
    })
    return this
  }

  resolve<T>(token: string): T {
    const definition = this.registry.get(token)
    if (!definition) {
      throw new Error(`No service registered for token: ${token}`)
    }
    if (definition.singleton) {
      if (definition.instance === undefined) {
        definition.instance = definition.factory(this)
      }
      return definition.instance as T
    }
    return definition.factory(this) as T
  }

  has(token: string): boolean {
    return this.registry.has(token)
  }

  clear(): void {
    this.registry.clear()
  }
}
