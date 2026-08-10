import { useState } from 'react'
import { Plus, Move, ZoomIn, ZoomOut, Maximize2, StickyNote, Code, Image, Link, Sparkles } from 'lucide-react'

interface CanvasItem {
  id: string
  type: 'sticky' | 'code' | 'ai' | 'image' | 'link'
  x: number
  y: number
  w: number
  h: number
  title?: string
  content: string
  color?: string
}

const CANVAS_ITEMS: CanvasItem[] = [
  {
    id: 'c1', type: 'sticky', x: 80, y: 80, w: 200, h: 160,
    content: 'The orb should feel like a living entity — not an icon, not a logo. Plasma energy. Consciousness.',
    color: '#f59e0b',
  },
  {
    id: 'c2', type: 'code', x: 320, y: 60, w: 280, h: 180,
    title: 'provider.ts',
    content: `export class ZaramAIProvider {
  async generate(prompt: string) {
    const context = await this.memory
      .query(prompt, { limit: 12 })
    return this.stream(context)
  }
}`,
    color: '#6366f1',
  },
  {
    id: 'c3', type: 'ai', x: 640, y: 40, w: 240, h: 140,
    title: 'Zara insight',
    content: 'The memory architecture could benefit from a tiered approach: hot memory (recent 2h), warm memory (past 7d), cold archive. This mirrors human cognition.',
    color: '#818cf8',
  },
  {
    id: 'c4', type: 'sticky', x: 80, y: 290, w: 200, h: 130,
    content: 'Local-first means privacy by default. No data ever leaves the device without explicit user consent.',
    color: '#06b6d4',
  },
  {
    id: 'c5', type: 'link', x: 320, y: 290, w: 240, h: 100,
    title: 'Attention Is All You Need',
    content: 'arxiv.org/abs/1706.03762',
    color: '#10b981',
  },
  {
    id: 'c6', type: 'sticky', x: 600, y: 240, w: 180, h: 140,
    content: 'Design system: 8pt grid. Glass panels. Electric indigo + cyan. No harsh borders.',
    color: '#8b5cf6',
  },
  {
    id: 'c7', type: 'ai', x: 880, y: 120, w: 220, h: 160,
    title: 'Zara analysis',
    content: 'Three workspaces with the highest user value: Build (productivity core), Memory (knowledge retention), Canvas (spatial thinking).',
    color: '#818cf8',
  },
]

const TYPE_CONFIGS: Record<string, { icon: React.ReactNode; label: string }> = {
  sticky: { icon: <StickyNote size={11} />, label: 'Note' },
  code: { icon: <Code size={11} />, label: 'Code' },
  ai: { icon: <Sparkles size={11} />, label: 'AI' },
  image: { icon: <Image size={11} />, label: 'Image' },
  link: { icon: <Link size={11} />, label: 'Link' },
}

const STICKY_COLORS: Record<string, { bg: string; border: string; header: string }> = {
  '#f59e0b': { bg: 'rgba(245,158,11,0.08)', border: 'rgba(245,158,11,0.2)', header: 'rgba(245,158,11,0.15)' },
  '#06b6d4': { bg: 'rgba(6,182,212,0.08)', border: 'rgba(6,182,212,0.2)', header: 'rgba(6,182,212,0.15)' },
  '#10b981': { bg: 'rgba(16,185,129,0.08)', border: 'rgba(16,185,129,0.2)', header: 'rgba(16,185,129,0.15)' },
  '#8b5cf6': { bg: 'rgba(139,92,246,0.08)', border: 'rgba(139,92,246,0.2)', header: 'rgba(139,92,246,0.15)' },
  '#6366f1': { bg: 'rgba(99,102,241,0.08)', border: 'rgba(99,102,241,0.2)', header: 'rgba(99,102,241,0.15)' },
  '#818cf8': { bg: 'rgba(129,140,248,0.06)', border: 'rgba(129,140,248,0.2)', header: 'rgba(129,140,248,0.12)' },
}

