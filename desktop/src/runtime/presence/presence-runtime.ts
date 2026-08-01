import {
  AnimationRuntimeStatus,
  ConnectionState,
  EmbodimentStatus,
  EmbodimentType,
  ExpressiveParams,
  FrameState,
  GpuContextStatus,
  PresenceHealth,
  PresenceLifecycle,
  RendererHealthStatus,
  DEFAULT_EXPRESSIVE_PARAMS,
  PresenceState,
  PresenceEventType,
  PresenceEvent
} from '../types'
import type { RuntimeSnapshot } from '../sources/types'
import type { RuntimeState } from '@zaram/engine'
import {
  IEmbodiment,
  IEngineAdapter,
  IExpressiveParamsSource,
  IPresenceDiagnostics,
  IPresenceRuntime
} from '../interfaces'
import { PresenceDiagnostics } from './diagnostics'
import { CharacterRuntime } from '../embodiment/character-runtime'
import { CharacterFrame, EmotionEvent } from '../embodiment/types'
import { toCharacterFrame } from '../embodiment/character-frame'
import { CognitiveBundle } from '../cognitive/bundle'
import { attentionTargetFromCognitive } from '../cognitive/attention-runtime'
import { WorldRuntime, IWorldStateProvider } from '../world'
import type { ExecutiveRuntime, ExecutiveSnapshot, ExecutiveIntent } from '../executive'
import type { IExecutionRuntime } from '../execution'
import type { IWorkspaceRuntime } from '../workspace'
import { eventBus, type ZaramEventType } from '../event-bus'

type Lifecycle = 'uninitialized' | 'initializing' | 'running' | 'paused' | 'shutdown'

export interface PresenceRuntimeOptions {
  engineAdapter?: IEngineAdapter
  stateProvider?: {
    getSnapshot(): RuntimeSnapshot
    subscribe?(listener: (snapshot: RuntimeSnapshot) => void): () => void
  }
  personality?: IExpressiveParamsSource
  embodiment?: IEmbodiment
  // Optional injected CharacterRuntime. When present, the PresenceRuntime feeds
  // it from the aggregated runtime snapshot (event-driven) and projects a
  // renderer-neutral CharacterFrame. The legacy FrameState pipeline is untouched.
  characterRuntime?: CharacterRuntime
  // Optional injected CognitiveBundle (Milestone 1.2). Internal AI state,
  // independent of rendering. Fed event-driven from the aggregator; advanced on
  // the existing frame tick. Never reaches the renderer.
  cognitiveRuntime?: CognitiveBundle
  // Optional injected WorldRuntime (Milestone 1.3). Intelligence Runtime that
  // aggregates system perception into an immutable WorldState. Advanced on the
  // existing 30Hz frame tick. Never reaches the renderer.
  worldRuntime?: IWorldStateProvider
  // Optional injected ExecutiveRuntime (Milestone 1.4). The AI's single
  // authority for high-level decision-making. Advanced on the existing 30Hz
  // frame tick via DI only. It never reaches the renderer or CharacterFrame;
  // CharacterRuntime receives only the high-level Intent.
  executiveRuntime?: ExecutiveRuntime
  // Optional injected ExecutionRuntime (Milestone 1.6). The ONLY runtime
  // allowed to invoke capabilities. Advanced on the existing 30Hz frame tick
  // via DI only. It never reaches the renderer, embodiment, or CharacterFrame.
  executionRuntime?: IExecutionRuntime
  // Optional injected WorkspaceRuntime (Milestone 2.1). Intelligence Runtime
  // that provides semantic understanding of projects. Advanced on the existing
  // 30Hz frame tick via DI only. It never reaches the renderer, embodiment,
  // or CharacterFrame.
  workspaceRuntime?: IWorkspaceRuntime
}

export class PresenceRuntime implements IPresenceRuntime, IPresenceDiagnostics {
  private embodiment: IEmbodiment | null = null
  private lifecycle: Lifecycle = 'uninitialized'
  private readonly diagnostics = new PresenceDiagnostics()
  private readonly engineAdapter?: IEngineAdapter
  private readonly stateProvider?: {
    getSnapshot(): RuntimeSnapshot
    subscribe?(listener: (snapshot: RuntimeSnapshot) => void): () => void
  }
  private readonly personality?: IExpressiveParamsSource
  private readonly characterRuntime?: CharacterRuntime
  private readonly cognitiveRuntime?: CognitiveBundle
  private readonly worldRuntime?: IWorldStateProvider
  private readonly executiveRuntime?: ExecutiveRuntime
  private readonly executionRuntime?: IExecutionRuntime
  private readonly workspaceRuntime?: IWorkspaceRuntime
  private latestExpressive: ExpressiveParams = DEFAULT_EXPRESSIVE_PARAMS
  private sequence = 0
  private timer: ReturnType<typeof setInterval> | null = null
  private lastTickTime = 0
  private unsubscribeState: (() => void) | null = null
  private animationEngineFailed = false

  // Presence state management
  private currentPresenceState: PresenceState = 'Idle'
  private presenceSubscribers: Set<(event: PresenceEvent) => void> = new Set()
  private currentAudioLevel = 0

