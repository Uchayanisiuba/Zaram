/**
 * What is holding the graphics card right now, and a way to get it back.
 *
 * **Measured 12 September 2026, on a 12 GB card.** Ollama held a 10.4 GB chat
 * model that routing preferred not to use; TabbyAPI held 9.5 GB on top of it;
 * the desktop needed 3 GB more. The driver paged GPU memory over PCIe for every
 * process on the machine, and "my PC is slow" was true with Zaram in the
 * background and nothing else running. There was no way to see any of that
 * and no way to undo it short of quitting.
 *
 * Three things this shows, and each is a fact rather than a claim:
 *
 * - **What is resident**, per model, with the size where the server reports
 *   one. A server that reports residency without a size (TabbyAPI, LM Studio)
 *   shows the name and no number — never a zero, which would read as "free".
 * - **What is free** on the card as a whole, from the driver, beside every
 *   other process. Absent where there is no NVIDIA driver to ask.
 * - **Why nothing was preloaded**, in the backend's own sentence, when that is
 *   what happened. A preload that silently did not happen is a first-message
 *   cold start with no explanation; this is the explanation.
 *
 * And one action. *Release the card* unloads what every local server can
 * unload and reports what it cannot — a server with no unload route stays
 * listed as still holding its model, with the reason, because a button that
 * says "done" while 9.5 GB is still on the card is worse than no button.
 *
 * Loopback only. Nothing here leaves the machine, so nothing here is logged
 * as egress.
 */
import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, Check, Minus } from 'lucide-react';

import {
  SettingsError,
  fetchCardStatus,
  releaseCard,
  type CardStatus,
} from '@/services/settingsClient';

/** Gigabytes, one decimal — the same shape Settings uses for model sizes. */
function gb(bytes: number): string {
  return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
}

/** The sum of what is resident, counting only the sizes actually reported. */
export function residentBytes(status: CardStatus): number | null {
  if (!status.resident) return null;
  const sized = status.resident.filter((m) => typeof m.bytes === 'number');
  if (sized.length === 0) return null;
  return sized.reduce((sum, m) => sum + (m.bytes ?? 0), 0);
}

/** The one-line value beside the label. Pure, so it can be asserted. */
export function summarise(status: CardStatus | null, loading: boolean): string {
  if (loading && !status) return 'reading…';
  if (!status) return 'unknown';
  if (status.resident === null) return 'unknown';
  if (status.resident.length === 0) return 'nothing resident';
  const total = residentBytes(status);
  const count = status.resident.length;
  const noun = count === 1 ? 'model' : 'models';
  return total === null ? `${count} ${noun} resident` : `${count} ${noun} · ${gb(total)}`;
}

export default function OnTheCard() {
  const [status, setStatus] = useState<CardStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setStatus(await fetchCardStatus());
      setError(null);
    } catch (e) {
      setError(e instanceof SettingsError ? e.message : 'Could not read the card.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const release = useCallback(async () => {
    setBusy(true);
    try {
      setStatus(await releaseCard());
      setError(null);
    } catch (e) {
      setError(e instanceof SettingsError ? e.message : 'Could not release the card.');
    } finally {
      setBusy(false);
    }
  }, []);

  const resident = status?.resident ?? null;
  const anything = Boolean(resident && resident.length > 0);
  const notReleased = status?.outcome
    ? Object.entries(status.outcome).filter(([, v]) => v !== 'released')
    : [];
  const state: 'good' | 'neutral' | 'warn' = error
    ? 'warn'
    : anything
      ? 'good'
      : 'neutral';
  const colour =
    state === 'good'
      ? 'var(--color-emerald)'
      : state === 'warn'
        ? 'var(--color-amber, #fbbf24)'
        : 'var(--color-text-muted)';

  return (
    <div
      className="flex items-start gap-3 px-5 py-3.5"
      style={{ borderBottom: '1px solid var(--color-border-subtle)' }}
      data-testid="on-the-card"
    >
      <span className="mt-0.5 shrink-0" style={{ color: colour }}>
        {state === 'good' ? <Check size={14} /> : state === 'warn' ? <AlertTriangle size={14} /> : <Minus size={14} />}
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2 flex-wrap">
          <span className="text-sm" style={{ color: 'var(--color-text)' }}>
            On the card
          </span>
          <span className="text-xs" style={{ fontFamily: 'var(--font-mono)', color: colour }}>
            {summarise(status, loading)}
          </span>
          {status?.freeVramBytes !== null && status?.freeVramBytes !== undefined && (
            <span className="text-xs" style={{ color: 'var(--color-text-faint)' }}>
              {gb(status.freeVramBytes)} free
            </span>
          )}
        </div>

        <p
          className="text-[11px] leading-snug mt-0.5"
          style={{ color: 'var(--color-text-muted)', maxWidth: '52ch' }}
        >
          What the local servers are holding in graphics memory right now, beside
          everything else you have open. Release it before a game, a render or another
          model needs the room; the next question loads it again.
        </p>

        {resident && resident.length > 0 && (
          <ul className="mt-2 flex flex-col gap-1" aria-label="Resident models">
            {resident.map((m) => (
              <li
                key={m.name}
                className="text-[11px] flex items-baseline gap-2"
                style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text)' }}
              >
                <span className="truncate">{m.name}</span>
                <span style={{ color: 'var(--color-text-faint)' }}>
                  {m.bytes === null ? 'size not reported' : gb(m.bytes)}
                </span>
              </li>
            ))}
          </ul>
        )}

        {status?.preloadSkippedBecause && (
          <p
            className="text-[11px] leading-snug mt-1.5"
            style={{ color: 'var(--color-text-muted)', maxWidth: '52ch' }}
          >
            Nothing was preloaded at launch: {status.preloadSkippedBecause}.
          </p>
        )}

        {notReleased.length > 0 && (
          <ul className="mt-1.5 flex flex-col gap-0.5" aria-label="Still resident">
            {notReleased.map(([name, why]) => (
              <li
                key={name}
                className="text-[11px] leading-snug"
                style={{ color: 'var(--color-amber, #fbbf24)', maxWidth: '52ch' }}
              >
                {name}: {why.replace(/^not released:\s*/, '')}
              </li>
            ))}
          </ul>
        )}

        {error && (
          <p className="text-[11px] mt-1" style={{ color: 'var(--color-amber, #fbbf24)' }}>
            {error}
          </p>
        )}

        <div className="mt-2 flex items-center gap-2">
          <button
            type="button"
            onClick={() => void release()}
            disabled={busy || !anything}
            className="text-[11px] px-2.5 py-1 rounded-md transition-colors disabled:opacity-40"
            style={{
              border: '1px solid var(--color-border)',
              color: 'var(--color-text)',
              background: 'var(--color-glass)',
            }}
          >
            {busy ? 'Releasing…' : 'Release the card'}
          </button>
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={loading || busy}
            className="text-[11px] px-2 py-1 rounded-md transition-colors disabled:opacity-40"
            style={{ color: 'var(--color-text-muted)' }}
          >
            Refresh
          </button>
        </div>
      </div>
    </div>
  );
}
