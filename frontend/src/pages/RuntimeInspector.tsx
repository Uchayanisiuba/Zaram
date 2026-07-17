import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import {
  Cpu, HardDrive, Activity, Zap, Brain, Globe, FolderOpen,
  Hash, FileText, GitBranch, AlertTriangle, Shield,
  Search, Play, Clock, BarChart3
} from 'lucide-react'
import { desktop } from '@/desktop/desktop-bridge'
import { Button } from '@/components/ui/Button'
import { useWorkspaceContextStore } from '@/stores/workspaceContextStore'

type RuntimeStatus = 'healthy' | 'degraded' | 'offline' | 'loading' | 'restarting' | 'ready' | 'busy' | 'error'

interface RuntimeInfo {
  name: string
  status: RuntimeStatus
  description: string
  uptime?: number
  lastUpdate?: number
}

export function RuntimeInspector() {
  const [health, setHealth] = useState<any>(null)
  const [runtimes, setRuntimes] = useState<RuntimeInfo[]>([])
  const [refreshing, setRefreshing] = useState(false)
  const [workspaceState, setWorkspaceState] = useState<any>(null)
  const [workspaceContext, setWorkspaceContext] = useState<any>(null)
  const [vscodeSnapshot, setVscodeSnapshot] = useState<any>(null)
  const [executivePlan, setExecutivePlan] = useState<any>(null)
  const [executiveConfidence, setExecutiveConfidence] = useState(0)
  const [executiveEvidence, setExecutiveEvidence] = useState<string[]>([])
  const [capabilityMetrics, setCapabilityMetrics] = useState<any[]>([])
  const [filesystemMetrics, setFilesystemMetrics] = useState<any>(null)
  const [executiveSnapshot, setExecutiveSnapshot] = useState<any>(null)
  const advancedMode = useWorkspaceContextStore((s) => s.advancedMode)
  const setAdvancedMode = useWorkspaceContextStore((s) => s.setAdvancedMode)
  const storeSnapshot = useWorkspaceContextStore((s) => s.snapshot)
  const subscribeToWorkspace = useWorkspaceContextStore((s) => s.subscribeToWorkspace)

  const statusColor = (status: RuntimeStatus) => {
    switch (status) {
      case 'healthy': return 'bg-green-400'
      case 'ready': return 'bg-green-400'
      case 'busy': return 'bg-blue-400'
      case 'degraded': return 'bg-yellow-400'
      case 'offline': return 'bg-red-400'
      case 'loading': return 'bg-blue-400'
      case 'restarting': return 'bg-orange-400'
      case 'error': return 'bg-red-400'
      default: return 'bg-slate-400'
    }
  }

  const statusLabel = (status: RuntimeStatus) => {
    return status.toUpperCase()
  }

  const refresh = useCallback(async () => {
    setRefreshing(true)
    try {
      const h = await desktop.presence.getHealth()
      setHealth(h)
      const ws = (await desktop.workspace.getState()) as any
      setWorkspaceState(ws)
      const ctx = (await desktop.workspace.getContext()) as any
      setWorkspaceContext(ctx)
      const vsc = (await desktop.vscode.getSnapshot()) as any
      setVscodeSnapshot(vsc)
      const plan = (await desktop.executive.getPlan()) as any
      setExecutivePlan(plan)
      const confidence = (await desktop.executive.getConfidence()) as number
      setExecutiveConfidence(confidence)
      const evidence = (await desktop.executive.getEvidence()) as string[]
      setExecutiveEvidence(evidence)
      const metrics = (await desktop.executive.getMetrics()) as any[]
      setCapabilityMetrics(metrics)
      const fsMetrics = (await desktop.filesystem.getMetrics()) as any
      setFilesystemMetrics(fsMetrics)
    } catch {
      // ignore
    }
    setRefreshing(false)
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  useEffect(() => {
    const unsubExec = desktop.execution.onEvent(() => {
      refresh()
    })
    const unsubWorkspace = subscribeToWorkspace()
    const unsubVSCode = desktop.vscode?.onEvent?.(() => {
      refresh()
    }) || (() => {})
    const unsubExecSnapshot = desktop.executive.onSnapshot((snap: any) => {
      setExecutiveSnapshot(snap)
    })
    return () => {
      unsubExec()
      unsubWorkspace()
      unsubVSCode()
      unsubExecSnapshot()
    }
  }, [refresh, subscribeToWorkspace])

  const buildRuntimes = useCallback((h: any): RuntimeInfo[] => {
    if (!h) return []
    const execStatus = executiveSnapshot ? 'busy' : 'ready'
    const execDesc = executiveSnapshot?.goal
      ? `Goal: ${executiveSnapshot.goal.slice(0, 60)}${executiveSnapshot.goal.length > 60 ? '...' : ''}`
      : 'High-level decision-making and intent generation'

    const list: RuntimeInfo[] = [
      {
        name: 'Presence Runtime',
        status: h.presenceRuntimeStatus === 'running' ? 'healthy' : h.presenceRuntimeStatus === 'paused' ? 'degraded' : 'offline',
        description: 'Central orchestrator and 30Hz tick owner',
        uptime: h.uptimeMs,
        lastUpdate: h.lastFrameAt
      },
      {
        name: 'Animation Runtime',
        status: h.animationRuntimeStatus === 'running' ? 'healthy' : h.animationRuntimeStatus === 'paused' ? 'degraded' : 'offline',
        description: 'Engine adapter for FrameState production'
      },
      {
        name: 'Embodiment',
        status: h.embodimentHealthy ? 'healthy' : 'offline',
        description: h.currentEmbodiment ? `Type: ${h.currentEmbodiment}` : 'No embodiment attached'
      },
      {
        name: 'Renderer',
        status: h.rendererHealth === 'healthy' ? 'healthy' : h.rendererHealth === 'degraded' ? 'degraded' : 'offline',
        description: 'Canvas renderer health and GPU context'
      },
      {
        name: 'World Runtime',
        status: 'ready',
        description: 'System perception aggregation'
      },
      {
        name: 'Cognitive Runtime',
        status: 'ready',
        description: 'Internal AI state: attention, relationship, reasoning'
      },
      {
        name: 'Executive Runtime',
        status: execStatus,
        description: execDesc
      },
      {
        name: 'Execution Runtime',
        status: 'ready',
        description: 'Capability invocation lifecycle and audit'
      },
      {
        name: 'Capability Runtime',
        status: 'ready',
        description: 'Capability metadata registry and discovery'
      },
      {
        name: 'Character Runtime',
        status: 'ready',
        description: 'Emotion and behaviour projection'
      },
      {
        name: 'Workspace Runtime',
        status: storeSnapshot ? 'ready' : 'loading',
        description: storeSnapshot
          ? `Workspace: ${storeSnapshot.workspace} (${storeSnapshot.projects} projects, ${storeSnapshot.open_modules.length} files)`
          : 'Semantic project understanding and indexing'
      },
      {
        name: 'VS Code Runtime',
        status: vscodeSnapshot?.connected ? 'healthy' : 'offline',
        description: vscodeSnapshot?.connected
          ? `Workspace: ${vscodeSnapshot.workspace || 'unknown'}`
          : 'Developer context: editor, diagnostics, git status'
      }
    ]
    return list
  }, [executiveSnapshot, storeSnapshot, vscodeSnapshot])

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
        <div>
          <h2 className="text-lg font-bold text-white tracking-wide">RUNTIME INSPECTOR</h2>
          <p className="text-xs text-slate-400 mt-1">All registered runtimes and their status</p>
        </div>
        <Button variant="ghost" size="sm" onClick={refresh} disabled={refreshing}>
          <Activity className={`w-3 h-3 mr-1 ${refreshing ? 'animate-spin' : ''}`} />
          {refreshing ? 'Refreshing...' : 'Refresh'}
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="grid grid-cols-2 gap-4">
          {runtimes.map((rt) => (
            <motion.div
              key={rt.name}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="glass rounded-xl p-5 border border-white/10 hover:border-white/20 transition-colors"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center">
                    {rt.name.includes('Presence') && <Zap className="w-4 h-4 text-yellow-400" />}
                    {rt.name.includes('Animation') && <Activity className="w-4 h-4 text-purple-400" />}
                    {rt.name.includes('Embodiment') && <HardDrive className="w-4 h-4 text-green-400" />}
                    {rt.name.includes('Renderer') && <Cpu className="w-4 h-4 text-cyan-400" />}
                    {rt.name.includes('World') && <Globe className="w-4 h-4 text-blue-400" />}
                    {rt.name.includes('Cognitive') && <Brain className="w-4 h-4 text-pink-400" />}
                    {rt.name.includes('Executive') && <Brain className="w-4 h-4 text-orange-400" />}
                    {rt.name.includes('Execution') && <Activity className="w-4 h-4 text-red-400" />}
                    {rt.name.includes('Capability') && <Cpu className="w-4 h-4 text-teal-400" />}
                    {rt.name.includes('Character') && <Activity className="w-4 h-4 text-indigo-400" />}
                    {rt.name.includes('Workspace') && <FolderOpen className="w-4 h-4 text-emerald-400" />}
                    {rt.name.includes('VS Code') && <FileText className="w-4 h-4 text-violet-400" />}
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white">{rt.name}</h3>
                    <p className="text-[10px] text-slate-400 mt-0.5">{rt.description}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${statusColor(rt.status)}`} />
                  <span className="text-[10px] font-mono text-slate-400">{statusLabel(rt.status)}</span>
                </div>
              </div>
              {rt.uptime && (
                <div className="flex items-center gap-4 text-[10px] text-slate-500">
                  <span>Uptime: {rt.uptime.toFixed(0)} ms</span>
                </div>
              )}
            </motion.div>
          ))}
        </div>

        {health && (
          <div className="mt-8 glass rounded-xl p-5 border border-white/10">
            <h3 className="text-sm font-bold text-white mb-4">System Diagnostics</h3>
            <div className="grid grid-cols-4 gap-4">
              <div>
                <p className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">Frame Rate</p>
                <p className="text-sm font-mono text-white">{health.frameRateHz || '--'} Hz</p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">Dropped Frames</p>
                <p className="text-sm font-mono text-white">{health.droppedFrames ?? '--'}</p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">GPU Frame Time</p>
                <p className="text-sm font-mono text-white">{health.gpuFrameTimeMs ? `${health.gpuFrameTimeMs.toFixed(1)} ms` : '--'}</p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">Quality Level</p>
                <p className="text-sm font-mono text-white">{health.qualityLevel || '--'}</p>
              </div>
            </div>
          </div>
        )}

        <div className="mt-8 glass rounded-xl p-5 border border-white/10">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Brain className="w-4 h-4 text-orange-400" />
              Executive Runtime
            </h3>
            <span className="text-[10px] text-slate-400">Confidence: {Math.round(executiveConfidence * 100)}%</span>
          </div>

          {executiveSnapshot ? (
            <div className="space-y-4">
              <div>
                <p className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">Status</p>
                <p className="text-sm font-mono text-white capitalize">{executiveSnapshot.state?.currentIntent || 'Ready'}</p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">Goal</p>
                <p className="text-sm font-mono text-white">{executiveSnapshot.goal || '—'}</p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">Plan Steps</p>
                <div className="space-y-1">
                  {executiveSnapshot.steps?.map((step: any, i: number) => (
                    <div key={i} className="flex items-center gap-2 text-xs">
                      <div className={`w-1.5 h-1.5 rounded-full ${step.status === 'completed' ? 'bg-green-400' : step.status === 'running' ? 'bg-blue-400 animate-pulse' : 'bg-slate-500'}`} />
                      <span className="text-slate-300">{step.description || step.capabilityId}</span>
                    </div>
                  ))}
                </div>
              </div>
              {executiveEvidence.length > 0 && (
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">Evidence</p>
                  <div className="space-y-1">
                    {executiveEvidence.map((item, i) => (
                      <p key={i} className="text-xs text-slate-400">- {item}</p>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <p className="text-xs text-slate-500">No active plan</p>
          )}
        </div>

        <div className="mt-8 glass rounded-xl p-5 border border-white/10">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <FolderOpen className="w-4 h-4 text-emerald-400" />
              Workspace Runtime
            </h3>
            <label className="flex items-center gap-2 text-[10px] text-slate-400 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={advancedMode}
                onChange={(e) => setAdvancedMode(e.target.checked)}
                className="rounded"
              />
              Advanced Mode
            </label>
          </div>

          {storeSnapshot ? (
            <div className="space-y-4">
              <div>
                <p className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">Workspace</p>
                <p className="text-sm font-mono text-white">{storeSnapshot.workspace || '—'}</p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <RuntimeField label="Framework" value={storeSnapshot.framework} />
                <RuntimeField label="Language" value={storeSnapshot.language} />
                <RuntimeField label="Projects" value={String(storeSnapshot.projects)} />
                <RuntimeField label="Files Indexed" value={String(storeSnapshot.open_modules.length)} />
                <RuntimeField
                  label="Status"
                  value={storeSnapshot.projects > 0 ? 'Synced' : 'Awaiting'}
                />
                <RuntimeField label="Confidence" value={`${storeSnapshot.confidence}%`} />
              </div>

              {advancedMode && workspaceState?.workspaceHash && (
                <div className="flex items-center gap-2 text-[10px] text-slate-500 font-mono">
                  <Hash className="w-3 h-3" />
                  <span className="break-all">{workspaceState.workspaceHash}</span>
                </div>
              )}

              {!advancedMode && workspaceState?.workspaceHash && (
                <p className="text-[10px] text-slate-600">Enable Advanced Mode to reveal internal hashes</p>
              )}
            </div>
          ) : (
            <p className="text-xs text-slate-500">No workspace indexed yet</p>
          )}
        </div>

        <div className="mt-8 glass rounded-xl p-5 border border-white/10">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <HardDrive className="w-4 h-4 text-orange-400" />
              Filesystem Capability Pack
            </h3>
          </div>

          {filesystemMetrics ? (
            <div className="grid grid-cols-2 gap-4">
              <RuntimeField label="Operations" value={String(filesystemMetrics.operationsExecuted ?? 0)} />
              <RuntimeField label="Reads" value={String(filesystemMetrics.readCount ?? 0)} />
              <RuntimeField label="Writes" value={String(filesystemMetrics.writeCount ?? 0)} />
              <RuntimeField label="Searches" value={String(filesystemMetrics.searchCount ?? 0)} />
              <RuntimeField label="Average Time" value={filesystemMetrics.averageTimeMs ? `${filesystemMetrics.averageTimeMs.toFixed(1)}ms` : '--'} />
              <RuntimeField label="Status" value={filesystemMetrics.available !== false ? 'Healthy' : 'Unavailable'} />
            </div>
          ) : (
            <p className="text-xs text-slate-500">No filesystem operations yet</p>
          )}
        </div>

        <div className="mt-8 glass rounded-xl p-5 border border-white/10">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <FileText className="w-4 h-4 text-violet-400" />
              VS Code Capability Pack
            </h3>
            <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded ${vscodeSnapshot?.connected ? 'bg-green-400/10 text-green-400' : 'bg-slate-400/10 text-slate-400'}`}>
              {vscodeSnapshot?.connected ? 'Connected' : 'Offline'}
            </span>
          </div>

          {vscodeSnapshot ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <RuntimeField label="Workspace" value={vscodeSnapshot.workspace || '—'} />
                <RuntimeField label="Active File" value={vscodeSnapshot.activeFile || '—'} />
                <RuntimeField label="Language" value={vscodeSnapshot.language || '—'} />
                <RuntimeField label="Diagnostics" value={String(vscodeSnapshot.diagnostics ?? 0)} />
                <RuntimeField label="Git Branch" value={vscodeSnapshot.gitBranch || '—'} />
                <RuntimeField label="Modified Files" value={String(vscodeSnapshot.modifiedFiles ?? 0)} />
              </div>
              {vscodeSnapshot.selection && (
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">Selection</p>
                  <p className="text-xs font-mono text-white truncate">{vscodeSnapshot.selection}</p>
                </div>
              )}
            </div>
          ) : (
            <p className="text-xs text-slate-500">No VS Code context available</p>
          )}
        </div>

        {capabilityMetrics.length > 0 && (
          <div className="mt-8 glass rounded-xl p-5 border border-white/10">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-teal-400" />
                Capability Metrics
              </h3>
            </div>
            <div className="space-y-2">
              {capabilityMetrics.slice(0, 10).map((metric, i) => (
                <div key={i} className="flex items-center justify-between text-xs p-2 rounded bg-white/5">
                  <span className="font-mono text-slate-300">{metric.capabilityId}</span>
                  <div className="flex items-center gap-4 text-[10px] text-slate-500">
                    <span>Calls: {metric.calls}</span>
                    <span>Avg: {metric.calls > 0 ? Math.round(metric.totalTimeMs / metric.calls) : 0}ms</span>
                    <span className={metric.failures === 0 ? 'text-green-400' : 'text-red-400'}>
                      {metric.calls > 0 ? Math.round((metric.successes / metric.calls) * 100) : 0}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function RuntimeField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">{label}</p>
      <p className="text-sm font-mono text-white">{value}</p>
    </div>
  )
}
