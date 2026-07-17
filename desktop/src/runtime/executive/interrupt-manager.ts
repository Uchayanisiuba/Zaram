// desktop/src/runtime/executive/interrupt-manager.ts
//
// Milestone 1.4 — Interrupt Manager.
//
// Owns interrupt handling. Subsystems (World, Conversation, Tools, Plugins,
// Automation) raise interrupts; the manager queues them by salience, decides
// whether the current flow should be preempted, and reports whether the
// executive should interrupt itself. It is a private subsystem.

import { Interrupt, InterruptSeverity, InterruptState } from './types'

const SEVERITY_WEIGHT: Record<InterruptSeverity, number> = {
  critical: 1,
  high: 0.75,
  medium: 0.5,
  low: 0.25
}

let _interruptSeq = 0
function nextInterruptId(): string {
  _interruptSeq += 1
  return `int-${Date.now().toString(36)}-${_interruptSeq}`
}

export interface InterruptInput {
  reason: string
  severity?: InterruptSeverity
  salience?: number
  source?: string
}

export class InterruptManager {
  private pending: Interrupt[] = []
  private state: InterruptState = 'clear'
  // salience above which an interrupt preempts the current flow
  private preemptThreshold = 0.6

  reset(): void {
    this.pending = []
    this.state = 'clear'
  }

  raise(input: InterruptInput): Interrupt {
    const severity = input.severity ?? 'medium'
    const salience = clamp01(input.salience ?? SEVERITY_WEIGHT[severity])
    const interrupt: Interrupt = {
      id: nextInterruptId(),
      reason: input.reason,
      severity,
      salience,
      source: input.source ?? 'unknown',
      arrivedAt: now(),
      handled: false
    }
    this.pending.push(interrupt)
    this.pending.sort((a, b) => b.salience - a.salience)
    if (this.state === 'clear') this.state = 'pending'
    return interrupt
  }

  // Mark the highest-salience pending interrupt as handled and drop it.
  handleTop(): Interrupt | null {
    const top = this.pending[0]
    if (!top) {
      this.state = 'clear'
      return null
    }
    top.handled = true
    this.pending = this.pending.filter((i) => i.id !== top.id)
    this.state = this.pending.length ? 'pending' : 'clear'
    return top
  }

  // True when the highest-priority pending interrupt demands preemption.
  shouldPreempt(): boolean {
    const top = this.pending[0]
    if (!top) return false
    return top.salience >= this.preemptThreshold
  }

  getState(): InterruptState {
    return this.state
  }

  pendingSnapshot(): Array<{ id: string; reason: string; severity: string; salience: number }> {
    return this.pending.map((i) => ({
      id: i.id,
      reason: i.reason,
      severity: i.severity,
      salience: i.salience
    }))
  }

  topSalience(): number {
    return this.pending[0]?.salience ?? 0
  }

  count(): number {
    return this.pending.length
  }

  setPreemptThreshold(value: number): void {
    this.preemptThreshold = clamp01(value)
  }
}

function clamp01(v: number): number {
  if (Number.isNaN(v)) return 0
  return Math.min(1, Math.max(0, v))
}

function now(): number {
  return typeof performance !== 'undefined' ? performance.now() : Date.now()
}
