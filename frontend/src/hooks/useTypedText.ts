import { useEffect, useRef, useState } from 'react';

import { useIsReducedMotion } from '@/hooks/useReducedMotion';
import { nextRevealed, revealAll } from '@/lib/typewriter';

/**
 * Show a growing string as steady typing rather than in the bursts it arrives in.
 *
 * The rule lives in `lib/typewriter.ts` as a pure function so it can be tested
 * without rendering anything — the same shape as `lib/orbActivity.ts`, and for
 * the same reason: this repository has twice shipped correct logic that no test
 * could reach because the only way to observe it was to mount a component.
 *
 * **This hook is display only.** `chatStore.streamingText` remains the truth and
 * is what `pushSpeech` reads, so the voice starts on the first finished sentence
 * regardless of how much of it has been drawn. Wiring speech to the *typed*
 * text instead would put an animation in front of the microphone, which is the
 * opposite of what was asked for.
 *
 * Not to be confused with `useStreamingText.ts`, which takes a finished string
 * and replays it, is reachable only from `src/legacy/`, and cannot consume a
 * stream at all.
 *
 * @param text  the full text so far — append-only within a reply, reset between
 * @param done  whether the stream has closed; finished text is never held back
 */
export function useTypedText(text: string, done: boolean): string {
  const prefersReducedMotion = useIsReducedMotion();
  const [revealed, setRevealed] = useState(text.length);
  const revealedRef = useRef(revealed);
  revealedRef.current = revealed;

  // The target is read from a ref inside the loop, never from the effect's
  // closure. **This is the whole reason the loop is shaped this way.** Keying
  // the effect on `text` instead means every arriving token tears down the
  // pending `requestAnimationFrame` and schedules a fresh one — and tokens from
  // a local model routinely arrive closer together than one 16 ms frame, so the
  // frame is cancelled before it ever fires and *nothing is revealed at all*
  // until the stream pauses. The reveal would then snap in whole at `done`,
  // which looks exactly like the animation not working, and no test of the
  // reveal arithmetic could see it.
  const targetRef = useRef(text.length);
  targetRef.current = text.length;

  const immediate = revealAll(prefersReducedMotion, done);

  useEffect(() => {
    if (immediate) return;

    let frame = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const elapsed = now - last;
      last = now;
      const target = targetRef.current;
      const current = revealedRef.current;
      // Shorter than what is shown means a new reply took the slot. Snapping
      // back is correct: the previous answer is already committed to the
      // transcript, and typing it again under the new one would show it twice.
      const next = nextRevealed(current, target, elapsed);
      if (next !== current) {
        revealedRef.current = next;
        setRevealed(next);
      }
      // One loop for the whole reply rather than one per token. It ends with
      // the stream, when `immediate` flips and this effect is cleaned up.
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [immediate]);

  return immediate ? text : text.slice(0, revealed);
}
