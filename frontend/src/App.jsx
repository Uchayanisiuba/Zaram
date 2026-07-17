import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import {
  Activity, MessageSquare, Brain, Database, Settings,
  Code, HardDrive, Terminal, Cpu, Search,
  FolderOpen, ChevronRight
} from 'lucide-react'
import { desktop } from './desktop/desktop-bridge'
import { OrbEngine } from './components/OrbEngine/OrbEngine'
import { Button } from './components/ui/Button'
import { Orchestration } from './pages/Orchestration'
import { ConversationPanel } from './pages/ConversationPanel'
import { AuditTerminal } from './pages/AuditTerminal'
import { RuntimeInspector } from './pages/RuntimeInspector'
import { CapabilityExplorer } from './pages/CapabilityExplorer'
import { FilesystemDemo } from './pages/FilesystemDemo'
import { useNotifications, NotificationContainer } from './hooks/useNotifications'

const NAV_ITEMS = [
  { id: 'orchestration', label: 'Orchestration', icon: Activity },
  { id: 'conversation', label: 'Conversation', icon: MessageSquare },
  { id: 'audit', label: 'Audit Terminal', icon: Terminal },
  { id: 'runtime', label: 'Runtime Inspector', icon: Cpu },
  { id: 'capabilities', label: 'Capabilities', icon: Search },
  { id: 'filesystem', label: 'Filesystem', icon: FolderOpen },
]

const STORAGE_KEY = 'zaram-dev-preview-view'

function App() {
  const [view, setView] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) || 'orchestration'
    } catch {
      return 'orchestration'
    }
  })
  const [isDesktop, setIsDesktop] = useState(false)
  const [backendStatus, setBackendStatus] = useState(null)
  const { notifications, addNotification, removeNotification } = useNotifications()

  useEffect(() => {
    setIsDesktop(desktop.isDesktop)
    if (desktop.backend.onStatus) {
      desktop.backend.onStatus((status) => setBackendStatus(status))
    }
  }, [])

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, view)
    } catch {
      // ignore
    }
  }, [view])

  useEffect(() => {
    const unsubWorkspace = desktop.workspace.onEvent((evt) => {
      if (evt.type === 'workspace.snapshot_created') {
        addNotification('success', 'Workspace indexed', 'Snapshot updated')
      } else if (evt.type === 'workspace.scan_completed') {
        addNotification('success', 'Indexing complete', 'Workspace fully indexed')
      } else if (evt.type === 'workspace.error') {
        addNotification('error', 'Workspace error', evt.data?.message || 'Unknown error')
      }
    })
    const unsubVSCode = desktop.vscode?.onEvent?.((evt) => {
      if (evt.type === 'vscode.connected') {
        addNotification('success', 'VS Code connected')
      } else if (evt.type === 'vscode.disconnected') {
        addNotification('warning', 'VS Code disconnected')
      } else if (evt.type === 'vscode.diagnostics_updated') {
        addNotification('info', 'Diagnostics updated', `${evt.data?.count || 0} issues`)
      } else if (evt.type === 'vscode.error') {
        addNotification('error', 'VS Code error', evt.data?.message || 'Unknown error')
      }
    }) || (() => {})
    return () => {
      unsubWorkspace()
      unsubVSCode()
    }
  }, [addNotification])

  const renderView = () => {
    switch (view) {
      case 'orchestration':
        return <Orchestration />
      case 'conversation':
        return <ConversationPanel />
      case 'audit':
        return <AuditTerminal />
      case 'runtime':
        return <RuntimeInspector />
      case 'capabilities':
        return <CapabilityExplorer />
      case 'filesystem':
        return <FilesystemDemo />
      default:
        return <Orchestration />
    }
  }

  return (
    <div className="h-screen w-screen flex overflow-hidden bg-[#050810] text-slate-200">
      <div className="w-64 flex flex-col bg-[#0a0f1c] border-r border-white/5">
        <div className="p-6 border-b border-white/5">
          <h1 className="text-2xl font-bold text-white tracking-wider">ZARAM</h1>
          <p className="text-[10px] mt-1 uppercase tracking-widest text-cyan-400">Developer Preview</p>
        </div>
        <nav className="flex-1 p-4 space-y-1">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              onClick={() => setView(item.id)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 ${view === item.id ? 'bg-white/10 text-white border border-white/10' : 'text-slate-400 hover:text-white hover:bg-white/5 border border-transparent'}`}
            >
              <item.icon size={18} />
              <span className="text-sm font-medium">{item.label}</span>
              {view === item.id && <ChevronRight className="w-4 h-4 ml-auto" />}
            </button>
          ))}
        </nav>
        <div className="p-4 border-t border-white/5">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-cyan-500 to-orange-500 flex items-center justify-center font-bold text-white">
              Z
            </div>
            <div>
              <div className="text-sm font-semibold text-white tracking-wide">ZARAM OS</div>
              <div className="text-[10px] text-green-400 flex items-center gap-1">
                <div className="w-1.5 h-1.5 rounded-full bg-green-400"></div>
                {isDesktop ? 'Desktop Runtime' : 'Browser Mode'}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 flex flex-col relative overflow-hidden">
        <div className="h-12 flex items-center justify-between px-6 border-b border-white/5 bg-black/20 z-30">
          <div className="flex items-center gap-3 text-[10px] font-mono">
            <span className="text-slate-500">ZARAM OS</span>
            <span className="text-slate-700">|</span>
            <span className="font-bold text-cyan-400">{view.toUpperCase()}</span>
            {backendStatus && (
              <>
                <span className="text-slate-700">|</span>
                <span className={backendStatus.running ? 'text-green-400' : 'text-red-400'}>
                  BACKEND: {backendStatus.running ? 'ONLINE' : 'OFFLINE'}
                </span>
              </>
            )}
          </div>
          <div className="text-[10px] text-slate-500">
            {isDesktop ? 'Native Runtime' : 'Web Preview'}
          </div>
        </div>

        <div className="flex-1 overflow-hidden">
          {renderView()}
        </div>

        <div className="h-8 flex items-center justify-between px-6 border-t border-white/5 bg-black/20 text-[10px] text-slate-500">
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-green-400"></span>
              Executive Runtime Ready
            </span>
            <span className="text-slate-700">|</span>
            <span>Workspace Synced</span>
          </div>
          <div className="flex items-center gap-4">
            <span>620 Tests Passing</span>
          </div>
        </div>
      </div>

      <NotificationContainer notifications={notifications} onRemove={removeNotification} />
    </div>
  )
}

export default App
