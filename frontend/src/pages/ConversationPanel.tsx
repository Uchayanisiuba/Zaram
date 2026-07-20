import { useState, useEffect, useCallback, useRef } from 'react'
import {
  MessageSquare, Bot, User, Loader2, Copy,
  Play, Mic, FolderOpen, RefreshCw,
  ImagePlus, Camera, Monitor, X, Paperclip, ThumbsUp, ThumbsDown,
  Wifi, WifiOff
} from 'lucide-react'
import { desktop } from '@/desktop/desktop-bridge'
import { Button } from '@/components/ui/Button'
import { OrbEngine } from '@/components/OrbEngine/OrbEngine'
import { ResizablePanels, PresenceCanvas, ConversationFeed, ConversationInput } from '@/components/conversation'
import { useWorkspaceContextStore } from '@/stores/workspaceContextStore'
import { useZaram } from '@/hooks/useZaram'
import {
  buildContextPill,
  type WorkspaceSnapshot,
} from '@/lib/workspaceConversation'

export type ExecutiveState = 'idle' | 'thinking' | 'planning' | 'searching' | 'reading' | 'generating' | 'done' | 'error' | 'searchingInternet'

export interface ExecutiveSnapshot {
  state?: { currentIntent?: string; focus?: string }
  intent?: { decision?: string }
  goal?: string
  steps?: Array<{ description: string; capabilityId?: string; status?: string }>
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
  error?: boolean
  workspaceContext?: WorkspaceSnapshot
  referencedFiles?: Array<{ path: string; name: string; preview?: string }>
}

interface ExecutionTimelineEntry {
  id: string
  step: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  capabilityId?: string
  output?: unknown
  error?: string
  durationMs?: number
}

interface CapabilitySnapshot {
  total: number
  enabled: number
  byCategory: Record<string, number>
  capabilities: Array<{
    id: string
    name: string
    category: string
    availability: string
    latencyEstimateMs: number
  }>
}

function mapExecutiveState(snap: ExecutiveSnapshot | null): ExecutiveState {
  if (!snap) return 'idle'
  const intent = (snap.intent?.decision || '').toLowerCase()
  const focus = (snap.state?.focus || '').toLowerCase()
  if (intent.includes('error') || focus.includes('error')) return 'error'
  if (focus.includes('internet') || intent.includes('internet') || focus.includes('knowledge') || intent.includes('knowledge')) return 'searchingInternet'
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
    case 'searching': return 'Searching...'
    case 'searchingInternet': return 'Searching Internet...'
    case 'reading': return 'Reading Files...'
    case 'generating': return 'Generating Response...'
    case 'done': return 'Done'
    case 'error': return 'Error'
    default: return 'Ready'
  }
}

function extractFileReferences(text: string): Array<{ path: string; name: string }> {
  const refs: Array<{ path: string; name: string }> = []
  const regex = /(?:file:|path:)\s*([^\s]+(?:\.[a-zA-Z0-9]+)?)/g
  let match
  while ((match = regex.exec(text)) !== null) {
    refs.push({ path: match[1], name: match[1].split('/').pop() || match[1] })
  }
  return refs
}

