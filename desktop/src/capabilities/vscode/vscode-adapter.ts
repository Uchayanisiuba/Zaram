// desktop/src/capabilities/vscode/vscode-adapter.ts
//
// Sprint 2.3 — VS Code Adapter.
//
// Event-driven read-only observer of the developer's VS Code context.
// It watches the filesystem for VS Code artifacts and workspace changes,
// derives a lightweight VSCodeContextSnapshot, and publishes discrete events.
// It never executes capabilities, never imports the drawing layer, and never
// touches the renderer.

import { existsSync, statSync, readdirSync, readFileSync } from 'fs'
import { execSync } from 'child_process'
import { join, dirname, basename, extname, relative } from 'path'
import type {
  VSCodeContextSnapshot,
  VSCodeDiagnostic,
  VSCodeEditorInfo,
  VSCodeEvent,
  VSCodeEventType,
  VSCodeGitStatus,
  VSCodeWorkspaceFolder,
  VSCodeEventListener
} from './vscode-types'

export interface VSCodeAdapterOptions {
  workspaceRoot: string
  now?: () => number
}

interface FileWatch {
  path: string
  recursive?: boolean
}

export class VSCodeAdapter {
  private readonly workspaceRoot: string
  private readonly now: () => number
  private readonly listeners = new Set<VSCodeEventListener>()

  private editor: VSCodeEditorInfo = {
    activeFile: null,
    language: null,
    cursorPosition: null,
    selectedText: null
  }

  private workspaceFolders: VSCodeWorkspaceFolder[] = []
  private diagnostics: VSCodeDiagnostic[] = []
  private gitStatus: VSCodeGitStatus = {
    branch: null,
    changedFiles: [],
    stagedFiles: [],
    ahead: 0,
    behind: 0
  }

  private connected = false
  private revision = 0
  private eventSeq = 0
  private watchers: FileWatch[] = []
  private lastActiveFileMtime = 0
  private diagnosticsTimer: ReturnType<typeof setTimeout> | null = null

  constructor(options: VSCodeAdapterOptions) {
    this.workspaceRoot = options.workspaceRoot
    this.now = options.now ?? (() => Date.now())
  }

  // --- Lifecycle -----------------------------------------------------------

  start(): void {
    if (this.connected) return
    this.connected = true
    this.detectWorkspaceFolders()
    this.detectGitBranch()
    this.refreshGitStatus()
    this.detectActiveFile()
    this.collectDiagnostics()
    this.watchFilesystem()
    this.emit('vscode.connected', { connected: true, workspace: this.workspaceRoot })
  }

  stop(): void {
    if (!this.connected) return
    this.connected = false
    this.watchers = []
    this.emit('vscode.disconnected', { workspace: this.workspaceRoot })
  }

  // --- Public read-only API ------------------------------------------------

  getEditorInfo(): Readonly<VSCodeEditorInfo> {
    return { ...this.editor }
  }

  getWorkspaceFolders(): VSCodeWorkspaceFolder[] {
    return [...this.workspaceFolders]
  }

  getDiagnostics(): VSCodeDiagnostic[] {
    return [...this.diagnostics]
  }

  getGitStatus(): Readonly<VSCodeGitStatus> {
    return { ...this.gitStatus }
  }

  getSnapshot(): Readonly<VSCodeContextSnapshot> {
    return {
      workspace: basename(this.workspaceRoot) || this.workspaceRoot,
      activeFile: this.editor.activeFile,
      language: this.editor.language,
      selection: this.editor.selectedText,
      diagnostics: this.diagnostics.length,
      gitBranch: this.gitStatus.branch,
      modifiedFiles: this.gitStatus.changedFiles.length,
      connected: this.connected
    }
  }

