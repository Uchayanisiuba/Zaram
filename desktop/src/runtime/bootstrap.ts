import { IEmbodiment, IExpressiveParamsSource, IPresenceRuntime } from './interfaces'
import { IRenderTransport } from './interfaces'
import type { RuntimeSnapshot } from './sources/types'
import { ExpressiveParams } from './types'
import { PresenceRuntime } from './presence/presence-runtime'
import { EmbodimentManager } from './embodiment'
import { DefaultExpressiveParamsSource } from './personality/expressive-params'
import { NullRenderTransport } from './electron/render-transport'
import { ConversationRuntime } from './sources/conversation-runtime'
import { VoiceRuntime } from './sources/voice-runtime'
import { MemoryRuntime } from './sources/memory-runtime'
import { SystemRuntime } from './sources/system-runtime'
import { RuntimeSourceAggregator } from './sources/aggregator'
import { Container, TOKENS } from './di'
import { ZaramKernel } from './kernel/zaram-kernel'
import { AnimationRuntime as EngineAnimationRuntime } from '@zaram/engine'
import { EmbodimentRegistry, CharacterRuntime } from './embodiment'
import { CognitiveBundle } from './cognitive'
import { WorldRuntime } from './world'
import { ExecutiveRuntime } from './executive'
import { CapabilityRuntime, ICapabilityRuntime } from './capability'
import { ExecutionRuntime, IExecutionRuntime, ExecutionInvoker, IExecutionInvoker } from './execution'
import { WorkspaceRuntime } from './workspace'
import { FilesystemCapabilityPack } from '../capabilities/filesystem'
import { VSCodeCapabilityPack } from '../capabilities/vscode'

export interface BootstrapOptions {
  renderTransport?: IRenderTransport
  expressiveSource?: IExpressiveParamsSource
}

export interface BootstrapResult {
  container: Container
  presenceRuntime: IPresenceRuntime
  embodiment: IEmbodiment
  buildKernel: () => ZaramKernel
}

// Adapts the Personality expressive-params source into the runtime-source
// contract expected by the aggregator. The Animation Runtime reads personality
// exclusively through this aggregated, read-only view.
function asParamsSource(source: IExpressiveParamsSource): {
  getSnapshot: () => ExpressiveParams
  subscribe: (listener: (snapshot: ExpressiveParams) => void) => () => void
  start: () => void
  stop: () => void
} {
  return {
    getSnapshot: () => source.getExpressiveParams(),
    subscribe: (listener) => source.subscribe(listener),
    start: () => {},
    stop: () => {}
  }
}