export function ConversationPanel() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [executiveState, setExecutiveState] = useState<ExecutiveSnapshot | null>(null)
  const [mappedState, setMappedState] = useState<ExecutiveState>('idle')
  const [isListening, setIsListening] = useState(false)
  const [attachedImages, setAttachedImages] = useState<string[]>([])
  const [showAttachmentMenu, setShowAttachmentMenu] = useState(false)
  const [capabilitySnapshot, setCapabilitySnapshot] = useState<CapabilitySnapshot | null>(null)
  const [backendStatus, setBackendStatus] = useState<{ running: boolean; error?: string } | null>(null)
  const [backendRetrying, setBackendRetrying] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const snapshot = useWorkspaceContextStore((s) => s.snapshot)
  const indexing = useWorkspaceContextStore((s) => s.indexing)
  const subscribeToWorkspace = useWorkspaceContextStore((s) => s.subscribeToWorkspace)

  const { selectedCharacter, selectedModel } = useZaram()

  useEffect(() => {
    let mounted = true
    const checkBackend = async () => {
      try {
        const status = await desktop.backend.getStatus()
        if (mounted) setBackendStatus(status)
      } catch {
        // ignore
      }
    }
    checkBackend()
    const interval = setInterval(checkBackend, 3000)
    return () => {
      mounted = false
      clearInterval(interval)
    }
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    const unsub = desktop.executive.onSnapshot((snap: any) => {
      setExecutiveState(snap)
      setMappedState(mapExecutiveState(snap))
    })
    const unsubWorkspace = subscribeToWorkspace()
    return () => {
      unsub()
      unsubWorkspace()
    }
  }, [subscribeToWorkspace])

  useEffect(() => {
    const loadCapabilities = async () => {
      try {
        const caps = await desktop.capability.getSnapshot()
        setCapabilitySnapshot(caps)
      } catch {
        // ignore
      }
    }
    loadCapabilities()
    const interval = setInterval(loadCapabilities, 5000)
    return () => clearInterval(interval)
  }, [])

  const waitForExecution = useCallback(async (executionId: string, timelineId: string): Promise<any> => {
    return new Promise((resolve, reject) => {
      const startTime = Date.now()
      console.log('[IPC] waitForExecution started for:', executionId)
      const unsub = desktop.execution.onEvent((evt: any) => {
        const eventExecutionId = evt?.data?.executionId
        console.log('[IPC] Event received in waitForExecution, eventExecutionId:', eventExecutionId, 'looking for:', executionId, 'match:', eventExecutionId === executionId)
        if (eventExecutionId === executionId) {
          const durationMs = Date.now() - startTime
          const eventStatus = evt?.data?.status
          if (eventStatus === 'completed' || eventStatus === 'failed' || eventStatus === 'cancelled') {
            unsub()
            resolve({
              status: evt.data.status,
              output: evt.data.output,
              error: evt.data.error,
              durationMs: evt.data.durationMs,
            })
          }
        }
      })

      desktop.execution.getExecution(executionId).then((execResult: any) => {
        if (execResult && (execResult.status === 'completed' || execResult.status === 'failed' || execResult.status === 'cancelled')) {
          unsub()
          resolve({
            status: execResult.status,
            output: execResult.output,
            error: execResult.error,
            durationMs: execResult.durationMs,
          })
        }
      }).catch(() => {
        // execution may not exist yet, wait for event
      })

      setTimeout(() => {
        if (Date.now() - startTime > 30000) {
          unsub()
          reject(new Error('Execution timeout'))
        }
      }, 30000)
    })
  }, [])

  const sendMessage = async (overrideText?: string) => {
    const text = (overrideText || input).trim()
    if (!text || isLoading) return
    setInput('')
    setIsLoading(true)
    const startTime = Date.now()
    const timeline: ExecutionTimelineEntry[] = []

    console.log('[STAGE-1][UI] sendMessage:', text)

    setMessages(prev => [...prev, { id: `u-${Date.now()}`, role: 'user', content: text, timestamp: Date.now() }])

    const currentSnapshot = useWorkspaceContextStore.getState().snapshot
    const usedCapabilities: string[] = []

    try {
      if (!backendStatus?.running) {
        throw new Error('Backend unavailable — cannot process conversation. Please ensure the backend is running.')
      }

      console.log('[STAGE-2][IPC] Calling desktop.executive.plan()')
      const plan = await desktop.executive.plan(text, { persona: selectedCharacter, model: selectedModel })
      console.log('[STAGE-3][Runtime] Executive plan received:', plan)
      if (!plan || !plan.steps || plan.steps.length === 0) {
        throw new Error('Runtime did not return a plan')
      }

      const results: any[] = []
      const stepOutputs = new Map<string, any>()
      for (const step of plan.steps) {
        const timelineId = `step-${step.id || Date.now()}-${Math.random().toString(36).slice(2, 7)}`
        timeline.push({
          id: timelineId,
          step: step.description || step.capabilityId,
          capabilityId: step.capabilityId,
          status: 'running',
        })

        try {
          console.log('[STAGE-4][IPC] Calling desktop.execution.execute:', step.capabilityId)
          let stepInput = step.input || {}
          if (step.capabilityId.startsWith('vision.') && attachedImages.length > 0) {
            stepInput = {
              ...stepInput,
              image: attachedImages[0],
              images: attachedImages
            }
          }
          if (step.capabilityId === 'reasoning.generate') {
            const prior = stepOutputs.get('knowledge.search')
            if (prior) {
              const searchContext = typeof prior === 'string' ? prior : JSON.stringify(prior)
              stepInput = {
                ...stepInput,
                prompt: `${stepInput.prompt || ''}\n\nSearch results:\n${searchContext}`
              }
            }
          }
          const execResult = await desktop.execution.execute(step.capabilityId, stepInput)
          console.log('[STAGE-5][IPC] Execution started, result:', execResult)
          if (execResult && execResult.id) {
            const status = await waitForExecution(execResult.id, timelineId)
            console.log('[STAGE-6][IPC] Execution completed, status:', status)
             if (status.status === 'completed') {
               const rawOutput = status.output
               let assistantText = ''
               if (typeof rawOutput === 'string') {
                 assistantText = rawOutput
               } else if (rawOutput && typeof rawOutput.response === 'string') {
                 assistantText = rawOutput.response
               } else if (rawOutput && typeof rawOutput === 'object') {
                 assistantText = JSON.stringify(rawOutput)
               }
               results.push({ step: step.description, output: rawOutput })
               if (step.capabilityId) {
                 usedCapabilities.push(step.capabilityId)
                 stepOutputs.set(step.capabilityId, rawOutput)
               }
               const idx = timeline.findIndex(t => t.id === timelineId)
               if (idx >= 0) {
                 timeline[idx] = { ...timeline[idx], status: 'completed', output: rawOutput }
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
      }

      const successfulResult = results.find(r => !r.error && r.output && (typeof r.output === 'string' || r.output.response))
      const assistantText = successfulResult
        ? (typeof successfulResult.output === 'string' ? successfulResult.output : successfulResult.output.response || '')
        : results.map(r => r.error || JSON.stringify(r.output)).join('\n') || 'No response generated'
      const referencedFiles = extractFileReferences(assistantText)

      console.log('[STAGE-7][Renderer] Appending assistant message, length:', assistantText.length)
      setMessages(prev => [...prev, {
        id: `a-${Date.now()}`,
        role: 'assistant',
        content: assistantText,
        timestamp: Date.now(),
        referencedFiles,
      }])
      console.log('[STAGE-8][Renderer] Assistant message appended')
    } catch {
      setMessages(prev => [...prev, {
        id: `a-${Date.now()}`,
        role: 'assistant',
        content: `Something went wrong. Please try again.`,
        timestamp: Date.now(),
        error: true,
      }])
    } finally {
      setIsLoading(false)
      setAttachedImages([])
    }
  }

  const chooseWorkspace = async () => {
    try {
      const root = await desktop.dialog?.selectDirectory?.()
      if (root) {
        await desktop.workspace?.setRootPath?.(root)
      }
    } catch {
      // ignore
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
        const result = await desktop.dialog.showOpen()
        const filePaths = result?.filePaths || []
        if (filePaths.length > 0) {
          setInput(prev => prev + ' ' + filePaths[0])
        }
      } catch {
        // ignore
      }
    }
    setIsListening(false)
  }

  const retryBackend = async () => {
    setBackendRetrying(true)
    try {
      const status = await desktop.backend.getStatus()
      setBackendStatus(status)
    } catch {
      // ignore
    } finally {
      setBackendRetrying(false)
    }
  }

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return
    
    for (const file of files) {
      const reader = new FileReader()
      reader.onload = () => {
        const base64 = reader.result as string
        setAttachedImages(prev => [...prev, base64])
      }
      reader.readAsDataURL(file)
    }
    
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const handleScreenCapture = async () => {
    setShowAttachmentMenu(false)
    try {
      const sources = await desktop.runtime?.desktopGetSources?.({ types: ['window', 'screen'] })
      if (!sources || sources.length === 0) return
      
      const selected = sources[0]
      if (selected.thumbnail) {
        setAttachedImages(prev => [...prev, selected.thumbnail])
      }
    } catch {
      // ignore screen capture errors
    }
  }

  const handleCameraCapture = async () => {
    setShowAttachmentMenu(false)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } })
      const video = document.createElement('video')
      video.srcObject = stream
      video.play()
      
      await new Promise((resolve) => {
        video.onloadedmetadata = () => {
          setTimeout(resolve, 500)
        }
      })
      
      const canvas = document.createElement('canvas')
      canvas.width = video.videoWidth
      canvas.height = video.videoHeight
      const ctx = canvas.getContext('2d')
      ctx?.drawImage(video, 0, 0)
      
      const tracks = stream.getTracks()
      tracks.forEach(track => track.stop())
      
      const base64 = canvas.toDataURL('image/png')
      setAttachedImages(prev => [...prev, base64])
    } catch {
      // ignore camera errors
    }
  }

  const handleClipboardPaste = async () => {
    setShowAttachmentMenu(false)
    try {
      const text = await navigator.clipboard.readText()
      setInput(prev => prev + text)
    } catch {
      // ignore clipboard errors
    }
  }

  const removeImage = (index: number) => {
    setAttachedImages(prev => prev.filter((_, i) => i !== index))
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

  const noWorkspace = !snapshot || !snapshot.workspace || snapshot.workspace === 'root' || snapshot.projects === 0

  const backendBanner = () => {
    if (backendStatus?.running) return null
    if (!backendStatus) return null
    
    return (
      <div className="fixed bottom-4 right-4 z-50">
        <div className="flex items-center gap-2 px-4 py-2 bg-red-500/10 border border-red-500/20 text-red-400 text-xs rounded-lg backdrop-blur-sm">
          <WifiOff className="w-3.5 h-3.5" />
          <span>Connection unavailable</span>
          <Button variant="ghost" size="sm" onClick={retryBackend} className="ml-2 h-6 px-2 text-xs">
            Retry
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      {backendBanner()}

      {/* Project Pill */}
      <div className="flex items-center justify-center px-6 py-3 border-b border-white/5">
        {!noWorkspace && snapshot ? (
          <div className="flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs border border-white/10 bg-white/5 text-slate-300">
            <FolderOpen className="w-3.5 h-3.5 text-cyan-400" />
            <span className="font-medium text-white">{snapshot.workspace}</span>
            <span className="text-slate-500">|</span>
            <span>{buildContextPill(snapshot)}</span>
            {snapshot.confidence > 0 && (
              <>
                <span className="text-slate-500">|</span>
                <span className="text-cyan-400/80">{snapshot.confidence}% match</span>
              </>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">Open a project to enable workspace context</span>
          </div>
        )}
        {indexing && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs border border-blue-400/30 bg-blue-400/5 text-blue-300 ml-3">
            <Loader2 className="w-3 h-3 animate-spin" />
            <span>Indexing...</span>
          </div>
        )}
      </div>

      {/* Main Content: Resizable Three-Panel Layout */}
      <div className="flex-1 flex min-h-0">
        <ResizablePanels
          defaultSizes={{ sidebar: 15, canvas: 55, conversation: 30 }}
          minWidths={{ sidebar: 220, canvas: 500, conversation: 350 }}
        >
          {/* Left Connections Panel */}
          <div className="h-full flex flex-col border-r border-white/5 overflow-hidden">
            <div className="p-4 border-b border-white/5">
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Connections</h3>
            </div>
            <div className="flex-1 overflow-y-auto p-3 space-y-1">
              <ConnectionItem icon="📁" label="Projects" onClick={() => {}} />
              <ConnectionItem icon="🌐" label="Browser" onClick={() => {}} />
              <ConnectionItem icon="📄" label="Documents" onClick={() => {}} />
              <div className="h-px bg-white/5 my-2" />
              <ConnectionItem icon="📧" label="Email" onClick={() => {}} />
              <ConnectionItem icon="📅" label="Calendar" onClick={() => {}} />
              <ConnectionItem icon="📰" label="RSS" onClick={() => {}} />
              <div className="h-px bg-white/5 my-2" />
              <ConnectionItem icon="📷" label="Camera" onClick={() => {}} />
              <ConnectionItem icon="🖥" label="Screen Share" onClick={() => {}} />
              <div className="h-px bg-white/5 my-2" />
              <ConnectionItem icon="⚡" label="Automation" onClick={() => {}} />
            </div>
          </div>

          {/* Center: Presence Canvas */}
          <PresenceCanvas
            state={mappedState}
            mode="orb"
          />

          {/* Right: Conversation Feed */}
          <ConversationFeed
            messages={messages}
            isLoading={isLoading}
            mappedState={mappedState}
            noWorkspace={noWorkspace}
            onFilePreview={openFilePreview}
          >
            <ConversationInput
              input={input}
              isLoading={isLoading}
              isListening={isListening}
              attachedImages={attachedImages}
              showAttachmentMenu={showAttachmentMenu}
              onInputChange={setInput}
              onSend={sendMessage}
              onVoice={handleVoice}
              onFileSelect={handleFileSelect}
              onCameraCapture={handleCameraCapture}
              onScreenCapture={handleScreenCapture}
              onClipboardPaste={handleClipboardPaste}
              onRemoveImage={removeImage}
              onToggleAttachmentMenu={() => setShowAttachmentMenu(!showAttachmentMenu)}
            />
          </ConversationFeed>
        </ResizablePanels>
      </div>
    </div>
  )
}

function ClipboardIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
    </svg>
  )
}

function ConnectionItem({ icon, label, onClick }: { icon: string; label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs text-slate-300 hover:bg-white/5 hover:text-white transition-colors text-left"
    >
      <span className="text-sm">{icon}</span>
      <span>{label}</span>
    </button>
  )
}
