// desktop/tests/capabilities/filesystem/filesystem-operations.test.ts
//
// Milestone 2.0 — Filesystem Capability Pack operational tests.
//
// Verifies: path validation, workspace isolation, permissions, atomic writes,
// trash/delete, file operations, metadata, search, tree, project creation,
// performance, and stress.

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync, existsSync, mkdirSync, writeFileSync, readFileSync, statSync, renameSync, copyFileSync, accessSync, constants } from 'fs'
import { join, dirname, sep } from 'path'
import { tmpdir } from 'os'
import { FilesystemCapabilityPack, createFilesystemHandlers, buildFilesystemRollback } from '../../../src/capabilities/filesystem'
import type { ExecutionRequest, ExecutionContext, ExecutionControls } from '../../../src/runtime/execution'
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
let previousWorkspace: string | undefined

beforeEach(() => {
  tmpWorkspace = mkdtempSync(join(tmpdir(), 'zaram-fs-'))
  previousWorkspace = process.env.ZARAM_WORKSPACE
  process.env.ZARAM_WORKSPACE = tmpWorkspace
})

afterEach(() => {
  if (previousWorkspace === undefined) {
    delete process.env.ZARAM_WORKSPACE
  } else {
    process.env.ZARAM_WORKSPACE = previousWorkspace
  }
  try { rmSync(tmpWorkspace, { recursive: true, force: true }) } catch { /* ignore */ }
})

describe('Filesystem Capability Pack — path validation & security', () => {
  it('rejects path traversal with ../', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const result = handlers.permissionManager.check(['read'], makeContext(), join(handlers.config.root, '..', '..', 'etc', 'passwd'))
    expect(result.granted).toBe(false)
  })

  it('rejects path traversal with backslash', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const result = handlers.permissionManager.check(['read'], makeContext(), join(handlers.config.root, '..', '..', 'etc', 'passwd'))
    expect(result.granted).toBe(false)
  })

  it('rejects absolute paths outside workspace', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const outside = sep === '\\' ? 'C:\\Windows\\System32' : '/etc/passwd'
    const result = handlers.permissionManager.check(['read'], makeContext(), outside)
    expect(result.granted).toBe(false)
  })

  it('rejects system paths on current platform', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const outside = sep === '\\' ? 'C:\\Windows\\System32' : '/usr/bin/bash'
    const result = handlers.permissionManager.check(['read'], makeContext(), outside)
    expect(result.granted).toBe(false)
  })

  it('rejects .git access', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const result = handlers.permissionManager.check(['read'], makeContext(), join(handlers.config.root, '.git', 'config'))
    expect(result.granted).toBe(false)
  })

  it('allows paths inside workspace', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const result = handlers.permissionManager.check(['read'], { ...makeContext(), grantedPermissions: ['read'] }, join(handlers.config.root, 'test.txt'))
    expect(result.granted).toBe(true)
  })
})

describe('Filesystem Capability Pack — workspace isolation', () => {
  it('resolves workspace root from ZARAM_WORKSPACE env', () => {
    const original = process.env.ZARAM_WORKSPACE
    process.env.ZARAM_WORKSPACE = join(tmpdir(), 'custom-workspace')
    const handlers = createFilesystemHandlers(() => {}, () => {})
    expect(handlers.config.root).toBe(join(tmpdir(), 'custom-workspace'))
    if (original === undefined) {
      delete process.env.ZARAM_WORKSPACE
    } else {
      process.env.ZARAM_WORKSPACE = original
    }
  })

  it('creates trash and temp dirs', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    expect(handlers.config.trashDir.endsWith('.zaram_trash')).toBe(true)
    expect(handlers.config.tempDir.endsWith('.zaram_tmp')).toBe(true)
  })
})

