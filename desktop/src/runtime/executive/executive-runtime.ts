// desktop/src/runtime/executive/executive-runtime.ts
//
// Milestone 1.4 — Executive Runtime (Decision Engine).
//
// The AI's executive control system. Every cognitive subsystem (Conversation,
// Memory, World, Attention, Relationship, Vision, Automation, Tool, Plugin) feeds
// INTO the Executive Runtime, and the Executive Runtime is the SINGLE authority
// for high-level AI decision-making:
//
//   reply | wait | listen | continue-thinking | look | remember | ignore
//   interrupt-self | cancel-task | switch-context | launch-automation
//   call-tool | ask-clarification | be-proactive
//
// It owns: focus, priorities, interrupt handling, task switching, context
// selection, goal management, and intention generation. Everything else is a
// subsystem. It NEVER imports the drawing layer, the body layer, concrete
// avatars, the character projection, the animation engine, frame snapshots, the
// orb drawing code, the desktop shell, any GPU/3D engine, or platform-specific
// graphics code.
//
// It reuses the existing 30Hz scheduler (PresenceRuntime.tick) — no new timers,
// no polling, no requestAnimationFrame. It reuses the existing DI container and
// the existing Set-based pub/sub (the same EventBus pattern used by the World
// and Cognitive runtimes).

import {
  ExecutiveDecision,
  ExecutiveGoal,
  ExecutiveIntent,
  FocusTarget,
  InterruptSeverity,
  ReasoningMode,
  ThinkingMode
} from './types'
import {
  cloneExecutiveState,
  defaultExecutiveState,
  ExecutiveState
} from './executive-state'
import { GoalManager, GoalInput } from './goal-manager'
import { FocusManager } from './focus-manager'
import { InterruptManager, InterruptInput } from './interrupt-manager'
import { PriorityManager } from './priority-manager'
import { IntentGenerator, IntentContext } from './intent-generator'
import {
  ExecutionPlan,
  ExecutionStep,
  PlanStepStatus,
  CapabilityMetrics,
  DEFAULT_METRICS,
  createExecutionPlan,
  createExecutionStep,
  cloneExecutionPlan
} from './execution-plan'

// The Executive Runtime depends on the Capability Runtime ONLY through its
// interface. It requests capabilities (metadata) and never calls tools directly
// or imports a concrete capability implementation.
import type { ICapabilityRuntime, CapabilityQuery, CapabilityResolution } from '../capability'

// --- Inbound perception contracts (subsystems push; the executive does not pull) -

export interface ConversationSignal {
  phase: string
  activity?: number
}

export interface MemorySignal {
  recall?: number
  activity?: number
}

export interface WorldSignal {
  // peak notification salience 0..1
  salience?: number
  // true if the AI is in the foreground
  foreground?: boolean
}

export interface AttentionSignal {
  target?: FocusTarget
  confidence?: number
  notificationSalience?: number
}

export interface RelationshipSignal {
  familiarity?: number
  interactionFrequency?: number
}

export interface CognitiveSignal {
  reasoning?: ReasoningMode
  thinking?: boolean
  needsClarification?: boolean
  hasPendingTask?: boolean
  goalFocus?: FocusTarget
}

export interface VSCodeSignal {
  workspace?: string
  activeFile?: string | null
  language?: string | null
  selection?: string | null
  diagnostics?: number
  gitBranch?: string | null
  modifiedFiles?: number
  connected?: boolean
}

export interface ExecutiveRuntimeOptions {
  // Injectable clock (test hook).
  now?: () => number
  // The Capability Runtime, consumed ONLY through its interface. The executive
  // requests capabilities (metadata) and never calls tools directly or imports
  // a concrete capability implementation.
  capabilityRuntime?: ICapabilityRuntime
  // Workspace Runtime, consumed read-only for snapshot and project context.
  workspaceRuntime?: {
    getWorkspaceSnapshot(): unknown
  }
}

export interface ExecutiveSnapshot {
  state: ExecutiveState
  intent: ExecutiveIntent
}

export class ExecutiveRuntime {
  private readonly goals = new GoalManager()
  private readonly focus = new FocusManager()
  private readonly interrupts = new InterruptManager()
  private readonly priority = new PriorityManager()
  private readonly intentGen = new IntentGenerator()
  private readonly subscribers = new Set<(s: ExecutiveSnapshot) => void>()
  private readonly capabilityRuntime?: ICapabilityRuntime
  private readonly workspaceRuntime?: ExecutiveRuntimeOptions['workspaceRuntime']
  private readonly now: () => number

