// desktop/src/capabilities/filesystem/filesystem-capability.ts
//
// Milestone 2.0 — Filesystem Capability Pack.
//
// Implements ICapabilityPack. Registers 12 filesystem capability descriptors
// with the Capability Runtime and 12 handlers with the Execution Invoker.
// Emits filesystem-specific events through its own event bus.
//
// This pack is completely isolated. It does not import the drawing layer,
// the body layer, concrete avatars, the character projection, the animation
// engine, frame snapshots, the desktop shell, any GPU/3D engine, or the
// Emotion/Behaviour/Presence/Character/body-layer runtimes.

import type { ICapabilityRuntime } from '../../runtime/capability'
import type { IExecutionInvoker, ExecutionHandler, ExecutionRollback } from '../../runtime/execution'
import type { ICapabilityPack, CapabilitySchema } from './filesystem-types'
import { createFilesystemHandlers, handleRead, handleWrite, handleDelete, handleCreateFolder, handleRename, handleMove, handleCopy, handleListDirectory, handleMetadata, handleExists, handleSearch, handleTree, handleCreateProject } from './filesystem-handler'
import type { FilesystemHandlerContext } from './filesystem-handler'

const FILESYSTEM_CAPABILITIES: Array<{
  id: string
  name: string
  description: string
  category: 'filesystem'
  permissions: string[]
  inputSchema: CapabilitySchema
  outputSchema: CapabilitySchema
  latencyEstimateMs: number
  location: 'local'
}> = [
  {
    id: 'filesystem.read',
    name: 'Read File',
    description: 'Read a file from the workspace',
    category: 'filesystem',
    permissions: ['filesystem:read'],
    inputSchema: { type: 'object', properties: { path: { type: 'string' }, encoding: { type: 'string' } }, required: ['path'] },
    outputSchema: { type: 'object', properties: { content: { type: 'string' } } },
    latencyEstimateMs: 10,
    location: 'local'
  },
  {
    id: 'filesystem.write',
    name: 'Write File',
    description: 'Write content to a file in the workspace',
    category: 'filesystem',
    permissions: ['filesystem:write'],
    inputSchema: { type: 'object', properties: { path: { type: 'string' }, content: { type: 'string' }, encoding: { type: 'string' }, append: { type: 'boolean' } }, required: ['path', 'content'] },
    outputSchema: { type: 'object', properties: {} },
    latencyEstimateMs: 20,
    location: 'local'
  },
  {
    id: 'filesystem.copy',
    name: 'Copy File',
    description: 'Copy a file within the workspace',
    category: 'filesystem',
    permissions: ['filesystem:read', 'filesystem:write'],
    inputSchema: { type: 'object', properties: { sourcePath: { type: 'string' }, destinationPath: { type: 'string' } }, required: ['sourcePath', 'destinationPath'] },
    outputSchema: { type: 'object', properties: {} },
    latencyEstimateMs: 30,
    location: 'local'
  },
  {
    id: 'filesystem.move',
    name: 'Move File',
    description: 'Move a file within the workspace',
    category: 'filesystem',
    permissions: ['filesystem:read', 'filesystem:write', 'filesystem:delete'],
    inputSchema: { type: 'object', properties: { sourcePath: { type: 'string' }, destinationPath: { type: 'string' } }, required: ['sourcePath', 'destinationPath'] },
    outputSchema: { type: 'object', properties: {} },
    latencyEstimateMs: 30,
    location: 'local'
  },
  {
    id: 'filesystem.rename',
    name: 'Rename File',
    description: 'Rename a file within the workspace',
    category: 'filesystem',
    permissions: ['filesystem:write', 'filesystem:delete'],
    inputSchema: { type: 'object', properties: { oldPath: { type: 'string' }, newPath: { type: 'string' } }, required: ['oldPath', 'newPath'] },
    outputSchema: { type: 'object', properties: {} },
    latencyEstimateMs: 20,
    location: 'local'
  },
  {
    id: 'filesystem.delete',
    name: 'Delete File',
    description: 'Move a file to the recycle bin / trash',
    category: 'filesystem',
    permissions: ['filesystem:delete'],
    inputSchema: { type: 'object', properties: { path: { type: 'string' } }, required: ['path'] },
    outputSchema: { type: 'object', properties: { trashedPath: { type: 'string' } } },
    latencyEstimateMs: 50,
    location: 'local'
  },
  {
    id: 'filesystem.mkdir',
    name: 'Create Folder',
    description: 'Create a directory in the workspace',
    category: 'filesystem',
    permissions: ['filesystem:write'],
    inputSchema: { type: 'object', properties: { path: { type: 'string' }, recursive: { type: 'boolean' } }, required: ['path'] },
    outputSchema: { type: 'object', properties: {} },
    latencyEstimateMs: 15,
    location: 'local'
  },
  {
    id: 'filesystem.listdir',
    name: 'List Directory',
    description: 'List contents of a directory',
    category: 'filesystem',
    permissions: ['filesystem:read'],
    inputSchema: { type: 'object', properties: { path: { type: 'string' } }, required: ['path'] },
    outputSchema: { type: 'object', properties: { entries: { type: 'array' }, total: { type: 'number' } } },
    latencyEstimateMs: 20,
    location: 'local'
  },
  {
    id: 'filesystem.search',
    name: 'Search Files',
    description: 'Search for files by name within the workspace',
    category: 'filesystem',
    permissions: ['filesystem:read'],
    inputSchema: { type: 'object', properties: { rootPath: { type: 'string' }, query: { type: 'string' }, maxResults: { type: 'number' } }, required: ['rootPath', 'query'] },
    outputSchema: { type: 'object', properties: { results: { type: 'array' }, total: { type: 'number' } } },
    latencyEstimateMs: 100,
    location: 'local'
  },
  {
    id: 'filesystem.metadata',
    name: 'File Metadata',
    description: 'Get metadata for a file or directory',
    category: 'filesystem',
    permissions: ['filesystem:read'],
    inputSchema: { type: 'object', properties: { path: { type: 'string' } }, required: ['path'] },
    outputSchema: { type: 'object', properties: { name: { type: 'string' }, size: { type: 'number' }, isDirectory: { type: 'boolean' } } },
    latencyEstimateMs: 10,
    location: 'local'
  },
  {
    id: 'filesystem.exists',
    name: 'Exists',
    description: 'Check if a file or directory exists',
    category: 'filesystem',
    permissions: ['filesystem:read'],
    inputSchema: { type: 'object', properties: { path: { type: 'string' } }, required: ['path'] },
    outputSchema: { type: 'object', properties: { exists: { type: 'boolean' } } },
    latencyEstimateMs: 5,
    location: 'local'
  },
  {
    id: 'filesystem.project.create',
    name: 'Create Project',
    description: 'Create a new project structure in the workspace',
    category: 'filesystem',
    permissions: ['filesystem:write'],
    inputSchema: { type: 'object', properties: { name: { type: 'string' }, template: { type: 'string' }, root: { type: 'string' } }, required: ['name'] },
    outputSchema: { type: 'object', properties: { projectPath: { type: 'string' } } },
    latencyEstimateMs: 50,
    location: 'local'
  }
]

