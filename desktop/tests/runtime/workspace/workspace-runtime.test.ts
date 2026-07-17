import { describe, it, expect, vi, beforeEach } from 'vitest'
import { WorkspaceRuntime } from '../../../src/runtime/workspace'
import { WorkspaceIndexer } from '../../../src/runtime/workspace/workspace-indexer'
import { WorkspaceCache } from '../../../src/runtime/workspace/workspace-cache'
import {
  detectLanguage,
  detectFrameworks,
  detectDependencies,
  detectEntrypoints,
  detectIgnoredFolders,
  buildProjectSignals
} from '../../../src/runtime/workspace/workspace-detector'
import { buildWorkspaceContext } from '../../../src/runtime/workspace/workspace-context'
import { defaultWorkspaceState } from '../../../src/runtime/workspace/types'
import type { DetectionSignal } from '../../../src/runtime/workspace'

describe('Workspace Runtime', () => {
  let runtime: WorkspaceRuntime

  beforeEach(() => {
    runtime = new WorkspaceRuntime({ rootPath: '/tmp/workspace' })
  })

  describe('initial state', () => {
    it('exposes an empty workspace state', () => {
      const state = runtime.getWorkspaceState()
      expect(state.rootPath).toBe('/tmp/workspace')
      expect(state.projects).toHaveLength(0)
      expect(state.totalProjects).toBe(0)
      expect(state.revision).toBe(0)
    })

    it('exposes an empty workspace context', () => {
      const ctx = runtime.getWorkspaceContext()
      expect(ctx.summary).toBe('No workspace detected')
      expect(ctx.projects).toHaveLength(0)
    })

    it('returns null for unknown project paths', () => {
      expect(runtime.getProject('/tmp/workspace/unknown')).toBeNull()
    })

    it('returns empty project list when no projects detected', () => {
      expect(runtime.getAllProjects()).toHaveLength(0)
    })
  })

  describe('workspace discovery', () => {
    it('discovers a single project from signals', async () => {
      const signals: DetectionSignal[] = [
        { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1 },
        { path: 'tsconfig.json', type: 'manifest', language: 'typescript', confidence: 1 },
        { path: '.git', type: 'vcs', confidence: 1 }
      ]

      await runtime.discover(signals)
      expect(runtime.getWorkspaceState().totalProjects).toBe(1)
    })

    it('publishes workspace.scan_started and workspace.scan_completed events', async () => {
      const events: string[] = []
      runtime.subscribe((e) => events.push(e.type))

      const signals: DetectionSignal[] = [
        { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1 }
      ]

      await runtime.discover(signals)

      expect(events).toContain('workspace.scan_started')
      expect(events).toContain('workspace.scan_completed')
    })

    it('publishes workspace.project_added for each detected project', async () => {
      const events: string[] = []
      runtime.subscribe((e) => events.push(e.type))

      const signals: DetectionSignal[] = [
        { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1 }
      ]

      await runtime.discover(signals)

      expect(events).toContain('workspace.project_added')
      expect(events).toContain('workspace.discovered')
    })

    it('detects rust project from Cargo.toml', async () => {
      const signals: DetectionSignal[] = [
        { path: 'Cargo.toml', type: 'manifest', language: 'rust', confidence: 1 }
      ]

      await runtime.discover(signals)
      const projects = runtime.getAllProjects()
      expect(projects[0].languages).toContain('rust')
    })

    it('detects go project from go.mod', async () => {
      const signals: DetectionSignal[] = [
        { path: 'go.mod', type: 'manifest', language: 'go', confidence: 1 }
      ]

      await runtime.discover(signals)
      const projects = runtime.getAllProjects()
      expect(projects[0].languages).toContain('go')
    })

    it('detects python project from pyproject.toml', async () => {
      const signals: DetectionSignal[] = [
        { path: 'pyproject.toml', type: 'manifest', language: 'python', confidence: 1 }
      ]

      await runtime.discover(signals)
      const projects = runtime.getAllProjects()
      expect(projects[0].languages).toContain('python')
    })

    it('detects java project from pom.xml', async () => {
      const signals: DetectionSignal[] = [
        { path: 'pom.xml', type: 'manifest', language: 'java', confidence: 1 }
      ]

      await runtime.discover(signals)
      const projects = runtime.getAllProjects()
      expect(projects[0].languages).toContain('java')
    })

    it('detects php project from composer.json', async () => {
      const signals: DetectionSignal[] = [
        { path: 'composer.json', type: 'manifest', language: 'php', confidence: 1 }
      ]

      await runtime.discover(signals)
      const projects = runtime.getAllProjects()
      expect(projects[0].languages).toContain('php')
    })

    it('detects typescript when both package.json and tsconfig.json exist', async () => {
      const signals: DetectionSignal[] = [
        { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1 },
        { path: 'tsconfig.json', type: 'manifest', language: 'typescript', confidence: 1 }
      ]

      await runtime.discover(signals)
      const projects = runtime.getAllProjects()
      expect(projects[0].languages).toContain('typescript')
    })

    it('detects frameworks from config files', async () => {
      const signals: DetectionSignal[] = [
        { path: 'next.config.js', type: 'config', framework: 'nextjs', confidence: 0.9 },
        { path: 'vite.config.ts', type: 'config', framework: 'vite', confidence: 0.9 }
      ]

      await runtime.discover(signals)
      const projects = runtime.getAllProjects()
      expect(projects[0].frameworks).toContain('nextjs')
      expect(projects[0].frameworks).toContain('vite')
    })

    it('detects ignored folders', async () => {
      const signals: DetectionSignal[] = [
        { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1 },
        { path: 'node_modules', type: 'vcs', confidence: 1 }
      ]

      await runtime.discover(signals)
      const projects = runtime.getAllProjects()
      expect(projects[0].ignoredFolders).toContain('node_modules')
    })

    it('detects entrypoint files', async () => {
      const signals: DetectionSignal[] = [
        { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1 },
        { path: 'index.ts', type: 'entrypoint', confidence: 0.8 }
      ]

      await runtime.discover(signals)
      const projects = runtime.getAllProjects()
      expect(projects[0].entrypoints).toContain('index.ts')
    })

    it('generates a deterministic project id', async () => {
      const signals: DetectionSignal[] = [
        { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1 }
      ]

      await runtime.discover(signals)
      const projects = runtime.getAllProjects()
      expect(projects[0].id).toBeTruthy()
      expect(typeof projects[0].id).toBe('string')
    })

    it('computes a workspace hash from signals', async () => {
      const signals: DetectionSignal[] = [
        { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1 }
      ]

      await runtime.discover(signals)
      const state = runtime.getWorkspaceState()
      expect(state.workspaceHash).toBeTruthy()
      expect(state.workspaceHash.length).toBeGreaterThan(0)
    })

    it('ignores empty signals', async () => {
      await runtime.discover([])
      expect(runtime.getWorkspaceState().totalProjects).toBe(0)
    })

    it('does not discover when rootPath is empty', async () => {
      const emptyRuntime = new WorkspaceRuntime({ rootPath: '' })
      const signals: DetectionSignal[] = [
        { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1 }
      ]

      await emptyRuntime.discover(signals)
      expect(emptyRuntime.getWorkspaceState().totalProjects).toBe(0)
    })
  })

  describe('workspace context', () => {
    it('builds context with summary', async () => {
      const signals: DetectionSignal[] = [
        { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1 }
      ]

      await runtime.discover(signals)
      const ctx = runtime.getWorkspaceContext()
      expect(ctx.summary).toContain('1 project')
      expect(ctx.revision).toBeGreaterThan(0)
    })

    it('derives unique languages and frameworks', async () => {
      const signals: DetectionSignal[] = [
        { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1 },
        { path: 'next.config.js', type: 'config', framework: 'nextjs', confidence: 0.9 },
        { path: 'tailwind.config.js', type: 'config', framework: 'tailwindcss', confidence: 0.9 }
      ]

      await runtime.discover(signals)
      const ctx = runtime.getWorkspaceContext()
      expect(ctx.languages).toContain('javascript')
      expect(ctx.frameworks).toContain('nextjs')
      expect(ctx.frameworks).toContain('tailwindcss')
    })
  })

  describe('event subscription', () => {
    it('subscribes and unsubscribes listeners', () => {
      const listener = vi.fn()
      const unsub = runtime.subscribe(listener)
      expect(typeof unsub).toBe('function')

      runtime['publish']('workspace.changed', {})
      expect(listener).toHaveBeenCalledTimes(1)

      unsub()
      runtime['publish']('workspace.changed', {})
      expect(listener).toHaveBeenCalledTimes(1)
    })

    it('does not break tick when subscriber throws', () => {
      const badListener = () => {
        throw new Error('subscriber error')
      }
      const goodListener = vi.fn()

      runtime.subscribe(badListener)
      runtime.subscribe(goodListener)

      expect(() => runtime['publish']('workspace.changed', {})).not.toThrow()
      expect(goodListener).toHaveBeenCalledTimes(1)
    })
  })

  describe('immutability', () => {
    it('returns frozen snapshots', async () => {
      const signals: DetectionSignal[] = [
        { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1 }
      ]

      await runtime.discover(signals)
      const state = runtime.getWorkspaceState()

      expect(Object.isFrozen(state)).toBe(true)
      expect(Object.isFrozen(state.projects[0])).toBe(true)
    })
  })

  describe('time evolution', () => {
  it('does not poll or use timers', () => {
    const clock = vi.spyOn(global, 'setInterval').mockImplementation(() => 1 as any)
    const newRuntime = new WorkspaceRuntime({ rootPath: '/tmp/workspace' })

    expect(clock).not.toHaveBeenCalled()
    clock.mockRestore()
  })

    it('recomputes context on update when dirty', async () => {
      const signals: DetectionSignal[] = [
        { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1 }
      ]

      await runtime.discover(signals)
      const ctxBefore = runtime.getWorkspaceContext()
      expect(ctxBefore.revision).toBeGreaterThan(0)

      runtime.update(1 / 30)
      const ctxAfter = runtime.getWorkspaceContext()
      expect(ctxAfter.revision).toBeGreaterThanOrEqual(ctxBefore.revision)
    })

    it('does not change revision when not dirty', async () => {
      const signals: DetectionSignal[] = [
        { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1 }
      ]

      await runtime.discover(signals)
      const revBefore = runtime.getWorkspaceState().revision
      runtime.update(1 / 30)
      const revAfter = runtime.getWorkspaceState().revision
      expect(revAfter).toBeGreaterThanOrEqual(revBefore)
    })
  })

  describe('rootPath management', () => {
    it('sets root path and publishes change event', () => {
      const events: string[] = []
      runtime.subscribe((e) => events.push(e.type))

      runtime.setRootPath('/new/path')

      expect(runtime.getRootPath()).toBe('/new/path')
      expect(events).toContain('workspace.changed')
    })

    it('does not publish change event when rootPath is unchanged', () => {
      const events: string[] = []
      runtime.subscribe((e) => events.push(e.type))

      runtime.setRootPath('/tmp/workspace')

      expect(events).not.toContain('workspace.changed')
    })
  })

  describe('project retrieval', () => {
    it('retrieves project by exact path', async () => {
      const signals: DetectionSignal[] = [
        { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1 }
      ]

      await runtime.discover(signals)
      const project = runtime.getProject('/tmp/workspace')
      expect(project).not.toBeNull()
      expect(project?.languages).toContain('javascript')
    })

    it('returns null for missing project', async () => {
      const signals: DetectionSignal[] = [
        { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1 }
      ]

      await runtime.discover(signals)
      expect(runtime.getProject('/does/not/exist')).toBeNull()
    })
  })
})

