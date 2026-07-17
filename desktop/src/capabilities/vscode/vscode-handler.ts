// desktop/src/capabilities/vscode/vscode-handler.ts
//
// Sprint 2.3 — VS Code ExecutionHandler implementations.
//
// Each handler is read-only and returns VS Code context from the adapter.
// No filesystem bypass, no renderer imports.

import type { ExecutionRequest, ExecutionContext, ExecutionControls, ExecutionHandler } from '../../runtime/execution'
import type { VSCodeAdapter } from './vscode-adapter'
import type { VSCodeEditorInfo, VSCodeDiagnostic, VSCodeGitStatus, VSCodeWorkspaceFolder } from './vscode-types'

export interface VSCodeHandlerContext {
  adapter: VSCodeAdapter
  emit: (eventType: string, data: Record<string, unknown>) => void
}

export function createVSCodeHandlers(adapter: VSCodeAdapter, emit: (eventType: string, data: Record<string, unknown>) => void): VSCodeHandlerContext {
  return { adapter, emit }
}

export function handleVSCodeEditorActive(ctx: VSCodeHandlerContext): ExecutionHandler {
  return async (_request, _context, controls) => {
    ctx.emit('vscode.editor.active.started', {})
    controls.reportProgress(0.5)

    try {
      const info: VSCodeEditorInfo = ctx.adapter.getEditorInfo()
      controls.reportProgress(1)
      ctx.emit('vscode.editor.active.completed', { activeFile: info.activeFile, language: info.language })
      controls.succeed(info)
    } catch (error) {
      ctx.emit('vscode.error', { capability: 'vscode.editor.active', error: String(error) })
      controls.fail({ code: 'vscode_error', message: String(error), attempt: 1 })
    }
  }
}

export function handleVSCodeWorkspaceFolders(ctx: VSCodeHandlerContext): ExecutionHandler {
  return async (_request, _context, controls) => {
    ctx.emit('vscode.workspace.folders.started', {})
    controls.reportProgress(0.5)

    try {
      const folders: VSCodeWorkspaceFolder[] = ctx.adapter.getWorkspaceFolders()
      controls.reportProgress(1)
      ctx.emit('vscode.workspace.folders.completed', { folders: folders.length })
      controls.succeed(folders)
    } catch (error) {
      ctx.emit('vscode.error', { capability: 'vscode.workspace.folders', error: String(error) })
      controls.fail({ code: 'vscode_error', message: String(error), attempt: 1 })
    }
  }
}

export function handleVSCodeDiagnostics(ctx: VSCodeHandlerContext): ExecutionHandler {
  return async (_request, _context, controls) => {
    ctx.emit('vscode.diagnostics.started', {})
    controls.reportProgress(0.5)

    try {
      const diagnostics: VSCodeDiagnostic[] = ctx.adapter.getDiagnostics()
      controls.reportProgress(1)
      ctx.emit('vscode.diagnostics.completed', { count: diagnostics.length })
      controls.succeed(diagnostics)
    } catch (error) {
      ctx.emit('vscode.error', { capability: 'vscode.diagnostics', error: String(error) })
      controls.fail({ code: 'vscode_error', message: String(error), attempt: 1 })
    }
  }
}

export function handleVSCodeGitStatus(ctx: VSCodeHandlerContext): ExecutionHandler {
  return async (_request, _context, controls) => {
    ctx.emit('vscode.git.status.started', {})
    controls.reportProgress(0.5)

    try {
      const status: VSCodeGitStatus = ctx.adapter.getGitStatus()
      controls.reportProgress(1)
      ctx.emit('vscode.git.status.completed', { branch: status.branch, changed: status.changedFiles.length })
      controls.succeed(status)
    } catch (error) {
      ctx.emit('vscode.error', { capability: 'vscode.git.status', error: String(error) })
      controls.fail({ code: 'vscode_error', message: String(error), attempt: 1 })
    }
  }
}
