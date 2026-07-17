import { describe, it, expect } from 'vitest'
import { bootstrapPresence } from '../../src/runtime/bootstrap'
import { ZaramKernel } from '../../src/runtime/kernel/zaram-kernel'
import { Container, TOKENS } from '../../src/runtime/di/container'
import { LivingOrbAdapter } from '../../src/runtime/presence/living-orb-adapter'
import { PresenceRuntime } from '../../src/runtime/presence/presence-runtime'
import { NullRenderTransport } from '../../src/runtime/electron/render-transport'
import { IPresenceRuntime } from '../../src/runtime/interfaces'

describe('ZaramKernel (orchestrator)', () => {
  it('boots and disposes the Presence Runtime through DI', async () => {
    const { buildKernel } = bootstrapPresence()
    const kernel = buildKernel()
    await kernel.boot()
    expect(kernel.getPresenceRuntime().getStatus().state).toBe('running')
    await kernel.dispose()
    expect(kernel.getPresenceRuntime().getStatus().state).toBe('shutdown')
  })

  it('depends only on the IPresenceRuntime interface', async () => {
    const container = new Container()
    const transport = new NullRenderTransport()
    const embodiment = new LivingOrbAdapter(transport)
    container.register(TOKENS.embodiment, () => embodiment)
    container.register(TOKENS.presenceRuntime, (c) => {
      return new PresenceRuntime({ embodiment: c.resolve(TOKENS.embodiment) })
    })
    const presence = container.resolve<IPresenceRuntime>(TOKENS.presenceRuntime)
    const kernel = new ZaramKernel(presence)
    await kernel.boot()
    expect(kernel.getPresenceRuntime()).toBe(presence)
    await kernel.dispose()
  })

  it('resolves a kernel from the DI container', () => {
    const { container } = bootstrapPresence()
    const kernel = container.resolve(TOKENS.kernel)
    expect(kernel).toBeInstanceOf(ZaramKernel)
  })
})
