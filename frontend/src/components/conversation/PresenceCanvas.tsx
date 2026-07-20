// frontend/src/components/conversation/PresenceCanvas.tsx
//
// The visual heart of Zaram. Hosts the Living Orb or Avatar.
// Designed for expansion: vision indicators, thinking animations,
// screen sharing status, long-running task visualization.

import { useEffect, useRef } from 'react'
import { OrbEngine } from '@/components/OrbEngine/OrbEngine'
import type { ExecutiveState } from '@/pages/ConversationPanel'

interface PresenceCanvasProps {
  className?: string
  state?: ExecutiveState
  mode?: 'orb' | 'avatar'
  onModeChange?: (mode: 'orb' | 'avatar') => void
}

export function PresenceCanvas({ className, state = 'idle', mode = 'orb', onModeChange }: PresenceCanvasProps) {
  const canvasRef = useRef<HTMLDivElement>(null)

  return (
    <div className={`h-full w-full flex flex-col items-center justify-center relative ${className ?? ''}`}>
      {/* Main Presence Area - Stage for orb/avatar */}
      <div ref={canvasRef} className="flex-1 w-full flex items-center justify-center relative overflow-visible">
        <div className="w-full h-full flex items-center justify-center overflow-visible">
          {mode === 'orb' && (
            <div className="w-full h-full flex items-center justify-center overflow-visible">
              <OrbEngine className="w-full h-full" />
            </div>
          )}
          {mode === 'avatar' && (
            <div className="w-full h-full flex items-center justify-center">
              <div className="text-slate-500 text-sm">Avatar coming soon</div>
            </div>
          )}
        </div>
      </div>

      {/* Mode Toggle */}
      <div className="flex items-center gap-4 px-6 py-3 border-t border-white/5 flex-shrink-0">
        <button
          onClick={() => onModeChange?.('orb')}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs transition-colors ${
            mode === 'orb'
              ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
              : 'text-slate-400 hover:text-white border border-transparent'
          }`}
        >
          <span className="w-2 h-2 rounded-full bg-current" />
          Orb
        </button>
        <button
          onClick={() => onModeChange?.('avatar')}
          disabled
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs transition-colors ${
            mode === 'avatar'
              ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
              : 'text-slate-500 border border-transparent opacity-50'
          }`}
        >
          <span className="w-2 h-2 rounded-full bg-current" />
          Avatar
        </button>
      </div>
    </div>
  )
}
