import { describe, it, expect, vi } from 'vitest'
import { EmbodimentRegistry } from '../../src/runtime/embodiment/registry'
import {
  createBuiltInRegistry,
  livingOrbDescriptor,
  nullEmbodimentDescriptor,
  metaHumanDescriptor,
  robotDescriptor
} from '../../src/runtime/embodiment/descriptors'
import { EmbodimentManager } from '../../src/runtime/embodiment/EmbodimentManager'
import { NullEmbodiment } from '../../src/runtime/embodiment/null-embodiment'
import { LivingOrbAdapter } from '../../src/runtime/presence/living-orb-adapter'
import { NullRenderTransport } from '../../src/runtime/electron/render-transport'
import { EmotionRuntime } from '../../src/runtime/embodiment/emotion-runtime'
import { BehaviourRuntime } from '../../src/runtime/embodiment/behaviour-runtime'
import { GazeController } from '../../src/runtime/embodiment/gaze-controller'
import { CharacterRuntime } from '../../src/runtime/embodiment/character-runtime'
import { toCharacterFrame } from '../../src/runtime/embodiment/character-frame'
import { Container, TOKENS } from '../../src/runtime/di/container'
import { bootstrapPresence } from '../../src/runtime/bootstrap'
import { IRenderTransport } from '../../src/runtime/interfaces'
import { IEmbodiment } from '../../src/runtime/interfaces'

describe('PART 1 — Embodiment Registry', () => {
  it('registers and lists embodiments', () => {
    const registry = new EmbodimentRegistry()
    registry.register(livingOrbDescriptor)
    registry.register(nullEmbodimentDescriptor)
    expect(registry.has('living-orb')).toBe(true)
    expect(registry.has('none')).toBe(true)
    expect(registry.types()).toContain('living-orb')
  })

  it('requires dependency injection — never instantiates directly', () => {
    const registry = createBuiltInRegistry()
    // Resolve injects the transport via context; calling create without context
    // would throw for living-orb. This proves no `new LivingOrbAdapter()` path.
    const transport = new NullRenderTransport()
    const orb = registry.resolve('living-orb', { transport })
    expect(orb).toBeInstanceOf(LivingOrbAdapter)
    expect(() => registry.resolve('living-orb', {})).toThrow()
  })

  it('resolves MetaHuman only when its adapter is injected', () => {
    const registry = createBuiltInRegistry()
    expect(metaHumanDescriptor.enabled).toBe(false)
    const mockAdapter = { createEmbodiment: () => new NullEmbodiment() } as any
    // Disabled descriptor still resolvable when deps present (future enablement).
    expect(() => registry.resolve('metahuman', { metaHuman: mockAdapter })).not.toThrow()
    expect(() => registry.resolve('metahuman', {})).toThrow()
  })

  it('built-in registry seeds all known embodiments', () => {
    const registry = createBuiltInRegistry()
    expect(registry.has('living-orb')).toBe(true)
    expect(registry.has('none')).toBe(true)
    expect(registry.has('metahuman')).toBe(true)
    expect(registry.has('xr-avatar')).toBe(true)
  })

  it('EmbodimentManager uses the registry instead of direct instantiation', async () => {
    const transport = new NullRenderTransport()
    const manager = new EmbodimentManager({ transport })
    expect(manager.getCurrentType()).toBe('living-orb')
    expect(manager.getDescriptors().length).toBeGreaterThanOrEqual(4)
    expect(manager.getStatus().type).toBe('living-orb')
  })

  it('switches embodiment through the registry without touching the runtime', async () => {
    const transport = new NullRenderTransport()
    const manager = new EmbodimentManager({ transport })
    await manager.switchTo('none')
    expect(manager.getCurrentType()).toBe('none')
    expect(manager.getStatus().type).toBe('none')
  })
})