  // Latest inbound perception (event-driven). Replaced wholesale on each signal.
  private conversation: ConversationSignal = { phase: 'idle' }
  private memory: MemorySignal = {}
  private world: WorldSignal = {}
  private attention: AttentionSignal = {}
  private relationship: RelationshipSignal = {}
  private cognitive: CognitiveSignal = {}
  private vscode: VSCodeSignal = {}

  private state: ExecutiveState = defaultExecutiveState()
  private intent: ExecutiveIntent = this.intentGen.generate(this.baseContext())

  // Sprint 2.4: Orchestration state.
  private currentPlan: ExecutionPlan | null = null
  private readonly metrics = new Map<string, CapabilityMetrics>()
  private workspaceSnapshot: Record<string, unknown> = {}

  constructor(options: ExecutiveRuntimeOptions = {}) {
    this.now = options.now ?? (() => (typeof performance !== 'undefined' ? performance.now() : Date.now()))
    this.capabilityRuntime = options.capabilityRuntime
    this.workspaceRuntime = options.workspaceRuntime
    if (this.workspaceRuntime) {
      this.workspaceSnapshot = this.workspaceRuntime.getWorkspaceSnapshot() as Record<string, unknown> || {}
    }
  }

  // --- Ingestion (subsystems push; never pulled by the executive) ------------

  ingestConversation(signal: ConversationSignal): void {
    this.conversation = { phase: signal.phase, activity: signal.activity ?? this.conversation.activity ?? 0 }
    this.recompute()
  }

  ingestMemory(signal: MemorySignal): void {
    this.memory = { ...this.memory, ...signal }
    this.recompute()
  }

  ingestWorld(signal: WorldSignal): void {
    this.world = { ...this.world, ...signal }
    this.recompute()
  }

  ingestAttention(signal: AttentionSignal): void {
    this.attention = { ...this.attention, ...signal }
    this.recompute()
  }

  ingestRelationship(signal: RelationshipSignal): void {
    this.relationship = { ...this.relationship, ...signal }
    this.recompute()
  }

  ingestCognitive(signal: CognitiveSignal): void {
    this.cognitive = { ...this.cognitive, ...signal }
    this.recompute()
  }

  ingestVSCodeContext(signal: VSCodeSignal): void {
    this.vscode = { ...this.vscode, ...signal }
    this.recompute()
  }

  // --- Goal management (public, the executive owns goals) -------------------

  addGoal(input: GoalInput): ExecutiveGoal {
    const goal = this.goals.add(input)
    this.recompute()
    return goal
  }

  switchGoal(id: string): ExecutiveGoal | null {
    const goal = this.goals.switchTo(id)
    this.recompute()
    return goal
  }

  suspendCurrentGoal(): void {
    this.goals.suspendCurrent()
    this.recompute()
  }

  resumeGoal(id: string): void {
    this.goals.resume(id)
    this.recompute()
  }

  completeGoal(id: string): void {
    this.goals.complete(id)
    this.recompute()
  }

  // --- Interrupt handling (public) -------------------------------------------

  raiseInterrupt(input: InterruptInput): { id: string } {
    const intr = this.interrupts.raise(input)
    this.recompute()
    return { id: intr.id }
  }

  handleTopInterrupt(): void {
    this.interrupts.handleTop()
    this.recompute()
  }

  // --- Capability requests (interface only) -----------------------------------
  //
  // The Executive Runtime NEVER calls tools directly. It requests capability
  // metadata through the injected ICapabilityRuntime and lets the Execution
  // Engine (a separate layer, not built here) perform the work. This keeps the
  // executive decoupled from concrete capability implementations.

  hasCapabilityRuntime(): boolean {
    return Boolean(this.capabilityRuntime)
  }

  requestCapability(query: CapabilityQuery): CapabilityResolution | null {
    if (!this.capabilityRuntime) return null
    return this.capabilityRuntime.resolve(query)
  }

  hasCapability(id: string): boolean {
    return this.capabilityRuntime ? this.capabilityRuntime.has(id) : false
  }

  // --- Time evolution on the existing 30Hz tick ------------------------------
  //
  // Called by PresenceRuntime.tick(dt) (the reused scheduler). No new timer or
  // loop. Eases focus strength and re-resolves the decision so it evolves
  // smoothly with time.

