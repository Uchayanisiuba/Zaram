import { useState } from 'react'
import { ExternalLink, BookOpen, Globe, FileText, Link, Search, Sparkles } from 'lucide-react'

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
  paper: <FileText size={26} />,
  web: <Globe size={26} />,
  doc: <BookOpen size={26} />,
}

export default function KnowledgeWorkspace() {
  const [selected, setSelected] = useState('s3')
  const [_activeTag, _setActiveTag] = useState<string | null>(null)

  const selectedSource = SOURCES.find(s => s.id === selected)!

  return (
    <div style={{ flex: 1, display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* Sources list */}
      <div style={{
        width: 640,
        borderRight: '1px solid var(--color-border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--surface-sidebar)',
        flexShrink: 0,
      }}>
        <div style={{ padding: '28px 32px 20px', borderBottom: '1px solid var(--color-border-subtle)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, background: 'var(--color-glass)', borderRadius: 8, padding: '14px 20px', border: '1px solid var(--color-glass-hover)', marginBottom: 10 }}>
            <Search size={24} style={{ color: 'var(--color-text-muted)' }} />
            <span style={{ fontSize: 24, color: 'var(--color-text-secondary)' }}>Search sources…</span>
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            {['All', 'Papers', 'Web', 'Docs'].map(f => (
              <button
                key={f}
                style={{
                  padding: '6px 20px',
                  borderRadius: 99,
                  background: f === 'All' ? 'rgba(99,102,241,0.15)' : 'var(--color-glass)',
                  border: `1px solid ${f === 'All' ? 'var(--color-border-accent)' : 'var(--color-glass-hover)'}`,
                  cursor: 'pointer',
                  color: f === 'All' ? 'var(--color-indigo-light)' : 'var(--color-text-muted)',
                  fontSize: 22,
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
                 padding: '28px 32px',
                 background: selected === source.id ? 'rgba(99,102,241,0.08)' : 'transparent',
                 borderLeft: `3px solid ${selected === source.id ? source.color : 'transparent'}`,
                 borderBottom: '1px solid var(--color-glass)',
                 border: 'none',
                 cursor: 'pointer',
                 textAlign: 'left',
                 transition: 'all 0.15s',
               }}
              onMouseEnter={e => { if (selected !== source.id) e.currentTarget.style.background = 'rgba(255,255,255,0.03)' }}
              onMouseLeave={e => { if (selected !== source.id) e.currentTarget.style.background = 'transparent' }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                <div style={{
                  width: 56,
                  height: 56,
                  borderRadius: 14,
                  background: `${source.color}20`,
                  border: `1px solid ${source.color}30`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: source.color,
                  flexShrink: 0,
                  marginTop: 2,
                }}>
                  {TYPE_ICONS[source.type]}
                </div>
                <div style={{ flex: 1, overflow: 'hidden' }}>
                  <div style={{ fontSize: 26, color: selected === source.id ? 'var(--color-text)' : '#b0b4cc', fontWeight: 500, marginBottom: 48, lineHeight: 1.3 }}>
                    {source.title}
                  </div>
                  <div style={{ fontSize: 22, color: 'var(--color-text-secondary)', marginBottom: 6 }}>
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
            <div style={{ display: 'flex', alignItems: 'center', gap: 20, marginBottom: 12 }}>
              <div style={{
                width: 72,
                height: 72,
                borderRadius: 20,
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
                <div style={{ fontSize: 22, color: 'var(--color-text-muted)', marginBottom: 2 }}>
                  {selectedSource.author} · {selectedSource.date}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{
                    fontSize: 20,
                    padding: '4px 14px',
                    borderRadius: 6,
                    background: `${selectedSource.color}15`,
                    color: selectedSource.color,
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                  }}>{selectedSource.type}</span>
                  <span style={{ fontSize: 20, color: '#10b981' }}>
                    {Math.round(selectedSource.relevance * 100)}% relevant
                  </span>
                </div>
              </div>
              <button style={{
                marginLeft: 'auto',
                display: 'flex',
                alignItems: 'center',
                gap: 24,
                padding: '12px 24px',
                borderRadius: 14,
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.1)',
                cursor: 'pointer',
                color: 'var(--color-text-muted)',
                fontSize: 24,
              }}>
                <ExternalLink size={24} />
                Open source
              </button>
            </div>
            <h2 style={{
              fontFamily: "var(--font-display)",
              fontSize: 22,
              fontWeight: 700,
              color: 'var(--color-text)',
              margin: 0,
              lineHeight: 1.25,
              letterSpacing: '-0.01em',
            }}>
              {selectedSource.title}
            </h2>
          </div>

          {/* Tags */}
          <div style={{ display: 'flex', gap: 24, marginBottom: 48, flexWrap: 'wrap' }}>
            {selectedSource.tags.map(tag => (
              <span key={tag} style={{
                padding: '8px 20px',
                borderRadius: 99,
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.09)',
                fontSize: 22,
                color: '#b0b4cc',
                fontWeight: 500,
              }}>{tag}</span>
            ))}
          </div>

          {/* AI Summary */}
          <div style={{
            padding: 40,
            borderRadius: 24,
            background: 'rgba(99,102,241,0.06)',
            border: '1px solid rgba(99,102,241,0.15)',
            marginBottom: 48,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 12 }}>
              <Sparkles size={26} style={{ color: 'var(--color-indigo-light)' }} />
              <span style={{ fontSize: 24, fontWeight: 600, color: 'var(--color-indigo-light)', fontFamily: "var(--font-display)" }}>
                AI Summary
              </span>
            </div>
            <p style={{ fontSize: 26, color: '#b0b4cc', lineHeight: 1.7, margin: 0 }}>
              {selectedSource.summary}
            </p>
          </div>

          {/* Related concepts */}
          <div style={{ marginBottom: 24 }}>
            <h3 style={{ fontSize: 26, fontWeight: 600, color: 'var(--color-text-muted)', margin: '0 0 12px', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
              Related Concepts
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {RELATED.map(rel => (
                <div key={rel.label} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <Link size={22} style={{ color: 'var(--color-text-secondary)' }} />
                  <span style={{ fontSize: 24, color: '#b0b4cc', flex: 1 }}>{rel.label}</span>
                  <div style={{ width: 160, height: 2, background: 'var(--color-border-subtle)', borderRadius: 2, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${rel.strength * 100}%`, background: '#6366f1', borderRadius: 2 }} />
                  </div>
                  <span style={{ fontSize: 20, color: 'var(--color-text-secondary)', fontFamily: "var(--font-mono)", minWidth: 56 }}>
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
      <div style={{ flex: 1, height: 2, background: 'var(--color-border-subtle)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${value * 100}%`, background: color, borderRadius: 2 }} />
      </div>
      <span style={{ fontSize: 18, color: 'var(--color-text-secondary)', fontFamily: "var(--font-mono)" }}>
        {Math.round(value * 100)}%
      </span>
    </div>
  )
}
