// desktop/src/runtime/workspace/workspace-runtime.ts
//
// Milestone 2.1 — Workspace Runtime (Intelligence Runtime).
//
// Provides semantic understanding of projects. It is an Intelligence Runtime:
// fully decoupled from the drawing layer and the character projection pipeline.
// It never produces a FrameState.
//
// It is fully event-driven and time-evolved ONLY on the existing 30Hz frame
// tick (no setInterval, no requestAnimationFrame, no polling loop of its own).
//
// The Executive Runtime consumes the workspace exclusively through
// IWorkspaceRuntime (see ./types.ts). It never sees the concrete runtime.
// It stays decoupled from the drawing layer and the character projection pipeline.

import type { ExecutionRuntime } from '../execution'
import type {
  WorkspaceContext,
  WorkspaceEvent,
  WorkspaceEventType,
  WorkspaceEventListener,
  IWorkspaceRuntime,
  WorkspaceState,
  WorkspaceSnapshot,
  Project,
  DetectionSignal,
  WorkspaceIdentity,
  IndexingJob,
  IndexingResult
} from './types'
import { defaultWorkspaceState, defaultWorkspaceIdentity, deepFreeze } from './types'
import { WorkspaceIndexer } from './workspace-indexer'
import { WorkspaceCache } from './workspace-cache'
import { WorkerPool } from './workspace-pool'
import { buildProjectSignals, detectLanguage, PROTECTED_PATTERNS, SKIPPED_PATTERNS } from './workspace-detector'
import { buildWorkspaceContext } from './workspace-context'

export interface WorkspaceRuntimeOptions {
  rootPath?: string
  cacheMaxEntries?: number
  maxWorkers?: number
  now?: () => number
}

export class WorkspaceRuntime implements IWorkspaceRuntime {
  private readonly subscribers = new Set<WorkspaceEventListener>()
  private readonly indexer: WorkspaceIndexer
  private readonly cache: WorkspaceCache
  private readonly pool: WorkerPool
  private readonly now: () => number

  private rootPath: string
  private revision = 0
  private eventSeq = 0
  private snapshotVersion = 0
  private state: WorkspaceState = defaultWorkspaceState()
  private dirty = false
  private pendingJob: Promise<void> | null = null

  constructor(options: WorkspaceRuntimeOptions = {}) {
    this.rootPath = options.rootPath ?? ''
    this.now = options.now ?? (() => Date.now())
    const now = this.now()
    this.state = {
      ...defaultWorkspaceState(),
      rootPath: this.rootPath,
      identity: {
        ...defaultWorkspaceIdentity(now),
        rootUri: this.rootPath
      }
    }
    this.indexer = new WorkspaceIndexer({ now: this.now })
    this.cache = new WorkspaceCache({ maxEntries: options.cacheMaxEntries })
    this.pool = new WorkerPool({ maxWorkers: options.maxWorkers })
  }

  // --- Configuration --------------------------------------------------------

  setRootPath(path: string): void {
    if (path === this.rootPath) return
    this.rootPath = path
    const now = this.now()
    this.state = {
      ...defaultWorkspaceState(),
      rootPath: path,
      identity: {
        ...defaultWorkspaceIdentity(now),
        rootUri: path,
        name: computeWorkspaceName(path)
      },
      timestamp: now
    }
    this.dirty = true
    this.publish('workspace.changed', { workspaceState: this.snapshot() })
  }

  getRootPath(): string {
    return this.rootPath
  }

  // --- Workspace discovery --------------------------------------------------

  async discover(signals: DetectionSignal[], mode: 'shallow' | 'deep' = 'shallow'): Promise<void> {
    if (!this.rootPath) return
    if (signals.length === 0) return
    this.publish('workspace.scan_started', { rootPath: this.rootPath })

    try {
      const filtered = this.applyProtectedPolicy(signals)
      const job: IndexingJob = {
        id: `index-${Date.now()}`,
        rootPath: this.rootPath,
        signals: filtered,
        mode
      }

      this.pendingJob = this.pool.index(job).then((result: IndexingResult) => {
        this.applyProjects(result.projects)
        this.publish('workspace.scan_completed', { workspaceState: this.snapshot() })
        this.publish('workspace.snapshot_created', { snapshotVersion: this.snapshotVersion })
      }).catch((error) => {
        this.publish('workspace.error', { error: String(error) })
      })

      await this.pendingJob
    } catch (error) {
      this.publish('workspace.error', { error: String(error) })
    }
  }

  // --- Time evolution on the existing 30Hz tick -----------------------------
  //
  // Called by PresenceRuntime.tick(dt). If dirty, recomputes the derived
  // context. Introduces NO new timer or loop.

  update(_dt: number): void {
    if (!this.dirty) return
    this.dirty = false
    this.rebuildContext()
  }

  // --- Read-only snapshots --------------------------------------------------

  getWorkspaceState(): Readonly<WorkspaceState> {
    return deepFreeze({ ...this.state })
  }

  getWorkspaceContext(): Readonly<WorkspaceContext> {
    const ctx = buildWorkspaceContext(this.state)
    return deepFreeze(ctx)
  }

  // --- UI-facing snapshot (Sprint 2.2) ------------------------------------
  //
  // Flattened, conversation-safe view. Never exposes the project tree, hashes,
  // or internal implementation detail. Derived purely from WorkspaceState.