  constructor(options: PresenceRuntimeOptions = {}) {
    this.engineAdapter = options.engineAdapter
    this.stateProvider = options.stateProvider
    this.personality = options.personality
    this.embodiment = options.embodiment ?? null
    this.characterRuntime = options.characterRuntime
    this.cognitiveRuntime = options.cognitiveRuntime
    this.worldRuntime = options.worldRuntime
    this.executiveRuntime = options.executiveRuntime
    this.executionRuntime = options.executionRuntime
    this.workspaceRuntime = options.workspaceRuntime
    if (this.embodiment) {
      this.diagnostics.setEmbodiment(this.embodiment.getStatus().type, false)
    }
    if (this.personality) {
      this.latestExpressive = this.personality.getExpressiveParams()
      this.personality.subscribe((params) => {
        this.latestExpressive = params
      })
    }
    
    // Subscribe to Executive Runtime events - the new single source of truth
    this.unsubscribeExecutiveIntent = eventBus.subscribe('executive:intent_changed' as ZaramEventType, (event) => {
      const data = event.data as { decision: string; confidence: number; reasoning: string }
      this.updatePresenceFromIntent(data.decision, data.confidence, data.reasoning)
    })
    this.unsubscribeExecutiveState = eventBus.subscribe('executive:state_changed' as ZaramEventType, (event) => {
      const data = event.data as { focus: string; focus_strength: number; priority: string; urgency: number; goal_active: boolean; conversation_phase: string }
      this.updatePresenceFromState(data.focus, data.focus_strength, data.priority, data.urgency, data.goal_active, data.conversation_phase)
    })
    this.unsubscribeExecutiveFocus = eventBus.subscribe('executive:focus_changed' as ZaramEventType, (event) => {
      const data = event.data as { focus: string; strength: number }
      this.updatePresenceFromFocus(data.focus, data.strength)
    })
    this.unsubscribeExecutivePriority = eventBus.subscribe('executive:priority_changed' as ZaramEventType, (event) => {
      const data = event.data as { priority: string; urgency: number }
      this.updatePresenceFromPriority(data.priority, data.urgency)
    })
    this.unsubscribeExecutiveInterrupt = eventBus.subscribe('executive:interrupt_raised' as ZaramEventType, (event) => {
      const data = event.data as { severity: string; source: string }
      this.updatePresenceFromInterrupt(data.severity, data.source)
    })

    // Sprint C.3: Subscribe to Voice Runtime events for presence state
    this.unsubscribeVoiceStarted = eventBus.subscribe('voice:started' as ZaramEventType, (event) => {
      this.setPresenceState('Speaking')
    })
    this.unsubscribeVoiceFinished = eventBus.subscribe('voice:finished' as ZaramEventType, (event) => {
      this.setPresenceState('Idle')
    })
    this.unsubscribeVoiceFailed = eventBus.subscribe('voice:failed' as ZaramEventType, (event) => {
      this.setPresenceState('Error')
    })
    // Subscribe to voice.level for orb visualization (RMS amplitude)
    this.unsubscribeVoiceLevel = eventBus.subscribe('voice:level' as ZaramEventType, (event) => {
      const data = event.data as { level: number; timestamp: number; request_id?: string }
      if (data.level !== undefined) {
        this.setAudioLevel(data.level)
      }
    })
    // Subscribe to voice.chunk for orb visualization (waveform data)
    this.unsubscribeVoiceChunk = eventBus.subscribe('voice:chunk' as ZaramEventType, (event) => {
      const data = event.data as { audioId: string; sequence: number; rmsLevel?: number; timestamp: number }
      // Emit presence event with chunk data for orb
      this.emitPresenceEvent({
        type: 'presence:voice_chunk',
        timestamp: data.timestamp,
        payload: { audioId: data.audioId, sequence: data.sequence, rmsLevel: data.rmsLevel }
      })
    })

    // Subscribe to Knowledge/Search events
    this.unsubscribeKnowledgeSearchStarted = eventBus.subscribe('knowledge:search_started' as ZaramEventType, (event) => {
      this.setPresenceState('SearchingWeb')
    })
    this.unsubscribeKnowledgeSearchComplete = eventBus.subscribe('knowledge:search_complete' as ZaramEventType, (event) => {
      // Return to previous state or idle
      this.setPresenceState('Thinking')
    })
    this.unsubscribeMemoryRecalled = eventBus.subscribe('knowledge:memory_recalled' as ZaramEventType, (event) => {
      this.setPresenceState('SearchingMemory')
    })

    // Subscribe to Conversation phase events
    this.unsubscribeConversationPhase = eventBus.subscribe('conversation:phase_changed' as ZaramEventType, (event) => {
      const data = event.data as { phase: string; activity: number; previous_phase?: string }
      this.updatePresenceFromConversationPhase(data.phase)
    })

    // Subscribe to Reasoning events
    this.unsubscribeReasoningStarted = eventBus.subscribe('reasoning:started' as ZaramEventType, (event) => {
      this.setPresenceState('Thinking')
    })
    this.unsubscribeReasoningFinished = eventBus.subscribe('reasoning:finished' as ZaramEventType, (event) => {
      this.setPresenceState('Speaking')
    })

    // Event-driven feed: subscribe to the aggregated runtime snapshot so the
    // CharacterRuntime (emotion) AND the CognitiveBundle (internal AI state)
    // receive events from conversation, voice, knowledge, system, and memory
    // sources. No polling, no timers.
    if ((this.characterRuntime || this.cognitiveRuntime || this.executiveRuntime) && this.stateProvider?.subscribe) {
      this.unsubscribeState = this.stateProvider.subscribe((snapshot) => {
        this.feedCharacterFromSnapshot(snapshot)
        this.feedCognitiveFromSnapshot(snapshot)
        this.feedExecutiveFromSnapshot(snapshot)
        // NO LONGER update presence state from snapshot - it comes from Executive events
      })
      // Seed once with the current snapshot.
      const seed = this.stateProvider.getSnapshot()
      this.feedCharacterFromSnapshot(seed)
      this.feedCognitiveFromSnapshot(seed)
      this.feedExecutiveFromSnapshot(seed)
    }
  }

