// desktop/src/runtime/workspace/workspace-indexer.ts
//
// Milestone 2.1 — Workspace Runtime indexer.
//
// Walks a workspace root path and produces a lightweight index of projects.
// Uses the Filesystem Capability Pack through the Execution Runtime interface
// (never touches Node.js fs directly from this runtime).

import type { Project, DetectionSignal } from './types'
import {
  detectLanguage,
  detectFrameworks,
  detectDependencies,
  detectEntrypoints,
  detectIgnoredFolders
} from './workspace-detector'

export interface WorkspaceIndexerOptions {
  now?: () => number
}

export class WorkspaceIndexer {
  private readonly now: () => number

  constructor(options: WorkspaceIndexerOptions = {}) {
    this.now = options.now ?? (() => Date.now())
  }

  index(rootPath: string, signals: DetectionSignal[]): Project[] {
    if (signals.length === 0) return []

    const manifestNames = new Set<string>()
    const configNames = new Set<string>()
    const fileNames = new Set<string>()
    const dirNames = new Set<string>()

    for (const signal of signals) {
      const parts = signal.path.split(/[\\/]/)
      const name = parts[parts.length - 1] || signal.path
      if (signal.type === 'manifest') manifestNames.add(name)
      else if (signal.type === 'config') configNames.add(name)
      else if (signal.type === 'entrypoint') fileNames.add(name)
      else if (signal.type === 'vcs') dirNames.add(name)
    }

    const languages = [detectLanguage(manifestNames)].filter((l) => l !== 'unknown')
    const frameworks = detectFrameworks(manifestNames, configNames)
    const dependencies = detectDependencies(manifestNames)
    const entrypoints = detectEntrypoints(fileNames)
    const ignoredFolders = detectIgnoredFolders(dirNames)

    const project: Project = {
      id: computeProjectId(rootPath, languages, frameworks),
      name: computeProjectName(rootPath),
      rootPath,
      relativePath: rootPath,
      languages,
      frameworks,
      dependencies,
      entrypoints,
      ignoredFolders,
      workspaceHash: computeHash(rootPath, signals),
      detectedAt: this.now(),
      updatedAt: this.now()
    }

    return [project]
  }
}

function computeProjectId(rootPath: string, languages: string[], frameworks: string[]): string {
  const base = rootPath.toLowerCase().replace(/[^a-z0-9]/g, '-')
  const suffix = [...languages.slice(0, 2), ...frameworks.slice(0, 2)].join('-')
  return `${base}${suffix ? `-${suffix}` : ''}`
}

function computeProjectName(rootPath: string): string {
  const parts = rootPath.split(/[\\/]/)
  const last = parts[parts.length - 1] || rootPath
  return last || 'root'
}

function computeHash(rootPath: string, signals: DetectionSignal[]): string {
  const payload = `${rootPath}:${signals.map((s) => s.path).sort().join(',')}`
  let hash = 0
  for (let i = 0; i < payload.length; i++) {
    const char = payload.charCodeAt(i)
    hash = ((hash << 5) - hash) + char
    hash = hash & hash
  }
  return Math.abs(hash).toString(16).padStart(8, '0')
}
