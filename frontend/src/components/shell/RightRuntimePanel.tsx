import { motion } from 'framer-motion';
import { Mic, MicOff, Volume2, MessageSquare, Cpu, Database } from 'lucide-react';
import { useOrbStore } from '@/stores';

const MEMORY_METRICS = [
  { label: 'Context Window', value: 68, color: '#6366f1' },
  { label: 'Recall Index',   value: 92, color: '#22d3ee' },
];

const CONTEXT_ITEMS = [
  { label: 'Current session',    icon: MessageSquare },
  { label: 'Local neural engine', icon: Cpu },
  { label: 'Knowledge graph',    icon: Database },
];

const STATE_LABELS: Record<string, string> = {
  idle:      'Ready',
  listening: 'Listening',
  thinking:  'Thinking',
  speaking:  'Speaking',
};

const STATE_COLORS: Record<string, string> = {
  idle:      '#34d399',
  listening: '#22d3ee',
  thinking:  '#c084fc',
  speaking:  '#34d399',
};

/** Minimal orb indicator shown in the right panel — driven by orbStore only */
const MiniOrbIndicator = ({ orbState }: { orbState: string }) => {
  const color = STATE_COLORS[orbState] ?? '#34d399';

  return (
    <div className="relative flex items-center justify-center" style={{ width: 56, height: 56 }}>
      {/* Outer glow ring */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: 56,
          height: 56,
          background: `radial-gradient(circle, ${color}22 0%, transparent 70%)`,
          filter: 'blur(8px)',
        }}
        animate={{ scale: [1, 1.15, 1], opacity: [0.7, 1, 0.7] }}
        transition={{ duration: orbState === 'thinking' ? 1.2 : 3, repeat: Infinity, ease: 'easeInOut' }}
      />
      {/* Inner orb */}
      <motion.div
        className="relative z-10 rounded-full"
        style={{
          width: 36,
          height: 36,
          background: `radial-gradient(circle, ${color}55 0%, ${color}22 60%, transparent 100%)`,
          border: `1px solid ${color}44`,
          boxShadow: `0 0 16px ${color}44`,
        }}
        animate={{ scale: [1, 1.06, 1] }}
        transition={{ duration: orbState === 'thinking' ? 1 : 3, repeat: Infinity, ease: 'easeInOut' }}
      />
      {/* Center dot */}
      <motion.div
        className="absolute rounded-full bg-white z-20"
        style={{ width: 6, height: 6, boxShadow: `0 0 8px rgba(255,255,255,0.8)` }}
        animate={{ opacity: [0.4, 0.9, 0.4], scale: [0.8, 1.2, 0.8] }}
        transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut' }}
      />
    </div>
  );
};

