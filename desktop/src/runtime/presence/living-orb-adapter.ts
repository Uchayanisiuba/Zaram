import { EmbodimentStatus, FrameState } from '../types'
import { IEmbodiment, IRenderTransport } from '../interfaces'

export class LivingOrbAdapter implements IEmbodiment {
  // The LivingOrbAdapter is the ONLY integration point between the OS runtime
  // and the Living Orb Engine. It never imports or references renderer code; it
  // only pushes the frozen FrameState to the render transport (which delivers
  // it to the engine mounted in the renderer) and reflects renderer health that
  // is reported back across the boundary.
  private readonly transport: IRenderTransport
  private status: EmbodimentStatus
  private lastFrame: FrameState | null = null
  private rendererHealthy = true
  private rendererMessage?: string

  constructor(transport: IRenderTransport) {
    this.transport = transport
    this.status = {
      type: 'living-orb',
      state: 'uninitialized',
      healthy: false,
      lastUpdated: Date.now()
    }
  }

  // Called by the host when the renderer reports engine lifecycle/health.
  // Keeps the adapter as the single convergence point for embodiment state.
  applyRendererHealth(healthy: boolean, message?: string): void {
    this.rendererHealthy = healthy
    this.rendererMessage = message
    if (this.status.state !== 'shutdown' && this.status.state !== 'uninitialized') {
      this.updateStatus(this.status.state, message)
    }
  }

  setTransport(transport: IRenderTransport): void {
    ;(this as unknown as { transport: IRenderTransport }).transport = transport
  }

  async initialize(): Promise<void> {
    this.updateStatus('initializing')
    await this.waitForTransport()
    this.updateStatus('ready')
  }

  async start(): Promise<void> {
    this.updateStatus('running')
  }

  async pause(): Promise<void> {
    this.updateStatus('paused')
  }

  async resume(): Promise<void> {
    this.updateStatus('running')
  }

  async shutdown(): Promise<void> {
    this.updateStatus('shutdown')
    this.lastFrame = null
  }

  setFrameState(frameState: FrameState): void {
    if (this.status.state === 'shutdown') return
    this.lastFrame = frameState
    this.transport.sendFrameState(frameState)
  }

  getStatus(): EmbodimentStatus {
    return { ...this.status }
  }

  getLastFrame(): FrameState | null {
    return this.lastFrame
  }

  private waitForTransport(): Promise<void> {
    if (this.transport.isReady()) return Promise.resolve()
    return new Promise<void>((resolve) => {
      this.transport.onReady(() => resolve())
    })
  }

  private updateStatus(state: EmbodimentStatus['state'], message?: string): void {
    const effectiveMessage = message ?? this.rendererMessage
    this.status = {
      type: 'living-orb',
      state,
      healthy:
        state !== 'error' &&
        state !== 'shutdown' &&
        this.rendererHealthy,
      lastUpdated: Date.now(),
      message: effectiveMessage
    }
  }
}
