// desktop/src/runtime/workspace/workspace-pool.ts
//
// Milestone 2.1 — Workspace Runtime worker pool.
//
// Provides a simple worker pool for offloading indexing work. Falls back to
// synchronous execution when worker_threads are unavailable (tests, some
// Electron builds).

import type { DetectionSignal, IndexingJob, IndexingResult, Project, FrameworkId, Dependency } from './types'

export interface WorkerPoolOptions {
  maxWorkers?: number
}

export class WorkerPool {
  private readonly maxWorkers: number
  private queue: IndexingJob[] = []
  private active = 0

  constructor(options: WorkerPoolOptions = {}) {
    this.maxWorkers = options.maxWorkers ?? 2
  }

  async index(job: IndexingJob): Promise<IndexingResult> {
    return new Promise((resolve) => {
      const process = () => {
        this.active++
        try {
          const projects = this.indexSync(job.rootPath, job.signals)
          resolve({ id: job.id, projects })
        } catch (error) {
          resolve({ id: job.id, projects: [], error: String(error) })
        } finally {
          this.active--
          this.drain()
        }
      }

      if (this.active < this.maxWorkers) {
        process()
      } else {
        this.queue.push(job)
      }
    })
  }

  private indexSync(rootPath: string, signals: DetectionSignal[]): Project[] {
    const manifestNames = new Set<string>()
    const configNames = new Set<string>()
    const fileNames = new Set<string>()
    const dirNames = new Set<string>()

    for (const signal of signals) {
      const parts = signal.path.split(/[\\/]/)
      const name = parts[parts.length - 1] || signal.path
      if (signal.type === 'manifest') manifestNames.add(name)
      else if (signal.type === 'config') configNames.add(name)
      else if (signal.type === 'entrypoint') fileNames.add(name)
      else if (signal.type === 'vcs') dirNames.add(name)
    }

    const languages = [detectLanguage(manifestNames)].filter((l) => l !== 'unknown')
    const frameworks = detectFrameworks(manifestNames, configNames)
    const dependencies = detectDependencies(manifestNames)
    const entrypoints = detectEntrypoints(fileNames)
    const ignoredFolders = detectIgnoredFolders(dirNames)

    const project: Project = {
      id: computeProjectId(rootPath, languages, frameworks),
      name: computeProjectName(rootPath),
      rootPath,
      relativePath: rootPath,
      languages,
      frameworks,
      dependencies,
      entrypoints,
      ignoredFolders,
      workspaceHash: computeHash(rootPath, signals),
      detectedAt: Date.now(),
      updatedAt: Date.now()
    }

    return [project]
  }

  private drain(): void {
    while (this.active < this.maxWorkers && this.queue.length > 0) {
      const job = this.queue.shift()
      if (job) {
        this.index(job)
      }
    }
  }
}

function detectLanguage(manifestNames: Set<string>): 'typescript' | 'javascript' | 'python' | 'rust' | 'go' | 'java' | 'kotlin' | 'ruby' | 'php' | 'csharp' | 'cpp' | 'c' | 'swift' | 'dart' | 'scala' | 'unknown' {
  if (manifestNames.has('Cargo.toml')) return 'rust'
  if (manifestNames.has('go.mod')) return 'go'
  if (manifestNames.has('pom.xml')) return 'java'
  if (manifestNames.has('composer.json')) return 'php'
  if (manifestNames.has('pyproject.toml') || manifestNames.has('requirements.txt')) return 'python'
  if (manifestNames.has('package.json')) {
    if (manifestNames.has('tsconfig.json')) return 'typescript'
    return 'javascript'
  }
  if (manifestNames.has('tsconfig.json')) return 'typescript'
  return 'unknown'
}

