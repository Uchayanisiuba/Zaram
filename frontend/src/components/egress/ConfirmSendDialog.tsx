/**
 * Confirm before send — the moment the user decides what leaves.
 *
 * Rule 5 says nothing leaves the device without an explicit per-item policy,
 * and rule 6 says tools confirm before acting. This is where both stop being
 * documents. A thread is parked inside `EgressGate.check` while this is on
 * screen: nothing has been logged, nothing has been sent, and the model is not
 * thinking. The decision happens before the bytes move.
 *
 * Three things the design is deliberate about.
 *
 * **The literal text is available, and it is the record.** The primary view is
 * legible — where it is going, why it is being asked, and which remembered
 * facts are riding along — because the target user is not technical and a wall
 * of JSON is not a choice anyone can make. But the exact bytes are one click
 * away and update as facts are struck, so the readable view can always be
 * checked against what actually leaves. A summary the user cannot verify would
 * be a claim *about* the text rather than the text.
 *
 * **Removing a fact is the edit.** It is the case that actually arises — send
 * this question, but not my day rate — and it is what rule 4 promises. An
 * all-or-nothing dialog would make the useful answer impossible to express, so
 * the user would learn to answer "send" without reading.
 *
 * **Nothing about this is calm.** Motion has a budget across the product; this
 * spends none of it. There is no animation, no dismissal by clicking away, and
 * no default button. Closing without answering is not one of the options, since
 * a dialog that can be waved off teaches the user to wave it off.
 *
 * Silence still denies — the backend times out and refuses. No countdown is
 * shown, deliberately: this end does not know the deadline, and hardcoding one
 * to display would be a number in the interface that the thing enforcing it
 * never reads. That is how a status indicator starts reporting a value nobody
 * updated. If the wait is worth showing, the backend has to say how long it is.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import {
  decidePendingEgress,
  fetchPendingEgress,
  type PendingEgress,
} from '@/services/egressClient';
import { readRecalledFacts, withoutRecalledFacts } from './recalledFacts';

/** How often to ask whether something is waiting.
 *
 *  Faster than the 10s /health poll because the user is inside a request while
 *  this runs — the reply has stalled and every second before the question
 *  appears reads as the product hanging. It is a localhost GET returning an
 *  empty list the rest of the time. */
const POLL_MS = 1000;

interface ConfirmSendDialogProps {
  /** Overrides the poll, for tests and for a future push channel. */
  source?: () => Promise<PendingEgress[]>;
  decide?: typeof decidePendingEgress;
  pollMs?: number;
}

