import { useEmbodimentStore } from '@/stores/embodimentStore'
import { useOrbStore, type OrbState } from '@/stores/orbStore'
import { useEmbodimentState } from '@/hooks/useEmbodimentState'

/**
 * Spike scaffolding — **not shipped UI**.
 *
 * Two jobs, both temporary. It switches renderer so the orb and the avatar can
 * be compared side by side, and it drives the states by hand because nothing
 * else can yet: `swapping` is set by the backend pre-flight during a real model
 * load, and `speaking` by a TTS path that has to be driven end to end to see.
 * Without this the avatar could only ever be observed idle, which answers none
 * of the questions the spike exists to ask.
 *
 * The shipped renderer toggle belongs in Settings, greyed out with the reason
 * where the hardware cannot take it, and naming the download before it happens
 * — the same honesty as the pack catalogue. See `docs/EMBODIMENT-SPIKE.md`.
 * Delete this file when that lands, or when the spike is binned.
 *
 * It sets `orbStore` directly rather than going through
 * `systemStore.beginModelSwap`, which the orb path must never do — the orb and
 * its label are two renderings of one fact. That is tolerable *here* only
 * because this is a bench for looking at the renderer, not a path a user
 * reaches. It is the reason this file is quarantined rather than tidy.
 */
const STATES: OrbState[] = ['idle', 'thinking', 'listening', 'speaking', 'swapping']

export default function EmbodimentSpikeControls() {
  const renderer = useEmbodimentStore((s) => s.renderer)
  const setRenderer = useEmbodimentStore((s) => s.setRenderer)
  const setOrbState = useOrbStore((s) => s.setOrbState)
  const orbState = useOrbStore((s) => s.orbState)
  const derived = useEmbodimentState()

  const chip = (active: boolean) =>
    ({
      padding: '3px 9px',
      borderRadius: 6,
      fontSize: 11,
      cursor: 'pointer',
      border: `1px solid ${active ? 'rgba(120,220,240,0.55)' : 'rgba(255,255,255,0.12)'}`,
      background: active ? 'rgba(120,220,240,0.14)' : 'rgba(255,255,255,0.04)',
      color: active ? '#78dcf0' : '#94a3b8',
    }) as const

  return (
    <div
      className="absolute z-50 flex flex-col gap-2"
      style={{
        left: 16,
        bottom: 16,
        padding: '10px 12px',
        borderRadius: 10,
        background: 'rgba(15,23,42,0.82)',
        border: '1px dashed rgba(255,255,255,0.14)',
        backdropFilter: 'blur(8px)',
        fontFamily: 'var(--font-mono), monospace',
      }}
      data-testid="embodiment-spike-controls"
    >
      <div style={{ fontSize: 10, color: '#64748b', letterSpacing: '0.06em' }}>
        EMBODIMENT SPIKE — NOT SHIPPED UI
      </div>

      <div className="flex gap-1.5 items-center">
        <span style={{ fontSize: 10, color: '#64748b', width: 52 }}>renderer</span>
        {(['orb', 'avatar'] as const).map((r) => (
          <button key={r} style={chip(renderer === r)} onClick={() => setRenderer(r)}>
            {r}
          </button>
        ))}
      </div>

      <div className="flex gap-1.5 items-center flex-wrap" style={{ maxWidth: 330 }}>
        <span style={{ fontSize: 10, color: '#64748b', width: 52 }}>activity</span>
        {STATES.map((s) => (
          <button key={s} style={chip(orbState === s)} onClick={() => setOrbState(s)}>
            {s}
          </button>
        ))}
      </div>

      {/* The locality chips are gone. They drove `sessionStatusStore` so the
          avatar could show `local` and `cloud`, and the avatar no longer
          reports where an answer came from — `OrbStatusLabel` does, in words.
          Removed rather than left inert: a control that sets a value nothing
          renders is how a panel starts lying about what it is testing. */}

      {/* The derived value, shown because it is the thing under test. */}
      <div style={{ fontSize: 10, color: '#94a3b8' }}>
        useEmbodimentState() → <span style={{ color: '#78dcf0' }}>{derived}</span>
      </div>
    </div>
  )
}
