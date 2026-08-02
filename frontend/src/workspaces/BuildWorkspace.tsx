import { useState } from 'react'
import { ChevronRight, ChevronDown, File, Folder, FolderOpen, Terminal as TerminalIcon, Sparkles, Plus, Circle } from 'lucide-react'

const FILE_TREE = [
  { name: 'zaram-core', type: 'folder', open: true, children: [
    { name: 'src', type: 'folder', open: true, children: [
      { name: 'runtime', type: 'folder', open: false, children: [
        { name: 'engine.ts', type: 'file', active: false },
        { name: 'scheduler.ts', type: 'file', active: false },
      ]},
      { name: 'ai', type: 'folder', open: true, children: [
        { name: 'provider.ts', type: 'file', active: true },
        { name: 'context.ts', type: 'file', active: false },
        { name: 'memory.ts', type: 'file', active: false },
      ]},
      { name: 'index.ts', type: 'file', active: false },
    ]},
    { name: 'package.json', type: 'file', active: false },
  ]},
]

const CODE = `import { AIProvider, ModelConfig } from './types'
import { ContextManager } from './context'
import { MemoryStore } from './memory'

export class ZaramAIProvider implements AIProvider {
  private context: ContextManager
  private memory: MemoryStore
  private config: ModelConfig

  constructor(config: ModelConfig) {
    this.config = config
    this.context = new ContextManager({ maxTokens: 128_000 })
    this.memory = new MemoryStore({ vectorDimensions: 1536 })
  }

  async generate(prompt: string): Promise<string> {
    const relevantMemory = await this.memory.query(prompt, {
      limit: 12,
      threshold: 0.82,
    })

    const enrichedContext = this.context.enrich({
      prompt,
      memory: relevantMemory,
      systemInstructions: this.config.systemPrompt,
    })

    return await this.streamCompletion(enrichedContext)
  }

  private async streamCompletion(context: string): Promise<string> {
    // Local inference via GGUF runtime
    const stream = await this.config.model.createCompletion({
      prompt: context,
      maxTokens: this.config.maxOutputTokens,
      temperature: this.config.temperature ?? 0.7,
      stream: true,
    })

    let result = ''
    for await (const chunk of stream) {
      result += chunk.text
      this.emit('token', chunk.text)
    }

    await this.memory.store({ input: context, output: result })
    return result
  }
}`

const AI_SUGGESTIONS = [
  { type: 'optimize', text: 'Add error boundary for stream failures', line: 32 },
  { type: 'refactor', text: 'Extract stream handler to separate method', line: 38 },
  { type: 'docs', text: 'Document ModelConfig interface fields', line: 4 },
]

const TABS = [
  { name: 'provider.ts', modified: true },
  { name: 'context.ts', modified: false },
  { name: 'memory.ts', modified: false },
]

