import { motion } from 'framer-motion'
import { Cpu, HardDrive, Activity, Clock } from 'lucide-react'
import { useModelStore } from '@/stores/modelStore'
import { useThemeStore } from '@/stores/themeStore'

export function RightPanel() {
  const { currentModel, currentProvider, currentVoice } = useModelStore()
  const { rightPanelOpen } = useThemeStore()

  if (!rightPanelOpen) return null

  return (
    <motion.aside
      initial={{ x: 300, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      className="w-80 glass border-l border-white/10 p-6 space-y-6 overflow-y-auto"
    >
      <div>
        <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
          <Activity className="w-4 h-4" />
          System Status
        </h3>
        <div className="space-y-3">
          <div className="glass rounded-lg p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-muted-foreground">GPU Usage</span>
              <span className="text-xs font-medium">45%</span>
            </div>
            <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
              <div className="h-full w-[45%] bg-gradient-to-r from-cyan-500 to-blue-500 rounded-full" />
            </div>
          </div>
          <div className="glass rounded-lg p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-muted-foreground">Memory</span>
              <span className="text-xs font-medium">6.2 GB</span>
            </div>
            <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
              <div className="h-full w-[62%] bg-gradient-to-r from-orange-500 to-red-500 rounded-full" />
            </div>
          </div>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-4">Active Configuration</h3>
        <div className="space-y-3">
          <div className="glass rounded-lg p-3">
            <p className="text-xs text-muted-foreground mb-1">Model</p>
            <p className="text-sm font-medium">{currentModel?.name || 'None'}</p>
          </div>
          <div className="glass rounded-lg p-3">
            <p className="text-xs text-muted-foreground mb-1">Provider</p>
            <p className="text-sm font-medium">{currentProvider?.name || 'None'}</p>
          </div>
          <div className="glass rounded-lg p-3">
            <p className="text-xs text-muted-foreground mb-1">Voice</p>
            <p className="text-sm font-medium">{currentVoice?.name || 'None'}</p>
          </div>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
          <Clock className="w-4 h-4" />
          Recent Activity
        </h3>
        <div className="space-y-2">
          {['Model loaded: Gemma 3', 'Session started', 'Voice activated'].map((activity, i) => (
            <div key={i} className="text-xs text-muted-foreground py-2 border-b border-white/5 last:border-0">
              {activity}
            </div>
          ))}
        </div>
      </div>
    </motion.aside>
  )
}