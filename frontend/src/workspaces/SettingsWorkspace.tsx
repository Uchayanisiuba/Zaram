/**
 * Settings — reports the running system, and says what cannot be configured yet.
 *
 * Everything shown here is read from `GET /health`. Where a control does not
 * exist, the screen says so rather than presenting a switch that does nothing.
 * A settings screen full of inert toggles is the same failure as a status panel
 * full of invented numbers: it tells the user they have control they do not
 * have, and on a privacy product that is the worst thing to be wrong about.
 *
 * `docs/UI-SPEC.md` calls for Models · Privacy · Appearance · Storage as a
 * segmented control, with the Privacy pane carrying default source scope,
 * egress retention and a local kill switch. That is the shape to build here as
 * each capability lands.
 */
import { useEffect } from 'react';
import { Volume2, Shield, Cpu, RefreshCw, Check, Minus } from 'lucide-react';
import { useSystemStore } from '@/stores/systemStore';

function Row({
  label,
  value,
  detail,
  state = 'neutral',
}: {
  label: string;
  value: string;
  detail?: string;
  state?: 'good' | 'neutral' | 'absent';
}) {
  const colour =
    state === 'good'
      ? 'var(--color-emerald)'
      : state === 'absent'
        ? 'var(--color-text-faint)'
        : 'var(--color-text-muted)';
  return (
    <div
      className="flex items-start gap-3 px-5 py-3.5"
      style={{ borderBottom: '1px solid var(--color-border-subtle)' }}
    >
      <span className="mt-0.5 shrink-0" style={{ color: colour }}>
        {state === 'good' ? <Check size={14} /> : <Minus size={14} />}
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2 flex-wrap">
          <span className="text-sm" style={{ color: 'var(--color-text)' }}>
            {label}
          </span>
          <span
            className="text-xs"
            style={{ fontFamily: 'var(--font-mono)', color: colour }}
          >
            {value}
          </span>
        </div>
        {detail && (
          // pre-wrap so a detail can carry an indented command block. Without
          // it the install instructions collapse onto one line and stop being
          // copyable as a command.
          <p
            className="mt-1 text-[11px] text-slate-500 leading-relaxed"
            style={{ whiteSpace: 'pre-wrap' }}
          >
            {detail}
          </p>
        )}
      </div>
    </div>
  );
}

function Section({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div
      className="rounded-xl overflow-hidden mb-4"
      style={{ border: '1px solid var(--color-border-subtle)', background: 'var(--color-glass)' }}
    >
      <div className="flex items-center gap-2 px-5 py-3" style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
        {icon}
        <span
          className="text-xs uppercase tracking-wider"
          style={{ color: 'var(--color-text-muted)', fontFamily: 'var(--font-display)' }}
        >
          {title}
        </span>
      </div>
      {children}
    </div>
  );
}

export default function SettingsWorkspace() {
  const backendOnline = useSystemStore((s) => s.backendOnline);
  const routing = useSystemStore((s) => s.routing);
  const speech = useSystemStore((s) => s.speech);
  const refresh = useSystemStore((s) => s.refresh);
  const startPolling = useSystemStore((s) => s.startPolling);

  useEffect(() => startPolling(), [startPolling]);

  const providers = routing?.providers ?? [];

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="px-8 pt-6 pb-4 flex items-center gap-3">
        <h1
          className="text-lg font-semibold"
          style={{ fontFamily: 'var(--font-display)', color: 'var(--color-text)' }}
        >
          Settings
        </h1>
        <div className="flex-1" />
        <button
          onClick={() => void refresh()}
          aria-label="Refresh"
          className="p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-white/5 transition-colors"
        >
          <RefreshCw size={15} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-8 pb-8 max-w-3xl">
        <Section title="Privacy" icon={<Shield size={14} style={{ color: 'var(--color-emerald)' }} />}>
          <Row
            label="Requests that can leave this device"
            value={routing?.canLeaveDevice ? 'some' : 'none'}
            state={routing?.canLeaveDevice ? 'neutral' : 'good'}
            detail={
              routing?.canLeaveDevice
                ? 'A route off this machine exists. Check what has left in Activity.'
                : 'Inference runs locally and the Spine is a file on this disk. Nothing is sent out.'
            }
          />
          <Row
            label="Web search"
            value={routing?.webSearch ?? 'unknown'}
            state={routing?.webSearch === 'disabled' ? 'good' : 'neutral'}
            detail="Off until the egress log and per-source policy exist, so a question cannot reach a search provider unlogged."
          />
          <Row
            label="Egress log"
            value="not built"
            state="absent"
            detail="Nothing can leave yet, so there is nothing to record. It ships before the first cloud provider, together with its retention control."
          />
          <Row
            label="Kill switch"
            value="not built"
            state="absent"
            detail="Will cut all outbound traffic in one action. Nothing to cut today."
          />
        </Section>

        <Section title="Speech" icon={<Volume2 size={14} style={{ color: 'var(--color-indigo-light)' }} />}>
          {/* Not installed is the ordinary state of a base install, not a
              fault — so it says which, and says how to change it. A greyed
              control with no explanation leaves the user unable to tell
              "broken" from "unfinished" from "not installed", and the usual
              conclusion is that the product is broken. */}
          <Row
            label="Speech synthesis"
            value={
              speech === null
                ? 'unknown'
                : speech === 'available'
                  ? 'available'
                  : 'not installed'
            }
            state={speech === 'available' ? 'good' : speech === null ? 'neutral' : 'absent'}
            detail={
              speech === null
                ? 'Waiting for the backend to report.'
                : speech === 'available'
                  ? 'Kokoro is installed and runs on the CPU, so it does not compete with the local model for VRAM.'
                  : 'Voice ships as an optional extra because it pulls roughly 830 MB — torch, ' +
                    'transformers and the spaCy stack — for a feature that is out of scope for v1. ' +
                    'Chat is unaffected. To enable it, install the extra and restart Zaram:\n\n' +
                    '    pip install -r backend/requirements-voice.txt\n' +
                    '    python -m spacy download en_core_web_sm'
            }
          />
        </Section>

        <Section title="Models" icon={<Cpu size={14} style={{ color: 'var(--color-indigo-light)' }} />}>
          <Row
            label="Engine"
            value={backendOnline ? 'running' : 'offline'}
            state={backendOnline ? 'good' : 'absent'}
            detail={backendOnline ? undefined : 'Zaram’s backend is not reachable on port 8420.'}
          />
          {providers.length > 0 ? (
            providers.map((p) => (
              <Row
                key={p.id}
                label={p.id === 'ollama' ? 'On this computer' : p.id}
                value={p.locality}
                state="good"
                detail={
                  p.locality === 'local'
                    ? 'Answers are generated here. Nothing about your question is sent anywhere.'
                    : undefined
                }
              />
            ))
          ) : (
            <Row label="Providers" value="none detected" state="absent" />
          )}
          <Row
            label="Cloud model"
            value="not connected"
            state="absent"
            detail="Connecting one is not built yet. When it is, you will be able to use free models through OpenRouter alongside the local one, and choose which handles what."
          />
        </Section>

        <p className="text-[11px] text-slate-500 leading-relaxed px-1">
          Every value on this screen is read from the running backend. Where a
          control is missing it is marked not built rather than shown as a
          switch that does nothing.
        </p>
      </div>
    </div>
  );
}
