// desktop/src/capabilities/filesystem/filesystem-permissions.ts
//
// Milestone 2.0 — Filesystem permission enforcement.
//
// Four-level permission model with workspace isolation. No Node.js fs imports.

import type { FileSystemPermission, PermissionRule, PermissionContext } from './filesystem-types'
import { isSystemPath } from './filesystem-paths'

export interface PermissionCheck {
  granted: boolean
  reason?: string
}

export class FileSystemPermissionManager {
  constructor(private readonly workspaceRoot: string) {}

  check(
    required: FileSystemPermission[],
    context: PermissionContext,
    resolvedPath: string
  ): PermissionCheck {
    const granted = context.grantedPermissions ?? []

    if (isSystemPath(resolvedPath)) {
      return { granted: false, reason: 'System paths are hard-denied' }
    }

    if (required.includes('delete')) {
      const hasDeleteApproval = granted.includes('filesystem:delete')
      if (!hasDeleteApproval) {
        return { granted: false, reason: 'Delete requires approval (Level 4)' }
      }
    }

    const outsideWorkspace = !isWithinWorkspace(resolvedPath, this.workspaceRoot)

    if (outsideWorkspace) {
      const level = this.evaluateOutsideWorkspaceLevel(required, context)
      if (!level.allowed) {
        return { granted: false, reason: level.reason }
      }
    }

    const rules = context.rules ?? []
    for (const rule of rules) {
      if (matchesPattern(resolvedPath, rule.pathPattern)) {
        const hasAll = rule.permissions.every((p) => granted.includes(p))
        if (rule.effect === 'deny' && hasAll) {
          return { granted: false, reason: `Denied by rule for ${rule.pathPattern}` }
        }
        if (rule.effect === 'allow' && !hasAll) {
          return { granted: false, reason: `Insufficient permissions for ${rule.pathPattern}` }
        }
      }
    }

    const hasAllRequired = required.every((p) => granted.includes(p))
    if (!hasAllRequired) {
      return { granted: false, reason: `Missing required permissions: ${required.join(', ')}` }
    }

    return { granted: true }
  }

  private evaluateOutsideWorkspaceLevel(
    required: FileSystemPermission[],
    context: PermissionContext
  ): { allowed: boolean; reason?: string } {
    const granted = context.grantedPermissions ?? []

    if (required.includes('delete')) {
      return { allowed: false, reason: 'Delete outside workspace requires approval (Level 4)' }
    }

    if (required.includes('write')) {
      const hasWriteApproval = granted.includes('filesystem:write:outside')
      if (!hasWriteApproval) {
        return { allowed: false, reason: 'Write outside workspace requires approval (Level 3)' }
      }
      return { allowed: true }
    }

    if (required.includes('read')) {
      const hasReadApproval = granted.includes('filesystem:read:outside')
      if (!hasReadApproval) {
        return { allowed: false, reason: 'Read outside workspace requires approval (Level 2)' }
      }
      return { allowed: true }
    }

    return { allowed: true }
  }
}

function isWithinWorkspace(path: string, workspaceRoot: string): boolean {
  const normalized = path.replace(/\\/g, '/')
  const root = workspaceRoot.replace(/\\/g, '/')
  return normalized === root || normalized.startsWith(root + '/')
}

function matchesPattern(path: string, pattern: string): boolean {
  const normalized = path.replace(/\\/g, '/')
  const normalizedPattern = pattern.replace(/\\/g, '/')
  if (normalizedPattern.endsWith('/**')) {
    const prefix = normalizedPattern.slice(0, -2)
    return normalized.startsWith(prefix)
  }
  return normalized === normalizedPattern || normalized.startsWith(normalizedPattern + '/')
}
