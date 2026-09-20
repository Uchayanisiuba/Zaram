/**
 * What runs on its own — configured here, beside Tools, and nowhere else.
 *
 * Coworker step 4 (20 September 2026). A trigger is a question and when to
 * ask it; a run is the ordinary chat route, unattended, which never approves
 * itself. What it made appears under Activity with its transcript, and the
 * first tool the gate held appears there too, as something waiting on you.
 *
 * Three things this deliberately does not do. It does not suggest a trigger
 * — no "set up your Monday picture?" — because a trigger runs because the
 * person made it, and Zaram speaks first only with something real. It does
 * not offer a free-form schedule: a weekday and a time cover "Monday at nine"
 * and "every morning", and a cron field on a resting surface is the
 * quantization-slider mistake. And it does not render a next-run time it did
 * not read from the backend, which is the one that knows the local clock.
 */
import { useCallback, useEffect, useState } from 'react';
import { Clock, Play, Trash2 } from 'lucide-react';

import {
  createTrigger,
  deleteTrigger,
  describeSchedule,
  fetchTriggers,
  runTriggerNow,
  setTriggerEnabled,
  type Trigger,
  type TriggerKind,
} from '@/services/triggersClient';

export interface RunsOnItsOwnSectionProps {
  Row: React.ComponentType<{
    label: string;
    value?: string;
    detail?: React.ReactNode;
    state?: 'good' | 'neutral' | 'absent' | 'warn';
    children?: React.ReactNode;
  }>;
}

const WEEKDAYS: [string, string][] = [
  ['mon', 'Monday'],
  ['tue', 'Tuesday'],
  ['wed', 'Wednesday'],
  ['thu', 'Thursday'],
  ['fri', 'Friday'],
  ['sat', 'Saturday'],
  ['sun', 'Sunday'],
];

