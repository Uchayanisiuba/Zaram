import { useState, useEffect } from 'react'
import {
  MessageSquare, FolderOpen, Settings as SettingsIcon, ChevronRight, Activity,
  Terminal, Cpu, Search
} from 'lucide-react'
import { desktop } from './desktop/desktop-bridge'
import { Button } from './components/ui/Button'
import { ConversationPanel } from './pages/ConversationPanel'
import { FilesystemDemo } from './pages/FilesystemDemo'
import { Settings } from './components/settings/Settings'
import { AuditTerminal } from './pages/AuditTerminal'
import { RuntimeInspector } from './pages/RuntimeInspector'
import { CapabilityExplorer } from './pages/CapabilityExplorer'
import { useNotifications, NotificationContainer } from './hooks/useNotifications'
import { ZaramProvider } from './context/ZaramContext'
import { useZaram } from './hooks/useZaram'

const NAV_ITEMS = [
  { id: 'conversation', label: 'Conversation', icon: MessageSquare },
  { id: 'files', label: 'Files', icon: FolderOpen },
  { id: 'audit', label: 'Audit Terminal', icon: Terminal },
  { id: 'runtime', label: 'Runtime Inspector', icon: Cpu },
  { id: 'capabilities', label: 'Capabilities', icon: Search },
  { id: 'hq', label: 'HQ', icon: SettingsIcon },
]

const STORAGE_KEY = 'zaram-view'

function ContextHeader() {
  const { selectedCharacter } = useZaram()
  const [projectName, setProjectName] = useState('Zaram')
  
  return (
    <div className="h-12 flex items-center justify-between px-4 border-b border-white/5 bg-[#0a0f1c]/80 backdrop-blur-sm">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">Project</span>
          <span className="text-sm font-medium text-slate-200">{projectName}</span>
        </div>
      </div>
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">Persona</span>
          <span className="text-sm font-medium text-cyan-400">{selectedCharacter || 'Zaram Prime'}</span>
        </div>
      </div>
    </div>
  )
}

function App() {
  const [view, setView] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) || 'conversation'
    } catch {
      return 'conversation'
    }
  })
  const [isDesktop, setIsDesktop] = useState(false)
  const { notifications, addNotification, removeNotification } = useNotifications()

  useEffect(() => {
    setIsDesktop(desktop.isDesktop)
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
      case 'conversation':
        return <ConversationPanel />
      case 'audit':
        return <AuditTerminal />
      case 'runtime':
        return <RuntimeInspector />
      case 'capabilities':
        return <CapabilityExplorer />
      case 'files':
        return <FilesystemDemo />
      case 'hq':
        return <Settings />
      default:
        return <ConversationPanel />
    }
  }

  return (
    <ZaramProvider>
      <div className="h-full w-full flex overflow-hidden bg-[#050810] text-slate-200">
        <div className="w-60 flex flex-col bg-[#0a0f1c] border-r border-white/5">
          <div className="p-5 border-b border-white/5">
            <h1 className="text-xl font-bold text-white tracking-wider">ZARAM</h1>
            <p className="text-[10px] mt-1 uppercase tracking-widest text-cyan-400">OS</p>
          </div>
          <nav className="flex-1 p-3 space-y-0.5">
            {NAV_ITEMS.map((item) => (
              <button
                key={item.id}
                onClick={() => setView(item.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 text-sm ${view === item.id ? 'bg-white/10 text-white border border-white/10' : 'text-slate-400 hover:text-white hover:bg-white/5 border border-transparent'}`}
              >
                <item.icon size={18} />
                <span className="font-medium">{item.label}</span>
                {view === item.id && <ChevronRight className="w-4 h-4 ml-auto" />}
              </button>
            ))}
          </nav>

          <div className="p-4 border-t border-white/5">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-cyan-500 to-orange-500 flex items-center justify-center font-bold text-white text-sm">
                Z
              </div>
              <div>
                <div className="text-sm font-semibold text-white tracking-wide">Zaram</div>
                <div className="text-[10px] text-green-400 flex items-center gap-1">
                  <div className="w-1.5 h-1.5 rounded-full bg-green-400"></div>
                  {isDesktop ? 'Native' : 'Browser'}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="flex-1 flex flex-col relative overflow-hidden">
          <ContextHeader />
          <div className="flex-1 overflow-hidden">
            {renderView()}
          </div>
        </div>

        <NotificationContainer notifications={notifications} onRemove={removeNotification} />
      </div>
    </ZaramProvider>
  )
}

export default App
