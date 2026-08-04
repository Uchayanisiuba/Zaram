/**
 * Activity — what left this machine.
 *
 * Not knowledge, not history: evidence. Someone arriving here is checking, not
 * exploring, and the surface is built for that posture — dense, monospaced,
 * scannable, no illustration.
 *
 * Three things make this evidence rather than a claim:
 *
 *  1. **The literal outbound text.** Clicking a row shows the exact request
 *     that left, not a summary of it. "A request went to wikipedia.org" tells
 *     the user nothing they could not have guessed; the query string is the
 *     thing they cannot get anywhere else.
 *  2. **Refusals are shown alongside sends.** A log that only recorded what
 *     succeeded could not show you what your software *tried* to do, which is
 *     usually the more interesting question.
 *  3. **The caveat is on the screen, not in a docstring.** The hash chain
 *     detects tampering by anything that did not go through the append path.
 *     It cannot stop someone who already has write access. Saying more than
 *     that would be the absolute-security claim the contract forbids.
 *
 * Every display here has a control beside it: retention prunes, per-host policy
 * decides, and the kill switch cuts everything at once. A surface that only
 * displays is transparency theatre.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ShieldCheck,
  ShieldAlert,
  RefreshCw,
  ArrowUpRight,
  Ban,
  Check,
  HelpCircle,
  X,
} from 'lucide-react';
import {
  applyRetention,
  fetchEgressLog,
  fetchEgressPolicy,
  forgetEgressPolicy,
  setEgressPolicy,
  verifyEgressLog,
  type EgressEntry,
  type EgressIntegrity,
  type EgressPolicySnapshot,
  type PolicyMode,
} from '@/services/egressClient';

const RETENTION_CHOICES = [
  { days: 7, label: '7 days' },
  { days: 30, label: '30 days' },
  { days: 90, label: '90 days' },
  { days: 0, label: 'Keep all' },
];

function ts(at: number): string {
  const d = new Date(at * 1000);
  return d.toLocaleString(undefined, {
    year: '2-digit',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function bytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} kB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

const DECISION_COLOUR: Record<string, string> = {
  allowed: 'var(--color-amber, #fbbf24)',
  denied: 'var(--color-emerald, #34d399)',
  cancelled: 'var(--color-text-muted)',
};

/** Deliberate: a *denial* is the reassuring colour, a *send* is the one that
 *  draws the eye. On a privacy surface, traffic leaving is the exception worth
 *  noticing — colouring it green because it "succeeded" would invert the
 *  meaning the user came here for. */
function decisionLabel(d: string): string {
  if (d === 'allowed') return 'SENT';
  if (d === 'denied') return 'BLOCKED';
  if (d === 'cancelled') return 'CANCELLED';
  return d.toUpperCase();
}

