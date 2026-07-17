// desktop/src/runtime/capabilities/filesystem/permission-manager.ts
//
// Milestone 1.7 — Permission enforcement for filesystem capabilities.
//
// Evaluates allow/deny rules and granted permissions against required
// permissions for a given path. No Node.js imports.

import type { FileSystemPermission, PermissionRule, PermissionContext } from './types'

export interface PermissionCheck {
  granted: boolean
  reason?: string
}

export class PermissionManager {
  constructor(private readonly defaultRules: PermissionRule[] = []) {}

  check(required: FileSystemPermission[], context: PermissionContext, path: string): PermissionCheck {
    const granted = context.grantedPermissions ?? []

    for (const rule of [...this.defaultRules, ...(context.rules ?? [])]) {
      if (this.matchesPattern(path, rule.pathPattern)) {
        const hasAll = rule.permissions.every((p) => granted.includes(p))
        if (rule.effect === 'deny' && hasAll) {
          return { granted: false, reason: `Access denied by rule for ${rule.pathPattern}` }
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

  private matchesPattern(path: string, pattern: string): boolean {
    const normalized = path.replace(/\\/g, '/')
    const normalizedPattern = pattern.replace(/\\/g, '/')
    if (normalizedPattern.endsWith('/**')) {
      const prefix = normalizedPattern.slice(0, -2)
      return normalized.startsWith(prefix)
    }
    return normalized === normalizedPattern || normalized.startsWith(normalizedPattern + '/')
  }
}

export function hasPermission(permissions: string[], required: FileSystemPermission[]): boolean {
  return required.every((p) => permissions.includes(p))
}
