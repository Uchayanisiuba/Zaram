import { useState } from 'react'
import { ChevronRight, Cpu, Database, Mic, MessageSquare, Activity, X, Sparkles, Layers } from 'lucide-react'
import Orb from './Orb'

type OrbMode = 'idle' | 'thinking' | 'active'

const MEMORY_NODES = [
  { label: 'Project Context', value: '84%', color: '#6366f1' },
  { label: 'Conversation', value: '61%', color: '#06b6d4' },
  { label: 'Knowledge', value: '48%', color: '#10b981' },
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
        background: 'rgba(8,10,14,0.7)',
        backdropFilter: 'blur(30px)',
        borderLeft: '1px solid rgba(255,255,255,0.06)',
        flexShrink: 0,
        animation: 'slide-in-right 0.3s ease',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div style={{
        padding: '14px 16px 12px',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Sparkles size={13} style={{ color: '#818cf8' }} />
          <span style={{ fontSize: 12, fontWeight: 600, color: '#818cf8', letterSpacing: '0.04em', fontFamily: "'Space Grotesk', sans-serif" }}>
            Intelligence
          </span>
        </div>
        <div style={{
          fontSize: 10,
          padding: '2px 8px',
          borderRadius: 99,
          background: 'rgba(99,102,241,0.15)',
          border: '1px solid rgba(99,102,241,0.25)',
          color: '#818cf8',
          fontWeight: 600,
          letterSpacing: '0.04em',
        }}>
          LIVE
        </div>
      </div>

      <div className="scroll-area" style={{ flex: 1, padding: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>

        {/* Orb */}
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 12,
          padding: '20px 0 12px',
        }}>
          <Orb size="lg" mode={orbMode} />
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: '#e2e4ee', fontFamily: "'Space Grotesk', sans-serif" }}>
              Zara
            </div>
            <div style={{ fontSize: 11, color: '#6b7099', marginTop: 2 }}>
              {orbMode === 'thinking' ? 'Analyzing context…' : orbMode === 'active' ? 'Processing' : 'Ready'}
            </div>
          </div>

          {/* Thinking bar */}
          {orbMode === 'thinking' && (
            <div style={{ width: '100%', padding: '0 8px' }}>
              <div style={{ height: 2, background: 'rgba(255,255,255,0.06)', borderRadius: 1, overflow: 'hidden' }}>
                <div style={{
                  height: '100%',
                  background: 'linear-gradient(90deg, #6366f1, #22d3ee)',
                  animation: 'thinking-bar 2s ease-in-out infinite',
                  borderRadius: 1,
                }} />
              </div>
            </div>
          )}
        </div>

        {/* Memory status */}
        <Section icon={<Database size={12} />} label="Memory">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {MEMORY_NODES.map(node => (
              <div key={node.label}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
                  <span style={{ fontSize: 11, color: '#6b7099' }}>{node.label}</span>
                  <span style={{ fontSize: 11, color: '#b0b4cc', fontFamily: "'JetBrains Mono', monospace" }}>{node.value}</span>
                </div>
                <div style={{ height: 2, background: 'rgba(255,255,255,0.06)', borderRadius: 1, overflow: 'hidden' }}>
                  <div style={{
                    height: '100%',
                    width: node.value,
                    background: node.color,
                    borderRadius: 1,
                    boxShadow: `0 0 6px ${node.color}`,
                    transition: 'width 1s ease',
                  }} />
                </div>
              </div>
            ))}
          </div>
        </Section>

        {/* Reasoning steps */}
        <Section icon={<Cpu size={12} />} label="Reasoning">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {REASONING_STEPS.map((step, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{
                  width: 14,
                  height: 14,
                  borderRadius: '50%',
                  border: `1.5px solid ${step.done ? '#6366f1' : 'rgba(255,255,255,0.15)'}`,
                  background: step.done ? 'rgba(99,102,241,0.2)' : 'transparent',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  animation: !step.done ? 'pulse-dot 1.5s ease-in-out infinite' : 'none',
                }}>
                  {step.done && <span style={{ color: '#818cf8', fontSize: 8 }}>✓</span>}
                </div>
                <span style={{
                  fontSize: 11,
                  color: step.done ? '#b0b4cc' : '#6b7099',
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
        <Section icon={<Activity size={12} />} label="Agents">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {ACTIVE_AGENTS.map(agent => (
              <div key={agent.name} style={{
                padding: '8px 10px',
                borderRadius: 8,
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.06)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                  <span style={{ fontSize: 11, color: '#b0b4cc', fontFamily: "'JetBrains Mono', monospace" }}>{agent.name}</span>
                  <StatusDot status={agent.status} />
                </div>
                <div style={{ height: 1.5, background: 'rgba(255,255,255,0.06)', borderRadius: 1, overflow: 'hidden' }}>
                  <div style={{
                    height: '100%',
                    width: `${agent.progress}%`,
                    background: agent.status === 'running'
                      ? 'linear-gradient(90deg, #6366f1, #22d3ee)'
                      : 'rgba(255,255,255,0.2)',
                    borderRadius: 1,
                    animation: agent.status === 'running' ? 'gradient-flow 3s ease infinite' : 'none',
                    backgroundSize: '200% 200%',
                  }} />
                </div>
              </div>
            ))}
          </div>
        </Section>

        {/* Active context */}
        <Section icon={<Layers size={12} />} label="Context">
          <div style={{
            padding: '10px 12px',
            borderRadius: 8,
            background: 'rgba(99,102,241,0.06)',
            border: '1px solid rgba(99,102,241,0.15)',
          }}>
            <div style={{ fontSize: 11, color: '#818cf8', fontWeight: 600, marginBottom: 6 }}>zaram-core</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              {['src/runtime/', 'packages/ai/', 'packages/memory/'].map(path => (
                <span key={path} style={{ fontSize: 10, color: '#6b7099', fontFamily: "'JetBrains Mono', monospace" }}>{path}</span>
              ))}
            </div>
          </div>
        </Section>
      </div>

      {/* Voice controls */}
      <div style={{
        padding: '12px 16px',
        borderTop: '1px solid rgba(255,255,255,0.06)',
        display: 'flex',
        alignItems: 'center',
        gap: 10,
      }}>
        <button
          onClick={() => setVoiceActive(v => !v)}
          style={{
            width: 36,
            height: 36,
            borderRadius: '50%',
            border: `1.5px solid ${voiceActive ? '#6366f1' : 'rgba(255,255,255,0.1)'}`,
            background: voiceActive ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.04)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            color: voiceActive ? '#818cf8' : '#6b7099',
            boxShadow: voiceActive ? '0 0 16px rgba(99,102,241,0.4)' : 'none',
            transition: 'all 0.2s',
            animation: voiceActive ? 'orb-breathe 1.5s ease-in-out infinite' : 'none',
          }}
        >
          <Mic size={14} />
        </button>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 11, color: voiceActive ? '#818cf8' : '#6b7099', fontWeight: 500 }}>
            {voiceActive ? 'Listening…' : 'Voice Ready'}
          </div>
          <div style={{ fontSize: 10, color: '#3a3f5c' }}>Press to speak</div>
        </div>
        <button style={{
          width: 28,
          height: 28,
          borderRadius: 6,
          background: 'rgba(255,255,255,0.04)',
          border: '1px solid rgba(255,255,255,0.06)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          color: '#6b7099',
        }}>
          <MessageSquare size={13} />
        </button>
      </div>
    </aside>
  )
}

function Section({ icon, label, children }: { icon: React.ReactNode; label: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
        <span style={{ color: '#6b7099' }}>{icon}</span>
        <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.08em', color: '#4a4f6a', textTransform: 'uppercase' }}>{label}</span>
      </div>
      {children}
    </div>
  )
}

function StatusDot({ status }: { status: string }) {
  const colors: Record<string, string> = { running: '#10b981', idle: '#3a3f5c', error: '#f87171' }
  const color = colors[status] ?? '#3a3f5c'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
      <div style={{
        width: 6,
        height: 6,
        borderRadius: '50%',
        background: color,
        boxShadow: `0 0 5px ${color}`,
        animation: status === 'running' ? 'pulse-dot 1.5s ease-in-out infinite' : 'none',
      }} />
      <span style={{ fontSize: 10, color: '#6b7099', fontFamily: "'JetBrains Mono', monospace" }}>{status}</span>
    </div>
  )
}
