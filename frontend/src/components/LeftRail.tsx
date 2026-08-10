import { useState } from 'react'
import { Home, Brain, BookOpen, FileText, Layers, ShieldCheck, Settings, Search, FolderOpen, Database, Clock } from 'lucide-react'
import ResizeHandle from '@/components/common/ResizeHandle'
import {
  useLayoutStore,
  RAIL_MIN,
  RAIL_MAX,
  RAIL_COLLAPSED,
} from '@/stores/layoutStore'

import { surfaceOrder, surfaceLabels } from '@/runtime/shortcuts/registry'
import type { WorkspaceId } from '@/runtime/shortcuts/registry'

interface NavItem {
  id: WorkspaceId
  icon: React.ReactNode
  label: string
  badge?: number
}

// Badges removed with the Runtime Panel: they were hardcoded counts, not real ones.
//
// Icons only. The list itself and its order come from the registry, and this
// being a `Record<WorkspaceId, …>` means adding a node fails to compile here
// until it is given one — which is how a node stops going missing from a
// navigation surface without anyone noticing.
const NAV_ICONS: Record<WorkspaceId, React.ReactNode> = {
  // Landing is listed first so there is always a way back to it. Without this
  // entry, navigating into a workspace was a one-way trip.
  landing: <Home size={32} />,
  work: <FileText size={32} />,
  // Layers, not a folder. Project groups work; it does not browse a filesystem,
  // and a folder icon would promise the tree CLAUDE.md rules out.
  project: <Layers size={32} />,
  memory: <Brain size={32} />,
  knowledge: <BookOpen size={32} />,
  // Activity is evidence rather than content, which is why its icon is the odd
  // one out. Ordered next to Settings because both are about behaviour.
  activity: <ShieldCheck size={32} />,
  settings: <Settings size={32} />,
}

const NAV_LABELS: Partial<Record<WorkspaceId, string>> = { landing: 'Home' }

const NAV_ITEMS: NavItem[] = surfaceOrder.map((id) => ({
  id,
  icon: NAV_ICONS[id],
  label: NAV_LABELS[id] ?? surfaceLabels[id],
}))

const RECENT_CONTEXTS = [
  { icon: <FolderOpen size={24} />, label: 'zaram-core v0.4.2', sub: '2 min ago' },
  { icon: <Database size={24} />, label: 'Vector store sync', sub: '18 min ago' },
  { icon: <Clock size={24} />, label: 'Agent: code-review', sub: '1 hr ago' },
]

interface LeftRailProps {
  workspace: WorkspaceId
  onNavigate: (id: WorkspaceId) => void
}

