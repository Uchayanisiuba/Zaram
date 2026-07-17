import { describe, it, expect } from 'vitest'
import { bootstrapPresence } from '../../src/runtime/bootstrap'
import { NullRenderTransport } from '../../src/runtime/electron/render-transport'
import { PresenceDiagnostics } from '../../src/runtime/presence/diagnostics'
import { RuntimeSourceAggregator } from '../../src/runtime/sources/aggregator'
import { ConversationRuntime } from '../../src/runtime/sources/conversation-runtime'
import { VoiceRuntime } from '../../src/runtime/sources/voice-runtime'
import { DefaultExpressiveParamsSource } from '../../src/runtime/personality/expressive-params'
import type { ExpressiveParams } from '../../src/runtime/types'
import { AnimationRuntime } from '@zaram/engine'

// Mirror of the adapter used in bootstrap.ts: the Personality expressive-params
// source is read-only adapted into the IRuntimeSource contract.
function asParamsSource(source: DefaultExpressiveParamsSource) {
  return {
    getSnapshot: () => source.getExpressiveParams(),
    subscribe: (listener: (s: ExpressiveParams) => void) => source.subscribe(listener),
    start: () => {},
    stop: () => {}
  }
}

describe('Runtime source aggregation (Milestone 1.0)', () => {
  it('merges independent runtime sources into one snapshot', () => {
    const conversation = new ConversationRuntime()
    const voice = new VoiceRuntime()
    conversation.setPhase('speaking')
    voice.setVoiceLevel(0.8)

    const aggregator = new RuntimeSourceAggregator({
      conversation,
      voice,
      personality: asParamsSource(new DefaultExpressiveParamsSource()),
      memory: undefined,
      system: undefined
    })
    aggregator.start()

    const snapshot = aggregator.getSnapshot()
    expect(snapshot.conversation.phase).toBe('speaking')
    expect(snapshot.voice.voiceLevel).toBeCloseTo(0.8)
    expect(snapshot.personality).toBeDefined()
  })

  it('engine AnimationRuntime produces FrameState from live RuntimeState', () => {
    const engine = new AnimationRuntime(0.5)
    const snapshot = {
      state: 'Thinking' as const,
      cognitiveLoad: 0.7,
      audio: { voiceLevel: 0.3, microphoneLevel: 0.1 }
    }
    const frameState = engine.update(0.016, snapshot)
    expect(frameState).toBeDefined()
    expect(frameState.system.state).toBe('Thinking')
    expect(frameState.metadata.timestamp).toBeGreaterThan(0)
  })
})

describe('Engine -> Presence pipeline wiring', () => {
  it('flows FrameState from the Engine Adapter through the Presence Runtime', async () => {
    const transport = new NullRenderTransport()
    const { presenceRuntime, buildKernel } = bootstrapPresence({ renderTransport: transport })
    const kernel = buildKernel()
    await kernel.boot()

    await new Promise((resolve) => setTimeout(resolve, 80))
    expect((presenceRuntime as unknown as { getAnimationConnection(): string }).getAnimationConnection()).toBe('connected')
    expect(transport.getLastFrameState()).not.toBeNull()

    await kernel.dispose()
    expect(transport.getLastFrameState()).not.toBeNull()
  })
})

describe('Extended diagnostics (Milestone 1.0)', () => {
  it('exposes embodiment, FrameState frequency, dropped frames, GPU, animation, and renderer health', () => {
    const diag = new PresenceDiagnostics()
    diag.begin(0)
    diag.setPresenceRuntimeStatus('running')
    diag.recordFrameStateReceived()
    diag.recordFrameStateReceived()
    diag.recordDroppedFrame()
    diag.setGpuContextStatus('ok')
    diag.setAnimationRuntimeStatus('running')
    diag.setRendererHealth('healthy')

    const health = diag.getHealth()
    expect(health.presenceRuntimeStatus).toBe('running')
    expect(health.droppedFrames).toBe(1)
    expect(health.gpuContextStatus).toBe('ok')
    expect(health.animationRuntimeStatus).toBe('running')
    expect(health.rendererHealth).toBe('healthy')
    expect(health.frameStateFrequencyHz).toBeGreaterThanOrEqual(0)
  })
})

describe('Performance metrics (Milestone 1.2)', () => {
  it('records and exposes performance metrics', () => {
    const diag = new PresenceDiagnostics()
    diag.begin(0)
    diag.setPresenceRuntimeStatus('running')
    diag.setGpuFrameTime(8.5)
    diag.setCpuFrameTime(2.1)
    diag.setFrameBudget(16.6)
    diag.setRefreshRate(60)
    diag.setQualityLevel('adaptive')

    const health = diag.getHealth()
    expect(health.gpuFrameTimeMs).toBeCloseTo(8.5)
    expect(health.cpuFrameTimeMs).toBeCloseTo(2.1)
    expect(health.frameBudgetMs).toBeCloseTo(16.6)
    expect(health.refreshRateHz).toBe(60)
    expect(health.qualityLevel).toBe('adaptive')
  })
})
