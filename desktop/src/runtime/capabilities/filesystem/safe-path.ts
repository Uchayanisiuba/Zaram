// desktop/src/runtime/capabilities/filesystem/safe-path.ts
//
// Milestone 1.7 — Safe path utilities for filesystem capabilities.
//
// Thin wrappers around path-validator that add convenience methods for
// common path operations. No Node.js imports.

import { validatePath, isWithinWorkspace, resolveSafePath, checkSymlinkEscape } from './path-validator'
import type { PathValidationResult } from './path-validator'

export function sanitizePath(rawPath: string, workspaceRoot: string, allowAbsolute = false): PathValidationResult {
  return validatePath(rawPath, workspaceRoot, allowAbsolute)
}

export function assertSafePath(rawPath: string, workspaceRoot: string): string {
  return resolveSafePath(rawPath, workspaceRoot)
}

export function isPathEscapingSymlink(path: string, workspaceRoot: string): boolean {
  return checkSymlinkEscape(path, workspaceRoot)
}

export function ensureWithinWorkspace(path: string, workspaceRoot: string): void {
  if (!isWithinWorkspace(path, workspaceRoot)) {
    throw new Error('Path is outside the allowed workspace')
  }
}

export function getFileExtension(filename: string): string {
  const lastDot = filename.lastIndexOf('.')
  return lastDot === -1 ? '' : filename.slice(lastDot + 1).toLowerCase()
}

export function getFileName(filepath: string): string {
  const normalized = filepath.replace(/\\/g, '/')
  const segments = normalized.split('/')
  return segments[segments.length - 1] ?? filepath
}
