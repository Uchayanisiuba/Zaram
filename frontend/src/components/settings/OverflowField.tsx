/**
 * What happens when a conversation outgrows the window, and how long a
 * single reply may run.
 *
 * The last two of LM Studio's four token controls, asked for 4 October
 * 2026. The other two — the window itself and the per-model override —
 * are in `ContextWindowField`.
 *
 * **Zaram already had the better half of this and no choice about it.**
 * `core/transcript.fit` drops whole turns, oldest first, never leaves a
 * reply whose question was cut, and says so once per session. That is a
 * rolling window and a more careful one than the account the maintainer
 * sent.
 *
 * What was missing is the alternative, and it is not pedantry. Trimming
 * is right for chat, where the recent end is what matters. It is wrong
 * for an answer grounded in something said at the start — a document
 * pasted an hour ago, a constraint agreed in the first message —
 * because the model cannot know what was cut and will answer
 * confidently from a premise that is no longer there. *Generation must
 * fail rather than invent* is the rule that covers exactly that, and
 * this is the one place in the conversation path where somebody can ask
 * to have it enforced.
 *
 * **The reply cap is a different quantity and the two are easy to
 * confuse**, which is why they sit together with the difference stated
 * rather than apart with it implied. The window is the whole pool:
 * prompt, history and reply. The cap bounds the reply alone, and a small
 * one cuts a model off mid-sentence however much room is left.
 */
import type { OverflowPolicy } from '@/services/settingsClient';

const POLICY_LABEL: Record<OverflowPolicy, string> = {
  trim: 'Drop the oldest exchanges',
  stop: 'Stop and say so',
};

const POLICY_DETAIL: Record<OverflowPolicy, string> = {
  trim: 'The conversation keeps going and Zaram says what it let go of. Right for most work, and wrong when the answer depends on something said at the very start.',
  stop: 'Zaram refuses the turn rather than answering from a shortened history. Choose this when you are working from a document or a brief that must stay in view.',
};

/** Caps worth offering, smallest first. `0` lifts it.
 *
 *  Short ones are the point — a cap of 32k on a 32k window does nothing,
 *  and the reason anybody sets this is to stop a model writing an essay
 *  when a sentence was wanted. */
const CAPS = [0, 256, 512, 1_024, 2_048, 4_096] as const;

function capLabel(tokens: number): string {
  if (!tokens) return 'As long as it needs';
  if (tokens >= 1_024) return `${tokens / 1_024}k tokens`;
  return `${tokens} tokens`;
}

interface Props {
  policy: OverflowPolicy;
  cap: number;
  busy?: boolean;
  onChoosePolicy: (policy: OverflowPolicy) => void;
  onChooseCap: (tokens: number) => void;
}

export default function OverflowField({
  policy,
  cap,
  busy,
  onChoosePolicy,
  onChooseCap,
}: Props) {
  return (
    <details className="mt-1" data-testid="advanced-overflow">
      <summary
        className="text-xs cursor-pointer select-none"
        style={{ color: 'var(--color-text-muted)' }}
      >
        Advanced
      </summary>

      <div className="flex flex-col gap-3 mt-2">
        <div className="flex flex-col gap-1">
          {(Object.keys(POLICY_LABEL) as OverflowPolicy[]).map((option) => {
            const active = policy === option;
            return (
              <button
                key={option}
                type="button"
                data-testid={`overflow-${option}`}
                aria-pressed={active}
                disabled={busy}
                onClick={() => onChoosePolicy(option)}
                className="rounded-lg px-2.5 py-2 text-left text-xs disabled:opacity-40"
                style={{
                  border: `1px solid ${active ? 'var(--color-cyan)' : 'var(--color-border)'}`,
                  color: active ? 'var(--color-cyan-light)' : 'var(--color-text-muted)',
                }}
              >
                <span className="block">{POLICY_LABEL[option]}</span>
                <span
                  className="block mt-0.5 leading-snug"
                  style={{ color: 'var(--color-text-faint)', maxWidth: '48ch' }}
                >
                  {POLICY_DETAIL[option]}
                </span>
              </button>
            );
          })}
        </div>

        <div className="flex flex-col gap-1.5" data-testid="reply-cap">
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            Longest single reply
          </span>
          <div className="flex flex-wrap items-center gap-1.5">
            {CAPS.map((size) => (
              <button
                key={size}
                type="button"
                data-testid={`reply-cap-${size}`}
                aria-pressed={cap === size}
                disabled={busy}
                onClick={() => onChooseCap(size)}
                className="rounded-lg px-2.5 py-1 text-xs disabled:opacity-40"
                style={{
                  border: `1px solid ${cap === size ? 'var(--color-cyan)' : 'var(--color-border)'}`,
                  color: cap === size ? 'var(--color-cyan-light)' : 'var(--color-text-muted)',
                }}
              >
                {capLabel(size)}
              </button>
            ))}
          </div>
          <p
            className="text-xs leading-snug"
            style={{ color: 'var(--color-text-faint)', maxWidth: '52ch' }}
          >
            A separate thing from the context window, which is the whole pool —
            question, conversation and reply together. This bounds the reply
            alone, and a short one stops mid-sentence rather than finishing
            early.
          </p>
        </div>
      </div>
    </details>
  );
}
