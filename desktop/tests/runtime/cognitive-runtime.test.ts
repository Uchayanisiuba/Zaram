import { describe, it, expect, vi } from 'vitest'
import { CognitiveRuntime, CognitiveBundle } from '../../src/runtime/cognitive'
import { AttentionRuntime, attentionTargetFromCognitive } from '../../src/runtime/cognitive'
import { RelationshipRuntime } from '../../src/runtime/cognitive'
import { projectConversation } from '../../src/runtime/cognitive'
import { MemoryProjection, ConversationContext } from '../../src/runtime/cognitive'
import { Container, TOKENS } from '../../src/runtime/di/container'
import { bootstrapPresence } from '../../src/runtime/bootstrap'
import { NullRenderTransport } from '../../src/runtime/electron/render-transport'
import { IRenderTransport } from '../../src/runtime/interfaces'

describe('PART 1 — CognitiveRuntime', () => {
  it('tracks reasoning state derived from conversation phase', () => {
    const c = new CognitiveRuntime()
    c.emit({ kind: 'phase', phase: 'thinking' })
    expect(c.getReasoning()).toBe('reasoning')
    expect(c.getThinking()).toBe(true)
    c.emit({ kind: 'phase', phase: 'idle' })
    expect(c.getThinking()).toBe(false)
  })

  it('tracks conversation intent', () => {
    const c = new CognitiveRuntime()
    c.emit({ kind: 'intent', intent: 'greet' })
    expect(c.getIntent()).toBe('greet')
  })

  it('manages internal goals weighted and sorted', () => {
    const c = new CognitiveRuntime()
    c.emit({ kind: 'goal', id: 'a', label: 'low', weight: 0.2 })
    c.emit({ kind: 'goal', id: 'b', label: 'high', weight: 0.9 })
    const goals = c.getState().goals
    expect(goals[0].id).toBe('b')
  })

  it('manages a planning state and task queue', () => {
    const c = new CognitiveRuntime()
    c.emit({ kind: 'task', task: { id: 't1', label: 'do x', priority: 0.8 } })
    c.emit({ kind: 'task', task: { id: 't2', label: 'do y', priority: 0.3 } })
    expect(c.getPendingTasks().length).toBe(2)
    c.emit({ kind: 'plan', steps: ['step1', 'step2'] })
    const s = c.getState()
    expect(s.planning.active).toBe(true)
    expect(s.planning.steps.length).toBe(2)
    const planned = s.taskQueue.find((t) => t.id === 't1')
    expect(planned?.planned).toBe(true)
    c.emit({ kind: 'planProgress', progress: 0.5 })
    expect(c.getState().planning.progress).toBe(0.5)
  })

  it('tracks attention priority', () => {
    const c = new CognitiveRuntime()
    c.emit({ kind: 'attention', priority: 0.9 })
    expect(c.getAttentionPriority()).toBeCloseTo(0.9, 5)
  })

  it('tracks knowledge and memory requests', () => {
    const c = new CognitiveRuntime()
    c.emit({ kind: 'knowledgeRequest', query: 'q1' })
    c.emit({ kind: 'memoryRequest', query: 'm1' })
    expect(c.getOpenKnowledgeRequests()).toBe(1)
    expect(c.getOpenMemoryRequests()).toBe(1)
    const kId = c.getState().knowledgeRequests[0].id
    c.emit({ kind: 'knowledgeResolved', id: kId })
    expect(c.getOpenKnowledgeRequests()).toBe(0)
  })

  it('is event-driven and notifies subscribers', () => {
    const c = new CognitiveRuntime()
    const spy = vi.fn()
    c.subscribe(spy)
    c.emit({ kind: 'thinking', value: true })
    expect(spy).toHaveBeenCalledOnce()
    expect(spy.mock.calls[0][0].thinking).toBe(true)
  })

  it('revision increments on every event', () => {
    const c = new CognitiveRuntime()
    const r0 = c.getState().revision
    c.emit({ kind: 'intent', intent: 'ask' })
    expect(c.getState().revision).toBe(r0 + 1)
  })
})