  private unsubscribeExecutiveIntent: (() => void) | null = null
  private unsubscribeExecutiveState: (() => void) | null = null
  private unsubscribeExecutiveFocus: (() => void) | null = null
  private unsubscribeExecutivePriority: (() => void) | null = null
  private unsubscribeExecutiveInterrupt: (() => void) | null = null

  // Voice runtime subscriptions
  private unsubscribeVoiceStarted: (() => void) | null = null
  private unsubscribeVoiceFinished: (() => void) | null = null
  private unsubscribeVoiceFailed: (() => void) | null = null
  private unsubscribeVoiceLevel: (() => void) | null = null
  private unsubscribeVoiceChunk: (() => void) | null = null

  // Knowledge/Search subscriptions
  private unsubscribeKnowledgeSearchStarted: (() => void) | null = null
  private unsubscribeKnowledgeSearchComplete: (() => void) | null = null
  private unsubscribeMemoryRecalled: (() => void) | null = null

  // Conversation subscriptions
  private unsubscribeConversationPhase: (() => void) | null = null

  // Reasoning subscriptions
  private unsubscribeReasoningStarted: (() => void) | null = null
  private unsubscribeReasoningFinished: (() => void) | null = null

  // Presence state event system
  subscribe(listener: (event: PresenceEvent) => void): () => void {
    this.presenceSubscribers.add(listener)
    return () => this.presenceSubscribers.delete(listener)
  }

  getPresenceState(): PresenceState {
    return this.currentPresenceState
  }

  setPresenceState(state: PresenceState): void {
    if (this.currentPresenceState === state) return
    const previousState = this.currentPresenceState
    this.currentPresenceState = state
    this.emitPresenceEvent({
      type: 'presence:state_changed',
      timestamp: Date.now(),
      payload: { state, previousState }
    })
    // Also publish to global event bus for IPC forwarding
    eventBus.publish('presence:state_changed' as ZaramEventType, { state, previousState }, 'presence')
  }

  setAudioLevel(level: number): void {
    const clamped = Math.min(1, Math.max(0, level))
    this.currentAudioLevel = clamped
    this.emitPresenceEvent({
      type: 'presence:audio_level',
      timestamp: Date.now(),
      payload: { audioLevel: clamped }
    })
  }

  private emitPresenceEvent(event: PresenceEvent): void {
    this.presenceSubscribers.forEach(cb => {
      try { cb(event) } catch { /* ignore subscriber errors */ }
    })
  }

  private updatePresenceFromIntent(decision: string, confidence: number, reasoning: string): void {
    const lowerDecision = decision.toLowerCase()
    
    // Map executive decisions to presence states
    if (lowerDecision.includes('reply') || lowerDecision.includes('speak')) {
      this.setPresenceState('Speaking')
    } else if (lowerDecision.includes('think') || lowerDecision.includes('reason') || lowerDecision.includes('deliberate') || lowerDecision.includes('analyze')) {
      this.setPresenceState('Thinking')
    } else if (lowerDecision.includes('search') || lowerDecision.includes('browse') || lowerDecision.includes('look up')) {
      this.setPresenceState('SearchingWeb')
    } else if (lowerDecision.includes('memory') || lowerDecision.includes('recall') || lowerDecision.includes('remember')) {
      this.setPresenceState('SearchingMemory')
    } else if (lowerDecision.includes('plan') || lowerDecision.includes('schedule') || lowerDecision.includes('organize')) {
      this.setPresenceState('Planning')
    } else if (lowerDecision.includes('learn') || lowerDecision.includes('study') || lowerDecision.includes('absorb')) {
      this.setPresenceState('Learning')
    } else if (lowerDecision.includes('wait') || lowerDecision.includes('listen') || lowerDecision.includes('idle')) {
      this.setPresenceState('Listening')
    } else if (lowerDecision.includes('error') || lowerDecision.includes('fail') || lowerDecision.includes('cancel')) {
      this.setPresenceState('Error')
    }
  }

  private updatePresenceFromState(focus: string, focusStrength: number, priority: string, urgency: number, goalActive: boolean, conversationPhase: string): void {
    // If we have an active goal or high priority/urgency, we're in an active state
    if (goalActive && (priority === 'high' || priority === 'critical' || urgency > 0.7)) {
      if (focus.includes('speak') || focus.includes('reply')) {
        this.setPresenceState('Speaking')
      } else if (focus.includes('think') || focus.includes('reason')) {
        this.setPresenceState('Thinking')
      } else if (focus.includes('search')) {
        this.setPresenceState('SearchingWeb')
      } else if (focus.includes('memory')) {
        this.setPresenceState('SearchingMemory')
      } else if (focus.includes('plan')) {
        this.setPresenceState('Planning')
      } else if (focus.includes('learn')) {
        this.setPresenceState('Learning')
      }
    } else if (conversationPhase === 'listening') {
      this.setPresenceState('Listening')
    } else if (conversationPhase === 'speaking') {
      this.setPresenceState('Speaking')
    } else if (conversationPhase === 'thinking' || conversationPhase === 'generating' || conversationPhase === 'working') {
      this.setPresenceState('Thinking')
    }
  }

  private updatePresenceFromFocus(focus: string, strength: number): void {
    // Focus changes can refine presence state
    if (strength > 0.8) {
      if (focus.includes('external') || focus.includes('world') || focus.includes('search')) {
        // Strong external focus = searching
        this.setPresenceState('SearchingWeb')
      }
    }
  }