export default function BuildWorkspace() {
  const [terminalOpen, setTerminalOpen] = useState(true)
  const [activeTab, setActiveTab] = useState(0)

  return (
    <div style={{ flex: 1, display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* File tree */}
      <div style={{
        width: 220,
        height: '100%',
        background: 'rgba(8,10,14,0.6)',
        borderRight: '1px solid var(--color-border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
      }}>
        <div style={{
          padding: '12px 12px 8px',
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: '0.08em',
          color: 'var(--color-text-faint)',
          textTransform: 'uppercase',
          borderBottom: '1px solid var(--color-glass)',
        }}>
          Explorer
        </div>
        <div className="scroll-area" style={{ flex: 1, padding: '8px 0' }}>
          <TreeNode node={FILE_TREE[0]} depth={0} />
        </div>
      </div>

      {/* Main editor area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Tabs */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          background: 'rgba(8,10,14,0.8)',
          borderBottom: '1px solid var(--color-border-subtle)',
          paddingLeft: 8,
        }}>
          {TABS.map((tab, i) => (
            <button
              key={tab.name}
              onClick={() => setActiveTab(i)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '9px 14px',
                borderRadius: 0,
                background: activeTab === i ? 'rgba(255,255,255,0.05)' : 'transparent',
                border: 'none',
                borderBottom: `2px solid ${activeTab === i ? 'var(--color-indigo)' : 'transparent'}`,
                cursor: 'pointer',
                color: activeTab === i ? 'var(--color-text)' : 'var(--color-text-muted)',
                fontSize: 12,
                fontFamily: "var(--font-mono)",
                transition: 'all 0.15s',
              }}
            >
              {tab.modified && (
                <Circle size={6} fill="var(--color-indigo)" style={{ color: 'var(--color-indigo)' }} />
              )}
              {tab.name}
            </button>
          ))}
          <button style={{
            marginLeft: 4,
            width: 28,
            height: 28,
            borderRadius: 6,
            background: 'transparent',
            border: 'none',
            cursor: 'pointer',
            color: 'var(--color-text-secondary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            <Plus size={13} />
          </button>
        </div>

        {/* Editor + AI sidebar */}
        <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
          {/* Code editor */}
          <div
            className="scroll-area"
            style={{
              flex: 1,
              padding: '16px 0',
              overflowY: 'auto',
              fontFamily: "var(--font-mono)",
              fontSize: 13,
              lineHeight: 1.7,
            }}
          >
            {CODE.split('\n').map((line, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  paddingInline: '16px 24px',
                  background: AI_SUGGESTIONS.some(s => s.line === i + 1)
                    ? 'rgba(99,102,241,0.06)'
                    : 'transparent',
                  borderLeft: AI_SUGGESTIONS.some(s => s.line === i + 1)
                    ? '2px solid rgba(99,102,241,0.4)'
                    : '2px solid transparent',
                }}
              >
                <span style={{ color: 'var(--color-text-faint)', minWidth: 36, userSelect: 'none', fontSize: 11 }}>
                  {i + 1}
                </span>
                <CodeLine line={line} />
              </div>
            ))}
          </div>

          {/* AI suggestions panel */}
          <div style={{
            width: 240,
            borderLeft: '1px solid var(--color-border-subtle)',
            background: 'rgba(8,10,14,0.5)',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
          }}>
            <div style={{
              padding: '12px 14px 10px',
              borderBottom: '1px solid var(--color-border-subtle)',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}>
              <Sparkles size={12} style={{ color: 'var(--color-indigo-light)' }} />
              <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--color-indigo-light)', fontFamily: "var(--font-display)" }}>
                AI Suggestions
              </span>
            </div>
            <div className="scroll-area" style={{ flex: 1, padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
              {AI_SUGGESTIONS.map((s, i) => (
                <div key={i} style={{
                  padding: '10px 12px',
                  borderRadius: 8,
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid var(--color-glass-hover)',
                  cursor: 'pointer',
                  transition: 'all 0.15s',
                }}
                onMouseEnter={e => { e.currentTarget.style.background = 'rgba(99,102,241,0.08)'; e.currentTarget.style.borderColor = 'rgba(99,102,241,0.2)' }}
                onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.03)'; e.currentTarget.style.borderColor = 'var(--color-glass-hover)' }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                    <SuggestionBadge type={s.type} />
                    <span style={{ fontSize: 9, color: 'var(--color-text-faint)', fontFamily: "var(--font-mono)" }}>
                      L{s.line}
                    </span>
                  </div>
                  <p style={{ fontSize: 11, color: '#b0b4cc', margin: 0, lineHeight: 1.5 }}>{s.text}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Terminal drawer */}
        <div style={{
          height: terminalOpen ? 160 : 36,
          borderTop: '1px solid var(--color-border-subtle)',
          background: 'rgba(4,6,10,0.9)',
          transition: 'height 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
          flexShrink: 0,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '7px 12px',
              borderBottom: terminalOpen ? '1px solid var(--color-glass)' : 'none',
              cursor: 'pointer',
              flexShrink: 0,
            }}
            onClick={() => setTerminalOpen(o => !o)}
          >
            <TerminalIcon size={12} style={{ color: 'var(--color-emerald)' }} />
            <span style={{ fontSize: 11, color: 'var(--color-text-muted)', fontWeight: 500, fontFamily: "var(--font-mono)" }}>
              Terminal
            </span>
            <div style={{ marginLeft: 'auto', display: 'flex', gap: 4 }}>
              <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--color-red)' }} />
              <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--color-amber)' }} />
              <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--color-emerald)' }} />
            </div>
          </div>
          {terminalOpen && (
            <div style={{ flex: 1, padding: '8px 16px', fontFamily: "var(--font-mono)", fontSize: 12, overflowY: 'auto' }}>
              <TermLine prompt="$" cmd="pnpm build" />
              <TermLine text="  ✓ TypeScript compiled in 0.8s" color="var(--color-emerald)" />
              <TermLine text="  ✓ Bundle: 142kb (gzip: 48kb)" color="var(--color-emerald)" />
              <TermLine text="  ✓ Memory index updated" color="var(--color-emerald)" />
              <TermLine prompt="$" cmd="" />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function TreeNode({ node, depth }: { node: any; depth: number }) {
  const [open, setOpen] = useState<boolean>(node.open ?? false)
  if (node.type === 'folder') {
    return (
      <div>
        <button
          onClick={() => setOpen(o => !o)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            padding: `4px 8px 4px ${8 + depth * 14}px`,
            width: '100%',
            background: 'transparent',
            border: 'none',
            cursor: 'pointer',
            color: 'var(--color-text-muted)',
            fontSize: 12,
            transition: 'all 0.1s',
          }}
          onMouseEnter={e => { e.currentTarget.style.background = 'var(--color-glass)'; e.currentTarget.style.color = 'var(--color-text)' }}
          onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--color-text-muted)' }}
        >
          {open ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
          {open ? <FolderOpen size={13} style={{ color: 'var(--color-amber)' }} /> : <Folder size={13} style={{ color: 'var(--color-amber)' }} />}
          <span>{node.name}</span>
        </button>
        {open && node.children?.map((child: any, i: number) => (
          <TreeNode key={i} node={child} depth={depth + 1} />
        ))}
      </div>
    )
  }
  return (
    <button
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        padding: `4px 8px 4px ${22 + depth * 14}px`,
        width: '100%',
        background: node.active ? 'rgba(99,102,241,0.12)' : 'transparent',
        border: 'none',
        borderLeft: node.active ? '2px solid var(--color-indigo)' : '2px solid transparent',
        cursor: 'pointer',
        color: node.active ? 'var(--color-text)' : 'var(--color-text-muted)',
        fontSize: 12,
        fontFamily: "var(--font-mono)",
        transition: 'all 0.1s',
      }}
      onMouseEnter={e => { if (!node.active) { e.currentTarget.style.background = 'var(--color-glass)'; e.currentTarget.style.color = 'var(--color-text)' }}}
      onMouseLeave={e => { if (!node.active) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--color-text-muted)' }}}
    >
      <File size={12} style={{ color: 'var(--color-text-secondary)' }} />
      {node.name}
    </button>
  )
}

const KEYWORDS = ['import', 'export', 'class', 'implements', 'constructor', 'private', 'async', 'await', 'return', 'for', 'const', 'let', 'new', 'this', 'true', 'false', 'from', 'of']
const TYPES = ['AIProvider', 'ModelConfig', 'ContextManager', 'MemoryStore', 'string', 'Promise', 'number']

function CodeLine({ line }: { line: string }) {
  const words = line.split(/(\s+|[{}()[\],.:;<>?!|&=+\-*/])/g)
  return (
    <span>
      {words.map((word, i) => {
        let color = '#c8ccd8'
        if (KEYWORDS.includes(word)) color = 'var(--color-indigo-light)'
        else if (TYPES.includes(word)) color = '#22d3ee'
        else if (word.startsWith("'") || word.startsWith('"') || word.startsWith('`')) color = '#86efac'
        else if (/^\d+/.test(word)) color = '#fb923c'
        else if (word.startsWith('//')) color = 'var(--color-text-secondary)'
        else if (['(', ')', '{', '}', '[', ']'].includes(word)) color = 'var(--color-text)'
        return <span key={i} style={{ color }}>{word}</span>
      })}
    </span>
  )
}

function SuggestionBadge({ type }: { type: string }) {
  const colors: Record<string, [string, string]> = {
    optimize: ['var(--color-emerald)', 'rgba(16,185,129,0.15)'],
    refactor: ['var(--color-indigo)', 'rgba(99,102,241,0.15)'],
    docs: ['var(--color-amber)', 'rgba(245,158,11,0.15)'],
  }
  const [color, bg] = colors[type] ?? ['var(--color-text-muted)', 'rgba(107,112,153,0.1)']
  return (
    <span style={{
      fontSize: 9,
      fontWeight: 700,
      padding: '1px 6px',
      borderRadius: 3,
      background: bg,
      color,
      textTransform: 'uppercase',
      letterSpacing: '0.06em',
    }}>
      {type}
    </span>
  )
}

function TermLine({ prompt, cmd, text, color }: { prompt?: string; cmd?: string; text?: string; color?: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, lineHeight: 1.8 }}>
      {prompt && <span style={{ color: 'var(--color-emerald)' }}>{prompt}</span>}
      {cmd != null && (
        <span style={{ color: 'var(--color-text)' }}>
          {cmd}
          {cmd === '' && <span style={{ animation: 'blink-cursor 1s step-end infinite', color: 'var(--color-emerald)' }}>▋</span>}
        </span>
      )}
      {text && <span style={{ color: color ?? 'var(--color-text-muted)' }}>{text}</span>}
    </div>
  )
}
