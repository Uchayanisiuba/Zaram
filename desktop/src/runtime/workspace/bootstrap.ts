// desktop/src/runtime/workspace/bootstrap.ts
//
// Milestone 2.1 — Workspace Runtime bootstrap.
//
// Wires the Workspace Runtime into the DI container. Does NOT modify any
// existing runtime. The Workspace Runtime is injected into PresenceRuntime
// and advanced on the existing 30Hz tick.

import { Container, TOKENS } from '../di'
import { WorkspaceRuntime } from './workspace-runtime'

export interface WorkspaceBootstrapOptions {
  rootPath?: string
  cacheMaxEntries?: number
}

export function bootstrapWorkspace(options: WorkspaceBootstrapOptions = {}): WorkspaceRuntime {
  const runtime = new WorkspaceRuntime({
    rootPath: options.rootPath,
    cacheMaxEntries: options.cacheMaxEntries
  })

  return runtime
}
