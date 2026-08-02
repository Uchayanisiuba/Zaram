import { useState } from 'react'
import { Cpu, Brain, Mic, Puzzle, Paintbrush, Shield, SlidersHorizontal, ChevronRight } from 'lucide-react'

const CATEGORIES = [
  { id: 'ai', icon: <Cpu size={16} />, label: 'AI & Models', desc: 'Model selection, temperature, context' },
  { id: 'memory', icon: <Brain size={16} />, label: 'Memory', desc: 'Storage, retrieval, retention policy' },
  { id: 'voice', icon: <Mic size={16} />, label: 'Voice', desc: 'Hotword, language, noise settings' },
  { id: 'plugins', icon: <Puzzle size={16} />, label: 'Plugins', desc: 'Permissions, updates, sandboxing' },
  { id: 'appearance', icon: <Paintbrush size={16} />, label: 'Appearance', desc: 'Theme, density, motion' },
  { id: 'security', icon: <Shield size={16} />, label: 'Security', desc: 'Encryption, auth, audit log' },
  { id: 'advanced', icon: <SlidersHorizontal size={16} />, label: 'Advanced', desc: 'Runtime, logging, developer mode' },
]

const SETTINGS: Record<string, React.ReactNode> = {
  ai: <AISettings />,
  memory: <MemorySettings />,
  appearance: <AppearanceSettings />,
  voice: <VoiceSettings />,
  plugins: <PluginsSettings />,
  security: <SecuritySettings />,
  advanced: <AdvancedSettings />,
}

export default function SettingsWorkspace() {
  const [active, setActive] = useState('ai')

  return (
    <div style={{ flex: 1, display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* Category sidebar */}
      <div style={{
        width: 260,
        borderRight: '1px solid var(--color-border-subtle)',
        background: 'var(--surface-sidebar)',
        padding: '20px 12px',
        flexShrink: 0,
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
      }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-text)', fontFamily: "var(--font-display)", padding: '0 8px 16px' }}>
          Settings
        </div>
        {CATEGORIES.map(cat => (
          <button
            key={cat.id}
            onClick={() => setActive(cat.id)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '10px 12px',
              borderRadius: 10,
              background: active === cat.id ? 'rgba(99,102,241,0.12)' : 'transparent',
              border: `1px solid ${active === cat.id ? 'rgba(99,102,241,0.2)' : 'transparent'}`,
              cursor: 'pointer',
              color: active === cat.id ? 'var(--color-indigo-light)' : 'var(--color-text-muted)',
              textAlign: 'left',
              transition: 'all 0.15s',
              width: '100%',
            }}
            onMouseEnter={e => { if (active !== cat.id) { e.currentTarget.style.background = 'var(--color-glass)'; e.currentTarget.style.color = '#b0b4cc' }}}
            onMouseLeave={e => { if (active !== cat.id) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--color-text-muted)' }}}
          >
            <span style={{ color: active === cat.id ? 'var(--color-indigo-light)' : 'var(--color-text-secondary)' }}>{cat.icon}</span>
            <div>
              <div style={{ fontSize: 13, fontWeight: 500 }}>{cat.label}</div>
              <div style={{ fontSize: 11, color: 'var(--color-text-secondary)', marginTop: 1 }}>{cat.desc}</div>
            </div>
            {active === cat.id && <ChevronRight size={12} style={{ marginLeft: 'auto', color: 'var(--color-indigo)' }} />}
          </button>
        ))}
      </div>

      {/* Settings panel */}
      <div className="scroll-area" style={{ flex: 1, padding: 32, overflowY: 'auto', animation: 'fade-in 0.2s ease' }}>
        {SETTINGS[active]}
      </div>
    </div>
  )
}

function SectionHeader({ title, desc }: { title: string; desc?: string }) {
  return (
    <div style={{ marginBottom: 24 }}>
      <h2 style={{ fontFamily: "var(--font-display)", fontSize: 20, fontWeight: 700, color: 'var(--color-text)', margin: '0 0 6px', letterSpacing: '-0.01em' }}>
        {title}
      </h2>
      {desc && <p style={{ fontSize: 13, color: 'var(--color-text-muted)', margin: 0 }}>{desc}</p>}
    </div>
  )
}

function SettingCard({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      padding: 20,
      borderRadius: 12,
      background: 'rgba(255,255,255,0.03)',
      border: '1px solid var(--color-glass-hover)',
      marginBottom: 12,
      display: 'flex',
      flexDirection: 'column',
      gap: 16,
    }}>
      {children}
    </div>
  )
}

function SettingRow({ label, desc, control }: { label: string; desc?: string; control: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
      <div>
        <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--color-text)', marginBottom: desc ? 3 : 0 }}>{label}</div>
        {desc && <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>{desc}</div>}
      </div>
      {control}
    </div>
  )
}

