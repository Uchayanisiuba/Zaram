// frontend/src/components/OrbEngine/OrbEngine.tsx
//
// Renderer-side mount for the Living Orb. It owns the canvas, instantiates
// OrbRenderer, and bridges IPC (FrameState, viewport resize, renderer health).
// No engine code is imported here; the engine is consumed as a data contract
// (FrameState) over IPC.

import { useEffect, useRef } from 'react'
import { OrbRenderer, type FrameState, type RendererHealth } from './OrbRenderer'
import { desktop } from '@/desktop/desktop-bridge'

const IDLE_FRAME: FrameState = {
  visual: { presence: 0.5, energy: 0.4, focus: 0.6, activity: 0.3 },
  audio: { voiceLevel: 0, microphoneLevel: 0 },
  emotion: { calmness: 0.5, confidence: 0.5, curiosity: 0.5, warmth: 0.5, empathy: 0.5, playfulness: 0.5 },
  system: { state: 'Idle', cognitiveLoad: 0.2, visualIdentity: 0.5 },
  metadata: { timestamp: 0, correlationId: 'idle', version: '1.0.0' },
  sequence: 0
}

interface ElectronBridge {
  receive?: (channel: string, cb: (data: unknown) => void) => (() => void) | undefined
  send?: (channel: string, data?: unknown) => void
}

function getElectron(): ElectronBridge | undefined {
  return (window as unknown as { electron?: ElectronBridge }).electron
}

function reportHealth(_bridge: unknown, _health: RendererHealth): void {
  // Renderer health is logged locally; the main process does not currently consume it.
}

export interface OrbEngineProps {
  className?: string
}

export function OrbEngine({ className }: OrbEngineProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const rendererRef = useRef<OrbRenderer | null>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const renderer = new OrbRenderer(canvas, { targetFps: 60, adaptivePerformance: true })
    rendererRef.current = renderer
    renderer.mount()
    renderer.setFrameState(IDLE_FRAME)

    const rect = canvas.getBoundingClientRect()
    const dpr = typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1
    if (rect.width && rect.height) renderer.resize(rect.width, rect.height, dpr)

    let offFrame: (() => void) | undefined
    let offViewport: (() => void) | undefined

    if (desktop.presence.onFrame) {
      offFrame = desktop.presence.onFrame((data) => {
        renderer.setFrameState(data as FrameState)
      })
    }
    if (desktop.presence.onViewport) {
      offViewport = desktop.presence.onViewport((data) => {
        const vp = data as { width: number; height: number; scaleFactor: number }
        if (vp && vp.width && vp.height) {
          renderer.resize(vp.width, vp.height, vp.scaleFactor || 1)
        }
      })
    }

    const resizeObserver = new ResizeObserver(() => {
      const rect = canvas.getBoundingClientRect()
      const dpr = typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1
      if (rect.width && rect.height) renderer.resize(rect.width, rect.height, dpr)
    })
    resizeObserver.observe(canvas)

    const onVisibility = (): void => {
      if (document.hidden) {
        renderer.setThrottled(true)
        renderer.suspend()
      } else {
        renderer.setThrottled(false)
        renderer.resume()
      }
    }
    document.addEventListener('visibilitychange', onVisibility)

    const healthTimer = window.setInterval(() => {
      reportHealth(null, renderer.getHealth())
    }, 1000)

    return () => {
      offFrame?.()
      offViewport?.()
      resizeObserver.disconnect()
      document.removeEventListener('visibilitychange', onVisibility)
      window.clearInterval(healthTimer)
      renderer.dispose()
      rendererRef.current = null
    }
  }, [])

  return <canvas ref={canvasRef} className={className} />
}

export default OrbEngine
