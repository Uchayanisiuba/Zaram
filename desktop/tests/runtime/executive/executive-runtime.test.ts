// desktop/tests/runtime/executive/executive-runtime.test.ts
//
// Unit + integration tests — Milestone 1.4 Executive Runtime (Decision Engine).
//
// Verifies: goal switching, interrupt handling, focus transitions, priority
// calculation, intent generation, context switching, DI registration, the
// 30Hz tick advancement (no new timers), and renderer/embodiment independence
// (asserted structurally — no renderer/embodiment/CharacterFrame imports).

import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import {
  ExecutiveRuntime,
  defaultExecutiveState,
  cloneExecutiveState
} from '../../../src/runtime/executive'
import { Container, TOKENS } from '../../../src/runtime/di/container'
import { bootstrapPresence } from '../../../src/runtime/bootstrap'

describe('Executive Runtime — initial state', () => {
  it('starts from the default executive state and waits', () => {
    const e = new ExecutiveRuntime()
    const s = e.getState()
    expect(s.currentGoal).toBeNull()
    expect(s.currentIntent).toBe('wait')
    expect(s.focus).toBe('none')
    expect(s.interruptState).toBe('clear')
    expect(s.revision).toBe(0)
  })

  it('defaultExecutiveState / clone are independent copies', () => {
    const a = defaultExecutiveState()
    const b = cloneExecutiveState(a)
    b.focus = 'world'
    expect(a.focus).toBe('none')
  })
})

describe('Executive Runtime — goal switching', () => {
  it('adds goals and promotes the highest-weight as current', () => {
    const e = new ExecutiveRuntime()
    e.addGoal({ label: 'low', weight: 0.2 })
    const high = e.addGoal({ label: 'high', weight: 0.9 })
    expect(e.getState().currentGoal?.id).toBe(high.id)
  })

  it('switches context to a lower-weight goal on demand', () => {
    const e = new ExecutiveRuntime()
    const a = e.addGoal({ label: 'A', weight: 0.9 })
    const b = e.addGoal({ label: 'B', weight: 0.3 })
    e.switchGoal(b.id)
    expect(e.getState().currentGoal?.id).toBe(b.id)
    // switching back works
    e.switchGoal(a.id)
    expect(e.getState().currentGoal?.id).toBe(a.id)
  })
})

describe('Executive Runtime — interrupt handling', () => {
  it('raises an interrupt and moves into pending state', () => {
    const e = new ExecutiveRuntime()
    e.raiseInterrupt({ reason: 'call', severity: 'high' })
    expect(e.getState().interruptState).toBe('pending')
    expect(e.getState().pendingInterrupts.length).toBe(1)
  })

  it('preempts the current flow on a critical interrupt', () => {
    const e = new ExecutiveRuntime()
    e.ingestConversation({ phase: 'speaking' })
    e.raiseInterrupt({ reason: 'fire', severity: 'critical' })
    const s = e.getState()
    expect(s.interruptState).toBe('pending')
    expect(s.currentIntent).toBe('interrupt-self')
    expect(e.getIntent().shouldInterrupt).toBe(true)
  })

  it('handles the top interrupt and returns to clear', () => {
    const e = new ExecutiveRuntime()
    e.raiseInterrupt({ reason: 'x', severity: 'low' })
    e.handleTopInterrupt()
    expect(e.getState().interruptState).toBe('clear')
    expect(e.getState().pendingInterrupts.length).toBe(0)
  })
})

describe('Executive Runtime — focus transitions', () => {
  it('focuses the speaker while listening', () => {
    const e = new ExecutiveRuntime()
    e.ingestConversation({ phase: 'listening' })
    expect(e.getState().focus).toBe('speaker')
  })

  it('focuses the world during an interrupt', () => {
    const e = new ExecutiveRuntime()
    e.ingestConversation({ phase: 'speaking' })
    e.raiseInterrupt({ reason: 'ping', severity: 'high' })
    expect(e.getState().focus).toBe('world')
  })

  it('eases focus strength toward target on the 30Hz tick (no timers)', () => {
    const e = new ExecutiveRuntime({ now: () => 0 })
    e.ingestConversation({ phase: 'thinking' })
    const before = e.getState().focusStrength
    for (let i = 0; i < 15; i++) e.update(1 / 30)
    const after = e.getState().focusStrength
    expect(after).toBeGreaterThan(before)
  })
})

describe('Executive Runtime — priority calculation', () => {
  it('resolves a critical priority under interrupt', () => {
    const e = new ExecutiveRuntime()
    e.raiseInterrupt({ reason: 'alarm', severity: 'critical' })
    expect(e.getState().priority).toBe('critical')
    expect(e.getState().urgency).toBeGreaterThanOrEqual(0.8)
  })

  it('resolves background priority when idle with no signals', () => {
    const e = new ExecutiveRuntime()
    expect(e.getState().priority).toBe('background')
  })
})

describe('Executive Runtime — intent generation', () => {
  it('produces an intent that is the only embodiment-facing signal', () => {
    const e = new ExecutiveRuntime()
    e.ingestConversation({ phase: 'listening' })
    const intent = e.getIntent()
    expect(intent.decision).toBe('listen')
    // The intent carries NO goal/planning/relationship internals.
    expect((intent as unknown as Record<string, unknown>).currentGoal).toBeUndefined()
    expect((intent as unknown as Record<string, unknown>).goalStack).toBeUndefined()
  })

  it('asks clarification when upstream requests it', () => {
    const e = new ExecutiveRuntime()
    e.ingestCognitive({ needsClarification: true })
    expect(e.getState().currentIntent).toBe('ask-clarification')
  })
})

