import { describe, it, expect } from 'vitest'
import { LivingOrbAdapter } from '../../src/runtime/presence/living-orb-adapter'
import { NullRenderTransport } from '../../src/runtime/electron/render-transport'

describe('LivingOrbAdapter', () => {
  it('reports a living-orb embodiment type', () => {
    const transport = new NullRenderTransport()
    const adapter = new LivingOrbAdapter(transport)
    expect(adapter.getStatus().type).toBe('living-orb')
    expect(adapter.getStatus().state).toBe('uninitialized')
  })

  it('runs the full lifecycle', async () => {
    const transport = new NullRenderTransport()
    const adapter = new LivingOrbAdapter(transport)
    await adapter.initialize()
    expect(adapter.getStatus().state).toBe('ready')
    await adapter.start()
    expect(adapter.getStatus().state).toBe('running')
    await adapter.pause()
    expect(adapter.getStatus().state).toBe('paused')
    await adapter.resume()
    expect(adapter.getStatus().state).toBe('running')
    await adapter.shutdown()
    expect(adapter.getStatus().state).toBe('shutdown')
  })

  it('forwards FrameState to the renderer transport without rendering', async () => {
    const transport = new NullRenderTransport()
    const adapter = new LivingOrbAdapter(transport)
    await adapter.initialize()
    await adapter.start()

    const frameState = {
      visual: { presence: 0.5, energy: 0.5, focus: 0.5, activity: 0.5 },
      audio: { voiceLevel: 0, microphoneLevel: 0 },
      emotion: { calmness: 0.5, confidence: 0.5, curiosity: 0.5, warmth: 0.5, empathy: 0.5, playfulness: 0.5 },
      system: { state: 'Speaking' as const, cognitiveLoad: 0.2, visualIdentity: 0.5 },
      metadata: { timestamp: Date.now(), correlationId: 'test', version: '1.0.0' },
      sequence: 1
    }
    adapter.setFrameState(frameState)
    expect(transport.getLastFrameState()).toBe(frameState)
    expect(adapter.getLastFrame()).toBe(frameState)
  })

  it('waits for a not-yet-ready transport before initializing', async () => {
    const transport = new NullRenderTransport()
    transport.setReady(false)
    const adapter = new LivingOrbAdapter(transport)
    const init = adapter.initialize()
    expect(adapter.getStatus().state).toBe('initializing')
    transport.setReady(true)
    await init
    expect(adapter.getStatus().state).toBe('ready')
  })

  it('does not import or contain renderer code', () => {
    const transport = new NullRenderTransport()
    const adapter = new LivingOrbAdapter(transport)
    const proto = Object.getPrototypeOf(adapter)
    const methods = Object.getOwnPropertyNames(proto)
    expect(methods).not.toContain('render')
  })
})
