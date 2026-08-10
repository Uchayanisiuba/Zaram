// frontend/src/components/OrbEngine/OrbEngine.tsx
//
// Renderer-side mount for the Living Orb. It owns the canvas, instantiates
// OrbRenderer, and bridges IPC (FrameState, viewport resize, renderer health).
// No engine code is imported here; the engine is consumed as a data contract
// (FrameState) over IPC.

import { useEffect, useRef } from 'react'
import { OrbRenderer } from './OrbRenderer'
import { FrameState, IDLE_FRAME } from '../../core/frame/types'
import { desktop } from '../../desktop/desktop-bridge'

export interface OrbEngineProps {
  className?: string
  frameState?: FrameState
}

export function OrbEngine({ className, frameState }: OrbEngineProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const rendererRef = useRef<OrbRenderer | null>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const renderer = new OrbRenderer(canvas, { targetFps: 60, adaptivePerformance: true })
    rendererRef.current = renderer
    renderer.mount()
    renderer.setFrameState(frameState ?? IDLE_FRAME)

    const rect = canvas.getBoundingClientRect()
    const dpr = typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1
    if (rect.width && rect.height) renderer.resize(rect.width, rect.height, dpr)

    let offFrame: (() => void) | undefined
    let offViewport: (() => void) | undefined

    // Receive FrameState from PresenceRuntime (pushed at animation frequency)
    // Only subscribe to IPC if no frameState prop is provided (embedded usage)
    if (!frameState && desktop.presence.onFrame) {
      offFrame = desktop.presence.onFrame((data) => {
        const ipcFrameState = data as FrameState
        renderer.setFrameState(ipcFrameState)
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

    return () => {
      offFrame?.()
      offViewport?.()
      resizeObserver.disconnect()
      document.removeEventListener('visibilitychange', onVisibility)
      renderer.dispose()
      rendererRef.current = null
    }
  }, [frameState])

  // Update frameState when prop changes (for embedded usage)
  useEffect(() => {
    if (frameState && rendererRef.current) {
      rendererRef.current.setFrameState(frameState)
    }
  }, [frameState])

  return <canvas ref={canvasRef} className={className} />
}

export default OrbEngine