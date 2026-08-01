import { useState } from 'react'
import { ExternalLink, BookOpen, Globe, FileText, Link, Search, Sparkles, ChevronRight } from 'lucide-react'

const SOURCES = [
  {
    id: 's1', type: 'paper', title: 'Attention Is All You Need',
    author: 'Vaswani et al.', date: '2017', relevance: 0.95,
    summary: 'Foundational transformer architecture paper. Introduces self-attention mechanism that eliminates recurrence in sequence models.',
    tags: ['transformer', 'attention', 'NLP'],
    color: '#6366f1',
  },
  {
    id: 's2', type: 'web', title: 'Local LLM Inference — State of the Art',
    author: 'Simon Willison', date: 'Dec 2024', relevance: 0.89,
    summary: 'Comprehensive overview of running large language models locally, covering GGUF formats, quantization, and performance benchmarks.',
    tags: ['local AI', 'GGUF', 'inference'],
    color: '#06b6d4',
  },
  {
    id: 's3', type: 'doc', title: 'Zaram Architecture Spec v0.4',
    author: 'Internal', date: 'Jan 2025', relevance: 0.98,
    summary: 'Core architecture decisions for the Zaram runtime, including the memory pipeline, context manager, and AI provider abstraction.',
    tags: ['architecture', 'internal', 'zaram'],
    color: '#10b981',
  },
  {
    id: 's4', type: 'web', title: 'Vector Similarity Search at Scale',
    author: 'Pinecone Blog', date: 'Nov 2024', relevance: 0.82,
    summary: 'Deep dive into approximate nearest-neighbor algorithms for semantic search, comparing HNSW, IVF, and PQ approaches.',
    tags: ['vectors', 'search', 'embeddings'],
    color: '#8b5cf6',
  },
]

const RELATED = [
  { label: 'Transformer Architecture', strength: 0.95 },
  { label: 'Local-First AI', strength: 0.89 },
  { label: 'Memory Systems', strength: 0.84 },
  { label: 'Context Management', strength: 0.78 },
  { label: 'GGUF Format', strength: 0.71 },
]

const TYPE_ICONS: Record<string, React.ReactNode> = {
  paper: <FileText size={13} />,
  web: <Globe size={13} />,
  doc: <BookOpen size={13} />,
}

