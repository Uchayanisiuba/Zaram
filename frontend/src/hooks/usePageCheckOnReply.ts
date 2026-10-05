import { useEffect, useRef } from 'react';

interface Turn {
  role: string;
  text: string;
}

/**
 * Start the page check when a reply has just finished streaming — and for no
 * other reason.
 *
 * Only a reply that finished streaming in this session. Opening an old
 * conversation changes `messages` without anything streaming, and must not
 * start a browser for every page in its history. The length at the start of
 * the stream says which assistant message is the new one, so a reply that
 * errored out with nothing to show never lends its check to the next message
 * that happens to arrive.
 *
 * Its own hook, and not an effect inside `ChatSurface`, because the transition
 * logic is where this goes wrong and `ChatSurface` is too large to mount in a
 * test.
 */
export function usePageCheckOnReply(
  messages: readonly Turn[],
  isStreaming: boolean,
  check: (reply: string, question: string) => void | Promise<void>,
): void {
  const startedAt = useRef<number | null>(null);
  // The first turn when the stream began. A different one afterwards means the
  // whole conversation was swapped (another one opened), not that a reply
  // arrived, so the armed state is dropped rather than lent to its history.
  const firstAtStart = useRef<string | null>(null);
  useEffect(() => {
    if (isStreaming) {
      if (startedAt.current === null) {
        startedAt.current = messages.length;
        firstAtStart.current = messages[0]?.text ?? null;
      }
      return;
    }
    const started = startedAt.current;
    if (started === null) return;
    if ((messages[0]?.text ?? null) !== firstAtStart.current) {
      startedAt.current = null;
      return;
    }
    const last = messages[messages.length - 1];
    if (!last || last.role !== 'assistant' || messages.length <= started) return;
    startedAt.current = null;
    const asked = [...messages].reverse().find((m) => m.role === 'user');
    void check(last.text, asked?.text ?? '');
  }, [isStreaming, messages, check]);
}
