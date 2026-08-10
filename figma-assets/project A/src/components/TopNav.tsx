import { Search, Wifi, Zap, Bell, User, ChevronRight } from 'lucide-react'

type WorkspaceId = 'landing' | 'build' | 'memory' | 'knowledge' | 'canvas' | 'plugins' | 'settings'

const WORKSPACE_LABELS: Record<WorkspaceId, string> = {
  landing: 'Zaram',
  build: 'Build',
  memory: 'Memory',
  knowledge: 'Knowledge',
  canvas: 'Canvas',
  plugins: 'Plugins',
  settings: 'Settings',
}

interface TopNavProps {
  workspace: WorkspaceId
  onSearchOpen: () => void
}

export default function TopNav({ workspace, onSearchOpen }: TopNavProps) {
  const isLanding = workspace === 'landing'

  return (
    <header
      className="glass-strong"
      style={{
        height: 44,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingInline: 16,
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        flexShrink: 0,
        position: 'relative',
        zIndex: 50,
      }}
    >
      {/* Left: breadcrumb */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 200 }}>
        <span
          style={{
            fontFamily: "'Space Grotesk', sans-serif",
            fontSize: 13,
            fontWeight: 600,
            letterSpacing: '0.02em',
          }}
          className="text-gradient-orb"
        >
          Zaram
        </span>
        {!isLanding && (
          <>
            <ChevronRight size={12} style={{ color: '#3a3f5c' }} />
            <span style={{ fontSize: 13, color: '#6b7099', fontWeight: 500 }}>
              {WORKSPACE_LABELS[workspace]}
            </span>
          </>
        )}
      </div>

      {/* Center: status indicators */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, position: 'absolute', left: '50%', transform: 'translateX(-50%)' }}>
        <StatusPill icon={<span style={{ width: 5, height: 5, borderRadius: '50%', background: '#10b981', display: 'inline-block', boxShadow: '0 0 6px #10b981' }} />} label="Local" />
        <StatusPill icon={<Zap size={10} />} label="Claude 3.5" accent />
        <StatusPill icon={<Wifi size={10} />} label="Synced" />
      </div>

      {/* Right: actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 200, justifyContent: 'flex-end' }}>
        <button
          onClick={onSearchOpen}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            background: 'rgba(255,255,255,0.05)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 6,
            padding: '4px 10px',
            cursor: 'pointer',
            color: '#6b7099',
            fontSize: 12,
            transition: 'all 0.15s',
          }}
          onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.08)')}
          onMouseLeave={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.05)')}
        >
          <Search size={11} />
          <span>Search</span>
          <span style={{ fontSize: 10, opacity: 0.5, fontFamily: "'JetBrains Mono', monospace" }}>⌘K</span>
        </button>

        <NavIcon>
          <Bell size={13} />
        </NavIcon>
        <NavIcon>
          <div style={{
            width: 22,
            height: 22,
            borderRadius: '50%',
            background: 'linear-gradient(135deg, #6366f1, #22d3ee)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            <User size={11} style={{ color: '#fff' }} />
          </div>
        </NavIcon>
      </div>
    </header>
  )
}

function StatusPill({ icon, label, accent = false }: { icon: React.ReactNode; label: string; accent?: boolean }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 5,
      padding: '3px 8px',
      borderRadius: 99,
      background: accent ? 'rgba(99,102,241,0.12)' : 'rgba(255,255,255,0.04)',
      border: `1px solid ${accent ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.06)'}`,
      fontSize: 11,
      color: accent ? '#818cf8' : '#6b7099',
      fontWeight: 500,
    }}>
      {icon}
      {label}
    </div>
  )
}

function NavIcon({ children }: { children: React.ReactNode }) {
  return (
    <button style={{
      width: 28,
      height: 28,
      borderRadius: 6,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'rgba(255,255,255,0.04)',
      border: '1px solid rgba(255,255,255,0.07)',
      cursor: 'pointer',
      color: '#6b7099',
      transition: 'all 0.15s',
    }}
    onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.08)'; e.currentTarget.style.color = '#e2e4ee' }}
    onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.04)'; e.currentTarget.style.color = '#6b7099' }}
    >
      {children}
    </button>
  )
}