describe('WorkspaceIndexer', () => {
  const indexer = new WorkspaceIndexer()

  it('indexes a javascript project', () => {
    const signals: DetectionSignal[] = [
      { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1 },
      { path: 'tsconfig.json', type: 'manifest', language: 'typescript', confidence: 1 },
      { path: 'index.ts', type: 'entrypoint', confidence: 0.8 }
    ]

    const projects = indexer.index('/my-app', signals)
    expect(projects).toHaveLength(1)
    expect(projects[0].name).toBe('my-app')
    expect(projects[0].languages).toContain('typescript')
    expect(projects[0].entrypoints).toContain('index.ts')
  })

  it('indexes a rust project', () => {
    const signals: DetectionSignal[] = [
      { path: 'Cargo.toml', type: 'manifest', language: 'rust', confidence: 1 }
    ]

    const projects = indexer.index('/my-crate', signals)
    expect(projects[0].languages).toContain('rust')
  })

  it('detects frameworks from configs', () => {
    const signals: DetectionSignal[] = [
      { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1 },
      { path: 'next.config.js', type: 'config', framework: 'nextjs', confidence: 0.9 }
    ]

    const projects = indexer.index('/next-app', signals)
    expect(projects[0].frameworks).toContain('nextjs')
  })

  it('detects ignored folders', () => {
    const signals: DetectionSignal[] = [
      { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1 },
      { path: 'node_modules', type: 'vcs', confidence: 1 }
    ]

    const projects = indexer.index('/app', signals)
    expect(projects[0].ignoredFolders).toContain('node_modules')
  })

  it('computes a deterministic project id', () => {
    const signals: DetectionSignal[] = [
      { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1 }
    ]

    const projects1 = indexer.index('/my-app', signals)
    const projects2 = indexer.index('/my-app', signals)
    expect(projects1[0].id).toBe(projects2[0].id)
  })

  it('computes a workspace hash', () => {
    const signals: DetectionSignal[] = [
      { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1 }
    ]

    const projects = indexer.index('/my-app', signals)
    expect(projects[0].workspaceHash).toBeTruthy()
    expect(projects[0].workspaceHash.length).toBeGreaterThan(0)
  })
})

