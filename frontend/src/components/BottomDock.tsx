import { Code2, Brain, BookOpen, LayoutGrid, Puzzle, Settings, Search, Mic } from 'lucide-react'

type WorkspaceId = 'landing' | 'build' | 'memory' | 'knowledge' | 'canvas' | 'plugins' | 'settings'

const DOCK_ITEMS = [
  { id: 'build' as WorkspaceId, icon: <Code2 size={32} />, label: 'Build' },
  { id: 'memory' as WorkspaceId, icon: <Brain size={32} />, label: 'Memory' },
  { id: 'knowledge' as WorkspaceId, icon: <BookOpen size={32} />, label: 'Knowledge' },
  { id: 'canvas' as WorkspaceId, icon: <LayoutGrid size={32} />, label: 'Canvas' },
  { id: 'plugins' as WorkspaceId, icon: <Puzzle size={32} />, label: 'Plugins' },
  { id: 'settings' as WorkspaceId, icon: <Settings size={32} />, label: 'Settings' },
]

interface BottomDockProps {
  workspace: WorkspaceId
  onNavigate: (id: WorkspaceId) => void
  onSearch: () => void
}

export default function BottomDock({ workspace, onNavigate, onSearch }: BottomDockProps) {
  return (
    <div style={{
      position: 'absolute',
      bottom: 40,
      left: '50%',
      transform: 'translateX(-50%)',
      zIndex: 100,
    }}>
      <div
        className="glass-strong"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 4,
          padding: '6px 8px',
          borderRadius: 16,
          boxShadow: '0 16px 80px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.06)',
        }}
      >
        {/* Search */}
        <DockButton
          icon={<Search size={32} />}
          label="Search"
          active={false}
          onClick={onSearch}
          accent
        />

        <div style={{ width: 1, height: 48, background: 'rgba(255,255,255,0.08)', margin: '0 8px' }} />

        {DOCK_ITEMS.map(item => (
          <DockButton
            key={item.id}
            icon={item.icon}
            label={item.label}
            active={workspace === item.id}
            onClick={() => onNavigate(item.id)}
          />
        ))}

        <div style={{ width: 1, height: 48, background: 'rgba(255,255,255,0.08)', margin: '0 8px' }} />

        {/* Voice */}
        <DockButton
          icon={<Mic size={32} />}
          label="Voice"
          active={false}
          onClick={() => {}}
        />
      </div>
    </div>
  )
}

function DockButton({
  icon,
  label,
  active,
  onClick,
  accent = false,
}: {
  icon: React.ReactNode
  label: string
  active: boolean
  onClick: () => void
  accent?: boolean
}) {
  return (
    <button
      onClick={onClick}
      title={label}
      style={{
        position: 'relative',
        width: 80,
        height: 80,
        borderRadius: 20,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: active
          ? 'rgba(99,102,241,0.2)'
          : accent
          ? 'rgba(99,102,241,0.1)'
          : 'transparent',
        border: active
          ? '1px solid rgba(99,102,241,0.35)'
          : '1px solid transparent',
        cursor: 'pointer',
        color: active ? '#818cf8' : accent ? '#818cf8' : '#6b7099',
        transition: 'all 0.15s cubic-bezier(0.4, 0, 0.2, 1)',
        boxShadow: active ? '0 0 12px rgba(99,102,241,0.25)' : 'none',
      }}
      onMouseEnter={e => {
        if (!active) {
          e.currentTarget.style.background = 'rgba(255,255,255,0.08)'
          e.currentTarget.style.color = '#e2e4ee'
          e.currentTarget.style.transform = 'translateY(-4px) scale(1.08)'
        }
      }}
      onMouseLeave={e => {
        if (!active) {
          e.currentTarget.style.background = accent ? 'rgba(99,102,241,0.1)' : 'transparent'
          e.currentTarget.style.color = accent ? '#818cf8' : '#6b7099'
          e.currentTarget.style.transform = 'none'
        }
      }}
    >
      {icon}
      {active && (
        <div style={{
          position: 'absolute',
          bottom: -16,
          left: '50%',
          transform: 'translateX(-50%)',
          width: 6,
          height: 6,
          borderRadius: '50%',
          background: '#6366f1',
          boxShadow: '0 0 12px #6366f1',
        }} />
      )}
    </button>
  )
}
