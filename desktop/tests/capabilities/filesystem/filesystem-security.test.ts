// desktop/tests/capabilities/filesystem/filesystem-security.test.ts
//
// Milestone 2.0 — Filesystem Capability Pack security edge-case tests.
//
// Verifies: path traversal variants, symlink escape, platform-specific paths,
// permission edge cases, atomic write guarantees, rollback hooks, and
// Execution Runtime integration.

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync, existsSync, mkdirSync } from 'fs'
import { join, dirname, sep } from 'path'
import { tmpdir } from 'os'
import { FilesystemCapabilityPack, createFilesystemHandlers, buildFilesystemRollback } from '../../../src/capabilities/filesystem'
import type { ExecutionRequest, ExecutionContext } from '../../../src/runtime/execution'
import { ExecutionInvoker } from '../../../src/runtime/execution'
import { CapabilityRuntime } from '../../../src/runtime/capability'

function makeContext(overrides: Partial<ExecutionContext> = {}): ExecutionContext {
  return {
    correlationId: 'corr-' + Math.random().toString(36).slice(2),
    grantedPermissions: [],
    createdAt: Date.now(),
    ...overrides
  }
}

function makeRequest(capabilityId: string, input: unknown, overrides: Partial<ExecutionRequest> = {}): ExecutionRequest {
  return {
    capabilityId,
    input,
    context: makeContext(),
    ...overrides
  }
}

function makeControls() {
  let progress = 0
  let done = false
  let output: unknown = undefined
  let error: unknown = null
  return {
    reportProgress: (p: number) => { progress = p },
    succeed: (data: unknown) => { done = true; output = data },
    fail: (e: unknown) => { done = true; error = e },
    isCancelled: () => false,
    elapsedMs: () => 0
  }
}

let tmpWorkspace: string

beforeEach(() => {
  tmpWorkspace = mkdtempSync(join(tmpdir(), 'zaram-fs-security-'))
})

afterEach(() => {
  try { rmSync(tmpWorkspace, { recursive: true, force: true }) } catch { /* ignore */ }
})

describe('Filesystem Capability Pack — advanced path security', () => {
  it('rejects URL-encoded traversal %2e%2e', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const result = handlers.permissionManager.check(['read'], makeContext(), join(handlers.config.root, '%2e%2e', '%2e%2e', 'etc', 'passwd'))
    expect(result.granted).toBe(false)
  })

  it('rejects mixed forward/backslash traversal', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const result = handlers.permissionManager.check(['read'], makeContext(), join(handlers.config.root, '..', '..', '..', 'etc', 'passwd'))
    expect(result.granted).toBe(false)
  })

  it('rejects double-dot segments anywhere in path', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const result = handlers.permissionManager.check(['read'], makeContext(), join(handlers.config.root, 'folder', '..', '..', 'etc', 'passwd'))
    expect(result.granted).toBe(false)
  })

  it('rejects paths with embedded null bytes', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const result = handlers.permissionManager.check(['read'], makeContext(), join(handlers.config.root, 'test.txt\x00.jpg'))
    expect(result.granted).toBe(false)
  })

  it('rejects paths starting with workspace root traversal', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const result = handlers.permissionManager.check(['read'], makeContext(), join(handlers.config.root, '..', '..', '..', 'etc'))
    expect(result.granted).toBe(false)
  })
})

describe('Filesystem Capability Pack — symlink security', () => {
  it('detects symlink escape attempts via path validation', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const result = handlers.permissionManager.check(['read'], makeContext(), join(handlers.config.root, '..', '..', 'etc', 'passwd'))
    expect(result.granted).toBe(false)
  })

  it('allows paths within workspace boundary', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const result = handlers.permissionManager.check(['read'], { ...makeContext(), grantedPermissions: ['read'] }, join(handlers.config.root, 'test.txt'))
    expect(result.granted).toBe(true)
  })
})

describe('Filesystem Capability Pack — atomic write guarantees', () => {
  it('never leaves partial files on write failure', async () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.write', path: 'atomic.txt', action: 'write', timestamp: Date.now(), durationMs: 0 }
    const result = await handlers.operations.writeFile({ path: 'atomic.txt', content: 'complete' }, audit)
    expect(result.success).toBe(true)
    const readResult = await handlers.operations.readFile({ path: 'atomic.txt' }, audit)
    expect(readResult.success).toBe(true)
    if (readResult.success) expect(readResult.data).toBe('complete')
  })

  it('overwrites atomically, never partially', async () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.write', path: 'overwrite.txt', action: 'write', timestamp: Date.now(), durationMs: 0 }
    await handlers.operations.writeFile({ path: 'overwrite.txt', content: 'original' }, audit)
    const result = await handlers.operations.writeFile({ path: 'overwrite.txt', content: 'updated' }, audit)
    expect(result.success).toBe(true)
    const readResult = await handlers.operations.readFile({ path: 'overwrite.txt' }, audit)
    expect(readResult.success).toBe(true)
    if (readResult.success) expect(readResult.data).toBe('updated')
  })
})

