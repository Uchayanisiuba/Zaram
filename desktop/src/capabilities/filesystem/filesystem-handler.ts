// desktop/src/capabilities/filesystem/filesystem-handler.ts
//
// Milestone 2.0 — Filesystem ExecutionHandler implementations.
//
// Each handler receives an ExecutionRequest, validates through the security
// and permission layers, delegates to FileSystemOperations, and reports
// progress/audit/events through controls.

import type { ExecutionRequest, ExecutionContext, ExecutionControls, ExecutionHandler, ExecutionRollback } from '../../runtime/execution'
import type { FileSystemResult, FileSystemAudit } from './filesystem-types'
import { FileSystemPermissionManager } from './filesystem-permissions'
import { validatePathSecurity, assertPathSafe } from './filesystem-security'
import { createFileSystemOperations, type FileSystemOperations } from './filesystem-operations'
import type { WorkspaceConfig } from './filesystem-paths'
import { buildWorkspaceConfig } from './filesystem-paths'

export interface FilesystemHandlerContext {
  config: WorkspaceConfig
  operations: FileSystemOperations
  permissionManager: FileSystemPermissionManager
  emit: (eventType: string, data: Record<string, unknown>) => void
  recordOperation: (capabilityId: string) => void
}

export function createFilesystemHandlers(emit: (eventType: string, data: Record<string, unknown>) => void, recordOperation: (capabilityId: string) => void): FilesystemHandlerContext {
  const config = buildWorkspaceConfig()
  const operations = createFileSystemOperations(config)
  const permissionManager = new FileSystemPermissionManager(config.root)
  return { config, operations, permissionManager, emit, recordOperation }
}

export function buildAudit(request: ExecutionRequest, action: string): FileSystemAudit {
  return {
    capability: request.capabilityId,
    path: typeof request.input === 'object' && request.input !== null && 'path' in request.input ? String((request.input as Record<string, unknown>).path) : '',
    action,
    timestamp: Date.now(),
    durationMs: 0,
    actor: request.context.actor,
    correlationId: request.context.correlationId
  }
}

function finishAudit(audit: FileSystemAudit): FileSystemAudit {
  audit.durationMs = Date.now() - audit.timestamp
  return audit
}

async function resolveInputPath(input: { path?: string }, workspaceRoot: string): Promise<{ resolved: string } | { error: { code: string; message: string } }> {
  if (!input.path) {
    return { error: { code: 'validation_error', message: 'path is required' } }
  }
  try {
    const resolved = assertPathSafe(input.path, workspaceRoot)
    return { resolved }
  } catch (error) {
    return { error: { code: 'security_error', message: String(error) } }
  }
}

function checkPermission(
  permissionManager: FileSystemPermissionManager,
  required: string[],
  context: ExecutionContext,
  resolved: string
): { granted: boolean; reason?: string } {
  return permissionManager.check(required as any, context, resolved)
}

export function handleRead(ctx: FilesystemHandlerContext): ExecutionHandler {
  return async (request, _context, controls) => {
    const input = request.input as { path?: string; encoding?: BufferEncoding }
    const resolvedInput = await resolveInputPath(input, ctx.config.root)
    if ('error' in resolvedInput) {
      controls.fail({ code: resolvedInput.error.code, message: resolvedInput.error.message, attempt: 1 })
      return
    }
    const permResult = checkPermission(ctx.permissionManager, ['read'], request.context, resolvedInput.resolved)
    if (!permResult.granted) {
      ctx.emit('filesystem.error', { path: input.path, error: permResult.reason })
      controls.fail({ code: 'permission_denied', message: permResult.reason ?? 'Permission denied', attempt: 1 })
      return
    }

    ctx.emit('filesystem.read.started', { path: input.path })
    controls.reportProgress(0.1)

    try {
      const audit = finishAudit(buildAudit(request, 'read'))
      const result = await ctx.operations.readFile({ path: input.path!, encoding: input.encoding }, audit)

      if (result.success) {
        controls.reportProgress(1)
        ctx.emit('filesystem.read.completed', { path: input.path })
        controls.succeed(result.data)
      } else {
        ctx.emit('filesystem.error', { path: input.path, error: result.error })
        controls.fail({ code: result.error.code, message: result.error.message, attempt: 1 })
      }
    } catch (error) {
      ctx.emit('filesystem.error', { path: input.path, error: String(error) })
      controls.fail({ code: 'security_error', message: String(error), attempt: 1 })
    }
  }
}

