import { describe, it, expect, vi } from 'vitest'
import { EmbodimentManager } from '../../src/runtime/embodiment/EmbodimentManager'
import { IEmbodiment } from '../../src/runtime/interfaces'
import { NullRenderTransport } from '../../src/runtime/electron/render-transport'

describe('EmbodimentManager', () => {
  const transport = new NullRenderTransport()

  it('defaults to living-orb', () => {
    const manager = new EmbodimentManager({ transport })
    expect(manager.getCurrentType()).toBe('living-orb')
    expect(manager.getAvailable()).toContain('living-orb')
  })

  it('registers additional embodiments', () => {
    const manager = new EmbodimentManager({ transport })
    const mock: IEmbodiment = {
      initialize: vi.fn().mockResolvedValue(undefined),
      start: vi.fn().mockResolvedValue(undefined),
      pause: vi.fn().mockResolvedValue(undefined),
      resume: vi.fn().mockResolvedValue(undefined),
      shutdown: vi.fn().mockResolvedValue(undefined),
      setFrameState: vi.fn(),
      getStatus: () => ({
        type: 'xr-avatar',
        state: 'running',
        healthy: true,
        lastUpdated: Date.now()
      })
    }
    manager.register('xr-avatar', mock)
    expect(manager.getAvailable()).toContain('xr-avatar')
  })

  it('switches embodiment without modifying the runtime', async () => {
    const manager = new EmbodimentManager({ transport })
    const mock: IEmbodiment = {
      initialize: vi.fn().mockResolvedValue(undefined),
      start: vi.fn().mockResolvedValue(undefined),
      pause: vi.fn().mockResolvedValue(undefined),
      resume: vi.fn().mockResolvedValue(undefined),
      shutdown: vi.fn().mockResolvedValue(undefined),
      setFrameState: vi.fn(),
      getStatus: () => ({
        type: 'xr-avatar',
        state: 'running',
        healthy: true,
        lastUpdated: Date.now()
      })
    }
    manager.register('xr-avatar', mock)
    await manager.switchTo('xr-avatar')
    expect(manager.getCurrentType()).toBe('xr-avatar')
    expect(mock.initialize).toHaveBeenCalled()
    expect(mock.start).toHaveBeenCalled()
  })

  it('shuts down the previous embodiment before switching', async () => {
    const manager = new EmbodimentManager({ transport })
    const shutdown = vi.fn().mockResolvedValue(undefined)
    const livingOrb = manager.getStatus()
    ;(manager as unknown as { current: IEmbodiment }).current = {
      initialize: vi.fn().mockResolvedValue(undefined),
      start: vi.fn().mockResolvedValue(undefined),
      pause: vi.fn().mockResolvedValue(undefined),
      resume: vi.fn().mockResolvedValue(undefined),
      shutdown,
      setFrameState: vi.fn(),
      getStatus: () => livingOrb
    }
    const mock: IEmbodiment = {
      initialize: vi.fn().mockResolvedValue(undefined),
      start: vi.fn().mockResolvedValue(undefined),
      pause: vi.fn().mockResolvedValue(undefined),
      resume: vi.fn().mockResolvedValue(undefined),
      shutdown: vi.fn().mockResolvedValue(undefined),
      setFrameState: vi.fn(),
      getStatus: () => ({
        type: 'metahuman',
        state: 'running',
        healthy: true,
        lastUpdated: Date.now()
      })
    }
    manager.register('metahuman', mock as any)
    await manager.switchTo('metahuman' as any)
    await manager.switchTo('metahuman')
    expect(shutdown).toHaveBeenCalled()
  })

  it('delegates lifecycle calls to the active embodiment', async () => {
    const manager = new EmbodimentManager({ transport })
    const mock: IEmbodiment = {
      initialize: vi.fn().mockResolvedValue(undefined),
      start: vi.fn().mockResolvedValue(undefined),
      pause: vi.fn().mockResolvedValue(undefined),
      resume: vi.fn().mockResolvedValue(undefined),
      shutdown: vi.fn().mockResolvedValue(undefined),
      setFrameState: vi.fn(),
      getStatus: () => ({
        type: 'living-orb',
        state: 'running',
        healthy: true,
        lastUpdated: Date.now()
      })
    }
    manager.register('living-orb', mock)
    ;(manager as unknown as { current: IEmbodiment }).current = mock
    await manager.initialize()
    await manager.start()
    await manager.pause()
    await manager.resume()
    await manager.shutdown()
    expect(mock.initialize).toHaveBeenCalled()
    expect(mock.start).toHaveBeenCalled()
    expect(mock.pause).toHaveBeenCalled()
    expect(mock.resume).toHaveBeenCalled()
    expect(mock.shutdown).toHaveBeenCalled()
  })
})