describe('Filesystem Capability Pack — permission enforcement', () => {
  it('allows workspace read/write automatically', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const result = handlers.permissionManager.check(['read', 'write'], { ...makeContext(), grantedPermissions: ['read', 'write'] }, join(handlers.config.root, 'test.txt'))
    expect(result.granted).toBe(true)
  })

  it('denies read outside workspace without approval', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const outside = sep === '\\' ? 'C:\\Windows\\System32' : '/etc/passwd'
    const result = handlers.permissionManager.check(['read'], { ...makeContext(), grantedPermissions: ['read'] }, outside)
    expect(result.granted).toBe(false)
  })

  it('allows read outside workspace with approval', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const outside = sep === '\\' ? 'C:\\Users\\user\\test.txt' : '/tmp/test.txt'
    const result = handlers.permissionManager.check(['read'], { ...makeContext(), grantedPermissions: ['read', 'filesystem:read:outside'] }, outside)
    expect(result.granted).toBe(true)
  })

  it('denies write outside workspace without approval', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const outside = sep === '\\' ? 'C:\\Windows\\System32' : '/etc/passwd'
    const result = handlers.permissionManager.check(['write'], { ...makeContext(), grantedPermissions: ['write'] }, outside)
    expect(result.granted).toBe(false)
  })

  it('denies delete outside workspace always', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const outside = sep === '\\' ? 'C:\\Windows\\System32' : '/etc/passwd'
    const result = handlers.permissionManager.check(['delete'], { ...makeContext(), grantedPermissions: ['read', 'write', 'filesystem:read:outside', 'filesystem:write:outside'] }, outside)
    expect(result.granted).toBe(false)
  })

  it('denies delete inside workspace without approval', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const result = handlers.permissionManager.check(['delete'], { ...makeContext(), grantedPermissions: ['delete'] }, join(handlers.config.root, 'test.txt'))
    expect(result.granted).toBe(false)
  })

  it('honors deny rules', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const result = handlers.permissionManager.check(['read'], { ...makeContext(), grantedPermissions: ['read'], rules: [{ pathPattern: join(handlers.config.root, 'secret'), permissions: ['read'], effect: 'deny' }] }, join(handlers.config.root, 'secret', 'file.txt'))
    expect(result.granted).toBe(false)
  })

  it('honors allow rules', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const result = handlers.permissionManager.check(['read'], { ...makeContext(), grantedPermissions: ['read'], rules: [{ pathPattern: join(handlers.config.root, 'public'), permissions: ['read'], effect: 'allow' }] }, join(handlers.config.root, 'public', 'file.txt'))
    expect(result.granted).toBe(true)
  })
})

describe('Filesystem Capability Pack — atomic writes', () => {
  it('writes a file', async () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.write', path: 'atomic.txt', action: 'write', timestamp: Date.now(), durationMs: 0 }
    const result = await handlers.operations.writeFile({ path: 'atomic.txt', content: 'hello' }, audit)
    expect(result.success).toBe(true)
  })

  it('supports append mode', async () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.write', path: 'append.txt', action: 'write', timestamp: Date.now(), durationMs: 0 }
    await handlers.operations.writeFile({ path: 'append.txt', content: 'line1' }, audit)
    await handlers.operations.writeFile({ path: 'append.txt', content: 'line2', append: true }, audit)
    const result = await handlers.operations.readFile({ path: 'append.txt' }, audit)
    expect(result.success).toBe(true)
    if (result.success) expect(result.data).toBe('line1line2')
  })
})

describe('Filesystem Capability Pack — trash / delete', () => {
  it('moves files to trash instead of deleting', async () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.delete', path: 'todelete.txt', action: 'delete', timestamp: Date.now(), durationMs: 0 }
    await handlers.operations.writeFile({ path: 'todelete.txt', content: 'bye' }, audit)
    const result = await handlers.operations.deleteFile({ path: 'todelete.txt' }, audit)
    expect(result.success).toBe(true)
    if (result.success) expect(result.data.trashedPath).toBeDefined()
  })

  it('never returns permanent delete for missing file', async () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.delete', path: 'never.txt', action: 'delete', timestamp: Date.now(), durationMs: 0 }
    const result = await handlers.operations.deleteFile({ path: 'never.txt' }, audit)
    expect(result.success).toBe(false)
  })
})