  subscribe(listener: VSCodeEventListener): () => void {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  getRevision(): number {
    return this.revision
  }

  // --- Internals ------------------------------------------------------------

  private watchFilesystem(): void {
    const vscodeDir = join(this.workspaceRoot, '.vscode')
    if (existsSync(vscodeDir)) {
      this.watchers.push({ path: vscodeDir, recursive: true })
    }

    const gitDir = join(this.workspaceRoot, '.git')
    if (existsSync(gitDir)) {
      this.watchers.push({ path: gitDir, recursive: true })
    }

    this.watchers.push({ path: this.workspaceRoot, recursive: false })

    const fs = require('fs')
    for (const watch of this.watchers) {
      try {
        fs.watch(watch.path, { recursive: Boolean(watch.recursive) }, (eventType: string, filename: string) => {
          if (!filename) return
          this.handleFilesystemEvent(eventType, filename)
        })
      } catch {
        // ignore watch errors
      }
    }
  }

  private handleFilesystemEvent(eventType: string, filename: string): void {
    if (!this.connected) return
    const fullPath = join(this.workspaceRoot, filename)
    const ext = extname(filename).toLowerCase()

    if (filename.startsWith('.vscode' + require('path').sep) || filename === '.vscode') {
      this.detectWorkspaceFolders()
      this.emit('vscode.active_file_changed', { source: 'vscode-settings', path: fullPath })
    }

    if (filename.startsWith('.git' + require('path').sep) || filename === '.git') {
      this.refreshGitStatus()
      this.emit('vscode.git_status_refreshed', { source: 'git-change', path: fullPath })
    }

    if (eventType === 'change' || eventType === 'rename') {
      const isSource = ['.ts', '.tsx', '.js', '.jsx', '.py', '.rs', '.go', '.java', '.c', '.cpp', '.h'].includes(ext)
      if (isSource) {
        this.trackActiveFile(fullPath)
        this.scheduleDiagnostics(fullPath)
      }
    }
  }

  private trackActiveFile(fullPath: string): void {
    try {
      const stats = statSync(fullPath)
      if (stats.mtimeMs > this.lastActiveFileMtime) {
        this.lastActiveFileMtime = stats.mtimeMs
        const rel = relative(this.workspaceRoot, fullPath)
        const language = this.languageFromExtension(extname(fullPath))
        this.editor = {
          activeFile: rel,
          language,
          cursorPosition: null,
          selectedText: null
        }
        this.bump()
        this.emit('vscode.active_file_changed', { file: rel, language })
      }
    } catch {
      // ignore
    }
  }

  private detectActiveFile(): void {
    let latest = { path: '' as string, mtime: 0 }
    const sourceExtensions = ['.ts', '.tsx', '.js', '.jsx', '.py', '.rs', '.go', '.java', '.c', '.cpp', '.h']

    const walk = (dir: string) => {
      if (!existsSync(dir)) return
      try {
        const entries = readdirSync(dir)
        for (const entry of entries) {
          if (entry.startsWith('.') && entry !== '.vscode') continue
          const full = join(dir, entry)
          try {
            const stats = statSync(full)
            if (stats.isFile() && sourceExtensions.includes(extname(entry).toLowerCase())) {
              if (stats.mtimeMs > latest.mtime) {
                latest = { path: full, mtime: stats.mtimeMs }
              }
            } else if (stats.isDirectory()) {
              walk(full)
            }
          } catch {
            // skip
          }
        }
      } catch {
        // skip
      }
    }

    walk(this.workspaceRoot)
    if (latest.path) {
      this.lastActiveFileMtime = latest.mtime
      const rel = relative(this.workspaceRoot, latest.path)
      this.editor = {
        activeFile: rel,
        language: this.languageFromExtension(extname(latest.path)),
        cursorPosition: null,
        selectedText: null
      }
      this.bump()
    }
  }

  private detectWorkspaceFolders(): void {
    const vscodeSettings = join(this.workspaceRoot, '.vscode', 'settings.json')
    const folders: VSCodeWorkspaceFolder[] = []

    if (existsSync(vscodeSettings)) {
      try {
        const content = readFileSync(vscodeSettings, 'utf-8')
        const settings = JSON.parse(content)
        if (settings['vscode-folders']) {
          for (const uri of settings['vscode-folders']) {
            folders.push({ uri, name: basename(uri) })
          }
        }
      } catch {
        // ignore parse errors
      }
    }

    if (folders.length === 0) {
      folders.push({ uri: this.workspaceRoot, name: basename(this.workspaceRoot) || 'root' })
    }

    this.workspaceFolders = folders
    this.bump()
  }

  private detectGitBranch(): void {
    const gitHead = join(this.workspaceRoot, '.git', 'HEAD')
    if (!existsSync(gitHead)) {
      this.gitStatus.branch = null
      return
    }
    try {
      const head = readFileSync(gitHead, 'utf-8').trim()
      const match = head.match(/ref: refs\/heads\/(.+)/)
      this.gitStatus.branch = match ? match[1] : null
    } catch {
      this.gitStatus.branch = null
    }
  }

  private refreshGitStatus(): void {
    const changed: string[] = []
    const staged: string[] = []

    try {
      const output = this.runCommand('git', ['status', '--porcelain'])
      const lines = output.split('\n').filter((l) => l.trim())
      for (const line of lines) {
        const status = line.slice(0, 2)
        const file = line.slice(3)
        if (status.includes('M') || status.includes('A') || status.includes('D') || status.includes('R') || status.includes('C') || status.includes('U')) {
          changed.push(file)
        }
        if (status.includes('A') || status.includes('M')) {
          staged.push(file)
        }
      }
    } catch {
      // git not available or not a repo
    }

    this.gitStatus.changedFiles = changed
    this.gitStatus.stagedFiles = staged
    this.detectGitBranch()
    this.bump()
    this.emit('vscode.git_status_refreshed', {
      branch: this.gitStatus.branch,
      changedFiles: changed.length,
      stagedFiles: staged.length
    })
  }

  private collectDiagnostics(): void {
    const diagnostics: VSCodeDiagnostic[] = []
    const tsconfig = join(this.workspaceRoot, 'tsconfig.json')

    if (!existsSync(tsconfig)) {
      this.diagnostics = diagnostics
      this.bump()
      return
    }

    try {
      const tscPath = require.resolve('typescript/bin/tsc')
      const output = this.runCommand('node', [tscPath, '--noEmit', '--project', this.workspaceRoot])
      const lines = output.split('\n')
      for (const line of lines) {
        const match = line.match(/^(.+)\((\d+),(\d+)\):\s+(error|warning)\s+TS\d+:\s+(.+)$/)
        if (match) {
          diagnostics.push({
            file: relative(this.workspaceRoot, match[1]),
            line: Number(match[2]),
            character: Number(match[3]),
            message: match[5],
            severity: match[4] as 'error' | 'warning',
            source: 'tsc'
          })
        }
      }
    } catch (output) {
      const errOut = typeof output === 'string' ? output : String(output)
      const lines = errOut.split('\n')
      for (const line of lines) {
        const match = line.match(/^(.+)\((\d+),(\d+)\):\s+(error|warning)\s+TS\d+:\s+(.+)$/)
        if (match) {
          diagnostics.push({
            file: relative(this.workspaceRoot, match[1]),
            line: Number(match[2]),
            character: Number(match[3]),
            message: match[5],
            severity: match[4] as 'error' | 'warning',
            source: 'tsc'
          })
        }
      }
    }

    this.diagnostics = diagnostics
    this.bump()
    this.emit('vscode.diagnostics_updated', { count: diagnostics.length })
  }

  private scheduleDiagnostics(_path: string): void {
    if (this.diagnosticsTimer) clearTimeout(this.diagnosticsTimer)
    this.diagnosticsTimer = setTimeout(() => {
      this.collectDiagnostics()
      this.diagnosticsTimer = null
    }, 500)
  }

  private runCommand(command: string, args: string[]): string {
    return execSync(`${JSON.stringify(command)} ${args.map(a => JSON.stringify(a)).join(' ')}`, {
      cwd: this.workspaceRoot,
      encoding: 'utf-8',
      stdio: ['pipe', 'pipe', 'pipe']
    }).toString()
  }

  private languageFromExtension(ext: string): string | null {
    const map: Record<string, string> = {
      '.ts': 'TypeScript',
      '.tsx': 'TypeScript React',
      '.js': 'JavaScript',
      '.jsx': 'JavaScript React',
      '.py': 'Python',
      '.rs': 'Rust',
      '.go': 'Go',
      '.java': 'Java',
      '.c': 'C',
      '.cpp': 'C++',
      '.h': 'C/C++ Header',
      '.json': 'JSON',
      '.md': 'Markdown'
    }
    return map[ext.toLowerCase()] || null
  }

  private bump(): void {
    this.revision += 1
    this.emit('vscode.context_provided', { snapshot: this.getSnapshot() })
  }

  private emit(type: VSCodeEventType, data: Record<string, unknown>): void {
    const event: VSCodeEvent = {
      type,
      timestamp: this.now(),
      data: { ...data, revision: this.revision }
    }
    for (const listener of this.listeners) {
      try {
        listener(event)
      } catch {
        // subscriber errors must not break the adapter
      }
    }
  }
}
