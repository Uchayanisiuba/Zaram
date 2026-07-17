import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('electron', () => ({
  screen: {
    getPrimaryDisplay: () => ({ scaleFactor: 2 })
  }
}))

import { EmbodimentHost } from '../../src/runtime/electron/embodiment-host'
import { NullRenderTransport } from '../../src/runtime/electron/render-transport'
import { PresenceRuntime } from '../../src/runtime/presence/presence-runtime'
import { LivingOrbAdapter } from '../../src/runtime/presence/living-orb-adapter'

function makeWindow() {
  const handlers: Record<string, Array<() => void>> = {}
  const wcHandlers: Record<string, Array<() => void>> = {}
  const window = {
    isDestroyed: vi.fn(() => false),
    getSize: vi.fn(() => [1280, 720]),
    webContents: {
      send: vi.fn(),
      on: vi.fn((event: string, cb: () => void) => {
        ;(wcHandlers[event] ||= []).push(cb)
      })
    },
    on: vi.fn((event: string, cb: () => void) => {
      ;(handlers[event] ||= []).push(cb)
    }),
    off: vi.fn((event: string, cb: () => void) => {
      handlers[event] = (handlers[event] || []).filter((h) => h !== cb)
    }),
    once: vi.fn((event: string, cb: () => void) => {
      ;(handlers[event] ||= []).push(cb)
    }),
    emit: (event: string) => {
      ;(handlers[event] || []).forEach((h) => h())
    },
    emitWebContents: (event: string) => {
      ;(wcHandlers[event] || []).forEach((h) => h())
    }
  }
  return window
}

describe('EmbodimentHost (Electron integration)', () => {
  let window: ReturnType<typeof makeWindow>
  let presence: PresenceRuntime
  let adapter: LivingOrbAdapter

  beforeEach(() => {
    window = makeWindow()
    const transport = new NullRenderTransport()
    adapter = new LivingOrbAdapter(transport)
    presence = new PresenceRuntime({ embodiment: adapter })
  })

  it('mounts lifecycle listeners on the window', () => {
    const host = new EmbodimentHost({ getWindow: () => window, presence })
    host.mount()
    expect(window.on).toHaveBeenCalledWith('resize', expect.any(Function))
    expect(window.on).toHaveBeenCalledWith('show', expect.any(Function))
    expect(window.on).toHaveBeenCalledWith('hide', expect.any(Function))
    expect(window.webContents.on).toHaveBeenCalledWith('crashed', expect.any(Function))
    host.unmount()
  })

  it('publishes viewport (resize + DPI) to the renderer', () => {
    const host = new EmbodimentHost({ getWindow: () => window, presence })
    const seen: Array<{ width: number; height: number; scaleFactor: number }> = []
    host.onViewport((info) => seen.push(info))
    host.mount()
    expect(seen.length).toBeGreaterThanOrEqual(1)
    expect(seen[0]).toEqual({ width: 1280, height: 720, scaleFactor: 2 })
    host.unmount()
  })

  it('swaps the render transport into the active embodiment', async () => {
    const host = new EmbodimentHost({ getWindow: () => window, presence })
    host.mount()
    host.attachToEmbodiment(adapter)
    await host.boot()
    expect(adapter.getStatus().state).toBe('running')
    host.unmount()
    await presence.shutdown()
  })

  it('throttles the presence runtime when the window is hidden', async () => {
    const host = new EmbodimentHost({ getWindow: () => window, presence, throttleOnHidden: true })
    host.mount()
    await host.boot()
    window.emit('hide')
    await Promise.resolve()
    expect(adapter.getStatus().state).toBe('paused')
    window.emit('show')
    await Promise.resolve()
    expect(adapter.getStatus().state).toBe('running')
    host.unmount()
    await presence.shutdown()
  })

  it('recovers the GPU context on web contents crash', async () => {
    const host = new EmbodimentHost({ getWindow: () => window, presence })
    host.mount()
    await host.boot()
    window.emitWebContents('crashed')
    await new Promise((r) => setTimeout(r, 20))
    expect(adapter.getStatus().state).toBe('running')
    host.unmount()
    await presence.shutdown()
  })
})