  private updatePresenceFromPriority(priority: string, urgency: number): void {
    // High priority/critical urgency overrides to active states
    if (priority === 'critical' || urgency > 0.8) {
      // Don't override Speaking - let speech complete
      if (this.currentPresenceState !== 'Speaking') {
        this.setPresenceState('Thinking')
      }
    }
  }

  private updatePresenceFromInterrupt(severity: string, source: string): void {
    if (severity === 'critical' || severity === 'high') {
      this.setPresenceState('Error')
    }
  }

  private updatePresenceFromConversationPhase(phase: string): void {
    const lowerPhase = phase.toLowerCase()
    if (lowerPhase === 'speaking') {
      this.setPresenceState('Speaking')
    } else if (lowerPhase === 'listening') {
      this.setPresenceState('Listening')
    } else if (lowerPhase === 'thinking' || lowerPhase === 'generating' || lowerPhase === 'working') {
      this.setPresenceState('Thinking')
    } else if (lowerPhase === 'idle' || lowerPhase === 'sleeping') {
      this.setPresenceState('Idle')
    } else if (lowerPhase === 'interrupted' || lowerPhase === 'error') {
      this.setPresenceState('Error')
    }
  }

  private updatePresenceStateFromSnapshot(snapshot: RuntimeSnapshot): void {
    // Determine presence state from conversation phase and voice level
    const phase = snapshot.conversation.phase
    const voiceLevel = snapshot.voice.voiceLevel

    let newState: PresenceState = 'Idle'

    switch (phase) {
      case 'listening':
        newState = 'Listening'
        break
      case 'thinking':
      case 'generating':
      case 'working':
        newState = voiceLevel > 0.1 ? 'Speaking' : 'Thinking'
        break
      case 'speaking':
        newState = 'Speaking'
        break
      case 'interrupted':
        newState = 'Error'
        break
      case 'idle':
      case 'sleeping':
      default:
        newState = 'Idle'
        break
    }

    // Override with executive intent if available
    const execSnapshot = this.executiveRuntime?.getSnapshot()
    if (execSnapshot) {
      const intent = (execSnapshot.intent?.decision || '').toLowerCase()
      const focus = (execSnapshot.state?.focus || '').toLowerCase()
      if (intent.includes('search') || focus.includes('search')) {
        newState = 'SearchingWeb'
      } else if (intent.includes('memory') || focus.includes('memory')) {
        newState = 'SearchingMemory'
      } else if (intent.includes('plan') || focus.includes('plan')) {
        newState = 'Planning'
      } else if (intent.includes('learn') || focus.includes('learn')) {
        newState = 'Learning'
      } else if (intent.includes('error') || focus.includes('error')) {
        newState = 'Error'
      }
    }

    this.setPresenceState(newState)
  }

  private feedCharacterFromSnapshot(snapshot: RuntimeSnapshot): void {
    if (!this.characterRuntime) return
    const events: EmotionEvent[] = []
    // Conversation: phase drives intent + curiosity/attention.
    switch (snapshot.conversation.phase) {
      case 'listening':
        this.characterRuntime.setIntent('listening')
        events.push({ source: 'conversation', attention: 0.1, curiosity: 0.05 })
        break
      case 'thinking':
      case 'generating':
      case 'working':
        this.characterRuntime.setIntent('thinking')
        events.push({ source: 'conversation', thinkingLoad: 0.2, focus: 0.1 })
        break
      case 'speaking':
        this.characterRuntime.setIntent('speaking')
        events.push({ source: 'conversation', speakingEnergy: 0.3, confidence: 0.05 })
        break
      case 'interrupted':
        this.characterRuntime.triggerSurprise()
        break
      case 'idle':
      case 'sleeping':
      default:
        this.characterRuntime.setIntent('idle')
        events.push({ source: 'conversation', fatigue: 0.02 })
        break
    }
    // Voice: speaking energy + arousal from voice level.
    events.push({
      source: 'voice',
      speakingEnergy: snapshot.voice.voiceLevel * 0.4,
      arousal: (snapshot.voice.voiceLevel - snapshot.voice.microphoneLevel) * 0.2
    })
    // System: cognitive load -> thinking load + fatigue.
    events.push({
      source: 'system',
      thinkingLoad: snapshot.system.cognitiveLoad * 0.3,
      fatigue: snapshot.system.cognitiveLoad * 0.05
    })
    // Memory: recall drives curiosity.
    events.push({ source: 'memory', curiosity: snapshot.memory.recall * 0.1 })
    for (const ev of events) this.characterRuntime.emitEmotion(ev)
  }

  // Milestone 1.2: feed the CognitiveBundle from the same aggregated snapshot.
  // This keeps internal AI state independent of rendering and event-driven
  // (single subscription, no polling).
  private feedCognitiveFromSnapshot(snapshot: RuntimeSnapshot): void {
    if (!this.cognitiveRuntime) return
    const bundle = this.cognitiveRuntime
    const phase = snapshot.conversation.phase
    bundle.emitCognitive({ kind: 'phase', phase })
    // Map conversation phase -> attention target + relationship interaction.
    switch (phase) {
      case 'listening':
        bundle.emitAttention({ target: 'speaker', memoryRelevance: snapshot.memory.recall })
        bundle.emitRelationship({ interaction: true, familiarityDelta: 0.01 })
        break
      case 'speaking':
        bundle.emitAttention({ target: 'conversation' })
        bundle.emitRelationship({ interaction: true })
        break
      case 'thinking':
      case 'generating':
      case 'working':
        bundle.emitAttention({ target: 'internal' })
        break
      case 'interrupted':
        bundle.emitAttention({ target: 'notification', notification: { id: 'interrupt', severity: 0.8 } })
        break
      case 'idle':
      case 'sleeping':
      default:
        bundle.emitAttention({ target: 'none' })
        break
    }
    // Memory relevance feeds attention; knowledge requests are issued when the
    // system cognitive load is high (a stand-in for "needs to look something up").
    if (snapshot.system.cognitiveLoad > 0.7) {
      bundle.emitCognitive({ kind: 'knowledgeRequest', query: 'context' })
    }
    // Drive CharacterRuntime intent from the cognitive reasoning state so the
    // embodiment follows the AI's internal state (thinking/listening/speaking).
    if (this.characterRuntime) {
      const reasoning = bundle.getCognitiveState().reasoning
      if (reasoning === 'perceiving') this.characterRuntime.setIntent('listening')
      else if (reasoning === 'reasoning' || reasoning === 'planning') this.characterRuntime.setIntent('thinking')
      else if (reasoning === 'deciding') this.characterRuntime.setIntent('speaking')
      else this.characterRuntime.setIntent('idle')
    }
  }

