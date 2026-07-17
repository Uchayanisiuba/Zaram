import {
  AnimationRuntimeStatus,
  ConnectionState,
  EmbodimentType,
  GpuContextStatus,
  PresenceHealth,
  PresenceLifecycle,
  RendererHealthStatus,
  RuntimeHealth
} from '../types'
import { IPresenceDiagnostics } from '../interfaces'

const FPS_SAMPLE_WINDOW_MS = 1000
const MAX_TIMESTAMP_SAMPLES = 120
const MAX_FREQUENCY_SAMPLES = 120

export class PresenceDiagnostics implements IPresenceDiagnostics {
  private readonly timestamps: number[] = []
  private readonly frequencySamples: number[] = []
  private frameCount = 0
  private lastFrameAt: number | null = null
  private startedAt = 0
  private animationConnection: ConnectionState = 'disconnected'
  private currentEmbodiment: EmbodimentType = 'none'
  private embodimentHealthy = false
  private lastMessage?: string

  // --- Extended diagnostics (Milestone 1.0) ---
  private presenceStatus: PresenceLifecycle = 'uninitialized'
  private droppedFrames = 0
  private gpuContext: GpuContextStatus = 'unknown'
  private animationRuntime: AnimationRuntimeStatus = 'stopped'
  private rendererHealth: RendererHealthStatus = 'unknown'

  // --- Performance metrics (Milestone 1.2) ---
  private gpuFrameTimeMs = 0
  private cpuFrameTimeMs = 0
  private frameBudgetMs = 1000 / 60
  private refreshRateHz = 60
  private qualityLevel: PresenceHealth['qualityLevel'] = 'adaptive'

  begin(startedAt: number = Date.now()): void {
    this.startedAt = startedAt
  }

  recordFrame(): void {
    const now = Date.now()
    this.frameCount += 1
    this.lastFrameAt = now
    this.timestamps.push(now)
    if (this.timestamps.length > MAX_TIMESTAMP_SAMPLES) {
      this.timestamps.shift()
    }
  }

  recordFrameStateReceived(): void {
    const now = Date.now()
    this.frequencySamples.push(now)
    if (this.frequencySamples.length > MAX_FREQUENCY_SAMPLES) {
      this.frequencySamples.shift()
    }
  }

  recordDroppedFrame(): void {
    this.droppedFrames += 1
  }

  resetFrames(): void {
    this.timestamps.length = 0
    this.frameCount = 0
    this.lastFrameAt = null
  }

  setAnimationConnection(state: ConnectionState): void {
    this.animationConnection = state
  }

  setEmbodiment(type: EmbodimentType, healthy: boolean): void {
    this.currentEmbodiment = type
    this.embodimentHealthy = healthy
  }

  setMessage(message: string | undefined): void {
    this.lastMessage = message
  }

  setPresenceRuntimeStatus(status: PresenceLifecycle): void {
    this.presenceStatus = status
  }

  setGpuContextStatus(status: GpuContextStatus): void {
    this.gpuContext = status
  }

  setAnimationRuntimeStatus(status: AnimationRuntimeStatus): void {
    this.animationRuntime = status
  }

  setRendererHealth(status: RendererHealthStatus): void {
    this.rendererHealth = status
  }

  setGpuFrameTime(ms: number): void {
    this.gpuFrameTimeMs = ms
  }

  setCpuFrameTime(ms: number): void {
    this.cpuFrameTimeMs = ms
  }

  setFrameBudget(ms: number): void {
    this.frameBudgetMs = ms
  }

  setRefreshRate(hz: number): void {
    this.refreshRateHz = hz
  }

  setQualityLevel(level: PresenceHealth['qualityLevel']): void {
    this.qualityLevel = level
  }

  getFrameRate(): number {
    if (this.timestamps.length < 2) {
      return this.timestamps.length === 1 ? 1 : 0
    }
    const oldest = this.timestamps[0]
    const newest = this.timestamps[this.timestamps.length - 1]
    const span = newest - oldest
    if (span <= 0) return 0
    return Math.round((this.timestamps.length / span) * FPS_SAMPLE_WINDOW_MS * 10) / 10
  }

  getFrameStateFrequencyHz(): number {
    if (this.frequencySamples.length < 2) {
      return this.frequencySamples.length === 1 ? 1 : 0
    }
    const oldest = this.frequencySamples[0]
    const newest = this.frequencySamples[this.frequencySamples.length - 1]
    const span = newest - oldest
    if (span <= 0) return 0
    return Math.round((this.frequencySamples.length / span) * FPS_SAMPLE_WINDOW_MS * 10) / 10
  }

  getDroppedFrames(): number {
    return this.droppedFrames
  }

  getGpuContextStatus(): GpuContextStatus {
    return this.gpuContext
  }

  getAnimationRuntimeStatus(): AnimationRuntimeStatus {
    return this.animationRuntime
  }

  getRendererHealth(): RendererHealthStatus {
    return this.rendererHealth
  }

  getGpuFrameTime(): number {
    return this.gpuFrameTimeMs
  }

  getCpuFrameTime(): number {
    return this.cpuFrameTimeMs
  }

  getFrameBudget(): number {
    return this.frameBudgetMs
  }

  getRefreshRate(): number {
    return this.refreshRateHz
  }

  getQualityLevel(): PresenceHealth['qualityLevel'] {
    return this.qualityLevel
  }

  getEmbodimentType(): EmbodimentType {
    return this.currentEmbodiment
  }

  getAnimationConnection(): ConnectionState {
    return this.animationConnection
  }

  getHealth(): PresenceHealth {
    const status = this.computeStatus()
    return {
      status,
      currentEmbodiment: this.currentEmbodiment,
      embodimentHealthy: this.embodimentHealthy,
      frameRateHz: this.getFrameRate(),
      animationConnection: this.animationConnection,
      uptimeMs: this.startedAt ? Date.now() - this.startedAt : 0,
      lastFrameAt: this.lastFrameAt,
      message: this.lastMessage,
      presenceRuntimeStatus: this.presenceStatus,
      frameStateFrequencyHz: this.getFrameStateFrequencyHz(),
      droppedFrames: this.droppedFrames,
      gpuContextStatus: this.gpuContext,
      animationRuntimeStatus: this.animationRuntime,
      rendererHealth: this.rendererHealth,
      gpuFrameTimeMs: this.gpuFrameTimeMs,
      cpuFrameTimeMs: this.cpuFrameTimeMs,
      frameBudgetMs: this.frameBudgetMs,
      refreshRateHz: this.refreshRateHz,
      qualityLevel: this.qualityLevel
    }
  }

  private computeStatus(): RuntimeHealth {
    if (this.currentEmbodiment === 'none') return 'degraded'
    if (!this.embodimentHealthy) return 'unhealthy'
    if (this.gpuContext === 'lost') return 'unhealthy'
    if (this.rendererHealth === 'unhealthy') return 'unhealthy'
    if (this.animationConnection === 'disconnected') return 'degraded'
    if (this.animationConnection === 'reconnecting') return 'degraded'
    if (this.rendererHealth === 'degraded') return 'degraded'
    return 'healthy'
  }
}
