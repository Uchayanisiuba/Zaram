/**
 * What the model actually did to reach an answer.
 *
 * **The backend has emitted this since the tool loop shipped and nothing
 * rendered it.** `StreamEvent.tool_call` carried the server, the tool and the
 * gate's verdict for every call; `chatClient.parseEvent` dropped it in its
 * default case. So a reply that searched a repository and read two files looked
 * exactly like one answered from memory — and the working, which is the whole
 * difference between a claim and a checkable claim, was invisible.
 *
 * `CLAUDE.md`: *"Show routing decisions in plain language"*, and *"disabled
 * capabilities are visible, not silent"*. A refused tool changed the answer;
 * saying so is not a debug affordance.
 *
 * **Not styled as the model speaking.** Same posture as `NoticeCard`: this is
 * Zaram reporting on itself, and putting it in the reply's own voice would
 * attribute Zaram's bookkeeping to the model.
 *
 * Deliberately one line per call and nothing more. The *arguments* are not
 * shown — a `read_lines` on a 400-line range is a wall of numbers that tells a
 * reader nothing they wanted — and neither is the result, which is the file
 * contents and belongs in the model's context rather than on the screen.
 */
import { Check, CircleAlert, Clock } from 'lucide-react';
import type { ChatToolCall } from '../../stores/chatStore';

/** How each verdict reads. The gate's word, not the model's.
 *
 *  `allow` is deliberately the quietest of the three: a tool that ran as
 *  intended is the ordinary case, and drawing it in a warning colour would
 *  train the eye past the two that matter. */
const VERDICTS: Record<string, { Icon: typeof Check; color: string; label: string }> = {
  allow: { Icon: Check, color: 'var(--color-text-faint)', label: 'ran' },
  confirm: { Icon: Clock, color: 'var(--color-amber, #d97706)', label: 'waiting on you' },
  refuse: { Icon: CircleAlert, color: 'var(--color-amber, #d97706)', label: 'did not run' },
};

const UNKNOWN = { Icon: CircleAlert, color: 'var(--color-amber, #d97706)', label: '' };

export default function ToolCalls({ calls }: { calls: ChatToolCall[] }) {
  if (!calls.length) return null;

  return (
    <ul className="mt-2 flex flex-col gap-1" data-testid="tool-calls">
      {calls.map((call, i) => {
        const { Icon, color, label } = VERDICTS[call.verdict] ?? UNKNOWN;
        return (
          <li
            key={`${call.server}/${call.tool}/${i}`}
            className="flex items-start gap-1.5 text-[10px] leading-snug"
            style={{ color: 'var(--color-text-muted)' }}
            data-verdict={call.verdict}
          >
            <Icon size={11} className="mt-px shrink-0" style={{ color }} aria-hidden />
            <span style={{ fontFamily: 'var(--font-mono)' }}>
              {call.server}/{call.tool}
            </span>
            {label && <span style={{ color: 'var(--color-text-faint)' }}>· {label}</span>}
            {/* The reason only when there is one, and there is one exactly when
                something did not go as asked. A "ran" carries none, and
                inventing filler for it would make the line longer and say
                less. */}
            {call.reason && call.verdict !== 'allow' && (
              <span style={{ color: 'var(--color-text-faint)' }}>· {call.reason}</span>
            )}
          </li>
        );
      })}
    </ul>
  );
}