export interface FilesystemMetrics {
  operationsExecuted: number
  searchCount: number
  readCount: number
  writeCount: number
  deleteCount: number
  renameCount: number
  moveCount: number
  copyCount: number
  mkdirCount: number
  listdirCount: number
  metadataCount: number
  existsCount: number
  projectCreateCount: number
}

export const DEFAULT_FILESYSTEM_METRICS: FilesystemMetrics = {
  operationsExecuted: 0,
  searchCount: 0,
  readCount: 0,
  writeCount: 0,
  deleteCount: 0,
  renameCount: 0,
  moveCount: 0,
  copyCount: 0,
  mkdirCount: 0,
  listdirCount: 0,
  metadataCount: 0,
  existsCount: 0,
  projectCreateCount: 0
}

export class FilesystemCapabilityPack implements ICapabilityPack {
  private readonly subscribers = new Set<(event: { eventType: string; data: Record<string, unknown> }) => void>()
  private readonly metrics: FilesystemMetrics = { ...DEFAULT_FILESYSTEM_METRICS }

  constructor(private readonly capabilityRuntime: ICapabilityRuntime) {}

  getMetrics(): FilesystemMetrics {
    return { ...this.metrics }
  }

  recordOperation(capabilityId: string): void {
    this.metrics.operationsExecuted += 1
    if (capabilityId.includes('search')) this.metrics.searchCount += 1
    else if (capabilityId.includes('read')) this.metrics.readCount += 1
    else if (capabilityId.includes('write')) this.metrics.writeCount += 1
    else if (capabilityId.includes('delete')) this.metrics.deleteCount += 1
    else if (capabilityId.includes('rename')) this.metrics.renameCount += 1
    else if (capabilityId.includes('move')) this.metrics.moveCount += 1
    else if (capabilityId.includes('copy')) this.metrics.copyCount += 1
    else if (capabilityId.includes('mkdir')) this.metrics.mkdirCount += 1
    else if (capabilityId.includes('listdir')) this.metrics.listdirCount += 1
    else if (capabilityId.includes('metadata')) this.metrics.metadataCount += 1
    else if (capabilityId.includes('exists')) this.metrics.existsCount += 1
    else if (capabilityId.includes('project.create')) this.metrics.projectCreateCount += 1
  }

