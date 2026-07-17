// desktop/src/capabilities/filesystem/filesystem-paths.ts
//
// Milestone 2.0 — Filesystem path resolution and workspace detection.
//
// Resolves the ZARAM_WORKSPACE, canonicalizes paths, and provides the
// default workspace location. No Node.js fs imports here.

import { homedir, platform } from 'os'
import { resolve, join, isAbsolute, normalize } from 'path'

export interface WorkspaceConfig {
  root: string
  trashDir: string
  tempDir: string
}

export function resolveWorkspaceRoot(): string {
  const envRoot = process.env.ZARAM_WORKSPACE
  if (envRoot && envRoot.trim().length > 0) {
    return resolve(envRoot.trim())
  }
  const home = homedir()
  if (platform() === 'win32') {
    return join(home, 'Documents', 'Zaram')
  }
  return join(home, 'Documents', 'Zaram')
}

export function buildWorkspaceConfig(root?: string): WorkspaceConfig {
  const resolvedRoot = root ? resolve(root) : resolveWorkspaceRoot()
  return {
    root: resolvedRoot,
    trashDir: join(resolvedRoot, '.zaram_trash'),
    tempDir: join(resolvedRoot, '.zaram_tmp')
  }
}

export function canonicalizePath(raw: string, workspaceRoot: string): string {
  if (!isAbsolute(raw)) {
    return resolve(workspaceRoot, normalize(raw))
  }
  return resolve(normalize(raw))
}

export function isSystemPath(path: string): boolean {
  const lower = path.toLowerCase().replace(/\\/g, '/')
  const systemPrefixes = [
    '/system',
    '/windows',
    '/usr/bin',
    '/usr/sbin',
    '/bin',
    '/sbin',
    '/etc',
    '/proc',
    '/sys',
    'c:/windows',
    'c:/system32',
    'c:/program files',
    'c:/program files (x86)'
  ]
  return systemPrefixes.some((prefix) => lower === prefix || lower.startsWith(prefix + '/'))
}

export function containsGitSegment(path: string): boolean {
  const segments = path.replace(/\\/g, '/').split('/')
  return segments.some((seg) => seg === '.git')
}