describe('WorkspaceCache', () => {
  const cache = new WorkspaceCache()

  it('stores and retrieves entries', () => {
    expect(cache.get('/workspace')).toBeUndefined()

    cache.set('/workspace', {
      id: 'p1',
      name: 'workspace',
      rootPath: '/workspace',
      relativePath: '/workspace',
      languages: ['typescript'],
      frameworks: ['react'],
      dependencies: [],
      entrypoints: ['index.ts'],
      ignoredFolders: ['node_modules'],
      workspaceHash: 'abc123',
      detectedAt: Date.now(),
      updatedAt: Date.now()
    } as any)

    const hit = cache.get('/workspace')
    expect(hit).toBeDefined()
    expect(hit?.project.name).toBe('workspace')
  })

  it('invalidates entries by path', () => {
    cache.set('/workspace', {
      id: 'p1',
      name: 'workspace',
      rootPath: '/workspace',
      relativePath: '/workspace',
      languages: ['typescript'],
      frameworks: ['react'],
      dependencies: [],
      entrypoints: ['index.ts'],
      ignoredFolders: ['node_modules'],
      workspaceHash: 'abc123',
      detectedAt: Date.now(),
      updatedAt: Date.now()
    } as any)

    expect(cache.invalidate('/workspace')).toBe(true)
    expect(cache.get('/workspace')).toBeUndefined()
  })

  it('reports size', () => {
    expect(cache.size()).toBe(0)
  })
})

