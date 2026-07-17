// desktop/tests/runtime/executive/vscode-context.test.ts
//
// Sprint 2.3 — VS Code context ingestion into Executive Runtime.

import { describe, it, expect, beforeEach } from 'vitest'
import { ExecutiveRuntime } from '../../../src/runtime/executive/executive-runtime'

describe('ExecutiveRuntime VS Code context', () => {
  let runtime: ExecutiveRuntime

  beforeEach(() => {
    runtime = new ExecutiveRuntime()
  })

  it('should ingest VS Code context and update state', () => {
    runtime.ingestVSCodeContext({
      workspace: 'Zaram',
      activeFile: 'workspace-runtime.ts',
      language: 'TypeScript',
      selection: 'WorkspaceSnapshot',
      diagnostics: 2,
      gitBranch: 'feature/workspace-runtime',
      modifiedFiles: 4,
      connected: true
    })

    const signal = runtime.getVSCodeSignal()
    expect(signal.workspace).toBe('Zaram')
    expect(signal.activeFile).toBe('workspace-runtime.ts')
    expect(signal.language).toBe('TypeScript')
    expect(signal.diagnostics).toBe(2)
    expect(signal.gitBranch).toBe('feature/workspace-runtime')
    expect(signal.modifiedFiles).toBe(4)
    expect(signal.connected).toBe(true)
  })

  it('should merge partial VS Code signals', () => {
    runtime.ingestVSCodeContext({ activeFile: 'a.ts', diagnostics: 1 })
    runtime.ingestVSCodeContext({ activeFile: 'b.ts', diagnostics: 2 })

    const signal = runtime.getVSCodeSignal()
    expect(signal.activeFile).toBe('b.ts')
    expect(signal.diagnostics).toBe(2)
  })

  it('should reset VS Code context on reset()', () => {
    runtime.ingestVSCodeContext({ workspace: 'Zaram', activeFile: 'test.ts' })
    runtime.reset()

    const signal = runtime.getVSCodeSignal()
    expect(signal.workspace).toBeUndefined()
    expect(signal.activeFile).toBeUndefined()
  })
})