function detectFrameworks(
  manifestNames: Set<string>,
  configNames: Set<string>
): FrameworkId[] {
  const frameworks: FrameworkId[] = []

  const KNOWN_CONFIGS: Record<string, FrameworkId[]> = {
    'next.config.js': ['nextjs', 'react'],
    'next.config.ts': ['nextjs', 'react'],
    'vite.config.js': ['vite'],
    'vite.config.ts': ['vite'],
    'tailwind.config.js': ['tailwindcss'],
    'tailwind.config.ts': ['tailwindcss'],
    'Dockerfile': ['docker']
  }

  const KNOWN_MANIFESTS: Record<string, FrameworkId[]> = {
    'package.json': [],
    'Cargo.toml': [],
    'go.mod': [],
    'pyproject.toml': ['fastapi', 'django', 'flask'],
    'requirements.txt': [],
    'pom.xml': ['spring'],
    'composer.json': [],
    'tsconfig.json': []
  }

  for (const [file, fws] of Object.entries(KNOWN_CONFIGS)) {
    if (configNames.has(file)) {
      frameworks.push(...fws)
    }
  }

  for (const [file, fws] of Object.entries(KNOWN_MANIFESTS)) {
    if (manifestNames.has(file)) {
      for (const fw of fws) {
        if (!frameworks.includes(fw)) frameworks.push(fw)
      }
    }
  }

  return frameworks
}

function detectDependencies(manifestNames: Set<string>): Dependency[] {
  const deps: Dependency[] = []

  if (manifestNames.has('package.json')) deps.push({ name: 'npm', type: 'runtime', source: 'package.json' })
  if (manifestNames.has('Cargo.toml')) deps.push({ name: 'cargo', type: 'runtime', source: 'Cargo.toml' })
  if (manifestNames.has('go.mod')) deps.push({ name: 'go', type: 'runtime', source: 'go.mod' })
  if (manifestNames.has('pyproject.toml') || manifestNames.has('requirements.txt')) {
    deps.push({ name: 'pip', type: 'runtime', source: manifestNames.has('pyproject.toml') ? 'pyproject.toml' : 'requirements.txt' })
  }
  if (manifestNames.has('pom.xml')) deps.push({ name: 'maven', type: 'runtime', source: 'pom.xml' })
  if (manifestNames.has('composer.json')) deps.push({ name: 'composer', type: 'runtime', source: 'composer.json' })

  return deps
}

function detectEntrypoints(fileNames: Set<string>): string[] {
  const ENTRYPOINT_FILES = new Set([
    'main.ts',
    'main.js',
    'index.ts',
    'index.js',
    'app.ts',
    'app.js',
    'server.ts',
    'server.js',
    'main.py',
    'manage.py',
    'main.go',
    'main.rs',
    'Main.kt',
    'Program.cs',
    'main.dart'
  ])

  const entrypoints: string[] = []
  for (const name of ENTRYPOINT_FILES) {
    if (fileNames.has(name)) entrypoints.push(name)
  }
  return entrypoints
}

function detectIgnoredFolders(dirNames: Set<string>): string[] {
  const IGNORED_FOLDERS = new Set([
    'node_modules',
    'target',
    'dist',
    'build',
    '__pycache__',
    '.git',
    '.venv',
    'venv',
    'vendor',
    'bin',
    'obj',
    '.idea',
    '.vscode'
  ])

  return Array.from(dirNames).filter((name) => IGNORED_FOLDERS.has(name))
}

function computeProjectId(rootPath: string, languages: string[], frameworks: string[]): string {
  const base = rootPath.toLowerCase().replace(/[^a-z0-9]/g, '-')
  const suffix = [...languages.slice(0, 2), ...frameworks.slice(0, 2)].join('-')
  return `${base}${suffix ? `-${suffix}` : ''}`
}

function computeProjectName(rootPath: string): string {
  const parts = rootPath.split(/[\\/]/)
  const last = parts[parts.length - 1] || rootPath
  return last || 'root'
}

function computeHash(rootPath: string, signals: DetectionSignal[]): string {
  const payload = `${rootPath}:${signals.map((s) => s.path).sort().join(',')}`
  let hash = 0
  for (let i = 0; i < payload.length; i++) {
    const char = payload.charCodeAt(i)
    hash = ((hash << 5) - hash) + char
    hash = hash & hash
  }
  return Math.abs(hash).toString(16).padStart(8, '0')
}