export function handleWrite(ctx: FilesystemHandlerContext): ExecutionHandler {
  return async (request, _context, controls) => {
    const input = request.input as { path?: string; content?: string; encoding?: BufferEncoding; append?: boolean }
    if (!input.path) {
      controls.fail({ code: 'validation_error', message: 'path is required', attempt: 1 })
      return
    }

    ctx.emit('filesystem.write.started', { path: input.path })
    controls.reportProgress(0.1)

    try {
      const resolved = assertPathSafe(input.path, ctx.config.root)
      const permResult = checkPermission(ctx.permissionManager, ['write'], request.context, resolved)
      if (!permResult.granted) {
        ctx.emit('filesystem.error', { path: input.path, error: permResult.reason })
        controls.fail({ code: 'permission_denied', message: permResult.reason ?? 'Permission denied', attempt: 1 })
        return
      }

      const audit = finishAudit(buildAudit(request, 'write'))
      const result = await ctx.operations.writeFile(
        { path: input.path, content: input.content ?? '', encoding: input.encoding, append: input.append },
        audit
      )

      if (result.success) {
        controls.reportProgress(1)
        ctx.emit('filesystem.write.completed', { path: input.path })
        controls.succeed(undefined)
      } else {
        ctx.emit('filesystem.error', { path: input.path, error: result.error })
        controls.fail({ code: result.error.code, message: result.error.message, attempt: 1 })
      }
    } catch (error) {
      ctx.emit('filesystem.error', { path: input.path, error: String(error) })
      controls.fail({ code: 'security_error', message: String(error), attempt: 1 })
    }
  }
}

export function handleDelete(ctx: FilesystemHandlerContext): ExecutionHandler {
  return async (request, _context, controls) => {
    const input = request.input as { path?: string }
    if (!input.path) {
      controls.fail({ code: 'validation_error', message: 'path is required', attempt: 1 })
      return
    }

    ctx.emit('filesystem.delete.requested', { path: input.path })
    controls.reportProgress(0.1)

    try {
      const resolved = assertPathSafe(input.path, ctx.config.root)
      const permResult = checkPermission(ctx.permissionManager, ['delete'], request.context, resolved)
      if (!permResult.granted) {
        ctx.emit('filesystem.error', { path: input.path, error: permResult.reason })
        controls.fail({ code: 'permission_denied', message: permResult.reason ?? 'Permission denied', attempt: 1 })
        return
      }

      const audit = finishAudit(buildAudit(request, 'delete'))
      const result = await ctx.operations.deleteFile({ path: input.path }, audit)

      if (result.success) {
        controls.reportProgress(1)
        ctx.emit('filesystem.delete.completed', { path: input.path })
        controls.succeed(result.data)
      } else {
        ctx.emit('filesystem.error', { path: input.path, error: result.error })
        controls.fail({ code: result.error.code, message: result.error.message, attempt: 1 })
      }
    } catch (error) {
      ctx.emit('filesystem.error', { path: input.path, error: String(error) })
      controls.fail({ code: 'security_error', message: String(error), attempt: 1 })
    }
  }
}

export function handleCreateFolder(ctx: FilesystemHandlerContext): ExecutionHandler {
  return async (request, _context, controls) => {
    const input = request.input as { path?: string; recursive?: boolean }
    if (!input.path) {
      controls.fail({ code: 'validation_error', message: 'path is required', attempt: 1 })
      return
    }

    controls.reportProgress(0.1)

    try {
      const resolved = assertPathSafe(input.path, ctx.config.root)
      const permResult = checkPermission(ctx.permissionManager, ['write'], request.context, resolved)
      if (!permResult.granted) {
        ctx.emit('filesystem.error', { path: input.path, error: permResult.reason })
        controls.fail({ code: 'permission_denied', message: permResult.reason ?? 'Permission denied', attempt: 1 })
        return
      }

      const audit = finishAudit(buildAudit(request, 'mkdir'))
      const result = await ctx.operations.createFolder({ path: input.path, recursive: input.recursive }, audit)

      if (result.success) {
        controls.reportProgress(1)
        controls.succeed(undefined)
      } else {
        ctx.emit('filesystem.error', { path: input.path, error: result.error })
        controls.fail({ code: result.error.code, message: result.error.message, attempt: 1 })
      }
    } catch (error) {
      ctx.emit('filesystem.error', { path: input.path, error: String(error) })
      controls.fail({ code: 'security_error', message: String(error), attempt: 1 })
    }
  }
}