  update(dt: number): ExecutiveSnapshot {
    this.focus.ease(dt)
    this.recompute()
    return this.snapshot()
  }

  // --- Read-only consumption --------------------------------------------------

  getState(): ExecutiveState {
    return cloneExecutiveState(this.state)
  }

  getIntent(): ExecutiveIntent {
    return { ...this.intent }
  }

  getSnapshot(): ExecutiveSnapshot {
    return this.snapshot()
  }

  getVSCodeSignal(): VSCodeSignal {
    return { ...this.vscode }
  }

  // --- Sprint 2.4: Orchestration ---------------------------------------------

  getCurrentPlan(): ExecutionPlan | null {
    return this.currentPlan ? cloneExecutionPlan(this.currentPlan) : null
  }

  getConfidence(): number {
    return this.state.confidence
  }

  getEvidence(): string[] {
    const evidence: string[] = []
    if (this.workspaceSnapshot.workspace) {
      evidence.push(`Workspace: ${this.workspaceSnapshot.workspace}`)
    }
    if (this.vscode.activeFile) {
      evidence.push(`Active file: ${this.vscode.activeFile}`)
    }
    if (this.vscode.language) {
      evidence.push(`Language: ${this.vscode.language}`)
    }
    if (this.vscode.gitBranch) {
      evidence.push(`Git branch: ${this.vscode.gitBranch}`)
    }
    if (this.vscode.diagnostics !== undefined && this.vscode.diagnostics > 0) {
      evidence.push(`Diagnostics: ${this.vscode.diagnostics}`)
    }
    return evidence
  }

  getCapabilityMetrics(): CapabilityMetrics[] {
    return Array.from(this.metrics.values())
  }

  ingestWorkspaceSnapshot(snapshot: Record<string, unknown>): void {
    this.workspaceSnapshot = { ...snapshot }
    this.recompute()
  }

  plan(query: string, options?: { persona?: string; model?: string }): ExecutionPlan {
    console.log(`[EXECUTIVE] plan() called with query: "${query}" persona=${options?.persona} model=${options?.model}`)
    const plan = createExecutionPlan(query)
    const lower = query.toLowerCase()
    const persona = options?.persona
    const model = options?.model

    if (this.capabilityRuntime) {
      console.log(`[EXECUTIVE] Capability runtime available, evaluating query...`)
      if (lower.includes('project') || lower.includes('workspace') || lower.includes('how many')) {
        plan.steps.push(createExecutionStep('workspace.getWorkspaceSnapshot', 'Read Workspace Snapshot'))
        plan.evidence.push('Workspace Snapshot')
      }

      if (lower.includes('file') || lower.includes('find') || lower.includes('search') || lower.includes('where')) {
        plan.steps.push(createExecutionStep('filesystem.search', 'Search Files'))
        plan.evidence.push('Filesystem Search')
      }

      if (lower.includes('read') || lower.includes('show') || lower.includes('package') || lower.includes('json')) {
        plan.steps.push(createExecutionStep('filesystem.read', 'Read File'))
        plan.evidence.push('Filesystem Read')
      }

      if (lower.includes('auth') || lower.includes('database') || lower.includes('supabase') || lower.includes('config')) {
        plan.steps.push(createExecutionStep('filesystem.search', 'Search for configuration'))
        if (lower.includes('auth')) {
          plan.steps.push(createExecutionStep('filesystem.read', 'Read authentication file'))
        }
        if (lower.includes('database') || lower.includes('supabase')) {
          plan.steps.push(createExecutionStep('filesystem.metadata', 'Get file metadata'))
        }
        plan.evidence.push('Filesystem Search', 'Filesystem Read')
      }

      if (lower.includes('language') || lower.includes('framework')) {
        plan.steps.push(createExecutionStep('vscode.editor.active', 'Get active editor'))
        plan.steps.push(createExecutionStep('workspace.getWorkspaceSnapshot', 'Read Workspace Snapshot'))
        plan.evidence.push('VS Code Context', 'Workspace Snapshot')
      }

      if (lower.includes('git') || lower.includes('changed') || lower.includes('modified')) {
        plan.steps.push(createExecutionStep('vscode.git.status', 'Get Git Status'))
        plan.evidence.push('Git Status')
      }

      if (lower.includes('error') || lower.includes('diagnostic') || lower.includes('problem')) {
        plan.steps.push(createExecutionStep('vscode.diagnostics', 'Get Diagnostics'))
        plan.evidence.push('Diagnostics')
      }

      if (lower.includes('look at this') || lower.includes('what do you see') || lower.includes('describe image') || 
          lower.includes('analyze screenshot') || lower.includes('read this pdf') || lower.includes('ocr') ||
          lower.includes('camera') || lower.includes('screen') || lower.includes('diagram') ||
          lower.includes('ui') || lower.includes('chart') || lower.includes('image') || lower.includes('photo') ||
          lower.includes('picture') || lower.includes('screenshot') || lower.includes('scan') || lower.includes('document')) {
        const capabilityId = lower.includes('screen') || lower.includes('screenshot') ? 'vision.screen' :
                            lower.includes('camera') || lower.includes('photo') ? 'vision.camera' :
                            lower.includes('pdf') || lower.includes('document') ? 'vision.document' :
                            lower.includes('ocr') || lower.includes('scan') ? 'vision.ocr' :
                            'vision.analyze'
        plan.steps.push(createExecutionStep(capabilityId, capabilityId.replace('vision.', 'Analyze ').replace(/\b\w/g, l => l.toUpperCase()), { prompt: query }))
        plan.evidence.push('Vision Analysis')
      }

      if (lower.includes('latest') || lower.includes('news') || lower.includes('current') || lower.includes('today') ||
          lower.includes('search') || lower.includes('browse') || lower.includes('internet') || lower.includes('online')) {
        plan.steps.push(createExecutionStep('knowledge.search', 'Search Internet', { query }))
        plan.steps.push(createExecutionStep('reasoning.generate', 'Generate response from search', { prompt: `Based on internet search results for: ${query}`, persona, model }))
        plan.evidence.push('Internet Search')
      }
    } else {
      console.log(`[EXECUTIVE] No capability runtime available`)
    }

    if (plan.steps.length === 0) {
      plan.steps.push(createExecutionStep('conversation.runtime', 'Conversation response', { text: query, prompt: query, persona, model }))
      plan.evidence.push('Executive Reasoning')
    }

    plan.confidence = this.computePlanConfidence(plan)
    plan.updatedAt = Date.now()
    this.currentPlan = plan
    console.log(`[EXECUTIVE] plan() returning plan with ${plan.steps.length} steps, confidence: ${plan.confidence}`)
    return cloneExecutionPlan(plan)
  }

