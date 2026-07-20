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
import { VisionCapabilityPack } from '../capabilities/vision'
import { KnowledgeCapabilityPack } from '../capabilities/knowledge'

export interface BootstrapOptions {
  renderTransport?: IRenderTransport
  expressiveSource?: IExpressiveParamsSource
  backendUrl?: string
}

export interface BootstrapResult {
  container: Container
  presenceRuntime: IPresenceRuntime
  embodiment: IEmbodiment
  tokens: typeof TOKENS
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
  console.log('[STARTUP] Registered: ExpressiveParams')

  container.register(
    TOKENS.renderTransport,
    () => options.renderTransport ?? new NullRenderTransport(),
    { singleton: true }
  )
  console.log('[STARTUP] Registered: RenderTransport')

  container.register(
    TOKENS.embodimentRegistry,
    () => new EmbodimentRegistry(),
    { singleton: true }
  )
  console.log('[STARTUP] Registered: EmbodimentRegistry')

  container.register(
    TOKENS.embodiment,
    (c) =>
      new EmbodimentManager({
        transport: c.resolve<IRenderTransport>(TOKENS.renderTransport),
        registry: c.resolve<EmbodimentRegistry>(TOKENS.embodimentRegistry)
      }),
    { singleton: true }
  )
  console.log('[STARTUP] Registered: Embodiment')

  container.register(
    TOKENS.characterRuntime,
    () => new CharacterRuntime(),
    { singleton: true }
  )
  console.log('[STARTUP] Registered: CharacterRuntime')

  container.register(
    TOKENS.cognitiveRuntime,
    () => new CognitiveBundle(),
    { singleton: true }
  )
  console.log('[STARTUP] Registered: CognitiveRuntime')

  container.register(
    TOKENS.worldRuntime,
    () => new WorldRuntime(),
    { singleton: true }
  )
  console.log('[STARTUP] Registered: WorldRuntime')

  // Milestone 1.4: ExecutiveRuntime (Decision Engine) is the single authority
  // for high-level AI decision-making. It coordinates every cognitive subsystem
  // and produces the high-level Intent. It is dependency-injected as a singleton
  // and advanced on the existing 30Hz frame tick; it never touches the renderer,
  // embodiment, or CharacterFrame.
  container.register(
    TOKENS.executiveRuntime,
    (c) => {
      console.log('[STARTUP] Instantiating ExecutiveRuntime...')
      const instance = new ExecutiveRuntime({
        capabilityRuntime: c.resolve<ICapabilityRuntime>(TOKENS.capabilityRuntime),
        workspaceRuntime: {
          getWorkspaceSnapshot: () => {
            const ws = c.resolve<WorkspaceRuntime>(TOKENS.workspaceRuntime)
            return ws.getWorkspaceSnapshot()
          }
        }
      })
      console.log('[STARTUP] ExecutiveRuntime instantiated')
      return instance
    },
    { singleton: true }
  )
  console.log('[STARTUP] Registered: ExecutiveRuntime')

  // Milestone 1.5: CapabilityRuntime is the OS capability discovery and
  // execution interface — the single source of truth for every capability
  // available to the OS. It is dependency-injected as a singleton and consumed
  // by the Executive Runtime strictly through ICapabilityRuntime (it requests
  // capabilities, never tools). It exposes only capability metadata and never
  // touches the drawing layer, the body layer, or any runtime implementation.
  container.register(
    TOKENS.capabilityRuntime,
    () => {
      console.log('[STARTUP] Instantiating CapabilityRuntime...')
      const instance = new CapabilityRuntime()
      console.log('[STARTUP] CapabilityRuntime instantiated')
      return instance
    },
    { singleton: true }
  )
  console.log('[STARTUP] Registered: CapabilityRuntime')

  // Milestone 1.6: ExecutionRuntime is the ONLY runtime allowed to invoke
  // capabilities. It is dependency-injected as a singleton and advanced on the
  // existing 30Hz frame tick via PresenceRuntime. It enforces lifecycle,
  // timeout, retry, cancellation, progress, audit, rollback, and permission
  // enforcement. It never touches the renderer, embodiment, or CharacterFrame.
  container.register(
    TOKENS.executionInvoker,
    () => {
      console.log('[STARTUP] Instantiating ExecutionInvoker...')
      const instance = new ExecutionInvoker()
      console.log('[STARTUP] ExecutionInvoker instantiated')
      return instance
    },
    { singleton: true }
  )
  container.register(
    TOKENS.executionRuntime,
    (c) => {
      console.log('[STARTUP] Instantiating ExecutionRuntime...')
      const instance = new ExecutionRuntime({
        invoker: c.resolve<IExecutionInvoker>(TOKENS.executionInvoker),
        capabilityRuntime: c.resolve<ICapabilityRuntime>(TOKENS.capabilityRuntime)
      })
      console.log('[STARTUP] ExecutionRuntime instantiated')
      return instance
    },
    { singleton: true }
  )
  console.log('[STARTUP] Registered: ExecutionRuntime')

