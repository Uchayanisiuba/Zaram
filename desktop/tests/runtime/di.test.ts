import { describe, it, expect, vi } from 'vitest'
import { Container, TOKENS } from '../../src/runtime/di/container'
import { EmbodimentManager } from '../../src/runtime/embodiment/EmbodimentManager'
import { PresenceRuntime } from '../../src/runtime/presence/presence-runtime'
import { NullRenderTransport } from '../../src/runtime/electron/render-transport'
import { bootstrapPresence } from '../../src/runtime/bootstrap'
import { IPresenceRuntime } from '../../src/runtime/interfaces'

describe('Dependency Injection container', () => {
  it('registers and resolves a singleton', () => {
    const container = new Container()
    container.register('svc', () => ({ id: Math.random() }), { singleton: true })
    const a = container.resolve('svc')
    const b = container.resolve('svc')
    expect(a).toBe(b)
  })

  it('returns a fresh instance for non-singletons', () => {
    const container = new Container()
    container.register('svc', () => ({ id: Math.random() }), { singleton: false })
    expect(container.resolve('svc')).not.toBe(container.resolve('svc'))
  })

  it('throws for unregistered tokens', () => {
    const container = new Container()
    expect(() => container.resolve('missing')).toThrow()
  })

  it('supports factory dependency graphs', () => {
    const container = new Container()
    container.register('a', () => 1)
    container.register('b', (c) => c.resolve<number>('a') + 1)
    expect(container.resolve<number>('b')).toBe(2)
  })
})

describe('Presence Runtime DI registration', () => {
  it('registers the Presence Runtime via DI (no singleton globals)', () => {
    const { container, presenceRuntime } = bootstrapPresence()
    expect(container.has(TOKENS.presenceRuntime)).toBe(true)
    expect(container.has(TOKENS.embodiment)).toBe(true)
    expect(presenceRuntime).toBeDefined()
  })

  it('resolves the same Presence Runtime singleton', () => {
    const { container } = bootstrapPresence()
    const a = container.resolve<IPresenceRuntime>(TOKENS.presenceRuntime)
    const b = container.resolve<IPresenceRuntime>(TOKENS.presenceRuntime)
    expect(a).toBe(b)
  })

  it('defaults to the LivingOrbAdapter embodiment', () => {
    const { container } = bootstrapPresence()
    const embodiment = container.resolve(TOKENS.embodiment)
    expect(embodiment).toBeInstanceOf(EmbodimentManager)
    expect((embodiment as any).getCurrentType()).toBe('living-orb')
  })

  it('allows swapping the embodiment without touching the kernel', async () => {
    const container = new Container()
    const transport = new NullRenderTransport()
    const mockEmbodiment = {
      initialize: vi.fn().mockResolvedValue(undefined),
      start: vi.fn().mockResolvedValue(undefined),
      pause: vi.fn().mockResolvedValue(undefined),
      resume: vi.fn().mockResolvedValue(undefined),
      shutdown: vi.fn().mockResolvedValue(undefined),
      setFrameState: vi.fn(),
      getStatus: () => ({ type: 'unreal-character' as const, state: 'running' as const, healthy: true, lastUpdated: Date.now() })
    }
    container.register(TOKENS.renderTransport, () => transport)
    container.register(TOKENS.embodiment, () => mockEmbodiment)
    container.register(TOKENS.presenceRuntime, (c) => {
      return new PresenceRuntime({ embodiment: c.resolve(TOKENS.embodiment) })
    })
    const presence = container.resolve<IPresenceRuntime>(TOKENS.presenceRuntime)
    await presence.initialize()
    await presence.start()
    expect(presence.getStatus().type).toBe('unreal-character')
  })
})