function when(ts: number | null): string {
  if (!ts) return '';
  return new Date(ts * 1000).toLocaleString(undefined, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

const link = {
  color: 'var(--color-cyan-light)',
  background: 'none',
  border: 0,
  padding: 0,
  cursor: 'pointer',
} as const;

function TriggerRow({
  trigger,
  onChange,
}: {
  trigger: Trigger;
  onChange: () => void;
}) {
  const [busy, setBusy] = useState<'' | 'run' | 'toggle' | 'delete'>('');
  const [said, setSaid] = useState('');
  const act = async (what: 'run' | 'toggle' | 'delete') => {
    setBusy(what);
    setSaid('');
    try {
      if (what === 'run') {
        const runs = await runTriggerNow(trigger.id);
        const first = runs[0];
        setSaid(
          first
            ? first.outcome === 'done'
              ? 'Ran — see Activity for what it made.'
              : first.outcome === 'held'
                ? `Stopped at something that needs you — ${first.note}`
                : `Failed — ${first.note}`
            : 'Nothing to do.',
        );
      } else if (what === 'toggle') {
        await setTriggerEnabled(trigger.id, !trigger.enabled);
      } else {
        await deleteTrigger(trigger.id);
      }
      onChange();
    } catch (caught) {
      setSaid((caught as Error).message);
    } finally {
      setBusy('');
    }
  };
  const paused = Boolean(trigger.pausedReason);
  const state = paused ? 'warn' : trigger.enabled ? 'good' : 'absent';
  const status = paused
    ? trigger.pausedReason
    : trigger.enabled
      ? trigger.nextRunAt
        ? `Next: ${when(trigger.nextRunAt)}`
        : 'On'
      : 'Off';
  return (
    <div
      className="flex items-start gap-3 px-5 py-3.5"
      style={{ borderBottom: '1px solid var(--color-border-subtle)' }}
      data-testid="trigger-row"
      data-state={state}
    >
      <div className="min-w-0 flex-1">
        <div className="text-sm" style={{ color: 'var(--color-text)' }}>
          {trigger.kind === 'obligations' ? 'Draft a reply for each obligation coming due' : trigger.question}
        </div>
        <div className="text-xs mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
          {describeSchedule(trigger)}
          <span style={{ color: paused ? 'var(--color-amber, #fbbf24)' : 'var(--color-text-faint)' }}>
            {' '}
            · {status}
          </span>
        </div>
        {said && (
          <div className="text-xs mt-1" style={{ color: 'var(--color-text-faint)' }} data-testid="trigger-said">
            {said}
          </div>
        )}
      </div>
      <div className="flex items-center gap-3 text-xs shrink-0">
        <button type="button" style={link} disabled={busy !== ''} onClick={() => void act('run')} data-testid="trigger-run-now">
          <Play size={11} className="inline mr-1" aria-hidden />
          {busy === 'run' ? 'Running…' : 'Run now'}
        </button>
        <button type="button" style={link} disabled={busy !== ''} onClick={() => void act('toggle')} data-testid="trigger-toggle">
          {trigger.enabled && !paused ? 'Turn off' : 'Turn on'}
        </button>
        <button
          type="button"
          style={{ ...link, color: 'var(--color-text-faint)' }}
          disabled={busy !== ''}
          onClick={() => void act('delete')}
          aria-label="Remove"
          data-testid="trigger-delete"
        >
          <Trash2 size={12} aria-hidden />
        </button>
      </div>
    </div>
  );
}

export default function RunsOnItsOwnSection({ Row }: RunsOnItsOwnSectionProps) {
  const [triggers, setTriggers] = useState<Trigger[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [kind, setKind] = useState<TriggerKind>('weekly');
  const [question, setQuestion] = useState('');
  const [at, setAt] = useState('09:00');
  const [weekday, setWeekday] = useState('mon');
  const [daysAhead, setDaysAhead] = useState(7);
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    try {
      setTriggers((await fetchTriggers()).triggers);
      setLoadError(null);
    } catch (caught) {
      // Never an empty list on a failed fetch: "nothing runs on its own" and
      // "could not ask" are different answers.
      setTriggers(null);
      setLoadError((caught as Error).message);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const submit = async () => {
    setBusy(true);
    setFormError(null);
    try {
      await createTrigger({ question, kind, at, weekday, daysAhead });
      setQuestion('');
      await reload();
    } catch (caught) {
      setFormError((caught as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const needsQuestion = kind !== 'obligations';

  return (
    <>
      {loadError && (
        <Row label="Runs on its own" value="could not read" state="warn" detail={loadError} />
      )}
      {triggers && triggers.length === 0 && !loadError && (
        <Row
          label="Nothing yet"
          state="absent"
          detail="A question asked on a schedule, unattended. It never approves anything on its own: the first tool that needs you stops it, and what it made — or what it is waiting for — appears under Activity."
        />
      )}
      {triggers?.map((t) => (
        <TriggerRow key={t.id} trigger={t} onChange={() => void reload()} />
      ))}
      <div className="px-5 py-4 flex flex-col gap-2" data-testid="trigger-form">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <Clock size={12} style={{ color: 'var(--color-text-faint)' }} aria-hidden />
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value as TriggerKind)}
            className="rounded px-2 py-1 text-xs"
            style={{ background: 'var(--color-surface-2, transparent)', color: 'var(--color-text)', border: '1px solid var(--color-border-subtle)' }}
            aria-label="How often"
            data-testid="trigger-kind"
          >
            <option value="weekly">Weekly</option>
            <option value="daily">Daily</option>
            <option value="obligations">For each obligation coming due</option>
          </select>
          {kind === 'weekly' && (
            <select
              value={weekday}
              onChange={(e) => setWeekday(e.target.value)}
              className="rounded px-2 py-1 text-xs"
              style={{ background: 'var(--color-surface-2, transparent)', color: 'var(--color-text)', border: '1px solid var(--color-border-subtle)' }}
              aria-label="Which day"
            >
              {WEEKDAYS.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          )}
          <span style={{ color: 'var(--color-text-faint)' }}>at</span>
          <input
            type="time"
            value={at}
            onChange={(e) => setAt(e.target.value)}
            className="rounded px-2 py-1 text-xs"
            style={{ background: 'var(--color-surface-2, transparent)', color: 'var(--color-text)', border: '1px solid var(--color-border-subtle)' }}
            aria-label="At what time"
          />
          {kind === 'obligations' && (
            <>
              <span style={{ color: 'var(--color-text-faint)' }}>for obligations due within</span>
              <input
                type="number"
                min={1}
                max={60}
                value={daysAhead}
                onChange={(e) => setDaysAhead(Number(e.target.value))}
                className="w-14 rounded px-2 py-1 text-xs"
                style={{ background: 'var(--color-surface-2, transparent)', color: 'var(--color-text)', border: '1px solid var(--color-border-subtle)' }}
                aria-label="Days ahead"
              />
              <span style={{ color: 'var(--color-text-faint)' }}>days</span>
            </>
          )}
        </div>
        {needsQuestion && (
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="The question to ask — e.g. What is the month's picture: what have I committed to, and what is due this week?"
            className="w-full rounded px-3 py-2 text-sm"
            style={{ background: 'var(--color-surface-2, transparent)', color: 'var(--color-text)', border: '1px solid var(--color-border-subtle)' }}
            aria-label="The question"
            data-testid="trigger-question"
          />
        )}
        <div className="flex items-center gap-3">
          <button
            type="button"
            disabled={busy || (needsQuestion && !question.trim())}
            onClick={() => void submit()}
            className="rounded px-3 py-1.5 text-xs"
            style={{ background: 'var(--color-indigo)', color: 'white', border: 0, cursor: 'pointer', opacity: busy || (needsQuestion && !question.trim()) ? 0.5 : 1 }}
            data-testid="trigger-add"
          >
            {busy ? 'Adding…' : 'Add'}
          </button>
          {formError && (
            <span className="text-xs" style={{ color: 'var(--color-amber, #fbbf24)' }} data-testid="trigger-form-error">
              {formError}
            </span>
          )}
        </div>
      </div>
    </>
  );
}