  // Milestone 1.4: feed the ExecutiveRuntime from the SAME aggregated snapshot.
  // The executive is the single authority for high-level decision-making; it
  // observes conversation, memory, world, attention, relationship, and cognitive
  // signals. It never reaches the renderer or CharacterFrame. No polling, no
  // timers — purely event-driven from the existing aggregator subscription.
  private feedExecutiveFromSnapshot(snapshot: RuntimeSnapshot): void {
    if (!this.executiveRuntime) return
    this.executiveRuntime.ingestConversation({ phase: snapshot.conversation.phase, activity: snapshot.conversation.activity })
    this.executiveRuntime.ingestMemory({ recall: snapshot.memory.recall, activity: snapshot.memory.activity })
    const world = this.worldRuntime?.getWorldState()
    this.executiveRuntime.ingestWorld({
      salience: world?.notification.peakSalience ?? 0,
      foreground: world?.environment.isForeground ?? true
    })
    const attention = this.cognitiveRuntime?.getAttentionState()
    this.executiveRuntime.ingestAttention({
      target: attention ? attentionTargetToFocus(attention.current) : undefined,
      confidence: attention?.focusConfidence,
      notificationSalience: attention?.notificationSalience
    })
    const relationship = this.cognitiveRuntime?.getRelationshipState()
    this.executiveRuntime.ingestRelationship({
      familiarity: relationship?.familiarity,
      interactionFrequency: relationship?.interactionFrequency
    })
    const cognitive = this.cognitiveRuntime?.getCognitiveState()
    this.executiveRuntime.ingestCognitive({
      reasoning: cognitive ? reasoningToMode(cognitive.reasoning) : undefined,
      thinking: cognitive?.thinking,
      hasPendingTask: (cognitive?.taskQueue.length ?? 0) > 0
    })
  }

  async initialize(): Promise<void> {
    if (this.lifecycle !== 'uninitialized') return
    this.lifecycle = 'initializing'
    this.diagnostics.setPresenceRuntimeStatus('initializing')
    this.diagnostics.setAnimationConnection('disconnected')
    if (this.embodiment) {
      await this.embodiment.initialize()
      this.diagnostics.setEmbodiment(this.embodiment.getStatus().type, this.embodiment.getStatus().healthy)
    }
  }

  async start(): Promise<void> {
    if (this.lifecycle === 'running') return
    if (this.lifecycle === 'uninitialized' && this.embodiment) {
      await this.initialize()
    }
    if (this.embodiment && this.lifecycle !== 'paused') {
      await this.embodiment.start()
    }
    this.diagnostics.begin()
    this.diagnostics.setAnimationConnection('connected')
    this.diagnostics.setPresenceRuntimeStatus('running')
    this.diagnostics.setAnimationRuntimeStatus('running')
    this.lifecycle = 'running'

    if (this.engineAdapter && this.stateProvider) {
      this.lastTickTime = performance.now()
      this.timer = setInterval(() => this.tick(), 1000 / 30)
    }
  }

  async pause(): Promise<void> {
    if (this.lifecycle !== 'running') return
    if (this.embodiment) await this.embodiment.pause()
    this.stopEngineTick()
    this.diagnostics.setAnimationConnection('disconnected')
    this.diagnostics.setPresenceRuntimeStatus('paused')
    this.diagnostics.setAnimationRuntimeStatus('paused')
    this.lifecycle = 'paused'
  }

  async resume(): Promise<void> {
    if (this.lifecycle !== 'paused') return
    if (this.embodiment) await this.embodiment.resume()
    this.diagnostics.setAnimationConnection('connected')
    this.diagnostics.setPresenceRuntimeStatus('running')
    this.diagnostics.setAnimationRuntimeStatus('running')
    this.lifecycle = 'running'
    this.lastTickTime = performance.now()

    if (this.engineAdapter && this.stateProvider) {
      this.timer = setInterval(() => this.tick(), 1000 / 30)
    }
  }