export default function LeftRail({ workspace, onNavigate }: LeftRailProps) {
  const [expanded, setExpanded] = useState(false)

  const railWidth = useLayoutStore((s) => s.railWidth)
  const setRailWidth = useLayoutStore((s) => s.setRailWidth)
  const resetRail = useLayoutStore((s) => s.resetRail)
  const setResizing = useLayoutStore((s) => s.setResizing)
  const isResizing = useLayoutStore((s) => s.isResizing)

  // Dragging moves the pointer out of the rail, which would otherwise collapse
  // it mid-drag. Stay expanded for the duration.
  const isOpen = expanded || isResizing
  const currentWidth = isOpen ? railWidth : RAIL_COLLAPSED

  return (
    <>
    <aside
      onMouseEnter={() => setExpanded(true)}
      onMouseLeave={() => setExpanded(false)}
      style={{
        width: currentWidth,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        padding: '12px 8px',
        // No width transition while dragging, or the edge lags the cursor.
        transition: isResizing ? 'none' : 'width 0.22s cubic-bezier(0.4, 0, 0.2, 1)',
        background: 'var(--surface-rail)',
        // Saturation matches .glass so the rail reads the same as the dock and
        // the conversation panel rather than slightly flatter.
        backdropFilter: 'blur(20px) saturate(1.4)',
        WebkitBackdropFilter: 'blur(20px) saturate(1.4)',
        borderRight: '1px solid var(--color-border-subtle)',
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
          gap: 20,
          padding: '7px 8px',
          borderRadius: 16,
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          color: 'var(--color-text-muted)',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          transition: 'background 0.15s',
          width: '100%',
        }}
        onMouseEnter={e => { e.currentTarget.style.background = 'var(--color-border-subtle)'; e.currentTarget.style.color = 'var(--color-text)' }}
        onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--color-text-muted)' }}
      >
        <span style={{ flexShrink: 0, display: 'flex', alignItems: 'center' }}><Search size={32} /></span>
        {expanded && <span style={{ fontSize: 'var(--text-h1)', fontWeight: 500, opacity: expanded ? 1 : 0, transition: 'opacity 0.15s' }}>Search</span>}
      </button>

      <div style={{ height: 1, background: 'var(--color-border-subtle)', margin: '8px 0' }} />

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
          <div style={{ fontSize: 'var(--text-h2)', fontWeight: 600, letterSpacing: '0.08em', color: 'var(--color-text-secondary)', padding: '4px 8px 8px', textTransform: 'uppercase' }}>
            Recent
          </div>
          {RECENT_CONTEXTS.map((ctx, i) => (
            <button
              key={i}
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 4,
                padding: '6px 8px',
                borderRadius: 12,
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                color: 'var(--color-text-muted)',
                width: '100%',
                textAlign: 'left',
                transition: 'all 0.15s',
              }}
              onMouseEnter={e => { e.currentTarget.style.background = 'var(--color-glass)' }}
              onMouseLeave={e => { e.currentTarget.style.background = 'transparent' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 'var(--text-h1)', color: 'var(--color-text-muted-light)' }}>
                {ctx.icon}
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 280 }}>{ctx.label}</span>
              </div>
              <span style={{ fontSize: 'var(--text-h2)', color: 'var(--color-text-faint)', paddingLeft: 36 }}>{ctx.sub}</span>
            </button>
          ))}
        </div>
      )}

      <div style={{ height: 1, background: 'var(--color-border-subtle)', margin: '8px 0' }} />

      {/* Settings */}
      <RailItem
        item={{ id: 'settings', icon: <Settings size={32} />, label: 'Settings' }}
        active={workspace === 'settings'}
        expanded={expanded}
        onClick={() => onNavigate('settings')}
      />
    </aside>

    {/* Positioned against the viewport rather than the rail: the rail clips its
        overflow to hide labels while collapsing, which would hide the handle.
        Only offered while expanded — there is nothing to adjust when collapsed. */}
    {isOpen && (
      <ResizeHandle
        panelSide="left"
        label="Resize navigation rail"
        value={railWidth}
        min={RAIL_MIN}
        max={RAIL_MAX}
        onResize={(clientX) => setRailWidth(clientX)}
        onNudge={(deltaPx) => setRailWidth(railWidth + deltaPx)}
        onReset={resetRail}
        onResizingChange={setResizing}
        style={{ position: 'fixed', left: currentWidth - 4, right: 'auto', top: 0 }}
      />
    )}
    </>
  )
}

function RailItem({ item, active, expanded, onClick }: { item: NavItem; active: boolean; expanded: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      // Named whether or not the label is drawn. Collapsed, this button
      // contained an icon and nothing else — no text, no title, no label — so
      // the whole navigation announced itself as five anonymous buttons, and
      // "Knowledge" was unreachable to anything that finds controls by name.
      aria-label={item.label}
      aria-current={active ? 'page' : undefined}
      title={item.label}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 20,
        padding: '7px 8px',
        borderRadius: 16,
        background: active ? 'var(--color-indigo-a-15)' : 'transparent',
        border: `1px solid ${active ? 'var(--color-indigo-a-25)' : 'transparent'}`,
        cursor: 'pointer',
        color: active ? 'var(--color-indigo-light)' : 'var(--color-text-muted)',
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        transition: 'all 0.15s',
        width: '100%',
        position: 'relative',
      }}
      onMouseEnter={e => {
        if (!active) {
          e.currentTarget.style.background = 'var(--color-border-subtle)'
          e.currentTarget.style.color = 'var(--color-text)'
        }
      }}
      onMouseLeave={e => {
        if (!active) {
          e.currentTarget.style.background = 'transparent'
          e.currentTarget.style.color = 'var(--color-text-muted)'
        }
      }}
    >
      <span style={{ flexShrink: 0, display: 'flex', alignItems: 'center' }}>{item.icon}</span>
      {expanded && (
        <span style={{ fontSize: 'var(--text-h1)', fontWeight: 500, flex: 1, textAlign: 'left' }}>
          {item.label}
        </span>
      )}
      {expanded && item.badge != null && (
        <span style={{
          fontSize: 'var(--text-h2)',
          fontWeight: 700,
          background: 'var(--color-indigo-a-30)',
          color: 'var(--color-indigo-light)',
          borderRadius: 99,
          padding: '1px 6px',
          lineHeight: 1.6,
        }}>{item.badge}</span>
      )}
      {!expanded && item.badge != null && (
        <span style={{
          position: 'absolute',
          top: 8,
          right: 8,
          width: 12,
          height: 12,
          borderRadius: '50%',
          background: 'var(--color-indigo)',
          boxShadow: '0 0 12px var(--color-indigo-a-70)',
        }} />
      )}
    </button>
  )
}
