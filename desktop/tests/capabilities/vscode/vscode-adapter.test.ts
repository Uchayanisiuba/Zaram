// desktop/tests/capabilities/vscode/vscode-adapter.test.ts
//
// Sprint 2.3 — VS Code Adapter tests.

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { VSCodeAdapter } from '../../../src/capabilities/vscode/vscode-adapter'

describe('VS Code Adapter', () => {
  let adapter: VSCodeAdapter

  beforeEach(() => {
    adapter = new VSCodeAdapter({ workspaceRoot: '/tmp/workspace', now: () => 1000 })
  })

  it('should start and emit connected event', () => {
    const events: any[] = []
    adapter.subscribe((e) => events.push(e))

    adapter.start()

    const connected = events.find(e => e.type === 'vscode.connected')
    expect(connected).toBeDefined()
    expect(connected.data.connected).toBe(true)
    expect(adapter.getSnapshot().connected).toBe(true)
  })

  it('should detect workspace folders from .vscode/settings.json', () => {
    const fs = require('fs')
    const path = require('path')
    const tmpDir = '/tmp/vscode-test-' + Date.now()
    fs.mkdirSync(tmpDir, { recursive: true })
    fs.mkdirSync(path.join(tmpDir, '.vscode'), { recursive: true })
    fs.writeFileSync(path.join(tmpDir, '.vscode', 'settings.json'), JSON.stringify({ 'vscode-folders': ['/workspace1', '/workspace2'] }))

    const localAdapter = new VSCodeAdapter({ workspaceRoot: tmpDir, now: () => 1000 })
    localAdapter.start()

    const folders = localAdapter.getWorkspaceFolders()
    expect(folders.length).toBe(2)
    expect(folders[0].uri).toBe('/workspace1')

    fs.rmSync(tmpDir, { recursive: true })
  })

  it('should detect git branch from .git/HEAD', () => {
    const fs = require('fs')
    const path = require('path')
    const tmpDir = '/tmp/vscode-git-test-' + Date.now()
    fs.mkdirSync(tmpDir, { recursive: true })
    fs.mkdirSync(path.join(tmpDir, '.git'), { recursive: true })
    fs.writeFileSync(path.join(tmpDir, '.git', 'HEAD'), 'ref: refs/heads/main\n')

    const localAdapter = new VSCodeAdapter({ workspaceRoot: tmpDir, now: () => 1000 })
    localAdapter.start()

    expect(localAdapter.getGitStatus().branch).toBe('main')

    fs.rmSync(tmpDir, { recursive: true })
  })

  it('should track active file when a source file is modified', () => {
    const fs = require('fs')
    const path = require('path')
    const tmpDir = '/tmp/vscode-active-test-' + Date.now()
    fs.mkdirSync(tmpDir, { recursive: true })
    fs.writeFileSync(path.join(tmpDir, 'src.ts'), 'const x = 1')

    const localAdapter = new VSCodeAdapter({ workspaceRoot: tmpDir, now: () => 1000 })
    localAdapter.start()

    expect(localAdapter.getEditorInfo().activeFile).toBe('src.ts')
    expect(localAdapter.getEditorInfo().language).toBe('TypeScript')

    fs.rmSync(tmpDir, { recursive: true })
  })

  it('should emit context_provided when state changes', () => {
    const events: any[] = []
    adapter.subscribe((e) => events.push(e))

    adapter.start()

    const contextEvents = events.filter(e => e.type === 'vscode.context_provided')
    expect(contextEvents.length).toBeGreaterThan(0)
    expect(contextEvents[0].data.snapshot).toBeDefined()
  })

  it('should stop and emit disconnected event', () => {
    const events: any[] = []
    adapter.subscribe((e) => events.push(e))

    adapter.start()
    adapter.stop()

    const disconnected = events.find(e => e.type === 'vscode.disconnected')
    expect(disconnected).toBeDefined()
    expect(adapter.getSnapshot().connected).toBe(false)
  })
})