  async shutdown(): Promise<void> {
    if (this.lifecycle === 'shutdown') return
    if (this.embodiment) {
      try {
        await this.embodiment.shutdown()
      } catch {
        /* embodiment shutdown is best-effort */
      }
    }
    this.stopEngineTick()
    if (this.unsubscribeState) {
      this.unsubscribeState()
      this.unsubscribeState = null
    }
    // Unsubscribe from Executive events
    this.unsubscribeExecutiveIntent?.()
    this.unsubscribeExecutiveState?.()
    this.unsubscribeExecutiveFocus?.()
    this.unsubscribeExecutivePriority?.()
    this.unsubscribeExecutiveInterrupt?.()
    this.unsubscribeExecutiveIntent = null
    this.unsubscribeExecutiveState = null
    this.unsubscribeExecutiveFocus = null
    this.unsubscribeExecutivePriority = null
    this.unsubscribeExecutiveInterrupt = null

    // Unsubscribe from Voice events
    this.unsubscribeVoiceStarted?.()
    this.unsubscribeVoiceFinished?.()
    this.unsubscribeVoiceFailed?.()
    this.unsubscribeVoiceLevel?.()
    this.unsubscribeVoiceChunk?.()
    this.unsubscribeVoiceStarted = null
    this.unsubscribeVoiceFinished = null
    this.unsubscribeVoiceFailed = null
    this.unsubscribeVoiceLevel = null
    this.unsubscribeVoiceChunk = null

    // Unsubscribe from Knowledge/Search events
    this.unsubscribeKnowledgeSearchStarted?.()
    this.unsubscribeKnowledgeSearchComplete?.()
    this.unsubscribeMemoryRecalled?.()
    this.unsubscribeKnowledgeSearchStarted = null
    this.unsubscribeKnowledgeSearchComplete = null
    this.unsubscribeMemoryRecalled = null

    // Unsubscribe from Conversation events
    this.unsubscribeConversationPhase?.()
    this.unsubscribeConversationPhase = null

    // Unsubscribe from Reasoning events
    this.unsubscribeReasoningStarted?.()
    this.unsubscribeReasoningFinished?.()
    this.unsubscribeReasoningStarted = null
    this.unsubscribeReasoningFinished = null

    this.diagnostics.setAnimationConnection('disconnected')
    this.diagnostics.setPresenceRuntimeStatus('shutdown')
    this.diagnostics.setAnimationRuntimeStatus('stopped')
    this.lifecycle = 'shutdown'
  }

  setEmbodiment(embodiment: IEmbodiment): void {
    this.embodiment = embodiment
    this.diagnostics.setEmbodiment(embodiment.getStatus().type, embodiment.getStatus().healthy)
  }

  consumeFrameState(frameState: FrameState): void {
    if (this.lifecycle !== 'running' || !this.embodiment) return
    this.sequence += 1
    frameState.sequence = this.sequence
    this.embodiment.setFrameState(frameState)
    this.diagnostics.recordFrame()
    this.diagnostics.recordFrameStateReceived()
    this.diagnostics.setAnimationConnection('connected')
    if (this.embodiment.getStatus().healthy === false) {
      this.diagnostics.setEmbodiment(this.embodiment.getStatus().type, false)
    }
  }

  getStatus(): EmbodimentStatus {
    if (!this.embodiment) {
      return {
        type: 'none',
        state: this.lifecycle === 'shutdown' ? 'shutdown' : 'uninitialized',
        healthy: false,
        lastUpdated: Date.now(),
        message: 'No embodiment attached'
      }
    }
    return this.embodiment.getStatus()
  }

  // --- Milestone 1.1: renderer-neutral character frame projection ---------
  // The Renderer receives ONLY this frame. It has no visibility into emotion,
  // thinking, conversation, voice, memory, or knowledge concerns.
  getCharacterFrame(): CharacterFrame | null {
    if (!this.characterRuntime) return null
    this.sequence += 1
    return toCharacterFrame(this.characterRuntime.getState(), this.sequence)
  }

  getRendererFrame(): Record<string, unknown> | null {
    const snap = this.executiveRuntime?.getSnapshot()
    const intent = snap?.intent?.decision || snap?.state?.currentIntent || 'idle'
    const confidence = snap?.state?.confidence ?? 0.5
    const systemState = mapIntentToSystemState(intent)

    return {
      visual: {
        presence: 0.5,
        energy: systemState === 'Thinking' ? 0.7 : systemState === 'Speaking' ? 0.8 : systemState === 'Working' ? 0.9 : 0.4,
        focus: systemState === 'Thinking' ? 0.8 : 0.5,
        activity: systemState === 'Working' ? 0.9 : systemState === 'Thinking' ? 0.6 : 0.3
      },
      audio: {
        voiceLevel: this.currentAudioLevel,
        microphoneLevel: 0
      },
      emotion: {
        calmness: 0.5,
        confidence,
        curiosity: 0.5,
        warmth: 0.5,
        empathy: 0.5,
        playfulness: 0.3
      },
      system: {
        state: systemState,
        cognitiveLoad: 0.2,
        visualIdentity: 0.5
      },
      metadata: {
        timestamp: Date.now(),
        correlationId: 'presence',
        version: '1.0.0'
      },
      sequence: this.sequence
    }
  }

  hasCharacterRuntime(): boolean {
    return Boolean(this.characterRuntime)
  }

  // --- Milestone 1.2: internal cognition accessors -------------------------
  // These expose the AI's internal state. They are NOT sent to the renderer;
  // the renderer only ever receives CharacterFrame. They exist for the
  // application/cognition layer that consumes the AI separately from rendering.
  hasCognitiveRuntime(): boolean {
    return Boolean(this.cognitiveRuntime)
  }

  getCognitiveState(): ReturnType<CognitiveBundle['getCognitiveState']> | null {
    return this.cognitiveRuntime ? this.cognitiveRuntime.getCognitiveState() : null
  }

  getAttentionState(): ReturnType<CognitiveBundle['getAttentionState']> | null {
    return this.cognitiveRuntime ? this.cognitiveRuntime.getAttentionState() : null
  }

  getRelationshipState(): ReturnType<CognitiveBundle['getRelationshipState']> | null {
    return this.cognitiveRuntime ? this.cognitiveRuntime.getRelationshipState() : null
  }

