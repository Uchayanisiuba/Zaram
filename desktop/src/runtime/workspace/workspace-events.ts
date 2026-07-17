// desktop/src/runtime/workspace/workspace-events.ts
//
// Milestone 2.1 — Workspace Runtime event contracts.
//
// Mirrors the universal event bus contract shape but scoped to workspace
// semantics. No external Event Bus dependency; uses the same Set-based
// pub/sub pattern as World, Cognitive, Executive, and Execution runtimes.

export type { WorkspaceEventType, WorkspaceEvent, WorkspaceEventListener } from './types'
