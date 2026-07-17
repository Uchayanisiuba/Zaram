// desktop/src/runtime/executive/execution-plan.ts
//
// Sprint 2.4 — Executive Orchestration & Capability Composition.
//
// ExecutionPlan is the Executive Runtime's primary orchestration artifact.
// It composes existing capabilities into ordered steps, tracks confidence
// and evidence, and is consumed by the Conversation layer and Audit Terminal.
// No new runtimes, no renderer imports.

import type { CapabilityDescriptor } from '../capability'

export type PlanStepStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped'

export interface ExecutionStep {
  id: string
  capabilityId: string
  description: string
  status: PlanStepStatus
  input?: Record<string, unknown>
  output?: unknown
  error?: string
  startedAt?: number
  finishedAt?: number
  durationMs?: number
}

export interface ExecutionPlan {
  id: string
  goal: string
  steps: ExecutionStep[]
  status: 'draft' | 'running' | 'completed' | 'failed'
  confidence: number
  evidence: string[]
  createdAt: number
  updatedAt: number
}

export interface CapabilityMetrics {
  capabilityId: string
  calls: number
  totalTimeMs: number
  successes: number
  failures: number
  lastUsed: number
}

export const DEFAULT_METRICS: CapabilityMetrics = {
  capabilityId: '',
  calls: 0,
  totalTimeMs: 0,
  successes: 0,
  failures: 0,
  lastUsed: 0
}

export function createExecutionPlan(goal: string): ExecutionPlan {
  return {
    id: `plan-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
    goal,
    steps: [],
    status: 'draft',
    confidence: 0,
    evidence: [],
    createdAt: Date.now(),
    updatedAt: Date.now()
  }
}

export function createExecutionStep(capabilityId: string, description: string, input?: Record<string, unknown>): ExecutionStep {
  return {
    id: `step-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
    capabilityId,
    description,
    status: 'pending',
    input
  }
}

export function cloneExecutionPlan(plan: ExecutionPlan): ExecutionPlan {
  return {
    ...plan,
    steps: plan.steps.map((s) => ({ ...s }))
  }
}
