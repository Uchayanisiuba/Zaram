// frontend/src/components/OrbEngine/OrbRenderer.ts
//
// Canvas-based renderer for the Living Orb. It consumes the frozen FrameState
// produced by the engine and renders the orb with no additional runtime
// calculations. All visual state is driven by FrameState fields.

export interface OrbRendererOptions {
  targetFps?: number
  adaptivePerformance?: boolean
}

export interface FrameState {
  visual: {
    presence: number
    energy: number
    focus: number
    activity: number
  }
  audio: {
    voiceLevel: number
    microphoneLevel: number
  }
  emotion: {
    calmness: number
    confidence: number
    curiosity: number
    warmth: number
    empathy: number
    playfulness: number
  }
  system: {
    state: 'Idle' | 'Listening' | 'Thinking' | 'Speaking' | 'Working' | 'Sleeping' | 'Error' | 'SearchingInternet'
    cognitiveLoad: number
    visualIdentity: number
  }
  metadata: {
    timestamp: number
    correlationId: string
    version: string
  }
  sequence: number
}

export interface RendererHealth {
  status: 'healthy' | 'degraded' | 'unhealthy'
  gpuContextStatus: 'unknown' | 'ok' | 'lost' | 'recovering'
  fps: number
  droppedFrames: number
  gpuFrameTimeMs: number
}

const STATE_HUE: Record<string, number> = {
  Idle: 220,
  Listening: 180,
  Thinking: 260,
  Speaking: 150,
  Working: 30,
  Sleeping: 240,
  Error: 0,
  Planning: 270,
  Searching: 190,
  SearchingInternet: 190,
  Executing: 35,
}

const STATE_ENERGY: Record<string, number> = {
  Idle: 0.3,
  Listening: 0.5,
  Thinking: 0.6,
  Speaking: 0.8,
  Working: 0.9,
  Sleeping: 0.1,
  Error: 0.95,
  Planning: 0.7,
  Searching: 0.65,
  SearchingInternet: 0.7,
  Executing: 0.85,
}

const STATE_FOCUS: Record<string, number> = {
  Idle: 0.3,
  Listening: 0.8,
  Thinking: 0.9,
  Speaking: 0.6,
  Working: 0.95,
  Sleeping: 0.1,
  Error: 0.3,
  Planning: 0.85,
  Searching: 0.75,
  SearchingInternet: 0.8,
  Executing: 0.9,
}

const STATE_ACTIVITY: Record<string, number> = {
  Idle: 0.2,
  Listening: 0.3,
  Thinking: 0.4,
  Speaking: 0.7,
  Working: 0.9,
  Sleeping: 0.05,
  Error: 0.9,
  Planning: 0.5,
  Searching: 0.6,
  SearchingInternet: 0.75,
  Executing: 0.85,
}

export class OrbRenderer {
  private readonly canvas: HTMLCanvasElement
  private readonly ctx: CanvasRenderingContext2D
  private readonly targetFps: number
  private readonly adaptivePerformance: boolean
  private frameState: FrameState | null = null
  private running = false
  private throttled = false
  private disposed = false
  private animationFrameId: number | null = null
  private lastFrameTime = 0
  private frameCount = 0
  private fpsUpdateTime = 0
  private currentFps = 0
  private droppedFrames = 0
  private width = 0
  private height = 0
  private dpr = 1
  private rendererHealthy = true
  private gpuContextStatus: RendererHealth['gpuContextStatus'] = 'unknown'
  private gpuFrameTimeMs = 0
  private onHealthChange?: (health: RendererHealth) => void

  constructor(canvas: HTMLCanvasElement, options: OrbRendererOptions = {}) {
    this.canvas = canvas
    this.targetFps = options.targetFps ?? 60
    this.adaptivePerformance = options.adaptivePerformance ?? true
    const ctx = canvas.getContext('2d')
    if (!ctx) {
      throw new Error('Failed to get 2D canvas context')
    }
    this.ctx = ctx
  }

  mount(): void {
    if (this.running) return
    this.running = true
    this.disposed = false
    this.lastFrameTime = performance.now()
    this.fpsUpdateTime = this.lastFrameTime
    this.tick()
  }

