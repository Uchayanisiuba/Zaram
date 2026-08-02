import { useState } from 'react'
import { Clock, Search } from 'lucide-react'

interface MemNode {
  id: string
  label: string
  type: 'concept' | 'conversation' | 'code' | 'person' | 'project' | 'document'
  x: number
  y: number
  size: number
  importance: number
}

interface MemEdge {
  from: string
  to: string
  strength: number
}

const NODE_COLORS: Record<string, string> = {
  concept: '#6366f1',
  conversation: '#06b6d4',
  code: '#10b981',
  person: '#f59e0b',
  project: '#8b5cf6',
  document: '#818cf8',
}

const NODES: MemNode[] = [
  { id: 'n1', label: 'Zaram Core', type: 'project', x: 380, y: 200, size: 28, importance: 1 },
  { id: 'n2', label: 'AI Provider', type: 'code', x: 220, y: 140, size: 22, importance: 0.9 },
  { id: 'n3', label: 'Memory Store', type: 'code', x: 520, y: 130, size: 20, importance: 0.85 },
  { id: 'n4', label: 'Local-First AI', type: 'concept', x: 150, y: 270, size: 18, importance: 0.8 },
  { id: 'n5', label: 'Context Window', type: 'concept', x: 580, y: 280, size: 16, importance: 0.75 },
  { id: 'n6', label: 'Architecture Discussion', type: 'conversation', x: 300, y: 350, size: 15, importance: 0.7 },
  { id: 'n7', label: 'Vector Embeddings', type: 'concept', x: 460, y: 370, size: 15, importance: 0.68 },
  { id: 'n8', label: 'Alex Chen', type: 'person', x: 120, y: 160, size: 14, importance: 0.65 },
  { id: 'n9', label: 'Runtime Engine', type: 'code', x: 600, y: 180, size: 16, importance: 0.72 },
  { id: 'n10', label: 'GGUF Models', type: 'document', x: 680, y: 300, size: 13, importance: 0.6 },
  { id: 'n11', label: 'Design Philosophy', type: 'document', x: 200, y: 400, size: 13, importance: 0.6 },
  { id: 'n12', label: 'Semantic Search', type: 'concept', x: 420, y: 450, size: 14, importance: 0.62 },
]

const EDGES: MemEdge[] = [
  { from: 'n1', to: 'n2', strength: 0.9 },
  { from: 'n1', to: 'n3', strength: 0.9 },
  { from: 'n1', to: 'n9', strength: 0.8 },
  { from: 'n2', to: 'n4', strength: 0.7 },
  { from: 'n2', to: 'n8', strength: 0.6 },
  { from: 'n3', to: 'n7', strength: 0.85 },
  { from: 'n3', to: 'n12', strength: 0.8 },
  { from: 'n4', to: 'n6', strength: 0.65 },
  { from: 'n5', to: 'n9', strength: 0.7 },
  { from: 'n6', to: 'n11', strength: 0.55 },
  { from: 'n7', to: 'n12', strength: 0.9 },
  { from: 'n9', to: 'n10', strength: 0.7 },
]

const MEMORY_STATS = [
  { label: 'Total nodes', value: '1,847', delta: '+23 today' },
  { label: 'Conversations', value: '284', delta: '+3 today' },
  { label: 'Code artifacts', value: '631', delta: '+8 today' },
  { label: 'Concepts linked', value: '932', delta: '+12 today' },
]