export function handleRename(ctx: FilesystemHandlerContext): ExecutionHandler {
  return async (request, _context, controls) => {
    const input = request.input as { oldPath?: string; newPath?: string }
    if (!input.oldPath || !input.newPath) {
      controls.fail({ code: 'validation_error', message: 'oldPath and newPath are required', attempt: 1 })
      return
    }

    controls.reportProgress(0.1)

    try {
      const oldResolved = assertPathSafe(input.oldPath, ctx.config.root)
      const newResolved = assertPathSafe(input.newPath, ctx.config.root)
      const permResult = checkPermission(ctx.permissionManager, ['write', 'delete'], request.context, oldResolved)
      if (!permResult.granted) {
        ctx.emit('filesystem.error', { path: input.oldPath, error: permResult.reason })
        controls.fail({ code: 'permission_denied', message: permResult.reason ?? 'Permission denied', attempt: 1 })
        return
      }

      const audit = finishAudit(buildAudit(request, 'rename'))
      const result = await ctx.operations.rename({ oldPath: input.oldPath, newPath: input.newPath }, audit)

      if (result.success) {
        controls.reportProgress(1)
        controls.succeed(undefined)
      } else {
        ctx.emit('filesystem.error', { path: input.oldPath, error: result.error })
        controls.fail({ code: result.error.code, message: result.error.message, attempt: 1 })
      }
    } catch (error) {
      ctx.emit('filesystem.error', { path: input.oldPath, error: String(error) })
      controls.fail({ code: 'security_error', message: String(error), attempt: 1 })
    }
  }
}

export function handleMove(ctx: FilesystemHandlerContext): ExecutionHandler {
  return async (request, _context, controls) => {
    const input = request.input as { sourcePath?: string; destinationPath?: string }
    if (!input.sourcePath || !input.destinationPath) {
      controls.fail({ code: 'validation_error', message: 'sourcePath and destinationPath are required', attempt: 1 })
      return
    }

    controls.reportProgress(0.1)

    try {
      const sourceResolved = assertPathSafe(input.sourcePath, ctx.config.root)
      const destResolved = assertPathSafe(input.destinationPath, ctx.config.root)
      const permResult = checkPermission(ctx.permissionManager, ['write', 'delete'], request.context, sourceResolved)
      if (!permResult.granted) {
        ctx.emit('filesystem.error', { path: input.sourcePath, error: permResult.reason })
        controls.fail({ code: 'permission_denied', message: permResult.reason ?? 'Permission denied', attempt: 1 })
        return
      }

      const audit = finishAudit(buildAudit(request, 'move'))
      const result = await ctx.operations.move({ sourcePath: input.sourcePath, destinationPath: input.destinationPath }, audit)

      if (result.success) {
        controls.reportProgress(1)
        controls.succeed(undefined)
      } else {
        ctx.emit('filesystem.error', { path: input.sourcePath, error: result.error })
        controls.fail({ code: result.error.code, message: result.error.message, attempt: 1 })
      }
    } catch (error) {
      ctx.emit('filesystem.error', { path: input.sourcePath, error: String(error) })
      controls.fail({ code: 'security_error', message: String(error), attempt: 1 })
    }
  }
}

export function handleCopy(ctx: FilesystemHandlerContext): ExecutionHandler {
  return async (request, _context, controls) => {
    const input = request.input as { sourcePath?: string; destinationPath?: string }
    if (!input.sourcePath || !input.destinationPath) {
      controls.fail({ code: 'validation_error', message: 'sourcePath and destinationPath are required', attempt: 1 })
      return
    }

    controls.reportProgress(0.1)

    try {
      const sourceResolved = assertPathSafe(input.sourcePath, ctx.config.root)
      const destResolved = assertPathSafe(input.destinationPath, ctx.config.root)
      const permResult = checkPermission(ctx.permissionManager, ['read', 'write'], request.context, destResolved)
      if (!permResult.granted) {
        ctx.emit('filesystem.error', { path: input.sourcePath, error: permResult.reason })
        controls.fail({ code: 'permission_denied', message: permResult.reason ?? 'Permission denied', attempt: 1 })
        return
      }

      const audit = finishAudit(buildAudit(request, 'copy'))
      const result = await ctx.operations.copy({ sourcePath: input.sourcePath, destinationPath: input.destinationPath }, audit)

      if (result.success) {
        controls.reportProgress(1)
        controls.succeed(undefined)
      } else {
        ctx.emit('filesystem.error', { path: input.sourcePath, error: result.error })
        controls.fail({ code: result.error.code, message: result.error.message, attempt: 1 })
      }
    } catch (error) {
      ctx.emit('filesystem.error', { path: input.sourcePath, error: String(error) })
      controls.fail({ code: 'security_error', message: String(error), attempt: 1 })
    }
  }
}

