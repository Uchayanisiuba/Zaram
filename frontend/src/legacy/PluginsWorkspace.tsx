import { useState } from 'react'
import { Download, Check, Star, Zap, Shield, AlertTriangle, Search } from 'lucide-react'

interface Plugin {
  id: string
  name: string
  description: string
  author: string
  category: string
  version: string
  installed: boolean
  stars: number
  icon: string
  iconBg: string
  health: 'healthy' | 'warning' | 'error'
  permissions: string[]
}

const PLUGINS: Plugin[] = [
  {
    id: 'p1', name: 'Code Intelligence', author: 'Zaram Labs', category: 'Development',
    description: 'Deep code analysis with AST parsing, semantic search, and intelligent refactoring suggestions.',
    version: '2.1.4', installed: true, stars: 4.9,
    icon: '⬡', iconBg: 'linear-gradient(135deg, var(--color-indigo), var(--color-indigo-light))',
    health: 'healthy', permissions: ['read files', 'write files', 'execute commands'],
  },
  {
    id: 'p2', name: 'Research Assistant', author: 'Zaram Labs', category: 'Knowledge',
    description: 'Automated web research, paper summarization, and citation management with real-time source tracking.',
    version: '1.8.2', installed: true, stars: 4.7,
    icon: '◈', iconBg: 'linear-gradient(135deg, #06b6d4, #22d3ee)',
    health: 'healthy', permissions: ['network access', 'read memory'],
  },
  {
    id: 'p3', name: 'Memory Optimizer', author: 'Neural Systems', category: 'Memory',
    description: 'Intelligently clusters and deduplicates memory nodes, improving context retrieval by up to 40%.',
    version: '0.9.1', installed: true, stars: 4.5,
    icon: '◎', iconBg: 'linear-gradient(135deg, #10b981, #34d399)',
    health: 'warning', permissions: ['read memory', 'write memory'],
  },
  {
    id: 'p4', name: 'Voice Control Pro', author: 'Acoustic AI', category: 'Interface',
    description: 'Advanced voice commands with custom hotwords, multi-language support, and noise cancellation.',
    version: '3.0.0', installed: false, stars: 4.6,
    icon: '🎙', iconBg: 'linear-gradient(135deg, #8b5cf6, #a78bfa)',
    health: 'healthy', permissions: ['microphone', 'read context'],
  },
  {
    id: 'p5', name: 'Git Companion', author: 'DevTools Co', category: 'Development',
    description: 'AI-powered commit messages, PR descriptions, code review summaries, and branch management.',
    version: '1.4.0', installed: false, stars: 4.8,
    icon: '⊕', iconBg: 'linear-gradient(135deg, #f59e0b, #fbbf24)',
    health: 'healthy', permissions: ['execute commands', 'read files', 'network access'],
  },
  {
    id: 'p6', name: 'Canvas AI', author: 'Zaram Labs', category: 'Canvas',
    description: 'Intelligent object arrangement, auto-connecting related ideas, and AI-generated visual summaries.',
    version: '0.7.3', installed: false, stars: 4.3,
    icon: '⊡', iconBg: 'linear-gradient(135deg, #ec4899, #f472b6)',
    health: 'healthy', permissions: ['read canvas', 'write canvas', 'read memory'],
  },
]

const CATEGORIES = ['All', 'Development', 'Knowledge', 'Memory', 'Interface', 'Canvas']