export default function MemoryWorkspace() {
  const [selected, setSelected] = useState<string | null>('n1')
  const [activeFilter, setActiveFilter] = useState<string | null>(null)

  const selectedNode = NODES.find(n => n.id === selected)

  return (
    <div style={{ flex: 1, display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* Left sidebar */}
      <div style={{
        width: 240,
        borderRight: '1px solid var(--color-border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--surface-sidebar)',
        flexShrink: 0,
      }}>
        <div style={{ padding: '14px 16px 10px', borderBottom: '1px solid var(--color-border-subtle)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'var(--color-glass)', borderRadius: 8, padding: '7px 10px', border: '1px solid var(--color-glass-hover)' }}>
            <Search size={12} style={{ color: 'var(--color-text-muted)' }} />
            <span style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>Search memory…</span>
          </div>
        </div>

        {/* Stats */}
        <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--color-border-subtle)', display: 'flex', flexDirection: 'column', gap: 8 }}>
          {MEMORY_STATS.map(stat => (
            <div key={stat.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <span style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>{stat.label}</span>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: 13, color: 'var(--color-text)', fontWeight: 600, fontFamily: "var(--font-display)" }}>{stat.value}</div>
                <div style={{ fontSize: 10, color: '#10b981' }}>{stat.delta}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div style={{ padding: '12px 16px 8px' }}>
          <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', color: 'var(--color-text-faint)', marginBottom: 8, textTransform: 'uppercase' }}>
            Node Types
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {Object.entries(NODE_COLORS).map(([type, color]) => (
              <button
                key={type}
                onClick={() => setActiveFilter(activeFilter === type ? null : type)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '5px 8px',
                  borderRadius: 6,
                  background: activeFilter === type ? `${color}15` : 'transparent',
                  border: `1px solid ${activeFilter === type ? `${color}30` : 'transparent'}`,
                  cursor: 'pointer',
                  color: activeFilter === type ? color : 'var(--color-text-muted)',
                  fontSize: 12,
                  fontWeight: 500,
                  width: '100%',
                  textAlign: 'left',
                  transition: 'all 0.15s',
                  textTransform: 'capitalize',
                }}
              >
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: color, boxShadow: `0 0 4px ${color}` }} />
                {type}
              </button>
            ))}
          </div>
        </div>

        <div style={{ flex: 1 }} />

        {/* Selected node detail */}
        {selectedNode && (
          <div style={{
            padding: 16,
            borderTop: '1px solid var(--color-border-subtle)',
            background: 'rgba(99,102,241,0.05)',
          }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              marginBottom: 10,
            }}>
              <div style={{
                width: 10,
                height: 10,
                borderRadius: '50%',
                background: NODE_COLORS[selectedNode.type],
                boxShadow: `0 0 6px ${NODE_COLORS[selectedNode.type]}`,
              }} />
              <span style={{ fontSize: 13, color: 'var(--color-text)', fontWeight: 600 }}>{selectedNode.label}</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <Row label="Type" value={selectedNode.type} />
              <Row label="Connections" value={`${EDGES.filter(e => e.from === selectedNode.id || e.to === selectedNode.id).length}`} />
              <Row label="Importance" value={`${Math.round(selectedNode.importance * 100)}%`} />
            </div>
          </div>
        )}
      </div>

      {/* Graph area */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        <svg
          width="100%"
          height="100%"
          style={{ position: 'absolute', inset: 0 }}
        >
          {/* Background subtle grid */}
          <defs>
            <pattern id="grid" width="48" height="48" patternUnits="userSpaceOnUse">
              <path d="M 48 0 L 0 0 0 48" fill="none" stroke="rgba(255,255,255,0.025)" strokeWidth="1"/>
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />

          {/* Edges */}
          {EDGES.map((edge, i) => {
            const from = NODES.find(n => n.id === edge.from)!
            const to = NODES.find(n => n.id === edge.to)!
            const isActive = selected === edge.from || selected === edge.to
            const midX = (from.x + to.x) / 2 + (Math.random() * 20 - 10)
            const midY = (from.y + to.y) / 2 - 30
            return (
              <path
                key={i}
                d={`M ${from.x} ${from.y} Q ${midX} ${midY} ${to.x} ${to.y}`}
                fill="none"
                stroke={isActive ? '#6366f1' : 'var(--color-border)'}
                strokeWidth={isActive ? edge.strength * 2 : edge.strength * 1}
                opacity={isActive ? 0.7 : 0.4}
                style={{ transition: 'all 0.3s' }}
              />
            )
          })}

          {/* Nodes */}
          {NODES.map(node => {
            const color = NODE_COLORS[node.type]
            const isSelected = selected === node.id
            const filtered = activeFilter && activeFilter !== node.type
            return (
              <g
                key={node.id}
                onClick={() => setSelected(node.id)}
                style={{ cursor: 'pointer', opacity: filtered ? 0.2 : 1, transition: 'opacity 0.2s' }}
              >
                {isSelected && (
                  <circle
                    cx={node.x}
                    cy={node.y}
                    r={node.size + 10}
                    fill="none"
                    stroke={color}
                    strokeWidth="1.5"
                    opacity={0.4}
                    style={{ animation: 'ring-expand 2s ease-out infinite' }}
                  />
                )}
                <circle
                  cx={node.x}
                  cy={node.y}
                  r={node.size}
                  fill={`${color}25`}
                  stroke={color}
                  strokeWidth={isSelected ? 2 : 1}
                  style={{
                    filter: `drop-shadow(0 0 ${isSelected ? 12 : 6}px ${color})`,
                    transition: 'all 0.2s',
                  }}
                />
                <circle
                  cx={node.x - node.size * 0.25}
                  cy={node.y - node.size * 0.25}
                  r={node.size * 0.35}
                  fill="rgba(255,255,255,0.15)"
                />
                <text
                  x={node.x}
                  y={node.y + node.size + 14}
                  textAnchor="middle"
                  fill={isSelected ? 'var(--color-text)' : 'var(--color-text-muted)'}
                  fontSize={isSelected ? 12 : 11}
                  fontFamily="var(--font-sans)"
                  fontWeight={isSelected ? 600 : 400}
                  style={{ transition: 'all 0.2s', pointerEvents: 'none' }}
                >
                  {node.label}
                </text>
              </g>
            )
          })}
        </svg>

        {/* Timeline toggle */}
        <div style={{
          position: 'absolute',
          top: 16,
          right: 16,
          display: 'flex',
          gap: 8,
        }}>
          {['Graph', 'Timeline', 'Clusters'].map(v => (
            <button
              key={v}
              style={{
                padding: '5px 12px',
                borderRadius: 6,
                background: v === 'Graph' ? 'rgba(99,102,241,0.15)' : 'var(--color-glass)',
                border: `1px solid ${v === 'Graph' ? 'var(--color-border-accent)' : 'var(--color-border)'}`,
                cursor: 'pointer',
                color: v === 'Graph' ? '#818cf8' : 'var(--color-text-muted)',
                fontSize: 11,
                fontWeight: 500,
                backdropFilter: 'blur(12px)',
                transition: 'all 0.15s',
              }}
            >
              {v}
            </button>
          ))}
        </div>

        {/* Timestamp */}
        <div style={{
          position: 'absolute',
          bottom: 80,
          left: 16,
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          fontSize: 11,
          color: 'var(--color-text-faint)',
        }}>
          <Clock size={11} />
          Last synced: 2 minutes ago
        </div>
      </div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
      <span style={{ fontSize: 11, color: 'var(--color-text-secondary)' }}>{label}</span>
      <span style={{ fontSize: 11, color: '#b0b4cc', fontWeight: 500 }}>{value}</span>
    </div>
  )
}