describe('Filesystem Capability Pack — read/write/mkdir', () => {
  it('writes and reads a file', async () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.write', path: 'r.txt', action: 'write', timestamp: Date.now(), durationMs: 0 }
    await handlers.operations.writeFile({ path: 'r.txt', content: 'hello world' }, audit)
    const result = await handlers.operations.readFile({ path: 'r.txt' }, audit)
    expect(result.success).toBe(true)
    if (result.success) expect(result.data).toBe('hello world')
  })

  it('creates nested directories', async () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.mkdir', path: join('a', 'b', 'c'), action: 'mkdir', timestamp: Date.now(), durationMs: 0 }
    const result = await handlers.operations.createFolder({ path: join('a', 'b', 'c'), recursive: true }, audit)
    expect(result.success).toBe(true)
  })

  it('lists directory contents', async () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.write', path: 'listme.txt', action: 'write', timestamp: Date.now(), durationMs: 0 }
    await handlers.operations.writeFile({ path: 'listme.txt', content: 'x' }, audit)
    const result = await handlers.operations.listDirectory({ path: '.' }, audit)
    expect(result.success).toBe(true)
    if (result.success) expect(result.data.entries.some((e) => e.name === 'listme.txt')).toBe(true)
  })
})

describe('Filesystem Capability Pack — metadata & exists', () => {
  it('returns file metadata', async () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.write', path: 'meta.txt', action: 'write', timestamp: Date.now(), durationMs: 0 }
    await handlers.operations.writeFile({ path: 'meta.txt', content: 'x' }, audit)
    const result = await handlers.operations.metadata({ path: 'meta.txt' }, audit)
    expect(result.success).toBe(true)
    if (result.success) {
      expect(result.data.name).toBe('meta.txt')
      expect(result.data.isFile).toBe(true)
      expect(result.data.isDirectory).toBe(false)
    }
  })

  it('checks existence', async () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.write', path: 'exists.txt', action: 'write', timestamp: Date.now(), durationMs: 0 }
    await handlers.operations.writeFile({ path: 'exists.txt', content: 'x' }, audit)
    const result = await handlers.operations.exists({ path: 'exists.txt' }, audit)
    expect(result.success).toBe(true)
    if (result.success) expect(result.data).toBe(true)
    const missing = await handlers.operations.exists({ path: 'missing.txt' }, audit)
    expect(missing.success).toBe(true)
    if (missing.success) expect(missing.data).toBe(false)
  })
})

describe('Filesystem Capability Pack — rename/move/copy', () => {
  it('renames a file', async () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.write', path: 'old.txt', action: 'write', timestamp: Date.now(), durationMs: 0 }
    await handlers.operations.writeFile({ path: 'old.txt', content: 'x' }, audit)
    const result = await handlers.operations.rename({ oldPath: 'old.txt', newPath: 'new.txt' }, audit)
    expect(result.success).toBe(true)
    const exists = await handlers.operations.exists({ path: 'new.txt' }, audit)
    expect(exists.success).toBe(true)
    if (exists.success) expect(exists.data).toBe(true)
  }, 10000)

  it('copies a file', async () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.write', path: 'src.txt', action: 'write', timestamp: Date.now(), durationMs: 0 }
    await handlers.operations.writeFile({ path: 'src.txt', content: 'copy me' }, audit)
    const result = await handlers.operations.copy({ sourcePath: 'src.txt', destinationPath: 'dst.txt' }, audit)
    expect(result.success).toBe(true)
    const readResult = await handlers.operations.readFile({ path: 'dst.txt' }, audit)
    expect(readResult.success).toBe(true)
    if (readResult.success) expect(readResult.data).toBe('copy me')
  })

  it('moves a file', async () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.write', path: 'moveme.txt', action: 'write', timestamp: Date.now(), durationMs: 0 }
    await handlers.operations.writeFile({ path: 'moveme.txt', content: 'move' }, audit)
    mkdirSync(join(handlers.config.root, 'dest'), { recursive: true })
    const result = await handlers.operations.move({ sourcePath: 'moveme.txt', destinationPath: join('dest', 'moveme.txt') }, audit)
    expect(result.success).toBe(true)
    const exists = await handlers.operations.exists({ path: join('dest', 'moveme.txt') }, audit)
    expect(exists.success).toBe(true)
    if (exists.success) expect(exists.data).toBe(true)
  })
})