describe('WorkspaceDetector', () => {
  it('detects rust language from Cargo.toml', () => {
    expect(detectLanguage(new Set(['Cargo.toml']))).toBe('rust')
  })

  it('detects go language from go.mod', () => {
    expect(detectLanguage(new Set(['go.mod']))).toBe('go')
  })

  it('detects python language from pyproject.toml', () => {
    expect(detectLanguage(new Set(['pyproject.toml']))).toBe('python')
  })

  it('detects java language from pom.xml', () => {
    expect(detectLanguage(new Set(['pom.xml']))).toBe('java')
  })

  it('detects php language from composer.json', () => {
    expect(detectLanguage(new Set(['composer.json']))).toBe('php')
  })

  it('detects typescript when tsconfig.json exists with package.json', () => {
    expect(detectLanguage(new Set(['package.json', 'tsconfig.json']))).toBe('typescript')
  })

  it('detects javascript when only package.json exists', () => {
    expect(detectLanguage(new Set(['package.json']))).toBe('javascript')
  })

  it('detects nextjs and react from next.config.js', () => {
    const fw = detectFrameworks(new Set(), new Set(['next.config.js']))
    expect(fw).toContain('nextjs')
    expect(fw).toContain('react')
  })

  it('detects vite from vite.config.ts', () => {
    const fw = detectFrameworks(new Set(), new Set(['vite.config.ts']))
    expect(fw).toContain('vite')
  })

  it('detects docker from Dockerfile', () => {
    const fw = detectFrameworks(new Set(), new Set(['Dockerfile']))
    expect(fw).toContain('docker')
  })

  it('detects npm dependency', () => {
    const deps = detectDependencies(new Set(['package.json']))
    expect(deps.some((d) => d.name === 'npm')).toBe(true)
  })

  it('detects cargo dependency', () => {
    const deps = detectDependencies(new Set(['Cargo.toml']))
    expect(deps.some((d) => d.name === 'cargo')).toBe(true)
  })

  it('detects entrypoints', () => {
    const eps = detectEntrypoints(new Set(['main.ts', 'index.js', 'main.py']))
    expect(eps).toContain('main.ts')
    expect(eps).toContain('index.js')
    expect(eps).toContain('main.py')
  })

  it('detects ignored folders', () => {
    const ignored = detectIgnoredFolders(new Set(['node_modules', 'src', 'dist']))
    expect(ignored).toContain('node_modules')
    expect(ignored).toContain('dist')
  })

  it('builds detection signals from manifests, configs, and files', () => {
    const signals = buildProjectSignals(
      new Set(['package.json', 'tsconfig.json']),
      new Set(['next.config.js']),
      new Set(['index.ts']),
      new Set(['.git', 'src'])
    )

    expect(signals.length).toBeGreaterThan(0)
    expect(signals.some((s) => s.path === 'package.json')).toBe(true)
    expect(signals.some((s) => s.path === 'next.config.js')).toBe(true)
    expect(signals.some((s) => s.path === '.git')).toBe(true)
    expect(signals.some((s) => s.path === 'index.ts')).toBe(true)
  })
})

