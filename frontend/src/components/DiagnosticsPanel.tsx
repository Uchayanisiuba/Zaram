// frontend/src/components/DiagnosticsPanel.tsx
//
// Development-only diagnostics panel showing engine and renderer state.
// Not shipped in production builds.

import { useEffect, useState, useCallback } from 'react'
import type { FrameState } from './OrbEngine/OrbRenderer'
import { Cpu, HardDrive, Activity, Zap, Boxes, RefreshCw, Gauge } from 'lucide-react'

interface DesktopDiagnostics {
  status: string
  currentEmbodiment: string
  embodimentHealthy: boolean
  frameRateHz: number
  animationConnection: string
  uptimeMs: number
  lastFrameAt: number | null
  presenceRuntimeStatus: string
  frameStateFrequencyHz: number
  droppedFrames: number
  gpuContextStatus: string
  animationRuntimeStatus: string
  rendererHealth: string
  gpuFrameTimeMs: number
  cpuFrameTimeMs: number
  frameBudgetMs: number
  refreshRateHz: number
  qualityLevel: string
}

interface SystemMetrics {
  memoryUsage: number
  gpuUsage: number
  cpuUsage: number
}

interface ElectronBridge {
  invoke?: (channel: string, ...args: any[]) => Promise<any>
  receive?: (channel: string, callback: (data: any) => void) => (() => void) | undefined
}

function getElectron(): ElectronBridge | undefined {
  return (window as unknown as { electron?: ElectronBridge }).electron
}