  container.register(TOKENS.conversationRuntime, () => new ConversationRuntime(), { singleton: true })
  container.register(TOKENS.voiceRuntime, () => new VoiceRuntime(), { singleton: true })
  container.register(TOKENS.memoryRuntime, () => new MemoryRuntime(), { singleton: true })
  container.register(TOKENS.systemRuntime, () => new SystemRuntime(), { singleton: true })
  console.log('[STARTUP] Registered: Conversation/Voice/Memory/SystemRuntimes')

  container.register(
    TOKENS.runtimeAggregator,
    (c) => {
      console.log('[STARTUP] Instantiating RuntimeSourceAggregator...')
      const instance = new RuntimeSourceAggregator({
        conversation: c.resolve(TOKENS.conversationRuntime),
        voice: c.resolve(TOKENS.voiceRuntime),
        personality: asParamsSource(c.resolve<IExpressiveParamsSource>(TOKENS.expressiveParams)),
        memory: c.resolve(TOKENS.memoryRuntime),
        system: c.resolve(TOKENS.systemRuntime)
      })
      console.log('[STARTUP] RuntimeSourceAggregator instantiated')
      return instance
    },
    { singleton: true }
  )

  container.register(
    TOKENS.engineAdapter,
    (c) => {
      console.log('[STARTUP] Instantiating EngineAdapter...')
      const engineAnimation = new EngineAnimationRuntime(0.5)
      const system = c.resolve<{ getSnapshot(): { visualIdentity: number } }>(TOKENS.systemRuntime)
      const visualIdentity = system.getSnapshot().visualIdentity
      engineAnimation.initialize(visualIdentity)
      console.log('[STARTUP] EngineAdapter instantiated')
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
    () => {
      console.log('[STARTUP] Instantiating WorkspaceRuntime...')
      const instance = new WorkspaceRuntime()
      console.log('[STARTUP] WorkspaceRuntime instantiated')
      return instance
    },
    { singleton: true }
  )
  console.log('[STARTUP] Registered: WorkspaceRuntime')

  container.register(
    TOKENS.presenceRuntime,
    (c) => {
      console.log('[STARTUP] Instantiating PresenceRuntime...')
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
      console.log('[STARTUP] PresenceRuntime instantiated')
      return runtime
    },
    { singleton: true }
  )
  console.log('[STARTUP] Registered: PresenceRuntime')
  container.register(
    TOKENS.kernel,
    (c) => {
      console.log('[STARTUP] Instantiating ZaramKernel...')
      const instance = new ZaramKernel(c.resolve<IPresenceRuntime>(TOKENS.presenceRuntime))
      console.log('[STARTUP] ZaramKernel instantiated')
      return instance
    },
    { singleton: true }
  )

  // Milestone 2.0: Filesystem Capability Pack is the first concrete capability
  // executed through the completed Executive -> Capability -> Execution pipeline.
  // It is wired here (not in any runtime) so the architecture remains unchanged.
  console.log('[STARTUP] Registering FilesystemCapabilityPack...')
  const filesystemPack = new FilesystemCapabilityPack(container.resolve<ICapabilityRuntime>(TOKENS.capabilityRuntime))
  filesystemPack.registerHandlers(container.resolve<IExecutionInvoker>(TOKENS.executionInvoker))
  filesystemPack.registerDescriptors(container.resolve<ICapabilityRuntime>(TOKENS.capabilityRuntime))
  console.log('[STARTUP] FilesystemCapabilityPack registered')

  // Sprint Alpha.5: Vision Capability Pack integrates Qwen2.5-VL 7B as the
  // primary vision backend through the existing Executive -> Capability -> Execution pipeline.
  console.log('[STARTUP] Registering VisionCapabilityPack...')
  const visionPack = new VisionCapabilityPack(container.resolve<ICapabilityRuntime>(TOKENS.capabilityRuntime))
  visionPack.registerHandlers(container.resolve<IExecutionInvoker>(TOKENS.executionInvoker))
  visionPack.registerDescriptors(container.resolve<ICapabilityRuntime>(TOKENS.capabilityRuntime))
  console.log('[STARTUP] VisionCapabilityPack registered')

  // Sprint Alpha.5: Knowledge Capability Pack adds internet search as a capability
  // consumed by Executive Runtime. Local-first by default; internet only when needed.
  console.log('[STARTUP] Registering KnowledgeCapabilityPack...')
  const knowledgePack = new KnowledgeCapabilityPack(container.resolve<ICapabilityRuntime>(TOKENS.capabilityRuntime))
  knowledgePack.registerHandlers(container.resolve<IExecutionInvoker>(TOKENS.executionInvoker))
  knowledgePack.registerDescriptors(container.resolve<ICapabilityRuntime>(TOKENS.capabilityRuntime))
  console.log('[STARTUP] KnowledgeCapabilityPack registered')

  // Sprint 2.3: VS Code Capability Pack exposes the developer's coding context
  // through the same Executive -> Capability -> Execution pipeline.
  container.register(
    TOKENS.vscodePack,
    (c) => {
      console.log('[STARTUP] Instantiating VSCodeCapabilityPack...')
      const instance = new VSCodeCapabilityPack(c.resolve<ICapabilityRuntime>(TOKENS.capabilityRuntime), process.cwd())
      console.log('[STARTUP] VSCodeCapabilityPack instantiated')
      return instance
    },
    { singleton: true }
  )
  console.log('[STARTUP] Registered: VSCodePack')

  const vscodePack = container.resolve<VSCodeCapabilityPack>(TOKENS.vscodePack)
  vscodePack.registerHandlers(container.resolve<IExecutionInvoker>(TOKENS.executionInvoker))
  vscodePack.registerDescriptors(container.resolve<ICapabilityRuntime>(TOKENS.capabilityRuntime))
  console.log('[STARTUP] VSCodeCapabilityPack handlers/descriptors registered')
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

  if (options.backendUrl) {
    console.log('[STARTUP] Registering backend capability handlers...')
    const invoker = container.resolve<IExecutionInvoker>(TOKENS.executionInvoker)
    const capabilityRuntime = container.resolve<ICapabilityRuntime>(TOKENS.capabilityRuntime)
    invoker.register('conversation.runtime', async (req, ctx, controls) => {
      try {
        const text = ((req.input as any)?.text || (req.input as any)?.prompt || '') as string
        const persona = ((req.input as any)?.persona as string | undefined) || 'zaram_prime'
        const model = ((req.input as any)?.model as string | undefined) || 'gemma3:latest'
        const response = await callBackendChat(options.backendUrl!, text, persona, model)
        controls.succeed({ response })
      } catch (error) {
        controls.fail(error instanceof Error ? error.message : String(error))
      }
    })
    invoker.register('reasoning.generate', async (req, ctx, controls) => {
      try {
        const prompt = ((req.input as any)?.prompt || '') as string
        const persona = ((req.input as any)?.persona as string | undefined) || 'zaram_prime'
        const model = ((req.input as any)?.model as string | undefined) || 'gemma3:latest'
        const response = await callBackendChat(options.backendUrl!, prompt, persona, model)
        controls.succeed({ response })
      } catch (error) {
        controls.fail(error instanceof Error ? error.message : String(error))
      }
    })

    const backendCaps = [
      {
        id: 'conversation.runtime',
        name: 'Conversation Runtime',
        description: 'Send a message to the Executive Runtime and stream a response from the backend LLM.',
        category: 'conversation',
        permissions: [] as string[],
        inputSchema: { type: 'object', properties: { text: { type: 'string' }, prompt: { type: 'string' } }, required: [] },
        outputSchema: { type: 'object', properties: { response: { type: 'string' } } },
        latencyEstimateMs: 1500,
        location: 'backend'
      },
      {
        id: 'reasoning.generate',
        name: 'Reasoning Generate',
        description: 'Generate a reasoning response from the backend LLM.',
        category: 'reasoning',
        permissions: [] as string[],
        inputSchema: { type: 'object', properties: { prompt: { type: 'string' } }, required: ['prompt'] },
        outputSchema: { type: 'object', properties: { response: { type: 'string' } } },
        latencyEstimateMs: 1500,
        location: 'backend'
      }
    ]
    for (const cap of backendCaps) {
      try {
        capabilityRuntime.register({
          id: cap.id,
          name: cap.name,
          description: cap.description,
          category: cap.category,
          permissions: cap.permissions as any,
          inputSchema: cap.inputSchema,
          outputSchema: cap.outputSchema,
          availability: 'available',
          latencyEstimateMs: cap.latencyEstimateMs,
          location: cap.location,
          cost: 0,
          enabled: true,
          source: 'backend',
          tags: ['llm', 'backend']
        } as any)
      } catch { /* descriptor may already exist */ }
    }
    console.log('[STARTUP] Backend capability handlers registered')
  }

  console.log('[STARTUP] Resolving PresenceRuntime...')
  const presenceRuntime = container.resolve<IPresenceRuntime>(TOKENS.presenceRuntime)
  console.log('[STARTUP] PresenceRuntime resolved')
  
  console.log('[STARTUP] Resolving Embodiment...')
  const embodiment = container.resolve<IEmbodiment>(TOKENS.embodiment)
  console.log('[STARTUP] Embodiment resolved')

  console.log('[STARTUP] Bootstrap complete')
  return {
    container,
    presenceRuntime,
    embodiment,
    tokens: TOKENS,
    buildKernel: () => container.resolve<ZaramKernel>(TOKENS.kernel)
  }
}

import http from 'http'
import https from 'https'

const RETRY_DELAYS = [1000, 2000, 4000]

async function callBackendChat(baseUrl: string, text: string, persona: string = 'zaram_prime', model: string = 'gemma3:latest'): Promise<string> {
  const url = new URL(`${baseUrl}/chat`)
  const postData = JSON.stringify({ text, model, persona })
  
  console.log(`[STAGE-9][Backend] POST ${url.toString()} text='${text.slice(0, 50)}...' persona=${persona} model=${model}`)
  
  let lastError: any = null
  for (let attempt = 0; attempt < RETRY_DELAYS.length + 1; attempt++) {
    try {
      return await new Promise((resolve, reject) => {
        const protocol = url.protocol === 'https:' ? https : http
        const startTime = Date.now()
        
        const req = protocol.request({
          hostname: url.hostname,
          port: url.port || (url.protocol === 'https:' ? 443 : 80),
          path: url.pathname,
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(postData)
          }
        }, (res) => {
          if (res.statusCode !== 200) {
            reject(new Error(`Backend chat failed: ${res.statusCode} ${res.statusMessage}`))
            return
          }

          const reader = res
          const decoder = new TextDecoder()
          let fullText = ''
          let tokenCount = 0
          let buffer = ''

          reader.on('data', (chunk: Buffer) => {
            buffer += decoder.decode(chunk, { stream: true })
            const lines = buffer.split('\n')
            buffer = lines.pop() || ''
            for (const line of lines) {
              const trimmed = line.trim()
              if (!trimmed || !trimmed.startsWith('data: ')) continue
              const data = trimmed.slice(6)
              if (data === '[DONE]') {
                console.log(`[STAGE-9][Backend] Stream complete. Total tokens: ${tokenCount}`)
                resolve(fullText)
                return
              }
              try {
                const event = JSON.parse(data)
                if (event.type === 'token') {
                  tokenCount++
                  fullText += event.content || ''
                } else if (event.type === 'error') {
                  reject(new Error(event.content || 'Backend error'))
                  return
                }
              } catch {
                // ignore malformed events
              }
            }
          })

          reader.on('end', () => {
            console.log(`[STAGE-9][Backend] Stream ended. Total tokens: ${tokenCount}`)
            resolve(fullText)
          })
        })

        req.on('error', (error) => {
          console.error(`[STAGE-9][Backend] Request error:`, error)
          reject(error)
        })

        req.setTimeout(120000, () => {
          req.destroy()
          reject(new Error('Backend chat timeout'))
        })

        req.write(postData)
        req.end()
      })
    } catch (error) {
      lastError = error
      console.error(`[STAGE-9][Backend] Attempt ${attempt + 1} failed:`, error)
      if (attempt < RETRY_DELAYS.length) {
        await new Promise(r => setTimeout(r, RETRY_DELAYS[attempt]))
      }
    }
  }
  throw lastError || new Error('Backend chat failed after retries')
}