  subscribe(listener: (s: ExecutiveSnapshot) => void): () => void {
    this.subscribers.add(listener)
    return () => {
      this.subscribers.delete(listener)
    }
  }

  reset(): void {
    this.goals.reset()
    this.focus.reset()
    this.interrupts.reset()
    this.intentGen.reset()
    this.conversation = { phase: 'idle' }
    this.memory = {}
    this.world = {}
    this.attention = {}
    this.relationship = {}
    this.cognitive = {}
    this.vscode = {}
    this.workspaceSnapshot = {}
    this.currentPlan = null
    this.metrics.clear()
    this.state = defaultExecutiveState()
    this.intent = this.intentGen.generate(this.baseContext())
  }

  // --- Decision pipeline ------------------------------------------------------

  private recompute(): void {
    const goalActive = this.goals.count() > 0
    const currentGoal = this.goals.current()
    const worldSalience = clamp01(this.world.salience ?? this.attention.notificationSalience ?? 0)
    const interrupting = this.interrupts.shouldPreempt()

    // Focus resolution.
    const goalFocus: FocusTarget =
      this.cognitive.goalFocus ?? focusFromGoal(currentGoal?.label) ?? this.attention.target ?? 'internal'
    const focusResult = this.focus.select({
      goalFocus,
      conversationPhase: this.conversation.phase,
      worldSalience,
      interrupting
    })

    // Priority + urgency resolution.
    const { priority, urgency } = this.priority.resolve({
      goalWeight: currentGoal?.weight ?? 0.3,
      interruptSalience: this.interrupts.topSalience(),
      worldSalience,
      confidence: this.attention.confidence ?? 0.5
    })

    // Reasoning / thinking mode selection.
    const reasoningMode: ReasoningMode = this.cognitive.reasoning ?? (interrupting ? 'reactive' : this.deriveReasoning(priority))
    const thinkingMode: ThinkingMode = this.deriveThinkingMode(reasoningMode, this.cognitive.thinking ?? false)

    const context: IntentContext = {
      focus: focusResult.focus,
      focusStrength: focusResult.strength,
      priority,
      urgency,
      confidence: this.attention.confidence ?? 0.5,
      reasoningMode,
      interrupting,
      hasPendingTask: this.cognitive.hasPendingTask ?? false,
      goalActive,
      conversationPhase: this.conversation.phase,
      worldSalience,
      proactivitySignal: this.relationship.interactionFrequency ?? this.relationship.familiarity ?? 0,
      needsClarification: this.cognitive.needsClarification ?? false,
      inProgress: this.cognitive.thinking ?? false
    }

    const intent = this.intentGen.generate(context)

    this.state = {
      currentGoal,
      goalStack: this.goals.list(),
      focus: focusResult.focus,
      focusStrength: clamp01(this.focus.getStrength()),
      currentIntent: intent.decision,
      priority,
      interruptState: this.interrupts.getState(),
      pendingInterrupts: this.interrupts.pendingSnapshot(),
      reasoningMode,
      confidence: intent.confidence,
      urgency,
      thinkingMode,
      revision: this.state.revision + 1,
      updatedAt: this.now()
    }
    this.intent = intent
    this.emit()
  }