export default function CanvasWorkspace() {
  const [zoom, setZoom] = useState(1)
  const [selected, setSelected] = useState<string | null>(null)

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', position: 'relative' }}>
      {/* Toolbar */}
      <div style={{
        position: 'absolute',
        top: 16,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 20,
        display: 'flex',
        alignItems: 'center',
        gap: 2,
        padding: '5px 8px',
        borderRadius: 12,
        background: 'rgba(13,15,22,0.9)',
        backdropFilter: 'blur(20px)',
        border: '1px solid var(--color-border)',
        boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
      }}>
        {[
          { icon: <Move size={14} />, label: 'Pan' },
          { icon: <StickyNote size={14} />, label: 'Sticky' },
          { icon: <Code size={14} />, label: 'Code' },
          { icon: <Sparkles size={14} />, label: 'AI' },
          { icon: <Image size={14} />, label: 'Image' },
          { icon: <Link size={14} />, label: 'Link' },
        ].map(tool => (
          <button
            key={tool.label}
            title={tool.label}
            style={{
              width: 34,
              height: 34,
              borderRadius: 8,
              background: tool.label === 'Pan' ? 'rgba(99,102,241,0.15)' : 'transparent',
              border: `1px solid ${tool.label === 'Pan' ? 'rgba(99,102,241,0.3)' : 'transparent'}`,
              cursor: 'pointer',
              color: tool.label === 'Pan' ? '#818cf8' : 'var(--color-text-muted)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.15s',
            }}
            onMouseEnter={e => { if (tool.label !== 'Pan') { e.currentTarget.style.background = 'var(--color-glass-hover)'; e.currentTarget.style.color = 'var(--color-text)' }}}
            onMouseLeave={e => { if (tool.label !== 'Pan') { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--color-text-muted)' }}}
          >
            {tool.icon}
          </button>
        ))}

        <div style={{ width: 1, height: 20, background: 'var(--color-border)', margin: '0 4px' }} />

        <button
          onClick={() => setZoom(z => Math.max(0.5, z - 0.1))}
          style={{ width: 28, height: 28, borderRadius: 6, background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
        >
          <ZoomOut size={13} />
        </button>
        <span style={{ fontSize: 11, color: 'var(--color-text-muted)', minWidth: 38, textAlign: 'center', fontFamily: "var(--font-mono)" }}>
          {Math.round(zoom * 100)}%
        </span>
        <button
          onClick={() => setZoom(z => Math.min(2, z + 0.1))}
          style={{ width: 28, height: 28, borderRadius: 6, background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
        >
          <ZoomIn size={13} />
        </button>

        <div style={{ width: 1, height: 20, background: 'var(--color-border)', margin: '0 4px' }} />

        <button style={{
          width: 28,
          height: 28,
          borderRadius: 6,
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          color: 'var(--color-text-muted)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          <Maximize2 size={13} />
        </button>
      </div>

      {/* Canvas area */}
      <div
        style={{
          flex: 1,
          position: 'relative',
          overflow: 'hidden',
          cursor: 'grab',
          backgroundImage: `
            radial-gradient(circle, rgba(99,102,241,0.12) 1px, transparent 1px)
          `,
          backgroundSize: `${32 * zoom}px ${32 * zoom}px`,
        }}
        onClick={() => setSelected(null)}
      >
        {/* Canvas items */}
        <div style={{ transform: `scale(${zoom})`, transformOrigin: 'top left', position: 'absolute', inset: 0 }}>
          {CANVAS_ITEMS.map(item => {
            const colorCfg = STICKY_COLORS[item.color!] ?? STICKY_COLORS['#6366f1']
            const isSelected = selected === item.id
            return (
              <div
                key={item.id}
                onClick={e => { e.stopPropagation(); setSelected(item.id) }}
                style={{
                  position: 'absolute',
                  left: item.x,
                  top: item.y,
                  width: item.w,
                  height: item.h,
                  borderRadius: 12,
                  background: colorCfg.bg,
                  backdropFilter: 'blur(16px)',
                  border: `1.5px solid ${isSelected ? item.color : colorCfg.border}`,
                  boxShadow: isSelected
                    ? `0 8px 32px rgba(0,0,0,0.4), 0 0 0 2px ${item.color}30`
                    : '0 4px 16px rgba(0,0,0,0.3)',
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  overflow: 'hidden',
                  transition: 'all 0.2s cubic-bezier(0.4,0,0.2,1)',
                  animation: 'float-gentle 4s ease-in-out infinite',
                  animationDelay: `${parseInt(item.id.replace('c','')) * 0.4}s`,
                  transform: isSelected ? 'scale(1.02)' : 'scale(1)',
                  zIndex: isSelected ? 10 : 1,
                }}
              >
                {/* Header */}
                <div style={{
                  padding: '8px 12px',
                  background: colorCfg.header,
                  borderBottom: `1px solid ${colorCfg.border}`,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  flexShrink: 0,
                }}>
                  <span style={{ color: item.color }}>{TYPE_CONFIGS[item.type].icon}</span>
                  <span style={{ fontSize: 10, fontWeight: 600, color: item.color, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
                    {item.title ?? TYPE_CONFIGS[item.type].label}
                  </span>
                </div>

                {/* Content */}
                <div style={{
                  flex: 1,
                  padding: 12,
                  overflow: 'hidden',
                }}>
                  {item.type === 'code' ? (
                    <pre style={{
                      margin: 0,
                      fontSize: 10.5,
                      color: '#b0b4cc',
                      fontFamily: "var(--font-mono)",
                      lineHeight: 1.6,
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}>{item.content}</pre>
                  ) : item.type === 'link' ? (
                    <div>
                      <div style={{ fontSize: 12, color: 'var(--color-text)', fontWeight: 500, marginBottom: 4 }}>{item.content}</div>
                      <div style={{ fontSize: 11, color: item.color, textDecoration: 'underline', opacity: 0.7 }}>
                        {item.content}
                      </div>
                    </div>
                  ) : (
                    <p style={{
                      margin: 0,
                      fontSize: 12,
                      color: '#c8ccd8',
                      lineHeight: 1.6,
                      overflow: 'hidden',
                      display: '-webkit-box',
                      WebkitLineClamp: 5,
                      WebkitBoxOrient: 'vertical' as const,
                    }}>{item.content}</p>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Add item button */}
      <button
        style={{
          position: 'absolute',
          bottom: 80,
          right: 20,
          zIndex: 20,
          width: 44,
          height: 44,
          borderRadius: 12,
          background: 'rgba(99,102,241,0.2)',
          border: '1px solid rgba(99,102,241,0.4)',
          cursor: 'pointer',
          color: '#818cf8',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 4px 16px rgba(99,102,241,0.3)',
          backdropFilter: 'blur(12px)',
          transition: 'all 0.2s',
        }}
        onMouseEnter={e => { e.currentTarget.style.background = 'rgba(99,102,241,0.3)'; e.currentTarget.style.transform = 'scale(1.08)' }}
        onMouseLeave={e => { e.currentTarget.style.background = 'rgba(99,102,241,0.2)'; e.currentTarget.style.transform = 'scale(1)' }}
      >
        <Plus size={18} />
      </button>
    </div>
  )
}