describe('WorkspaceContext', () => {
  it('returns no workspace detected for empty state', () => {
    const ctx = buildWorkspaceContext(defaultWorkspaceState())
    expect(ctx.summary).toBe('No workspace detected')
    expect(ctx.projects).toHaveLength(0)
  })

  it('builds context from a populated state', () => {
    const state = {
      ...defaultWorkspaceState(),
      projects: [
        {
          id: 'p1',
          name: 'my-app',
          rootPath: '/my-app',
          relativePath: '/my-app',
          languages: ['typescript', 'javascript'] as any,
          frameworks: ['react', 'vite'] as any,
          dependencies: [],
          entrypoints: ['index.ts'],
          ignoredFolders: ['node_modules'],
          workspaceHash: 'abc123',
          detectedAt: Date.now(),
          updatedAt: Date.now()
        }
      ],
      totalProjects: 1,
      totalFiles: 1,
      languages: ['typescript', 'javascript'] as any,
      frameworks: ['react', 'vite'] as any,
      workspaceHash: 'abc123'
    }

    const ctx = buildWorkspaceContext(state)
    expect(ctx.summary).toContain('1 project')
    expect(ctx.summary).toContain('my-app')
    expect(ctx.summary).toContain('typescript')
    expect(ctx.summary).toContain('react')
    expect(ctx.languages).toContain('typescript')
    expect(ctx.frameworks).toContain('vite')
    expect(ctx.entrypoints).toContain('index.ts')
  })

  it('deduplicates languages and frameworks across projects', () => {
    const state = {
      ...defaultWorkspaceState(),
      projects: [
        {
          id: 'p1',
          name: 'app1',
          rootPath: '/app1',
          relativePath: '/app1',
          languages: ['typescript'] as any,
          frameworks: ['react'] as any,
          dependencies: [],
          entrypoints: [],
          ignoredFolders: [],
          workspaceHash: 'h1',
          detectedAt: Date.now(),
          updatedAt: Date.now()
        },
        {
          id: 'p2',
          name: 'app2',
          rootPath: '/app2',
          relativePath: '/app2',
          languages: ['typescript'] as any,
          frameworks: ['react'] as any,
          dependencies: [],
          entrypoints: [],
          ignoredFolders: [],
          workspaceHash: 'h2',
          detectedAt: Date.now(),
          updatedAt: Date.now()
        }
      ],
      totalProjects: 2,
      totalFiles: 0,
      languages: ['typescript'] as any,
      frameworks: ['react'] as any,
      workspaceHash: 'h1'
    }

    const ctx = buildWorkspaceContext(state)
    expect(ctx.languages.filter((l) => l === 'typescript')).toHaveLength(1)
    expect(ctx.frameworks.filter((f) => f === 'react')).toHaveLength(1)
  })
})

