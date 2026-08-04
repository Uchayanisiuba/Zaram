import { Home, Brain, BookOpen, ShieldCheck, Settings, Search } from 'lucide-react'
import { useState } from 'react'
import { NAV_SHORTCUTS, chordTokens, detectPlatform, type Platform, type Shortcut } from '@/runtime/shortcuts/registry'

/** Tooltip text: the label plus its shortcut, since the dock is now too short
 *  to show a keycap without covering the icon. */
function shortcutLabel(label: string, shortcut?: Shortcut, platform?: Platform) {
  if (!shortcut || !platform) return label
  return `${label} (${chordTokens(shortcut, platform)})`
}

import type { WorkspaceId } from '@/runtime/shortcuts/registry'

// Icons and labels mirror the landing page's orbital nodes exactly, so the same
// destination looks the same wherever it is reached from.
// Landing: Memory = Brain, Knowledge = BookOpen, Settings = Settings.
const DOCK_ITEMS = [
  // Always offer a way back to the landing surface.
  { id: 'landing' as WorkspaceId, icon: <Home size={22} />, label: 'Home' },
  { id: 'memory' as WorkspaceId, icon: <Brain size={22} />, label: 'Memory' },
  { id: 'knowledge' as WorkspaceId, icon: <BookOpen size={22} />, label: 'Knowledge' },
  { id: 'activity' as WorkspaceId, icon: <ShieldCheck size={22} />, label: 'Activity' },
  { id: 'settings' as WorkspaceId, icon: <Settings size={22} />, label: 'Settings' },
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
          padding: '4px 8px',
          borderRadius: 16,
          boxShadow: '0 16px 80px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.06)',
        }}
      >
        {/* Search */}
        <DockButton
          icon={<Search size={22} />}
          label="Search"
          active={false}
          onClick={onSearch}
          accent
        />

        <div style={{ width: 1, height: 32, background: 'var(--color-glass-hover)', margin: '0 6px' }} />

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
      title={shortcutLabel(label, shortcut, platform)}
      style={{
        position: 'relative',
        width: 52,
        height: 52,
        borderRadius: 14,
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
          bottom: -10,
          left: '50%',
          transform: 'translateX(-50%)',
          width: 5,
          height: 5,
          borderRadius: '50%',
          background: 'var(--color-indigo)',
          boxShadow: '0 0 12px var(--color-indigo-a-70)',
        }} />
      )}
    </button>
  )
}