export default function PluginsWorkspace() {
  const [filter, setFilter] = useState('All')
  const [tab, setTab] = useState<'installed' | 'available'>('installed')
  const [search, setSearch] = useState('')
  const [installedIds, setInstalledIds] = useState<Set<string>>(
    new Set(PLUGINS.filter(p => p.installed).map(p => p.id))
  )

  const visible = PLUGINS.filter(p => {
    const matchesTab = tab === 'installed' ? installedIds.has(p.id) : !installedIds.has(p.id)
    const matchesCat = filter === 'All' || p.category === filter
    const matchesSearch = p.name.toLowerCase().includes(search.toLowerCase()) || p.description.toLowerCase().includes(search.toLowerCase())
    return matchesTab && matchesCat && matchesSearch
  })

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', padding: 28 }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{
          fontFamily: "var(--font-display)",
          fontSize: 24,
          fontWeight: 700,
          color: 'var(--color-text)',
          margin: '0 0 6px',
          letterSpacing: '-0.02em',
        }}>
          Plugins
        </h1>
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)', margin: 0 }}>
          Extend Zaram with AI-powered capabilities
        </p>
      </div>

      {/* Controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        {/* Tabs */}
        <div style={{
          display: 'flex',
          background: 'var(--color-glass)',
          border: '1px solid var(--color-border)',
          borderRadius: 10,
          padding: 4,
          gap: 2,
        }}>
          {(['installed', 'available'] as const).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              style={{
                padding: '5px 14px',
                borderRadius: 7,
                background: tab === t ? 'rgba(99,102,241,0.2)' : 'transparent',
                border: `1px solid ${tab === t ? 'rgba(99,102,241,0.35)' : 'transparent'}`,
                cursor: 'pointer',
                color: tab === t ? 'var(--color-indigo-light)' : 'var(--color-text-muted)',
                fontSize: 12,
                fontWeight: 600,
                transition: 'all 0.15s',
                textTransform: 'capitalize',
              }}
            >
              {t}
              <span style={{
                marginLeft: 6,
                fontSize: 10,
                padding: '1px 6px',
                borderRadius: 99,
                background: tab === t ? 'rgba(99,102,241,0.3)' : 'var(--color-border-subtle)',
                color: tab === t ? 'var(--color-indigo-light)' : 'var(--color-text-secondary)',
              }}>
                {PLUGINS.filter(p => t === 'installed' ? installedIds.has(p.id) : !installedIds.has(p.id)).length}
              </span>
            </button>
          ))}
        </div>

        {/* Search */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          background: 'var(--color-glass)',
          border: '1px solid var(--color-border)',
          borderRadius: 8,
          padding: '7px 12px',
          flex: 1,
          maxWidth: 300,
        }}>
          <Search size={13} style={{ color: 'var(--color-text-muted)' }} />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search plugins…"
            style={{
              background: 'none',
              border: 'none',
              outline: 'none',
              color: 'var(--color-text)',
              fontSize: 13,
              flex: 1,
              fontFamily: "var(--font-sans)",
            }}
          />
        </div>

        {/* Category filter */}
        <div style={{ display: 'flex', gap: 6 }}>
          {CATEGORIES.map(cat => (
            <button
              key={cat}
              onClick={() => setFilter(cat)}
              style={{
                padding: '5px 12px',
                borderRadius: 8,
                background: filter === cat ? 'rgba(99,102,241,0.12)' : 'var(--color-glass)',
                border: `1px solid ${filter === cat ? 'rgba(99,102,241,0.25)' : 'var(--color-glass-hover)'}`,
                cursor: 'pointer',
                color: filter === cat ? 'var(--color-indigo-light)' : 'var(--color-text-muted)',
                fontSize: 11,
                fontWeight: 500,
                transition: 'all 0.15s',
              }}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Plugin grid */}
      <div
        className="scroll-area"
        style={{
          flex: 1,
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
          gap: 16,
          alignContent: 'start',
          overflowY: 'auto',
        }}
      >
        {visible.map(plugin => {
          const installed = installedIds.has(plugin.id)
          return (
            <div
              key={plugin.id}
              style={{
                padding: 20,
                borderRadius: 14,
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid var(--color-glass-hover)',
                display: 'flex',
                flexDirection: 'column',
                gap: 14,
                transition: 'all 0.2s',
                cursor: 'default',
              }}
              onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.05)'; e.currentTarget.style.borderColor = 'rgba(255,255,255,0.1)' }}
              onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.03)'; e.currentTarget.style.borderColor = 'var(--color-glass-hover)' }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
                {/* Icon */}
                <div style={{
                  width: 48,
                  height: 48,
                  borderRadius: 12,
                  background: plugin.iconBg,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 22,
                  flexShrink: 0,
                  boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
                }}>
                  {plugin.icon}
                </div>

                <div style={{ flex: 1, overflow: 'hidden' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
                    <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text)', fontFamily: "var(--font-display)" }}>
                      {plugin.name}
                    </span>
                    <HealthBadge health={plugin.health} />
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 11, color: 'var(--color-text-secondary)' }}>{plugin.author}</span>
                    <span style={{ fontSize: 10, color: 'var(--color-text-faint)' }}>v{plugin.version}</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 3, marginLeft: 'auto' }}>
                      <Star size={10} fill="#f59e0b" style={{ color: '#f59e0b' }} />
                      <span style={{ fontSize: 10, color: '#f59e0b', fontWeight: 600 }}>{plugin.stars}</span>
                    </div>
                  </div>
                </div>
              </div>

              <p style={{ fontSize: 12, color: '#8b8fa8', lineHeight: 1.6, margin: 0 }}>
                {plugin.description}
              </p>

              {/* Permissions */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {plugin.permissions.map(perm => (
                  <span key={perm} style={{
                    fontSize: 10,
                    padding: '2px 7px',
                    borderRadius: 4,
                    background: 'var(--color-glass)',
                    border: '1px solid var(--color-glass-hover)',
                    color: 'var(--color-text-muted)',
                  }}>{perm}</span>
                ))}
              </div>

              {/* Action */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{
                  fontSize: 10,
                  padding: '2px 8px',
                  borderRadius: 4,
                  background: 'var(--color-glass)',
                  color: 'var(--color-text-secondary)',
                }}>{plugin.category}</span>
                <button
                  onClick={() => {
                    setInstalledIds(prev => {
                      const next = new Set(prev)
                      if (next.has(plugin.id)) next.delete(plugin.id)
                      else next.add(plugin.id)
                      return next
                    })
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '6px 14px',
                    borderRadius: 8,
                    background: installed ? 'rgba(16,185,129,0.1)' : 'rgba(99,102,241,0.15)',
                    border: `1px solid ${installed ? 'rgba(16,185,129,0.25)' : 'rgba(99,102,241,0.3)'}`,
                    cursor: 'pointer',
                    color: installed ? '#10b981' : 'var(--color-indigo-light)',
                    fontSize: 12,
                    fontWeight: 600,
                    transition: 'all 0.15s',
                  }}
                >
                  {installed ? <><Check size={12} /> Installed</> : <><Download size={12} /> Install</>}
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function HealthBadge({ health }: { health: string }) {
  const configs = {
    healthy: { color: '#10b981', icon: <Zap size={9} />, label: 'Healthy' },
    warning: { color: '#f59e0b', icon: <AlertTriangle size={9} />, label: 'Warning' },
    error: { color: '#f87171', icon: <Shield size={9} />, label: 'Error' },
  }
  const cfg = configs[health as keyof typeof configs] ?? configs.healthy
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 3,
      padding: '1px 6px',
      borderRadius: 4,
      background: `${cfg.color}15`,
      border: `1px solid ${cfg.color}30`,
      color: cfg.color,
      fontSize: 9,
      fontWeight: 600,
    }}>
      {cfg.icon}
    </div>
  )
}