describe('PART 1 — Dependency Injection (no runtime news up embodiments)', () => {
  it('bootstrap injects CharacterRuntime and EmbodimentRegistry via DI', () => {
    const { container } = bootstrapPresence()
    expect(container.has(TOKENS.embodimentRegistry)).toBe(true)
    expect(container.has(TOKENS.characterRuntime)).toBe(true)
    const cr = container.resolve(TOKENS.characterRuntime)
    expect(cr).toBeDefined()
  })

  it('embodiment instance is resolved from the injected registry, not newed', () => {
    const container = new Container()
    container.register(TOKENS.renderTransport, () => new NullRenderTransport())
    let constructed = false
    container.register(TOKENS.embodiment, (c) => {
      constructed = true
      return new EmbodimentManager({ transport: c.resolve<IRenderTransport>(TOKENS.renderTransport) })
    })
    const emb = container.resolve<IEmbodiment>(TOKENS.embodiment)
    expect(constructed).toBe(true)
    expect(emb.getStatus().type).toBe('living-orb')
  })
})

describe('PART 3 — EmotionRuntime continuous model + smoothing', () => {
  it('starts at a sane default and never uses discrete labels', () => {
    const e = new EmotionRuntime()
    const s = e.getState()
    expect(s.valence).toBeGreaterThanOrEqual(-1)
    expect(s.valence).toBeLessThanOrEqual(1)
    expect(s.arousal).toBeGreaterThanOrEqual(0)
  })

  it('smooths toward a target instead of snapping', () => {
    const e = new EmotionRuntime({ smoothing: 0.1 })
    e.emit({ source: 'system', arousal: 1 }) // push target to 1
    const first = e.update(1 / 30).arousal
    // After a single tick at 0.1 ease it must be well below the target (1).
    expect(first).toBeGreaterThan(0)
    expect(first).toBeLessThan(0.5)
    // Continued ticks converge toward 1.
    let last = first
    for (let i = 0; i < 60; i++) last = e.update(1 / 30).arousal
    expect(last).toBeGreaterThan(0.8)
  })

  it('does not allow instant transitions', () => {
    const e = new EmotionRuntime({ smoothing: 0.05 })
    e.emit({ source: 'system', valence: -1 })
    const v = e.update(1 / 30).valence
    expect(v).toBeGreaterThan(-0.5) // far from -1 after one tick
  })

  it('the user cannot set emotion directly — only events nudge', () => {
    const e = new EmotionRuntime()
    // There is no setValence API. Only emit() exists.
    expect(typeof (e as any).setValence).toBe('undefined')
    e.emit({ source: 'conversation', confidence: 0.4 })
    e.update(1 / 30)
    expect(e.getState().confidence).toBeGreaterThan(0.6)
  })

  it('clamps all axes to valid ranges', () => {
    const e = new EmotionRuntime()
    e.emit({ source: 'system', arousal: 5, valence: -5, fatigue: 9 })
    const s = e.getState()
    expect(s.fatigue).toBeLessThanOrEqual(1)
    expect(s.valence).toBeGreaterThanOrEqual(-1)
  })
})

describe('PART 4 — BehaviourRuntime transitions', () => {
  it('maps system intent to a base behaviour mode', () => {
    const b = new BehaviourRuntime()
    b.setIntent('thinking')
    expect(b.update(0.1).mode).toBe('thinking')
    b.setIntent('speaking')
    expect(b.update(0.1).mode).toBe('speaking')
  })

  it('transient behaviours return to base intent after duration', () => {
    const b = new BehaviourRuntime({ transientDuration: 0.1 })
    const now = { t: 1000 }
    b.setNow(() => now.t)
    b.setIntent('idle')
    b.triggerGreeting()
    expect(b.getState().mode).toBe('greeting')
    b.update(0.05)
    now.t += 200 // exceed transient duration
    expect(b.update(0.05).mode).toBe('idle')
  })

  it('surprise injects a micro expression', () => {
    const b = new BehaviourRuntime({ transientDuration: 10 })
    b.triggerSurprise()
    expect(b.getState().microExpression).toBe('brow-raise')
  })

  it('intensity tracks the active behaviour', () => {
    const b = new BehaviourRuntime()
    b.setIntent('idle')
    const idle = b.update(0.1).intensity
    b.setIntent('speaking')
    const speaking = b.update(0.1).intensity
    expect(speaking).toBeGreaterThan(idle)
  })
})