export default function ActivityWorkspace() {
  const [entries, setEntries] = useState<EgressEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [integrity, setIntegrity] = useState<EgressIntegrity | null>(null);
  const [policy, setPolicy] = useState<EgressPolicySnapshot | null>(null);
  const [selected, setSelected] = useState<EgressEntry | null>(null);
  const [hostFilter, setHostFilter] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const [log, chain, pol] = await Promise.all([
        fetchEgressLog(200),
        verifyEgressLog(),
        fetchEgressPolicy(),
      ]);
      setEntries(log.entries);
      setTotal(log.total);
      setIntegrity(chain);
      setPolicy(pol);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not read the egress log.');
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const requests = useMemo(
    () => entries.filter((e) => e.kind === 'request'),
    [entries],
  );
  const shown = useMemo(
    () => (hostFilter ? requests.filter((e) => e.host === hostFilter) : requests),
    [requests, hostFilter],
  );

  const sentToday = useMemo(() => {
    const cutoff = Date.now() / 1000 - 86400;
    return requests
      .filter((e) => e.at >= cutoff && e.decision === 'allowed')
      .reduce((sum, e) => sum + e.bytes, 0);
  }, [requests]);

  const blockedCount = requests.filter((e) => e.decision !== 'allowed').length;

  const changePolicy = async (host: string, mode: PolicyMode | null) => {
    setBusy(true);
    try {
      if (mode === null) await forgetEgressPolicy(host);
      else await setEgressPolicy(host, mode);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not change the policy.');
      setBusy(false);
    }
  };

  /** Cut everything at once. Sets every known host to deny rather than flipping
   *  a global flag, so the state is visible per host afterwards and there is no
   *  hidden switch that contradicts what the policy list shows. */
  const killSwitch = async () => {
    if (!policy) return;
    setBusy(true);
    try {
      const hosts = new Set([...Object.keys(policy.rules), ...policy.hostsSeen]);
      for (const h of hosts) {
        if (h && h !== '-') await setEgressPolicy(h, 'deny');
      }
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not cut outbound traffic.');
      setBusy(false);
    }
  };

  const prune = async (days: number) => {
    setBusy(true);
    try {
      await applyRetention(days);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not apply retention.');
      setBusy(false);
    }
  };

  const hosts = policy ? [...new Set([...policy.hostsSeen, ...Object.keys(policy.rules)])].filter((h) => h && h !== '-') : [];

  return (
    <div className="flex-1 flex overflow-hidden">
      {/* ---------------------------------------------------------------- */}
      {/* Sources rail — every host contacted, and its standing rule.       */}
      {/* ---------------------------------------------------------------- */}
      <aside
        className="w-60 shrink-0 flex flex-col overflow-y-auto"
        style={{ borderRight: '1px solid var(--color-border-subtle)' }}
      >
        <div className="px-4 pt-6 pb-3">
          <h2
            className="text-[11px] uppercase tracking-wider"
            style={{ color: 'var(--color-text-muted)', fontFamily: 'var(--font-display)' }}
          >
            Destinations
          </h2>
        </div>

        <button
          onClick={() => setHostFilter(null)}
          className="flex items-center justify-between px-4 py-2 text-left text-xs hover:bg-white/5 transition-colors"
          style={{ color: hostFilter === null ? 'var(--color-text)' : 'var(--color-text-muted)' }}
        >
          <span>All destinations</span>
          <span style={{ fontFamily: 'var(--font-mono)' }}>{requests.length}</span>
        </button>

        {hosts.map((h) => {
          const mode = policy?.rules[h] ?? 'deny';
          const count = requests.filter((e) => e.host === h).length;
          return (
            <div key={h} className="px-4 py-2 hover:bg-white/5 transition-colors">
              <button
                onClick={() => setHostFilter(h)}
                className="w-full flex items-center justify-between text-left"
              >
                <span
                  className="text-xs truncate"
                  style={{
                    color: hostFilter === h ? 'var(--color-text)' : 'var(--color-text-muted)',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  {h}
                </span>
                <span className="text-[10px] shrink-0 ml-2" style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-faint)' }}>
                  {count}
                </span>
              </button>
              {/* The control that belongs with the display. */}
              <div className="flex gap-1 mt-1.5">
                {(['deny', 'ask', 'allow'] as PolicyMode[]).map((m) => (
                  <button
                    key={m}
                    disabled={busy}
                    onClick={() => void changePolicy(h, m)}
                    title={
                      m === 'deny'
                        ? 'Block every request to this destination'
                        : m === 'ask'
                          ? 'Show me the text and let me decide each time'
                          : 'Send without asking. Still logged.'
                    }
                    className="flex-1 rounded text-[9px] py-1 transition-colors disabled:opacity-40"
                    style={{
                      background: mode === m ? 'rgba(255,255,255,0.10)' : 'transparent',
                      border: `1px solid ${mode === m ? 'var(--color-border)' : 'var(--color-border-subtle)'}`,
                      color: mode === m ? 'var(--color-text)' : 'var(--color-text-faint)',
                      fontFamily: 'var(--font-mono)',
                    }}
                  >
                    {m}
                  </button>
                ))}
              </div>
            </div>
          );
        })}

        {hosts.length === 0 && (
          <p className="px-4 text-[11px] leading-relaxed" style={{ color: 'var(--color-text-faint)' }}>
            Nothing has been contacted yet.
          </p>
        )}
      </aside>

      {/* ---------------------------------------------------------------- */}
      {/* The log.                                                          */}
      {/* ---------------------------------------------------------------- */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="px-8 pt-6 pb-3 flex items-center gap-3">
          <h1
            className="text-lg font-semibold"
            style={{ fontFamily: 'var(--font-display)', color: 'var(--color-text)' }}
          >
            Activity
          </h1>
          <div className="flex-1" />
          <button
            onClick={() => void killSwitch()}
            disabled={busy || hosts.length === 0}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-colors disabled:opacity-30"
            style={{
              border: '1px solid rgba(248,113,113,0.35)',
              color: 'rgb(248,113,113)',
            }}
            title="Set every known destination to deny"
          >
            <Ban size={13} />
            Cut all outbound
          </button>
          <button
            onClick={() => void load()}
            aria-label="Refresh"
            className="p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-white/5 transition-colors"
          >
            <RefreshCw size={15} className={busy ? 'animate-spin' : undefined} />
          </button>
        </div>

        {/* The summary line. */}
        <div className="px-8 pb-4 flex items-baseline gap-6 flex-wrap">
          <span
            className="text-2xl"
            style={{ fontFamily: 'var(--font-mono)', color: sentToday === 0 ? 'var(--color-emerald, #34d399)' : 'var(--color-text)' }}
          >
            {bytes(sentToday)}
          </span>
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            left this device in the last 24 hours
          </span>
          {blockedCount > 0 && (
            <span className="text-xs" style={{ color: 'var(--color-text-faint)', fontFamily: 'var(--font-mono)' }}>
              · {blockedCount} blocked
            </span>
          )}
          <span className="text-xs" style={{ color: 'var(--color-text-faint)', fontFamily: 'var(--font-mono)' }}>
            · {total} recorded
          </span>
        </div>

        {/* Retention, beside the count it governs rather than in a footer.
         *  It began life at the bottom of the surface, where the floating dock
         *  covered it — and it reads better here anyway: how much left, and how
         *  long that record is kept, are the same question asked twice. */}
        <div className="px-8 pb-4 flex items-center gap-2 flex-wrap">
          <span className="text-[11px] mr-1" style={{ color: 'var(--color-text-muted)' }}>
            Keep this record for
          </span>
          {RETENTION_CHOICES.map((c) => (
            <button
              key={c.days}
              disabled={busy}
              onClick={() => void prune(c.days)}
              className="px-2.5 py-1 rounded text-[10px] transition-colors disabled:opacity-40 hover:bg-white/5"
              style={{
                border: '1px solid var(--color-border-subtle)',
                color: 'var(--color-text-muted)',
                fontFamily: 'var(--font-mono)',
              }}
            >
              {c.label}
            </button>
          ))}
          <span className="text-[10px] w-full mt-1" style={{ color: 'var(--color-text-faint)' }}>
            A permanent record of every question you have asked is its own privacy
            problem. Pruning is itself recorded.
          </span>
        </div>

        {/* Integrity, with its caveat on screen. */}
        {integrity && (
          <div
            className="mx-8 mb-4 rounded-lg px-4 py-3 flex items-start gap-2.5"
            style={{
              border: `1px solid ${integrity.intact ? 'var(--color-border-subtle)' : 'rgba(248,113,113,0.4)'}`,
              background: 'var(--color-glass)',
            }}
          >
            {integrity.intact ? (
              <ShieldCheck size={14} className="mt-0.5 shrink-0" style={{ color: 'var(--color-emerald, #34d399)' }} />
            ) : (
              <ShieldAlert size={14} className="mt-0.5 shrink-0" style={{ color: 'rgb(248,113,113)' }} />
            )}
            <div className="min-w-0">
              <p className="text-xs" style={{ color: 'var(--color-text)' }}>{integrity.detail}</p>
              {integrity.caveat && (
                <p className="text-[11px] mt-1 leading-relaxed" style={{ color: 'var(--color-text-faint)' }}>
                  {integrity.caveat}
                </p>
              )}
            </div>
          </div>
        )}

        {error && (
          <div className="mx-8 mb-4 rounded-lg px-4 py-3 text-xs" style={{ border: '1px solid rgba(248,113,113,0.4)', color: 'rgb(248,113,113)' }}>
            {error}
          </div>
        )}

        {/* The table. */}
        <div className="flex-1 overflow-y-auto px-8 pb-4">
          {shown.length === 0 ? (
            <p className="text-xs leading-relaxed" style={{ color: 'var(--color-text-faint)' }}>
              {hostFilter
                ? `Nothing recorded for ${hostFilter}.`
                : 'Nothing has left this device. Inference runs locally and the Spine is a file on this disk.'}
            </p>
          ) : (
            <table className="w-full" style={{ fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
              <thead>
                <tr style={{ color: 'var(--color-text-faint)' }}>
                  <th className="text-left font-normal pb-2 pr-3">when</th>
                  <th className="text-left font-normal pb-2 pr-3">destination</th>
                  <th className="text-left font-normal pb-2 pr-3">asked by</th>
                  <th className="text-left font-normal pb-2 pr-3">state</th>
                  <th className="text-right font-normal pb-2">bytes</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((e) => (
                  <tr
                    key={e.id}
                    onClick={() => setSelected(e)}
                    className="cursor-pointer hover:bg-white/5 transition-colors"
                    style={{ borderTop: '1px solid var(--color-border-subtle)' }}
                  >
                    <td className="py-2 pr-3 whitespace-nowrap" style={{ color: 'var(--color-text-faint)' }}>{ts(e.at)}</td>
                    <td className="py-2 pr-3 truncate max-w-[220px]" style={{ color: 'var(--color-text)' }}>{e.host}</td>
                    <td className="py-2 pr-3 truncate max-w-[160px]" style={{ color: 'var(--color-text-muted)' }}>{e.source}</td>
                    <td className="py-2 pr-3 whitespace-nowrap" style={{ color: DECISION_COLOUR[e.decision] ?? 'var(--color-text-muted)' }}>
                      {decisionLabel(e.decision)}
                    </td>
                    <td className="py-2 text-right" style={{ color: 'var(--color-text-faint)' }}>
                      {e.decision === 'allowed' ? bytes(e.bytes) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

      </div>

      {/* ---------------------------------------------------------------- */}
      {/* The literal text. What makes this evidence.                       */}
      {/* ---------------------------------------------------------------- */}
      {selected && (
        <div
          className="w-[420px] shrink-0 flex flex-col overflow-hidden"
          style={{ borderLeft: '1px solid var(--color-border-subtle)', background: 'var(--color-glass)' }}
        >
          <div className="flex items-center gap-2 px-5 py-4" style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
            <ArrowUpRight size={14} style={{ color: DECISION_COLOUR[selected.decision] }} />
            <span className="text-xs" style={{ color: 'var(--color-text)' }}>
              {decisionLabel(selected.decision)}
            </span>
            <div className="flex-1" />
            <button onClick={() => setSelected(null)} aria-label="Close" className="p-1 rounded hover:bg-white/5 text-slate-400">
              <X size={14} />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
            <div>
              <p className="text-[10px] uppercase tracking-wider mb-1.5" style={{ color: 'var(--color-text-faint)' }}>
                {selected.decision === 'allowed' ? 'What left this machine' : 'What was going to be sent'}
              </p>
              <pre
                className="text-[11px] whitespace-pre-wrap break-all rounded-lg p-3"
                style={{
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--color-text)',
                  background: 'rgba(0,0,0,0.25)',
                  border: '1px solid var(--color-border-subtle)',
                }}
              >
                {selected.literalText}
              </pre>
              <p className="text-[10px] mt-1.5" style={{ color: 'var(--color-text-faint)' }}>
                The full request, not a summary of it.
              </p>
            </div>

            <div className="space-y-2 text-[11px]" style={{ fontFamily: 'var(--font-mono)' }}>
              {[
                ['when', ts(selected.at)],
                ['destination', selected.host],
                ['method', selected.method],
                ['asked by', selected.source],
                ['bytes', selected.decision === 'allowed' ? bytes(selected.bytes) : '0 — nothing was sent'],
              ].map(([k, v]) => (
                <div key={k} className="flex gap-3">
                  <span className="w-24 shrink-0" style={{ color: 'var(--color-text-faint)' }}>{k}</span>
                  <span style={{ color: 'var(--color-text-muted)' }}>{v}</span>
                </div>
              ))}
            </div>

            <div>
              <p className="text-[10px] uppercase tracking-wider mb-1.5" style={{ color: 'var(--color-text-faint)' }}>
                Why
              </p>
              <p className="text-xs leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
                {selected.reason}
              </p>
            </div>

            <div>
              <p className="text-[10px] uppercase tracking-wider mb-2" style={{ color: 'var(--color-text-faint)' }}>
                {selected.host} from now on
              </p>
              <div className="flex gap-1.5">
                {([
                  ['deny', <Ban key="d" size={11} />, 'Block'],
                  ['ask', <HelpCircle key="a" size={11} />, 'Ask me'],
                  ['allow', <Check key="l" size={11} />, 'Allow'],
                ] as [PolicyMode, JSX.Element, string][]).map(([m, icon, label]) => (
                  <button
                    key={m}
                    disabled={busy}
                    onClick={() => void changePolicy(selected.host, m)}
                    className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-[11px] transition-colors disabled:opacity-40 hover:bg-white/5"
                    style={{
                      border: `1px solid ${policy?.rules[selected.host] === m ? 'var(--color-border)' : 'var(--color-border-subtle)'}`,
                      background: policy?.rules[selected.host] === m ? 'rgba(255,255,255,0.08)' : 'transparent',
                      color: 'var(--color-text-muted)',
                    }}
                  >
                    {icon}
                    {label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
