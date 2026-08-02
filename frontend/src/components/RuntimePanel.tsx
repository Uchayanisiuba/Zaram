import { useState } from 'react'
import { Cpu, Database, Mic, MessageSquare, Activity, Sparkles, Layers } from 'lucide-react'
import LivingOrb from './orb/LivingOrb'

type OrbMode = 'idle' | 'thinking' | 'active'

const MEMORY_NODES = [
  { label: 'Project Context', value: '84%', color: 'var(--color-indigo)' },
  { label: 'Conversation', value: '61%', color: 'var(--color-cyan)' },
  { label: 'Knowledge', value: '48%', color: 'var(--color-emerald)' },
]

const ACTIVE_AGENTS = [
  { name: 'code-reviewer', status: 'running', progress: 72 },
  { name: 'memory-sync', status: 'idle', progress: 100 },
]

const REASONING_STEPS = [
  { text: 'Analyzing project structure', done: true },
  { text: 'Indexing TypeScript types', done: true },
  { text: 'Identifying optimization paths', done: false },
]

export default function RuntimePanel() {
  const [orbMode] = useState<OrbMode>('thinking')
  const [voiceActive, setVoiceActive] = useState(false)

  return (
    <aside
      style={{
        width: 292,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--surface-panel)',
        backdropFilter: 'blur(30px)',
        borderLeft: '1px solid var(--color-border-subtle)',
        flexShrink: 0,
        animation: 'slide-in-right 0.3s ease',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div style={{
        padding: '14px 16px 12px',
        borderBottom: '1px solid var(--color-border-subtle)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Sparkles size={26} style={{ color: 'var(--color-indigo-light)' }} />
          <span style={{ fontSize: 'var(--text-h1)', fontWeight: 600, color: 'var(--color-indigo-light)', letterSpacing: '0.04em', fontFamily: 'var(--font-display)' }}>
            Intelligence
          </span>
        </div>
        <div style={{
          fontSize: 'var(--text-h2)',
          padding: '2px 8px',
          borderRadius: 99,
          background: 'var(--color-indigo-a-15)',
          border: '1px solid var(--color-indigo-a-25)',
          color: 'var(--color-indigo-light)',
          fontWeight: 600,
          letterSpacing: '0.04em',
        }}>
          LIVE
        </div>
      </div>

      <div className="scroll-area" style={{ flex: 1, padding: 32, display: 'flex', flexDirection: 'column', gap: 16 }}>

        {/* Orb */}
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 24,
          padding: '20px 0 12px',
        }}>
          <LivingOrb size="lg" />
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 'var(--text-h1)', fontWeight: 600, color: 'var(--color-text)', fontFamily: 'var(--font-display)' }}>
              Zara
            </div>
            <div style={{ fontSize: 'var(--text-h2)', color: 'var(--color-text-muted)', marginTop: 2 }}>
              {orbMode === 'thinking' ? 'Analyzing context…' : orbMode === 'active' ? 'Processing' : 'Ready'}
            </div>
          </div>

          {/* Thinking bar */}
          {orbMode === 'thinking' && (
            <div style={{ width: '100%', padding: '0 8px' }}>
              <div style={{ height: 4, background: 'var(--color-border-subtle)', borderRadius: 2, overflow: 'hidden' }}>
                <div style={{
                  height: '100%',
                  background: 'linear-gradient(90deg, var(--color-indigo), var(--color-cyan-light))',
                  animation: 'thinking-bar 2s ease-in-out infinite',
                  borderRadius: 2,
                }} />
              </div>
            </div>
          )}
        </div>

        {/* Memory status */}
        <Section icon={<Database size={24} />} label="Memory">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {MEMORY_NODES.map(node => (
              <div key={node.label}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
                  <span style={{ fontSize: 'var(--text-h2)', color: 'var(--color-text-muted)' }}>{node.label}</span>
                  <span style={{ fontSize: 'var(--text-h2)', color: 'var(--color-text-muted-light)', fontFamily: 'var(--font-mono)' }}>{node.value}</span>
                </div>
                <div style={{ height: 4, background: 'var(--color-border-subtle)', borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{
                    height: '100%',
                    width: node.value,
                    background: node.color,
                    borderRadius: 2,
                    boxShadow: `0 0 6px ${node.color}`,
                    transition: 'width 1s ease',
                  }} />
                </div>
              </div>
            ))}
          </div>
        </Section>

        {/* Reasoning steps */}
        <Section icon={<Cpu size={24} />} label="Reasoning">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {REASONING_STEPS.map((step, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{
                  width: 28,
                  height: 28,
                  borderRadius: '50%',
                   border: `1.5px solid ${step.done ? 'var(--color-indigo)' : 'var(--color-border-glass-strong)'}`,
                  background: step.done ? 'var(--color-indigo-a-20)' : 'transparent',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  animation: !step.done ? 'pulse-dot 1.5s ease-in-out infinite' : 'none',
                }}>
                  {step.done && <span style={{ color: 'var(--color-indigo-light)', fontSize: 8 }}>✓</span>}
                </div>
                <span style={{
                  fontSize: 'var(--text-h2)',
                  color: step.done ? 'var(--color-text-faint)' : 'var(--color-text-muted)',
                  fontStyle: !step.done ? 'italic' : 'normal',
                }}>
                  {step.text}
                  {!step.done && <span style={{ animation: 'blink-cursor 1s step-end infinite', marginLeft: 1 }}>|</span>}
                </span>
              </div>
            ))}
          </div>
        </Section>

        {/* Active agents */}
        <Section icon={<Activity size={24} />} label="Agents">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {ACTIVE_AGENTS.map(agent => (
              <div key={agent.name} style={{
                padding: '8px 10px',
                borderRadius: 8,
                background: 'var(--color-glass)',
                border: '1px solid var(--color-border-subtle)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                  <span style={{ fontSize: 'var(--text-h2)', color: 'var(--color-text-muted-light)', fontFamily: 'var(--font-mono)' }}>{agent.name}</span>
                  <StatusDot status={agent.status} />
                </div>
                <div style={{ height: 1.5, background: 'var(--color-border-subtle)', borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{
                    height: '100%',
                    width: `${agent.progress}%`,
                    background: agent.status === 'running'
                      ? 'linear-gradient(90deg, var(--color-indigo), var(--color-cyan-light))'
                      : 'var(--color-border-glass-strong)',
                    borderRadius: 2,
                    animation: agent.status === 'running' ? 'gradient-flow 3s ease infinite' : 'none',
                    backgroundSize: '200% 200%',
                  }} />
                </div>
              </div>
            ))}
          </div>
        </Section>

        {/* Active context */}
        <Section icon={<Layers size={24} />} label="Context">
          <div style={{
            padding: '10px 12px',
            borderRadius: 8,
            background: 'var(--color-indigo-a-06)',
            border: '1px solid var(--color-indigo-a-15)',
          }}>
            <div style={{ fontSize: 'var(--text-h2)', color: 'var(--color-indigo-light)', fontWeight: 600, marginBottom: 6 }}>zaram-core</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              {['src/runtime/', 'packages/ai/', 'packages/memory/'].map(path => (
                <span key={path} style={{ fontSize: 'var(--text-h2)', color: 'var(--color-text-muted)', fontFamily: 'var(--font-mono)' }}>{path}</span>
              ))}
            </div>
          </div>
        </Section>
      </div>

      {/* Voice controls */}
      <div style={{
        padding: '12px 16px',
        borderTop: '1px solid var(--color-border-subtle)',
        display: 'flex',
        alignItems: 'center',
        gap: 20,
      }}>
        <button
          onClick={() => setVoiceActive(v => !v)}
          style={{
            width: 72,
            height: 72,
            borderRadius: '50%',
            border: `1.5px solid ${voiceActive ? 'var(--color-indigo)' : 'var(--color-border-glass-strong)'}`,
            background: voiceActive ? 'var(--color-indigo-a-20)' : 'var(--color-glass)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            color: voiceActive ? 'var(--color-indigo-light)' : 'var(--color-text-muted)',
            boxShadow: voiceActive ? '0 0 16px var(--color-indigo-a-40)' : 'none',
            transition: 'all 0.2s',
            animation: voiceActive ? 'orb-breathe 1.5s ease-in-out infinite' : 'none',
          }}
        >
          <Mic size={28} />
        </button>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 'var(--text-h2)', color: voiceActive ? 'var(--color-indigo-light)' : 'var(--color-text-muted)', fontWeight: 500 }}>
            {voiceActive ? 'Listening…' : 'Voice Ready'}
          </div>
          <div style={{ fontSize: 'var(--text-h2)', color: 'var(--color-text-faint)' }}>Press to speak</div>
        </div>
        <button style={{
          width: 28,
          height: 28,
          borderRadius: 12,
          background: 'var(--color-glass)',
          border: '1px solid var(--color-border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          color: 'var(--color-text-muted)',
        }}>
          <MessageSquare size={26} />
        </button>
      </div>
    </aside>
  )
}

function Section({ icon, label, children }: { icon: React.ReactNode; label: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
        <span style={{ color: 'var(--color-text-muted)' }}>{icon}</span>
        <span style={{ fontSize: 'var(--text-h2)', fontWeight: 600, letterSpacing: '0.08em', color: 'var(--color-text-secondary)', textTransform: 'uppercase' }}>{label}</span>
      </div>
      {children}
    </div>
  )
}

function StatusDot({ status }: { status: string }) {
  const colors: Record<string, string> = { running: 'var(--color-emerald)', idle: 'var(--color-text-faint)', error: 'var(--color-red)' }
  const color = colors[status] ?? 'var(--color-text-faint)'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
      <div style={{
        width: 12,
        height: 12,
        borderRadius: '50%',
        background: color,
        boxShadow: `0 0 5px ${color}`,
        animation: status === 'running' ? 'pulse-dot 1.5s ease-in-out infinite' : 'none',
      }} />
      <span style={{ fontSize: 'var(--text-h2)', color: 'var(--color-text-muted)', fontFamily: 'var(--font-mono)' }}>{status}</span>
    </div>
  )
}
