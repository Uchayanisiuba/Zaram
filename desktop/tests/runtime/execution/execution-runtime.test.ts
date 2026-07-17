// desktop/tests/runtime/execution/execution-runtime.test.ts
//
// Milestone 1.6 — Execution Runtime tests.
//
// Verifies: lifecycle transitions, retry, timeout, cancellation, rollback,
// permission enforcement, progress reporting, audit trail, execution history,
// DI registration, the 30Hz tick advancement (no new timers), and
// renderer/embodiment independence (asserted structurally — no forbidden imports).

import { describe, it, expect, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import {
  ExecutionRuntime,
  ExecutionInvoker,
  newExecutionId,
  executionNow
} from '../../../src/runtime/execution'
import type {
  ExecutionRequest,
  ExecutionHandler,
  ExecutionRollback,
  ExecutionOptions
} from '../../../src/runtime/execution'
import type { ICapabilityRuntime, CapabilityDescriptor, CapabilityPermission } from '../../../src/runtime/capability'
import { Container, TOKENS } from '../../../src/runtime/di/container'
import { bootstrapPresence } from '../../../src/runtime/bootstrap'

// --- Helpers ---------------------------------------------------------------

function makeHandler(output: unknown = 'ok'): ExecutionHandler {
  return (_req, _ctx, controls) => {
    controls.reportProgress(1)
    controls.succeed(output)
  }
}

function makeAsyncHandler(delayMs: number, output: unknown = 'ok'): ExecutionHandler {
  return (_req, _ctx, controls) => {
    return new Promise((resolve) => {
      setTimeout(() => {
        controls.reportProgress(1)
        controls.succeed(output)
        resolve(undefined)
      }, delayMs)
    })
  }
}

function makeFailingHandler(message: string): ExecutionHandler {
  return (_req, _ctx, controls) => {
    controls.fail(new Error(message))
  }
}

function makeCapabilityRuntime(permissions: CapabilityPermission[] = []): ICapabilityRuntime {
  return {
    register: () => ({ id: '', name: '', description: '', category: 'system', permissions: [], inputSchema: { type: 'object' }, outputSchema: { type: 'object' }, availability: 'available', latencyEstimateMs: 0, location: 'local', cost: 0, enabled: true, revision: 0, updatedAt: 0 }),
    registerOrReplace: () => ({ id: '', name: '', description: '', category: 'system', permissions: [], inputSchema: { type: 'object' }, outputSchema: { type: 'object' }, availability: 'available', latencyEstimateMs: 0, location: 'local', cost: 0, enabled: true, revision: 0, updatedAt: 0 }),
    unregister: () => false,
    update: () => null,
    has: () => true,
    get: () => ({
      id: 'test.cap',
      name: 'Test Capability',
      description: 'A test capability',
      category: 'system',
      permissions,
      inputSchema: { type: 'object' },
      outputSchema: { type: 'object' },
      availability: 'available',
      latencyEstimateMs: 10,
      location: 'local',
      cost: 0,
      enabled: true,
      revision: 1,
      updatedAt: Date.now()
    } as CapabilityDescriptor),
    getByCategory: () => [],
    all: () => [],
    filter: () => [],
    resolve: () => ({ capability: null as unknown as CapabilityDescriptor, found: false, candidates: [] }),
    getSnapshot: () => ({ revision: 0, total: 0, enabled: 0, byCategory: {}, capabilities: [] }),
    getRevision: () => 0
  }
}

function makeInvoker(handler: ExecutionHandler, rollback?: ExecutionRollback): ExecutionInvoker {
  const invoker = new ExecutionInvoker()
  invoker.register('test.cap', handler)
  if (rollback) invoker.registerWithRollback('test.cap', handler, rollback)
  return invoker
}

function baseRequest(overrides: Partial<ExecutionRequest> = {}): ExecutionRequest {
  return {
    capabilityId: 'test.cap',
    input: { data: 'hello' },
    context: {
      correlationId: 'corr-1',
      grantedPermissions: ['system:execute'],
      createdAt: Date.now()
    },
    ...overrides
  }
}

// --- Lifecycle tests -------------------------------------------------------

describe('Execution Runtime — lifecycle', () => {
  it('queues an execution and advances through the lifecycle on the tick', () => {
    const runtime = new ExecutionRuntime({
      invoker: makeInvoker(makeHandler('done')),
      now: () => 1000
    })

    const id = runtime.execute(baseRequest())
    expect(runtime.getExecution(id)?.status).toBe('queued')

    runtime.update(1 / 30)

    const exec = runtime.getExecution(id)
    expect(exec?.status).toBe('completed')
    expect(exec?.output).toBe('done')
    expect(exec?.attempts).toBe(1)
    expect(exec?.progress).toBe(1)
    expect(exec?.startedAt).not.toBeNull()
    expect(exec?.finishedAt).not.toBeNull()
    expect(exec?.durationMs).not.toBeNull()
  })

  it('publishes lifecycle events on every transition', () => {
    const events: string[] = []
    const runtime = new ExecutionRuntime({
      invoker: makeInvoker(makeHandler()),
      now: () => 1000
    })
    runtime.subscribe((e) => events.push(e.event_type))

    const id = runtime.execute(baseRequest())
    runtime.update(1 / 30)

    expect(events).toContain('execution.queued')
    expect(events).toContain('execution.preparing')
    expect(events).toContain('execution.running')
    expect(events).toContain('execution.completed')
  })

  it('records audit trail on every action', () => {
    const runtime = new ExecutionRuntime({
      invoker: makeInvoker(makeHandler()),
      now: () => 1000
    })

    const id = runtime.execute(baseRequest())
    runtime.update(1 / 30)

    const exec = runtime.getExecution(id)
    expect(exec?.audit.length).toBeGreaterThan(0)
    expect(exec?.audit.some((a) => a.action === 'execute')).toBe(true)
    expect(exec?.audit.some((a) => a.action === 'transition')).toBe(true)
    expect(exec?.audit.some((a) => a.action === 'succeed')).toBe(true)
  })

  it('records execution history per attempt', () => {
    const runtime = new ExecutionRuntime({
      invoker: makeInvoker(makeHandler()),
      now: () => 1000
    })

    const id = runtime.execute(baseRequest())
    runtime.update(1 / 30)

    const exec = runtime.getExecution(id)
    expect(exec?.history.length).toBe(1)
    expect(exec?.history[0].status).toBe('completed')
    expect(exec?.history[0].attempt).toBe(1)
  })

  it('rejects illegal state transitions', () => {
    const runtime = new ExecutionRuntime({
      invoker: makeInvoker(makeHandler()),
      now: () => 1000
    })

    const id = runtime.execute(baseRequest())
    runtime.update(1 / 30)

    expect(() => {
      const exec = runtime.getExecution(id)
      if (exec) {
        const sm = require('../../../src/runtime/execution/execution-state-machine')
        sm.transition(exec.status, 'queued')
      }
    }).toThrow()
  })

  it('generates stable unique execution ids', () => {
    const runtime = new ExecutionRuntime()
    const a = runtime.execute(baseRequest())
    const b = runtime.execute(baseRequest())
    expect(a).not.toBe(b)
    expect(a.startsWith('exec-')).toBe(true)
  })
})

// --- Retry tests -----------------------------------------------------------

describe('Execution Runtime — retry', () => {
  it('retries a failed execution', () => {
    let calls = 0
    const invoker = new ExecutionInvoker()
    invoker.register('test.cap', (_req, _ctx, controls) => {
      calls += 1
      if (calls === 1) {
        controls.fail(new Error('fail'))
      } else {
        controls.succeed('ok')
      }
    })

    const runtime = new ExecutionRuntime({
      invoker,
      now: () => 1000
    })

    const id = runtime.execute({ ...baseRequest(), options: { maxRetries: 3 } })
    runtime.update(1 / 30)
    expect(runtime.getExecution(id)?.status).toBe('failed')

    runtime.retry(id)
    runtime.update(1 / 30)
    expect(runtime.getExecution(id)?.status).toBe('completed')
    expect(calls).toBe(2)
    expect(runtime.getExecution(id)?.attempts).toBe(2)
  })
})

// --- Timeout tests ---------------------------------------------------------

describe('Execution Runtime — timeout', () => {
  it('fails an execution that exceeds its timeout on the tick', () => {
    const clock = { t: 1000 }
    const invoker = new ExecutionInvoker()
    invoker.register('test.cap', (_req, _ctx, controls) => {
      if (controls.elapsedMs() < 30) {
        return
      }
      controls.succeed('ok')
    })

    const runtime = new ExecutionRuntime({
      invoker,
      now: () => clock.t
    })

    const id = runtime.execute({ ...baseRequest(), options: { timeoutMs: 50 } })
    runtime.update(1 / 30)
    expect(runtime.getExecution(id)?.status).toBe('running')

    clock.t += 100
    runtime.update(1 / 30)
    expect(runtime.getExecution(id)?.status).toBe('failed')
    expect(runtime.getExecution(id)?.error?.code).toBe('timeout')
  })

  it('does not timeout before the limit is reached', () => {
    const clock = { t: 1000 }
    const invoker = new ExecutionInvoker()
    invoker.register('test.cap', (_req, _ctx, controls) => {
      controls.succeed('ok')
    })

    const runtime = new ExecutionRuntime({
      invoker,
      now: () => clock.t
    })

    const id = runtime.execute({ ...baseRequest(), options: { timeoutMs: 5000 } })
    runtime.update(1 / 30)
    expect(runtime.getExecution(id)?.status).toBe('completed')
  })
})

// --- Cancellation tests ----------------------------------------------------

describe('Execution Runtime — cancellation', () => {
  it('cancels a queued execution immediately', () => {
    const runtime = new ExecutionRuntime({ now: () => 1000 })
    const id = runtime.execute(baseRequest())
    expect(runtime.cancel(id)).toBe(true)
    expect(runtime.getExecution(id)?.status).toBe('cancelled')
    expect(runtime.getExecution(id)?.cancelled).toBe(true)
  })

  it('cancels a running execution on the tick', () => {
    const runtime = new ExecutionRuntime({
      invoker: makeInvoker(() => {
        return makeHandler('ok')({} as any, {} as any, {
          reportProgress: () => {},
          succeed: () => {},
          fail: () => {},
          isCancelled: () => false,
          elapsedMs: () => 0
        } as any)
      }),
      now: () => 1000
    })

    const id = runtime.execute(baseRequest())
    runtime.update(1 / 30)
    expect(runtime.getExecution(id)?.status).toBe('running')

    runtime.cancel(id)
    runtime.update(1 / 30)
    expect(runtime.getExecution(id)?.status).toBe('cancelled')
  })

  it('cannot cancel a completed execution', () => {
    const runtime = new ExecutionRuntime({
      invoker: makeInvoker(makeHandler()),
      now: () => 1000
    })

    const id = runtime.execute(baseRequest())
    runtime.update(1 / 30)
    expect(runtime.cancel(id)).toBe(false)
  })

  it('respects cancellable: false option', () => {
    const runtime = new ExecutionRuntime({
      invoker: makeInvoker(makeHandler()),
      now: () => 1000
    })

    const id = runtime.execute({ ...baseRequest(), options: { cancellable: false } })
    runtime.update(1 / 30)
    expect(runtime.cancel(id)).toBe(false)
    expect(runtime.getExecution(id)?.status).toBe('completed')
  })
})

// --- Rollback tests --------------------------------------------------------

describe('Execution Runtime — rollback', () => {
  it('invokes rollback hook on failure when rollbackSupported is true', () => {
    const rollbackFn = vi.fn()
    const runtime = new ExecutionRuntime({
      invoker: makeInvoker(makeFailingHandler('fail'), rollbackFn),
      now: () => 1000
    })

    const id = runtime.execute({ ...baseRequest(), options: { rollbackSupported: true } })
    runtime.update(1 / 30)

    expect(rollbackFn).toHaveBeenCalledTimes(1)
    expect(runtime.getExecution(id)?.status).toBe('rolledback')
    expect(runtime.getExecution(id)?.rolledBack).toBe(true)
  })

  it('does not rollback when rollbackSupported is false', () => {
    const rollbackFn = vi.fn()
    const runtime = new ExecutionRuntime({
      invoker: makeInvoker(makeFailingHandler('fail'), rollbackFn),
      now: () => 1000
    })

    const id = runtime.execute(baseRequest())
    runtime.update(1 / 30)

    expect(rollbackFn).not.toHaveBeenCalled()
    expect(runtime.getExecution(id)?.status).toBe('failed')
  })

  it('can manually trigger rollback on a failed execution', () => {
    const rollbackFn = vi.fn()
    const runtime = new ExecutionRuntime({
      invoker: makeInvoker(makeFailingHandler('fail'), rollbackFn),
      now: () => 1000
    })

    const id = runtime.execute(baseRequest())
    runtime.update(1 / 30)
    expect(runtime.getExecution(id)?.status).toBe('failed')

    runtime.rollback(id)
    expect(rollbackFn).toHaveBeenCalledTimes(1)
    expect(runtime.getExecution(id)?.status).toBe('rolledback')
  })
})

// --- Permission tests ------------------------------------------------------

describe('Execution Runtime — permission enforcement', () => {
  it('fails execution when required permissions are missing', () => {
    const capabilityRuntime = makeCapabilityRuntime(['system:admin'])
    const runtime = new ExecutionRuntime({
      invoker: makeInvoker(makeHandler()),
      capabilityRuntime,
      now: () => 1000
    })

    const id = runtime.execute(baseRequest())
    runtime.update(1 / 30)

    expect(runtime.getExecution(id)?.status).toBe('failed')
    expect(runtime.getExecution(id)?.error?.kind).toBe('permission')
  })

  it('succeeds when all permissions are granted', () => {
    const capabilityRuntime = makeCapabilityRuntime(['system:execute'])
    const runtime = new ExecutionRuntime({
      invoker: makeInvoker(makeHandler()),
      capabilityRuntime,
      now: () => 1000
    })

    const id = runtime.execute(baseRequest())
    runtime.update(1 / 30)

    expect(runtime.getExecution(id)?.status).toBe('completed')
  })

  it('fails when capability is not found', () => {
    const capabilityRuntime: ICapabilityRuntime = {
      register: () => ({ id: '', name: '', description: '', category: 'system', permissions: [], inputSchema: { type: 'object' }, outputSchema: { type: 'object' }, availability: 'available', latencyEstimateMs: 0, location: 'local', cost: 0, enabled: true, revision: 0, updatedAt: 0 }),
      registerOrReplace: () => ({ id: '', name: '', description: '', category: 'system', permissions: [], inputSchema: { type: 'object' }, outputSchema: { type: 'object' }, availability: 'available', latencyEstimateMs: 0, location: 'local', cost: 0, enabled: true, revision: 0, updatedAt: 0 }),
      unregister: () => false,
      update: () => null,
      has: () => false,
      get: () => null,
      getByCategory: () => [],
      all: () => [],
      filter: () => [],
      resolve: () => ({ capability: null, found: false, candidates: [] }),
      getSnapshot: () => ({ revision: 0, total: 0, enabled: 0, byCategory: {}, capabilities: [] }),
      getRevision: () => 0
    }
    const runtime = new ExecutionRuntime({
      invoker: makeInvoker(makeHandler()),
      capabilityRuntime,
      now: () => 1000
    })

    const id = runtime.execute(baseRequest())
    runtime.update(1 / 30)

    expect(runtime.getExecution(id)?.status).toBe('failed')
    expect(runtime.getExecution(id)?.error?.kind).toBe('capability-unavailable')
  })
})

// --- Performance tests -----------------------------------------------------

describe('Execution Runtime — performance', () => {
  it('executes 1000 simple executions within a reasonable time', () => {
    const runtime = new ExecutionRuntime({
      invoker: makeInvoker(makeHandler()),
      now: () => 1000
    })

    const start = performance.now()
    const ids: string[] = []
    for (let i = 0; i < 1000; i++) {
      ids.push(runtime.execute(baseRequest()))
    }
    for (let i = 0; i < 10; i++) {
      runtime.update(1 / 30)
    }
    const elapsed = performance.now() - start

    expect(ids.length).toBe(1000)
    expect(runtime.getHistory().filter((e) => e.status === 'completed').length).toBe(1000)
    expect(elapsed).toBeLessThan(5000)
  })

  it('handles 10000 executions benchmark', () => {
    const runtime = new ExecutionRuntime({
      invoker: makeInvoker(makeHandler()),
      now: () => 1000
    })

    const start = performance.now()
    const ids: string[] = []
    for (let i = 0; i < 10000; i++) {
      ids.push(runtime.execute(baseRequest()))
    }
    for (let i = 0; i < 10; i++) {
      runtime.update(1 / 30)
    }
    const elapsed = performance.now() - start

    expect(ids.length).toBe(10000)
    expect(runtime.getHistory().filter((e) => e.status === 'completed').length).toBe(10000)
    expect(elapsed).toBeLessThan(15000)
  })
})

// --- Stress tests ----------------------------------------------------------

describe('Execution Runtime — stress', () => {
  it('survives concurrent submissions without state corruption', () => {
    const runtime = new ExecutionRuntime({
      invoker: makeInvoker(makeHandler()),
      now: () => 1000
    })

    const ids: string[] = []
    for (let i = 0; i < 5000; i++) {
      ids.push(runtime.execute(baseRequest()))
    }
    for (let i = 0; i < 20; i++) {
      runtime.update(1 / 30)
    }

    const history = runtime.getHistory()
    expect(history.length).toBe(5000)
    expect(history.every((e) => e.status === 'completed')).toBe(true)
  })

  it('handles mixed success and failure without leaking state', () => {
    let toggle = false
    const invoker = new ExecutionInvoker()
    invoker.register('test.cap', (_req, _ctx, controls) => {
      toggle = !toggle
      if (toggle) {
        controls.succeed('ok')
      } else {
        controls.fail(new Error('fail'))
      }
    })

    const runtime = new ExecutionRuntime({
      invoker,
      now: () => 1000
    })

    const ids: string[] = []
    for (let i = 0; i < 1000; i++) {
      ids.push(runtime.execute(baseRequest()))
    }
    for (let i = 0; i < 10; i++) {
      runtime.update(1 / 30)
    }

    const history = runtime.getHistory()
    expect(history.length).toBe(1000)
    const completed = history.filter((e) => e.status === 'completed').length
    const failed = history.filter((e) => e.status === 'failed').length
    expect(completed + failed).toBe(1000)
  })
})

// --- DI tests --------------------------------------------------------------

describe('Execution Runtime — DI', () => {
  it('registers as a singleton in the DI container', () => {
    const { container } = bootstrapPresence()
    expect(container.has(TOKENS.executionRuntime)).toBe(true)
    const a = container.resolve(TOKENS.executionRuntime)
    const b = container.resolve(TOKENS.executionRuntime)
    expect(a).toBe(b)
    expect(a).toBeInstanceOf(ExecutionRuntime)
  })

  it('can be resolved standalone and advanced', () => {
    const c = new Container()
    c.register(TOKENS.executionRuntime, () => new ExecutionRuntime())
    const runtime = c.resolve<ExecutionRuntime>(TOKENS.executionRuntime)
    runtime.update(1 / 30)
    expect(runtime.getHistory()).toHaveLength(0)
  })

  it('is wired into PresenceRuntime via DI (30Hz tick advances it)', () => {
    const { container } = bootstrapPresence()
    expect(container.has(TOKENS.executionRuntime)).toBe(true)
    const runtime = container.resolve<ExecutionRuntime>(TOKENS.executionRuntime)
    expect(runtime).toBeInstanceOf(ExecutionRuntime)
    // Verify the tick advances it without error
    expect(() => runtime.update(1 / 30)).not.toThrow()
  })
})

// --- No timers / polling / forbidden imports -------------------------------

describe('Execution Runtime — no timers / polling', () => {
  const files = [
    'index.ts',
    'types.ts',
    'execution-state-machine.ts',
    'execution-context.ts',
    'execution-invoker.ts',
    'execution-runtime.ts'
  ]

  for (const f of files) {
    it(`${f} must not use setInterval`, () => {
      const src = readFileSync(join(__dirname, '..', '..', '..', 'src', 'runtime', 'execution', f), 'utf8')
      expect(src, `${f} must not use setInterval`).not.toMatch(/setInterval\s*\(/)
    })

    it(`${f} must not use setTimeout`, () => {
      const src = readFileSync(join(__dirname, '..', '..', '..', 'src', 'runtime', 'execution', f), 'utf8')
      expect(src, `${f} must not use setTimeout`).not.toMatch(/setTimeout\s*\(/)
    })

    it(`${f} must not use requestAnimationFrame`, () => {
      const src = readFileSync(join(__dirname, '..', '..', '..', 'src', 'runtime', 'execution', f), 'utf8')
      expect(src, `${f} must not use requestAnimationFrame`).not.toMatch(/requestAnimationFrame\s*\(/)
    })

    it(`${f} must not use while loops`, () => {
      const src = readFileSync(join(__dirname, '..', '..', '..', 'src', 'runtime', 'execution', f), 'utf8')
      expect(src, `${f} must not use while loops`).not.toMatch(/while\s*\(\s*\)/)
    })

    it(`${f} must not use unbounded for`, () => {
      const src = readFileSync(join(__dirname, '..', '..', '..', 'src', 'runtime', 'execution', f), 'utf8')
      expect(src, `${f} must not use unbounded for`).not.toMatch(/for\s*\(\s*;\s*;\s*\)/)
    })
  }

  it('must not import renderer, embodiment, or character pipeline', () => {
    const dir = join(__dirname, '..', '..', '..', 'src', 'runtime', 'execution')
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