  resize(width: number, height: number, scaleFactor: number = 1): void {
    this.width = width
    this.height = height
    this.dpr = scaleFactor
    this.canvas.width = width * scaleFactor
    this.canvas.height = height * scaleFactor
    this.canvas.style.width = `${width}px`
    this.canvas.style.height = `${height}px`
    this.ctx.setTransform(scaleFactor, 0, 0, scaleFactor, 0, 0)
  }

  setFrameState(frameState: FrameState): void {
    this.frameState = frameState
  }

  setThrottled(throttled: boolean): void {
    this.throttled = throttled
  }

  suspend(): void {
    this.running = false
    if (this.animationFrameId !== null) {
      cancelAnimationFrame(this.animationFrameId)
      this.animationFrameId = null
    }
  }

  resume(): void {
    if (this.running) return
    this.running = true
    this.lastFrameTime = performance.now()
    this.tick()
  }

  dispose(): void {
    this.disposed = true
    this.running = false
    this.frameState = null
    if (this.animationFrameId !== null) {
      cancelAnimationFrame(this.animationFrameId)
      this.animationFrameId = null
    }
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height)
  }

  onHealth(callback: (health: RendererHealth) => void): void {
    this.onHealthChange = callback
  }

  getHealth(): RendererHealth {
    return {
      status: this.rendererHealthy ? 'healthy' : 'unhealthy',
      gpuContextStatus: this.gpuContextStatus,
      fps: this.currentFps,
      droppedFrames: this.droppedFrames,
      gpuFrameTimeMs: this.gpuFrameTimeMs
    }
  }

  private tick = (): void => {
    if (!this.running || this.disposed) return

    const now = performance.now()
    const frameInterval = 1000 / this.targetFps

    if (now - this.lastFrameTime >= frameInterval) {
      this.lastFrameTime = now
      this.render()
      this.frameCount += 1

      if (now - this.fpsUpdateTime >= 1000) {
        this.currentFps = Math.round((this.frameCount * 1000) / (now - this.fpsUpdateTime))
        this.frameCount = 0
        this.fpsUpdateTime = now
        this.onHealthChange?.(this.getHealth())
      }
    }

    this.animationFrameId = requestAnimationFrame(this.tick)
  }

  private render(): void {
    const state = this.frameState
    const w = this.width || this.canvas.clientWidth || 360
    const h = this.height || this.canvas.clientHeight || 360

    const frameStart = performance.now()
    this.ctx.clearRect(0, 0, w, h)

    if (!state) {
      this.drawIdleOrb(w, h)
    } else {
      const { visual, emotion, system } = state
      const baseHue = STATE_HUE[system.state] ?? 220
      const hueShift = (emotion.curiosity - 0.5) * 60 + (emotion.warmth - 0.5) * 30
      const hue = (baseHue + hueShift + 360) % 360

      const defaultEnergy = STATE_ENERGY[system.state] ?? 0.3
      const defaultFocus = STATE_FOCUS[system.state] ?? 0.3
      const defaultActivity = STATE_ACTIVITY[system.state] ?? 0.2

      const presence = visual.presence
      const energy = visual.energy || defaultEnergy
      const focus = visual.focus || defaultFocus
      const activity = visual.activity || defaultActivity
      const voiceLevel = state.audio.voiceLevel
      const cognitiveLoad = system.cognitiveLoad

      const baseRadius = Math.min(w, h) * 0.18
      const radius = baseRadius * (0.85 + presence * 0.3)
      const cx = w / 2
      const cy = h / 2

      const saturation = 60 + energy * 30
      const lightness = 45 + focus * 15

      const glowScale = system.state === 'Error' ? 3.5 : system.state === 'Speaking' ? 3.0 : 2.5
      const glowAlpha = system.state === 'Error' ? 0.25 : 0.15 + energy * 0.15 + voiceLevel * 0.1

      this.drawGlow(cx, cy, radius, hue, saturation, lightness, energy, voiceLevel, glowScale, glowAlpha)
      this.drawOrb(cx, cy, radius, hue, saturation, lightness, activity, cognitiveLoad, system.state)
      this.drawInnerCore(cx, cy, radius, hue, lightness, presence, system.state)
    }

    const frameEnd = performance.now()
    this.gpuContextStatus = 'ok'
    this.rendererHealthy = true
    this.gpuFrameTimeMs = frameEnd - frameStart
  }

  private drawIdleOrb(w: number, h: number): void {
    const cx = w / 2
    const cy = h / 2
    const radius = Math.min(w, h) * 0.18
    this.drawGlow(cx, cy, radius, 220, 70, 50, 0.3, 0, 2.5, 0.12)
    this.drawOrb(cx, cy, radius, 220, 70, 50, 0.2, 0.2, 'Idle')
    this.drawInnerCore(cx, cy, radius, 220, 50, 0.5, 'Idle')
  }

  private drawGlow(
    cx: number,
    cy: number,
    radius: number,
    hue: number,
    saturation: number,
    lightness: number,
    energy: number,
    voiceLevel: number,
    scale: number = 2.5,
    alpha: number = 0.15
  ): void {
    const glowRadius = radius * (scale + energy * 1.5 + voiceLevel * 0.8)
    const gradient = this.ctx.createRadialGradient(cx, cy, radius * 0.5, cx, cy, glowRadius)
    gradient.addColorStop(0, `hsla(${hue}, ${saturation}%, ${lightness}%, ${alpha})`)
    gradient.addColorStop(1, `hsla(${hue}, ${saturation}%, ${lightness}%, 0)`)
    this.ctx.fillStyle = gradient
    this.ctx.beginPath()
    this.ctx.arc(cx, cy, glowRadius, 0, Math.PI * 2)
    this.ctx.fill()
  }

  private drawOrb(
    cx: number,
    cy: number,
    radius: number,
    hue: number,
    saturation: number,
    lightness: number,
    activity: number,
    cognitiveLoad: number,
    state: string
  ): void {
    const gradient = this.ctx.createRadialGradient(cx, cy - radius * 0.3, radius * 0.1, cx, cy, radius)
    gradient.addColorStop(0, `hsla(${hue}, ${saturation}%, ${Math.min(lightness + 20, 90)}%, 0.95)`)
    gradient.addColorStop(0.7, `hsla(${hue}, ${saturation}%, ${lightness}%, 0.85)`)
    gradient.addColorStop(1, `hsla(${hue}, ${saturation - 10}%, ${lightness - 10}%, 0.6)`)

    this.ctx.fillStyle = gradient
    this.ctx.beginPath()
    this.ctx.arc(cx, cy, radius * (1 + cognitiveLoad * 0.05), 0, Math.PI * 2)
    this.ctx.fill()

    const ringCount = state === 'Error' ? 4 : state === 'Speaking' || state === 'Executing' ? 3 : 2
    for (let i = 0; i < ringCount; i++) {
      const ringRadius = radius * (1.3 + i * 0.4 + activity * 0.2)
      const alpha = 0.1 + activity * 0.15
      this.ctx.strokeStyle = `hsla(${hue}, ${saturation}%, ${lightness}%, ${alpha})`
      this.ctx.lineWidth = state === 'Error' ? 1.5 : 1
      this.ctx.beginPath()
      this.ctx.arc(cx, cy, ringRadius, 0, Math.PI * 2)
      this.ctx.stroke()
    }
  }

  private drawInnerCore(
    cx: number,
    cy: number,
    radius: number,
    hue: number,
    lightness: number,
    presence: number,
    state: string
  ): void {
    const coreRadius = radius * (state === 'Error' ? 0.45 : 0.35)
    const gradient = this.ctx.createRadialGradient(cx, cy, 0, cx, cy, coreRadius)
    const coreAlpha = state === 'Error' ? 0.8 : 0.6 + presence * 0.3
    gradient.addColorStop(0, `hsla(${hue}, 20%, 95%, ${coreAlpha})`)
    gradient.addColorStop(1, `hsla(${hue}, 30%, 80%, 0)`)
    this.ctx.fillStyle = gradient
    this.ctx.beginPath()
    this.ctx.arc(cx, cy, coreRadius, 0, Math.PI * 2)
    this.ctx.fill()
  }
}
