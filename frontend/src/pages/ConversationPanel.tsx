import { useState, useEffect, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  MessageSquare, Bot, User, Loader2, Copy, Check,
  Play, Mic, FolderOpen, Clock, CheckCircle2, XCircle,
  ChevronRight, FileText, Search, Globe, Cpu, HardDrive,
  FileCode, ExternalLink, Eye
} from 'lucide-react'
import { desktop } from '@/desktop/desktop-bridge'
import { Button } from '@/components/ui/Button'
import { Markdown } from '@/components/common/Markdown'
import { useWorkspaceContextStore } from '@/stores/workspaceContextStore'
import {
  buildContextPill,
  type WorkspaceSnapshot,
} from '@/lib/workspaceConversation'

type ExecutiveState = 'idle' | 'thinking' | 'planning' | 'searching' | 'reading' | 'generating' | 'done' | 'error'

interface ExecutiveSnapshot {
  state?: { currentIntent?: string; focus?: string }
  intent?: { decision?: string }
  goal?: string
  steps?: Array<{ description: string; capabilityId?: string; status?: string }>
}

interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: number
  workspaceContext?: WorkspaceSnapshot
  confidence?: number
  evidence?: string[]
  durationMs?: number
  capabilities?: string[]
  executionTimeline?: ExecutionTimelineEntry[]
  referencedFiles?: ReferencedFile[]
}

interface ExecutionTimelineEntry {
  id: string
  step: string
  capabilityId?: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  durationMs?: number
  output?: any
  error?: string
}

interface ReferencedFile {
  path: string
  name: string
  preview?: string
}

const EXECUTIVE_STATE_COPY: Record<string, ExecutiveState> = {
  idle: 'idle',
  thinking: 'thinking',
  planning: 'planning',
  searching: 'searching',
  reading: 'reading',
  generating: 'generating',
  done: 'done',
  error: 'error',
}

function mapExecutiveState(snap: ExecutiveSnapshot | null): ExecutiveState {
  if (!snap) return 'idle'
  const intent = (snap.intent?.decision || '').toLowerCase()
  const focus = (snap.state?.focus || '').toLowerCase()
  if (intent.includes('error') || focus.includes('error')) return 'error'
  if (focus.includes('search') || intent.includes('search')) return 'searching'
  if (focus.includes('read') || intent.includes('read')) return 'reading'
  if (focus.includes('plan') || intent.includes('plan')) return 'planning'
  if (focus.includes('generate') || intent.includes('generate') || focus.includes('respond')) return 'generating'
  if (focus.includes('think') || intent.includes('think')) return 'thinking'
  if (snap.goal && snap.steps && snap.steps.length > 0) {
    const allDone = snap.steps.every(s => s.status === 'completed')
    if (allDone) return 'done'
  }
  return 'thinking'
}

function executiveStateLabel(state: ExecutiveState): string {
  switch (state) {
    case 'thinking': return 'Thinking...'
    case 'planning': return 'Planning...'
    case 'searching': return 'Searching Workspace...'
    case 'reading': return 'Reading Files...'
    case 'generating': return 'Generating Response...'
    case 'done': return 'Done'
    case 'error': return 'Error'
    default: return 'Ready'
  }
}

function buildOrchestratedResponse(query: string, results: any[], confidence: number, evidence: string[], durationMs: number): string {
  const lines: string[] = []
  lines.push(`**Goal:** ${query}`)
  lines.push('')
  lines.push('**Plan:**')
  for (const result of results) {
    if (result.error) {
      lines.push(`- ✗ ${result.step}: ${result.error}`)
    } else {
      lines.push(`- ✓ ${result.step}`)
    }
  }
  lines.push('')
  lines.push('**Execution**')
  for (const result of results) {
    if (result.output) {
      const outputStr = typeof result.output === 'string' ? result.output : JSON.stringify(result.output)
      lines.push(`\`\`\`${outputStr.slice(0, 500)}\`\`\``)
    }
  }
  lines.push('')
  lines.push('**Completed**')
  lines.push('')
  lines.push(`**Confidence:** ${Math.round(confidence * 100)}%`)
  lines.push('')
  lines.push(`**Finished in:** ${durationMs}ms`)
  if (evidence.length > 0) {
    lines.push('')
    lines.push('**Evidence**')
    for (const item of evidence) {
      lines.push(`- ${item}`)
    }
  }
  return lines.join('\n')
}

