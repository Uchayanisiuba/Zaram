/**
 * Shortening what Zaram keeps.
 *
 * Asked for 3 October 2026 — *"a purge memory button … purge Zaram's entire
 * memory, or purge/delete in ranges, by date"* — and the backend answered the
 * same day, completely, with a route that counts before it deletes. Nothing in
 * the interface ever called it, which is this repository's most common defect
 * in its plainest form.
 *
 * **The count is the control.** "Remove 1,284 facts, October to December" is a
 * sentence somebody can disagree with; "Are you sure?" is not. So the button
 * that deletes does not exist until a count has been read, says the number on
 * its face, and goes away the moment any input changes — a preview of one range
 * must never authorise the removal of another.
 *
 * Not offered here: a scope picker. Scope is often what somebody means, and
 * the route takes it, but naming a project needs the list of them and a
 * screen that is honest about what each one holds. That is the next step, not
 * a reason to ship nothing.
 */
import { useState } from 'react';
import { Loader2, Trash2 } from 'lucide-react';

import {
  previewMemoryPurge,
  purgeMemory,
  type PurgeRange,
  type PurgeSummary,
} from '@/services/settingsClient';

type Mode = 'all' | 'before' | 'since' | 'between';

const DAY = 86_400;

/** Local midnight at the start of a `YYYY-MM-DD` date, in Unix seconds. */
function startOf(date: string): number | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return null;
  const [y, m, d] = date.split('-').map(Number);
  return new Date(y, m - 1, d).getTime() / 1000;
}

/**
 * The window a choice means, in the backend's exclusive bounds.
 *
 * `null` is "not yet decidable" — a date mode with no date — and the caller
 * treats it as no range at all, not as everything. Turning an unfinished form
 * into the widest possible deletion is the one mistake this function exists to
 * not make.
 */
export function rangeFor(mode: Mode, from: string, to: string): PurgeRange | null {
  if (mode === 'all') return {};
  const start = startOf(from);
  const end = startOf(to);
  // "from a date" means that whole day included, so the exclusive lower bound
  // sits a millisecond before it; "up to a date" means that whole day included
  // too, so the exclusive upper bound is the start of the next one.
  if (mode === 'before') return start === null ? null : { before: start };
  if (mode === 'since') return start === null ? null : { after: start - 0.001 };
  if (start === null || end === null) return null;
  const range = { after: start - 0.001, before: end + DAY };
  return range.before > range.after ? range : null;
}

function day(seconds: number | null): string {
  return seconds === null ? '' : new Date(seconds * 1000).toLocaleDateString();
}

