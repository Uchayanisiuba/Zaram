/**
 * What ran on its own — the runs, with their transcripts, in Activity.
 *
 * Coworker step 4. Activity is the log, and a run that happened while the
 * window was closed is the part of the log a person most needs to read on
 * opening it: what it made (its conversation), or what it stopped at (a
 * held tool, which `UnfinishedSection` beside this lists as waiting on you).
 * Configuring a trigger is under Settings; this only reads.
 *
 * Empty renders nothing at all — most people have no triggers, and a
 * heading over an empty list is furniture.
 */
import { useEffect, useState } from 'react';
import { Clock } from 'lucide-react';

import { describeSchedule, fetchTriggers, type Trigger, type TriggerRun } from '@/services/triggersClient';
import { useChatStore } from '@/stores/chatStore';

function when(ts: number): string {
  return new Date(ts * 1000).toLocaleString(undefined, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function RunsSection({ onOpenConversation }: { onOpenConversation?: () => void }) {
  const [runs, setRuns] = useState<TriggerRun[] | null>(null);
  const [triggers, setTriggers] = useState<Record<string, Trigger>>({});
  const resume = useChatStore((s) => s.resumeConversation);

  useEffect(() => {
    let live = true;
    fetchTriggers()
      .then(({ triggers: ts, runs: rs }) => {
        if (!live) return;
        setTriggers(Object.fromEntries(ts.map((t) => [t.id, t])));
        setRuns(rs);
      })
      .catch(() => live && setRuns(null));
    return () => {
      live = false;
    };
  }, []);

  if (!runs || runs.length === 0) return null;

  const paused = Object.values(triggers).filter((t) => t.pausedReason);

  return (
    <section className="mb-6" data-testid="runs-section">
      <h3 className="t-kicker mb-2 flex items-center gap-2">
        <Clock size={12} aria-hidden /> Ran on its own
      </h3>
      {paused.map((t) => (
        <p key={t.id} className="text-xs mb-2" style={{ color: 'var(--color-amber, #fbbf24)' }} data-testid="run-paused">
          {t.pausedReason} — {describeSchedule(t)}, under Settings.
        </p>
      ))}
      <ul className="flex flex-col gap-1">
        {runs.slice(0, 10).map((run) => {
          const trigger = triggers[run.triggerId];
          const label = run.obligationId
            ? run.question.replace(/^An obligation is coming up: /, '').split('. Draft')[0]
            : trigger?.kind === 'obligations'
              ? 'Checked obligations'
              : run.question || trigger?.question || 'a run';
          const outcome =
            run.outcome === 'done'
              ? run.conversationId
                ? 'done'
                : run.note || 'nothing to do'
              : run.outcome === 'held'
                ? run.note || 'stopped — needs you'
                : run.note || 'failed';
          return (
            <li
              key={run.id}
              className="flex items-baseline gap-3 text-xs"
              data-testid="run-row"
              data-outcome={run.outcome}
            >
              <span className="tabular-nums shrink-0" style={{ color: 'var(--color-text-faint)' }}>
                {when(run.startedAt)}
              </span>
              <span className="min-w-0 flex-1 truncate" style={{ color: 'var(--color-text)' }} title={run.question}>
                {label}
              </span>
              <span
                className="shrink-0"
                style={{
                  color:
                    run.outcome === 'done'
                      ? 'var(--color-text-muted)'
                      : run.outcome === 'held'
                        ? 'var(--color-amber, #fbbf24)'
                        : 'rgb(248,113,113)',
                }}
              >
                {outcome}
              </span>
              {run.conversationId && (
                <button
                  type="button"
                  className="shrink-0"
                  style={{ color: 'var(--color-cyan-light)', background: 'none', border: 0, padding: 0, cursor: 'pointer' }}
                  onClick={() => {
                    onOpenConversation?.();
                    void resume(run.conversationId);
                  }}
                  data-testid="run-open"
                >
                  open ›
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
