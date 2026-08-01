import type { FrameState as EngineFrameState } from '@zaram/engine'

declare module '@zaram/engine' {
  interface FrameState {
    sequence: number
  }
}

export type FrameState = EngineFrameState

export type PresenceState =
  | 'Idle'
  | 'Listening'
  | 'Thinking'
  | 'SearchingMemory'
  | 'SearchingWeb'
  | 'Planning'
  | 'Speaking'
  | 'Learning'
  | 'Error'
  | 'Success'

export type ConversationPhase =
  | 'idle'
  | 'listening'
  | 'thinking'
  | 'working'
  | 'speaking'
  | 'sleeping'
  | 'error'

export type EmbodimentType =
  | 'none'
  | 'living-orb'
  | 'metahuman'
  | 'unreal-character'
  | 'xr-avatar'

export type EmbodimentState =
  | 'uninitialized'
  | 'initializing'
  | 'ready'
  | 'running'
  | 'paused'
  | 'error'
  | 'shutdown'

export interface EmbodimentStatus {
  type: EmbodimentType
  state: EmbodimentState
  healthy: boolean
  lastUpdated: number
  message?: string
  error?: string
}

export type ConnectionState = 'connected' | 'disconnected' | 'reconnecting'

export type PresenceLifecycle =
  | 'uninitialized'
  | 'initializing'
  | 'running'
  | 'paused'
  | 'shutdown'
  | 'error'

export type GpuContextStatus = 'unknown' | 'ok' | 'lost' | 'recovering'

export type AnimationRuntimeStatus = 'stopped' | 'running' | 'paused'

export type RendererHealthStatus = 'unknown' | 'healthy' | 'degraded' | 'unhealthy'

export type RuntimeHealth = 'healthy' | 'degraded' | 'unhealthy'

export interface PresenceHealth {
  status: RuntimeHealth
  currentEmbodiment: EmbodimentType
  embodimentHealthy: boolean
  frameRateHz: number
  animationConnection: ConnectionState
  uptimeMs: number
  lastFrameAt: number | null
  message?: string
  presenceRuntimeStatus: PresenceLifecycle
  frameStateFrequencyHz: number
  droppedFrames: number
  gpuContextStatus: GpuContextStatus
  animationRuntimeStatus: AnimationRuntimeStatus
  rendererHealth: RendererHealthStatus
  gpuFrameTimeMs: number
  cpuFrameTimeMs: number
  frameBudgetMs: number
  refreshRateHz: number
  qualityLevel: 'low' | 'medium' | 'high' | 'adaptive'
}

export interface ExpressiveParams {
  presence: number
  energy: number
  focus: number
  emotion: string
  voiceLevel: number
  processingLoad: number
}

export const DEFAULT_EXPRESSIVE_PARAMS: ExpressiveParams = {
  presence: 0.5,
  energy: 0.4,
  focus: 0.6,
  emotion: 'neutral',
  voiceLevel: 0,
  processingLoad: 0.2
}

export function clampUnit(value: number): number {
  if (Number.isNaN(value)) return 0
  return Math.min(1, Math.max(0, value))
}

// ============================================================================
// Event Bus Types
// ============================================================================

export type ZaramEventType =
  // Executive events (source of truth)
  | 'executive:intent_changed'
  | 'executive:state_changed'
  | 'executive:focus_changed'
  | 'executive:priority_changed'
  | 'executive:goal_changed'
  | 'executive:interrupt_raised'
  | 'executive:plan_created'
  | 'executive:plan_step_started'
  | 'executive:plan_step_completed'
  | 'executive:plan_step_failed'
  | 'executive:speak'
  | 'executive:pause_speech'
  | 'executive:stop_speech'
  // Conversation events
  | 'conversation:phase_changed'
  | 'conversation:sentence_ready'
  | 'conversation:token_streaming'
  | 'conversation:response_complete'
  | 'conversation:user_input'
  // Speech/Voice events
  | 'speech:synthesis_started'
  | 'speech:chunk_generated'
  | 'speech:synthesis_complete'
  | 'speech:synthesis_failed'
  | 'voice:level'
  | 'voice:started'
  | 'voice:chunk'
  | 'voice:paused'
  | 'voice:finished'
  | 'voice:failed'
  // Presence events
  | 'presence:state_changed'
  | 'presence:audio_level'
  | 'presence:voice_chunk'
  | 'presence:theme_changed'
  // Knowledge Universe events
  | 'knowledge:search_started'
  | 'knowledge:search_complete'
  | 'knowledge:memory_recalled'
  // Reasoning events
  | 'reasoning:started'
  | 'reasoning:finished'
  // Orb/Visualization events
  | 'orb:animation_triggered'
  | 'orb:visual_state_changed'
  // Theme/UI events
  | 'theme:colors_changed'
  | 'theme:transition_complete'
  // System events
  | 'system:startup'
  | 'system:shutdown'
  | 'system:error'

export interface ZaramEvent {
  event_id: string
  timestamp: number
  source_runtime: string
  event_type: ZaramEventType
  version: number
  priority: 'critical' | 'high' | 'normal' | 'background'
  data: Record<string, unknown>
  correlation_id: string
}

// Event data payloads (for type safety)
export interface ExecutiveIntentChangedData {
  decision: string
  confidence: number
  reasoning: string
  previous_decision?: string
}

export interface ExecutiveStateChangedData {
  focus: string
  focus_strength: number
  priority: string
  urgency: number
  goal_active: boolean
  conversation_phase: string
}

export interface ConversationPhaseChangedData {
  phase: string
  activity: number
  previous_phase?: string
}

export interface PresenceStateChangedData {
  state: PresenceState
  previous_state?: PresenceState
  source: 'executive' | 'conversation' | 'voice' | 'speech'
}

export interface SpeechSynthesisData {
  text: string
  voice: string
  audio_id: string
  sequence: number
  final: boolean
}

export interface ExecutiveSpeakData {
  text: string
  persona?: string
  voice?: string
  audio_id?: string
}

export interface VoiceStartedData {
  audioId: string
  text: string
  persona: string
  voice: string
  sequence: number
}

export interface VoiceFinishedData {
  audioId: string
  text: string
  durationMs: number
}

export interface VoiceFailedData {
  audioId: string | null
  error: string
}

export interface ReasoningStartedData {
  task: string
  phase: string
}

export interface ReasoningFinishedData {
  task: string
  result?: string
}

export interface KnowledgeSearchData {
  query: string
  results_count: number
  sources: string[]
}

// Presence event types (derived from ZaramEventType — single source of truth)
export type PresenceEventType = Extract<ZaramEventType, `presence:${string}`>

export interface PresenceEvent {
  type: PresenceEventType
  timestamp: number
  payload: {
    state?: PresenceState
    previousState?: PresenceState
    audioLevel?: number
    audioId?: string
    sequence?: number
    rmsLevel?: number
    theme?: string
  }
}