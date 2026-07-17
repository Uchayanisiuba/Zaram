// desktop/tests/runtime/world/world-runtime.test.ts
//
// Unit tests — Milestone 1.3 World Runtime.
//
// Verifies: immutable snapshots, event publishing, dependency injection, the
// 30Hz tick advancing salience decay, and renderer/embodiment independence
// (no renderer/embodiment/CharacterFrame imports — asserted structurally).

import { describe, it, expect, vi } from 'vitest'
import {
  WorldRuntime,
  defaultWorldState,
  defaultEnvironment,
  defaultDesktop,
  defaultApplication,
  defaultSystem,
  defaultNotification,
  deepFreeze
} from '../../../src/runtime/world'
import { Container, TOKENS } from '../../../src/runtime/di/container'
import { bootstrapPresence } from '../../../src/runtime/bootstrap'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

describe('World Runtime — immutable WorldState', () => {
  it('returns a frozen deep copy of the world state', () => {
    const w = new WorldRuntime()
    const s = w.getWorldState() as WorldState
    expect(Object.isFrozen(s)).toBe(true)
    expect(Object.isFrozen(s.environment)).toBe(true)
    expect(Object.isFrozen(s.notification)).toBe(true)
    expect(Object.isFrozen(s.notification.active)).toBe(true)
  })

  it('increments revision on each perception update', () => {
    const w = new WorldRuntime()
    const r0 = w.getWorldState().revision
    w.setEnvironment({ isForeground: false })
    const r1 = w.getWorldState().revision
    expect(r1).toBeGreaterThan(r0)
  })

  it('producers never share mutable references with the returned snapshot', () => {
    const w = new WorldRuntime()
    const env = w.getEnvironment()
    expect(() => {
      // @ts-expect-error frozen object cannot be mutated
      env.isForeground = false
    }).toThrow()
    expect(w.getEnvironment().isForeground).toBe(true)
  })

  it('exposes the full default world out of the box', () => {
    const now = Date.now()
    const ws = defaultWorldState()
    expect(ws.environment).toEqual(defaultEnvironment(now))
    expect(ws.desktop).toEqual(defaultDesktop(now))
    expect(ws.application).toEqual(defaultApplication(now))
    expect(ws.system).toEqual(defaultSystem(now))
    expect(ws.notification).toEqual(defaultNotification(now))
  })
})

describe('World Runtime — sub-snapshots', () => {
  it('environment reflects occluded visibility and occlusion clamp', () => {
    const w = new WorldRuntime()
    w.setEnvironment({ visibility: 'occluded', occlusion: 2 })
    const env = w.getEnvironment()
    expect(env.visibility).toBe('occluded')
    expect(env.occlusion).toBe(1) // clamped to [0,1]
  })

  it('desktop reflects idle decay clamping', () => {
    const w = new WorldRuntime()
    w.setDesktop({ idleLevel: 5, power: 'idle' })
    const d = w.getDesktop()
    expect(d.idleLevel).toBe(1)
    expect(d.power).toBe('idle')
  })

  it('system reflects load clamping', () => {
    const w = new WorldRuntime()
    w.setSystem({ load: -1, state: 'working' })
    const s = w.getSystem()
    expect(s.load).toBe(0)
    expect(s.state).toBe('working')
  })

  it('application captures foreground app perception', () => {
    const w = new WorldRuntime()
    w.setApplication({ foregroundApp: { name: 'Editor', bundleId: 'com.x', focus: 0.8 } })
    expect(w.getApplication().foregroundApp?.focus).toBe(0.8)
  })
})

describe('World Runtime — notification perception & decay', () => {
  it('delivers notifications and tracks total/peak salience', () => {
    const w = new WorldRuntime()
    w.deliverNotification({ id: 'n1', title: 'Hi', severity: 0.9 })
    w.deliverNotification({ id: 'n2', title: 'Lo', severity: 0.2 })
    const n = w.getNotification()
    expect(n.active.length).toBe(2)
    expect(n.totalDelivered).toBe(2)
    expect(n.peakSalience).toBeCloseTo(0.9, 5)
  })

  it('caps retained notifications at maxNotifications', () => {
    const w = new WorldRuntime({ maxNotifications: 2 })
    for (let i = 0; i < 5; i++) w.deliverNotification({ id: `n${i}`, title: `t${i}`, severity: 0.5 })
    expect(w.getNotification().active.length).toBe(2)
  })

  it('clears a notification by id', () => {
    const w = new WorldRuntime()
    w.deliverNotification({ id: 'n1', title: 'Hi' })
    w.clearNotification('n1')
    expect(w.getNotification().active.length).toBe(0)
  })

  it('decays notification salience on the existing tick (no new timers)', () => {
    const w = new WorldRuntime({ notificationDecayPerSec: 1 })
    w.deliverNotification({ id: 'n1', title: 'Hi', severity: 1 })
    // ~0.5s of simulated 30Hz frames => salience ~0.5
    for (let i = 0; i < 15; i++) w.update(1 / 30)
    const sal = w.getNotification().active[0]?.salience ?? 0
    expect(sal).toBeGreaterThan(0.4)
    expect(sal).toBeLessThan(0.6)
  })

  it('prunes fully decayed notifications', () => {
    const w = new WorldRuntime({ notificationDecayPerSec: 1 })
    w.deliverNotification({ id: 'n1', title: 'Hi', severity: 0.2 })
    for (let i = 0; i < 10; i++) w.update(1 / 30)
    expect(w.getNotification().active.length).toBe(0)
  })
})

