import type { FrameState as EngineFrameState } from '@zaram/engine'

declare module '@zaram/engine' {
  interface FrameState {
    sequence: number
  }
}

export type FrameState = EngineFrameState

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