import { Search, Wifi, Zap, Bell, User, ChevronRight } from 'lucide-react'

type WorkspaceId = 'landing' | 'memory' | 'knowledge' | 'settings'

const WORKSPACE_LABELS: Record<WorkspaceId, string> = {
  landing: 'Zaram',
  memory: 'Memory',
  knowledge: 'Knowledge',
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
        height: 88,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingInline: 32,
        borderBottom: '1px solid var(--color-border-subtle)',
        flexShrink: 0,
        position: 'relative',
        zIndex: 50,
      }}
    >
      {/* Left: breadcrumb */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 64, minWidth: 200 }}>
        <span
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: 'var(--text-h1)',
            fontWeight: 600,
            letterSpacing: '0.02em',
          }}
          className="text-gradient-orb"
        >
          Zaram
        </span>
        {!isLanding && (
          <>
            <ChevronRight size={24} style={{ color: 'var(--color-text-faint)' }} />
            <span style={{ fontSize: 'var(--text-h1)', color: 'var(--color-text-muted)', fontWeight: 500 }}>
              {WORKSPACE_LABELS[workspace]}
            </span>
          </>
        )}
      </div>

      {/* Center: status indicators */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 64, position: 'absolute', left: '50%', transform: 'translateX(-50%)' }}>
        <StatusPill icon={<span style={{ width: 10, height: 10, borderRadius: '50%', background: 'var(--color-emerald)', display: 'inline-block', boxShadow: '0 0 6px var(--color-emerald)' }} />} label="Local" />
        <StatusPill icon={<Zap size={20} />} label="Claude 3.5" accent />
        <StatusPill icon={<Wifi size={20} />} label="Synced" />
      </div>

      {/* Right: actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 64, minWidth: 200, justifyContent: 'flex-end' }}>
        <button
          onClick={onSearchOpen}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 64,
            background: 'var(--color-glass-mid)',
            border: '1px solid var(--color-border)',
            borderRadius: 12,
            padding: '4px 10px',
            cursor: 'pointer',
            color: 'var(--color-text-muted)',
            fontSize: 'var(--text-h1)',
            transition: 'all 0.15s',
          }}
          onMouseEnter={e => (e.currentTarget.style.background = 'var(--color-border-glass-strong)')}
          onMouseLeave={e => (e.currentTarget.style.background = 'var(--color-glass-mid)')}
        >
          <Search size={22} />
          <span>Search</span>
          <span style={{ fontSize: 'var(--text-h2)', opacity: 0.5, fontFamily: 'var(--font-mono)' }}>⌘K</span>
        </button>

        <NavIcon>
          <Bell size={26} />
        </NavIcon>
        <NavIcon>
          <div style={{
            width: 44,
            height: 44,
            borderRadius: '50%',
            background: 'linear-gradient(135deg, var(--color-indigo), var(--color-cyan-light))',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
             <User size={22} style={{ color: 'var(--color-text)' }} />
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
      gap: 10,
      padding: '3px 8px',
      borderRadius: 99,
      background: accent ? 'var(--color-indigo-a-12)' : 'var(--color-glass)',
      border: `1px solid ${accent ? 'var(--color-indigo-a-20)' : 'var(--color-border-subtle)'}`,
      fontSize: 'var(--text-h2)',
      color: accent ? 'var(--color-indigo-light)' : 'var(--color-text-muted)',
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
      width: 56,
      height: 56,
      borderRadius: 12,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'var(--color-glass)',
      border: '1px solid var(--color-glass-hover)',
      cursor: 'pointer',
      color: 'var(--color-text-muted)',
      transition: 'all 0.15s',
    }}
      onMouseEnter={e => { e.currentTarget.style.background = 'var(--color-border)'; e.currentTarget.style.color = 'var(--color-text)' }}
      onMouseLeave={e => { e.currentTarget.style.background = 'var(--color-glass)'; e.currentTarget.style.color = 'var(--color-text-muted)' }}
    >
      {children}
    </button>
  )
}
