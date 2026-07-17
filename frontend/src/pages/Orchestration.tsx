import { useState, useEffect, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Activity, Play, Pause, SkipForward, RefreshCw } from 'lucide-react'
import { OrbEngine } from '@/components/OrbEngine/OrbEngine'
import { desktop } from '@/desktop/desktop-bridge'
import { Button } from '@/components/ui/Button'

const STATE_COLORS: Record<string, { primary: string; secondary: string }> = {
  Idle: { primary: '#3b82f6', secondary: '#06b6d4' },
  Listening: { primary: '#06b6d4', secondary: '#22d3ee' },
  Thinking: { primary: '#a855f7', secondary: '#d946ef' },
  Working: { primary: '#6366f1', secondary: '#818cf8' },
  Speaking: { primary: '#10b981', secondary: '#34d399' },
  Sleeping: { primary: '#8b5cf6', secondary: '#a78bfa' },
  Error: { primary: '#ef4444', secondary: '#f87171' },
}

export function Orchestration() {
  const [state, setState] = useState('Idle')
  const [health, setHealth] = useState<any>(null)
  const [frame, setFrame] = useState<any>(null)
  const intervalRef = useRef<number | null>(null)

  const refresh = useCallback(async () => {
    try {
      const h = await desktop.presence.getHealth()
      setHealth(h)
      const snap = await desktop.executive.getSnapshot()
      if (snap?.state) {
        setState(snap.state.currentIntent || 'Idle')
      }
    } catch {
      // runtime not available yet
    }
  }, [])

  useEffect(() => {
    refresh()
    intervalRef.current = window.setInterval(refresh, 1000)
    return () => {
      if (intervalRef.current) window.clearInterval(intervalRef.current)
    }
  }, [refresh])

  const togglePause = async () => {
    if (health?.presenceRuntimeStatus === 'paused') {
      await desktop.presence.getStatus()
      // resume via start
    }
  }

  const colors = STATE_COLORS[state] || STATE_COLORS.Idle

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
        <div>
          <h2 className="text-lg font-bold text-white tracking-wide">LIVING ORB</h2>
          <p className="text-xs text-slate-400 mt-1">Real-time runtime presence visualization</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="px-3 py-1.5 rounded-full text-xs font-mono border" style={{ borderColor: `${colors.primary}40`, color: colors.primary }}>
            STATE: {state.toUpperCase()}
          </div>
          <div className="px-3 py-1.5 rounded-full text-xs font-mono border border-white/10 text-slate-300">
            {health?.frameRateHz ? `${health.frameRateHz} Hz` : '-- Hz'}
          </div>
        </div>
      </div>

      <div className="flex-1 flex items-center justify-center relative overflow-hidden">
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none" style={{ margin: '-120px' }}>
          <OrbEngine className="w-full h-full" />
        </div>
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex items-center gap-4 z-10">
          <Button variant="ghost" size="icon" onClick={refresh} title="Refresh">
            <RefreshCw className="w-4 h-4" />
          </Button>
        </div>
      </div>

      <div className="px-6 py-4 border-t border-white/5">
        <div className="grid grid-cols-4 gap-4">
          {[
            { label: 'Frame Rate', value: health?.frameRateHz ? `${health.frameRateHz} Hz` : '--' },
            { label: 'Dropped Frames', value: health?.droppedFrames ?? '--' },
            { label: 'GPU Time', value: health?.gpuFrameTimeMs ? `${health.gpuFrameTimeMs.toFixed(1)} ms` : '--' },
            { label: 'Embodiment', value: health?.currentEmbodiment || 'none' },
          ].map((item) => (
            <div key={item.label} className="glass rounded-lg p-3 border border-white/5">
              <p className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">{item.label}</p>
              <p className="text-sm font-mono text-white">{item.value}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
