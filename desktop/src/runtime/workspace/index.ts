// desktop/src/runtime/workspace/index.ts
//
// Milestone 2.1 — Workspace Runtime barrel export.

export { WorkspaceRuntime } from './workspace-runtime'
export type { WorkspaceRuntimeOptions } from './workspace-runtime'
export { bootstrapWorkspace } from './bootstrap'
export type { WorkspaceBootstrapOptions } from './bootstrap'
export { WorkspaceCache } from './workspace-cache'
export type { WorkspaceCacheOptions } from './workspace-cache'
export { WorkspaceIndexer } from './workspace-indexer'
export type { WorkspaceIndexerOptions } from './workspace-indexer'
export { detectLanguage, detectFrameworks, detectDependencies, detectEntrypoints, detectIgnoredFolders, buildProjectSignals } from './workspace-detector'
export { buildWorkspaceContext } from './workspace-context'
export { type WorkspaceWatcher, type WorkspaceWatcherFactory } from './workspace-watcher'
export type {
  LanguageId,
  FrameworkId,
  Project,
  Dependency,
  WorkspaceState,
  WorkspaceContext,
  WorkspaceEventType,
  WorkspaceEvent,
  WorkspaceEventListener,
  DetectionSignal,
  WorkspaceCacheEntry,
  IWorkspaceRuntime
} from './types'
export { defaultWorkspaceState, defaultWorkspaceContext } from './types'
