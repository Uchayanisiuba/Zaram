// desktop/src/runtime/workspace/workspace-watcher.ts
//
// Milestone 2.1 — Workspace Runtime filesystem watcher.
//
// Abstracts filesystem observation so the Workspace Runtime never imports
// Node.js fs/watch APIs directly. The concrete implementation is provided at
// bootstrap time. This keeps the runtime testable and platform-agnostic.

export interface WorkspaceWatcher {
  start(): void
  stop(): void
  onChange(callback: (path: string) => void): () => void
}

export type WorkspaceWatcherFactory = (rootPath: string) => WorkspaceWatcher
