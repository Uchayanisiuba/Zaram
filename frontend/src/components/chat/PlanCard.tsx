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
import type { ChatPlanItem, ChatToolCall } from '../../stores/chatStore';

const STATUS: Record<string, { Icon: typeof Check; color: string; label: string }> = {
  done: { Icon: Check, color: 'var(--color-green, #4ade80)', label: 'done' },
  doing: { Icon: CircleDot, color: 'var(--color-cyan-light)', label: 'doing' },
  todo: { Icon: Circle, color: 'var(--color-text-faint)', label: 'to do' },
  skipped: { Icon: MinusCircle, color: 'var(--color-amber, #d97706)', label: 'skipped' },
};

/** What a call did, in as few words as carry the claim.
 *
 * The tool's name and what it was aimed at, which is the pair that makes the
 * row checkable — `read_lines` on `readiness.py:156-181` can be opened and
 * "read a file" cannot. `target` is model-written and already bounded by the
 * backend; it is rendered as text, never as markup.
 */
function evidenceOf(call: ChatToolCall): string {
  const name = call.label || call.tool || call.server;
  return call.target ? `${name} ${call.target}` : name;
}

/** The colour a call's verdict earns.
 *
 * A refusal must read as a refusal here too. A step that says `done` above two
 * calls the gate turned down is the exact shape of a status claim that is
 * false, and this card is the one place both facts are on screen together.
 */
const VERDICT_COLOUR: Record<string, string> = {
  refuse: 'var(--color-red, #fca5a5)',
  confirm: 'var(--color-amber, #d97706)',
};

export default function PlanCard({
  items,
  awaitingGo = false,
  onGo,
  toolCalls = [],
}: {
  items: ChatPlanItem[];
  awaitingGo?: boolean;
  onGo?: (level: 'ask' | 'full') => void;
  /** Every call this reply made. Those carrying a `planStep` are nested under
   *  the step they were made for; the rest are left to the interleaved rows,
   *  which is where a reply with no plan shows its working. */
  toolCalls?: ChatToolCall[];
}) {
  if (!items.length) return null;
  // **The join, and it is the whole point of this card now.** A checklist on
  // its own is a list of claims; the same list with what was actually run
  // under each line is a record. Grouped here rather than on the way in so the
  // card stays drawable from a stored message — history has the calls and the
  // plan, and nothing else has to have kept an index.
  const evidence = new Map<number, ChatToolCall[]>();
  for (const call of toolCalls) {
    if (call.planStep == null) continue;
    const at = evidence.get(call.planStep);
    if (at) at.push(call);
    else evidence.set(call.planStep, [call]);
  }
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
            <li key={i} className="text-xs" data-status={item.status}>
              <div className="flex items-start gap-1.5">
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
              </div>
              {/* Indented to the step's text, not to the bullet: the evidence
                  belongs to the claim above it and the alignment is what says
                  so without a second heading. */}
              {(evidence.get(i) ?? []).length > 0 && (
                <ul
                  className="mt-0.5 mb-0.5 flex flex-col gap-0.5"
                  style={{ marginLeft: '1.05rem', listStyle: 'none', padding: 0 }}
                  data-testid={`plan-evidence-${i}`}
                >
                  {(evidence.get(i) ?? []).map((call, j) => (
                    <li
                      key={j}
                      className="text-[11px]"
                      style={{
                        color: VERDICT_COLOUR[call.verdict] ?? 'var(--color-text-faint)',
                      }}
                      data-verdict={call.verdict}
                    >
                      {evidenceOf(call)}
                      {call.verdict === 'refuse' && ' — refused'}
                      {call.verdict === 'confirm' && ' — waiting for you'}
                    </li>
                  ))}
                </ul>
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