export default function ConfirmSendDialog({
  source = fetchPendingEgress,
  decide = decidePendingEgress,
  pollMs = POLL_MS,
}: ConfirmSendDialogProps = {}) {
  const [waiting, setWaiting] = useState<PendingEgress | null>(null);
  const [removed, setRemoved] = useState<string[]>([]);
  const [showLiteral, setShowLiteral] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Read inside the interval without making it a dependency, so answering does
  // not tear down and rebuild the poll.
  const currentId = useRef<string | null>(null);
  currentId.current = waiting?.id ?? null;

  useEffect(() => {
    let live = true;

    const check = async () => {
      try {
        const pending = await source();
        if (!live) return;
        const next = pending[0] ?? null;

        // Only reset the edit when the subject changes. Re-rendering the same
        // question every second would put struck facts back while the user was
        // still reading.
        if ((next?.id ?? null) !== currentId.current) {
          setWaiting(next);
          setRemoved([]);
          setShowLiteral(false);
          setError(null);
        }
      } catch {
        // The backend being unreachable is not this component's story to tell —
        // the orb already reports it, and a confirmation error over a question
        // that no longer exists would be noise.
      }
    };

    void check();
    const id = setInterval(() => void check(), pollMs);
    return () => {
      live = false;
      clearInterval(id);
    };
  }, [source, pollMs]);

  const facts = useMemo(() => readRecalledFacts(waiting?.body ?? null), [waiting]);

  const editedBody = useMemo(
    () => withoutRecalledFacts(waiting?.body ?? null, removed),
    [waiting, removed],
  );

  /** What will actually go on the wire, with the strikings applied. */
  const outboundText = useMemo(() => {
    if (!waiting) return '';
    if (editedBody === null) return waiting.literalText;
    return `${waiting.url}\n\n${editedBody}`;
  }, [waiting, editedBody]);

  const answer = useCallback(
    async (approved: boolean) => {
      if (!waiting || busy) return;
      setBusy(true);
      try {
        // `editedBody ?? undefined` matters: an untouched request sends no body
        // at all and keeps its original bytes, rather than being re-serialised
        // into something equivalent but not identical.
        await decide(waiting.id, approved, approved ? (editedBody ?? undefined) : undefined);
        setWaiting(null);
        setRemoved([]);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setBusy(false);
      }
    },
    [waiting, busy, editedBody, decide],
  );

  // Escape refuses. It does not close the dialog: there is a thread waiting on
  // an answer, and dismissing without one would leave it to time out while the
  // user believed they had cancelled — which they had.
  useEffect(() => {
    if (!waiting) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        void answer(false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [waiting, answer]);

  if (!waiting) return null;

  const struck = (marker: string) => removed.includes(marker);
  const outboundBytes = new TextEncoder().encode(outboundText).length;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-send-title"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 200,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(8, 10, 14, 0.72)',
        padding: 24,
      }}
    >
      <div
        style={{
          width: 'min(680px, 100%)',
          maxHeight: '86vh',
          overflowY: 'auto',
          borderRadius: 14,
          border: '1px solid rgba(255,255,255,0.10)',
          background: '#12151C',
          color: '#E5E7EB',
          padding: '22px 24px 18px',
          font: '400 14px/1.55 var(--font-sans, system-ui, sans-serif)',
        }}
      >
        <h2
          id="confirm-send-title"
          style={{ margin: '0 0 6px', font: '600 17px/1.3 var(--font-sans, system-ui, sans-serif)' }}
        >
          Send this to {waiting.host}?
        </h2>
        <p style={{ margin: '0 0 18px', color: '#9CA3AF' }}>
          {describeSource(waiting.source)} This host is set to ask, so nothing has left
          your machine yet.
        </p>

        {facts.length > 0 && (
          <section style={{ marginBottom: 18 }}>
            <h3 style={{ margin: '0 0 8px', font: '600 13px/1.3 inherit', color: '#D1D5DB' }}>
              Things Zaram remembered, included in this request
            </h3>
            <p style={{ margin: '0 0 10px', color: '#9CA3AF', fontSize: 13 }}>
              Remove any that should not leave. The rest of your message is sent as it is.
            </p>
            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {facts.map((fact) => (
                <li key={fact.marker}>
                  <button
                    type="button"
                    onClick={() =>
                      setRemoved((prev) =>
                        prev.includes(fact.marker)
                          ? prev.filter((m) => m !== fact.marker)
                          : [...prev, fact.marker],
                      )
                    }
                    aria-pressed={struck(fact.marker)}
                    aria-label={
                      struck(fact.marker)
                        ? `Put back: ${fact.text}`
                        : `Remove from this request: ${fact.text}`
                    }
                    style={{
                      maxWidth: 320,
                      textAlign: 'left',
                      cursor: 'pointer',
                      borderRadius: 8,
                      padding: '6px 10px',
                      font: 'inherit',
                      fontSize: 13,
                      border: struck(fact.marker)
                        ? '1px solid rgba(255,255,255,0.10)'
                        : '1px solid rgba(125,211,252,0.35)',
                      background: struck(fact.marker) ? 'transparent' : 'rgba(125,211,252,0.10)',
                      color: struck(fact.marker) ? '#6B7280' : '#E5E7EB',
                      textDecoration: struck(fact.marker) ? 'line-through' : 'none',
                    }}
                  >
                    <span style={{ color: '#6B7280', marginRight: 6 }}>{fact.when}</span>
                    {fact.text}
                    <span aria-hidden="true" style={{ marginLeft: 8, opacity: 0.7 }}>
                      {struck(fact.marker) ? '↺' : '×'}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}

        <button
          type="button"
          onClick={() => setShowLiteral((s) => !s)}
          aria-expanded={showLiteral}
          style={{
            background: 'none',
            border: 'none',
            padding: 0,
            font: 'inherit',
            fontSize: 13,
            color: '#7DD3FC',
            cursor: 'pointer',
          }}
        >
          {showLiteral ? 'Hide' : 'Show'} exactly what is sent ({outboundBytes} bytes)
        </button>

        {showLiteral && (
          <pre
            data-testid="literal-text"
            style={{
              marginTop: 10,
              maxHeight: 240,
              overflow: 'auto',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              borderRadius: 8,
              border: '1px solid rgba(255,255,255,0.08)',
              background: '#0B0D12',
              padding: 12,
              font: '400 12px/1.5 var(--font-mono, ui-monospace, monospace)',
              color: '#D1D5DB',
            }}
          >
            {outboundText}
          </pre>
        )}

        {error && (
          <p role="alert" style={{ marginTop: 12, color: '#FCA5A5', fontSize: 13 }}>
            {error}
          </p>
        )}

        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 20 }}>
          <button
            type="button"
            onClick={() => void answer(false)}
            disabled={busy}
            style={{
              padding: '9px 16px',
              borderRadius: 8,
              border: '1px solid rgba(255,255,255,0.14)',
              background: 'transparent',
              color: '#E5E7EB',
              font: 'inherit',
              cursor: busy ? 'default' : 'pointer',
            }}
          >
            Don’t send
          </button>
          <button
            type="button"
            onClick={() => void answer(true)}
            disabled={busy}
            style={{
              padding: '9px 16px',
              borderRadius: 8,
              border: '1px solid rgba(125,211,252,0.45)',
              background: 'rgba(125,211,252,0.16)',
              color: '#E0F2FE',
              font: 'inherit',
              cursor: busy ? 'default' : 'pointer',
            }}
          >
            {removed.length > 0 ? `Send without ${removed.length} fact${removed.length > 1 ? 's' : ''}` : 'Send'}
          </button>
        </div>
      </div>
    </div>
  );
}

/** Plain language for who is asking. Never a module path. */
function describeSource(source: string): string {
  if (source === 'chat') return 'Your conversation needs a model that runs off this machine.';
  if (!source || source === 'unknown') return 'Something in Zaram is trying to reach the internet.';
  return `${source} is trying to reach the internet.`;
}