function Toggle({ on, onChange }: { on: boolean; onChange: (v: boolean) => void }) {
  return (
    <div
      onClick={() => onChange(!on)}
      style={{
        width: 40,
        height: 22,
        borderRadius: 11,
        background: on ? 'var(--color-indigo)' : 'rgba(255,255,255,0.1)',
        border: `1px solid ${on ? '#4f46e5' : 'rgba(255,255,255,0.15)'}`,
        cursor: 'pointer',
        position: 'relative',
        transition: 'all 0.2s',
        boxShadow: on ? '0 0 10px rgba(99,102,241,0.4)' : 'none',
        flexShrink: 0,
      }}
    >
      <div style={{
        position: 'absolute',
        top: 2,
        left: on ? 20 : 2,
        width: 16,
        height: 16,
        borderRadius: '50%',
        background: '#fff',
        transition: 'left 0.2s',
        boxShadow: '0 1px 4px rgba(0,0,0,0.3)',
      }} />
    </div>
  )
}

function Select({ value, options }: { value: string; options: string[] }) {
  return (
    <select
      defaultValue={value}
      style={{
        background: 'var(--color-border-subtle)',
        border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: 7,
        color: 'var(--color-text)',
        padding: '5px 10px',
        fontSize: 12,
        cursor: 'pointer',
        outline: 'none',
        fontFamily: "var(--font-sans)",
      }}
    >
      {options.map(o => <option key={o} value={o}>{o}</option>)}
    </select>
  )
}

function AISettings() {
  const [streaming, setStreaming] = useState(true)
  const [caching, setCaching] = useState(true)
  const [tools, setTools] = useState(false)
  return (
    <div>
      <SectionHeader title="AI & Models" desc="Configure the language models and inference settings for Zaram." />
      <SettingCard>
        <SettingRow label="Primary Model" desc="Used for all general tasks" control={<Select value="Llama 3.1 70B" options={['Llama 3.1 70B', 'Llama 3.1 8B', 'Mistral 7B', 'Phi-3 Medium']} />} />
        <SettingRow label="Code Model" desc="Specialized for code generation" control={<Select value="DeepSeek Coder 33B" options={['DeepSeek Coder 33B', 'CodeLlama 34B', 'WizardCoder 34B']} />} />
        <SettingRow label="Embedding Model" desc="For memory and search" control={<Select value="nomic-embed-text" options={['nomic-embed-text', 'all-minilm-l6', 'text-embedding-3']} />} />
      </SettingCard>
      <SettingCard>
        <SettingRow label="Streaming responses" desc="Show tokens as they generate" control={<Toggle on={streaming} onChange={setStreaming} />} />
        <SettingRow label="Context caching" desc="Cache repeated context for speed" control={<Toggle on={caching} onChange={setCaching} />} />
        <SettingRow label="Tool use" desc="Allow AI to call system tools" control={<Toggle on={tools} onChange={setTools} />} />
      </SettingCard>
      <SettingCard>
        <SettingRow
          label="Temperature"
          desc="Controls response creativity (0.0–1.0)"
          control={
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <input type="range" min={0} max={100} defaultValue={70} style={{ width: 100, accentColor: 'var(--color-indigo)' }} />
              <span style={{ fontSize: 12, color: 'var(--color-indigo-light)', fontFamily: "var(--font-mono)", minWidth: 28 }}>0.7</span>
            </div>
          }
        />
        <SettingRow
          label="Max output tokens"
          desc="Maximum response length"
          control={<Select value="4096" options={['1024', '2048', '4096', '8192', '16384']} />}
        />
      </SettingCard>
    </div>
  )
}

function MemorySettings() {
  const [autoSync, setAutoSync] = useState(true)
  const [compress, setCompress] = useState(false)
  return (
    <div>
      <SectionHeader title="Memory" desc="Control how Zaram stores, retrieves, and manages your knowledge graph." />
      <SettingCard>
        <SettingRow label="Auto-sync" desc="Continuously index new memories" control={<Toggle on={autoSync} onChange={setAutoSync} />} />
        <SettingRow label="Compress old memories" desc="Summarize memories older than 30 days" control={<Toggle on={compress} onChange={setCompress} />} />
        <SettingRow label="Retention policy" control={<Select value="Forever" options={['7 days', '30 days', '90 days', '1 year', 'Forever']} />} />
      </SettingCard>
      <SettingCard>
        <SettingRow label="Vector dimensions" control={<Select value="1536" options={['384', '768', '1536', '3072']} />} />
        <SettingRow label="Index type" control={<Select value="HNSW" options={['HNSW', 'Flat', 'IVF-PQ']} />} />
        <SettingRow
          label="Similarity threshold"
          desc="Minimum relevance to surface a memory"
          control={
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <input type="range" min={0} max={100} defaultValue={82} style={{ width: 100, accentColor: 'var(--color-indigo)' }} />
              <span style={{ fontSize: 12, color: 'var(--color-indigo-light)', fontFamily: "var(--font-mono)" }}>0.82</span>
            </div>
          }
        />
      </SettingCard>
    </div>
  )
}