export function bootstrapPresence(options: BootstrapOptions = {}): BootstrapResult {
  const container = new Container()

  container.register(
    TOKENS.expressiveParams,
    () => options.expressiveSource ?? new DefaultExpressiveParamsSource(),
    { singleton: true }
  )
  container.register(
    TOKENS.renderTransport,
    () => options.renderTransport ?? new NullRenderTransport(),
    { singleton: true }
  )

  container.register(
    TOKENS.embodimentRegistry,
    () => new EmbodimentRegistry(),
    { singleton: true }
  )

  container.register(
    TOKENS.embodiment,
    (c) =>
      new EmbodimentManager({
        transport: c.resolve<IRenderTransport>(TOKENS.renderTransport),
        registry: c.resolve<EmbodimentRegistry>(TOKENS.embodimentRegistry)
      }),
    { singleton: true }
  )

  // Milestone 1.1: CharacterRuntime is dependency-injected into PresenceRuntime.
  // It is resolved (not newsed) so the runtime stays decoupled from construction.
  container.register(
    TOKENS.characterRuntime,
    () => new CharacterRuntime(),
    { singleton: true }
  )

  // Milestone 1.2: CognitiveBundle (Cognitive + Attention + Relationship
  // runtimes) is dependency-injected into PresenceRuntime. Internal AI state is
  // kept independent of rendering and fed event-driven from the aggregator.
  container.register(
    TOKENS.cognitiveRuntime,
    () => new CognitiveBundle(),
    { singleton: true }
  )

  // Milestone 1.3: WorldRuntime (Intelligence Runtime) aggregates system
  // perception into an immutable WorldState. It is dependency-injected and
  // advanced on the existing 30Hz frame tick; it never touches the renderer,
  // embodiment, or CharacterFrame.
  container.register(
    TOKENS.worldRuntime,
    () => new WorldRuntime(),
    { singleton: true }
  )

  // Milestone 1.4: ExecutiveRuntime (Decision Engine) is the single authority
  // for high-level AI decision-making. It coordinates every cognitive subsystem
  // and produces the high-level Intent. It is dependency-injected as a singleton
  // and advanced on the existing 30Hz frame tick; it never touches the renderer,
  // embodiment, or CharacterFrame.
  container.register(
    TOKENS.executiveRuntime,
    (c) => new ExecutiveRuntime({
      capabilityRuntime: c.resolve<ICapabilityRuntime>(TOKENS.capabilityRuntime),
      workspaceRuntime: {
        getWorkspaceSnapshot: () => {
          const ws = c.resolve<WorkspaceRuntime>(TOKENS.workspaceRuntime)
          return ws.getWorkspaceSnapshot()
        }
      }
    }),
    { singleton: true }
  )

  // Milestone 1.5: CapabilityRuntime is the OS capability discovery and
  // execution interface — the single source of truth for every capability
  // available to the OS. It is dependency-injected as a singleton and consumed
  // by the Executive Runtime strictly through ICapabilityRuntime (it requests
  // capabilities, never tools). It exposes only capability metadata and never
  // touches the drawing layer, the body layer, or any runtime implementation.
  container.register(
    TOKENS.capabilityRuntime,
    () => new CapabilityRuntime(),
    { singleton: true }
  )

  // Milestone 1.6: ExecutionRuntime is the ONLY runtime allowed to invoke
  // capabilities. It is dependency-injected as a singleton and advanced on the
  // existing 30Hz frame tick via PresenceRuntime. It enforces lifecycle,
  // timeout, retry, cancellation, progress, audit, rollback, and permission
  // enforcement. It never touches the renderer, embodiment, or CharacterFrame.
  container.register(
    TOKENS.executionInvoker,
    () => new ExecutionInvoker(),
    { singleton: true }
  )
  container.register(
    TOKENS.executionRuntime,
    (c) =>
      new ExecutionRuntime({
        invoker: c.resolve<IExecutionInvoker>(TOKENS.executionInvoker),
        capabilityRuntime: c.resolve<ICapabilityRuntime>(TOKENS.capabilityRuntime)
      }),
    { singleton: true }
  )

  container.register(TOKENS.conversationRuntime, () => new ConversationRuntime(), { singleton: true })
  container.register(TOKENS.voiceRuntime, () => new VoiceRuntime(), { singleton: true })
  container.register(TOKENS.memoryRuntime, () => new MemoryRuntime(), { singleton: true })
  container.register(TOKENS.systemRuntime, () => new SystemRuntime(), { singleton: true })
  container.register(
    TOKENS.runtimeAggregator,
    (c) =>
      new RuntimeSourceAggregator({
        conversation: c.resolve(TOKENS.conversationRuntime),
        voice: c.resolve(TOKENS.voiceRuntime),
        personality: asParamsSource(c.resolve<IExpressiveParamsSource>(TOKENS.expressiveParams)),
        memory: c.resolve(TOKENS.memoryRuntime),
        system: c.resolve(TOKENS.systemRuntime)
      }),
    { singleton: true }
  )

  container.register(
    TOKENS.engineAdapter,
    (c) => {
      const engineAnimation = new EngineAnimationRuntime(0.5)
      const system = c.resolve<{ getSnapshot(): { visualIdentity: number } }>(TOKENS.systemRuntime)
      const visualIdentity = system.getSnapshot().visualIdentity
      engineAnimation.initialize(visualIdentity)
      return engineAnimation
    },
    { singleton: true }
  )

  // Milestone 2.1: WorkspaceRuntime (Intelligence Runtime) provides semantic
  // understanding of projects. It is dependency-injected as a singleton and
  // advanced on the existing 30Hz frame tick; it never touches the renderer,
  // embodiment, or CharacterFrame.
  container.register(
    TOKENS.workspaceRuntime,
    () => new WorkspaceRuntime(),
    { singleton: true }
  )

  container.register(
    TOKENS.presenceRuntime,
    (c) => {
      const engineAnimation = c.resolve<EngineAnimationRuntime>(TOKENS.engineAdapter)
      const aggregator = c.resolve<RuntimeSourceAggregator>(TOKENS.runtimeAggregator)
      const runtime = new PresenceRuntime({
        engineAdapter: engineAnimation,
        stateProvider: aggregator,
        personality: c.resolve<IExpressiveParamsSource>(TOKENS.expressiveParams),
        embodiment: c.resolve<IEmbodiment>(TOKENS.embodiment),
        characterRuntime: c.resolve<CharacterRuntime>(TOKENS.characterRuntime),
        cognitiveRuntime: c.resolve<CognitiveBundle>(TOKENS.cognitiveRuntime),
        worldRuntime: c.resolve<WorldRuntime>(TOKENS.worldRuntime),
        executiveRuntime: c.resolve<ExecutiveRuntime>(TOKENS.executiveRuntime),
        executionRuntime: c.resolve<IExecutionRuntime>(TOKENS.executionRuntime),
        workspaceRuntime: c.resolve<WorkspaceRuntime>(TOKENS.workspaceRuntime)
      })
      aggregator.start()
      return runtime
    },
    { singleton: true }
  )
  container.register(
    TOKENS.kernel,
    (c) => new ZaramKernel(c.resolve<IPresenceRuntime>(TOKENS.presenceRuntime)),
    { singleton: true }
  )

  // Milestone 2.0: Filesystem Capability Pack is the first concrete capability
  // executed through the completed Executive -> Capability -> Execution pipeline.
  // It is wired here (not in any runtime) so the architecture remains unchanged.
  const filesystemPack = new FilesystemCapabilityPack(container.resolve<ICapabilityRuntime>(TOKENS.capabilityRuntime))
  filesystemPack.registerHandlers(container.resolve<IExecutionInvoker>(TOKENS.executionInvoker))
  filesystemPack.registerDescriptors(container.resolve<ICapabilityRuntime>(TOKENS.capabilityRuntime))

  // Sprint 2.3: VS Code Capability Pack exposes the developer's coding context
  // through the same Executive -> Capability -> Execution pipeline.
  container.register(
    TOKENS.vscodePack,
    (c) => new VSCodeCapabilityPack(c.resolve<ICapabilityRuntime>(TOKENS.capabilityRuntime), process.cwd()),
    { singleton: true }
  )

  const vscodePack = container.resolve<VSCodeCapabilityPack>(TOKENS.vscodePack)
  vscodePack.registerHandlers(container.resolve<IExecutionInvoker>(TOKENS.executionInvoker))
  vscodePack.registerDescriptors(container.resolve<ICapabilityRuntime>(TOKENS.capabilityRuntime))
  vscodePack.getAdapter().subscribe((event) => {
    if (event.type === 'vscode.context_provided' || event.type === 'vscode.active_file_changed' || event.type === 'vscode.diagnostics_updated' || event.type === 'vscode.git_status_refreshed') {
      const snapshot = vscodePack.getAdapter().getSnapshot()
      const executive = container.resolve<ExecutiveRuntime>(TOKENS.executiveRuntime)
      executive.ingestVSCodeContext({
        workspace: snapshot.workspace,
        activeFile: snapshot.activeFile,
        language: snapshot.language,
        selection: snapshot.selection,
        diagnostics: snapshot.diagnostics,
        gitBranch: snapshot.gitBranch,
        modifiedFiles: snapshot.modifiedFiles,
        connected: snapshot.connected
      })
    }
  })

  return {
    container,
    presenceRuntime: container.resolve<IPresenceRuntime>(TOKENS.presenceRuntime),
    embodiment: container.resolve<IEmbodiment>(TOKENS.embodiment),
    buildKernel: () => container.resolve<ZaramKernel>(TOKENS.kernel)
  }
}