describe('World Runtime — event publishing', () => {
  it('publishes a world event per perceived change', () => {
    const w = new WorldRuntime()
    const spy = vi.fn()
    w.subscribe(spy)
    w.setEnvironment({ isForeground: false })
    // A foreground flip publishes both environment_changed and
    // foreground_changed.
    expect(spy).toHaveBeenCalledTimes(2)
    const last = spy.mock.calls[spy.mock.calls.length - 1][0]
    expect(last.type).toBe('world.environment_changed')
    expect(last.data.environment?.isForeground).toBe(false)
    expect(Object.isFrozen(last.data)).toBe(true)
  })

  it('publishes foreground_changed when foreground flips', () => {
    const w = new WorldRuntime()
    const types: string[] = []
    w.subscribe((e) => types.push(e.type))
    w.setEnvironment({ isForeground: false })
    expect(types).toContain('world.foreground_changed')
  })

  it('publishes notification_arrived with correlationId', () => {
    const w = new WorldRuntime()
    const spy = vi.fn()
    w.subscribe(spy)
    w.deliverNotification({ id: 'n1', title: 'Hi', correlationId: 'c-1' })
    const ev = spy.mock.calls[0][0]
    expect(ev.type).toBe('world.notification_arrived')
    expect(ev.correlationId).toBe('c-1')
  })

  it('unsubscribe stops delivery', () => {
    const w = new WorldRuntime()
    const spy = vi.fn()
    const off = w.subscribe(spy)
    off()
    w.setDesktop({ power: 'idle' })
    expect(spy).not.toHaveBeenCalled()
  })
})

describe('World Runtime — dependency injection', () => {
  it('registers as a singleton in the DI container', () => {
    const { container } = bootstrapPresence()
    expect(container.has(TOKENS.worldRuntime)).toBe(true)
    const a = container.resolve(TOKENS.worldRuntime)
    const b = container.resolve(TOKENS.worldRuntime)
    expect(a).toBe(b)
    expect(a).toBeInstanceOf(WorldRuntime)
  })

  it('is wired into PresenceRuntime via DI (30Hz tick advances it)', () => {
    const { presenceRuntime } = bootstrapPresence()
    expect((presenceRuntime as unknown as { hasWorldRuntime(): boolean }).hasWorldRuntime()).toBe(true)
  })

  it('can be resolved standalone and advanced via the interface', () => {
    const c = new Container()
    let built = false
    c.register(TOKENS.worldRuntime, () => {
      built = true
      return new WorldRuntime()
    })
    const w = c.resolve<WorldRuntime>(TOKENS.worldRuntime)
    w.update(1 / 30)
    expect(built).toBe(true)
  })
})

describe('World Runtime — drawing-layer & character-pipeline independence', () => {
  it('does not import drawing layer, character pipeline, or engine modules', () => {
    const dir = join(__dirname, '..', '..', '..', 'src', 'runtime', 'world')
    const files = ['index.ts', 'types.ts', 'world-runtime.ts', 'world-attention-adapter.ts']
    for (const f of files) {
      const src = readFileSync(join(dir, f), 'utf8')
      expect(src, `${f} must not reference drawing layer`).not.toMatch(/renderer/i)
      expect(src, `${f} must not reference character pipeline`).not.toMatch(/embodiment/i)
      expect(src, `${f} must not reference CharacterFrame`).not.toMatch(/CharacterFrame/i)
      expect(src, `${f} must not import engine`).not.toMatch(/@zaram\/engine/)
    }
  })

  it('deepFreeze leaves primitives untouched', () => {
    expect(deepFreeze(5)).toBe(5)
    expect(deepFreeze('x')).toBe('x')
    expect(deepFreeze(null)).toBe(null)
  })
})

// Local re-typing to keep the import list tidy without pulling renderer types.
type WorldState = ReturnType<WorldRuntime['getWorldState']>
