import { describe, it, expect, vi } from 'vitest'
import { PresenceRuntime } from '../../src/runtime/presence/presence-runtime'
import { LivingOrbAdapter } from '../../src/runtime/presence/living-orb-adapter'
import { AnimationRuntime } from '@zaram/engine'
import { DefaultExpressiveParamsSource } from '../../src/runtime/personality/expressive-params'
import { NullRenderTransport } from '../../src/runtime/electron/render-transport'
import { RuntimeSourceAggregator } from '../../src/runtime/sources/aggregator'
import { ConversationRuntime } from '../../src/runtime/sources/conversation-runtime'
import { VoiceRuntime } from '../../src/runtime/sources/voice-runtime'
import { MemoryRuntime } from '../../src/runtime/sources/memory-runtime'
import { SystemRuntime } from '../../src/runtime/sources/system-runtime'

function buildRuntime() {
  const transport = new NullRenderTransport()
  const adapter = new LivingOrbAdapter(transport)
  const aggregator = new RuntimeSourceAggregator({
    conversation: new ConversationRuntime(),
    voice: new VoiceRuntime(),
    memory: new MemoryRuntime(),
    system: new SystemRuntime()
  })
  const engineAnimation = new AnimationRuntime(0.5)
  const runtime = new PresenceRuntime({
    engineAdapter: engineAnimation,
    stateProvider: aggregator,
    personality: new DefaultExpressiveParamsSource(),
    embodiment: adapter
  })
  return { runtime, adapter, transport, aggregator, engineAnimation }
}

describe('PresenceRuntime data flow', () => {
  it('forwards FrameState from the Engine Adapter to the LivingOrbAdapter', async () => {
    const { runtime, adapter, transport, aggregator } = buildRuntime()
    aggregator.start()
    await runtime.initialize()
    await runtime.start()

    await new Promise((resolve) => setTimeout(resolve, 150))
    expect(transport.getLastFrameState()).not.toBeNull()
    expect(adapter.getLastFrame()).not.toBeNull()
    expect(runtime.getAnimationConnection()).toBe('connected')

    runtime.shutdown()
  })

  it('reports embodiment health and connection diagnostics', async () => {
    const { runtime, adapter } = buildRuntime()
    await runtime.initialize()
    await runtime.start()

    const health = runtime.getHealth()
    expect(health.currentEmbodiment).toBe('living-orb')
    expect(health.embodimentHealthy).toBe(true)
    expect(health.status).toBe('healthy')
    expect(runtime.getEmbodimentType()).toBe('living-orb')
  })

  it('does not forward frames before start()', () => {
    const { runtime, transport } = buildRuntime()
    expect(transport.getLastFrameState()).toBeNull()
  })

  it('consumes an externally produced FrameState', async () => {
    const { runtime, transport } = buildRuntime()
    await runtime.initialize()
    await runtime.start()
    runtime.consumeFrameState({
      visual: { presence: 0.4, energy: 0.4, focus: 0.4, activity: 0.4 },
      audio: { voiceLevel: 0, microphoneLevel: 0 },
      emotion: { calmness: 0.5, confidence: 0.5, curiosity: 0.5, warmth: 0.5, empathy: 0.5, playfulness: 0.5 },
      system: { state: 'Thinking', cognitiveLoad: 0.2, visualIdentity: 0.5 },
      metadata: { timestamp: Date.now(), correlationId: 'test', version: '1.0.0' },
      sequence: 0
    })
    expect(transport.getLastFrameState()?.sequence).toBe(1)
  })

  it('switches embodiment without knowing the implementation', async () => {
    const { runtime } = buildRuntime()
    await runtime.initialize()
    await runtime.start()

    const mockEmbodiment = {
      initialize: vi.fn().mockResolvedValue(undefined),
      start: vi.fn().mockResolvedValue(undefined),
      pause: vi.fn().mockResolvedValue(undefined),
      resume: vi.fn().mockResolvedValue(undefined),
      shutdown: vi.fn().mockResolvedValue(undefined),
      setFrameState: vi.fn(),
      getStatus: () => ({
        type: 'xr-avatar' as const,
        state: 'running' as const,
        healthy: true,
        lastUpdated: Date.now()
      })
    }
    runtime.setEmbodiment(mockEmbodiment)
    runtime.consumeFrameState({
      visual: { presence: 0.4, energy: 0.4, focus: 0.4, activity: 0.4 },
      audio: { voiceLevel: 0, microphoneLevel: 0 },
      emotion: { calmness: 0.5, confidence: 0.5, curiosity: 0.5, warmth: 0.5, empathy: 0.5, playfulness: 0.5 },
      system: { state: 'Thinking', cognitiveLoad: 0.2, visualIdentity: 0.5 },
      metadata: { timestamp: Date.now(), correlationId: 'test', version: '1.0.0' },
      sequence: 0
    })
    expect(mockEmbodiment.setFrameState).toHaveBeenCalled()
    expect(runtime.getEmbodimentType()).toBe('xr-avatar')
  })
})