export default function PurgeMemory() {
  const [mode, setMode] = useState<Mode>('before');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [preview, setPreview] = useState<PurgeSummary | null>(null);
  const [result, setResult] = useState<PurgeSummary | null>(null);
  const [busy, setBusy] = useState<'count' | 'remove' | null>(null);
  const [error, setError] = useState('');

  const range = rangeFor(mode, from, to);

  // Any change to the question throws away the answer to the old one.
  const change = <T,>(set: (value: T) => void) => (value: T) => {
    set(value);
    setPreview(null);
    setResult(null);
    setError('');
  };

  async function count() {
    if (!range) return;
    setBusy('count');
    setError('');
    setResult(null);
    try {
      setPreview(await previewMemoryPurge(range));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Zaram could not count that.');
    } finally {
      setBusy(null);
    }
  }

  async function remove() {
    if (!range || !preview) return;
    setBusy('remove');
    setError('');
    try {
      const done = await purgeMemory(range);
      setPreview(null);
      setResult(done);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Nothing was removed.');
    } finally {
      setBusy(null);
    }
  }

  const field = {
    background: 'var(--color-glass)',
    border: '1px solid var(--color-border)',
    color: 'var(--color-text)',
  } as const;

  return (
    <div data-testid="purge-memory" className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <select
          aria-label="Which facts"
          data-testid="purge-mode"
          value={mode}
          onChange={(e) => change(setMode)(e.target.value as Mode)}
          className="rounded-lg px-2 py-1 text-xs outline-none"
          style={field}
        >
          <option value="before">Everything from before…</option>
          <option value="since">Everything from… onwards</option>
          <option value="between">Everything between…</option>
          <option value="all">Everything</option>
        </select>
        {mode !== 'all' && (
          <input
            type="date"
            aria-label={mode === 'before' ? 'Before this date' : 'From this date'}
            data-testid="purge-from"
            value={from}
            onChange={(e) => change(setFrom)(e.target.value)}
            className="rounded-lg px-2 py-1 text-xs outline-none"
            style={field}
          />
        )}
        {mode === 'between' && (
          <>
            <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
              and
            </span>
            <input
              type="date"
              aria-label="Up to and including this date"
              data-testid="purge-to"
              value={to}
              onChange={(e) => change(setTo)(e.target.value)}
              className="rounded-lg px-2 py-1 text-xs outline-none"
              style={field}
            />
          </>
        )}
        <button
          type="button"
          data-testid="purge-count"
          disabled={!range || busy !== null}
          onClick={() => void count()}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1 text-xs disabled:opacity-40"
          style={{ border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
        >
          {busy === 'count' && <Loader2 size={12} className="animate-spin" aria-hidden />}
          See what would go
        </button>
      </div>

      {preview && (
        <div data-testid="purge-preview" className="flex flex-col gap-2">
          {preview.matched === 0 && preview.superseded === 0 ? (
            <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
              Nothing matches, so there is nothing to remove.
            </p>
          ) : (
            <>
              <p className="text-xs" style={{ color: 'var(--color-text)' }}>
                {preview.matched} {preview.matched === 1 ? 'fact' : 'facts'}
                {preview.oldest !== null &&
                  `, from ${day(preview.oldest)} to ${day(preview.newest)}`}
                {preview.scopes.length > 0 && `, across ${preview.scopes.join(', ')}`}
                {preview.superseded > 0 &&
                  `, plus ${preview.superseded} earlier ${preview.superseded === 1 ? 'version' : 'versions'} of facts you corrected`}
                .
              </p>
              <button
                type="button"
                data-testid="purge-remove"
                disabled={busy !== null}
                onClick={() => void remove()}
                className="flex w-fit items-center gap-1.5 rounded-lg px-3 py-1 text-xs disabled:opacity-40"
                style={{
                  border: '1px solid rgba(239,68,68,0.5)',
                  color: 'var(--color-text)',
                  background: 'rgba(239,68,68,0.12)',
                }}
              >
                {busy === 'remove' ? (
                  <Loader2 size={12} className="animate-spin" aria-hidden />
                ) : (
                  <Trash2 size={12} aria-hidden />
                )}
                Remove {preview.matched} {preview.matched === 1 ? 'fact' : 'facts'}
                {preview.superseded > 0 && ` and ${preview.superseded} earlier ${preview.superseded === 1 ? 'version' : 'versions'}`}
              </button>
            </>
          )}
        </div>
      )}

      {result && (
        <p data-testid="purge-result" className="text-xs" style={{ color: 'var(--color-emerald)' }}>
          Removed {result.deleted} {result.deleted === 1 ? 'fact' : 'facts'}. Answers that leaned
          on them will change. It is noted in Activity that this happened and how much — never what.
        </p>
      )}

      {error && (
        <p data-testid="purge-error" className="text-xs" style={{ color: 'var(--color-amber-light, #fcd34d)' }}>
          {error}
        </p>
      )}

      <p className="text-xs leading-relaxed" style={{ color: 'var(--color-text-faint)' }}>
        This cannot be undone. Nothing is deleted until you have seen how many facts it would be.
        Pinned facts go too if they are in the range — you are asking on purpose.
      </p>
    </div>
  );
}