function extractFileReferences(text: string): ReferencedFile[] {
  const patterns = [
    /(?:package\.json|tsconfig\.json|\.tsx?|\.jsx?|\.py|\.rs|\.go|\.java|\.c(?:pp)?|\.h|\.cs|\.rb|\.php|\.swift|\.kt|\.scala|\.sql|\.sh|\.yaml|\.yml|\.toml|\.xml|\.html|\.css|\.scss|\.md)/g,
    /(?:\.\/[^\s]+|\/[^\s]+)/g,
  ]
  const files = new Map<string, string>()
  for (const pattern of patterns) {
    const matches = text.match(pattern)
    if (matches) matches.forEach(m => files.set(m, m.split('/').pop() || m))
  }
  return Array.from(files.entries()).slice(0, 10).map(([path, name]) => ({ path, name }))
}

export function ConversationPanel() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [executiveState, setExecutiveState] = useState<ExecutiveSnapshot | null>(null)
  const [mappedState, setMappedState] = useState<ExecutiveState>('idle')
  const [isListening, setIsListening] = useState(false)
  const [currentTimeline, setCurrentTimeline] = useState<ExecutionTimelineEntry[]>([])
  const [activeCapabilities, setActiveCapabilities] = useState<string[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const timelineRef = useRef<HTMLDivElement>(null)

  const snapshot = useWorkspaceContextStore((s) => s.snapshot)
  const indexing = useWorkspaceContextStore((s) => s.indexing)
  const subscribeToWorkspace = useWorkspaceContextStore((s) => s.subscribeToWorkspace)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, currentTimeline])

  useEffect(() => {
    timelineRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [currentTimeline])

  useEffect(() => {
    const unsub = desktop.executive.onSnapshot((snap: any) => {
      setExecutiveState(snap)
      setMappedState(mapExecutiveState(snap))
    })
    const unsubWorkspace = subscribeToWorkspace()
    const unsubExec = desktop.execution.onEvent((evt: any) => {
      if (evt.event_type === 'execution.completed' || evt.event_type === 'execution.failed' || evt.event_type === 'execution.running') {
        setCurrentTimeline(prev => {
          const next = [...prev]
          const idx = next.findIndex(t => t.id === evt.data?.executionId)
          if (idx >= 0) {
            next[idx] = {
              ...next[idx],
              status: evt.event_type === 'execution.completed' ? 'completed' : evt.event_type === 'execution.failed' ? 'failed' : 'running',
              durationMs: evt.data?.durationMs,
              output: evt.data?.output,
              error: evt.data?.error?.message,
            }
          }
          return next
        })
      }
    })
    return () => {
      unsub()
      unsubWorkspace()
      unsubExec()
    }
  }, [subscribeToWorkspace])

  const waitForExecution = useCallback(async (executionId: string, timelineId: string): Promise<any> => {
    return new Promise((resolve, reject) => {
      const startTime = Date.now()
      const unsub = desktop.execution.onEvent((evt: any) => {
        if (evt.executionId === executionId) {
          const durationMs = Date.now() - startTime
          setCurrentTimeline(prev => prev.map(t =>
            t.id === timelineId
              ? { ...t, status: evt.status === 'completed' ? 'completed' : evt.status === 'failed' ? 'failed' : 'running', durationMs }
              : t
          ))
          if (evt.status === 'completed' || evt.status === 'failed' || evt.status === 'cancelled') {
            unsub()
            resolve(evt)
          }
        }
      })

      desktop.execution.getExecution(executionId).then((status: any) => {
        if (status && (status.status === 'completed' || status.status === 'failed' || status.status === 'cancelled')) {
          unsub()
          resolve(status)
        }
      }).catch(() => {
        // wait for event
      })
    })
  }, [])

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return
    const text = input.trim()
    setInput('')
    setIsLoading(true)
    const startTime = Date.now()
    const timeline: ExecutionTimelineEntry[] = []

    setMessages(prev => [...prev, { id: `u-${Date.now()}`, role: 'user', content: text, timestamp: Date.now() }])
    setCurrentTimeline([])
    setActiveCapabilities([])

    const currentSnapshot = useWorkspaceContextStore.getState().snapshot
    const usedCapabilities: string[] = []

    try {
      const plan = await desktop.executive.plan(text)
      if (!plan || !plan.steps || plan.steps.length === 0) {
        throw new Error('Executive Runtime did not return a plan')
      }

      timeline.push({
        id: 'plan',
        step: `Goal: ${plan.goal || text}`,
        status: 'completed',
        durationMs: 0,
      })

      const results: any[] = []
      for (const step of plan.steps) {
        const timelineId = `step-${step.id || Date.now()}-${Math.random().toString(36).slice(2, 7)}`
        timeline.push({
          id: timelineId,
          step: step.description || step.capabilityId,
          capabilityId: step.capabilityId,
          status: 'running',
        })
        setCurrentTimeline([...timeline])
        setActiveCapabilities(prev => step.capabilityId ? [...prev, step.capabilityId] : prev)

        try {
          const execResult = await desktop.execution.execute(step.capabilityId, step.input || {})
          if (execResult && execResult.id) {
            const status = await waitForExecution(execResult.id, timelineId)
            if (status.status === 'completed') {
              results.push({ step: step.description, output: status.output })
              if (step.capabilityId) usedCapabilities.push(step.capabilityId)
              const idx = timeline.findIndex(t => t.id === timelineId)
              if (idx >= 0) {
                timeline[idx] = { ...timeline[idx], status: 'completed', output: status.output }
              }
            } else if (status.status === 'failed') {
              results.push({ step: step.description, error: status.error?.message || 'Failed' })
              const idx = timeline.findIndex(t => t.id === timelineId)
              if (idx >= 0) {
                timeline[idx] = { ...timeline[idx], status: 'failed', error: status.error?.message }
              }
            }
          }
        } catch (err) {
          results.push({ step: step.description, error: err instanceof Error ? err.message : String(err) })
          const idx = timeline.findIndex(t => t.id === timelineId)
          if (idx >= 0) {
            timeline[idx] = { ...timeline[idx], status: 'failed', error: err instanceof Error ? err.message : String(err) }
          }
        }
        setCurrentTimeline([...timeline])
        setActiveCapabilities(prev => step.capabilityId ? prev.filter(c => c !== step.capabilityId) : prev)
      }

      const confidence = await desktop.executive.getConfidence()
      const evidence = await desktop.executive.getEvidence()
      const durationMs = Date.now() - startTime
      const response = buildOrchestratedResponse(text, results, confidence, evidence, durationMs)
      const referencedFiles = extractFileReferences(response)

      timeline.push({
        id: 'response',
        step: 'Response Generated',
        status: 'completed',
        durationMs,
      })
      setCurrentTimeline([...timeline])

      setMessages(prev => [...prev, {
        id: `a-${Date.now()}`,
        role: 'assistant',
        content: response,
        timestamp: Date.now(),
        workspaceContext: currentSnapshot ?? undefined,
        confidence,
        evidence,
        durationMs,
        capabilities: usedCapabilities,
        executionTimeline: timeline,
        referencedFiles,
      }])
    } catch (err) {
      setMessages(prev => [...prev, {
        id: `a-${Date.now()}`,
        role: 'assistant',
        content: `Error: ${err instanceof Error ? err.message : String(err)}`,
        timestamp: Date.now(),
      }])
    } finally {
      setIsLoading(false)
      setCurrentTimeline([])
      setActiveCapabilities([])
    }
  }

  const handleVoice = async () => {
    if (isListening) {
      setIsListening(false)
      return
    }
    setIsListening(true)
    if (desktop.dialog?.showOpen) {
      try {
        const files = await desktop.dialog.showOpen()
        if (files && Array.isArray(files) && files.length > 0) {
          setInput(prev => prev + ' ' + files[0])
        }
      } catch {
        // ignore
      }
    }
    setIsListening(false)
  }

  const copyToClipboard = async (text: string) => {
    if (desktop.clipboard?.writeText) {
      await desktop.clipboard.writeText(text)
    }
  }

  const openFilePreview = async (filePath: string) => {
    const content = await desktop.execution.execute('filesystem.read', { path: filePath })
    if (content && content.output) {
      setMessages(prev => {
        const lastAssistant = [...prev].reverse().find(m => m.role === 'assistant')
        if (!lastAssistant) return prev
        return prev.map(msg =>
          msg.id === lastAssistant.id
            ? { ...msg, referencedFiles: [...(msg.referencedFiles || []), { path: filePath, name: filePath.split('/').pop() || filePath, preview: typeof content.output === 'string' ? content.output : JSON.stringify(content.output, null, 2) }] }
            : msg
        )
      })
    }
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
        <div>
          <h2 className="text-lg font-bold text-white tracking-wide">CONVERSATION</h2>
          <p className="text-xs text-slate-400 mt-1">Connected to Executive Runtime</p>
        </div>
        <div className="flex items-center gap-2">
          {isLoading && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-mono border border-blue-400/30 bg-blue-400/5 text-blue-300">
              <Loader2 className="w-3 h-3 animate-spin" />
              <span>{executiveStateLabel(mappedState)}</span>
            </div>
          )}
          {!isLoading && mappedState !== 'idle' && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-mono border border-white/10 text-slate-300">
              <span>{executiveStateLabel(mappedState)}</span>
            </div>
          )}
          {snapshot && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs border border-cyan-400/30 bg-cyan-400/5 text-cyan-300">
              <FolderOpen className="w-3 h-3" />
              <span className="font-medium">{snapshot.workspace}</span>
              <span className="text-slate-400">|</span>
              <span>{buildContextPill(snapshot)}</span>
            </div>
          )}
          {indexing && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs border border-blue-400/30 bg-blue-400/5 text-blue-300">
              <Loader2 className="w-3 h-3 animate-spin" />
              <span>Indexing workspace...</span>
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <MessageSquare className="w-12 h-12 mx-auto mb-4 text-slate-600" />
              <p className="text-slate-400 text-sm">Start a conversation with the Executive Runtime</p>
              <p className="text-slate-500 text-xs mt-2">All responses come from the real runtime pipeline</p>
            </div>
          </div>
        )}
        <AnimatePresence>
          {messages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {msg.role === 'assistant' && (
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-orange-500 flex items-center justify-center flex-shrink-0">
                  <Bot className="w-4 h-4 text-white" />
                </div>
              )}
              <div className={`flex flex-col gap-1.5 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                {msg.workspaceContext && (
                  <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] border border-cyan-400/20 bg-cyan-400/5 text-cyan-300/90">
                    <span>📁</span>
                    <span className="font-medium">Workspace</span>
                    <span className="text-slate-400">|</span>
                    <span>{buildContextPill(msg.workspaceContext)}</span>
                    <span className="text-slate-400">|</span>
                    <span className="text-cyan-400/80">Confidence {msg.workspaceContext.confidence}%</span>
                  </div>
                )}
                {msg.capabilities && msg.capabilities.length > 0 && (
                  <div className="flex items-center gap-1.5">
                    {msg.capabilities.map((cap) => (
                      <span key={cap} className="px-2 py-0.5 rounded-full text-[10px] font-mono border border-white/10 bg-white/5 text-slate-300">
                        {cap}
                      </span>
                    ))}
                  </div>
                )}
                {msg.executionTimeline && msg.executionTimeline.length > 0 && (
                  <div className="space-y-1 max-w-[80%]">
                    {msg.executionTimeline.map((entry, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs p-2 rounded-lg bg-white/5 border border-white/10">
                        <div className={`w-1.5 h-1.5 rounded-full ${
                          entry.status === 'completed' ? 'bg-green-400' :
                          entry.status === 'failed' ? 'bg-red-400' :
                          entry.status === 'running' ? 'bg-blue-400 animate-pulse' : 'bg-slate-500'
                        }`} />
                        <span className="text-slate-300 flex-1">{entry.step}</span>
                        {entry.durationMs && (
                          <span className="text-[10px] text-slate-500 font-mono">{entry.durationMs}ms</span>
                        )}
                        {entry.status === 'completed' && <CheckCircle2 className="w-3 h-3 text-green-400" />}
                        {entry.status === 'failed' && <XCircle className="w-3 h-3 text-red-400" />}
                      </div>
                    ))}
                  </div>
                )}
                <div className={`max-w-[80%] rounded-2xl p-4 ${msg.role === 'user' ? 'bg-white/10' : 'bg-black/40 border border-white/10'}`}>
                  {msg.role === 'assistant' ? (
                    <Markdown content={msg.content} />
                  ) : (
                    <p className="text-sm text-slate-200 whitespace-pre-wrap">{msg.content}</p>
                  )}
                  {msg.referencedFiles && msg.referencedFiles.length > 0 && (
                    <div className="mt-3 space-y-1">
                      {msg.referencedFiles.map((file, i) => (
                        <button
                          key={i}
                          onClick={() => openFilePreview(file.path)}
                          className="flex items-center gap-2 px-2 py-1 rounded-lg text-xs bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300 transition-colors"
                        >
                          <FileText className="w-3 h-3" />
                          <span className="font-mono truncate max-w-[200px]">{file.name}</span>
                          <Eye className="w-3 h-3 ml-auto" />
                        </button>
                      ))}
                    </div>
                  )}
                  <div className="flex items-center gap-3 mt-2">
                    <p className="text-[10px] text-slate-500">
                      {new Date(msg.timestamp).toLocaleTimeString()}
                    </p>
                    {msg.durationMs !== undefined && (
                      <p className="text-[10px] text-slate-500 flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        Finished in {msg.durationMs}ms
                      </p>
                    )}
                    {msg.confidence !== undefined && (
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-green-400/10 text-green-400 border border-green-400/20">
                        Confidence {Math.round(msg.confidence * 100)}%
                      </span>
                    )}
                    {msg.evidence && msg.evidence.length > 0 && (
                      <span className="text-[10px] text-slate-500">
                        Evidence: {msg.evidence.length} sources
                      </span>
                    )}
                  </div>
                </div>
                {msg.role === 'user' && (
                  <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center flex-shrink-0">
                    <User className="w-4 h-4 text-white" />
                  </div>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        {isLoading && currentTimeline.length > 0 && (
          <div className="space-y-1 max-w-[80%]">
            {currentTimeline.map((entry) => (
              <div key={entry.id} className="flex items-center gap-2 text-xs p-2 rounded-lg bg-white/5 border border-white/10">
                <div className={`w-1.5 h-1.5 rounded-full ${
                  entry.status === 'completed' ? 'bg-green-400' :
                  entry.status === 'failed' ? 'bg-red-400' :
                  entry.status === 'running' ? 'bg-blue-400 animate-pulse' : 'bg-slate-500'
                }`} />
                <span className="text-slate-300 flex-1">{entry.step}</span>
                {entry.durationMs && (
                  <span className="text-[10px] text-slate-500 font-mono">{entry.durationMs}ms</span>
                )}
                {entry.status === 'completed' && <CheckCircle2 className="w-3 h-3 text-green-400" />}
                {entry.status === 'failed' && <XCircle className="w-3 h-3 text-red-400" />}
              </div>
            ))}
            <div ref={timelineRef} />
          </div>
        )}
        {isLoading && currentTimeline.length === 0 && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-3 justify-start">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-orange-500 flex items-center justify-center flex-shrink-0">
              <Bot className="w-4 h-4 text-white" />
            </div>
            <div className="rounded-2xl p-4 bg-black/40 border border-white/10 flex items-center gap-2">
              <motion.div
                animate={{ opacity: [0.4, 1, 0.4] }}
                transition={{ duration: 1.5, repeat: Infinity }}
              >
                <Loader2 className="w-4 h-4 animate-spin text-cyan-400" />
              </motion.div>
              <span className="text-sm text-white/60">{executiveStateLabel(mappedState)}</span>
            </div>
          </motion.div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {activeCapabilities.length > 0 && (
        <div className="px-6 py-2 border-t border-white/5 bg-black/20">
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-slate-500 uppercase tracking-wider">Active:</span>
            {activeCapabilities.map((cap) => (
              <span key={cap} className="px-2 py-0.5 rounded-full text-[10px] font-mono border border-blue-400/30 bg-blue-400/5 text-blue-300 animate-pulse">
                {cap}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="px-6 py-4 border-t border-white/5">
        <div className="max-w-4xl mx-auto">
          <div className="glass rounded-2xl p-2 flex items-center gap-2 border border-white/10">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  sendMessage()
                }
              }}
              placeholder="Send to Executive Runtime..."
              className="flex-1 bg-transparent outline-none text-sm text-white px-4"
            />
            <button
              onClick={handleVoice}
              className={`p-2 rounded-lg transition-colors ${isListening ? 'bg-red-500/20 text-red-400' : 'text-slate-400 hover:text-white'}`}
            >
              <Mic className="w-4 h-4" />
            </button>
            <Button onClick={sendMessage} disabled={!input.trim() || isLoading}>
              <Play className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
