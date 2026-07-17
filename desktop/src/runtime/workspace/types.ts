// desktop/src/runtime/workspace/types.ts
//
// Milestone 2.1 — Workspace Runtime type contracts.
//
// The Workspace Runtime provides semantic understanding of projects. It is an
// Intelligence Runtime: fully decoupled from the drawing layer and the character
// projection pipeline. It never produces a FrameState.
//
// Every snapshot type below is a plain data structure. The runtime never hands
// out mutable references; consumers receive frozen deep copies.

// --- Language detection ----------------------------------------------------

export type LanguageId =
  | 'typescript'
  | 'javascript'
  | 'python'
  | 'rust'
  | 'go'
  | 'java'
  | 'kotlin'
  | 'ruby'
  | 'php'
  | 'csharp'
  | 'cpp'
  | 'c'
  | 'swift'
  | 'dart'
  | 'scala'
  | 'unknown'

// --- Framework detection ---------------------------------------------------

export type FrameworkId =
  | 'react'
  | 'vue'
  | 'angular'
  | 'svelte'
  | 'nextjs'
  | 'nuxt'
  | 'django'
  | 'flask'
  | 'fastapi'
  | 'spring'
  | 'express'
  | 'vite'
  | 'webpack'
  | 'tailwindcss'
  | 'docker'
  | 'unknown'

// --- Project types ---------------------------------------------------------

export interface Project {
  id: string
  name: string
  rootPath: string
  relativePath: string
  languages: LanguageId[]
  frameworks: FrameworkId[]
  dependencies: Dependency[]
  entrypoints: string[]
  ignoredFolders: string[]
  workspaceHash: string
  detectedAt: number
  updatedAt: number
}

export interface Dependency {
  name: string
  version?: string
  type: 'runtime' | 'dev' | 'peer' | 'optional'
  source: string
}

// --- Workspace identity ----------------------------------------------------

export interface WorkspaceIdentity {
  workspaceId: string
  name: string
  rootUri: string
  primaryLanguage: LanguageId
  primaryFramework: FrameworkId
  confidence: number
  projects: string[]
  created: number
  lastIndexed: number
  snapshotVersion: number
}

// --- Workspace state -------------------------------------------------------

export interface WorkspaceState {
  revision: number
  timestamp: number
  rootPath: string
  projects: Project[]
  languages: LanguageId[]
  frameworks: FrameworkId[]
  totalProjects: number
  totalFiles: number
  workspaceHash: string
  identity: WorkspaceIdentity
}

// --- Workspace events ------------------------------------------------------

export type WorkspaceEventType =
  | 'workspace.discovered'
  | 'workspace.changed'
  | 'workspace.project_added'
  | 'workspace.project_updated'
  | 'workspace.project_removed'
  | 'workspace.scan_started'
  | 'workspace.scan_completed'
  | 'workspace.snapshot_created'
  | 'workspace.context_provided'
  | 'workspace.error'

export interface WorkspaceEvent {
  type: WorkspaceEventType
  eventId: number
  timestamp: number
  data: Record<string, unknown>
  correlationId?: string
}

export type WorkspaceEventListener = (event: Readonly<WorkspaceEvent>) => void

// --- Workspace context (produced output) -----------------------------------

export interface WorkspaceContext {
  revision: number
  timestamp: number
  rootPath: string
  projects: Project[]
  summary: string
  languages: LanguageId[]
  frameworks: FrameworkId[]
  entrypoints: string[]
  totalProjects: number
  totalFiles: number
  workspaceHash: string
  identity: WorkspaceIdentity
}

// --- Detection signals -----------------------------------------------------

export interface DetectionSignal {
  path: string
  type: 'manifest' | 'config' | 'vcs' | 'entrypoint'
  language?: LanguageId
  framework?: FrameworkId
  confidence: number
  evidence?: string[]
}

// --- Cache contract --------------------------------------------------------

export interface WorkspaceCacheEntry {
  path: string
  hash: string
  project: Project
  cachedAt: number
}

// --- Watcher contract ------------------------------------------------------

export interface WorkspaceWatcher {
  start(): void
  stop(): void
  onChange(callback: (path: string) => void): () => void
}

// --- Worker pool contract --------------------------------------------------

export interface IndexingJob {
  id: string
  rootPath: string
  signals: DetectionSignal[]
  mode: 'shallow' | 'deep'
}

export interface IndexingResult {
  id: string
  projects: Project[]
  error?: string
}

// --- Workspace snapshot (UI-facing flattened context) ----------------------
//
// Sprint 2.2 — Workspace-Aware Conversation. A deliberately small,
// read-only view of the workspace that the Conversation panel is allowed to
// consume. It is derived ONLY from the WorkspaceContext/WorkspaceState; the
// full project tree is never exposed to the conversation layer.
//
// `open_modules` are the workspace-level modules currently considered in
// scope (derived from project names / relative paths) so the assistant can
// answer "what project am I in?" without the entire tree.

export interface WorkspaceSnapshot {
  workspace: string
  framework: string
  language: string
  projects: number
  confidence: number
  open_modules: string[]
}

// --- Interfaces ------------------------------------------------------------

export interface IWorkspaceRuntime {
  getWorkspaceState(): Readonly<WorkspaceState>
  getWorkspaceContext(): Readonly<WorkspaceContext>
  getWorkspaceSnapshot(): Readonly<WorkspaceSnapshot>
  getProject(path: string): Project | null
  getAllProjects(): Project[]
  subscribe(listener: WorkspaceEventListener): () => void
  update(dt: number): void
}

// --- Helpers ---------------------------------------------------------------

export function defaultWorkspaceIdentity(now: number = Date.now()): WorkspaceIdentity {
  return {
    workspaceId: '',
    name: '',
    rootUri: '',
    primaryLanguage: 'unknown',
    primaryFramework: 'unknown',
    confidence: 0,
    projects: [],
    created: now,
    lastIndexed: now,
    snapshotVersion: 0
  }
}

export function defaultWorkspaceState(): WorkspaceState {
  const now = Date.now()
  return {
    revision: 0,
    timestamp: now,
    rootPath: '',
    projects: [],
    languages: [],
    frameworks: [],
    totalProjects: 0,
    totalFiles: 0,
    workspaceHash: '',
    identity: defaultWorkspaceIdentity(now)
  }
}

export function defaultWorkspaceContext(): WorkspaceContext {
  const now = Date.now()
  return {
    revision: 0,
    timestamp: now,
    rootPath: '',
    projects: [],
    summary: 'No workspace detected',
    languages: [],
    frameworks: [],
    entrypoints: [],
    totalProjects: 0,
    totalFiles: 0,
    workspaceHash: '',
    identity: defaultWorkspaceIdentity(now)
  }
}

export function deepFreeze<T>(value: T): T {
  if (value === null || typeof value !== 'object') return value
  if (Object.isFrozen(value)) return value
  Object.freeze(value)
  for (const key of Object.keys(value as Record<string, unknown>)) {
    deepFreeze((value as Record<string, unknown>)[key])
  }
  return value
}
