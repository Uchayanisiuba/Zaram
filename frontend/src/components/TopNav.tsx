import { Search, Bell, User, ChevronRight } from 'lucide-react'
import OrbStatus from '@/components/orb/OrbStatus'

import type { WorkspaceId } from '@/runtime/shortcuts/registry'

const WORKSPACE_LABELS: Record<WorkspaceId, string> = {
  landing: 'Zaram',
  memory: 'Memory',
  knowledge: 'Knowledge',
  activity: 'Activity',
  settings: 'Settings',
}

interface TopNavProps {
  workspace: WorkspaceId
  onSearchOpen: () => void
  /** Leave the workspace and open the conversation at full size. */
  onOpenConversation: () => void
}

export default function TopNav({ workspace, onSearchOpen, onOpenConversation }: TopNavProps) {
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

      {/* Centre: the Orb, at working size.
          It replaced three hardcoded pills — "Local", "Claude 3.5" and
          "Synced". None reflected anything: no cloud provider is wired and
          there is no sync. One indicator reporting real state is worth more
          than three claiming things that are not true. */}
      <div style={{ position: 'absolute', left: '50%', transform: 'translateX(-50%)' }}>
        {/* Ring 48px (1.2x the original 40). Orb 84px (1.5x its previous 56),
            so it reads as the orb with a ring around it rather than a ring with
            a small orb inside. The orb's glow extends past the ring, which is
            why the container does not clip. */}
        <OrbStatus ringSize={48} orbSize={84} onOpen={onOpenConversation} />
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
