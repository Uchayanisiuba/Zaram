// desktop/src/runtime/workspace/workspace-cache.ts
//
// Milestone 2.1 — Workspace Runtime cache.
//
// Provides a simple in-memory LRU cache keyed by workspace root path.
// Entries are invalidated by hash mismatch or explicit invalidation.
// No timers, no polling; the runtime decides when to invalidate.

import type { Project, WorkspaceCacheEntry } from './types'

export interface WorkspaceCacheOptions {
  maxEntries?: number
}

export class WorkspaceCache {
  private readonly maxEntries: number
  private readonly entries = new Map<string, WorkspaceCacheEntry>()

  constructor(options: WorkspaceCacheOptions = {}) {
    this.maxEntries = options.maxEntries ?? 128
  }

  get(path: string): WorkspaceCacheEntry | undefined {
    const entry = this.entries.get(path)
    if (!entry) return undefined
    this.touch(path)
    return entry
  }

  set(path: string, project: Project): void {
    this.evictIfNeeded()
    this.entries.set(path, {
      path,
      hash: project.workspaceHash,
      project: { ...project },
      cachedAt: Date.now()
    })
  }

  invalidate(path: string): boolean {
    return this.entries.delete(path)
  }

  invalidateAll(): void {
    this.entries.clear()
  }

  has(path: string): boolean {
    return this.entries.has(path)
  }

  size(): number {
    return this.entries.size
  }

  private touch(path: string): void {
    const entry = this.entries.get(path)
    if (entry) {
      entry.cachedAt = Date.now()
      this.entries.delete(path)
      this.entries.set(path, entry)
    }
  }

  private evictIfNeeded(): void {
    if (this.entries.size >= this.maxEntries) {
      const oldest = this.entries.keys().next().value
      if (typeof oldest === 'string') {
        this.entries.delete(oldest)
      }
    }
  }
}
