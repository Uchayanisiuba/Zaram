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
  onGo?: () => void;
}) {
  if (!items.length) return null;
  const done = items.filter((i) => i.status === 'done').length;
  return (
    <div
      className="mt-2 rounded-lg px-3 py-2"
      style={{ border: '1px solid var(--color-border-subtle)', background: 'var(--color-glass)' }}
      data-testid="plan-card"
      data-awaiting-go={awaitingGo ? 'true' : 'false'}
    >
      <div className="flex items-center gap-2 text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
        <span>Plan</span>
        <span style={{ color: 'var(--color-text-faint)' }}>
          {done}/{items.length} done
        </span>
      </div>
      <ol className="mt-1 flex flex-col gap-0.5">
        {items.map((item, i) => {
          const { Icon, color, label } = STATUS[item.status] ?? STATUS.todo;
          return (
            <li key={i} className="flex items-start gap-1.5 text-[11px]" data-status={item.status}>
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
        <button
          type="button"
          onClick={onGo}
          className="mt-2 text-[11px] flex items-center gap-1"
          style={{ color: 'var(--color-cyan-light)' }}
          data-testid="plan-go"
        >
          Go
          <ArrowRight size={10} aria-hidden />
        </button>
      )}
    </div>
  );
}