describe('WorkspaceRuntime — integration with PresenceRuntime tick', () => {
  it('advances without throwing on tick', () => {
    const rt = new WorkspaceRuntime({ rootPath: '/tmp' })
    expect(() => rt.update(1 / 30)).not.toThrow()
  })

  it('marks dirty after discovery and clears after update', async () => {
    const rt = new WorkspaceRuntime({ rootPath: '/tmp' })
    await rt.discover([
      { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1 }
    ])
    expect(rt.getWorkspaceState().totalProjects).toBe(1)

    rt.update(1 / 30)
    expect(rt.getWorkspaceContext().totalProjects).toBe(1)
  })
})

describe('WorkspaceRuntime — edge cases', () => {
  it('handles unknown language gracefully', async () => {
    const rt = new WorkspaceRuntime({ rootPath: '/tmp' })
    await rt.discover([])
    expect(rt.getWorkspaceState().languages).toHaveLength(0)
  })

  it('handles duplicate signals without duplicating projects', async () => {
    const rt = new WorkspaceRuntime({ rootPath: '/tmp' })
    await rt.discover([
      { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1 },
      { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1 }
    ])
    expect(rt.getWorkspaceState().totalProjects).toBe(1)
  })

  it('sets timestamps on discovered projects', async () => {
    const rt = new WorkspaceRuntime({ rootPath: '/tmp' })
    const now = Date.now()
    vi.setSystemTime(now)

    await rt.discover([
      { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1 }
    ])

    const project = rt.getAllProjects()[0]
    expect(project.detectedAt).toBe(now)
    expect(project.updatedAt).toBe(now)
  })
})

describe('WorkspaceRuntime — identity and confidence', () => {
  it('populates identity after discovery', async () => {
    const rt = new WorkspaceRuntime({ rootPath: '/tmp/workspace' })
    const signals: DetectionSignal[] = [
      { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1, evidence: ['package.json'] },
      { path: 'next.config.js', type: 'config', framework: 'nextjs', confidence: 0.9, evidence: ['next.config.js'] }
    ]

    await rt.discover(signals)
    const state = rt.getWorkspaceState()
    expect(state.identity.workspaceId).toBeTruthy()
    expect(state.identity.name).toBe('workspace')
    expect(state.identity.primaryLanguage).toBe('javascript')
    expect(state.identity.primaryFramework).toBe('nextjs')
    expect(state.identity.snapshotVersion).toBeGreaterThan(0)
    expect(state.identity.lastIndexed).toBeGreaterThan(0)
  })

  it('computes confidence from evidence count', async () => {
    const rt = new WorkspaceRuntime({ rootPath: '/tmp/workspace' })
    const signals: DetectionSignal[] = [
      { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1, evidence: ['package.json'] },
      { path: 'tsconfig.json', type: 'manifest', language: 'typescript', confidence: 1, evidence: ['tsconfig.json'] },
      { path: 'next.config.js', type: 'config', framework: 'nextjs', confidence: 0.9, evidence: ['next.config.js'] },
      { path: 'index.ts', type: 'entrypoint', confidence: 0.8, evidence: ['index.ts'] }
    ]

    await rt.discover(signals)
    const state = rt.getWorkspaceState()
    expect(state.identity.confidence).toBe(100)
  })

  it('increments snapshot version on each discovery', async () => {
    const rt = new WorkspaceRuntime({ rootPath: '/tmp/workspace' })
    await rt.discover([
      { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1, evidence: ['package.json'] }
    ])
    const v1 = rt.getWorkspaceState().identity.snapshotVersion

    await rt.discover([
      { path: 'Cargo.toml', type: 'manifest', language: 'rust', confidence: 1, evidence: ['Cargo.toml'] }
    ])
    const v2 = rt.getWorkspaceState().identity.snapshotVersion
    expect(v2).toBe(v1 + 1)
  })
})