export function handleListDirectory(ctx: FilesystemHandlerContext): ExecutionHandler {
  return async (request, _context, controls) => {
    const input = request.input as { path?: string }
    if (!input.path) {
      controls.fail({ code: 'validation_error', message: 'path is required', attempt: 1 })
      return
    }

    controls.reportProgress(0.1)

    try {
      const resolved = assertPathSafe(input.path, ctx.config.root)
      const permResult = checkPermission(ctx.permissionManager, ['read'], request.context, resolved)
      if (!permResult.granted) {
        ctx.emit('filesystem.error', { path: input.path, error: permResult.reason })
        controls.fail({ code: 'permission_denied', message: permResult.reason ?? 'Permission denied', attempt: 1 })
        return
      }

      const audit = finishAudit(buildAudit(request, 'listdir'))
      const result = await ctx.operations.listDirectory({ path: input.path }, audit)

      if (result.success) {
        controls.reportProgress(1)
        controls.succeed(result.data)
      } else {
        ctx.emit('filesystem.error', { path: input.path, error: result.error })
        controls.fail({ code: result.error.code, message: result.error.message, attempt: 1 })
      }
    } catch (error) {
      ctx.emit('filesystem.error', { path: input.path, error: String(error) })
      controls.fail({ code: 'security_error', message: String(error), attempt: 1 })
    }
  }
}

export function handleMetadata(ctx: FilesystemHandlerContext): ExecutionHandler {
  return async (request, _context, controls) => {
    const input = request.input as { path?: string }
    if (!input.path) {
      controls.fail({ code: 'validation_error', message: 'path is required', attempt: 1 })
      return
    }

    controls.reportProgress(0.1)

    try {
      const resolved = assertPathSafe(input.path, ctx.config.root)
      const permResult = checkPermission(ctx.permissionManager, ['read'], request.context, resolved)
      if (!permResult.granted) {
        ctx.emit('filesystem.error', { path: input.path, error: permResult.reason })
        controls.fail({ code: 'permission_denied', message: permResult.reason ?? 'Permission denied', attempt: 1 })
        return
      }

      const audit = finishAudit(buildAudit(request, 'metadata'))
      const result = await ctx.operations.metadata({ path: input.path }, audit)

      if (result.success) {
        controls.reportProgress(1)
        controls.succeed(result.data)
      } else {
        ctx.emit('filesystem.error', { path: input.path, error: result.error })
        controls.fail({ code: result.error.code, message: result.error.message, attempt: 1 })
      }
    } catch (error) {
      ctx.emit('filesystem.error', { path: input.path, error: String(error) })
      controls.fail({ code: 'security_error', message: String(error), attempt: 1 })
    }
  }
}

export function handleExists(ctx: FilesystemHandlerContext): ExecutionHandler {
  return async (request, _context, controls) => {
    const input = request.input as { path?: string }
    if (!input.path) {
      controls.fail({ code: 'validation_error', message: 'path is required', attempt: 1 })
      return
    }

    controls.reportProgress(0.1)

    try {
      const resolved = assertPathSafe(input.path, ctx.config.root)
      const permResult = checkPermission(ctx.permissionManager, ['read'], request.context, resolved)
      if (!permResult.granted) {
        ctx.emit('filesystem.error', { path: input.path, error: permResult.reason })
        controls.fail({ code: 'permission_denied', message: permResult.reason ?? 'Permission denied', attempt: 1 })
        return
      }

      const audit = finishAudit(buildAudit(request, 'exists'))
      const result = await ctx.operations.exists({ path: input.path }, audit)

      if (result.success) {
        controls.reportProgress(1)
        controls.succeed(result.data)
      } else {
        ctx.emit('filesystem.error', { path: input.path, error: result.error })
        controls.fail({ code: result.error.code, message: result.error.message, attempt: 1 })
      }
    } catch (error) {
      ctx.emit('filesystem.error', { path: input.path, error: String(error) })
      controls.fail({ code: 'security_error', message: String(error), attempt: 1 })
    }
  }
}

