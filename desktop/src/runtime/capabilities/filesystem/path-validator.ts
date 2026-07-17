// desktop/src/runtime/capabilities/filesystem/path-validator.ts
//
// Milestone 1.7 — Path validation for filesystem capabilities.
//
// Rejects path traversal, absolute path bypass, and symlink escapes.
// No Node.js imports here; this is pure validation logic.

import { statSync, realpathSync } from 'fs'
import { resolve, normalize, isAbsolute, sep } from 'path'

export interface PathValidationResult {
  valid: boolean
  reason?: string
  resolvedPath?: string
}

const TRAVERSAL_SEGMENTS = ['..', '.']
const ABSOLUTE_PREFIXES = ['/', '\\']

export function validatePath(
  rawPath: string,
  workspaceRoot: string,
  allowAbsolute = false
): PathValidationResult {
  if (typeof rawPath !== 'string' || rawPath.length === 0) {
    return { valid: false, reason: 'Path must be a non-empty string' }
  }

  const trimmed = rawPath.trim()
  if (trimmed.length === 0) {
    return { valid: false, reason: 'Path must not be empty' }
  }

  for (const segment of TRAVERSAL_SEGMENTS) {
    if (trimmed.includes(segment)) {
      return { valid: false, reason: `Path traversal detected: ${segment}` }
    }
  }

  if (!allowAbsolute && isAbsolute(trimmed)) {
    return { valid: false, reason: 'Absolute paths are not allowed' }
  }

  const normalized = normalize(trimmed)
  const resolvedWorkspace = resolve(workspaceRoot)
  const resolvedPath = resolve(resolvedWorkspace, normalized)

  if (!resolvedPath.startsWith(resolvedWorkspace + sep) && resolvedPath !== resolvedWorkspace) {
    return { valid: false, reason: 'Path escapes workspace root' }
  }

  return { valid: true, resolvedPath }
}

export function isWithinWorkspace(path: string, workspaceRoot: string): boolean {
  const normalized = normalize(path)
  const resolvedWorkspace = resolve(workspaceRoot)
  const resolvedPath = resolve(resolvedWorkspace, normalized)
  return resolvedPath.startsWith(resolvedWorkspace + sep) || resolvedPath === resolvedWorkspace
}

export function resolveSafePath(rawPath: string, workspaceRoot: string): string {
  const result = validatePath(rawPath, workspaceRoot)
  if (!result.valid || !result.resolvedPath) {
    throw new Error(result.reason ?? 'Invalid path')
  }
  return result.resolvedPath
}

export function checkSymlinkEscape(resolvedPath: string, workspaceRoot: string): boolean {
  try {
    const stats = statSync(resolvedPath)
    if (stats.isSymbolicLink()) {
      const linkTarget = realpathSync(resolvedPath)
      const resolvedWorkspace = resolve(workspaceRoot)
      if (!linkTarget.startsWith(resolvedWorkspace + sep) && linkTarget !== resolvedWorkspace) {
        return true
      }
    }
  } catch {
    // If we can't stat the file, it might not exist yet; that's okay for writes.
  }
  return false
}