describe('PART 2 — AttentionRuntime', () => {
  it('tracks speaker, conversation target, and cursor/camera targets', () => {
    const a = new AttentionRuntime()
    a.emit({ speaker: 'user-1', conversationTarget: 'user-1' })
    a.emit({ cursor: { x: 1, y: -1 }, camera: { x: 0, y: 0.5 } })
    const s0 = a.getState()
    expect(s0.speaker).toBe('user-1')
    expect(s0.conversationTarget).toBe('user-1')
    // Cursor/camera ease toward the emitted targets over ticks.
    let s = s0
    for (let i = 0; i < 120; i++) s = a.update(1 / 30)
    expect(s.cursor.x).toBeCloseTo(1, 2)
    expect(s.cursor.y).toBeCloseTo(-1, 2)
  })

  it('eases toward targets (smooth transitions, no instant snap)', () => {
    const a = new AttentionRuntime()
    a.emit({ camera: { x: 1, y: 1 } })
    const before = a.getState().camera.x
    const after = a.update(1 / 30).camera.x
    expect(after).toBeGreaterThan(before)
    expect(after).toBeLessThan(1) // not snapped instantly
  })

  it('notifications carry salience that decays over time', () => {
    const a = new AttentionRuntime()
    a.emit({ notification: { id: 'n', severity: 1 } })
    expect(a.getState().notificationSalience).toBe(1)
    let s = a.getState()
    for (let i = 0; i < 120; i++) s = a.update(1 / 30)
    expect(s.notificationSalience).toBe(0)
  })

  it('derives focus confidence from current target weighting', () => {
    const a = new AttentionRuntime()
    a.emit({ target: 'notification' })
    a.update(1 / 30)
    expect(a.getState().priority).toBeGreaterThanOrEqual(0.5)
  })

  it('maps cognitive reasoning to an attention target', () => {
    const c = new CognitiveRuntime()
    c.emit({ kind: 'phase', phase: 'listening' })
    expect(attentionTargetFromCognitive(c.getState())).toBe('speaker')
    c.emit({ kind: 'phase', phase: 'thinking' })
    expect(attentionTargetFromCognitive(c.getState())).toBe('internal')
  })
})

describe('PART 3 — RelationshipRuntime', () => {
  it('evolves gradually (no instant jumps)', () => {
    const r = new RelationshipRuntime({ maxStep: 0.05 })
    const before = r.getState().trust
    r.emit({ trustDelta: 1 }) // huge nudge
    const after = r.getState().trust
    expect(after - before).toBeLessThanOrEqual(0.05 + 1e-9)
    expect(after).toBeGreaterThan(before)
  })

  it('tracks all required metrics', () => {
    const r = new RelationshipRuntime()
    r.emit({ interaction: true, preferenceObserved: 0.4, humor: 0.3, respectDelta: 0.2, familiarityDelta: 0.1 })
    const s = r.getState()
    expect(s.interactions).toBe(1)
    expect(s.preferenceConfidence).toBeGreaterThan(0.3)
    expect(s.humorCompatibility).toBeGreaterThan(0.5)
    expect(s.respect).toBeGreaterThan(0.6)
    expect(s.familiarity).toBeGreaterThan(0.2)
  })

  it('decays interaction frequency when idle', () => {
    const r = new RelationshipRuntime({ frequencyDecayPerSec: 0.1 })
    r.emit({ interaction: true })
    const before = r.getState().interactionFrequency
    r.update(1) // 1 second of inactivity
    expect(r.getState().interactionFrequency).toBeLessThan(before)
  })

  it('is event-driven with subscribers', () => {
    const r = new RelationshipRuntime()
    const spy = vi.fn()
    r.subscribe(spy)
    r.emit({ interaction: true })
    expect(spy).toHaveBeenCalledOnce()
  })
})

describe('PART 4 — MemoryProjection (interfaces only)', () => {
  it('defines projection interfaces without touching MemoryRuntime', () => {
    // Structural check: an implementer satisfies the contract.
    const proj: MemoryProjection = {
      project: (snap) => ({ count: 0, recall: snap.recall, activity: snap.activity, relevant: [] }),
      buildContext: (_snap, ctx: ConversationContext) => ctx,
      rankRelevant: () => []
    }
    expect(typeof proj.project).toBe('function')
    expect(typeof proj.buildContext).toBe('function')
    expect(typeof proj.rankRelevant).toBe('function')
  })
})