export function handleSearch(ctx: FilesystemHandlerContext): ExecutionHandler {
  return async (request, _context, controls) => {
    const input = request.input as { rootPath?: string; query?: string; maxResults?: number }
    if (!input.rootPath || !input.query) {
      controls.fail({ code: 'validation_error', message: 'rootPath and query are required', attempt: 1 })
      return
    }

    controls.reportProgress(0.1)

    try {
      const resolved = assertPathSafe(input.rootPath, ctx.config.root)
      const permResult = checkPermission(ctx.permissionManager, ['read'], request.context, resolved)
      if (!permResult.granted) {
        ctx.emit('filesystem.error', { path: input.rootPath, error: permResult.reason })
        controls.fail({ code: 'permission_denied', message: permResult.reason ?? 'Permission denied', attempt: 1 })
        return
      }

      const audit = finishAudit(buildAudit(request, 'search'))
      const result = await ctx.operations.search({ rootPath: input.rootPath, query: input.query, maxResults: input.maxResults }, audit)

      if (result.success) {
        controls.reportProgress(1)
        controls.succeed(result.data)
      } else {
        ctx.emit('filesystem.error', { path: input.rootPath, error: result.error })
        controls.fail({ code: result.error.code, message: result.error.message, attempt: 1 })
      }
    } catch (error) {
      ctx.emit('filesystem.error', { path: input.rootPath, error: String(error) })
      controls.fail({ code: 'security_error', message: String(error), attempt: 1 })
    }
  }
}

export function handleTree(ctx: FilesystemHandlerContext): ExecutionHandler {
  return async (request, _context, controls) => {
    const input = request.input as { path?: string }
    if (!input.path) {
      controls.fail({ code: 'validation_error', message: 'path is required', attempt: 1 })
      return
    }

    controls.reportProgress(0.1)

    try {
      const resolved = assertPathSafe(input.path, ctx.config.root)
      const permResult = checkPermission(ctx.permissionManager, ['read'], request.context, resolved)
      if (!permResult.granted) {
        ctx.emit('filesystem.error', { path: input.path, error: permResult.reason })
        controls.fail({ code: 'permission_denied', message: permResult.reason ?? 'Permission denied', attempt: 1 })
        return
      }

      const audit = finishAudit(buildAudit(request, 'tree'))
      const result = await ctx.operations.tree({ path: input.path }, audit)

      if (result.success) {
        controls.reportProgress(1)
        controls.succeed(result.data)
      } else {
        ctx.emit('filesystem.error', { path: input.path, error: result.error })
        controls.fail({ code: result.error.code, message: result.error.message, attempt: 1 })
      }
    } catch (error) {
      ctx.emit('filesystem.error', { path: input.path, error: String(error) })
      controls.fail({ code: 'security_error', message: String(error), attempt: 1 })
    }
  }
}

export function handleCreateProject(ctx: FilesystemHandlerContext): ExecutionHandler {
  return async (request, _context, controls) => {
    const input = request.input as { name?: string; template?: string; root?: string }
    if (!input.name) {
      controls.fail({ code: 'validation_error', message: 'name is required', attempt: 1 })
      return
    }

    controls.reportProgress(0.1)

    try {
      const resolved = input.root ? assertPathSafe(input.root, ctx.config.root) : input.name
      const permResult = checkPermission(ctx.permissionManager, ['write'], request.context, resolved)
      if (!permResult.granted) {
        ctx.emit('filesystem.error', { path: input.name, error: permResult.reason })
        controls.fail({ code: 'permission_denied', message: permResult.reason ?? 'Permission denied', attempt: 1 })
        return
      }

      const audit = finishAudit(buildAudit(request, 'project.create'))
      const result = await ctx.operations.createProject({ name: input.name, template: input.template, root: input.root }, audit)

      if (result.success) {
        controls.reportProgress(1)
        controls.succeed(result.data)
      } else {
        ctx.emit('filesystem.error', { path: input.name, error: result.error })
        controls.fail({ code: result.error.code, message: result.error.message, attempt: 1 })
      }
    } catch (error) {
      ctx.emit('filesystem.error', { path: input.name, error: String(error) })
      controls.fail({ code: 'security_error', message: String(error), attempt: 1 })
    }
  }
}