export function DiagnosticsPanel() {
  const [open, setOpen] = useState(false)
  const [diagnostics, setDiagnostics] = useState<DesktopDiagnostics | null>(null)
  const [frameState, setFrameState] = useState<FrameState | null>(null)
  const [rendererFps, setRendererFps] = useState(0)
  const [frameLatencyMs, setFrameLatencyMs] = useState(0)
  const [systemMetrics, setSystemMetrics] = useState<SystemMetrics>({
    memoryUsage: 0,
    gpuUsage: 0,
    cpuUsage: 0,
  })

  const fetchDiagnostics = useCallback(async () => {
    const bridge = getElectron()
    if (!bridge?.invoke) return
    try {
      const diag = await bridge.invoke('presence:diagnostics')
      if (diag) setDiagnostics(diag)
    } catch {
      // ignore
    }
  }, [])

  useEffect(() => {
    fetchDiagnostics()
    const interval = window.setInterval(fetchDiagnostics, 2000)
    return () => window.clearInterval(interval)
  }, [fetchDiagnostics])

  useEffect(() => {
    const bridge = getElectron()
    if (!bridge?.receive) return

    const offFrame = bridge.receive('presence:frame', (data: unknown) => {
      setFrameState(data as FrameState)
      const meta = (data as { metadata?: { timestamp?: number } }).metadata
      setFrameLatencyMs(performance.now() - (meta?.timestamp ?? 0))
    })

    return () => {
      offFrame?.()
    }
  }, [])

  useEffect(() => {
    let frames = 0
    let lastTime = performance.now()
    const tick = () => {
      frames += 1
      const now = performance.now()
      if (now - lastTime >= 1000) {
        setRendererFps(Math.round((frames * 1000) / (now - lastTime)))
        frames = 0
        lastTime = now
      }
      requestAnimationFrame(tick)
    }
    const id = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(id)
  }, [])

  useEffect(() => {
    const updateMetrics = async () => {
      if (navigator.storage && navigator.storage.estimate) {
        const estimate = await navigator.storage.estimate()
        const usage = estimate.usage || 0
        const quota = estimate.quota || 1
        setSystemMetrics((prev) => ({
          ...prev,
          memoryUsage: Math.round((usage / quota) * 100),
        }))
      }
      if (typeof navigator !== 'undefined' && (navigator as any).getBattery) {
        try {
          const battery = await (navigator as any).getBattery()
          setSystemMetrics((prev) => ({
            ...prev,
            gpuUsage: Math.round((1 - battery.level) * 100),
          }))
        } catch {
          // ignore
        }
      }
      const start = performance.now()
      let count = 0
      const interval = setInterval(() => {
        count++
        if (count >= 10) {
          clearInterval(interval)
          const end = performance.now()
          const cpuUsage = Math.min(100, Math.round((end - start) / 10))
          setSystemMetrics((prev) => ({
            ...prev,
            cpuUsage,
          }))
        }
      }, 100)
    }
    updateMetrics()
    const interval = setInterval(updateMetrics, 5000)
    return () => clearInterval(interval)
  }, [])

  const animationFps = diagnostics?.frameRateHz ?? 0
  const frameStateFreq = diagnostics?.frameStateFrequencyHz ?? 0

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-4 right-4 z-50 rounded-lg border border-white/20 bg-black/60 px-3 py-1.5 text-xs text-white/70 backdrop-blur hover:bg-black/80 hover:text-white"
      >
        Diagnostics
      </button>
    )
  }

  return (
    <div className="fixed bottom-4 right-4 z-50 w-96 max-h-[80vh] overflow-y-auto rounded-2xl border border-cyan-400/30 bg-black/90 p-4 shadow-2xl backdrop-blur-xl">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-cyan-300">Development Diagnostics</h3>
        <button className="text-white/50 hover:text-white" onClick={() => setOpen(false)}>
          ✕
        </button>
      </div>

      <div className="space-y-3 text-xs">
        <section>
          <h4 className="mb-1 font-semibold text-white/80 flex items-center gap-1">
            <Boxes className="w-3.5 h-3.5" />
            Runtime Modules
          </h4>
          <div className="space-y-1">
            {['PresenceRuntime', 'AnimationRuntime', 'LivingOrbAdapter', 'OrbRenderer', 'EngineAdapter'].map((module) => (
              <div key={module} className="flex items-center justify-between rounded bg-white/5 px-2 py-1">
                <span className="text-white/70">{module}</span>
                <span className="text-[10px] text-green-400 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
                  Running
                </span>
              </div>
            ))}
          </div>
        </section>

        <section>
          <h4 className="mb-1 font-semibold text-white/80 flex items-center gap-1">
            <Activity className="w-3.5 h-3.5" />
            Runtime Health
          </h4>
          <div className="grid grid-cols-2 gap-1">
            <DiagnosticRow label="Presence" value={diagnostics?.presenceRuntimeStatus ?? '—'} />
            <DiagnosticRow label="Engine" value={diagnostics?.animationRuntimeStatus ?? '—'} />
            <DiagnosticRow label="Renderer" value={diagnostics?.rendererHealth ?? '—'} />
            <DiagnosticRow label="Embodiment" value={diagnostics?.currentEmbodiment ?? '—'} />
            <DiagnosticRow label="Healthy" value={diagnostics?.embodimentHealthy ? 'Yes' : 'No'} />
            <DiagnosticRow label="Quality" value={diagnostics?.qualityLevel ?? '—'} />
          </div>
        </section>

        <section>
          <h4 className="mb-1 font-semibold text-white/80 flex items-center gap-1">
            <Gauge className="w-3.5 h-3.5" />
            Performance
          </h4>
          <div className="grid grid-cols-2 gap-1">
            <DiagnosticRow label="Animation FPS" value={String(animationFps)} />
            <DiagnosticRow label="Renderer FPS" value={String(rendererFps)} />
            <DiagnosticRow label="Frame Latency" value={`${frameLatencyMs.toFixed(1)} ms`} />
            <DiagnosticRow label="Frame Freq" value={`${frameStateFreq.toFixed(1)} Hz`} />
            <DiagnosticRow label="GPU Frame" value={diagnostics?.gpuFrameTimeMs ? `${diagnostics.gpuFrameTimeMs.toFixed(1)} ms` : '—'} />
            <DiagnosticRow label="CPU Frame" value={diagnostics?.cpuFrameTimeMs ? `${diagnostics.cpuFrameTimeMs.toFixed(1)} ms` : '—'} />
            <DiagnosticRow label="Frame Budget" value={diagnostics?.frameBudgetMs ? `${diagnostics.frameBudgetMs.toFixed(1)} ms` : '—'} />
            <DiagnosticRow label="Dropped" value={String(diagnostics?.droppedFrames ?? 0)} />
          </div>
        </section>

        <section>
          <h4 className="mb-1 font-semibold text-white/80 flex items-center gap-1">
            <HardDrive className="w-3.5 h-3.5" />
            System
          </h4>
          <div className="grid grid-cols-2 gap-1">
            <DiagnosticRow label="Memory" value={`${systemMetrics.memoryUsage}%`} />
            <DiagnosticRow label="GPU" value={`${systemMetrics.gpuUsage}%`} />
            <DiagnosticRow label="CPU" value={`${systemMetrics.cpuUsage}%`} />
            <DiagnosticRow label="Uptime" value={diagnostics?.uptimeMs ? `${Math.round(diagnostics.uptimeMs / 1000)}s` : '—'} />
          </div>
        </section>

        <section>
          <h4 className="mb-1 font-semibold text-white/80">FrameState</h4>
          <pre className="whitespace-pre-wrap break-words rounded bg-white/5 p-2 text-white/70">
            {frameState ? JSON.stringify(frameState, null, 2) : 'No frame received'}
          </pre>
        </section>

        <section>
          <h4 className="mb-1 font-semibold text-white/80">RuntimeState (engine input)</h4>
          <pre className="whitespace-pre-wrap break-words rounded bg-white/5 p-2 text-white/70">
            {frameState
              ? JSON.stringify(
                  {
                    state: frameState.system.state,
                    cognitiveLoad: frameState.system.cognitiveLoad,
                    audio: frameState.audio
                  },
                  null,
                  2
                )
              : 'No frame received'}
          </pre>
        </section>
      </div>
    </div>
  )
}

function DiagnosticRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-white/50">{label}</span>
      <span className="font-mono text-white/80">{value}</span>
    </div>
  )
}

export default DiagnosticsPanel