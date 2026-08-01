import { useState } from 'react'
import { Code2, Brain, BookOpen, LayoutGrid, Puzzle, Settings, Search, Pin, FolderOpen, Database, Clock } from 'lucide-react'

type WorkspaceId = 'landing' | 'build' | 'memory' | 'knowledge' | 'canvas' | 'plugins' | 'settings'

interface NavItem {
  id: WorkspaceId
  icon: React.ReactNode
  label: string
  badge?: number
}

const NAV_ITEMS: NavItem[] = [
  { id: 'build', icon: <Code2 size={16} />, label: 'Build' },
  { id: 'memory', icon: <Brain size={16} />, label: 'Memory', badge: 3 },
  { id: 'knowledge', icon: <BookOpen size={16} />, label: 'Knowledge' },
  { id: 'canvas', icon: <LayoutGrid size={16} />, label: 'Canvas' },
  { id: 'plugins', icon: <Puzzle size={16} />, label: 'Plugins', badge: 2 },
]

const RECENT_CONTEXTS = [
  { icon: <FolderOpen size={12} />, label: 'zaram-core v0.4.2', sub: '2 min ago' },
  { icon: <Database size={12} />, label: 'Vector store sync', sub: '18 min ago' },
  { icon: <Clock size={12} />, label: 'Agent: code-review', sub: '1 hr ago' },
]

interface LeftRailProps {
  workspace: WorkspaceId
  onNavigate: (id: WorkspaceId) => void
}

export default function LeftRail({ workspace, onNavigate }: LeftRailProps) {
  const [expanded, setExpanded] = useState(false)

  return (
    <aside
      onMouseEnter={() => setExpanded(true)}
      onMouseLeave={() => setExpanded(false)}
      style={{
        width: expanded ? 220 : 56,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
        padding: '12px 8px',
        transition: 'width 0.22s cubic-bezier(0.4, 0, 0.2, 1)',
        background: 'rgba(8,10,14,0.6)',
        backdropFilter: 'blur(20px)',
        borderRight: '1px solid rgba(255,255,255,0.06)',
        overflow: 'hidden',
        flexShrink: 0,
        zIndex: 30,
      }}
    >
      {/* Search */}
      <button
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '7px 8px',
          borderRadius: 8,
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          color: '#6b7099',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          transition: 'background 0.15s',
          width: '100%',
        }}
        onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.06)'; e.currentTarget.style.color = '#e2e4ee' }}
        onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#6b7099' }}
      >
        <span style={{ flexShrink: 0, display: 'flex', alignItems: 'center' }}><Search size={16} /></span>
        {expanded && <span style={{ fontSize: 13, fontWeight: 500, opacity: expanded ? 1 : 0, transition: 'opacity 0.15s' }}>Search</span>}
      </button>

      <div style={{ height: 1, background: 'rgba(255,255,255,0.06)', margin: '4px 0' }} />

      {/* Nav items */}
      {NAV_ITEMS.map(item => (
        <RailItem
          key={item.id}
          item={item}
          active={workspace === item.id}
          expanded={expanded}
          onClick={() => onNavigate(item.id)}
        />
      ))}

      <div style={{ flex: 1 }} />

      {/* Recent context (expanded only) */}
      {expanded && (
        <div style={{ animation: 'fade-in 0.2s ease' }}>
          <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.08em', color: '#3a3f5c', padding: '4px 8px 8px', textTransform: 'uppercase' }}>
            Recent
          </div>
          {RECENT_CONTEXTS.map((ctx, i) => (
            <button
              key={i}
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 2,
                padding: '6px 8px',
                borderRadius: 6,
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                color: '#6b7099',
                width: '100%',
                textAlign: 'left',
                transition: 'all 0.15s',
              }}
              onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.05)' }}
              onMouseLeave={e => { e.currentTarget.style.background = 'transparent' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#b0b4cc' }}>
                {ctx.icon}
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 140 }}>{ctx.label}</span>
              </div>
              <span style={{ fontSize: 10, color: '#3a3f5c', paddingLeft: 18 }}>{ctx.sub}</span>
            </button>
          ))}
        </div>
      )}

      <div style={{ height: 1, background: 'rgba(255,255,255,0.06)', margin: '4px 0' }} />

      {/* Settings */}
      <RailItem
        item={{ id: 'settings', icon: <Settings size={16} />, label: 'Settings' }}
        active={workspace === 'settings'}
        expanded={expanded}
        onClick={() => onNavigate('settings')}
      />
    </aside>
  )
}

function RailItem({ item, active, expanded, onClick }: { item: NavItem; active: boolean; expanded: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '7px 8px',
        borderRadius: 8,
        background: active ? 'rgba(99,102,241,0.15)' : 'transparent',
        border: `1px solid ${active ? 'rgba(99,102,241,0.25)' : 'transparent'}`,
        cursor: 'pointer',
        color: active ? '#818cf8' : '#6b7099',
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        transition: 'all 0.15s',
        width: '100%',
        position: 'relative',
      }}
      onMouseEnter={e => {
        if (!active) {
          e.currentTarget.style.background = 'rgba(255,255,255,0.06)'
          e.currentTarget.style.color = '#e2e4ee'
        }
      }}
      onMouseLeave={e => {
        if (!active) {
          e.currentTarget.style.background = 'transparent'
          e.currentTarget.style.color = '#6b7099'
        }
      }}
    >
      <span style={{ flexShrink: 0, display: 'flex', alignItems: 'center' }}>{item.icon}</span>
      {expanded && (
        <span style={{ fontSize: 13, fontWeight: 500, flex: 1, textAlign: 'left' }}>
          {item.label}
        </span>
      )}
      {expanded && item.badge != null && (
        <span style={{
          fontSize: 10,
          fontWeight: 700,
          background: 'rgba(99,102,241,0.3)',
          color: '#818cf8',
          borderRadius: 99,
          padding: '1px 6px',
          lineHeight: 1.6,
        }}>{item.badge}</span>
      )}
      {!expanded && item.badge != null && (
        <span style={{
          position: 'absolute',
          top: 4,
          right: 4,
          width: 6,
          height: 6,
          borderRadius: '50%',
          background: '#6366f1',
          boxShadow: '0 0 6px rgba(99,102,241,0.7)',
        }} />
      )}
    </button>
  )
}