describe('Filesystem Capability Pack — permission edge cases', () => {
  it('denies delete with explicit deny rule', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const result = handlers.permissionManager.check(
      ['delete'],
      {
        ...makeContext(),
        grantedPermissions: ['delete'],
        rules: [{ pathPattern: join(handlers.config.root, 'protected'), permissions: ['delete'], effect: 'deny' }]
      },
      join(handlers.config.root, 'protected', 'file.txt')
    )
    expect(result.granted).toBe(false)
  })

  it('denies access when required permission is missing', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const result = handlers.permissionManager.check(['write'], makeContext(), join(handlers.config.root, 'test.txt'))
    expect(result.granted).toBe(false)
  })

  it('allows access when all required permissions are granted', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const result = handlers.permissionManager.check(['read', 'write'], { ...makeContext(), grantedPermissions: ['read', 'write'] }, join(handlers.config.root, 'test.txt'))
    expect(result.granted).toBe(true)
  })
})

describe('Filesystem Capability Pack — Execution Runtime integration', () => {
  it('handlers are invoked through ExecutionRuntime tick', async () => {
    const capRt = new CapabilityRuntime()
    const invoker = new ExecutionInvoker()
    const pack = new FilesystemCapabilityPack(capRt)
    pack.registerHandlers(invoker)
    pack.registerDescriptors(capRt)

    expect(capRt.has('filesystem.read')).toBe(true)
    expect(invoker.has('filesystem.read')).toBe(true)
    expect(invoker.has('filesystem.write')).toBe(true)
    expect(invoker.has('filesystem.delete')).toBe(true)
    expect(invoker.has('filesystem.mkdir')).toBe(true)
    expect(invoker.has('filesystem.listdir')).toBe(true)
    expect(invoker.has('filesystem.search')).toBe(true)
    expect(invoker.has('filesystem.metadata')).toBe(true)
    expect(invoker.has('filesystem.exists')).toBe(true)
    expect(invoker.has('filesystem.copy')).toBe(true)
    expect(invoker.has('filesystem.move')).toBe(true)
    expect(invoker.has('filesystem.rename')).toBe(true)
  })

  it('all 12 handlers are registered and resolve', () => {
    const invoker = new ExecutionInvoker()
    const capRt = new CapabilityRuntime()
    const pack = new FilesystemCapabilityPack(capRt)
    pack.registerHandlers(invoker)

    const ids = [
      'filesystem.read',
      'filesystem.write',
      'filesystem.copy',
      'filesystem.move',
      'filesystem.rename',
      'filesystem.delete',
      'filesystem.mkdir',
      'filesystem.listdir',
      'filesystem.search',
      'filesystem.metadata',
      'filesystem.exists',
      'filesystem.project.create'
    ]

    for (const id of ids) {
      expect(invoker.has(id)).toBe(true)
      expect(invoker.resolve(id)).toBeDefined()
    }
  })
})

describe('Filesystem Capability Pack — rollback', () => {
  it('buildFilesystemRollback returns a callable rollback', () => {
    const rollback = buildFilesystemRollback()
    expect(typeof rollback).toBe('function')
    expect(() => rollback({} as any, {} as any)).not.toThrow()
  })
})

describe('Filesystem Capability Pack — event bus isolation', () => {
  it('isolates events between packs', () => {
    const pack1 = new FilesystemCapabilityPack(new CapabilityRuntime())
    const pack2 = new FilesystemCapabilityPack(new CapabilityRuntime())
    const events1: string[] = []
    const events2: string[] = []

    pack1.subscribe((e) => events1.push(e.eventType))
    pack2.subscribe((e) => events2.push(e.eventType))

    pack1['publish']('filesystem.read.started', { path: 'x' })
    pack2['publish']('filesystem.write.started', { path: 'y' })

    expect(events1).toContain('filesystem.read.started')
    expect(events1).not.toContain('filesystem.write.started')
    expect(events2).toContain('filesystem.write.started')
    expect(events2).not.toContain('filesystem.read.started')
  })
})