  // --- Milestone 1.3: world accessors --------------------------------------
  // The Attention Runtime (and any consumer) reads the world only through the
  // IWorldStateProvider interface. The concrete WorldRuntime is never exposed.
  hasWorldRuntime(): boolean {
    return Boolean(this.worldRuntime)
  }

  getWorldState(): IWorldStateProvider | null {
    return this.worldRuntime ?? null
  }

  // --- Milestone 1.4: executive accessors ------------------------------------
  // The ExecutiveRuntime is the single authority for high-level AI
  // decision-making. It is consumed read-only; its internals (goals, planning,
  // confidence, reasoning, memory, relationship) NEVER reach the renderer or
  // CharacterFrame. CharacterRuntime receives only the high-level Intent.
  hasExecutiveRuntime(): boolean {
    return Boolean(this.executiveRuntime)
  }

  getExecutiveSnapshot(): ExecutiveSnapshot | null {
    return this.executiveRuntime ? this.executiveRuntime.getSnapshot() : null
  }

  getExecutiveIntent(): ExecutiveIntent | null {
    return this.executiveRuntime ? this.executiveRuntime.getIntent() : null
  }

  getHealth(): PresenceHealth {
    return this.diagnostics.getHealth()
  }

  getEmbodimentType(): EmbodimentType {
    return this.diagnostics.getEmbodimentType()
  }

  getFrameRate(): number {
    return this.diagnostics.getFrameRate()
  }

  getAnimationConnection(): ConnectionState {
    return this.diagnostics.getAnimationConnection()
  }

  private tick(): void {
    if (this.lifecycle !== 'running' || !this.engineAdapter || !this.stateProvider) return
    if (this.animationEngineFailed) return
    const tickStart = performance.now()
    const snapshot = this.stateProvider.getSnapshot()
    const runtimeState = this.mapSnapshot(snapshot)
    const dt = this.lastTickTime ? Math.min((tickStart - this.lastTickTime) / 1000, 0.1) : 1 / 30
    this.lastTickTime = tickStart
    try {
      const frameState = this.engineAdapter.update(dt, runtimeState)
      const tickEnd = performance.now()
      this.diagnostics.setCpuFrameTime(tickEnd - tickStart)
      this.consumeFrameState(frameState)
    } catch (error) {
      console.error('[PresenceRuntime] Animation engine crashed, disabling:', error)
      this.animationEngineFailed = true
      this.stopEngineTick()
      this.diagnostics.setAnimationRuntimeStatus('stopped')
      this.diagnostics.setAnimationConnection('disconnected')
      this.diagnostics.setPresenceRuntimeStatus('error')
      return
    }
    // Milestone 1.1: drive the injected CharacterRuntime on the SAME existing
    // frame tick. No new render loop is introduced.
    if (this.characterRuntime) {
      this.characterRuntime.update(dt)
    }
    // Milestone 1.2: advance the CognitiveBundle on the SAME existing frame
    // tick. No new render loop is introduced; cognition evolves over time
    // (attention easing, relationship decay) independent of rendering.
    if (this.cognitiveRuntime) {
      this.cognitiveRuntime.update(dt)
    }
    // Milestone 1.3: advance the WorldRuntime on the SAME existing 30Hz frame
    // tick. No new render loop, timer, or polling is introduced; the world's
    // notification salience decays here, time-driven but tick-owned.
    if (this.worldRuntime) {
      this.worldRuntime.update(dt)
    }
    // Milestone 1.4: advance the ExecutiveRuntime on the SAME existing 30Hz
    // frame tick. No new render loop, timer, or polling is introduced. The
    // executive's focus eases and its decision is re-resolved here; it owns all
    // high-level decision-making and never reaches the renderer/CharacterFrame.
    if (this.executiveRuntime) {
      this.executiveRuntime.update(dt)
    }
    // Milestone 1.6: advance the ExecutionRuntime on the SAME existing 30Hz
    // frame tick. No new render loop, timer, or polling is introduced. The
    // execution runtime enforces lifecycle, timeout, retry, cancellation,
    // progress, audit, rollback, and permission enforcement; it is the ONLY
    // runtime that invokes capabilities and never reaches the renderer.
    if (this.executionRuntime) {
      this.executionRuntime.update(dt)
    }
    // Milestone 2.1: advance the WorkspaceRuntime on the SAME existing 30Hz
    // frame tick. No new render loop, timer, or polling is introduced. The
    // workspace runtime provides semantic project understanding and never
    // reaches the renderer, embodiment, or CharacterFrame.
    if (this.workspaceRuntime) {
      this.workspaceRuntime.update(dt)
    }
  }

  private stopEngineTick(): void {
    if (this.timer) {
      clearInterval(this.timer)
      this.timer = null
    }
  }

  private mapSnapshot(snapshot: RuntimeSnapshot): RuntimeState {
    const execSnapshot = this.executiveRuntime?.getSnapshot()
    let derivedState = snapshot.system.state

    if (execSnapshot) {
      const intent = (execSnapshot.intent?.decision || '').toLowerCase()
      const focus = (execSnapshot.state?.focus || '').toLowerCase()
      if (intent.includes('error') || focus.includes('error')) derivedState = 'error'
      else if (intent.includes('speak') || focus.includes('speak')) derivedState = 'speaking'
      else if (intent.includes('generate') || focus.includes('generate') || focus.includes('respond')) derivedState = 'working'
      else if (intent.includes('think') || focus.includes('think')) derivedState = 'thinking'
      else if (intent.includes('plan') || focus.includes('plan')) derivedState = 'thinking'
      else if (intent.includes('search') || focus.includes('search')) derivedState = 'working'
      else if (intent.includes('read') || focus.includes('read')) derivedState = 'working'
      else derivedState = 'idle'
    }

    const stateMap: Record<string, RuntimeState['state']> = {
      'idle': 'Idle',
      'listening': 'Listening',
      'thinking': 'Thinking',
      'working': 'Working',
      'speaking': 'Speaking',
      'sleeping': 'Sleeping',
      'error': 'Error'
    }
    return {
      state: stateMap[derivedState] ?? 'Idle',
      cognitiveLoad: snapshot.system.cognitiveLoad,
      audio: {
        voiceLevel: snapshot.voice.voiceLevel,
        microphoneLevel: snapshot.voice.microphoneLevel
      }
    }
  }