describe('Executive Runtime — context switching', () => {
  it('re-resolves the decision when conversation phase changes', () => {
    const e = new ExecutiveRuntime()
    e.ingestConversation({ phase: 'listening' })
    expect(e.getState().currentIntent).toBe('listen')
    e.ingestConversation({ phase: 'speaking' })
    expect(e.getState().currentIntent).toBe('reply')
    e.ingestConversation({ phase: 'idle' })
    e.addGoal({ label: 'do task', weight: 0.7 })
    expect(e.getState().currentIntent).toBe('wait')
  })
})

describe('Executive Runtime — DI', () => {
  it('registers as a singleton in the DI container', () => {
    const { container } = bootstrapPresence()
    expect(container.has(TOKENS.executiveRuntime)).toBe(true)
    const a = container.resolve(TOKENS.executiveRuntime)
    const b = container.resolve(TOKENS.executiveRuntime)
    expect(a).toBe(b)
    expect(a).toBeInstanceOf(ExecutiveRuntime)
  })

  it('can be resolved standalone and advanced', () => {
    const c = new Container()
    let built = false
    c.register(TOKENS.executiveRuntime, () => {
      built = true
      return new ExecutiveRuntime()
    })
    const e = c.resolve<ExecutiveRuntime>(TOKENS.executiveRuntime)
    e.update(1 / 30)
    expect(built).toBe(true)
  })

  it('is wired into PresenceRuntime via DI (30Hz tick advances it)', () => {
    const { presenceRuntime } = bootstrapPresence()
    const pr = presenceRuntime as unknown as {
      hasExecutiveRuntime(): boolean
      update(dt: number): void
      getExecutiveSnapshot(): ReturnType<ExecutiveRuntime['getSnapshot']> | null
    }
    expect(pr.hasExecutiveRuntime()).toBe(true)
    expect(pr.getExecutiveSnapshot()).not.toBeNull()
  })
})

describe('Executive Runtime — no timers / polling', () => {
  it('does not introduce setInterval / setTimeout / RAF / loops', () => {
    const dir = join(__dirname, '..', '..', '..', 'src', 'runtime', 'executive')
    const files = [
      'index.ts',
      'types.ts',
      'executive-state.ts',
      'executive-runtime.ts',
      'goal-manager.ts',
      'focus-manager.ts',
      'interrupt-manager.ts',
      'priority-manager.ts',
      'intent-generator.ts'
    ]
    for (const f of files) {
      const src = readFileSync(join(dir, f), 'utf8')
      expect(src, `${f} must not use setInterval`).not.toMatch(/setInterval\s*\(/)
      expect(src, `${f} must not use setTimeout`).not.toMatch(/setTimeout\s*\(/)
      expect(src, `${f} must not use requestAnimationFrame`).not.toMatch(/requestAnimationFrame\s*\(/)
      expect(src, `${f} must not use while loops`).not.toMatch(/while\s*\(/)
      expect(src, `${f} must not use unbounded for`).not.toMatch(/for\s*\(;;/)
    }
  })

  it('does not import renderer, embodiment, or character pipeline', () => {
    const dir = join(__dirname, '..', '..', '..', 'src', 'runtime', 'executive')
    const files = [
      'index.ts',
      'types.ts',
      'executive-state.ts',
      'executive-runtime.ts',
      'goal-manager.ts',
      'focus-manager.ts',
      'interrupt-manager.ts',
      'priority-manager.ts',
      'intent-generator.ts'
    ]
    for (const f of files) {
      const src = readFileSync(join(dir, f), 'utf8')
      expect(src, `${f} must not reference renderer`).not.toMatch(/renderer/i)
      expect(src, `${f} must not reference embodiment`).not.toMatch(/embodiment/i)
      expect(src, `${f} must not reference CharacterFrame`).not.toMatch(/CharacterFrame/i)
      expect(src, `${f} must not reference animation-runtime`).not.toMatch(/animation-runtime/i)
      expect(src, `${f} must not reference frame-state`).not.toMatch(/frame-state|FrameState/i)
      expect(src, `${f} must not import engine`).not.toMatch(/@zaram\/engine/)
      expect(src, `${f} must not reference orb-renderer`).not.toMatch(/orb-renderer|OrbRenderer/i)
      expect(src, `${f} must not reference electron`).not.toMatch(/electron/i)
      expect(src, `${f} must not reference threejs`).not.toMatch(/three/i)
      expect(src, `${f} must not reference webgpu`).not.toMatch(/webgpu/i)
      expect(src, `${f} must not reference unreal`).not.toMatch(/unreal/i)
      expect(src, `${f} must not reference arkit`).not.toMatch(/arkit/i)
      expect(src, `${f} must not reference gnm`).not.toMatch(/gnm/i)
      expect(src, `${f} must not reference metahuman`).not.toMatch(/metahuman/i)
      expect(src, `${f} must not reference living-orb`).not.toMatch(/living-orb|LivingOrb/i)
      expect(src, `${f} must not reference robot`).not.toMatch(/robot/i)
    }
  })
})
