/**
 * The model's checklist for this task, rendered from the record.
 *
 * `docs/AGENT-UX.md`: the plan is a checklist the model writes for itself
 * through the `plan` tool, shown whole under the reply — never folded, above
 * the tool rows — and kept on the task's row in Project when the task ends.
 * Items tick as the model marks them; the card is drawn from the `plan` event,
 * which carries the whole list every time, so it is the record and never a
 * diff of one.
 *
 * **Go is the offer, not a mode.** When a long plan is about to change
 * something, the loop pauses and the card shows the plan awaiting Go. The
 * button is the person's consent for *this* plan, given once; "tell Zaram what
 * to change" is a sentence they type, not an editor here.
 *
 * **Two rungs, 15 September 2026, after reading OpenWorker's plan card.**
 * Theirs approves a plan *and* asks how independently it may then run — keep
 * asking per action, or go. That second question was missing here, and its
 * absence was a real hole rather than a nicety: plain Go cleared only the
 * plan-level review, so every individual change still returned "needs your
 * say-so" and stopped the loop. A plan a person had read could not finish
 * unless they had already granted each tool in Settings.
 *
 * So the pause offers both, and the wording is the whole design. *Go* is the
 * quiet default and keeps every change asking. *Run without stopping* is the
 * louder one and is stated as what it costs — it does not ask again for this
 * plan. Neither is a mode: both are spent when the next question starts, and
 * the engine excludes deletions from the second (`_runs_uninterrupted`), so
 * "don't stop for each change" can never become "empty the mailbox".
 */
import { ArrowRight, Check, Circle, CircleDot, MinusCircle } from 'lucide-react';
import type { ChatPlanItem } from '../../stores/chatStore';

const STATUS: Record<string, { Icon: typeof Check; color: string; label: string }> = {
  done: { Icon: Check, color: 'var(--color-green, #4ade80)', label: 'done' },
  doing: { Icon: CircleDot, color: 'var(--color-cyan-light)', label: 'doing' },
  todo: { Icon: Circle, color: 'var(--color-text-faint)', label: 'to do' },
  skipped: { Icon: MinusCircle, color: 'var(--color-amber, #d97706)', label: 'skipped' },
};

export default function PlanCard({
  items,
  awaitingGo = false,
  onGo,
}: {
  items: ChatPlanItem[];
  awaitingGo?: boolean;
  onGo?: (level: 'ask' | 'full') => void;
}) {
  if (!items.length) return null;
  const done = items.filter((i) => i.status === 'done').length;
  return (
    <div
      className="mt-2 rounded-lg px-3 py-2 surface"
      data-testid="plan-card"
      data-awaiting-go={awaitingGo ? 'true' : 'false'}
    >
      <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>
        <span>Plan</span>
        <span style={{ color: 'var(--color-text-faint)' }}>
          {done}/{items.length} done
        </span>
      </div>
      <ol className="mt-1 flex flex-col gap-0.5">
        {items.map((item, i) => {
          const { Icon, color, label } = STATUS[item.status] ?? STATUS.todo;
          return (
            <li key={i} className="flex items-start gap-1.5 text-xs" data-status={item.status}>
              <Icon size={11} className="mt-0.5 shrink-0" style={{ color }} aria-label={label} />
              <span
                style={{
                  color: item.status === 'done' ? 'var(--color-text-faint)' : 'var(--color-text)',
                  textDecoration: item.status === 'skipped' ? 'line-through' : 'none',
                }}
              >
                {item.text}
              </span>
              {item.reason && (
                <span style={{ color: 'var(--color-text-faint)' }}>— {item.reason}</span>
              )}
            </li>
          );
        })}
      </ol>
      {awaitingGo && onGo && (
        <div className="mt-2 flex flex-col gap-1">
          <div className="flex items-center gap-4">
            <button
              type="button"
              onClick={() => onGo('ask')}
              className="text-xs flex items-center gap-1"
              style={{ color: 'var(--color-cyan-light)' }}
              data-testid="plan-go"
            >
              Go
              <ArrowRight size={10} aria-hidden />
            </button>
            {/* The second rung is deliberately the quieter of the two to look
                at and the louder of the two to read. It asks for more, so it
                does not get the accent colour as well. */}
            <button
              type="button"
              onClick={() => onGo('full')}
              className="text-xs"
              style={{ color: 'var(--color-text-muted)' }}
              data-testid="plan-go-full"
            >
              Run without stopping
            </button>
          </div>
          <p className="text-[11px]" style={{ margin: 0, color: 'var(--color-text-faint)' }}>
            Go asks before each change. Run without stopping asks only for this
            plan — deletions still ask.
          </p>
        </div>
      )}
    </div>
  );
}
