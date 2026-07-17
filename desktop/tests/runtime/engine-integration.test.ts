import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { join } from 'path'
import { AnimationRuntime } from '@zaram/engine'

describe('AnimationRuntime as engine adapter', () => {
  it('initializes with visualIdentity from the system', () => {
    const engine = new AnimationRuntime(0.5)
    engine.initialize(0.8)
    const frameState = engine.update(0.016, {
      state: 'Thinking',
      cognitiveLoad: 0.7,
      audio: { voiceLevel: 0.3, microphoneLevel: 0.1 }
    })
    expect(frameState.system.visualIdentity).toBe(0.8)
  })

  it('receives RuntimeState and returns FrameState', () => {
    const engine = new AnimationRuntime(0.5)
    const runtimeState = {
      state: 'Thinking' as const,
      cognitiveLoad: 0.7,
      audio: { voiceLevel: 0.3, microphoneLevel: 0.1 }
    }
    const frameState = engine.update(0.016, runtimeState)
    expect(frameState).toBeDefined()
    expect(frameState.system.state).toBe('Thinking')
    expect(frameState.metadata.timestamp).toBeGreaterThan(0)
  })

  it('owns a single AnimationRuntime instance', () => {
    const engine = new AnimationRuntime(0.5)
    engine.initialize(0.9)
    const frameState = engine.update(0.016, {
      state: 'Speaking' as const,
      cognitiveLoad: 0.3,
      audio: { voiceLevel: 0.6 }
    })
    expect(frameState.system.visualIdentity).toBe(0.9)
  })

  it('has no renderer dependency', () => {
    const source = readFileSync(join(__dirname, '../../../packages/zaram-engine/runtime/AnimationRuntime.ts'), 'utf-8')
    expect(source).not.toMatch(/three|webgl|renderer|shader|electron/i)
  })
})
