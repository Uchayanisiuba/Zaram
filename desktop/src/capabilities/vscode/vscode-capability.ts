// desktop/src/capabilities/vscode/vscode-capability.ts
//
// Sprint 2.3 — VS Code Capability Pack.
//
// Implements ICapabilityPack. Registers 4 VS Code capability descriptors
// with the Capability Runtime and 4 handlers with the Execution Invoker.
// Emits VS Code-specific events through its own event bus.
//
// This pack is completely isolated. It does not import the drawing layer,
// the body layer, concrete avatars, the character projection, the animation
// engine, frame snapshots, the desktop shell, any GPU/3D engine, or the
// Emotion/Behaviour/Presence/Character/body-layer runtimes.

import type { ICapabilityRuntime } from '../../runtime/capability'
import type { IExecutionInvoker, ExecutionHandler, ExecutionRollback } from '../../runtime/execution'
import { createVSCodeHandlers, handleVSCodeEditorActive, handleVSCodeWorkspaceFolders, handleVSCodeDiagnostics, handleVSCodeGitStatus } from './vscode-handler'
import type { VSCodeHandlerContext } from './vscode-handler'
import { VSCodeAdapter } from './vscode-adapter'

const VSCODE_CAPABILITIES: Array<{
  id: string
  name: string
  description: string
  category: 'developer'
  permissions: string[]
  inputSchema: Record<string, unknown>
  outputSchema: Record<string, unknown>
  latencyEstimateMs: number
  location: 'local'
}> = [
  {
    id: 'vscode.editor.active',
    name: 'Active Editor',
    description: 'Return the active file, language, cursor position, and selected text',
    category: 'developer',
    permissions: [],
    inputSchema: { type: 'object', properties: {} },
    outputSchema: { type: 'object', properties: { activeFile: { type: 'string' }, language: { type: 'string' }, cursorPosition: { type: 'object' }, selectedText: { type: 'string' } } },
    latencyEstimateMs: 5,
    location: 'local'
  },
  {
    id: 'vscode.workspace.folders',
    name: 'Workspace Folders',
    description: 'Return the opened workspace folders',
    category: 'developer',
    permissions: [],
    inputSchema: { type: 'object', properties: {} },
    outputSchema: { type: 'object', properties: { folders: { type: 'array' } } },
    latencyEstimateMs: 5,
    location: 'local'
  },
  {
    id: 'vscode.diagnostics',
    name: 'Diagnostics',
    description: 'Return compiler errors, warnings, and diagnostics',
    category: 'developer',
    permissions: [],
    inputSchema: { type: 'object', properties: {} },
    outputSchema: { type: 'object', properties: { diagnostics: { type: 'array' }, count: { type: 'number' } } },
    latencyEstimateMs: 200,
    location: 'local'
  },
  {
    id: 'vscode.git.status',
    name: 'Git Status',
    description: 'Return changed files, staged files, and branch',
    category: 'developer',
    permissions: [],
    inputSchema: { type: 'object', properties: {} },
    outputSchema: { type: 'object', properties: { branch: { type: 'string' }, changedFiles: { type: 'array' }, stagedFiles: { type: 'array' } } },
    latencyEstimateMs: 50,
    location: 'local'
  }
]

export class VSCodeCapabilityPack {
  private readonly adapter: VSCodeAdapter
  private readonly subscribers = new Set<(event: { eventType: string; data: Record<string, unknown> }) => void>()

  constructor(private readonly capabilityRuntime: ICapabilityRuntime, workspaceRoot: string) {
    this.adapter = new VSCodeAdapter({ workspaceRoot })
  }

  start(): void {
    this.adapter.start()
  }

  stop(): void {
    this.adapter.stop()
  }

  getAdapter(): VSCodeAdapter {
    return this.adapter
  }

  registerHandlers(invoker: IExecutionInvoker): void {
    const emit = (eventType: string, data: Record<string, unknown>) => {
      this.publish(eventType, data)
    }
    const ctx = createVSCodeHandlers(this.adapter, emit)

    invoker.register('vscode.editor.active', wrapHandler(ctx, handleVSCodeEditorActive(ctx)))
    invoker.register('vscode.workspace.folders', wrapHandler(ctx, handleVSCodeWorkspaceFolders(ctx)))
    invoker.register('vscode.diagnostics', wrapHandler(ctx, handleVSCodeDiagnostics(ctx)))
    invoker.register('vscode.git.status', wrapHandler(ctx, handleVSCodeGitStatus(ctx)))
  }

  registerDescriptors(capabilityRuntime: ICapabilityRuntime): void {
    for (const cap of VSCODE_CAPABILITIES) {
      capabilityRuntime.register({
        id: cap.id,
        name: cap.name,
        description: cap.description,
        category: cap.category,
        permissions: cap.permissions as any,
        inputSchema: cap.inputSchema as any,
        outputSchema: cap.outputSchema as any,
        availability: 'available',
        latencyEstimateMs: cap.latencyEstimateMs,
        location: cap.location,
        cost: 0,
        enabled: true,
        source: 'vscode-pack',
        tags: ['vscode', 'read-only']
      })
    }
  }

  subscribe(listener: (event: { eventType: string; data: Record<string, unknown> }) => void): () => void {
    this.subscribers.add(listener)
    return () => { this.subscribers.delete(listener) }
  }

  private publish(eventType: string, data: Record<string, unknown>): void {
    for (const listener of this.subscribers) {
      try { listener({ eventType, data }) } catch { /* subscriber errors must not break operations */ }
    }
  }
}

function wrapHandler(_ctx: VSCodeHandlerContext, handler: ExecutionHandler): ExecutionHandler {
  return (req, ctx, controls) => handler(req, ctx, controls)
}

export function buildVSCodeRollback(): ExecutionRollback {
  return (_req, _ctx) => {
    // Read-only capabilities do not require rollback.
  }
}