  private baseContext(): IntentContext {
    return {
      focus: 'none',
      focusStrength: 0,
      priority: 'background',
      urgency: 0,
      confidence: 0.5,
      reasoningMode: 'reactive',
      interrupting: false,
      hasPendingTask: false,
      goalActive: false,
      conversationPhase: 'idle',
      worldSalience: 0,
      proactivitySignal: 0,
      needsClarification: false,
      inProgress: false
    }
  }

  private deriveReasoning(priority: import('./types').Priority): ReasoningMode {
    switch (priority) {
      case 'critical':
        return 'reactive'
      case 'high':
        return 'analytical'
      case 'normal':
        return 'deliberative'
      case 'low':
        return 'reflective'
      case 'background':
      default:
        return 'reactive'
    }
  }

  private deriveThinkingMode(reasoning: ReasoningMode, thinking: boolean): ThinkingMode {
    if (!thinking && reasoning === 'reactive') return 'idle'
    if (reasoning === 'creative' || reasoning === 'reflective') return 'continuous'
    if (reasoning === 'analytical' || reasoning === 'deliberative') return 'deep'
    return thinking ? 'shallow' : 'idle'
  }

  private computePlanConfidence(plan: ExecutionPlan): number {
    if (plan.steps.length === 0) return 0.3
    const hasWorkspace = plan.steps.some(s => s.capabilityId.startsWith('workspace.'))
    const hasVSCode = plan.steps.some(s => s.capabilityId.startsWith('vscode.'))
    const hasFilesystem = plan.steps.some(s => s.capabilityId.startsWith('filesystem.'))
    const sourceCount = [hasWorkspace, hasVSCode, hasFilesystem].filter(Boolean).length
    const base = 0.5 + sourceCount * 0.15
    return Math.min(0.98, Math.max(0.3, base))
  }

  recordCapabilityCall(capabilityId: string, durationMs: number, success: boolean): void {
    const existing = this.metrics.get(capabilityId) ?? { ...DEFAULT_METRICS, capabilityId }
    existing.calls += 1
    existing.totalTimeMs += durationMs
    if (success) existing.successes += 1
    else existing.failures += 1
    existing.lastUsed = Date.now()
    this.metrics.set(capabilityId, existing)
  }

  private snapshot(): ExecutiveSnapshot {
    return { state: cloneExecutiveState(this.state), intent: { ...this.intent } }
  }

  private emit(): void {
    if (this.subscribers.size === 0) return
    const snap = this.snapshot()
    this.subscribers.forEach((l) => l(snap))
  }
}

function focusFromGoal(label: string | undefined): FocusTarget | null {
  if (!label) return null
  const l = label.toLowerCase()
  if (l.includes('task')) return 'task'
  if (l.includes('automation')) return 'automation'
  if (l.includes('tool')) return 'tool'
  if (l.includes('plugin')) return 'plugin'
  if (l.includes('memory') || l.includes('remember')) return 'memory'
  if (l.includes('knowledge') || l.includes('learn')) return 'knowledge'
  if (l.includes('world') || l.includes('observe')) return 'world'
  return 'internal'
}

function clamp01(v: number): number {
  if (Number.isNaN(v)) return 0
  return Math.min(1, Math.max(0, v))
}

export { ExecutiveDecision, ExecutiveGoal, ExecutiveIntent, FocusTarget, InterruptSeverity, ReasoningMode, ThinkingMode }
