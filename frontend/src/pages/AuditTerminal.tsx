import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Terminal, CheckCircle2, XCircle, Clock, AlertTriangle,
  ChevronRight, ChevronDown, RefreshCw, FolderOpen, FileText,
  GitBranch, Play, Search, FileCode, Activity, BarChart3,
  Zap, Globe, HardDrive, Cpu
} from 'lucide-react'
import { desktop } from '@/desktop/desktop-bridge'
import { Button } from '@/components/ui/Button'
import { describeWorkspaceEvent } from '@/lib/workspaceConversation'

type ExecutionEvent = {
  event_id: string
  timestamp: number
  event_type: string
  data: any
}

type WorkspaceEvent = {
  eventId: number
  timestamp: number
  type: string
  data: Record<string, unknown>
}

type ExecutionHistoryEntry = {
  attempt: number
  status: string
  startedAt: number
  finishedAt: number
  durationMs: number
  error?: string
}

type ExecutionRecord = {
  id: string
  capabilityId: string
  status: string
  input: any
  output: any
  error: any
  progress: number
  startedAt: number | null
  finishedAt: number | null
  durationMs: number | null
  audit: any[]
  history: ExecutionHistoryEntry[]
}

type TabId = 'timeline' | 'history' | 'workspace' | 'vscode'

type VSCodeEvent = {
  type: string
  timestamp: number
  data: Record<string, unknown>
}

interface TimelineEntry {
  id: string
  type: 'execution' | 'workspace' | 'vscode' | 'system' | 'plan' | 'response'
  timestamp: number
  title: string
  description?: string
  status?: string
  durationMs?: number
  confidence?: number
  evidence?: string[]
  children?: TimelineEntry[]
  expanded?: boolean
}

const EXECUTIVE_COLOR = 'border-blue-400 bg-blue-400/5'
const WORKSPACE_COLOR = 'border-emerald-400 bg-emerald-400/5'
const FILESYSTEM_COLOR = 'border-orange-400 bg-orange-400/5'
const VSCODE_COLOR = 'border-violet-400 bg-violet-400/5'
const SYSTEM_COLOR = 'border-slate-400 bg-slate-400/5'
const PLAN_COLOR = 'border-cyan-400 bg-cyan-400/5'
const RESPONSE_COLOR = 'border-green-400 bg-green-400/5'

function getCapabilityColor(capabilityId: string): string {
  if (capabilityId.startsWith('filesystem.')) return FILESYSTEM_COLOR
  if (capabilityId.startsWith('workspace.')) return WORKSPACE_COLOR
  if (capabilityId.startsWith('vscode.')) return VSCODE_COLOR
  if (capabilityId.startsWith('execution.')) return EXECUTIVE_COLOR
  return SYSTEM_COLOR
}

function getEventColor(type: string): string {
  if (type.startsWith('workspace.')) return WORKSPACE_COLOR
  if (type.startsWith('vscode.')) return VSCODE_COLOR
  if (type.startsWith('filesystem.')) return FILESYSTEM_COLOR
  return SYSTEM_COLOR
}