  registerHandlers(invoker: IExecutionInvoker): void {
    const emit = (eventType: string, data: Record<string, unknown>) => {
      this.publish(eventType, data)
    }
    const ctx = createFilesystemHandlers(emit, (capabilityId) => this.recordOperation(capabilityId))

    invoker.register('filesystem.read', wrapHandler(ctx, handleRead(ctx)))
    invoker.register('filesystem.write', wrapHandler(ctx, handleWrite(ctx)))
    invoker.register('filesystem.copy', wrapHandler(ctx, handleCopy(ctx)))
    invoker.register('filesystem.move', wrapHandler(ctx, handleMove(ctx)))
    invoker.register('filesystem.rename', wrapHandler(ctx, handleRename(ctx)))
    invoker.register('filesystem.delete', wrapHandler(ctx, handleDelete(ctx)))
    invoker.register('filesystem.mkdir', wrapHandler(ctx, handleCreateFolder(ctx)))
    invoker.register('filesystem.listdir', wrapHandler(ctx, handleListDirectory(ctx)))
    invoker.register('filesystem.search', wrapHandler(ctx, handleSearch(ctx)))
    invoker.register('filesystem.metadata', wrapHandler(ctx, handleMetadata(ctx)))
    invoker.register('filesystem.exists', wrapHandler(ctx, handleExists(ctx)))
    invoker.register('filesystem.project.create', wrapHandler(ctx, handleCreateProject(ctx)))
  }

  registerDescriptors(capabilityRuntime: ICapabilityRuntime): void {
    for (const cap of FILESYSTEM_CAPABILITIES) {
      capabilityRuntime.register({
        id: cap.id,
        name: cap.name,
        description: cap.description,
        category: cap.category,
        permissions: cap.permissions as any,
        inputSchema: cap.inputSchema,
        outputSchema: cap.outputSchema,
        availability: 'available',
        latencyEstimateMs: cap.latencyEstimateMs,
        location: cap.location,
        cost: 0,
        enabled: true,
        source: 'filesystem-pack',
        tags: ['filesystem', 'sandboxed']
      })
    }
  }

  subscribe(listener: (event: { eventType: string; data: Record<string, unknown> }) => void): () => void {
    this.subscribers.add(listener)
    return () => { this.subscribers.delete(listener) }
  }

  private publish(eventType: string, data: Record<string, unknown>): void {
    for (const listener of this.subscribers) {
      try { listener({ eventType, data }) } catch { /* subscriber errors must not break operations */ }
    }
  }
}

function wrapHandler(ctx: FilesystemHandlerContext, handler: ExecutionHandler): ExecutionHandler {
  return (req, c, controls) => {
    const result = handler(req, c, controls)
    if (result && typeof result.then === 'function') {
      return result.then((res) => {
        ctx.recordOperation(req.capabilityId)
        return res
      }).catch(() => {
        // failed executions still count toward metrics for observability
        ctx.recordOperation(req.capabilityId)
      })
    }
    ctx.recordOperation(req.capabilityId)
    return result
  }
}

export function buildFilesystemRollback(): ExecutionRollback {
  return (_req, _ctx) => {
    // Rollback for filesystem operations is handled by the trash layer;
    // permanent rollback is intentionally not supported.
  }
}