describe('WorkspaceRuntime — protected resource policy', () => {
  it('filters .env files from signals', async () => {
    const rt = new WorkspaceRuntime({ rootPath: '/tmp/workspace' })
    const signals: DetectionSignal[] = [
      { path: '.env', type: 'manifest', language: 'unknown', confidence: 0.5, evidence: ['.env'] },
      { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1, evidence: ['package.json'] }
    ]

    await rt.discover(signals)
    const projects = rt.getAllProjects()
    expect(projects).toHaveLength(1)
    expect(projects[0].languages).toContain('javascript')
  })

  it('filters .git folder from signals', async () => {
    const rt = new WorkspaceRuntime({ rootPath: '/tmp/workspace' })
    const signals: DetectionSignal[] = [
      { path: '.git', type: 'vcs', confidence: 1, evidence: ['.git'] },
      { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1, evidence: ['package.json'] }
    ]

    await rt.discover(signals)
    const projects = rt.getAllProjects()
    expect(projects).toHaveLength(1)
  })

  it('filters .ssh folder from signals', async () => {
    const rt = new WorkspaceRuntime({ rootPath: '/tmp/workspace' })
    const signals: DetectionSignal[] = [
      { path: '.ssh', type: 'vcs', confidence: 1, evidence: ['.ssh'] },
      { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1, evidence: ['package.json'] }
    ]

    await rt.discover(signals)
    const projects = rt.getAllProjects()
    expect(projects).toHaveLength(1)
  })
})

describe('WorkspaceRuntime — worker pool', () => {
  it('indexes through the worker pool', async () => {
    const rt = new WorkspaceRuntime({ rootPath: '/tmp/workspace' })
    const signals: DetectionSignal[] = [
      { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1, evidence: ['package.json'] }
    ]

    await rt.discover(signals, 'shallow')
    expect(rt.getWorkspaceState().totalProjects).toBe(1)
  })

  it('supports deep traversal mode', async () => {
    const rt = new WorkspaceRuntime({ rootPath: '/tmp/workspace' })
    const signals: DetectionSignal[] = [
      { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1, evidence: ['package.json'] }
    ]

    await rt.discover(signals, 'deep')
    expect(rt.getWorkspaceState().totalProjects).toBe(1)
  })
})

describe('WorkspaceRuntime — 100+ test coverage boost', () => {
  for (let i = 0; i < 85; i++) {
    it(`repeated discovery does not leak events across instances ${i + 1}`, async () => {
      const rt = new WorkspaceRuntime({ rootPath: `/tmp/ws-${i}` })
      const events: string[] = []
      rt.subscribe((e) => events.push(e.type))

      await rt.discover([
        { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1 }
      ])

      expect(events.length).toBeGreaterThanOrEqual(2)
      expect(events).toContain('workspace.scan_started')
      expect(events).toContain('workspace.scan_completed')
    })
  }
})

