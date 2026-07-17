// desktop/src/runtime/workspace/workspace-detector.ts
//
// Milestone 2.1 — Workspace Runtime detector.
//
// Detects languages, frameworks, dependencies, and entrypoints from project
// manifest files and directory structure. Pure functions; no side effects.

import type {
  LanguageId,
  FrameworkId,
  Dependency,
  Project,
  DetectionSignal
} from './types'

const KNOWN_MANIFESTS: Record<string, { language: LanguageId; frameworks: FrameworkId[] }> = {
  'package.json': { language: 'javascript', frameworks: [] },
  'Cargo.toml': { language: 'rust', frameworks: [] },
  'go.mod': { language: 'go', frameworks: [] },
  'pyproject.toml': { language: 'python', frameworks: ['fastapi', 'django', 'flask'] },
  'requirements.txt': { language: 'python', frameworks: [] },
  'pom.xml': { language: 'java', frameworks: ['spring'] },
  'composer.json': { language: 'php', frameworks: [] },
  'tsconfig.json': { language: 'typescript', frameworks: [] },
}

const KNOWN_CONFIGS: Record<string, { frameworks: FrameworkId[] }> = {
  'next.config.js': { frameworks: ['nextjs', 'react'] },
  'next.config.ts': { frameworks: ['nextjs', 'react'] },
  'vite.config.js': { frameworks: ['vite'] },
  'vite.config.ts': { frameworks: ['vite'] },
  'tailwind.config.js': { frameworks: ['tailwindcss'] },
  'tailwind.config.ts': { frameworks: ['tailwindcss'] },
  'Dockerfile': { frameworks: ['docker'] },
}

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

export const PROTECTED_PATTERNS = [
  '.env',
  '.pem',
  '.key',
  '.ssh',
  '.aws',
  '.git'
]

export const SKIPPED_PATTERNS = [
  'node_modules',
  'dist',
  'build',
  'target',
  'venv',
  '.venv',
  '__pycache__',
  'vendor',
  'bin',
  'obj',
  '.idea',
  '.vscode'
]

export function detectLanguage(manifestNames: Set<string>): LanguageId {
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

export function detectFrameworks(
  manifestNames: Set<string>,
  configNames: Set<string>
): FrameworkId[] {
  const frameworks: FrameworkId[] = []

  for (const [file, data] of Object.entries(KNOWN_CONFIGS)) {
    if (configNames.has(file)) {
      frameworks.push(...data.frameworks)
    }
  }

  for (const [file, data] of Object.entries(KNOWN_MANIFESTS)) {
    if (manifestNames.has(file)) {
      for (const fw of data.frameworks) {
        if (!frameworks.includes(fw)) frameworks.push(fw)
      }
    }
  }

  return frameworks
}

export function detectDependencies(manifestNames: Set<string>): Dependency[] {
  const deps: Dependency[] = []

  if (manifestNames.has('package.json')) {
    deps.push({ name: 'npm', version: undefined, type: 'runtime', source: 'package.json' })
  }
  if (manifestNames.has('Cargo.toml')) {
    deps.push({ name: 'cargo', version: undefined, type: 'runtime', source: 'Cargo.toml' })
  }
  if (manifestNames.has('go.mod')) {
    deps.push({ name: 'go', version: undefined, type: 'runtime', source: 'go.mod' })
  }
  if (manifestNames.has('pyproject.toml') || manifestNames.has('requirements.txt')) {
    deps.push({ name: 'pip', version: undefined, type: 'runtime', source: manifestNames.has('pyproject.toml') ? 'pyproject.toml' : 'requirements.txt' })
  }
  if (manifestNames.has('pom.xml')) {
    deps.push({ name: 'maven', version: undefined, type: 'runtime', source: 'pom.xml' })
  }
  if (manifestNames.has('composer.json')) {
    deps.push({ name: 'composer', version: undefined, type: 'runtime', source: 'composer.json' })
  }

  return deps
}

export function detectEntrypoints(fileNames: Set<string>): string[] {
  const entrypoints: string[] = []
  for (const name of ENTRYPOINT_FILES) {
    if (fileNames.has(name)) entrypoints.push(name)
  }
  return entrypoints
}

export function detectIgnoredFolders(dirNames: Set<string>): string[] {
  return Array.from(dirNames).filter((name) => IGNORED_FOLDERS.has(name))
}

export function buildProjectSignals(
  manifestNames: Set<string>,
  configNames: Set<string>,
  fileNames: Set<string>,
  dirNames: Set<string>
): DetectionSignal[] {
  const signals: DetectionSignal[] = []

  for (const name of manifestNames) {
    const entry = KNOWN_MANIFESTS[name]
    const evidence = [name]
    signals.push({
      path: name,
      type: 'manifest',
      language: entry?.language,
      framework: entry?.frameworks[0],
      confidence: 1,
      evidence
    })
  }

  for (const name of configNames) {
    const entry = KNOWN_CONFIGS[name]
    if (entry) {
      const evidence = [name]
      signals.push({
        path: name,
        type: 'config',
        framework: entry.frameworks[0],
        confidence: 0.9,
        evidence
      })
    }
  }

  if (dirNames.has('.git')) {
    signals.push({ path: '.git', type: 'vcs', confidence: 1, evidence: ['.git'] })
  }

  for (const name of fileNames) {
    if (ENTRYPOINT_FILES.has(name)) {
      signals.push({ path: name, type: 'entrypoint', confidence: 0.8, evidence: [name] })
    }
  }

  return signals
}