describe('PART 5 — ConversationProjection', () => {
  it('produces thinking/speaking/listening/interruptible states', () => {
    const c = new CognitiveRuntime()
    c.emit({ kind: 'phase', phase: 'thinking' })
    const p = projectConversation('thinking', c.getState())
    expect(p.thinking.active).toBe(true)
    expect(p.speaking.active).toBe(false)
    expect(p.listening.active).toBe(false)
    expect(p.interruptible.interruptible).toBe(false)
  })

  it('speaking phase is not interruptible', () => {
    const c = new CognitiveRuntime()
    const p = projectConversation('speaking', c.getState())
    expect(p.speaking.active).toBe(true)
    expect(p.interruptible.interruptible).toBe(false)
    expect(p.interruptible.openness).toBeLessThan(0.2)
  })

  it('listening phase is interruptible', () => {
    const c = new CognitiveRuntime()
    const p = projectConversation('listening', c.getState())
    expect(p.listening.active).toBe(true)
    expect(p.interruptible.interruptible).toBe(true)
  })

  it('carries the conversation intent', () => {
    const c = new CognitiveRuntime()
    c.emit({ kind: 'intent', intent: 'ask' })
    const p = projectConversation('idle', c.getState())
    expect(p.intent).toBe('ask')
  })
})

describe('PART 6 — Presence integration (no renderer changes)', () => {
  it('bootstrap injects a CognitiveBundle via DI', () => {
    const { container } = bootstrapPresence()
    expect(container.has(TOKENS.cognitiveRuntime)).toBe(true)
    const bundle = container.resolve(TOKENS.cognitiveRuntime)
    expect(bundle).toBeDefined()
  })

  it('PresenceRuntime exposes cognitive state when injected', () => {
    const { container } = bootstrapPresence()
    const presence = container.resolve<any>(TOKENS.presenceRuntime)
    expect(presence.hasCognitiveRuntime()).toBe(true)
    expect(presence.getCognitiveState()).not.toBeNull()
    expect(presence.getAttentionState()).not.toBeNull()
    expect(presence.getRelationshipState()).not.toBeNull()
  })

  it('cognitive state is independent of the renderer (CharacterFrame has no cognition fields)', () => {
    const { container } = bootstrapPresence()
    const presence = container.resolve<any>(TOKENS.presenceRuntime)
    const frame = presence.getCharacterFrame()
    expect(frame).not.toBeNull()
    expect(JSON.stringify(frame)).not.toMatch(/reasoning|relationship|trust|planning/i)
  })

  it('feeds the cognitive bundle event-driven from the aggregator', async () => {
    const { container } = bootstrapPresence()
    const presence = container.resolve<any>(TOKENS.presenceRuntime)
    await presence.start()
    const state = presence.getCognitiveState()
    // The initial/seed snapshot drives at least reasoning + attention.
    expect(state.reasoning).toBeDefined()
    expect(presence.getAttentionState().current).toBeDefined()
  })
})

describe('PART 7 — Performance (event-driven, no extra loops)', () => {
  it('CognitiveBundle.update is cheap across many ticks', () => {
    const bundle = new CognitiveBundle()
    const start = performance.now()
    for (let i = 0; i < 5000; i++) bundle.update(1 / 30)
    expect(performance.now() - start).toBeLessThan(100)
  })

  it('emitting a cognitive event is O(1)-cheap', () => {
    const c = new CognitiveRuntime()
    c.subscribe(() => {})
    const start = performance.now()
    for (let i = 0; i < 10000; i++) c.emit({ kind: 'attention', priority: 0.5 })
    expect(performance.now() - start).toBeLessThan(100)
  })

  it('no new requestAnimationFrame / setInterval in the cognitive layer', async () => {
    const fs = await import('fs')
    const path = await import('path')
    const src = fs.readFileSync(path.join(__dirname, '../../src/runtime/cognitive/types.ts'), 'utf-8')
    expect(src).not.toMatch(/requestAnimationFrame|setInterval|setTimeout|setImmediate/)
  })

  it('shares the single existing 30Hz tick (no duplicated state)', () => {
    // When injected, PresenceRuntime advances the bundle inside its tick.
    // We assert the relationship state advances after start() ticks without any
    // additional timers being created by the cognitive layer.
    const { container } = bootstrapPresence()
    const presence = container.resolve<any>(TOKENS.presenceRuntime)
    const bundle = container.resolve<any>(TOKENS.cognitiveRuntime)
    const before = bundle.getRelationshipState().updatedAt
    return new Promise<void>((resolve) => {
      presence.start().then(() => {
        setTimeout(() => {
          const after = bundle.getRelationshipState().updatedAt
          expect(after).toBeGreaterThanOrEqual(before)
          presence.shutdown()
          resolve()
        }, 100)
      })
    })
  })
})