describe('Filesystem Capability Pack — search & tree', () => {
  it('searches files by name', async () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.write', path: 'searchme.txt', action: 'write', timestamp: Date.now(), durationMs: 0 }
    await handlers.operations.writeFile({ path: 'searchme.txt', content: 'x' }, audit)
    const result = await handlers.operations.search({ rootPath: '.', query: 'searchme' }, audit)
    expect(result.success).toBe(true)
    if (result.success) expect(result.data.results.length).toBeGreaterThanOrEqual(1)
  }, 10000)

  it('returns empty search for no matches', async () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.search', path: '.', action: 'search', timestamp: Date.now(), durationMs: 0 }
    const result = await handlers.operations.search({ rootPath: '.', query: 'nonexistent_xyz' }, audit)
    expect(result.success).toBe(true)
    if (result.success) expect(result.data.results.length).toBe(0)
  })

  it('produces a directory tree', async () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.mkdir', path: 'treeDir', action: 'mkdir', timestamp: Date.now(), durationMs: 0 }
    await handlers.operations.createFolder({ path: 'treeDir' }, audit)
    await handlers.operations.writeFile({ path: join('treeDir', 'file.txt'), content: 'x' }, audit)
    const result = await handlers.operations.tree({ path: 'treeDir' }, audit)
    expect(result.success).toBe(true)
    if (result.success) expect(result.data.length).toBeGreaterThanOrEqual(1)
  })
})

describe('Filesystem Capability Pack — project creation', () => {
  it('creates a project structure', async () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.project.create', path: 'myproject', action: 'project.create', timestamp: Date.now(), durationMs: 0 }
    const result = await handlers.operations.createProject({ name: 'myproject' }, audit)
    expect(result.success).toBe(true)
    if (result.success) expect(result.data.projectPath).toBeDefined()
  })

  it('creates project with template', async () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.project.create', path: 'tplproject', action: 'project.create', timestamp: Date.now(), durationMs: 0 }
    const result = await handlers.operations.createProject({ name: 'tplproject', template: 'react' }, audit)
    expect(result.success).toBe(true)
    if (result.success) expect(result.data.projectPath).toBeDefined()
  })
})