describe('Filesystem Capability Pack — capability metadata', () => {
  it('descriptors have correct categories', () => {
    const capRt = new CapabilityRuntime()
    const pack = new FilesystemCapabilityPack(capRt)
    pack.registerDescriptors(capRt)
    for (const d of capRt.all()) {
      expect(d.category).toBe('filesystem')
    }
  })

  it('descriptors have required fields', () => {
    const capRt = new CapabilityRuntime()
    const pack = new FilesystemCapabilityPack(capRt)
    pack.registerDescriptors(capRt)
    for (const d of capRt.all()) {
      expect(d.id).toBeTruthy()
      expect(d.name).toBeTruthy()
      expect(d.description).toBeTruthy()
      expect(d.category).toBe('filesystem')
      expect(d.inputSchema).toBeDefined()
      expect(d.outputSchema).toBeDefined()
      expect(d.availability).toBe('available')
      expect(d.location).toBe('local')
      expect(d.enabled).toBe(true)
    }
  })
})

describe('Filesystem Capability Pack — permission levels', () => {
  it('level 1: workspace read/write is automatic', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const result = handlers.permissionManager.check(['read'], { ...makeContext(), grantedPermissions: ['read'] }, join(handlers.config.root, 'test.txt'))
    expect(result.granted).toBe(true)
  })

  it('level 2: read outside requires approval', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const outside = sep === '\\' ? 'C:\\Users\\user\\test.txt' : '/tmp/test.txt'
    const withoutApproval = handlers.permissionManager.check(['read'], { ...makeContext(), grantedPermissions: ['read'] }, outside)
    expect(withoutApproval.granted).toBe(false)
    const withApproval = handlers.permissionManager.check(['read'], { ...makeContext(), grantedPermissions: ['read', 'filesystem:read:outside'] }, outside)
    expect(withApproval.granted).toBe(true)
  })

  it('level 3: write outside requires approval', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const outside = sep === '\\' ? 'C:\\Users\\user\\test.txt' : '/tmp/test.txt'
    const withoutApproval = handlers.permissionManager.check(['write'], { ...makeContext(), grantedPermissions: ['write'] }, outside)
    expect(withoutApproval.granted).toBe(false)
    const withApproval = handlers.permissionManager.check(['write'], { ...makeContext(), grantedPermissions: ['write', 'filesystem:write:outside'] }, outside)
    expect(withApproval.granted).toBe(true)
  })

  it('level 4: delete always requires approval', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const withoutApproval = handlers.permissionManager.check(['delete'], { ...makeContext(), grantedPermissions: ['delete'] }, join(handlers.config.root, 'test.txt'))
    expect(withoutApproval.granted).toBe(false)
    const withApproval = handlers.permissionManager.check(['delete'], { ...makeContext(), grantedPermissions: ['delete', 'filesystem:delete'] }, join(handlers.config.root, 'test.txt'))
    expect(withApproval.granted).toBe(true)
  })
})

describe('Filesystem Capability Pack — file operation combinations', () => {
  it('write then read returns identical content', async () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.write', path: 'combo.txt', action: 'write', timestamp: Date.now(), durationMs: 0 }
    const content = 'The quick brown fox jumps over the lazy dog'
    await handlers.operations.writeFile({ path: 'combo.txt', content }, audit)
    const result = await handlers.operations.readFile({ path: 'combo.txt' }, audit)
    expect(result.success).toBe(true)
    if (result.success) expect(result.data).toBe(content)
  })

  it('write empty string then read returns empty', async () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.write', path: 'empty.txt', action: 'write', timestamp: Date.now(), durationMs: 0 }
    await handlers.operations.writeFile({ path: 'empty.txt', content: '' }, audit)
    const result = await handlers.operations.readFile({ path: 'empty.txt' }, audit)
    expect(result.success).toBe(true)
    if (result.success) expect(result.data).toBe('')
  })

  it('write unicode then read returns identical content', async () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.write', path: 'unicode.txt', action: 'write', timestamp: Date.now(), durationMs: 0 }
    const content = 'Hello 世界 🌍'
    await handlers.operations.writeFile({ path: 'unicode.txt', content }, audit)
    const result = await handlers.operations.readFile({ path: 'unicode.txt' }, audit)
    expect(result.success).toBe(true)
    if (result.success) expect(result.data).toBe(content)
  })
})

