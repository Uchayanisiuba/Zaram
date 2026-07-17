// desktop/tests/runtime/executive/orchestration.test.ts
//
// Sprint 2.4 — Executive Orchestration & Capability Composition tests.

import { describe, it, expect, beforeEach } from 'vitest'
import { ExecutiveRuntime } from '../../../src/runtime/executive/executive-runtime'
import { CapabilityRuntime } from '../../../src/runtime/capability/capability-runtime'

describe('ExecutiveRuntime Orchestration', () => {
  let runtime: ExecutiveRuntime
  let capabilityRuntime: CapabilityRuntime

  beforeEach(() => {
    capabilityRuntime = new CapabilityRuntime()
    runtime = new ExecutiveRuntime({
      capabilityRuntime,
      workspaceRuntime: {
        getWorkspaceSnapshot: () => ({
          workspace: 'Zaram',
          framework: 'React',
          language: 'TypeScript',
          projects: 3,
          confidence: 85,
          open_modules: ['frontend', 'desktop', 'runtime']
        })
      }
    })
  })

  it('should generate a plan for project questions', () => {
    const plan = runtime.plan('What project is this?')
    expect(plan.goal).toBe('What project is this?')
    expect(plan.steps.length).toBeGreaterThan(0)
    expect(plan.steps.some(s => s.capabilityId === 'workspace.getWorkspaceSnapshot')).toBe(true)
    expect(plan.evidence).toContain('Workspace Snapshot')
  })

  it('should generate a plan for file search questions', () => {
    const plan = runtime.plan('Find package.json')
    expect(plan.steps.length).toBeGreaterThan(0)
    expect(plan.steps.some(s => s.capabilityId === 'filesystem.search')).toBe(true)
    expect(plan.steps.some(s => s.capabilityId === 'filesystem.read')).toBe(true)
  })

  it('should generate a plan for language/framework questions', () => {
    const plan = runtime.plan('What language is this?')
    expect(plan.steps.length).toBeGreaterThan(0)
    expect(plan.steps.some(s => s.capabilityId === 'vscode.editor.active')).toBe(true)
    expect(plan.steps.some(s => s.capabilityId === 'workspace.getWorkspaceSnapshot')).toBe(true)
  })

  it('should generate a plan for git questions', () => {
    const plan = runtime.plan('What changed in Git?')
    expect(plan.steps.length).toBeGreaterThan(0)
    expect(plan.steps.some(s => s.capabilityId === 'vscode.git.status')).toBe(true)
  })

  it('should generate a plan for auth/database questions', () => {
    const plan = runtime.plan('Find authentication')
    expect(plan.steps.length).toBeGreaterThan(0)
    expect(plan.steps.some(s => s.capabilityId === 'filesystem.search')).toBe(true)
  })

  it('should compute confidence based on source diversity', () => {
    const plan = runtime.plan('Find authentication')
    expect(plan.confidence).toBeGreaterThan(0.5)
    expect(plan.confidence).toBeLessThanOrEqual(0.98)
  })

  it('should track capability metrics', () => {
    runtime.recordCapabilityCall('filesystem.search', 100, true)
    runtime.recordCapabilityCall('filesystem.search', 200, true)
    runtime.recordCapabilityCall('filesystem.read', 50, false)

    const metrics = runtime.getCapabilityMetrics()
    const searchMetric = metrics.find(m => m.capabilityId === 'filesystem.search')
    expect(searchMetric).toBeDefined()
    expect(searchMetric!.calls).toBe(2)
    expect(searchMetric!.totalTimeMs).toBe(300)
    expect(searchMetric!.successes).toBe(2)
    expect(searchMetric!.failures).toBe(0)

    const readMetric = metrics.find(m => m.capabilityId === 'filesystem.read')
    expect(readMetric).toBeDefined()
    expect(readMetric!.failures).toBe(1)
  })

  it('should return current plan', () => {
    runtime.plan('test query')
    const plan = runtime.getCurrentPlan()
    expect(plan).not.toBeNull()
    expect(plan!.goal).toBe('test query')
  })

  it('should return evidence', () => {
    runtime.ingestVSCodeContext({ activeFile: 'test.ts', language: 'TypeScript' })
    runtime.ingestWorkspaceSnapshot({ workspace: 'Zaram' })

    const evidence = runtime.getEvidence()
    expect(evidence.length).toBeGreaterThan(0)
    expect(evidence.some(e => e.includes('Workspace'))).toBe(true)
  })

  it('should reset orchestration state', () => {
    runtime.plan('test')
    runtime.recordCapabilityCall('filesystem.search', 100, true)
    runtime.reset()

    expect(runtime.getCurrentPlan()).toBeNull()
    expect(runtime.getCapabilityMetrics().length).toBe(0)
    expect(runtime.getEvidence().length).toBe(0)
  })
})
