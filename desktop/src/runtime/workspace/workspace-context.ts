// desktop/src/runtime/workspace/workspace-context.ts
//
// Milestone 2.1 — Workspace Runtime context generator.
//
// Produces the immutable WorkspaceContext consumed by other runtimes and the
// UI. Pure derivation from WorkspaceState; no side effects.

import type { WorkspaceContext, WorkspaceState, Project } from './types'

export function buildWorkspaceContext(state: WorkspaceState): WorkspaceContext {
  const projects = state.projects
  const languages = Array.from(new Set(projects.flatMap((p) => p.languages)))
  const frameworks = Array.from(new Set(projects.flatMap((p) => p.frameworks)))
  const entrypoints = Array.from(new Set(projects.flatMap((p) => p.entrypoints)))
  const summary = buildSummary(projects, languages, frameworks)

  return {
    revision: state.revision,
    timestamp: state.timestamp,
    rootPath: state.rootPath,
    projects,
    summary,
    languages,
    frameworks,
    entrypoints,
    totalProjects: state.totalProjects,
    totalFiles: state.totalFiles,
    workspaceHash: state.workspaceHash,
    identity: state.identity
  }
}

function buildSummary(
  projects: Project[],
  languages: string[],
  frameworks: string[]
): string {
  if (projects.length === 0) return 'No workspace detected'
  const projectPart =
    projects.length === 1 ? `1 project (${projects[0].name})` : `${projects.length} projects`
  const parts = [projectPart]
  if (languages.length > 0) parts.push(`languages: ${languages.join(', ')}`)
  if (frameworks.length > 0) parts.push(`frameworks: ${frameworks.join(', ')}`)
  return parts.join('; ')
}