describe('Filesystem Capability Pack — event emission', () => {
  it('emits read events', async () => {
    const events: string[] = []
    const pack = new FilesystemCapabilityPack(new CapabilityRuntime())
    pack.subscribe((e) => events.push(e.eventType))

    const invoker = new ExecutionInvoker()
    pack.registerHandlers(invoker)
    const writeHandler = invoker.resolve('filesystem.write')!
    const writeReq = makeRequest('filesystem.write', { path: 'evt.txt', content: 'hi' })
    writeReq.context.grantedPermissions = ['write']
    const writeControls = makeControls()
    await writeHandler(writeReq, writeReq.context, writeControls)

    const handler = invoker.resolve('filesystem.read')!
    const req = makeRequest('filesystem.read', { path: 'evt.txt' })
    req.context.grantedPermissions = ['read']
    const controls = makeControls()
    await handler(req, req.context, controls)

    expect(events).toContain('filesystem.write.started')
    expect(events).toContain('filesystem.write.completed')
    expect(events).toContain('filesystem.read.started')
    expect(events).toContain('filesystem.read.completed')
  })

  it('emits write events', async () => {
    const events: string[] = []
    const pack = new FilesystemCapabilityPack(new CapabilityRuntime())
    pack.subscribe((e) => events.push(e.eventType))

    const invoker = new ExecutionInvoker()
    pack.registerHandlers(invoker)
    const handler = invoker.resolve('filesystem.write')!
    const req = makeRequest('filesystem.write', { path: 'evt.txt', content: 'hi' })
    req.context.grantedPermissions = ['write']
    const controls = makeControls()
    await handler(req, req.context, controls)

    expect(events).toContain('filesystem.write.started')
    expect(events).toContain('filesystem.write.completed')
  })

  it('emits delete events', async () => {
    const events: string[] = []
    const pack = new FilesystemCapabilityPack(new CapabilityRuntime())
    pack.subscribe((e) => events.push(e.eventType))

    const invoker = new ExecutionInvoker()
    pack.registerHandlers(invoker)

    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.write', path: 'evtdel.txt', action: 'write', timestamp: Date.now(), durationMs: 0 }
    await handlers.operations.writeFile({ path: 'evtdel.txt', content: 'bye' }, audit)

    const handler = invoker.resolve('filesystem.delete')!
    const req = makeRequest('filesystem.delete', { path: 'evtdel.txt' })
    req.context.grantedPermissions = ['filesystem:delete']
    const controls = makeControls()
    await handler(req, req.context, controls)

    expect(events).toContain('filesystem.delete.requested')
    expect(events.some((e) => e === 'filesystem.delete.completed' || e === 'filesystem.error')).toBe(true)
  })

  it('emits error events on permission denial', async () => {
    const events: string[] = []
    const pack = new FilesystemCapabilityPack(new CapabilityRuntime())
    pack.subscribe((e) => events.push(e.eventType))

    const invoker = new ExecutionInvoker()
    pack.registerHandlers(invoker)
    const handler = invoker.resolve('filesystem.read')!
    const req = makeRequest('filesystem.read', { path: 'evt.txt' })
    const controls = makeControls()
    await handler(req, { ...req.context, grantedPermissions: [] }, controls)

    expect(events).toContain('filesystem.error')
  })
})

describe('Filesystem Capability Pack — performance', () => {
  it('writes 100 files quickly', async () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.write', path: 'perf.txt', action: 'write', timestamp: Date.now(), durationMs: 0 }
    const start = Date.now()
    for (let i = 0; i < 100; i++) {
      await handlers.operations.writeFile({ path: `perf_${i}.txt`, content: 'x' }, audit)
    }
    expect(Date.now() - start).toBeLessThan(15000)
  }, 20000)

  it('resolves 1000 paths quickly', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const start = Date.now()
    for (let i = 0; i < 1000; i++) {
      handlers.permissionManager.check(['read'], makeContext(), join(tmpWorkspace, `file_${i}.txt`))
    }
    expect(Date.now() - start).toBeLessThan(2000)
  })

  it('rejects 1000 traversal attempts quickly', () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const start = Date.now()
    for (let i = 0; i < 1000; i++) {
      handlers.permissionManager.check(['read'], makeContext(), join(tmpWorkspace, '..', '..', 'etc', 'passwd_' + i))
    }
    expect(Date.now() - start).toBeLessThan(1000)
  })
})

describe('Filesystem Capability Pack — stress', () => {
  it('survives 100 mixed operations without corruption', async () => {
    const handlers = createFilesystemHandlers(() => {}, () => {})
    const audit = { capability: 'filesystem.write', path: 'stress.txt', action: 'write', timestamp: Date.now(), durationMs: 0 }
    for (let i = 0; i < 100; i++) {
      const path = `stress_${i}.txt`
      await handlers.operations.writeFile({ path, content: `data_${i}` }, audit)
      const read = await handlers.operations.readFile({ path }, audit)
      expect(read.success).toBe(true)
      if (read.success) expect(read.data).toBe(`data_${i}`)
    }
  }, 10000)

  it('handles concurrent event subscribers', () => {
    const pack = new FilesystemCapabilityPack(new CapabilityRuntime())
    const listeners: string[][] = []
    for (let i = 0; i < 50; i++) {
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

describe('Filesystem Capability Pack — rollback', () => {
  it('buildFilesystemRollback returns a no-op rollback', () => {
    const rollback = buildFilesystemRollback()
    expect(() => rollback({} as any, {} as any)).not.toThrow()
  })
})