  getWorkspaceSnapshot(): Readonly<WorkspaceSnapshot> {
    const identity = this.state.identity
    const primaryFramework = this.state.frameworks[0] || identity.primaryFramework || 'unknown'
    const primaryLanguage = this.state.languages[0] || identity.primaryLanguage || 'unknown'
    const name = identity.name || computeWorkspaceName(this.rootPath)

    const snapshot: WorkspaceSnapshot = {
      workspace: name,
      framework: primaryFramework,
      language: primaryLanguage,
      projects: this.state.totalProjects,
      confidence: identity.confidence,
      open_modules: this.deriveOpenModules()
    }
    return deepFreeze(snapshot)
  }

  // Called by the Conversation layer when it grounds a turn in the workspace.
  // Returns the snapshot and publishes a human-readable lifecycle event.
  provideContext(): Readonly<WorkspaceSnapshot> {
    const snapshot = this.getWorkspaceSnapshot()
    this.publish('workspace.context_provided', { snapshot: { ...snapshot } })
    return snapshot
  }

  private deriveOpenModules(): string[] {
    const modules = this.state.projects.map((p) => p.name || computeWorkspaceName(p.rootPath))
    if (modules.length === 0 && this.rootPath) {
      return [computeWorkspaceName(this.rootPath)]
    }
    return Array.from(new Set(modules.filter(Boolean)))
  }

  getProject(path: string): Project | null {
    const project = this.state.projects.find((p) => p.rootPath === path || p.relativePath === path)
    return project ? { ...project } : null
  }

  getAllProjects(): Project[] {
    return this.state.projects.map((p) => ({ ...p }))
  }

  // --- Event publishing -----------------------------------------------------

  subscribe(listener: WorkspaceEventListener): () => void {
    this.subscribers.add(listener)
    return () => {
      this.subscribers.delete(listener)
    }
  }

  // --- Internals ------------------------------------------------------------

  private applyProtectedPolicy(signals: DetectionSignal[]): DetectionSignal[] {
    return signals.filter((s) => {
      const name = s.path.split(/[\\/]/).pop()?.toLowerCase() || s.path.toLowerCase()
      for (const pattern of PROTECTED_PATTERNS) {
        if (name === pattern || name.startsWith(pattern)) {
          return false
        }
      }
      return true
    })
  }

  private applyProjects(projects: Project[]): void {
    this.state.projects = projects.map((p) => ({ ...p }))
    this.state.totalProjects = projects.length
    this.state.totalFiles = projects.reduce((sum, p) => sum + p.entrypoints.length, 0)
    this.state.languages = Array.from(new Set(projects.flatMap((p) => p.languages)))
    this.state.frameworks = Array.from(new Set(projects.flatMap((p) => p.frameworks)))
    this.state.workspaceHash = projects.length > 0 ? projects[0].workspaceHash : ''
    this.snapshotVersion += 1

    const primaryLanguage = this.state.languages[0] || 'unknown'
    const primaryFramework = this.state.frameworks[0] || 'unknown'
    const confidence = this.computeConfidence(projects)

    this.state.identity = {
      workspaceId: this.state.identity.workspaceId || computeWorkspaceId(this.rootPath),
      name: this.state.identity.name || computeWorkspaceName(this.rootPath),
      rootUri: this.rootPath,
      primaryLanguage,
      primaryFramework,
      confidence,
      projects: projects.map((p) => p.id),
      created: this.state.identity.created || this.now(),
      lastIndexed: this.now(),
      snapshotVersion: this.snapshotVersion
    }

    this.revision += 1
    this.state.revision = this.revision
    this.state.timestamp = this.now()
    this.dirty = true

    for (const project of projects) {
      this.publish('workspace.project_added', { project })
    }

    this.publish('workspace.discovered', { workspaceState: this.snapshot() })
  }

  private rebuildContext(): void {
    this.revision += 1
    this.state.revision = this.revision
    this.state.timestamp = this.now()
    this.publish('workspace.changed', { workspaceState: this.snapshot() })
  }

  private computeConfidence(projects: Project[]): number {
    if (projects.length === 0) return 0
    const project = projects[0]
    const evidenceCount = [
      project.languages.length > 0 ? 1 : 0,
      project.frameworks.length > 0 ? 1 : 0,
      project.dependencies.length > 0 ? 1 : 0,
      project.entrypoints.length > 0 ? 1 : 0
    ].reduce((sum, c) => sum + c, 0)

    return Math.round((evidenceCount / 4) * 100)
  }

  private snapshot(): WorkspaceState {
    return {
      revision: this.revision,
      timestamp: this.state.timestamp,
      rootPath: this.state.rootPath,
      projects: this.state.projects.map((p) => ({ ...p })),
      languages: [...this.state.languages],
      frameworks: [...this.state.frameworks],
      totalProjects: this.state.totalProjects,
      totalFiles: this.state.totalFiles,
      workspaceHash: this.state.workspaceHash,
      identity: { ...this.state.identity, projects: [...this.state.identity.projects] }
    }
  }

  private publish(type: WorkspaceEventType, data: Record<string, unknown>): void {
    const event: WorkspaceEvent = {
      type,
      eventId: this.eventSeq++,
      timestamp: this.now(),
      data: deepFreeze(data)
    }
    this.subscribers.forEach((l) => {
      try {
        l(event)
      } catch {
        // subscriber errors must not break the tick
      }
    })
  }
}

function computeWorkspaceId(rootPath: string): string {
  const base = rootPath.toLowerCase().replace(/[^a-z0-9]/g, '-')
  return `workspace-${base || 'root'}`
}

function computeWorkspaceName(rootPath: string): string {
  const parts = rootPath.split(/[\\/]/)
  const last = parts[parts.length - 1] || rootPath
  return last || 'root'
}