export function AuditTerminal() {
  const [activeTab, setActiveTab] = useState<TabId>('timeline')
  const [history, setHistory] = useState<ExecutionRecord[]>([])
  const [workspaceEvents, setWorkspaceEvents] = useState<WorkspaceEvent[]>([])
  const [vscodeEvents, setVscodeEvents] = useState<VSCodeEvent[]>([])
  const [timeline, setTimeline] = useState<TimelineEntry[]>([])
  const [selectedExec, setSelectedExec] = useState<ExecutionRecord | null>(null)
  const [collapsedIds, setCollapsedIds] = useState<Set<string>>(new Set())
  const [autoScroll, setAutoScroll] = useState(true)
  const [executionPlans, setExecutionPlans] = useState<Array<{ goal: string; steps: string[]; confidence: number; timestamp: number }>>([])

  const loadHistory = useCallback(async () => {
    try {
      const h = await desktop.execution.getHistory()
      setHistory(h || [])
      buildTimeline(h || [])
    } catch {
      // ignore
    }
  }, [workspaceEvents, vscodeEvents, executionPlans])

  const buildTimeline = useCallback((execHistory: ExecutionRecord[]) => {
    const entries: TimelineEntry[] = []

    for (const plan of executionPlans) {
      const parentId = `plan-${plan.timestamp}`
      entries.push({
        id: parentId,
        type: 'plan',
        timestamp: plan.timestamp,
        title: `Goal: ${plan.goal}`,
        status: 'completed',
        confidence: plan.confidence,
        expanded: !collapsedIds.has(parentId),
        children: plan.steps.map((step, i) => ({
          id: `${parentId}-step-${i}`,
          type: 'execution',
          timestamp: plan.timestamp + i * 100,
          title: step,
          status: 'completed',
        }))
      })
    }

    for (const exec of execHistory) {
      const parentId = `exec-${exec.id}`
      entries.push({
        id: parentId,
        type: 'execution',
        timestamp: exec.startedAt || Date.now(),
        title: exec.capabilityId,
        description: exec.input ? JSON.stringify(exec.input).slice(0, 120) : undefined,
        status: exec.status,
        durationMs: exec.durationMs || undefined,
        expanded: !collapsedIds.has(parentId),
        children: [
          {
            id: `${parentId}-result`,
            type: 'execution',
            timestamp: exec.finishedAt || exec.startedAt || Date.now(),
            title: exec.status === 'completed' ? 'Completed' : exec.status === 'failed' ? 'Failed' : exec.status,
            description: exec.output ? (typeof exec.output === 'string' ? exec.output.slice(0, 200) : JSON.stringify(exec.output).slice(0, 200)) : exec.error?.message,
            status: exec.status,
            durationMs: exec.durationMs || undefined,
          }
        ]
      })
    }

    for (const evt of workspaceEvents) {
      entries.push({
        id: `ws-${evt.eventId}`,
        type: 'workspace',
        timestamp: evt.timestamp,
        title: describeWorkspaceEvent(evt.type).label,
        status: evt.type.includes('error') ? 'failed' : 'completed',
      })
    }

    for (const evt of vscodeEvents) {
      entries.push({
        id: `vsc-${evt.timestamp}-${evt.type}`,
        type: 'vscode',
        timestamp: evt.timestamp,
        title: describeVSCodeEvent(evt.type),
        status: evt.type.includes('error') ? 'failed' : 'completed',
      })
    }

    entries.sort((a, b) => a.timestamp - b.timestamp)
    setTimeline(entries)
  }, [collapsedIds, workspaceEvents, vscodeEvents, executionPlans])

  useEffect(() => {
    loadHistory()
    const unsubExec = desktop.execution.onEvent((evt: ExecutionEvent) => {
      setHistory(prev => {
        const updated = [...prev]
        const idx = updated.findIndex(e => e.id === evt.data?.executionId)
        if (idx >= 0) {
          updated[idx] = { ...updated[idx], ...evt.data }
        }
        return updated
      })
    })
    const unsubWorkspace = desktop.workspace.onEvent((evt: WorkspaceEvent) => {
      setWorkspaceEvents(prev => [...prev.slice(-200), evt])
    })
    const unsubVSCode = desktop.vscode?.onEvent?.((evt: VSCodeEvent) => {
      setVscodeEvents(prev => [...prev.slice(-200), evt])
    }) || (() => {})
    const unsubExecPlan = desktop.executive.onSnapshot((snap: any) => {
      if (snap?.goal && snap?.steps && snap.steps.length > 0) {
        setExecutionPlans(prev => [...prev.slice(-20), {
          goal: snap.goal,
          steps: snap.steps.map((s: any) => s.description || s.capabilityId),
          confidence: snap.state?.confidence || 0,
          timestamp: Date.now(),
        }])
      }
    })
    return () => {
      unsubExec()
      unsubWorkspace()
      unsubVSCode()
      unsubExecPlan()
    }
  }, [loadHistory])

  useEffect(() => {
    buildTimeline(history)
  }, [history, buildTimeline])

  useEffect(() => {
    if (autoScroll && activeTab === 'timeline' && timeline.length > 0) {
      const el = document.getElementById('audit-scroll-timeline')
      if (el) el.scrollTop = el.scrollHeight
    }
  }, [timeline, autoScroll, activeTab])

  const toggleCollapse = (id: string) => {
    setCollapsedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const formatTime = (ts: number | null) => {
    if (!ts) return '--'
    return new Date(ts).toLocaleTimeString()
  }

  const formatDuration = (ms: number | null | undefined) => {
    if (!ms) return '--'
    return `${ms.toFixed(1)} ms`
  }

  const tabClass = (tab: TabId) =>
    `px-4 py-2 text-xs font-bold uppercase tracking-wider border-b-2 transition-colors ${
      activeTab === tab ? 'border-white text-white' : 'border-transparent text-slate-400 hover:text-slate-200'
    }`

  const workspaceEventIcon = (type: string) => {
    if (type.includes('scan_started')) return <Clock className="w-3 h-3 text-blue-400" />
    if (type.includes('scan_completed')) return <CheckCircle2 className="w-3 h-3 text-green-400" />
    if (type.includes('error')) return <XCircle className="w-3 h-3 text-red-400" />
    return <FolderOpen className="w-3 h-3 text-slate-400" />
  }

  const vscodeEventIcon = (type: string): React.ReactNode => {
    if (type.includes('connected')) return <CheckCircle2 className="w-3 h-3 text-green-400" />
    if (type.includes('active_file_changed')) return <FileText className="w-3 h-3 text-violet-400" />
    if (type.includes('diagnostics_updated')) return <AlertTriangle className="w-3 h-3 text-yellow-400" />
    if (type.includes('git_status_refreshed')) return <GitBranch className="w-3 h-3 text-orange-400" />
    if (type.includes('disconnected')) return <XCircle className="w-3 h-3 text-red-400" />
    if (type.includes('error')) return <XCircle className="w-3 h-3 text-red-400" />
    return <FileText className="w-3 h-3 text-slate-400" />
  }

  const describeVSCodeEvent = (type: string): string => {
    const map: Record<string, string> = {
      'vscode.connected': 'VS Code connected',
      'vscode.active_file_changed': 'Active file changed',
      'vscode.diagnostics_updated': 'Diagnostics updated',
      'vscode.git_status_refreshed': 'Git status refreshed',
      'vscode.context_provided': 'Context provided to Executive Runtime',
      'vscode.disconnected': 'VS Code disconnected',
      'vscode.error': 'VS Code error'
    }
    return map[type] || type
  }

  const typeIcon = (type: string) => {
    if (type === 'execution') return <Play className="w-3 h-3" />
    if (type === 'workspace') return <FolderOpen className="w-3 h-3" />
    if (type === 'vscode') return <FileCode className="w-3 h-3" />
    if (type === 'plan') return <Activity className="w-3 h-3" />
    if (type === 'response') return <CheckCircle2 className="w-3 h-3" />
    return <Terminal className="w-3 h-3" />
  }

  const statusBadge = (status?: string) => {
    if (status === 'completed') return <span className="text-[10px] font-bold uppercase text-green-400">Completed</span>
    if (status === 'failed') return <span className="text-[10px] font-bold uppercase text-red-400">Failed</span>
    if (status === 'running') return <span className="text-[10px] font-bold uppercase text-blue-400">Running</span>
    return null
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
        <div>
          <h2 className="text-lg font-bold text-white tracking-wide">AUDIT TERMINAL</h2>
          <p className="text-xs text-slate-400 mt-1">Execution pipeline timeline</p>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-xs text-slate-400 cursor-pointer">
            <input type="checkbox" checked={autoScroll} onChange={(e) => setAutoScroll(e.target.checked)} className="rounded" />
            Auto-scroll
          </label>
          <Button variant="ghost" size="sm" onClick={loadHistory}>
            <RefreshCw className="w-3 h-3 mr-1" /> Refresh
          </Button>
        </div>
      </div>

      <div className="flex items-center gap-1 px-6 border-b border-white/5">
        <button className={tabClass('timeline')} onClick={() => setActiveTab('timeline')}>
          Timeline
        </button>
        <button className={tabClass('history')} onClick={() => setActiveTab('history')}>
          History ({history.length})
        </button>
        <button className={tabClass('workspace')} onClick={() => setActiveTab('workspace')}>
          Workspace
        </button>
        <button className={tabClass('vscode')} onClick={() => setActiveTab('vscode')}>
          VS Code
        </button>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {activeTab === 'timeline' && (
          <div className="flex-1 overflow-y-auto p-6 space-y-2" id="audit-scroll-timeline">
            {timeline.length === 0 && (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <Terminal className="w-12 h-12 mx-auto mb-4 text-slate-600" />
                  <p className="text-slate-400 text-sm">No executions yet</p>
                </div>
              </div>
            )}
            {timeline.map((entry) => {
              const isCollapsed = collapsedIds.has(entry.id)
              const colorClass = entry.type === 'plan' ? PLAN_COLOR :
                                 entry.type === 'response' ? RESPONSE_COLOR :
                                 entry.type === 'execution' ? getCapabilityColor(entry.title) :
                                 entry.type === 'workspace' ? WORKSPACE_COLOR :
                                 entry.type === 'vscode' ? VSCODE_COLOR : SYSTEM_COLOR
              return (
                <motion.div
                  key={entry.id}
                  initial={{ opacity: 0, y: 5 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`rounded-lg border-l-2 p-3 ${colorClass}`}
                >
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => entry.children && toggleCollapse(entry.id)}
                      className={`text-slate-400 hover:text-white ${entry.children ? 'cursor-pointer' : 'cursor-default opacity-0'}`}
                    >
                      {entry.children ? (isCollapsed ? <ChevronRight className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />) : <span className="w-3 h-3" />}
                    </button>
                    {typeIcon(entry.type)}
                    <span className="text-xs font-medium text-white">{entry.title}</span>
                    {statusBadge(entry.status)}
                    {entry.confidence !== undefined && (
                      <span className="text-[10px] font-mono text-green-400">{Math.round(entry.confidence * 100)}%</span>
                    )}
                    <span className="text-[10px] text-slate-500 ml-auto">{formatTime(entry.timestamp)}</span>
                    {entry.durationMs && (
                      <span className="text-[10px] font-mono text-slate-500">{formatDuration(entry.durationMs)}</span>
                    )}
                  </div>
                  {entry.description && !isCollapsed && (
                    <p className="text-[10px] text-slate-400 mt-1 ml-5 font-mono truncate">{entry.description}</p>
                  )}
                  {entry.evidence && entry.evidence.length > 0 && !isCollapsed && (
                    <div className="mt-1 ml-5 space-y-0.5">
                      {entry.evidence.slice(0, 3).map((ev, i) => (
                        <p key={i} className="text-[10px] text-slate-400">- {ev}</p>
                      ))}
                    </div>
                  )}
                  {entry.children && !isCollapsed && (
                    <div className="mt-2 ml-5 space-y-1 border-l border-white/5 pl-3">
                      {entry.children.map((child) => (
                        <div key={child.id} className="flex items-center gap-2 py-1">
                          <div className="w-1 h-1 rounded-full bg-slate-500" />
                          <span className="text-[10px] text-slate-300">{child.title}</span>
                          {child.durationMs && (
                            <span className="text-[10px] text-slate-500">{formatDuration(child.durationMs)}</span>
                          )}
                          {child.description && (
                            <span className="text-[10px] text-slate-500 truncate max-w-[200px]">{child.description}</span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </motion.div>
              )
            })}
          </div>
        )}

        {activeTab === 'history' && (
          <div className="flex-1 overflow-y-auto p-6 space-y-2">
            {history.length === 0 ? (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <Clock className="w-12 h-12 mx-auto mb-4 text-slate-600" />
                  <p className="text-slate-400 text-sm">No execution history</p>
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                {history.slice(0, 20).map((exec) => (
                  <button
                    key={exec.id}
                    onClick={() => setSelectedExec(exec)}
                    className={`w-full text-left p-3 rounded-lg border transition-colors ${selectedExec?.id === exec.id ? 'border-white/30 bg-white/10' : 'border-white/10 hover:border-white/20'}`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-mono text-white">{exec.capabilityId}</span>
                      <span className={`text-[10px] uppercase font-bold ${exec.status === 'completed' ? 'text-green-400' : exec.status === 'failed' ? 'text-red-400' : 'text-blue-400'}`}>
                        {exec.status}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-[10px] text-slate-500">
                      <span>{formatTime(exec.startedAt)}</span>
                      <span>{formatDuration(exec.durationMs)}</span>
                    </div>
                    {exec.input && (
                      <p className="text-[10px] text-slate-400 mt-1 font-mono truncate">
                        Input: {JSON.stringify(exec.input).slice(0, 100)}
                      </p>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'workspace' && (
          <div className="flex-1 flex flex-col overflow-hidden">
            <div className="flex-1 overflow-y-auto p-6 space-y-2" id="audit-scroll-workspace">
              {workspaceEvents.length === 0 ? (
                <div className="flex items-center justify-center h-full">
                  <div className="text-center">
                    <FolderOpen className="w-12 h-12 mx-auto mb-4 text-slate-600" />
                    <p className="text-slate-400 text-sm">Waiting for workspace events...</p>
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  {workspaceEvents.map((evt, i) => {
                    const readable = describeWorkspaceEvent(evt.type)
                    return (
                      <div key={`${evt.eventId}-${i}`} className={`flex items-start gap-3 p-3 rounded-lg border ${WORKSPACE_COLOR}`}>
                        <div className="mt-0.5">
                          {workspaceEventIcon(evt.type)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs font-medium text-emerald-300">{readable.label}</span>
                            <span className="text-[10px] text-slate-500">{new Date(evt.timestamp).toLocaleTimeString()}</span>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'vscode' && (
          <div className="flex-1 flex flex-col overflow-hidden">
            <div className="flex-1 overflow-y-auto p-6 space-y-2" id="audit-scroll-vscode">
              {vscodeEvents.length === 0 ? (
                <div className="flex items-center justify-center h-full">
                  <div className="text-center">
                    <FileText className="w-12 h-12 mx-auto mb-4 text-slate-600" />
                    <p className="text-slate-400 text-sm">Waiting for VS Code events...</p>
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  {vscodeEvents.map((evt, i) => {
                    const icon = vscodeEventIcon(evt.type)
                    const label = describeVSCodeEvent(evt.type)
                    const file = typeof evt.data?.file === 'string' ? evt.data.file : null
                    const branch = typeof evt.data?.branch === 'string' ? evt.data.branch : null
                    const count = typeof evt.data?.count === 'number' ? evt.data.count : null
                    return (
                      <div key={`${evt.type}-${i}`} className={`flex items-start gap-3 p-3 rounded-lg border ${VSCODE_COLOR}`}>
                        <div className="mt-0.5">{icon}</div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs font-medium text-violet-300">{label}</span>
                            <span className="text-[10px] text-slate-500">{new Date(evt.timestamp).toLocaleTimeString()}</span>
                          </div>
                          {file && (
                            <p className="text-[10px] font-mono text-slate-400 truncate">{file}</p>
                          )}
                          {branch && (
                            <p className="text-[10px] font-mono text-slate-400 truncate">Branch: {branch}</p>
                          )}
                          {count !== null && (
                            <p className="text-[10px] font-mono text-slate-400">Count: {count}</p>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