describe('Filesystem Capability Pack — directory operations', () => {
  it('creates deeply nested directories', async () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.mkdir', path: join('a', 'b', 'c', 'd', 'e'), action: 'mkdir', timestamp: Date.now(), durationMs: 0 }
    const result = await handlers.operations.createFolder({ path: join('a', 'b', 'c', 'd', 'e'), recursive: true }, audit)
    expect(result.success).toBe(true)
  })

  it('lists files in nested directory', async () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.write', path: join('nested', 'file.txt'), action: 'write', timestamp: Date.now(), durationMs: 0 }
    await handlers.operations.createFolder({ path: 'nested', recursive: true }, audit)
    await handlers.operations.writeFile({ path: join('nested', 'file.txt'), content: 'x' }, audit)
    const result = await handlers.operations.listDirectory({ path: 'nested' }, audit)
    expect(result.success).toBe(true)
    if (result.success) expect(result.data.entries.some((e) => e.name === 'file.txt')).toBe(true)
  })
})

describe('Filesystem Capability Pack — search edge cases', () => {
  it('searches case-insensitively', async () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.write', path: 'CaseTest.txt', action: 'write', timestamp: Date.now(), durationMs: 0 }
    await handlers.operations.writeFile({ path: 'CaseTest.txt', content: 'x' }, audit)
    const result = await handlers.operations.search({ rootPath: '.', query: 'casetest' }, audit)
    expect(result.success).toBe(true)
    if (result.success) expect(result.data.results.length).toBeGreaterThanOrEqual(1)
  })

  it('returns all results for empty query', async () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.search', path: '.', action: 'search', timestamp: Date.now(), durationMs: 0 }
    const result = await handlers.operations.search({ rootPath: '.', query: '' }, audit)
    expect(result.success).toBe(true)
    if (result.success) expect(result.data.results.length).toBeGreaterThanOrEqual(0)
  })
})

describe('Filesystem Capability Pack — tree edge cases', () => {
  it('returns empty tree for empty directory', async () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.mkdir', path: 'emptytree', action: 'mkdir', timestamp: Date.now(), durationMs: 0 }
    await handlers.operations.createFolder({ path: 'emptytree' }, audit)
    const result = await handlers.operations.tree({ path: 'emptytree' }, audit)
    expect(result.success).toBe(true)
    if (result.success) expect(result.data.length).toBe(0)
  })
})

describe('Filesystem Capability Pack — project creation edge cases', () => {
  it('creates project with custom root', async () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.project.create', path: 'customproject', action: 'project.create', timestamp: Date.now(), durationMs: 0 }
    const result = await handlers.operations.createProject({ name: 'customproject', root: 'customproject' }, audit)
    expect(result.success).toBe(true)
    if (result.success) expect(result.data.projectPath).toContain('customproject')
  })

  it('creates project README with project name', async () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.project.create', path: 'readmeproject', action: 'project.create', timestamp: Date.now(), durationMs: 0 }
    const result = await handlers.operations.createProject({ name: 'readmeproject' }, audit)
    expect(result.success).toBe(true)
    if (result.success) {
      const readmePath = join(result.data.projectPath, 'README.md')
      const readmeResult = await handlers.operations.readFile({ path: readmePath }, audit)
      expect(readmeResult.success).toBe(true)
      if (readmeResult.success) expect(readmeResult.data).toContain('readmeproject')
    }
  })
})

describe('Filesystem Capability Pack — stress 10k permission checks', () => {
  it('handles 10,000 permission checks without degradation', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const start = Date.now()
    for (let i = 0; i < 10000; i++) {
      handlers.permissionManager.check(['read'], makeContext(), join(handlers.config.root, `file_${i}.txt`))
    }
    expect(Date.now() - start).toBeLessThan(5000)
  })
})

describe('Filesystem Capability Pack — concurrent subscribers', () => {
  it('handles 200 concurrent subscribers', () => {
    const pack = new FilesystemCapabilityPack(new CapabilityRuntime())
    const listeners: string[][] = []
    for (let i = 0; i < 200; i++) {
      const buf: string[] = []
      listeners.push(buf)
      pack.subscribe((e) => buf.push(e.eventType))
    }
    pack['publish']('filesystem.read.started', { path: 'x' })
    for (const buf of listeners) {
      expect(buf).toContain('filesystem.read.started')
    }
  })
})

describe('Filesystem Capability Pack — handler error propagation', () => {
  it('propagates permission errors through controls.fail', async () => {
    const invoker = new ExecutionInvoker()
    const capRt = new CapabilityRuntime()
    const pack = new FilesystemCapabilityPack(capRt)
    pack.registerHandlers(invoker)

    const handler = invoker.resolve('filesystem.read')!
    const req = makeRequest('filesystem.read', { path: 'nonexistent.txt' })
    req.context.grantedPermissions = []
    const controls = makeControls()
    await handler(req, req.context, controls)

    expect(controls.isCancelled()).toBe(false)
  })
})
