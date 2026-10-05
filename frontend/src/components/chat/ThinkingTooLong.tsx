/**
 * "Still thinking" — and the way out, offered when it is wanted.
 *
 * Measured 4 October 2026 against the resident 27B: a looping CSS animation took
 * **870 seconds**, 87% of it the model reasoning about a bouncing ball. The
 * Thinking switch in Settings is the right control and the wrong moment (rule
 * 7h: offer at the moment of doubt, never make the user choose in advance).
 * Nobody knows before asking whether a question will cost fourteen minutes; they
 * know eighty seconds in, with the answer not started.
 *
 * So this appears only then: thinking has run past the threshold and no answer
 * word has arrived. Before that it costs nothing and is not drawn, and after the
 * answer starts it is gone — there is nothing left to skip. It never changes the
 * Settings switch; it asks the same question again for this one message.
 *
 * What it does not do is say the thinking is wasted. On a hard question it is
 * where a 27B earns its keep, and the person is the one who knows which this is.
 */
import { useEffect, useState } from 'react';

/** How long thinking runs, with no answer begun, before the offer is made. Long
 *  enough that an ordinary question never sees it; short enough that the person
 *  has not already given up and walked away. */
export const OFFER_AFTER_MS = 45_000;

export function elapsedLabel(ms: number): string {
  const seconds = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(seconds / 60);
  return minutes > 0 ? `${minutes}m ${String(seconds % 60).padStart(2, '0')}s` : `${seconds}s`;
}

interface Props {
  /** When thinking began, or `null` when it has not. */
  since: number | null;
  /** The answer has started; there is nothing left to skip. */
  answering: boolean;
  onSkip: () => void;
  /** For tests. */
  now?: () => number;
}

export default function ThinkingTooLong({ since, answering, onSkip, now = Date.now }: Props) {
  const [, tick] = useState(0);

  useEffect(() => {
    if (since === null || answering) return undefined;
    const timer = setInterval(() => tick((n) => n + 1), 1000);
    return () => clearInterval(timer);
  }, [since, answering]);

  if (since === null || answering) return null;
  const elapsed = now() - since;
  if (elapsed < OFFER_AFTER_MS) return null;

  return (
    <div
      data-testid="thinking-too-long"
      role="status"
      className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs"
      style={{ color: 'var(--color-text-muted)' }}
    >
      <span>Still thinking — {elapsedLabel(elapsed)} so far.</span>
      <button
        type="button"
        data-testid="skip-thinking"
        onClick={onSkip}
        className="underline-offset-2 hover:underline"
        style={{ color: 'var(--color-cyan-light)' }}
      >
        Answer without thinking
      </button>
      <span style={{ color: 'var(--color-text-faint)' }}>Asks again, for this message only.</span>
    </div>
  );
}