export default function KnowledgeWorkspace() {
  const [selected, setSelected] = useState('s3')
  const [activeTag, setActiveTag] = useState<string | null>(null)

  const selectedSource = SOURCES.find(s => s.id === selected)!

  return (
    <div style={{ flex: 1, display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* Sources list */}
      <div style={{
        width: 320,
        borderRight: '1px solid rgba(255,255,255,0.06)',
        display: 'flex',
        flexDirection: 'column',
        background: 'rgba(8,10,14,0.5)',
        flexShrink: 0,
      }}>
        <div style={{ padding: '14px 16px 10px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'rgba(255,255,255,0.04)', borderRadius: 8, padding: '7px 10px', border: '1px solid rgba(255,255,255,0.07)', marginBottom: 10 }}>
            <Search size={12} style={{ color: '#6b7099' }} />
            <span style={{ fontSize: 12, color: '#4a4f6a' }}>Search sources…</span>
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            {['All', 'Papers', 'Web', 'Docs'].map(f => (
              <button
                key={f}
                style={{
                  padding: '3px 10px',
                  borderRadius: 99,
                  background: f === 'All' ? 'rgba(99,102,241,0.15)' : 'rgba(255,255,255,0.04)',
                  border: `1px solid ${f === 'All' ? 'rgba(99,102,241,0.3)' : 'rgba(255,255,255,0.07)'}`,
                  cursor: 'pointer',
                  color: f === 'All' ? '#818cf8' : '#6b7099',
                  fontSize: 11,
                  fontWeight: 500,
                }}
              >{f}</button>
            ))}
          </div>
        </div>

        <div className="scroll-area" style={{ flex: 1 }}>
          {SOURCES.map(source => (
            <button
              key={source.id}
              onClick={() => setSelected(source.id)}
              style={{
                width: '100%',
                padding: '14px 16px',
                borderBottom: '1px solid rgba(255,255,255,0.04)',
                background: selected === source.id ? 'rgba(99,102,241,0.08)' : 'transparent',
                borderLeft: `3px solid ${selected === source.id ? source.color : 'transparent'}`,
                border: 'none',
                borderBottom: '1px solid rgba(255,255,255,0.04)',
                borderLeft: `3px solid ${selected === source.id ? source.color : 'transparent'}`,
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.15s',
              }}
              onMouseEnter={e => { if (selected !== source.id) e.currentTarget.style.background = 'rgba(255,255,255,0.03)' }}
              onMouseLeave={e => { if (selected !== source.id) e.currentTarget.style.background = 'transparent' }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                <div style={{
                  width: 28,
                  height: 28,
                  borderRadius: 7,
                  background: `${source.color}20`,
                  border: `1px solid ${source.color}30`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: source.color,
                  flexShrink: 0,
                  marginTop: 1,
                }}>
                  {TYPE_ICONS[source.type]}
                </div>
                <div style={{ flex: 1, overflow: 'hidden' }}>
                  <div style={{ fontSize: 13, color: selected === source.id ? '#e2e4ee' : '#b0b4cc', fontWeight: 500, marginBottom: 3, lineHeight: 1.3 }}>
                    {source.title}
                  </div>
                  <div style={{ fontSize: 11, color: '#4a4f6a', marginBottom: 6 }}>
                    {source.author} · {source.date}
                  </div>
                  <RelevanceBar value={source.relevance} color={source.color} />
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Source detail */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div className="scroll-area" style={{ flex: 1, padding: 28 }}>
          {/* Header */}
          <div style={{ marginBottom: 24 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              <div style={{
                width: 36,
                height: 36,
                borderRadius: 10,
                background: `${selectedSource.color}20`,
                border: `1px solid ${selectedSource.color}40`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: selectedSource.color,
              }}>
                {TYPE_ICONS[selectedSource.type]}
              </div>
              <div>
                <div style={{ fontSize: 11, color: '#6b7099', marginBottom: 2 }}>
                  {selectedSource.author} · {selectedSource.date}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{
                    fontSize: 10,
                    padding: '2px 7px',
                    borderRadius: 3,
                    background: `${selectedSource.color}15`,
                    color: selectedSource.color,
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                  }}>{selectedSource.type}</span>
                  <span style={{ fontSize: 10, color: '#10b981' }}>
                    {Math.round(selectedSource.relevance * 100)}% relevant
                  </span>
                </div>
              </div>
              <button style={{
                marginLeft: 'auto',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '6px 12px',
                borderRadius: 7,
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.1)',
                cursor: 'pointer',
                color: '#6b7099',
                fontSize: 12,
              }}>
                <ExternalLink size={12} />
                Open source
              </button>
            </div>
            <h2 style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: 22,
              fontWeight: 700,
              color: '#e2e4ee',
              margin: 0,
              lineHeight: 1.25,
              letterSpacing: '-0.01em',
            }}>
              {selectedSource.title}
            </h2>
          </div>

          {/* Tags */}
          <div style={{ display: 'flex', gap: 6, marginBottom: 24, flexWrap: 'wrap' }}>
            {selectedSource.tags.map(tag => (
              <span key={tag} style={{
                padding: '4px 10px',
                borderRadius: 99,
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.09)',
                fontSize: 11,
                color: '#b0b4cc',
                fontWeight: 500,
              }}>{tag}</span>
            ))}
          </div>

          {/* AI Summary */}
          <div style={{
            padding: 20,
            borderRadius: 12,
            background: 'rgba(99,102,241,0.06)',
            border: '1px solid rgba(99,102,241,0.15)',
            marginBottom: 24,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 12 }}>
              <Sparkles size={13} style={{ color: '#818cf8' }} />
              <span style={{ fontSize: 12, fontWeight: 600, color: '#818cf8', fontFamily: "'Space Grotesk', sans-serif" }}>
                AI Summary
              </span>
            </div>
            <p style={{ fontSize: 13, color: '#b0b4cc', lineHeight: 1.7, margin: 0 }}>
              {selectedSource.summary}
            </p>
          </div>

          {/* Related concepts */}
          <div style={{ marginBottom: 24 }}>
            <h3 style={{ fontSize: 13, fontWeight: 600, color: '#6b7099', margin: '0 0 12px', letterSpacing: '0.04em', textTransform: 'uppercase', fontSize: 10 }}>
              Related Concepts
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {RELATED.map(rel => (
                <div key={rel.label} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <Link size={11} style={{ color: '#4a4f6a' }} />
                  <span style={{ fontSize: 12, color: '#b0b4cc', flex: 1 }}>{rel.label}</span>
                  <div style={{ width: 80, height: 2, background: 'rgba(255,255,255,0.06)', borderRadius: 1, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${rel.strength * 100}%`, background: '#6366f1', borderRadius: 1 }} />
                  </div>
                  <span style={{ fontSize: 10, color: '#4a4f6a', fontFamily: "'JetBrains Mono', monospace", minWidth: 28 }}>
                    {Math.round(rel.strength * 100)}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function RelevanceBar({ value, color }: { value: number; color: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ flex: 1, height: 2, background: 'rgba(255,255,255,0.06)', borderRadius: 1, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${value * 100}%`, background: color, borderRadius: 1 }} />
      </div>
      <span style={{ fontSize: 9, color: '#4a4f6a', fontFamily: "'JetBrains Mono', monospace" }}>
        {Math.round(value * 100)}%
      </span>
    </div>
  )
}