  // --- Delegating diagnostic setters (Milestone 1.0) ---
  setPresenceRuntimeStatus(status: PresenceLifecycle): void {
    this.diagnostics.setPresenceRuntimeStatus(status)
  }

  recordFrameStateReceived(): void {
    this.diagnostics.recordFrameStateReceived()
  }

  recordDroppedFrame(): void {
    this.diagnostics.recordDroppedFrame()
  }

  setGpuContextStatus(status: GpuContextStatus): void {
    this.diagnostics.setGpuContextStatus(status)
  }

  setAnimationRuntimeStatus(status: AnimationRuntimeStatus): void {
    this.diagnostics.setAnimationRuntimeStatus(status)
  }

  setRendererHealth(status: RendererHealthStatus): void {
    this.diagnostics.setRendererHealth(status)
  }

  setGpuFrameTime(ms: number): void {
    this.diagnostics.setGpuFrameTime(ms)
  }

  setCpuFrameTime(ms: number): void {
    this.diagnostics.setCpuFrameTime(ms)
  }

  setFrameBudget(ms: number): void {
    this.diagnostics.setFrameBudget(ms)
  }

  setRefreshRate(hz: number): void {
    this.diagnostics.setRefreshRate(hz)
  }

  setQualityLevel(level: PresenceHealth['qualityLevel']): void {
    this.diagnostics.setQualityLevel(level)
  }

  getFrameStateFrequencyHz(): number {
    return this.diagnostics.getFrameStateFrequencyHz()
  }

  getDroppedFrames(): number {
    return this.diagnostics.getDroppedFrames()
  }

  getGpuContextStatus(): GpuContextStatus {
    return this.diagnostics.getGpuContextStatus()
  }

  getAnimationRuntimeStatus(): AnimationRuntimeStatus {
    return this.diagnostics.getAnimationRuntimeStatus()
  }

  getRendererHealth(): RendererHealthStatus {
    return this.diagnostics.getRendererHealth()
  }

  getGpuFrameTime(): number {
    return this.diagnostics.getGpuFrameTime()
  }

  getCpuFrameTime(): number {
    return this.diagnostics.getCpuFrameTime()
  }

  getFrameBudget(): number {
    return this.diagnostics.getFrameBudget()
  }

  getRefreshRate(): number {
    return this.diagnostics.getRefreshRate()
  }

  getQualityLevel(): PresenceHealth['qualityLevel'] {
    return this.diagnostics.getQualityLevel()
  }

  hasWorkspaceRuntime(): boolean {
    return Boolean(this.workspaceRuntime)
  }

  getWorkspaceState(): ReturnType<IWorkspaceRuntime['getWorkspaceState']> | null {
    return this.workspaceRuntime ? this.workspaceRuntime.getWorkspaceState() : null
  }

  getWorkspaceContext(): ReturnType<IWorkspaceRuntime['getWorkspaceContext']> | null {
    return this.workspaceRuntime ? this.workspaceRuntime.getWorkspaceContext() : null
  }

  getWorkspaceSnapshot(): ReturnType<IWorkspaceRuntime['getWorkspaceSnapshot']> | null {
    return this.workspaceRuntime ? this.workspaceRuntime.getWorkspaceSnapshot() : null
  }
}

// Map an AttentionTarget (cognitive) onto an Executive FocusTarget. The
// executive's focus vocabulary is a superset-ish of attention; 'notification'
// folds into 'world' and 'none' stays 'none'.
function attentionTargetToFocus(target: string): import('../executive/types').FocusTarget {
  switch (target) {
    case 'speaker':
    case 'conversation':
      return 'conversation'
    case 'notification':
    case 'cursor':
    case 'camera':
      return 'world'
    case 'memory':
      return 'memory'
    case 'internal':
      return 'internal'
    case 'none':
    default:
      return 'none'
  }
}

// Map a cognitive ReasoningState onto an Executive ReasoningMode.
function reasoningToMode(reasoning: string): import('../executive/types').ReasoningMode {
  switch (reasoning) {
    case 'perceiving':
      return 'reactive'
    case 'reasoning':
      return 'analytical'
    case 'planning':
      return 'deliberative'
    case 'reflecting':
      return 'reflective'
    case 'deciding':
      return 'deliberative'
    case 'idle':
    default:
      return 'reactive'
  }
}

function mapIntentToSystemState(intent: string): string {
  const lower = intent.toLowerCase()
  if (lower.includes('think') || lower.includes('plan')) return 'Thinking'
  if (lower.includes('speak') || lower.includes('respond') || lower.includes('reply')) return 'Speaking'
  if (lower.includes('work') || lower.includes('execute') || lower.includes('search') || lower.includes('read')) return 'Working'
  if (lower.includes('listen') || lower.includes('hear')) return 'Listening'
  if (lower.includes('error') || lower.includes('fail')) return 'Error'
  if (lower.includes('sleep') || lower.includes('idle')) return 'Sleeping'
  return 'Idle'
}