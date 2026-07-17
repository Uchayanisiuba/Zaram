// desktop/tests/capabilities/vscode/vscode-handler.test.ts
//
// Sprint 2.3 — VS Code Handler tests.

import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { ExecutionRequest, ExecutionContext, ExecutionControls } from '../../../src/runtime/execution'
import { createVSCodeHandlers, handleVSCodeEditorActive, handleVSCodeWorkspaceFolders, handleVSCodeDiagnostics, handleVSCodeGitStatus } from '../../../src/capabilities/vscode/vscode-handler'
import type { VSCodeAdapter } from '../../../src/capabilities/vscode/vscode-adapter'

function createMockAdapter(overrides: any = {}): VSCodeAdapter {
  return {
    getEditorInfo: () => overrides.editor ?? { activeFile: 'test.ts', language: 'TypeScript', cursorPosition: null, selectedText: null },
    getWorkspaceFolders: () => overrides.folders ?? [],
    getDiagnostics: () => overrides.diagnostics ?? [],
    getGitStatus: () => overrides.git ?? { branch: 'main', changedFiles: [], stagedFiles: [], ahead: 0, behind: 0 }
  } as unknown as VSCodeAdapter
}

function createMockControls() {
  const calls: Array<{ type: string; value?: any; output?: any; error?: any }> = []
  const controls: ExecutionControls = {
    reportProgress: (p: number) => calls.push({ type: 'progress', value: p }),
    succeed: (output: any) => calls.push({ type: 'succeed', output }),
    fail: (error: any) => calls.push({ type: 'fail', error }),
    isCancelled: () => false,
    elapsedMs: () => 0
  }
  return { controls, calls }
}

describe('VS Code Handlers', () => {
  let ctx: ReturnType<typeof createVSCodeHandlers>
  let emit: ReturnType<typeof vi.fn>

  beforeEach(() => {
    emit = vi.fn()
    ctx = createVSCodeHandlers(createMockAdapter(), emit)
  })

  it('handleVSCodeEditorActive should return editor info', async () => {
    const { controls, calls } = createMockControls()
    const request = { capabilityId: 'vscode.editor.active', input: null, context: {} as ExecutionContext, id: '1', options: {} }
    await handleVSCodeEditorActive(ctx)(request, {} as ExecutionContext, controls)

    const succeed = calls.find(c => c.type === 'succeed')
    expect(succeed).toBeDefined()
    expect(succeed!.output.activeFile).toBe('test.ts')
    expect(succeed!.output.language).toBe('TypeScript')
  })

  it('handleVSCodeWorkspaceFolders should return folders', async () => {
    const mockAdapter = createMockAdapter({ folders: [{ uri: '/workspace', name: 'Zaram' }] })
    const localCtx = createVSCodeHandlers(mockAdapter, emit)
    const { controls, calls } = createMockControls()
    const request = { capabilityId: 'vscode.workspace.folders', input: null, context: {} as ExecutionContext, id: '1', options: {} }
    await handleVSCodeWorkspaceFolders(localCtx)(request, {} as ExecutionContext, controls)

    const succeed = calls.find(c => c.type === 'succeed')
    expect(succeed).toBeDefined()
    expect(succeed!.output.length).toBe(1)
    expect(succeed!.output[0].name).toBe('Zaram')
  })

  it('handleVSCodeDiagnostics should return diagnostics', async () => {
    const mockAdapter = createMockAdapter({ diagnostics: [{ file: 'test.ts', line: 1, character: 1, message: 'error', severity: 'error', source: 'tsc' }] })
    const localCtx = createVSCodeHandlers(mockAdapter, emit)
    const { controls, calls } = createMockControls()
    const request = { capabilityId: 'vscode.diagnostics', input: null, context: {} as ExecutionContext, id: '1', options: {} }
    await handleVSCodeDiagnostics(localCtx)(request, {} as ExecutionContext, controls)

    const succeed = calls.find(c => c.type === 'succeed')
    expect(succeed).toBeDefined()
    expect(succeed!.output.length).toBe(1)
    expect(succeed!.output[0].message).toBe('error')
  })

  it('handleVSCodeGitStatus should return git status', async () => {
    const mockAdapter = createMockAdapter({ git: { branch: 'feature/vscode', changedFiles: ['a.ts'], stagedFiles: ['b.ts'], ahead: 1, behind: 0 } })
    const localCtx = createVSCodeHandlers(mockAdapter, emit)
    const { controls, calls } = createMockControls()
    const request = { capabilityId: 'vscode.git.status', input: null, context: {} as ExecutionContext, id: '1', options: {} }
    await handleVSCodeGitStatus(localCtx)(request, {} as ExecutionContext, controls)

    const succeed = calls.find(c => c.type === 'succeed')
    expect(succeed).toBeDefined()
    expect(succeed!.output.branch).toBe('feature/vscode')
    expect(succeed!.output.changedFiles.length).toBe(1)
  })
})
