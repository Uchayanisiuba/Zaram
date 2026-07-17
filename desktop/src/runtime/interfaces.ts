import {
  AnimationRuntimeStatus,
  ConnectionState,
  EmbodimentStatus,
  EmbodimentType,
  FrameState,
  GpuContextStatus,
  PresenceHealth,
  PresenceLifecycle,
  RendererHealthStatus,
  ExpressiveParams
} from './types'
import type { RuntimeSnapshot } from './sources/types'
import type { RuntimeState } from '@zaram/engine'

export interface IEmbodiment {
  initialize(): Promise<void>
  start(): Promise<void>
  pause(): Promise<void>
  resume(): Promise<void>
  shutdown(): Promise<void>
  setFrameState(frameState: FrameState): void
  getStatus(): EmbodimentStatus
}

export interface IExpressiveParamsSource {
  getExpressiveParams(): ExpressiveParams
  subscribe(listener: (params: ExpressiveParams) => void): () => void
}

export interface IRenderTransport {
  sendFrameState(frameState: FrameState): void
  isReady(): boolean
  onReady(listener: () => void): void
}

export interface IEngineAdapter {
  initialize(visualIdentity: number): void
  update(dt: number, runtimeState: RuntimeState): FrameState
}

export interface IPresenceRuntime {
  initialize(): Promise<void>
  start(): Promise<void>
  pause(): Promise<void>
  resume(): Promise<void>
  shutdown(): Promise<void>
  setEmbodiment(embodiment: IEmbodiment): void
  consumeFrameState(frameState: FrameState): void
  getStatus(): EmbodimentStatus
  getHealth(): PresenceHealth
}

export interface IPresenceDiagnostics {
  getHealth(): PresenceHealth
  getEmbodimentType(): EmbodimentType
  getFrameRate(): number
  getAnimationConnection(): ConnectionState
  setPresenceRuntimeStatus(status: PresenceLifecycle): void
  recordFrameStateReceived(): void
  recordDroppedFrame(): void
  setGpuContextStatus(status: GpuContextStatus): void
  setAnimationRuntimeStatus(status: AnimationRuntimeStatus): void
  setRendererHealth(status: RendererHealthStatus): void
  getFrameStateFrequencyHz(): number
  getDroppedFrames(): number
  getGpuContextStatus(): GpuContextStatus
  getAnimationRuntimeStatus(): AnimationRuntimeStatus
  getRendererHealth(): RendererHealthStatus
  setGpuFrameTime(ms: number): void
  setCpuFrameTime(ms: number): void
  setFrameBudget(ms: number): void
  setRefreshRate(hz: number): void
  setQualityLevel(level: PresenceHealth['qualityLevel']): void
  getGpuFrameTime(): number
  getCpuFrameTime(): number
  getFrameBudget(): number
  getRefreshRate(): number
  getQualityLevel(): PresenceHealth['qualityLevel']
}

export interface IZaramKernel {
  boot(): Promise<void>
  dispose(): Promise<void>
  getPresenceRuntime(): IPresenceRuntime
  getDiagnostics(): IPresenceDiagnostics
}