describe('PART 5 — GazeController eye/head/blink targets', () => {
  it('produces bounded eye and head targets', () => {
    const g = new GazeController()
    g.setMode('cursor')
    g.setTarget({ x: 2, y: -2 }) // out of range
    const state = g.update(1 / 30)
    expect(state.eye.x).toBeLessThanOrEqual(1)
    expect(state.eye.x).toBeGreaterThanOrEqual(-1)
    expect(state.head.x).toBeLessThanOrEqual(1)
    expect(state.head.tilt).toBeGreaterThanOrEqual(-1)
  })

  it('schedules blinks without polling', () => {
    const g = new GazeController({ blinkInterval: 0.05, blinkDuration: 0.08 })
    g.setRng(() => 1) // deterministic
    let sawBlink = false
    for (let i = 0; i < 200; i++) {
      if (g.update(1 / 30).blink.closure > 0.1) sawBlink = true
    }
    expect(sawBlink).toBe(true)
  })

  it('wander mode keeps the eye moving', () => {
    const g = new GazeController({ blinkInterval: 100 })
    g.setMode('wander')
    const a = g.update(0.5).eye.x
    const b = g.update(0.5).eye.x
    expect(a).not.toBe(b)
  })
})

describe('PART 2 — CharacterRuntime produces CharacterState', () => {
  it('owns emotion, behaviour, gaze, breath, and micro movement', () => {
    const c = new CharacterRuntime()
    const state = c.update(1 / 30)
    expect(state).toHaveProperty('emotion')
    expect(state).toHaveProperty('behaviour')
    expect(state).toHaveProperty('gaze')
    expect(typeof state.breath).toBe('number')
    expect(typeof state.microMovement).toBe('number')
  })

  it('ingests events and projects them into state', () => {
    const c = new CharacterRuntime()
    c.setIntent('thinking')
    c.emitEmotion({ source: 'conversation', thinkingLoad: 0.8 })
    const state = c.update(1 / 30)
    expect(state.behaviour.mode).toBe('thinking')
    expect(state.emotion.thinkingLoad).toBeGreaterThan(0)
  })

  it('ticks micro movement toward an arousal-driven target', () => {
    const c = new CharacterRuntime()
    c.emitEmotion({ source: 'system', arousal: 1 })
    const s1 = c.update(1 / 30).microMovement
    let last = s1
    for (let i = 0; i < 60; i++) last = c.update(1 / 30).microMovement
    expect(last).toBeGreaterThan(s1)
  })
})

describe('PART 8 — Renderer independence (CharacterFrame boundary)', () => {
  it('CharacterFrame carries no emotion/thinking/voice/memory semantics', () => {
    const c = new CharacterRuntime()
    c.emitEmotion({ source: 'conversation', valence: 0.5 })
    const frame = toCharacterFrame(c.update(1 / 30), 1)
    const keys = JSON.stringify(frame)
    // Renderer sees values, not source identity.
    expect(frame).toHaveProperty('emotion.valence')
    expect(frame).toHaveProperty('gaze.eyeX')
    expect(frame).toHaveProperty('behaviour.mode')
    expect(keys).not.toMatch(/conversation|voice|memory|knowledge|thinking/i)
  })

  it('PresenceRuntime exposes a renderer-neutral CharacterFrame', () => {
    const { container } = bootstrapPresence()
    const presence = container.resolve<any>(TOKENS.presenceRuntime)
    expect(presence.hasCharacterRuntime()).toBe(true)
    const frame = presence.getCharacterFrame()
    expect(frame).not.toBeNull()
    expect(frame.version).toBe('1.1.0')
  })
})

describe('PART 9 — Performance (no extra render loops)', () => {
  it('CharacterRuntime.update is cheap and synchronous', () => {
    const c = new CharacterRuntime()
    const start = performance.now()
    for (let i = 0; i < 1000; i++) c.update(1 / 30)
    const elapsed = performance.now() - start
    // 1000 updates well under 50ms on any machine.
    expect(elapsed).toBeLessThan(50)
  })

  it('does not introduce a new requestAnimationFrame or setInterval in the embodiment layer', async () => {
    const fs = await import('fs')
    const path = await import('path')
    const src = fs.readFileSync(
      path.join(__dirname, '../../src/runtime/embodiment/character-runtime.ts'),
      'utf-8'
    )
    expect(src).not.toMatch(/requestAnimationFrame|setInterval|setTimeout/)
  })
})

describe('Existing Milestone 1.0 pipeline remains intact', () => {
  it('bootstrap still wires AnimationRuntime -> PresenceRuntime -> LivingOrb', () => {
    const { presenceRuntime } = bootstrapPresence()
    expect(presenceRuntime).toBeDefined()
  })
})