const RightRuntimePanel = () => {
  const { orbState, setOrbState } = useOrbStore();
  const stateColor = STATE_COLORS[orbState] ?? '#34d399';

  const handleToggleMic = () => {
    setOrbState(orbState === 'listening' ? 'idle' : 'listening');
  };

  return (
    <div
      className="fixed top-0 right-0 bottom-0 hidden xl:flex flex-col border-l overflow-y-auto scroll-thin"
      style={{
        width: 'var(--right-panel-width)',
        paddingTop: 'var(--nav-height)',
        background: 'rgba(6,7,9,0.60)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        borderColor: 'var(--glass-border)',
        zIndex: 'var(--z-rail)',
        scrollbarWidth: 'none',
      }}
    >
      {/* Header */}
      <div className="px-4 py-3 border-b shrink-0" style={{ borderColor: 'var(--glass-border)' }}>
        <p className="text-xs text-slate-600 uppercase" style={{ letterSpacing: '0.10em' }}>
          AI Runtime
        </p>
      </div>

      {/* Mini orb + status */}
      <div className="flex flex-col items-center py-8 border-b shrink-0" style={{ borderColor: 'var(--glass-border)' }}>
        <MiniOrbIndicator orbState={orbState} />
        <div className="mt-4 flex items-center gap-2">
          <motion.div
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: stateColor }}
            animate={{ opacity: [1, 0.3, 1] }}
            transition={{ duration: 2, repeat: Infinity }}
          />
          <span className="text-xs text-slate-500">{STATE_LABELS[orbState] ?? 'Ready'}</span>
        </div>
      </div>

      {/* Content sections */}
      <div className="px-4 py-5 space-y-6">

        {/* Memory metrics */}
        <section>
          <p className="text-xs text-slate-700 uppercase mb-3" style={{ letterSpacing: '0.08em' }}>
            Memory
          </p>
          {MEMORY_METRICS.map((metric) => (
            <div key={metric.label} className="mb-3">
              <div className="flex justify-between mb-1.5">
                <span className="text-xs text-slate-600">{metric.label}</span>
                <span
                  className="text-xs text-slate-600"
                  style={{ fontVariantNumeric: 'tabular-nums' }}
                >
                  {metric.value}%
                </span>
              </div>
              <div
                className="h-0.5 rounded-full overflow-hidden"
                style={{ background: 'rgba(255,255,255,0.06)' }}
              >
                <motion.div
                  className="h-full rounded-full"
                  style={{
                    background: `linear-gradient(to right, ${metric.color}, rgba(34,211,238,0.8))`,
                  }}
                  initial={{ width: 0 }}
                  animate={{ width: `${metric.value}%` }}
                  transition={{ duration: 1.4, ease: 'easeOut' }}
                />
              </div>
            </div>
          ))}
        </section>

        {/* Active context */}
        <section>
          <p className="text-xs text-slate-700 uppercase mb-3" style={{ letterSpacing: '0.08em' }}>
            Active Context
          </p>
          <div className="space-y-2">
            {CONTEXT_ITEMS.map((item) => (
              <div key={item.label} className="flex items-center gap-2.5 py-1.5">
                <item.icon className="w-3 h-3 text-slate-700" />
                <span className="text-xs text-slate-600">{item.label}</span>
              </div>
            ))}
          </div>
        </section>

        {/* Agents */}
        <section>
          <p className="text-xs text-slate-700 uppercase mb-3" style={{ letterSpacing: '0.08em' }}>
            Agents
          </p>
          <div
            className="rounded-xl p-3 flex items-center gap-2.5"
            style={{
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.05)',
            }}
          >
            <motion.div
              className="w-1.5 h-1.5 rounded-full bg-emerald-400"
              animate={{ scale: [1, 1.4, 1] }}
              transition={{ duration: 1.5, repeat: Infinity }}
            />
            <span className="text-xs text-slate-500">Core agent active</span>
          </div>
        </section>

        {/* Voice controls */}
        <section>
          <p className="text-xs text-slate-700 uppercase mb-3" style={{ letterSpacing: '0.08em' }}>
            Voice
          </p>
          <div className="flex gap-2">
            <button
              onClick={handleToggleMic}
              className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-xs transition-all"
              style={
                orbState === 'listening'
                  ? {
                      background: 'rgba(239,68,68,0.15)',
                      border: '1px solid rgba(239,68,68,0.30)',
                      color: '#f87171',
                    }
                  : {
                      background: 'rgba(255,255,255,0.04)',
                      border: '1px solid rgba(255,255,255,0.07)',
                      color: '#64748b',
                    }
              }
            >
              {orbState === 'listening' ? (
                <MicOff className="w-3 h-3" />
              ) : (
                <Mic className="w-3 h-3" />
              )}
              {orbState === 'listening' ? 'Stop' : 'Input'}
            </button>
            <button
              className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-xs transition-all"
              style={{
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.07)',
                color: '#64748b',
              }}
            >
              <Volume2 className="w-3 h-3" />
              Output
            </button>
          </div>
        </section>

      </div>
    </div>
  );
};

export default RightRuntimePanel;