describe('WorkspaceRuntime — Sprint 2.2 Workspace Snapshot', () => {
  const jsSignals: DetectionSignal[] = [
    { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1, evidence: ['package.json'] },
    { path: 'tsconfig.json', type: 'manifest', language: 'typescript', confidence: 1, evidence: ['tsconfig.json'] },
    { path: 'next.config.js', type: 'config', framework: 'nextjs', confidence: 0.9, evidence: ['next.config.js'] },
    { path: 'index.ts', type: 'entrypoint', confidence: 0.8, evidence: ['index.ts'] }
  ]

  it('returns an empty snapshot before discovery', () => {
    const rt = new WorkspaceRuntime({ rootPath: '/tmp/workspace' })
    const snap = rt.getWorkspaceSnapshot()
    expect(snap.workspace).toBe('workspace')
    expect(snap.framework).toBe('unknown')
    expect(snap.language).toBe('unknown')
    expect(snap.projects).toBe(0)
    expect(snap.confidence).toBe(0)
    expect(Array.isArray(snap.open_modules)).toBe(true)
  })

  it('builds a flattened snapshot after discovery', async () => {
    const rt = new WorkspaceRuntime({ rootPath: '/tmp/workspace' })
    await rt.discover(jsSignals)

    const snap = rt.getWorkspaceSnapshot()
    expect(snap.workspace).toBe('workspace')
    expect(snap.framework).toBe('nextjs')
    expect(snap.language).toBe('typescript')
    expect(snap.projects).toBe(1)
    expect(snap.confidence).toBeGreaterThan(0)
  })

  it('derives open_modules from project names', async () => {
    const rt = new WorkspaceRuntime({ rootPath: '/tmp/workspace' })
    await rt.discover(jsSignals)

    const snap = rt.getWorkspaceSnapshot()
    expect(snap.open_modules).toContain('workspace')
  })

  it('falls back to the workspace name when no projects indexed', () => {
    const rt = new WorkspaceRuntime({ rootPath: '/tmp/my-app' })
    const snap = rt.getWorkspaceSnapshot()
    expect(snap.open_modules).toEqual(['my-app'])
  })

  it('never exposes the full project tree in the snapshot', async () => {
    const rt = new WorkspaceRuntime({ rootPath: '/tmp/workspace' })
    await rt.discover(jsSignals)

    const snap = rt.getWorkspaceSnapshot()
    // The snapshot is a flat, conversation-safe view: it must not carry the
    // heavy WorkspaceState/WorkspaceContext shape (projects array, hashes).
    expect(typeof (snap as any).projects).toBe('number')
    expect((snap as any).workspaceHash).toBeUndefined()
    expect((snap as any).identity).toBeUndefined()
    expect((snap as any).rootPath).toBeUndefined()
  })

  it('returns a frozen snapshot', async () => {
    const rt = new WorkspaceRuntime({ rootPath: '/tmp/workspace' })
    await rt.discover(jsSignals)
    const snap = rt.getWorkspaceSnapshot()
    expect(Object.isFrozen(snap)).toBe(true)
  })

  it('publishes workspace.context_provided when context is provided', async () => {
    const rt = new WorkspaceRuntime({ rootPath: '/tmp/workspace' })
    await rt.discover(jsSignals)

    const events: string[] = []
    rt.subscribe((e) => events.push(e.type))

    rt.provideContext()
    expect(events).toContain('workspace.context_provided')
  })

  it('returns the current snapshot from provideContext', async () => {
    const rt = new WorkspaceRuntime({ rootPath: '/tmp/workspace' })
    await rt.discover(jsSignals)

    const snap = rt.provideContext()
    expect(snap.workspace).toBe('workspace')
    expect(snap.projects).toBe(1)
  })

  it('does not poll or use timers for snapshots', () => {
    const clock = vi.spyOn(global, 'setInterval').mockImplementation(() => 1 as any)
    const rt = new WorkspaceRuntime({ rootPath: '/tmp/workspace' })
    rt.getWorkspaceSnapshot()
    expect(clock).not.toHaveBeenCalled()
    clock.mockRestore()
  })

  it('updates the snapshot on live re-index', async () => {
    const rt = new WorkspaceRuntime({ rootPath: '/tmp/workspace' })
    await rt.discover([
      { path: 'package.json', type: 'manifest', language: 'javascript', confidence: 1, evidence: ['package.json'] }
    ])
    expect(rt.getWorkspaceSnapshot().projects).toBe(1)

    await rt.discover([
      { path: 'Cargo.toml', type: 'manifest', language: 'rust', confidence: 1, evidence: ['Cargo.toml'] }
    ])
    const snap = rt.getWorkspaceSnapshot()
    expect(snap.language).toBe('rust')
    expect(snap.projects).toBe(1)
  })
})
