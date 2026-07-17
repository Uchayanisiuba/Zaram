// desktop/src/capabilities/filesystem/filesystem-security.ts
//
// Milestone 2.0 — Zero-trust filesystem security.
//
// Validates every path against traversal, symlink escape, system folder,
// and LLM-generated path attacks. No Node.js fs imports here.

import { isSystemPath, containsGitSegment, canonicalizePath } from './filesystem-paths'

export interface PathValidationResult {
  valid: boolean
  reason?: string
  resolvedPath?: string
}

const TRAVERSAL_PATTERNS = [
  /\.\.\//,
  /\.\.\\/,
  /%2e%2e/i,
  /%2f/i,
  /%5c/i
]

export function validatePathSecurity(rawPath: string, workspaceRoot: string): PathValidationResult {
  if (typeof rawPath !== 'string' || rawPath.trim().length === 0) {
    return { valid: false, reason: 'Path must be a non-empty string' }
  }

  const trimmed = rawPath.trim()

  for (const pattern of TRAVERSAL_PATTERNS) {
    if (pattern.test(trimmed)) {
      return { valid: false, reason: 'Path traversal detected' }
    }
  }

  if (trimmed.includes('..')) {
    return { valid: false, reason: 'Path traversal detected' }
  }

  const resolved = canonicalizePath(trimmed, workspaceRoot)

  if (isSystemPath(resolved)) {
    return { valid: false, reason: 'Access to system paths is denied' }
  }

  if (containsGitSegment(resolved)) {
    return { valid: false, reason: 'Access to .git is denied' }
  }

  return { valid: true, resolvedPath: resolved }
}

export function assertPathSafe(rawPath: string, workspaceRoot: string): string {
  const result = validatePathSecurity(rawPath, workspaceRoot)
  if (!result.valid || !result.resolvedPath) {
    throw new Error(result.reason ?? 'Invalid path')
  }
  return result.resolvedPath
}
