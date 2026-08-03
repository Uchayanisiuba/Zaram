import { Home, Brain, BookOpen, Settings, Search, Mic } from 'lucide-react'
import { useState } from 'react'
import { Keycap } from '@/components/shortcuts/Keycap'
import { NAV_SHORTCUTS, detectPlatform, type Platform, type Shortcut } from '@/runtime/shortcuts/registry'

type WorkspaceId = 'landing' | 'memory' | 'knowledge' | 'settings'

const DOCK_ITEMS = [
  // Always offer a way back to the landing surface.
  { id: 'landing' as WorkspaceId, icon: <Home size={32} />, label: 'Home' },
  { id: 'memory' as WorkspaceId, icon: <Brain size={32} />, label: 'Memory' },
  { id: 'knowledge' as WorkspaceId, icon: <BookOpen size={32} />, label: 'Knowledge' },
  { id: 'settings' as WorkspaceId, icon: <Settings size={32} />, label: 'Settings' },
]

interface BottomDockProps {
  workspace: WorkspaceId
  onNavigate: (id: WorkspaceId) => void
  onSearch: () => void
}

export default function BottomDock({ workspace, onNavigate, onSearch }: BottomDockProps) {
  const [platform] = useState<Platform>(() => detectPlatform());
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

        <div style={{ width: 1, height: 48, background: 'var(--color-glass-hover)', margin: '0 8px' }} />

        {DOCK_ITEMS.map(item => {
          const sc = NAV_SHORTCUTS.find((n) => n.action.type === 'navigate' && n.action.target === item.id)
          return (
            <DockButton
              key={item.id}
              icon={item.icon}
              label={item.label}
              active={workspace === item.id}
              onClick={() => onNavigate(item.id)}
              shortcut={sc}
              platform={platform}
            />
          )
        })}

        <div style={{ width: 1, height: 48, background: 'var(--color-glass-hover)', margin: '0 8px' }} />

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
  shortcut,
  platform,
}: {
  icon: React.ReactNode
  label: string
  active: boolean
  onClick: () => void
  accent?: boolean
  shortcut?: Shortcut
  platform?: Platform
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
          ? 'var(--color-indigo-a-20)'
          : accent
          ? 'var(--color-indigo-a-10)'
          : 'transparent',
        border: active
          ? '1px solid var(--color-indigo-a-35)'
          : '1px solid transparent',
        cursor: 'pointer',
        color: active ? 'var(--color-indigo-light)' : accent ? 'var(--color-indigo-light)' : 'var(--color-text-muted)',
        transition: 'all 0.15s cubic-bezier(0.4, 0, 0.2, 1)',
        boxShadow: active ? '0 0 12px var(--color-indigo-a-25)' : 'none',
      }}
      onMouseEnter={e => {
        if (!active) {
          e.currentTarget.style.background = 'var(--color-glass-hover)'
          e.currentTarget.style.color = 'var(--color-text)'
          e.currentTarget.style.transform = 'translateY(-4px) scale(1.08)'
        }
      }}
      onMouseLeave={e => {
        if (!active) {
          e.currentTarget.style.background = accent ? 'var(--color-indigo-a-10)' : 'transparent'
          e.currentTarget.style.color = accent ? 'var(--color-indigo-light)' : 'var(--color-text-muted)'
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
          background: 'var(--color-indigo)',
          boxShadow: '0 0 12px var(--color-indigo-a-70)',
        }} />
      )}
      {shortcut && platform && (
        <span style={{ position: 'absolute', right: 6, bottom: 6 }}>
          <Keycap shortcut={shortcut} platform={platform} size="sm" />
        </span>
      )}
    </button>
  )
}
