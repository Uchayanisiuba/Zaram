/**
 * Packs — the optional extras, each one row: what it turns on, what it costs,
 * one button.
 *
 * Until 14 September 2026 these were `pip install` lines in Settings, which a
 * packaged install cannot run. Now the button runs the installer inside
 * Zaram's own runtime and shows its lines as they come; nothing is asked on
 * the first run (never block on a download), and the same offer appears at
 * the moment a pack is needed — choosing the avatar offers Speaking, the
 * microphone offers Listening — through `PackOffer` below.
 *
 * Takes `Row` as a prop, as the other sections do.
 */

import { useCallback, useEffect, useState } from 'react';

import { fetchExtras, installExtra, type Extra, type InstallEvent } from '@/services/extrasClient';

type RowComponent = React.ComponentType<{
  label: string;
  value?: string;
  detail?: React.ReactNode;
  state?: 'good' | 'neutral' | 'absent' | 'warn';
  children?: React.ReactNode;
}>;

export interface PacksSectionProps {
  Row: RowComponent;
  load?: () => Promise<Extra[]>;
  install?: typeof installExtra;
}

type Phase = 'idle' | 'busy' | 'done' | 'failed';

/** One pack's button and its progress, shared by the section and the offer. */
export function PackButton({
  extra,
  install = installExtra,
  onInstalled,
  compact = false,
}: {
  extra: Extra;
  install?: typeof installExtra;
  onInstalled?: () => void;
  compact?: boolean;
}) {
  const [phase, setPhase] = useState<Phase>(extra.installed ? 'done' : 'idle');
  const [last, setLast] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [restart, setRestart] = useState(false);

  const get = useCallback(async () => {
    setPhase('busy');
    setError(null);
    try {
      const terminal = await install(extra.id, (event: InstallEvent) => {
        if ('stage' in event) setLast(event.stage);
        else if ('line' in event) setLast(event.line);
      });
      if ('error' in terminal) {
        setPhase('failed');
        setError(terminal.error);
        return;
      }
      setPhase('done');
      setRestart('done' in terminal && Boolean(terminal.restart));
      onInstalled?.();
    } catch (e) {
      setPhase('failed');
      setError(e instanceof Error ? e.message : 'The pack could not be got.');
    }
  }, [extra.id, install, onInstalled]);

  if (phase === 'done') {
    return (
      <span className="text-xs" style={{ color: 'var(--color-emerald)', fontFamily: 'var(--font-mono)' }} data-testid={`pack-${extra.id}-done`}>
        {restart ? 'installed — restart Zaram to use it' : 'installed'}
      </span>
    );
  }
  return (
    <div className={`flex flex-col ${compact ? 'items-start' : 'items-end'} gap-1`}>
      <button
        type="button"
        onClick={get}
        disabled={phase === 'busy'}
        className="text-xs px-3 py-1.5 rounded-lg surface"
        style={{ color: 'var(--color-text)' }}
        data-testid={`pack-${extra.id}-get`}
      >
        {phase === 'busy' ? 'Getting it…' : `Get it — ${extra.sizeMb} MB, one time`}
      </button>
      {phase === 'busy' && last && (
        <span
          className="text-xs truncate max-w-xs"
          style={{ color: 'var(--color-text-muted)', fontFamily: 'var(--font-mono)' }}
          title={last}
          data-testid={`pack-${extra.id}-line`}
        >
          {last}
        </span>
      )}
      {error && (
        <span className="text-xs" style={{ color: 'var(--color-amber, #fbbf24)' }}>
          {error}
        </span>
      )}
    </div>
  );
}

export default function PacksSection({ Row, load = fetchExtras, install = installExtra }: PacksSectionProps) {
  const [extras, setExtras] = useState<Extra[] | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setExtras(await load());
      setProblem(null);
    } catch (e) {
      setProblem(e instanceof Error ? e.message : 'The packs could not be listed.');
    }
  }, [load]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  if (problem) {
    return <Row label="Packs" state="warn" detail={`Could not read the packs: ${problem}`} />;
  }
  if (extras === null) {
    return <Row label="Packs" state="neutral" detail="Reading…" />;
  }
  return (
    <>
      {extras.map((extra) => (
        <Row
          key={extra.id}
          label={extra.name}
          value={extra.installed ? 'installed' : undefined}
          state={extra.installed ? 'good' : 'absent'}
          detail={
            <>
              {extra.enables.join(' ')}{' '}
              <span style={{ color: 'var(--color-text-faint)' }}>
                {extra.sizeMb} MB, measured {extra.measured}.
              </span>
            </>
          }
        >
          <PackButton extra={extra} install={install} onInstalled={refresh} />
        </Row>
      ))}
    </>
  );
}

/**
 * The offer at the moment of doubt: one pack, inline, where the feature that
 * needs it was just chosen. Renders nothing when the pack is already here or
 * the list cannot be read — an offer that cannot say its price is not made.
 */
export function PackOffer({
  id,
  lead,
  load = fetchExtras,
  install = installExtra,
}: {
  id: string;
  /** The sentence before the button — "Speaking needs the voice pack." */
  lead: string;
  load?: () => Promise<Extra[]>;
  install?: typeof installExtra;
}) {
  const [extra, setExtra] = useState<Extra | null>(null);
  useEffect(() => {
    let cancelled = false;
    load()
      .then((list) => {
        if (cancelled) return;
        const found = list.find((e) => e.id === id) ?? null;
        setExtra(found && !found.installed ? found : null);
      })
      .catch(() => {
        /* no price, no offer */
      });
    return () => {
      cancelled = true;
    };
  }, [id, load]);
  if (!extra) return null;
  return (
    <div className="mt-2 flex flex-col gap-1.5" data-testid={`pack-offer-${id}`}>
      <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
        {lead}
      </span>
      <PackButton extra={extra} install={install} compact />
    </div>
  );
}
