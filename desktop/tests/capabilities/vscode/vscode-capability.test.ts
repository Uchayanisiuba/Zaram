// desktop/tests/capabilities/vscode/vscode-capability.test.ts
//
// Sprint 2.3 — VS Code Capability Pack tests.

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { CapabilityRuntime } from '../../../src/runtime/capability/capability-runtime'
import { ExecutionInvoker } from '../../../src/runtime/execution/execution-invoker'
import { VSCodeCapabilityPack } from '../../../src/capabilities/vscode/vscode-capability'

describe('VS Code Capability Pack', () => {
  let capabilityRuntime: CapabilityRuntime
  let invoker: ExecutionInvoker

  beforeEach(() => {
    capabilityRuntime = new CapabilityRuntime()
    invoker = new ExecutionInvoker()
  })

  it('should register 4 VS Code descriptors', () => {
    const pack = new VSCodeCapabilityPack(capabilityRuntime, '/tmp/workspace')
    pack.registerDescriptors(capabilityRuntime)

    const caps = capabilityRuntime.all()
    const vscodeCaps = caps.filter(c => c.id.startsWith('vscode.'))
    expect(vscodeCaps.length).toBe(4)

    const ids = vscodeCaps.map(c => c.id).sort()
    expect(ids).toEqual([
      'vscode.diagnostics',
      'vscode.editor.active',
      'vscode.git.status',
      'vscode.workspace.folders'
    ])
  })

  it('should register handlers for all 4 capabilities', () => {
    const pack = new VSCodeCapabilityPack(capabilityRuntime, '/tmp/workspace')
    pack.registerHandlers(invoker)

    expect(invoker.has('vscode.editor.active')).toBe(true)
    expect(invoker.has('vscode.workspace.folders')).toBe(true)
    expect(invoker.has('vscode.diagnostics')).toBe(true)
    expect(invoker.has('vscode.git.status')).toBe(true)
  })

  it('should emit events when handlers are invoked', async () => {
    const pack = new VSCodeCapabilityPack(capabilityRuntime, '/tmp/workspace')
    pack.registerHandlers(invoker)
    const events: any[] = []
    pack.subscribe((e) => events.push(e))

    const handler = invoker.resolve('vscode.editor.active')
    expect(handler).toBeDefined()

    await new Promise<void>((resolve) => {
      handler!(
        { capabilityId: 'vscode.editor.active', input: null, context: { correlationId: '1', grantedPermissions: [], createdAt: Date.now() }, id: '1', options: {} },
        { correlationId: '1', grantedPermissions: [], createdAt: Date.now() },
        {
          reportProgress: () => {},
          succeed: () => resolve(),
          fail: () => resolve(),
          isCancelled: () => false,
          elapsedMs: () => 0
        }
      )
    })

    const started = events.find(e => e.eventType === 'vscode.editor.active.started')
    expect(started).toBeDefined()
  })

  it('should publish adapter events through the pack', () => {
    const pack = new VSCodeCapabilityPack(capabilityRuntime, '/tmp/workspace')
    const events: any[] = []
    pack.getAdapter().subscribe((e) => events.push(e))

    pack.getAdapter().start()

    const connected = events.find(e => e.type === 'vscode.connected')
    expect(connected).toBeDefined()
  })
})
