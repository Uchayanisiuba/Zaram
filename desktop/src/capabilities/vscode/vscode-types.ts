// desktop/src/capabilities/vscode/vscode-types.ts
//
// Sprint 2.3 — VS Code Capability Pack types.
//
// Read-only contracts for editor, workspace, diagnostics, git, and context
// snapshot. No runtime logic here.

export interface VSCodeEditorInfo {
  activeFile: string | null
  language: string | null
  cursorPosition: { line: number; character: number } | null
  selectedText: string | null
}

export interface VSCodeWorkspaceFolder {
  uri: string
  name: string
}

export interface VSCodeDiagnostic {
  file: string
  line: number
  character: number
  message: string
  severity: 'error' | 'warning' | 'info'
  source?: string
}

export interface VSCodeGitStatus {
  branch: string | null
  changedFiles: string[]
  stagedFiles: string[]
  ahead: number
  behind: number
}

export interface VSCodeContextSnapshot {
  workspace: string
  activeFile: string | null
  language: string | null
  selection: string | null
  diagnostics: number
  gitBranch: string | null
  modifiedFiles: number
  connected: boolean
}

export type VSCodeEventType =
  | 'vscode.connected'
  | 'vscode.active_file_changed'
  | 'vscode.diagnostics_updated'
  | 'vscode.git_status_refreshed'
  | 'vscode.context_provided'
  | 'vscode.disconnected'
  | 'vscode.error'

export interface VSCodeEvent {
  type: VSCodeEventType
  timestamp: number
  data: Record<string, unknown>
}

export type VSCodeEventListener = (event: Readonly<VSCodeEvent>) => void
