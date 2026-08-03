import { useState, useEffect, useRef } from 'react'
import { Search, Brain, BookOpen, Settings, ArrowRight, Command } from 'lucide-react'

type WorkspaceId = 'landing' | 'memory' | 'knowledge' | 'settings'

const COMMANDS = [
  { id: 'memory', icon: <Brain size={28} />, label: 'Open Memory', sub: 'Workspace', ws: 'memory' as WorkspaceId },
  { id: 'knowledge', icon: <BookOpen size={28} />, label: 'Open Knowledge', sub: 'Workspace', ws: 'knowledge' as WorkspaceId },
  { id: 'settings', icon: <Settings size={28} />, label: 'Open Settings', sub: 'Workspace', ws: 'settings' as WorkspaceId },
]

const AI_SUGGESTIONS = [
  'Summarize active context',
  'Optimize memory clusters',
  'Start new agent: research',
  'Sync knowledge base',
  'Clear conversation history',
]

interface CommandPaletteProps {
  onClose: () => void
  onNavigate: (id: WorkspaceId) => void
}

export default function CommandPalette({ onClose, onNavigate }: CommandPaletteProps) {
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'ArrowDown') setSelected(s => Math.min(s + 1, filtered.length - 1))
      if (e.key === 'ArrowUp') setSelected(s => Math.max(s - 1, 0))
      if (e.key === 'Enter') {
        const item = filtered[selected]
        if (item?.ws) onNavigate(item.ws)
        else onClose()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [selected, query])

  const filtered = COMMANDS.filter(c =>
    c.label.toLowerCase().includes(query.toLowerCase()) ||
    c.sub.toLowerCase().includes(query.toLowerCase())
  )

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 200,
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        paddingTop: '14vh',
        background: 'rgba(0,0,0,0.6)',
        backdropFilter: 'blur(8px)',
        animation: 'fade-in 0.12s ease',
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        className="glass-strong"
        style={{
          width: 1120,
          borderRadius: 32,
          overflow: 'hidden',
          boxShadow: '0 24px 80px rgba(0,0,0,0.7), 0 0 0 1px rgba(99,102,241,0.15)',
          animation: 'slide-in-up 0.18s cubic-bezier(0.4, 0, 0.2, 1)',
        }}
      >
        {/* Search input */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 24,
          padding: '14px 16px',
          borderBottom: '1px solid rgba(255,255,255,0.07)',
        }}>
          <Search size={32} style={{ color: '#6b7099', flexShrink: 0 }} />
          <input
            ref={inputRef}
            value={query}
            onChange={e => { setQuery(e.target.value); setSelected(0) }}
            placeholder="Search or ask Zara anything…"
            style={{
              flex: 1,
              background: 'none',
              border: 'none',
              outline: 'none',
              color: '#e2e4ee',
              fontSize: 30,
              fontFamily: "'Inter', sans-serif",
              caretColor: '#6366f1',
            }}
          />
          <kbd style={{
            fontSize: 20,
            padding: '2px 6px',
            borderRadius: 4,
            background: 'rgba(255,255,255,0.06)',
            border: '1px solid rgba(255,255,255,0.1)',
            color: '#6b7099',
            fontFamily: "'JetBrains Mono', monospace",
          }}>ESC</kbd>
        </div>

        {/* Results */}
        <div style={{ maxHeight: 800, overflowY: 'auto' }}>
          {/* Workspace commands */}
          <div style={{ padding: '8px 0' }}>
            <div style={{ fontSize: 20, fontWeight: 600, letterSpacing: '0.08em', color: '#3a3f5c', padding: '6px 16px', textTransform: 'uppercase' }}>
              Workspaces
            </div>
            {filtered.map((item, i) => (
              <button
                key={item.id}
                onClick={() => onNavigate(item.ws)}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 24,
                  padding: '9px 16px',
                  background: i === selected ? 'rgba(99,102,241,0.12)' : 'transparent',
                  border: 'none',
                  borderLeft: `2px solid ${i === selected ? '#6366f1' : 'transparent'}`,
                  cursor: 'pointer',
                  color: i === selected ? '#e2e4ee' : '#6b7099',
                  transition: 'all 0.1s',
                  textAlign: 'left',
                }}
                onMouseEnter={() => setSelected(i)}
              >
                <span style={{ color: i === selected ? '#818cf8' : '#6b7099' }}>{item.icon}</span>
                <span style={{ flex: 1, fontSize: 26, fontWeight: 500 }}>{item.label}</span>
                <span style={{ fontSize: 22, color: '#3a3f5c' }}>{item.sub}</span>
                {i === selected && <ArrowRight size={24} style={{ color: '#6366f1' }} />}
              </button>
            ))}
          </div>

          {/* AI actions */}
          {query === '' && (
            <div style={{ padding: '4px 0 12px', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ fontSize: 20, fontWeight: 600, letterSpacing: '0.08em', color: '#3a3f5c', padding: '8px 16px 4px', textTransform: 'uppercase' }}>
                Ask Zara
              </div>
              {AI_SUGGESTIONS.map((s, i) => (
                <button
                  key={i}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 20,
                    padding: '8px 16px',
                    background: 'transparent',
                    border: 'none',
                    cursor: 'pointer',
                    color: '#6b7099',
                    fontSize: 24,
                    transition: 'all 0.1s',
                    textAlign: 'left',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.04)'; e.currentTarget.style.color = '#e2e4ee' }}
                  onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#6b7099' }}
                  onClick={onClose}
                >
                  <Command size={22} style={{ color: '#6366f1' }} />
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