function AppearanceSettings() {
  const [motion, setMotion] = useState(true)
  const [particles, setParticles] = useState(true)
  return (
    <div>
      <SectionHeader title="Appearance" desc="Customize the visual experience of your Zaram interface." />
      <SettingCard>
        <SettingRow label="Theme" control={<Select value="Dark (default)" options={['Dark (default)', 'Light', 'System']} />} />
        <SettingRow label="Accent color" control={
          <div style={{ display: 'flex', gap: 6 }}>
            {['var(--color-indigo)', 'var(--color-cyan)', 'var(--color-emerald)', 'var(--color-violet)', 'var(--color-amber)'].map(c => (
              <div key={c} style={{ width: 20, height: 20, borderRadius: '50%', background: c, cursor: 'pointer', border: c === 'var(--color-indigo)' ? '2px solid #fff' : '2px solid transparent', boxShadow: c === 'var(--color-indigo)' ? `0 0 8px ${c}` : 'none' }} />
            ))}
          </div>
        } />
        <SettingRow label="Density" control={<Select value="Comfortable" options={['Compact', 'Comfortable', 'Spacious']} />} />
      </SettingCard>
      <SettingCard>
        <SettingRow label="Motion & animations" desc="Orb transitions, workspace animations" control={<Toggle on={motion} onChange={setMotion} />} />
        <SettingRow label="Orb particles" desc="Floating particle effects" control={<Toggle on={particles} onChange={setParticles} />} />
      </SettingCard>
    </div>
  )
}

function VoiceSettings() {
  const [enabled, setEnabled] = useState(true)
  return (
    <div>
      <SectionHeader title="Voice" desc="Configure voice commands and speech synthesis." />
      <SettingCard>
        <SettingRow label="Enable voice" control={<Toggle on={enabled} onChange={setEnabled} />} />
        <SettingRow label="Hotword" control={<Select value="Hey Zara" options={['Hey Zara', 'Zara', 'Hey Zaram', 'Custom…']} />} />
        <SettingRow label="Language" control={<Select value="English (US)" options={['English (US)', 'English (UK)', 'French', 'German', 'Spanish', 'Japanese']} />} />
      </SettingCard>
    </div>
  )
}

function PluginsSettings() {
  const [autoUpdate, setAutoUpdate] = useState(true)
  return (
    <div>
      <SectionHeader title="Plugins" desc="Manage plugin permissions and update settings." />
      <SettingCard>
        <SettingRow label="Auto-update plugins" control={<Toggle on={autoUpdate} onChange={setAutoUpdate} />} />
        <SettingRow label="Plugin sandbox" desc="Isolate plugins from system access" control={<Toggle on={true} onChange={() => {}} />} />
        <SettingRow label="Telemetry" desc="Allow anonymous usage stats" control={<Toggle on={false} onChange={() => {}} />} />
      </SettingCard>
    </div>
  )
}

function SecuritySettings() {
  return (
    <div>
      <SectionHeader title="Security" desc="Encryption, authentication, and access control." />
      <SettingCard>
        <SettingRow label="Encryption at rest" desc="AES-256 for local data" control={<Toggle on={true} onChange={() => {}} />} />
        <SettingRow label="Biometric unlock" control={<Toggle on={false} onChange={() => {}} />} />
        <SettingRow label="Session timeout" control={<Select value="30 minutes" options={['5 minutes', '15 minutes', '30 minutes', '1 hour', 'Never']} />} />
      </SettingCard>
    </div>
  )
}

function AdvancedSettings() {
  const [devMode, setDevMode] = useState(false)
  const [verbose, setVerbose] = useState(false)
  return (
    <div>
      <SectionHeader title="Advanced" desc="Developer tools and runtime configuration." />
      <SettingCard>
        <SettingRow label="Developer mode" desc="Expose debug panels and raw API" control={<Toggle on={devMode} onChange={setDevMode} />} />
        <SettingRow label="Verbose logging" desc="Log all AI calls to console" control={<Toggle on={verbose} onChange={setVerbose} />} />
        <SettingRow label="Log level" control={<Select value="Info" options={['Debug', 'Info', 'Warn', 'Error']} />} />
      </SettingCard>
      <SettingCard>
        <SettingRow label="Max concurrent agents" control={<Select value="4" options={['1', '2', '4', '8', '16']} />} />
        <SettingRow label="Runtime threads" control={<Select value="Auto" options={['Auto', '2', '4', '8', '16']} />} />
      </SettingCard>
    </div>
  )
}
