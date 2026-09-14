/**
 * One key, a model for each job — offered after the key is saved.
 *
 * `providers/pairing.py` holds a dated list per provider; this asks what it
 * would assign from what the key can actually see, shows each pick with its
 * one-line reason, and writes them on one press into the same fields the
 * Advanced picker uses. Nothing runs until the person presses "See picks":
 * asking is discovery, which is a request to the provider they just
 * connected, and the button is the consent to make it now rather than on
 * mount (rule 7g's posture).
 *
 * It is an offer because every free tier here trains on prompts and Zaram
 * never routes there on its own; the card says so in the same breath as the
 * picks, with the local sentence beside it.
 */
import { useState } from 'react';

import { fetchPairing, applyPairing, type Pairing } from '@/services/settingsClient';
import { LOCAL_IS_FREE } from '@/lib/freeTier';

const SLOT_LABEL: Record<string, string> = {
  chat: 'Chat and everything else',
  code: 'Coding chains',
  vision: 'Reading pictures',
};

export default function PairingOffer({
  providerId,
  displayName,
  onAssigned,
}: {
  providerId: string;
  displayName: string;
  /** Called with what was written, so a parent can refresh its own view. */
  onAssigned?: (assigned: Record<string, string | null>) => void;
}) {
  const [pairing, setPairing] = useState<Pairing | null | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<Record<string, string | null> | null>(null);

  const see = async () => {
    setBusy(true);
    setError(null);
    try {
      setPairing(await fetchPairing(providerId));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not ask the provider what it offers.');
      setPairing(null);
    } finally {
      setBusy(false);
    }
  };

  const assign = async () => {
    if (!pairing) return;
    setBusy(true);
    setError(null);
    try {
      const out = await applyPairing(providerId, pairing.picks);
      setDone(out.assigned);
      onAssigned?.(out.assigned);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not assign them.');
    } finally {
      setBusy(false);
    }
  };

  const slots = pairing ? Object.keys(pairing.picks) : [];

  return (
    <div className="surface rounded-xl px-3.5 py-3 flex flex-col gap-2" data-testid="pairing-offer">
      <p className="t-body" style={{ margin: 0 }}>
        {done
          ? `Assigned. ${displayName} now answers those jobs; change any of them under Advanced.`
          : `${displayName} has a model for each job. Want Zaram to pick one for chat, coding and pictures from what your key can reach?`}
      </p>
      {!done && pairing === undefined && (
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void see()}
            disabled={busy}
            className="text-xs px-2.5 py-1 rounded-lg disabled:opacity-40"
            style={{ background: 'var(--color-indigo-light, #6366f1)', color: '#fff' }}
            data-testid="pairing-see"
          >
            {busy ? 'Asking…' : 'See picks'}
          </button>
          <span className="text-xs" style={{ color: 'var(--color-text-faint)' }}>
            Asks {displayName} what it offers — one request, logged.
          </span>
        </div>
      )}
      {!done && pairing && slots.length === 0 && (
        <p className="text-xs" style={{ margin: 0, color: 'var(--color-text-muted)' }}>
          None of the models on the list for {displayName} is one this key can see ({pairing.seen}{' '}
          found). Pick by hand under Advanced.
        </p>
      )}
      {!done && pairing && slots.length > 0 && (
        <>
          <ul className="flex flex-col gap-1" data-testid="pairing-picks">
            {slots.map((slot) => (
              <li key={slot} className="trace-line">
                <span className="trace-k" style={{ flexBasis: '11em' }}>{SLOT_LABEL[slot] ?? slot}</span>
                <span className="trace-v">
                  <span style={{ color: 'var(--color-text)' }}>{pairing.picks[slot].model}</span>
                  <span className="role-dim"> · {pairing.picks[slot].why}</span>
                </span>
              </li>
            ))}
          </ul>
          <p className="text-xs" style={{ margin: 0, color: 'var(--color-text-muted)' }}>
            These are {displayName}'s free models: prompts sent to them are logged and may be trained on,
            and Zaram tells you every time one goes.{' '}
            <span style={{ color: 'var(--color-emerald)' }}>{LOCAL_IS_FREE}</span>
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void assign()}
              disabled={busy}
              className="text-xs px-2.5 py-1 rounded-lg disabled:opacity-40"
              style={{ background: 'var(--color-indigo-light, #6366f1)', color: '#fff' }}
              data-testid="pairing-assign"
            >
              {busy ? 'Assigning…' : 'Assign these'}
            </button>
            <span className="t-mono" style={{ color: 'var(--color-text-faint)' }}>
              list dated {pairing.generated}
            </span>
          </div>
        </>
      )}
      {error && (
        <p role="alert" className="text-xs" style={{ margin: 0, color: 'var(--color-amber)' }}>
          {error}
        </p>
      )}
    </div>
  );
}
